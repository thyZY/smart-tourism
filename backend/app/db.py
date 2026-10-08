"""Shared PostgreSQL connection configuration for API and tourism routes."""
import os

import psycopg2
from dotenv import load_dotenv

load_dotenv()


def get_db_connection():
    """Return a new connection; callers must always close it."""
    return psycopg2.connect(
        host=os.getenv("DB_HOST"),
        port=os.getenv("DB_PORT"),
        dbname=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
    )
