"""USSD and SMS conversation handling.

SMS keywords (case-insensitive) are shortcuts for confident users; anything else
continues the same numbered menu used by USSD.

    MENU                               start the numbered menu
    PRICE MAIZE [GULU]                 price of one crop
    CHECK MAIZE 700 [200] [LIRA] [B]   is this offer fair? (qty kg, market, grade)
    REPORT MAIZE A 1200 GULU           field price report (group leaders)
    BRIEF | BRIEF ON | BRIEF OFF       weekly brief / subscribe / unsubscribe
    LANG                               change language
    HELP
"""

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.config import Settings
from app.i18n import crop_name, format_short_date, format_ugx, t
from app.models import Channel, Grade, Language, ReportStatus, User, UssdSession
from app.services import catalog
from app.services.briefs import latest_brief, render_brief
from app.services.menu import DbMenuData, run_menu, trend_text
from app.services.offers import check_offer, offer_message
from app.services.reports import ReportInput, submit_report
from app.services.snapshot import get_snapshot
from app.services.transport import TransportProvider

SMS_MENU_MAX_CHARS = 306
DEFAULT_CHECK_QTY_KG = 100.0
PATH_SEP = "*"


@dataclass(frozen=True)
class ChannelContext:
    db: Session
    settings: Settings
    transport: TransportProvider


def normalize_phone(phone: str) -> str:
    return "".join(ch for ch in phone.strip() if ch.isdigit() or ch == "+")


def get_or_create_user(db: Session, phone: str) -> User:
    user = db.get(User, phone)
    if user is None:
        user = User(phone=phone)
        db.add(user)
        db.flush()
    return user


# ---------- USSD ----------

def handle_ussd(ctx: ChannelContext, session_id: str, phone: str, text: str) -> str:
    """Return an Africa's Talking USSD response ('CON ...' keeps the session open, 'END ...' closes it)."""
    db = ctx.db
    user = get_or_create_user(db, normalize_phone(phone))
    session = db.get(UssdSession, session_id)
    if session is None:
        session = UssdSession(session_id=session_id, phone=user.phone, language_at_start=user.language)
        db.add(session)

    inputs = text.split(PATH_SEP) if text else []
    reply = run_menu(inputs, session.language_at_start, DbMenuData(db, ctx.settings))
    if reply.save_language:
        user.language = reply.save_language
    db.commit()
    return f"{'END' if reply.end else 'CON'} {reply.text}"


# ---------- SMS ----------

def handle_sms(ctx: ChannelContext, phone: str, text: str) -> str:
    db = ctx.db
    user = get_or_create_user(db, normalize_phone(phone))
    tokens = text.strip().upper().split()
    command = tokens[0] if tokens else ""

    match command:
        case "MENU":
            user.sms_menu_path = ""
            reply = _continue_menu(ctx, user, None)
        case "LANG" | "LANGUAGE":
            user.sms_menu_path = "0" if user.language else ""
            reply = _continue_menu(ctx, user, None)
        case "HELP":
            reply = t(user.language, "help")
        case "PRICE":
            reply = _price(ctx, user, tokens[1:])
        case "CHECK" | "OFFER":
            reply = _check(ctx, user, tokens[1:])
        case "REPORT":
            reply = _report(ctx, user, tokens[1:])
        case "BRIEF":
            reply = _brief(user, tokens[1:], db)
        case _ if command.isdigit():
            reply = _continue_menu(ctx, user, command)
        case _ if user.language is None:  # first contact with any text: start at the language picker
            user.sms_menu_path = ""
            reply = _continue_menu(ctx, user, None)
        case _:
            reply = t(user.language, "help")
    db.commit()
    return reply


def _continue_menu(ctx: ChannelContext, user: User, step: str | None) -> str:
    path = [p for p in user.sms_menu_path.split(PATH_SEP) if p]
    if step is not None:
        path.append(step)
    language_before = user.language
    reply = run_menu(path, language_before, DbMenuData(ctx.db, ctx.settings, SMS_MENU_MAX_CHARS))
    if reply.save_language:
        user.language = reply.save_language
        if language_before is None and path:
            path = path[1:]  # language step is consumed; later steps run with the saved language
    user.sms_menu_path = "" if reply.end else PATH_SEP.join(path)
    return reply.text


