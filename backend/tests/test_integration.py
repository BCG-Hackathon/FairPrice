from datetime import date
from decimal import Decimal
import pytest
from fastapi.testclient import TestClient
from app.main import create_app
from app.config import Settings
from app.services.published import catalogue, prices
from app.services.grade_policy import grade_prices

@pytest.fixture
def client():
    with TestClient(create_app(Settings(database_url="sqlite://", data_mode="published", _env_file=None))) as c:
        yield c


def test_grade_policy_and_rounding():
    assert grade_prices(2000) == {"A": 2080, "B": 2000, "C": 1890}
    assert grade_prices(100) == {"A": 104, "B": 100, "C": 95}
    assert grade_prices(Decimal("2750")) == {"A": 2860, "B": 2750, "C": 2599}


@pytest.mark.parametrize("bad", [0, -1, float("nan"), float("inf"), True])
def test_invalid_base_not_a_price(bad):
    with pytest.raises(ValueError):
        grade_prices(bad)


def test_real_catalogue_and_assets(client):
    data = client.get("/api/crops").json()
    assert {c["id"] for c in data["crops"]} == {
        "beans", "maize", "sorghum", "millet", "cassava_fresh", "leafy_vegetables"}
    for crop in data["crops"]:
        assert client.get(crop["image"]).status_code == 200
        rows = client.get("/api/prices/" + crop["id"]).json()["rows"]
        assert set(crop["markets"]) == {r["market"] for r in rows}
        assert len(rows) == len({r["market"] for r in rows})
        for row in rows:
            assert row["grade_prices"] == grade_prices(row["market_price"])
            assert row["last_month"] <= data["data_end"]


def test_staleness_uses_calendar_not_dataset_end():
    row = prices("beans", "Gulu", today=date(2026, 11, 1))["rows"][0]
    assert row["last_month"] == "2026-04"
    assert row["age_months"] == 7
    assert row["stale"] is True
    assert row["forecast_is_past"] is True


def test_sms_matches_kiosk_and_does_not_send(client):
    for crop in catalogue()["crops"]:
        row = prices(crop["id"])["rows"][0]
        for grade in "ABC":
            reply = client.post("/api/sms/preview", json={
                "crop": crop["id"], "market": row["market"], "grade": grade}).json()
            assert reply["sent"] is False
            assert str(row["grade_prices"][grade]) in reply["message"]
            assert row["last_month"] in reply["message"]


def test_unavailable_and_invalid_input(client):
    assert client.get("/api/prices/mango").status_code == 404
    assert client.get("/api/prices/beans?market=Missing").status_code == 404
    assert client.post("/api/sms/preview", json={"crop": "beans", "market": "Gulu", "grade": "D"}).status_code == 422
    assert client.get("/").status_code == 200
    assert client.get("/api/kiosk/status").json()["mode"] == "published_snapshot"


def test_training_scores_have_limits(client):
    response = client.get("/api/training").json()
    assert response["metrics"]["overall"]["rows"] == 626
    assert any("centred outlier" in s for s in response["limitations"])


def test_teammate_database_api_matches_public_kiosk(client):
    legacy = client.get("/api/v1/prices/snapshot?market=GULU").json()["items"]
    kiosk = client.get("/api/prices/beans?market=Gulu").json()["rows"][0]
    beans = next(r for r in legacy if r["crop_code"] == "beans")
    assert {"A": beans["price_a"], "B": beans["price_b"], "C": beans["price_c"]} == kiosk["grade_prices"]
    assert beans["as_of"][:7] == kiosk["last_month"]
    assert beans["data_source"] == "wfp_snapshot"
    assert {c["code"] for c in client.get("/api/v1/crops").json()} == {c["id"] for c in catalogue()["crops"]}
    assert client.post("/api/v1/channels/sms", data={"from": "test", "text": "hello"}).status_code == 404
