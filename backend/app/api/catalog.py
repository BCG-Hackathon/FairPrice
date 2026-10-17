import json
from functools import lru_cache
from pathlib import Path

from fastapi import APIRouter, HTTPException, status

from app.deps import DbSession
from app.models import Category
from app.schemas import CropOut, GradeStandardsOut, KioskOut, MarketOut
from app.services import catalog

router = APIRouter(tags=["catalog"])

GRADE_STANDARDS_FILE = Path(__file__).resolve().parent.parent / "content" / "grade_standards.json"


@lru_cache
def _grade_standards() -> dict:
    return json.loads(GRADE_STANDARDS_FILE.read_text(encoding="utf-8"))


@router.get("/crops", response_model=list[CropOut])
def list_crops(db: DbSession, category: Category | None = None):
    return catalog.list_crops(db, category)


@router.get("/markets", response_model=list[MarketOut])
def list_markets(db: DbSession):
    return catalog.list_markets(db)


@router.get("/kiosks", response_model=list[KioskOut])
def list_kiosks(db: DbSession):
    return catalog.list_kiosks(db)


@router.get(
    "/crops/{crop_code}/grades",
    response_model=GradeStandardsOut,
    summary="Category A vs B visual standards for a crop",
)
def get_grade_standards(crop_code: str) -> GradeStandardsOut:
    standards = _grade_standards().get(crop_code.lower())
    if standards is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"No grade standards for {crop_code!r}")
    return GradeStandardsOut(crop_code=crop_code.lower(), **standards)
