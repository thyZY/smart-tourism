from fastapi import APIRouter
from pydantic import BaseModel, Field

from .itinerary_planner import ItineraryPlanner

router = APIRouter(prefix="/api/ai/itinerary", tags=["AI Itinerary"])


class ItineraryRequest(BaseModel):
    location: str = Field(..., description="目标旅游区域")
    days: int = Field(default=1, ge=1, le=14)
    style: str = Field(default="历史文化")
    people: str = Field(default="普通游客")
    walking_limit: str = Field(default="中等")


@router.post("/generate")
def generate_itinerary(request: ItineraryRequest):
    planner = ItineraryPlanner()
    return planner.generate(
        location=request.location,
        days=request.days,
        style=request.style,
        people=request.people,
        walking_limit=request.walking_limit,
    )
