"""Callbacks for Africa's Talking (form-encoded payloads), also used by the in-app phone simulator."""

from typing import Annotated

from fastapi import APIRouter, Form, Query
from fastapi.responses import PlainTextResponse

from app.deps import ChannelCtx, DbSession, Gateway
from app.schemas import OutboxItem, SmsReply
from app.services.channels import handle_sms, handle_ussd, normalize_phone
from app.services.sms_gateway import deliver, outbox_for

router = APIRouter(prefix="/channels", tags=["sms & ussd"])


@router.post("/ussd", response_class=PlainTextResponse, summary="USSD callback: returns 'CON ...' or 'END ...'")
def ussd(
    ctx: ChannelCtx,
    session_id: Annotated[str, Form(alias="sessionId", max_length=100)],
    phone_number: Annotated[str, Form(alias="phoneNumber", max_length=20)],
    service_code: Annotated[str, Form(alias="serviceCode")] = "",
    text: Annotated[str, Form()] = "",
) -> str:
    return handle_ussd(ctx, session_id, phone_number, text)


@router.post("/sms", response_model=SmsReply, summary="Inbound SMS: menu or keyword command; reply is sent via the gateway")
def sms(
    ctx: ChannelCtx,
    gateway: Gateway,
    from_: Annotated[str, Form(alias="from", max_length=20)],
    text: Annotated[str, Form(max_length=480)] = "",
) -> SmsReply:
    phone = normalize_phone(from_)
    reply = handle_sms(ctx, phone, text)
    entry = deliver(ctx.db, gateway, phone, reply)
    return SmsReply(reply=reply, outbox_id=entry.id)


@router.get("/sms/outbox", response_model=list[OutboxItem], summary="Recent SMS sent to a phone (simulator / audit)")
def sms_outbox(db: DbSession, phone: str, limit: Annotated[int, Query(ge=1, le=100)] = 20):
    return outbox_for(db, normalize_phone(phone), limit)
