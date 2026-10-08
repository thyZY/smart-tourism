"""Tourism-aware POI response helpers.

This layer enriches existing GeoJSON records without changing spatial query logic.
It allows old POI records to gradually gain tourism attributes.
"""

from .tourism_metadata import normalize_tourism_metadata


def enrich_place_properties(properties: dict, metadata: dict | None = None) -> dict:
    """Merge stable tourism fields into a POI property dictionary."""
    result = dict(properties or {})
    result.update(normalize_tourism_metadata(metadata))
    return result


def build_tourism_card(place: dict) -> dict:
    """Prepare a frontend-friendly tourism detail card."""
    properties = place.get("properties", {})
    return {
        "name": properties.get("name", ""),
        "category": properties.get("category", ""),
        "visit_duration": properties.get("visit_duration"),
        "indoor": properties.get("indoor"),
        "tags": properties.get("tags", []),
        "description": properties.get("description", ""),
        "best_time": properties.get("best_time", ""),
    }
