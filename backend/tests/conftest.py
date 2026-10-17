from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.config import Settings
from app.main import create_app

ADMIN = {"X-Admin-Token": "test-token"}


@pytest.fixture
def settings() -> Settings:
    return Settings(database_url="sqlite://", admin_token="test-token", seed_on_startup=True, _env_file=None)


@pytest.fixture
def client(settings: Settings) -> Iterator[TestClient]:
    with TestClient(create_app(settings)) as test_client:
        yield test_client


@pytest.fixture
def db(client: TestClient) -> Iterator[Session]:
    with client.app.state.session_factory() as session:
        yield session
