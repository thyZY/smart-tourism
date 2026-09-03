from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os
import psycopg2

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
def get_places():
    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {
                    "id": 1,
                    "name": "南京博物院",
                    "category": "博物馆"
                },
                "geometry": {
                    "type": "Point",
                    "coordinates": [118.7921, 32.0407]
                }
            },
            {
                "type": "Feature",
                "properties": {
                    "id": 2,
                    "name": "夫子庙",
                    "category": "历史文化"
                },
                "geometry": {
                    "type": "Point",
                    "coordinates": [118.7877, 32.0270]
                }
            },
            {
                "type": "Feature",
                "properties": {
                    "id": 3,
                    "name": "中山陵",
                    "category": "陵园景区"
                },
                "geometry": {
                    "type": "Point",
                    "coordinates": [118.8487, 32.0593]
                }
            }
        ]
    }