"""Tourism card route helpers.

Kept separate from main.py while the existing API endpoints remain stable.
The application entrypoint can include these routes after validation.
"""

from fastapi import APIRouter, HTTPException

from .tourism_api import build_tourism_card

router = APIRouter(prefix="/api/tourism", tags=["tourism"])


@router.post("/card")
def create_tourism_card(place: dict):
    """Build a frontend-ready tourism card from a normalized POI record.

    This development endpoint does not replace database-backed POI queries yet.
    """
    if not isinstance(place, dict):
        raise HTTPException(status_code=422, detail="POI payload must be an object")
    return build_tourism_card(place)
