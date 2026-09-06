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

@app.get("/api/places")
def get_places(q: str | None = None):
    conn = get_db_connection()
    cursor = conn.cursor()

    if q:
        cursor.execute("""
            SELECT
                id,
                name,
                category,
                address,
                ST_X(geom) AS lng,
                ST_Y(geom) AS lat
            FROM places
            WHERE name ILIKE %s
            OR category ILIKE %s
            ORDER BY id;
        """, (f"%{q}%", f"%{q}%"))
    else:
        cursor.execute("""
            SELECT
                id,
                name,
                category,
                address,
                ST_X(geom) AS lng,
                ST_Y(geom) AS lat
            FROM places
            ORDER BY id;
        """)

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