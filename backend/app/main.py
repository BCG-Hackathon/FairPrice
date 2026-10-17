"""FastAPI application factory.

Run locally:  uvicorn app.main:app --reload   (from the backend/ folder)
"""

import logging
import asyncio
from contextlib import suppress
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

from app import models  # noqa: F401  (registers tables on Base.metadata)
from app.api import api_router
from app.config import Settings, get_settings
from app.db import Base, build_engine, build_session_factory
from app.seed import seed
from app.services.sms_gateway import OutboxGateway
from app.services.transport import EstimatedTransport
from app.services.published_seed import seed_published
from app.api import kiosk
from app.api import buyers, source_refresh, sms_updates

logger = logging.getLogger("fairprice")


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    logging.basicConfig(level=settings.log_level, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        Base.metadata.create_all(app.state.engine)
        if settings.seed_on_startup:
            with app.state.session_factory() as db:
                if settings.data_mode == "published":
                    seed_published(db, settings)
                else:
                    seed.run(db, settings)
        logger.info("FairPrice API ready (env=%s)", settings.environment)
        task = None
        if settings.data_mode == "published" and settings.source_refresh_enabled:
            async def refresh_loop():
                from app.services.source_refresh import refresh_source
                def run_once():
                    with app.state.session_factory() as db:
                        refresh_source(db,settings)
                while True:
                    await asyncio.to_thread(run_once)
                    await asyncio.sleep(settings.source_refresh_seconds)
            task=asyncio.create_task(refresh_loop())
        yield
        if task:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task
        app.state.engine.dispose()

    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        description=(
            "Ground-truth market prices for smallholder farmers in Northern Uganda. "
            "Serves the kiosk tablet app and the SMS/USSD channels for feature phones."
        ),
        lifespan=lifespan,
    )
    engine = build_engine(settings.database_url)
    app.state.settings = settings
    app.state.engine = engine
    app.state.session_factory = build_session_factory(engine)
    app.state.transport = EstimatedTransport(settings)
    app.state.sms_gateway = OutboxGateway()

    @app.middleware("http")
    async def private_directory_responses(request, call_next):
        response = await call_next(request)
        if request.url.path.startswith(("/api/buyers", "/api/source")):
            response.headers["Cache-Control"] = "no-store"
        return response

    app.add_middleware(GZipMiddleware, minimum_size=500)  # low-bandwidth kiosks
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["ETag"],
    )
    if settings.data_mode == "demo":
        app.include_router(api_router)
    else:
        # Keep synthetic reporting/registry/offer demos out of the public kiosk flow.
        from app.api import catalog, prices, status
        for module in (catalog, prices, status):
            app.include_router(module.router, prefix="/api/v1")
    app.include_router(kiosk.app)
    if settings.data_mode == "published":
        app.include_router(buyers.router)
        app.include_router(source_refresh.router)
        app.include_router(sms_updates.router)
    kiosk.mount_assets(app)

    @app.get("/health", tags=["status"], summary="Liveness probe")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
