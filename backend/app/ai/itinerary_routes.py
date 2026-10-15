"""AI itinerary API: verified database records only."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from .itinerary_geo_service import fetch_candidates
from .itinerary_planner import ItineraryPlanner

router = APIRouter(prefix="/api/ai/itinerary", tags=["AI Itinerary"])


class ItineraryRequest(BaseModel):
    location: str = Field(..., min_length=1, max_length=160, description="行程需求及目标区域")
    days: int = Field(default=1, ge=1, le=1, description="第一版仅支持单日")
    style: str = Field(default="历史文化", max_length=80)
    people: str = Field(default="普通游客", max_length=80)
    walking_limit: str = Field(default="中等", max_length=80)
    max_stops: int = Field(default=4, ge=2, le=6)
    travel_mode: str = Field(default="pedestrian", pattern="^(pedestrian|bicycle|auto)$")


@router.post("/generate")
def generate_itinerary(request: ItineraryRequest):
    try:
        candidates = fetch_candidates()
    except Exception as exc:
        raise HTTPException(status_code=503, detail="POI数据库暂不可用") from exc
    if not candidates:
        raise HTTPException(status_code=404, detail="数据库中没有可规划的景点")
    try:
        return ItineraryPlanner().generate(
            location=request.location, days=request.days, style=request.style,
            people=request.people, walking_limit=request.walking_limit,
            candidates=candidates, max_stops=request.max_stops,
            travel_mode=request.travel_mode,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
