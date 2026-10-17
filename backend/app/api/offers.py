from fastapi import APIRouter, HTTPException, status

from app.api.prices import option_out, require_crop, require_kiosk, require_market
from app.deps import AppSettings, DbSession, Transport
from app.schemas import OfferCheckIn, OfferCheckOut
from app.services.offers import check_offer, offer_message

router = APIRouter(prefix="/offers", tags=["offers"])


@router.post(
    "/check",
    response_model=OfferCheckOut,
    summary="Offer Check: is a broker's offer fair compared to the market price?",
)
def check(body: OfferCheckIn, db: DbSession, settings: AppSettings, transport: Transport) -> OfferCheckOut:
    crop = require_crop(db, body.crop_code)
    origin = require_kiosk(db, body.kiosk_code)
    market = require_market(db, body.market_code) if body.market_code else None
    result = check_offer(
        db,
        crop=crop,
        grade=body.grade,
        offer_per_kg=body.offer_ugx_per_kg,
        quantity_kg=body.quantity_kg,
        origin=origin,
        market=market,
        transport=transport,
        settings=settings,
    )
    if result is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No current price for this crop and market")

    message = offer_message(body.language, result)

    return OfferCheckOut(
        verdict=result.assessment.verdict,
        offer_ugx_per_kg=body.offer_ugx_per_kg,
        fair_price_ugx_per_kg=result.assessment.fair_price,
        pct_of_fair=result.assessment.pct_of_fair,
        gap_per_kg=round(result.assessment.gap_per_kg),
        total_loss_ugx=round(result.total_loss),
        quantity_kg=body.quantity_kg,
        reference=option_out(result.reference, body.quantity_kg),
        best=option_out(result.best, body.quantity_kg),
        message=message,
    )
