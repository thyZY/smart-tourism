from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .db import get_db_connection
from .tourism_routes import router as tourism_router
from .ai.router import router as ai_router
from .routing_routes import router as routing_router

app = FastAPI()
app.include_router(tourism_router)
app.include_router(ai_router)
app.include_router(routing_router)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/health")
def health_check():
    return {
        "status": "ok",
        "message": "Smart Tourism API is running"
    }


@app.get("/api/statistics")
def get_statistics():
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("SELECT COUNT(*) FROM places;")
        total_places = cursor.fetchone()[0]

        cursor.execute("""
            SELECT category, COUNT(*) AS place_count
            FROM places
            GROUP BY category
            ORDER BY place_count DESC, category ASC;
        """)
        category_rows = cursor.fetchall()
    finally:
        cursor.close()
        conn.close()

    category_counts = {category: count for category, count in category_rows}
    top_categories = [
        {"category": category, "count": count}
        for category, count in category_rows[:3]
    ]

    return {
        "total_places": total_places,
        "category_counts": category_counts,
        "top_categories": top_categories
    }


@app.get("/api/places")
def get_places(
    q: str | None = None,
    category: str | None = None,
    min_lng: float | None = None,
    min_lat: float | None = None,
    max_lng: float | None = None,
    max_lat: float | None = None
):
    conn = get_db_connection()
    cursor = conn.cursor()

    q = q.strip() if q else None
    category = category.strip() if category else None

    conditions = []
    params = []

    if q:
        conditions.append("(name ILIKE %s OR category ILIKE %s)")
        params.extend([f"%{q}%", f"%{q}%"])

    if category:
        conditions.append("category = %s")
        params.append(category)

    if all(value is not None for value in [min_lng, min_lat, max_lng, max_lat]):
        conditions.append("""
            ST_Within(
                geom,
                ST_MakeEnvelope(%s, %s, %s, %s, 4326)
            )
        """)
        params.extend([min_lng, min_lat, max_lng, max_lat])

    sql = """
        SELECT
            id,
            name,
            category,
            address,
            ST_X(geom) AS lng,
            ST_Y(geom) AS lat
        FROM places
    """

    if conditions:
        sql += " WHERE " + " AND ".join(conditions)

    sql += " ORDER BY id;"

    cursor.execute(sql, params)

    rows = cursor.fetchall()

    cursor.close()
    conn.close()

    features = []

    for row in rows:
        features.append({
            "type": "Feature",
            "properties": {
                "id": row[0],
                "name": row[1],
                "category": row[2],
                "address": row[3]
            },
            "geometry": {
                "type": "Point",
                "coordinates": [row[4], row[5]]
            }
        })

    return {
        "type": "FeatureCollection",
        "features": features
    }

@app.get("/api/places/nearby")
def get_nearby_places(
    lng: float,
    lat: float,
    radius: float = 5000,
    category: str | None = None
):
    category = category.strip() if category else None

    conn = get_db_connection()
    cursor = conn.cursor()

    sql = """
        SELECT
            id,
            name,
            category,
            address,
            ST_X(geom) AS lng,
            ST_Y(geom) AS lat,
            ST_Distance(
                geom::geography,
                ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography
            ) AS distance_m
        FROM places
        WHERE ST_DWithin(
            geom::geography,
            ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography,
            %s
        )
    """

    params = [lng, lat, lng, lat, radius]

    if category:
        sql += " AND category = %s"
        params.append(category)

    sql += " ORDER BY distance_m;"

    cursor.execute(sql, params)

    rows = cursor.fetchall()

    cursor.close()
    conn.close()

    features = []

    for row in rows:
        features.append({
            "type": "Feature",
            "properties": {
                "id": row[0],
                "name": row[1],
                "category": row[2],
                "address": row[3],
                "distance_km": round(row[6] / 1000, 2)
            },
            "geometry": {
                "type": "Point",
                "coordinates": [row[4], row[5]]
            }
        })

    return {
        "type": "FeatureCollection",
        "features": features
    }


@app.get("/api/places/natural")
def natural_place_search(query: str, lng: float | None = None, lat: float | None = None):
    """Grounded Chinese search backed by existing PostGIS endpoints.

    This is a rule-based MVP, not an LLM. Unhandled travel preferences are
    disclosed instead of silently claiming optimization.
    """
    from fastapi import HTTPException
    from .natural_language import parse_intent

    if len(query) > 300:
        raise HTTPException(status_code=422, detail="查询内容不得超过300字")
    try:
        intent = parse_intent(query)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    if intent.nearby and (lng is None or lat is None):
        raise HTTPException(status_code=422, detail="附近查询需要地图中心坐标")
    if lng is not None and not -180 <= lng <= 180:
        raise HTTPException(status_code=422, detail="经度不合法")
    if lat is not None and not -90 <= lat <= 90:
        raise HTTPException(status_code=422, detail="纬度不合法")

    if intent.nearby:
        collection = get_nearby_places(lng=lng, lat=lat, radius=intent.radius_m)
    else:
        collection = get_places()

    features = collection["features"]
    matched_names = [f for f in features if f["properties"]["name"] in query]
    if matched_names:
        features = matched_names
    elif intent.categories:
        features = [f for f in features if f["properties"]["category"] in intent.categories]
    elif not intent.generic:
        features = []
    features = features[:100]

    parts = []
    if matched_names:
        parts.append("已匹配景点名称")
    elif intent.categories:
        parts.append("已按景点类别筛选")
    elif intent.generic:
        parts.append("展示已收录景点")
    else:
        parts.append("未识别到可执行的景点名称或类别条件")
    if intent.nearby:
        parts.append(f"以地图中心为参考，搜索{intent.radius_m / 1000:g}公里范围")
    if intent.unsupported:
        parts.append("以下条件暂未参与筛选：" + "、".join(intent.unsupported))

    return {
        "mode": "rule_based",
        "explanation": "；".join(parts),
        "unsupported": list(intent.unsupported),
        "matched_categories": list(intent.categories),
        "places": {"type": "FeatureCollection", "features": features},
    }


@app.get("/api/places/itinerary-preview")
def itinerary_preview(lng: float, lat: float, max_stops: int = 4, query: str = ""):
    """A limited straight-line POI preview; NOT a real navigation itinerary."""
    from fastapi import HTTPException
    from .natural_language import parse_intent
    from .itinerary import build_preview

    if not -180 <= lng <= 180 or not -90 <= lat <= 90:
        raise HTTPException(status_code=422, detail="地图中心坐标无效")
    if not 2 <= max_stops <= 6:
        raise HTTPException(status_code=422, detail="站点数需要在2到6之间")
    if len(query) > 300:
        raise HTTPException(status_code=422, detail="查询不得超过300字")
    if query.strip():
        search = natural_place_search(query=query, lng=lng, lat=lat)
        features = search["places"]["features"]
        explanation = search["explanation"]
    else:
        features = get_places()["features"]
        explanation = "从已收录景点中按距离选取候选站点"
    result = build_preview(features=features, origin=(lng, lat), max_stops=max_stops)
    return {
        **result,
        "origin": {"lng": lng, "lat": lat},
        "explanation": explanation,
        "candidate_count": len(features),
    }
