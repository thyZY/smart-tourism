"""Tourism API routes.

The routes stay separate from spatial endpoints and provide frontend-ready
travel information cards.
"""

from fastapi import APIRouter, HTTPException

from .tourism_api import build_tourism_card

router = APIRouter(prefix="/api/tourism", tags=["tourism"])


@router.post("/card")
def create_tourism_card(place: dict):
    """Build a frontend-ready tourism card from a normalized POI record."""
    if not isinstance(place, dict):
        raise HTTPException(status_code=422, detail="POI payload must be an object")
    return build_tourism_card(place)


@router.get("/places/{place_id}")
def get_tourism_place(place_id: int):
    """Return a tourism card for a POI id.

    The SQL repository is separated from this route. Database connection
    injection will be wired with the existing FastAPI connection helper in the
    next integration commit.
    """
    if place_id <= 0:
        raise HTTPException(status_code=422, detail="POI id must be positive")

    return build_tourism_card({"id": place_id})
