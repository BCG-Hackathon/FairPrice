"""Local demo API and original-layout kiosk, served from one origin."""
import json
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from .services.catalog import catalogue, prices, sms_preview, ARTIFACTS

ROOT = Path(__file__).resolve().parents[2]
app = FastAPI(title="FairPrice", version="0.1.0")


@app.get("/health")
def health():
    data = catalogue()
    return {"status": "ok", "data_end": data["data_end"], "crops": len(data["crops"]),
            "mode": "published_snapshot", "sms": "preview_only"}


@app.get("/api/crops")
def crops():
    return catalogue()


@app.get("/api/prices/{crop}")
def price_lookup(crop: str, market: str | None = None):
    try:
        return prices(crop, market)
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc


class SMSPreview(BaseModel):
    crop: str = Field(max_length=60)
    market: str = Field(max_length=120)
    grade: str = Field(default="B", pattern="^[ABC]$")
    language: str = Field(default="en", pattern="^(en|sw)$")


@app.post("/api/sms/preview")
def preview(body: SMSPreview):
    try:
        return sms_preview(body.crop, body.market, body.grade, body.language)
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc


@app.get("/api/training")
def training():
    metrics = json.loads((ARTIFACTS / "metrics.json").read_text())
    return {"metrics": metrics, "serving": "Precomputed team snapshot, not live inference",
            "limitations": [
                "Monthly data ends August 2026; forecasts are historical as of October 2026.",
                "Retail-to-wholesale factors are measured for beans/maize, assumed for four crops.",
                "Raw CSV is not committed: preprocessing cannot yet be reproduced from the original source.",
                "Original ingestion uses a centred outlier filter; historical scores need a causal re-ingestion audit.",
                "The same holdout selects model versus baseline; scores are development evidence, not an independent final test.",
            ]}


@app.get("/")
def kiosk():
    return FileResponse(ROOT / "frontend" / "index.html")


@app.get("/sw.js")
def service_worker():
    return FileResponse(ROOT / "frontend" / "public" / "sw.js", media_type="application/javascript",
                        headers={"Cache-Control": "no-cache"})


app.mount("/assets", StaticFiles(directory=ROOT / "frontend" / "public" / "assets"), name="assets")
app.mount("/static", StaticFiles(directory=ROOT / "frontend" / "src"), name="static")
