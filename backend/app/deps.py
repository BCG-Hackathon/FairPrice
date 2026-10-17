"""FastAPI dependencies. Everything hangs off app.state so tests can swap implementations."""

import secrets
from typing import Annotated

from fastapi import Depends, Header, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.config import Settings
from app.db import get_db
from app.services.channels import ChannelContext
from app.services.sms_gateway import SmsGateway
from app.services.transport import TransportProvider


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_transport(request: Request) -> TransportProvider:
    return request.app.state.transport


def get_sms_gateway(request: Request) -> SmsGateway:
    return request.app.state.sms_gateway


DbSession = Annotated[Session, Depends(get_db)]
AppSettings = Annotated[Settings, Depends(get_settings)]
Transport = Annotated[TransportProvider, Depends(get_transport)]
Gateway = Annotated[SmsGateway, Depends(get_sms_gateway)]


def get_channel_context(db: DbSession, settings: AppSettings, transport: Transport) -> ChannelContext:
    return ChannelContext(db=db, settings=settings, transport=transport)


ChannelCtx = Annotated[ChannelContext, Depends(get_channel_context)]


def require_admin(
    settings: AppSettings,
    x_admin_token: Annotated[str | None, Header()] = None,
) -> None:
    if not x_admin_token or not secrets.compare_digest(x_admin_token, settings.admin_token):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or missing X-Admin-Token")
