from typing import Annotated
from fastapi import APIRouter, Header
from sqlalchemy import select
from app.deps import DbSession, AppSettings
from app.models import SourceRefreshRun
from app.api.buyers import secure_admin
from app.services.source_refresh import refresh_source

router=APIRouter(prefix="/api/source",tags=["source automation"])


@router.get("/status")
def status(db: DbSession, settings: AppSettings):
    row=db.scalar(select(SourceRefreshRun).order_by(SourceRefreshRun.id.desc()).limit(1))
    return {"enabled":settings.source_refresh_enabled,"interval_seconds":settings.source_refresh_seconds,
            "latest": {"status":row.status,**row.details} if row else None,
            "notice":"Checks published observations. It cannot invent newer data. Model forecasts are not retrained by a source refresh."}


@router.post("/refresh")
def refresh(db: DbSession, settings: AppSettings, x_admin_token: Annotated[str | None,Header()]=None):
    secure_admin(settings,x_admin_token)
    return refresh_source(db,settings)
