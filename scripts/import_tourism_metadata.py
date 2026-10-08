"""Validate and optionally apply provisional POI tourism metadata.

By default, validate files only. Use --apply only against the local database
you intend to update. All SQL writes happen in one transaction.
"""
import argparse
import csv
import json
import os
from pathlib import Path

from dotenv import load_dotenv
import psycopg2

ROOT = Path(__file__).resolve().parents[1]
CSV_PATH = ROOT / "data" / "nanjing_pois.csv"
DATA_PATH = ROOT / "data" / "poi_tourism_metadata.json"
MIGRATION_PATH = ROOT / "database" / "migrations" / "add_tourism_metadata.sql"


def load_records():
    data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    if data.get("review_status") != "planning_estimates_unverified":
        raise ValueError("Missing provisional-data disclosure")
    if data.get("schema_version") != 2:
        raise ValueError("Unsupported catalog version")
    with CSV_PATH.open(encoding="utf-8-sig", newline="") as handle:
        csv_names = [row["name"] for row in csv.DictReader(handle)]
    records = data["records"]
    names = [record["name"] for record in records]
    if len(csv_names) != 40 or len(records) != 40:
        raise ValueError("Expected exactly 40 catalog/CSV POIs")
    if len(set(names)) != 40 or set(csv_names) != set(names):
        raise ValueError("POI metadata names do not match nanjing_pois.csv")
    for record in records:
        duration = record.get("visit_duration")
        if not isinstance(duration, int) or isinstance(duration, bool) or not 15 <= duration <= 480:
            raise ValueError(f"Invalid planning duration: {record['name']}")
        if record.get("indoor") not in (True, False, None):
            raise ValueError(f"Invalid indoor field: {record['name']}")
        if not isinstance(record.get("tags"), list) or not record["tags"] or not all(
            isinstance(tag, str) and tag.strip() for tag in record["tags"]
        ):
            raise ValueError(f"Invalid tags: {record['name']}")
        if not isinstance(record.get("description"), str) or not record["description"].strip():
            raise ValueError(f"Invalid description: {record['name']}")
        if not isinstance(record.get("best_time"), str):
            raise ValueError(f"Invalid best_time: {record['name']}")
    return records


def apply_records(records):
    load_dotenv(ROOT / "backend" / ".env")
    conn = psycopg2.connect(**{
        key: os.environ[env] for key, env in {
            "host": "DB_HOST", "port": "DB_PORT", "dbname": "DB_NAME",
            "user": "DB_USER", "password": "DB_PASSWORD"
        }.items()
    })
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT name FROM places ORDER BY name")
            existing = [row[0] for row in cursor.fetchall()]
            expected = {record["name"] for record in records}
            if len(existing) != 40 or len(set(existing)) != 40 or set(existing) != expected:
                raise ValueError(
                    "Database must contain the exact 40 CSV POIs; refusing partial or mismatched writes."
                )
            cursor.execute(MIGRATION_PATH.read_text(encoding="utf-8"))
            for record in records:
                cursor.execute(
                    """UPDATE places
                       SET visit_duration = %s, indoor = %s, tags = %s,
                           description = %s, best_time = %s
                       WHERE name = %s""",
                    (
                        record["visit_duration"], record["indoor"], record["tags"],
                        record["description"], record["best_time"], record["name"]
                    ),
                )
                if cursor.rowcount != 1:
                    raise ValueError(f"Failed to update exactly one POI: {record['name']}")
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="apply migration and 40 updates atomically")
    args = parser.parse_args()
    records = load_records()
    print(f"PASS: validated {len(records)} unverified planning metadata records against CSV")
    if args.apply:
        apply_records(records)
        print("PASS: migrated and updated 40 PostgreSQL POIs; transaction committed")
    else:
        print("DRY RUN: no database was changed. Rerun with --apply to update local PostgreSQL.")


if __name__ == "__main__":
    main()
