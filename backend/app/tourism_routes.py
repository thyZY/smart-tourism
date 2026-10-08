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
    """Return a stable tourism card placeholder for a POI id.

    Database binding is intentionally isolated until the migration is deployed.
    The response schema is fixed so the frontend can be developed first.
    """
    if place_id <= 0:
        raise HTTPException(status_code=422, detail="POI id must be positive")

    # TODO: replace with PostGIS query after tourism metadata migration.
    return build_tourism_card({"id": place_id})
