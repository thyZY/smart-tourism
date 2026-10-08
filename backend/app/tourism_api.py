"""Tourism response helpers.

This module keeps API presentation logic separate from the existing spatial
query endpoints. It will be wired into FastAPI routes after the database
metadata migration is validated.
"""

from .tourism_metadata import normalize_tourism_metadata


def build_tourism_card(place: dict) -> dict:
    """Create a stable tourism card payload from a POI record."""
    metadata = normalize_tourism_metadata(place)
    return {
        "id": place.get("id"),
        "name": place.get("name", ""),
        "category": place.get("category", ""),
        "address": place.get("address", ""),
        "visit_duration": metadata["visit_duration"],
        "indoor": metadata["indoor"],
        "tags": metadata["tags"],
        "description": metadata["description"],
        "best_time": metadata["best_time"],
    }


def build_tourism_collection(places: list[dict]) -> list[dict]:
    """Convert multiple POIs into frontend-ready tourism cards."""
    return [build_tourism_card(place) for place in places]
