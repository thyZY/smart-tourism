"""Tourism metadata helpers.

Keeps tourism semantics separate from existing spatial query code.
The next API layer can use this module after database migration.
"""

DEFAULT_METADATA = {
    "visit_duration": None,
    "indoor": None,
    "tags": [],
    "description": "",
    "best_time": "",
}


def normalize_tourism_metadata(row: dict) -> dict:
    """Return stable frontend fields even when old POIs have no metadata."""
    result = dict(DEFAULT_METADATA)
    result.update(row or {})
    if result["tags"] is None:
        result["tags"] = []
    return result
