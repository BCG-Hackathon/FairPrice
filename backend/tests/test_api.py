import io

from sqlalchemy import select

from app.models import FieldReport, ReportStatus, User
from tests.conftest import ADMIN

PHONE = "+256711111111"


def ussd(client, text, session="s1", phone=PHONE):
    return client.post("/api/v1/channels/ussd", data={"sessionId": session, "phoneNumber": phone, "text": text}).text


def sms(client, text, phone=PHONE):
    return client.post("/api/v1/channels/sms", data={"from": phone, "text": text}).json()["reply"]


def test_health_and_status(client):
    assert client.get("/health").json() == {"status": "ok"}
    body = client.get("/api/v1/status").json()
    assert body["snapshot_generated_at"].endswith("Z")
    assert body["sources"][0]["source"] == "seed"


def test_snapshot_has_prices_trends_and_etag(client):
    r = client.get("/api/v1/prices/snapshot", params={"market": "GULU", "kiosk": "AWACH"})
    assert r.status_code == 200
    item = r.json()["items"][0]
    assert item["price_b"] < item["price_a"]
    assert item["trend"] in {"up", "down", "flat"}
    assert 0 < item["fair_farm_gate_a"] < item["price_a"]

    again = client.get(
        "/api/v1/prices/snapshot",
        params={"market": "GULU", "kiosk": "AWACH"},
        headers={"If-None-Match": r.headers["ETag"]},
    )
    assert again.status_code == 304


def test_history_and_compare(client):
    history = client.get("/api/v1/prices/history", params={"crop": "maize", "market": "GULU", "weeks": 8}).json()
    assert len(history["points"]) >= 7
    compare = client.get("/api/v1/prices/compare", params={"crop": "maize", "kiosk": "AWACH", "quantity_kg": 200}).json()
    prices = [o["fair_farm_gate_price"] for o in compare["options"]]
    assert prices == sorted(prices, reverse=True)


def test_offer_check_flags_low_ball(client):
    body = {"crop_code": "maize", "offer_ugx_per_kg": 300, "quantity_kg": 200, "kiosk_code": "AWACH", "market_code": "GULU"}
    r = client.post("/api/v1/offers/check", json=body).json()
    assert r["verdict"] == "very_low"
    assert r["total_loss_ugx"] > 0
    assert "VERY LOW" in r["message"]


def test_ussd_language_saved_once(client, db):
    assert ussd(client, "").startswith("CON FairPrice\n1. English")
    assert "Matunda" in ussd(client, "2")
    assert ussd(client, "2*2").startswith("CON Chagua soko")
    final = ussd(client, "2*2*1")
    assert final.startswith("END Gulu") and "Imesasishwa" in final
    assert db.get(User, PHONE).language == "sw"
    # New session: no language prompt
    assert "Matunda" in ussd(client, "", session="s2")


def test_ussd_response_fits_limit(client):
    ussd(client, "1", session="x")
    assert len(ussd(client, "1*2*1", session="x").removeprefix("END ")) <= 182


def test_sms_menu_and_keywords(client):
    assert "1. English" in sms(client, "hello")
    assert "Fruits" in sms(client, "1")
    assert "Choose market" in sms(client, "1")
    assert "Updated" in sms(client, "1")
    assert "UGX/kg" in sms(client, "PRICE maize lira")
    assert "VERY LOW" in sms(client, "CHECK MAIZE 300 200 GULU")
    assert "week to" in sms(client, "BRIEF")
    assert "stopped" in sms(client, "BRIEF OFF")
    assert "Crop not found" in sms(client, "PRICE rice")


def test_sms_report_from_trusted_reporter_is_accepted(client, db):
    gulu_maize = client.get("/api/v1/prices/snapshot", params={"market": "GULU"}).json()["items"]
    price = next(i["price_a"] for i in gulu_maize if i["crop_code"] == "maize")
    reply = sms(client, f"REPORT MAIZE A {int(price)} GULU", phone="+256700000001")
    assert "Thank you" in reply and "checked" not in reply
    assert db.scalar(select(FieldReport)).status == ReportStatus.ACCEPTED


def test_kiosk_batch_reports_are_idempotent_and_flag_outliers(client):
    batch = {
        "reports": [
            {"client_ref": "tab1-001", "reporter_phone": "kiosk-awach", "crop_code": "maize", "market_code": "GULU", "grade": "A", "price_ugx_per_kg": 99999},
            {"client_ref": "tab1-002", "reporter_phone": "kiosk-awach", "crop_code": "rice", "market_code": "GULU", "grade": "A", "price_ugx_per_kg": 1000},
        ]
    }
    first = client.post("/api/v1/reports", json=batch).json()["results"]
    assert first[0]["created"] and first[0]["status"] == "flagged"
    assert first[1]["error"] == "unknown crop_code"
    second = client.post("/api/v1/reports", json=batch).json()["results"]
    assert second[0]["created"] is False


def test_admin_requires_token(client):
    assert client.post("/api/v1/admin/refresh").status_code == 401
    assert client.post("/api/v1/admin/refresh", headers=ADMIN).json()["snapshots"] == 48


def test_admin_imports_prices_and_forecasts(client):
    prices = "market_code,crop_code,observed_on,price,currency,unit_kg,source\nKISUMU,maize,2099-01-05,50,KES,1,kamis\nGULU,nope,2099-01-05,1,UGX,1,x\n"
    r = client.post("/api/v1/admin/prices/import", headers=ADMIN, files={"file": ("p.csv", io.BytesIO(prices.encode()))}).json()
    assert r["created"] == 1 and len(r["errors"]) == 1

    forecasts = "market_code,crop_code,period_start,predicted_ugx_per_kg,lower,upper,model_version\nKISUMU,maize,2099-01-12,1500,1400,1600,lgbm-v1\n"
    client.post("/api/v1/admin/forecasts/import", headers=ADMIN, files={"file": ("f.csv", io.BytesIO(forecasts.encode()))})
    client.post("/api/v1/admin/refresh", headers=ADMIN)
    item = next(
        i for i in client.get("/api/v1/prices/snapshot", params={"market": "KISUMU"}).json()["items"] if i["crop_code"] == "maize"
    )
    assert item["price_a"] == round(50 * 28.5)  # KES converted to UGX
    assert item["forecast_source"] == "model:lgbm-v1"


def test_brief_generate_and_broadcast(client):
    sms(client, "1")  # choose English -> subscribed by default
    assert client.post("/api/v1/admin/briefs/generate", headers=ADMIN).status_code == 200
    result = client.post("/api/v1/admin/briefs/broadcast", headers=ADMIN).json()
    assert result["sent"] >= 1
    assert client.get("/api/v1/briefs/latest", params={"lang": "sw"}).json()["text"].startswith("FairPrice wiki")