def _price(ctx: ChannelContext, user: User, args: list[str]) -> str:
    lang = user.language
    if not args:
        return t(lang, "error.format", example="PRICE MAIZE GULU")
    crop = catalog.match_crop(ctx.db, args[0])
    if crop is None:
        return t(lang, "error.crop", value=args[0])
    market_code = args[1] if len(args) > 1 else ctx.settings.default_market_code
    market = catalog.match_market(ctx.db, market_code)
    if market is None:
        return t(lang, "error.market", value=market_code)
    snapshot = get_snapshot(ctx.db, market.id, crop.id)
    if snapshot is None:
        return t(lang, "prices.none", market=market.name)
    return t(
        lang,
        "price.single",
        crop=crop_name(lang, crop.code),
        market=market.name,
        a=format_ugx(snapshot.price_a),
        b=format_ugx(snapshot.price_b),
        trend=trend_text(lang or Language.EN, snapshot.change_pct, ctx.settings.trend_flat_band_pct),
        date=format_short_date(snapshot.as_of),
    )


def _check(ctx: ChannelContext, user: User, args: list[str]) -> str:
    lang = user.language
    example = "CHECK MAIZE 700 200"
    offer = _parse_number(args[1]) if len(args) >= 2 else None
    if offer is None:
        return t(lang, "error.format", example=example)
    crop = catalog.match_crop(ctx.db, args[0])
    if crop is None:
        return t(lang, "error.crop", value=args[0])

    quantity, grade, market = DEFAULT_CHECK_QTY_KG, Grade.A, None
    for arg in args[2:]:
        if (number := _parse_number(arg)) is not None:
            quantity = number
        elif arg in (Grade.A.value, Grade.B.value):
            grade = Grade(arg)
        else:
            market = catalog.match_market(ctx.db, arg)
            if market is None:
                return t(lang, "error.market", value=arg)

    origin = catalog.get_kiosk(ctx.db, user.home_kiosk_code or ctx.settings.default_kiosk_code)
    if origin is None:
        return t(lang, "error.format", example=example)
    result = check_offer(
        ctx.db,
        crop=crop,
        grade=grade,
        offer_per_kg=offer,
        quantity_kg=quantity,
        origin=origin,
        market=market,
        transport=ctx.transport,
        settings=ctx.settings,
    )
    if result is None:
        return t(lang, "prices.none", market=market.name if market else "")
    return offer_message(lang, result)


def _report(ctx: ChannelContext, user: User, args: list[str]) -> str:
    lang = user.language
    example = "REPORT MAIZE A 1200 GULU"
    price = _parse_number(args[2]) if len(args) == 4 else None
    if price is None or args[1] not in (Grade.A.value, Grade.B.value):
        return t(lang, "error.format", example=example)
    crop = catalog.match_crop(ctx.db, args[0])
    if crop is None:
        return t(lang, "error.crop", value=args[0])
    market = catalog.match_market(ctx.db, args[3])
    if market is None:
        return t(lang, "error.market", value=args[3])

    report, _ = submit_report(
        ctx.db,
        ReportInput(
            reporter_phone=user.phone,
            channel=Channel.SMS,
            crop=crop,
            market=market,
            grade=Grade(args[1]),
            price_ugx_per_kg=price,
        ),
        ctx.settings,
    )
    text = t(
        lang,
        "report.received",
        crop=crop_name(lang, crop.code),
        grade=report.grade.value,
        price=format_ugx(report.price_ugx_per_kg),
        market=market.name,
    )
    if report.status != ReportStatus.ACCEPTED:
        text += t(lang, "report.review")
    return text


def _brief(user: User, args: list[str], db: Session) -> str:
    if args and args[0] in ("ON", "OFF"):
        user.brief_subscribed = args[0] == "ON"
        return t(user.language, "brief.subscribed" if user.brief_subscribed else "brief.unsubscribed")
    return render_brief(latest_brief(db), user.language)


def _parse_number(value: str) -> float | None:
    """Positive number from SMS text, accepting thousands separators ('1,200')."""
    try:
        number = float(value.replace(",", ""))
    except ValueError:
        return None
    return number if number > 0 else None
