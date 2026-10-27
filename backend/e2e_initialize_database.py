"""Initialize and validate the disposable PostGIS database used by browser E2E."""
import os
from pathlib import Path
import sys

import psycopg2


ROOT = Path(__file__).resolve().parents[1]


def _require_ci_database():
    if os.getenv("GITHUB_ACTIONS") != "true":
        raise RuntimeError("This fixture may only run inside GitHub Actions")
    if os.getenv("E2E_DATABASE_FIXTURE") != "1":
        raise RuntimeError("Refusing to initialize a database without E2E_DATABASE_FIXTURE=1")
    if os.getenv("DB_NAME") != "smart_tourism_e2e":
        raise RuntimeError("Refusing to initialize a database other than smart_tourism_e2e")
    if os.getenv("DB_HOST") not in {"127.0.0.1", "localhost"}:
        raise RuntimeError("Refusing to initialize a non-loopback E2E database")
    required = ("DB_HOST", "DB_PORT", "DB_USER", "DB_PASSWORD")
    missing = [name for name in required if not os.getenv(name)]
    if missing:
        raise RuntimeError(f"Missing isolated database settings: {', '.join(missing)}")


def _execute_psql_script(cursor, filename):
    content = (ROOT / "database" / filename).read_text(encoding="utf-8-sig")
    lines = content.splitlines()
    if lines and lines[0].startswith("\\encoding "):
        lines = lines[1:]
    cursor.execute("\n".join(lines))


def main():
    _require_ci_database()
    sys.path.insert(0, str(ROOT))
    from scripts.import_pois import load_pois, sync_pois

    pois = load_pois()
    if len(pois) != 40:
        raise RuntimeError(f"Expected 40 CSV POIs, found {len(pois)}")

    connection_settings = {
        "host": os.environ["DB_HOST"],
        "port": os.environ["DB_PORT"],
        "dbname": os.environ["DB_NAME"],
        "user": os.environ["DB_USER"],
        "password": os.environ["DB_PASSWORD"],
    }
    with psycopg2.connect(**connection_settings) as connection:
        with connection.cursor() as cursor:
            _execute_psql_script(cursor, "schema.sql")
            _execute_psql_script(cursor, "seed.sql")

    inserted, updated = sync_pois(pois)

    with psycopg2.connect(**connection_settings) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT COUNT(*), COUNT(DISTINCT id),
                       COUNT(*) FILTER (
                           WHERE geom IS NULL
                              OR GeometryType(geom) <> 'POINT'
                              OR ST_SRID(geom) <> 4326
                              OR NOT ST_IsValid(geom)
                              OR ST_X(geom) NOT BETWEEN -180 AND 180
                              OR ST_Y(geom) NOT BETWEEN -90 AND 90
                       )
                FROM places
                """
            )
            count, unique_ids, invalid_geometries = cursor.fetchone()
            cursor.execute("SELECT name FROM places ORDER BY id")
            names = [row[0] for row in cursor.fetchall()]

    expected_names = [poi["name"] for poi in pois]
    if count != 40 or unique_ids != 40 or invalid_geometries != 0:
        raise RuntimeError(
            "Invalid E2E database contents: "
            f"count={count}, unique_ids={unique_ids}, invalid_geometries={invalid_geometries}"
        )
    if names != expected_names:
        raise RuntimeError("Database IDs do not follow the CSV order expected by browser fixtures")

    print(
        "E2E PostGIS fixture ready: "
        f"{count} POIs, {unique_ids} unique IDs, Point/4326 geometries valid; "
        f"CSV sync inserted={inserted}, updated={updated}."
    )


if __name__ == "__main__":
    main()
