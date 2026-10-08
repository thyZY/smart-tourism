"""Database access helpers for tourism metadata.

This module isolates SQL access from FastAPI routes. It is intentionally
small so the existing spatial endpoints remain unchanged while tourism
attributes are introduced incrementally.
"""

from .tourism_api import build_tourism_card


TOURISM_QUERY = """
SELECT
    id,
    name,
    category,
    address
FROM places
WHERE id = %s;
"""


def fetch_tourism_place(cursor, place_id: int) -> dict | None:
    """Fetch the base POI record used to build a tourism card.

    The current schema keeps metadata optional. Once the migration is applied,
    additional tourism columns can be selected here without changing the API
    contract.
    """
    cursor.execute(TOURISM_QUERY, (place_id,))
    row = cursor.fetchone()
    if row is None:
        return None

    return {
        "id": row[0],
        "name": row[1],
        "category": row[2],
        "address": row[3],
    }


def build_card_from_cursor(cursor, place_id: int) -> dict | None:
    place = fetch_tourism_place(cursor, place_id)
    if place is None:
        return None
    return build_tourism_card(place)
