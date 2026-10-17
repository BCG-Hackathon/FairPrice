from fastapi import APIRouter

from app.api import admin, briefs, catalog, channels, offers, prices, reports, status

api_router = APIRouter(prefix="/api/v1")
for module in (status, catalog, prices, offers, reports, briefs, channels, admin):
    api_router.include_router(module.router)
