from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")

def get_db_connection():
    return psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )

app = FastAPI()
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
