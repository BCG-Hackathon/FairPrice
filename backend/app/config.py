"""Application settings, loaded from environment variables or a .env file."""

from functools import lru_cache
from typing import Literal
from pydantic import Field, SecretStr

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "FairPrice API"
    environment: str = "local"
    log_level: str = "INFO"

    # SQLite locally, Azure SQL in prod (mssql+pyodbc://...)
    database_url: str = "sqlite:///./fairprice-published.db"
    seed_on_startup: bool = True
    # Published mode is the user-facing product. Synthetic legacy demos are opt-in.
    data_mode: Literal["published", "demo"] = "published"

    admin_token: str = "change-me"
    cors_origins: list[str] = ["*"]
    source_refresh_enabled: bool = False
    source_refresh_seconds: int = Field(default=86400, ge=300, le=604800)
    buyer_registration_daily_limit: int = Field(default=100, ge=1, le=1000)

    # SMS price updates via BulkSMS (bulksms.com > Settings > API Tokens). Empty = dry run only.
    bulksms_token_id: str = ""
    bulksms_token_secret: SecretStr = SecretStr("")
    bulksms_api_base: str = "https://api.bulksms.com/v1"
    bulksms_max_parts: int = 2  # each SMS part costs credits; update texts fit 2 parts
    # Comma-separated E.164 numbers. When set, SMS only goes to these numbers (testing).
    comms_allowed_recipients: str = ""

    # Defaults for channels
    default_language: str = "en"
    default_market_code: str = "GULU"
    default_kiosk_code: str = "AWACH"

    # Pricing assumptions (documented and configurable)
    fair_trader_margin: float = 0.20  # share of market price a fair trader keeps
    offer_low_threshold: float = 0.85  # offer >= 85% of fair price -> LOW, below -> VERY_LOW
    trend_flat_band_pct: float = 1.0  # |change| below this counts as "flat"
    kes_to_ugx: float = 28.5

    # Transport estimate until Azure Maps is wired in
    transport_ugx_per_kg_km: float = 2.0
    road_factor: float = 1.3  # straight-line km -> road km
    cross_border_ugx_per_kg: float = 150.0

    # Field report validation
    report_outlier_threshold: float = 0.35  # >35% away from current price -> flagged
    field_report_window_days: int = 7


@lru_cache
def get_settings() -> Settings:
    return Settings()
