"""Example tourism card payloads used for local development and UI validation.

This file intentionally contains sample structures only. Production data should come
from PostGIS and the tourism metadata table.
"""

SAMPLE_TOURISM_CARD = {
    "name": "南京博物院",
    "category": "博物馆",
    "visit_duration": 180,
    "indoor": True,
    "tags": ["历史", "文化", "展览"],
    "description": "历史文化类展览场馆示例。",
    "best_time": "全年",
}
