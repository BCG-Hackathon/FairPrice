from datetime import date
from decimal import Decimal
import pytest
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.services.catalog import catalogue, prices
from backend.app.services.pricing import grade_prices

client = TestClient(app)


def test_grade_policy_and_rounding():
    assert grade_prices(2000) == {"A": 2080, "B": 2000, "C": 1890}
    assert grade_prices(100) == {"A": 104, "B": 100, "C": 95}
    assert grade_prices(Decimal("2750")) == {"A": 2860, "B": 2750, "C": 2599}


@pytest.mark.parametrize("bad", [0, -1, float("nan"), float("inf"), True])
def test_invalid_base_not_a_price(bad):
    with pytest.raises(ValueError):
        grade_prices(bad)


def test_real_catalogue_and_assets():
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


def test_sms_matches_kiosk_and_does_not_send():
    for crop in catalogue()["crops"]:
        row = prices(crop["id"])["rows"][0]
        for grade in "ABC":
            reply = client.post("/api/sms/preview", json={
                "crop": crop["id"], "market": row["market"], "grade": grade}).json()
            assert reply["sent"] is False
            assert str(row["grade_prices"][grade]) in reply["message"]
            assert row["last_month"] in reply["message"]


def test_unavailable_and_invalid_input():
    assert client.get("/api/prices/mango").status_code == 404
    assert client.get("/api/prices/beans?market=Missing").status_code == 404
    assert client.post("/api/sms/preview", json={"crop": "beans", "market": "Gulu", "grade": "D"}).status_code == 422
    assert client.get("/").status_code == 200
    assert client.get("/health").json()["mode"] == "published_snapshot"


def test_training_scores_have_limits():
    response = client.get("/api/training").json()
    assert response["metrics"]["overall"]["rows"] == 626
    assert any("centred outlier" in s for s in response["limitations"])
