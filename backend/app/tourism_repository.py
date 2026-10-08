"""Read tourism attributes from the *actual* places table.

Using to_jsonb(p) allows the endpoint to survive before an optional
metadata migration has run; absent fields remain null/empty, never invented.
"""
from .tourism_api import build_tourism_card

TOURISM_QUERY = """
SELECT
    p.id, p.name, p.category, p.address,
    to_jsonb(p)->>'visit_duration' AS visit_duration,
    to_jsonb(p)->>'indoor' AS indoor,
    to_jsonb(p)->'tags' AS tags,
    to_jsonb(p)->>'description' AS description,
    to_jsonb(p)->>'best_time' AS best_time
FROM places AS p
WHERE p.id = %s;
"""


def fetch_tourism_place(cursor, place_id: int) -> dict | None:
    cursor.execute(TOURISM_QUERY, (place_id,))
    row = cursor.fetchone()
    if row is None:
        return None
    return {
        "id": row[0],
        "name": row[1],
        "category": row[2],
        "address": row[3],
        "visit_duration": int(row[4]) if row[4] is not None else None,
        "indoor": None if row[5] is None else row[5] == "true",
        "tags": row[6] if isinstance(row[6], list) else [],
        "description": row[7] or "",
        "best_time": row[8] or "",
    }


def build_card_from_cursor(cursor, place_id: int) -> dict | None:
    place = fetch_tourism_place(cursor, place_id)
    return None if place is None else build_tourism_card(place)
