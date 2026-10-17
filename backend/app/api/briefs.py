from fastapi import APIRouter, HTTPException, status

from app.deps import DbSession
from app.models import Language, MarketBrief
from app.schemas import BriefItem, BriefOut
from app.services.briefs import latest_brief, render_brief

router = APIRouter(prefix="/briefs", tags=["weekly brief"])


def brief_out(brief: MarketBrief, lang: Language) -> BriefOut:
    return BriefOut(
        generated_at=brief.generated_at,
        period_end=brief.period_end,
        language=lang,
        items=[BriefItem(**item) for item in brief.items],
        text=render_brief(brief, lang),
    )


@router.get("/latest", response_model=BriefOut, summary="Latest weekly market brief (structured + SMS text)")
def get_latest(db: DbSession, lang: Language = Language.EN) -> BriefOut:
    brief = latest_brief(db)
    if brief is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No weekly brief generated yet")
    return brief_out(brief, lang)
