import csv
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]

sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.main import get_db_connection


CSV_PATH = PROJECT_ROOT / "data" / "nanjing_pois.csv"

REQUIRED_COLUMNS = {
    "name",
    "category",
    "address",
    "longitude",
    "latitude",
    "rating",
}


def load_pois():
    pois = []
    seen_names = set()

    with CSV_PATH.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)

        if reader.fieldnames is None:
            raise ValueError("CSV 文件没有表头")

        missing_columns = REQUIRED_COLUMNS - set(reader.fieldnames)

        if missing_columns:
            raise ValueError(
                f"CSV 缺少字段: {', '.join(sorted(missing_columns))}"
            )

        for line_number, row in enumerate(reader, start=2):
            name = row["name"].strip()
            category = row["category"].strip()
            address = row["address"].strip()

            if not name:
                raise ValueError(f"第 {line_number} 行缺少 name")

            if not category:
                raise ValueError(f"第 {line_number} 行缺少 category")

            if not address:
                raise ValueError(f"第 {line_number} 行缺少 address")

            if name in seen_names:
                raise ValueError(
                    f"第 {line_number} 行发现重复 POI: {name}"
                )

            try:
                longitude = float(row["longitude"])
                latitude = float(row["latitude"])
            except ValueError:
                raise ValueError(
                    f"第 {line_number} 行经纬度不是有效数字"
                )

            if not -180 <= longitude <= 180:
                raise ValueError(
                    f"第 {line_number} 行 longitude 超出范围"
                )

            if not -90 <= latitude <= 90:
                raise ValueError(
                    f"第 {line_number} 行 latitude 超出范围"
                )

            rating_text = row["rating"].strip()

            if rating_text:
                try:
                    rating = float(rating_text)
                except ValueError:
                    raise ValueError(
                        f"第 {line_number} 行 rating 不是有效数字"
                    )

                if not 0 <= rating <= 5:
                    raise ValueError(
                        f"第 {line_number} 行 rating 必须在 0 到 5 之间"
                    )
            else:
                rating = None

            pois.append(
                {
                    "name": name,
                    "category": category,
                    "address": address,
                    "longitude": longitude,
                    "latitude": latitude,
                    "rating": rating,
                }
            )

            seen_names.add(name)

    return pois

def load_existing_place_names():
    conn = get_db_connection()

    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT name
                FROM places
                ORDER BY id;
            """)

            rows = cursor.fetchall()

        return [row[0] for row in rows]

    finally:
        conn.close()

def sync_pois(pois):
    conn = get_db_connection()

    inserted_count = 0
    updated_count = 0

    try:
        with conn.cursor() as cursor:
            for poi in pois:
                cursor.execute(
                    """
                    SELECT id
                    FROM places
                    WHERE name = %s;
                    """,
                    (poi["name"],),
                )

                existing = cursor.fetchone()

                if existing:
                    cursor.execute(
                        """
                        UPDATE places
                        SET
                            category = %s,
                            address = %s,
                            rating = %s,
                            geom = ST_SetSRID(
                                ST_MakePoint(%s, %s),
                                4326
                            )
                        WHERE id = %s;
                        """,
                        (
                            poi["category"],
                            poi["address"],
                            poi["rating"],
                            poi["longitude"],
                            poi["latitude"],
                            existing[0],
                        ),
                    )

                    updated_count += 1

                else:
                    cursor.execute(
                        """
                        INSERT INTO places (
                            name,
                            category,
                            address,
                            rating,
                            geom
                        )
                        VALUES (
                            %s,
                            %s,
                            %s,
                            %s,
                            ST_SetSRID(
                                ST_MakePoint(%s, %s),
                                4326
                            )
                        );
                        """,
                        (
                            poi["name"],
                            poi["category"],
                            poi["address"],
                            poi["rating"],
                            poi["longitude"],
                            poi["latitude"],
                        ),
                    )

                    inserted_count += 1

        conn.commit()

        return inserted_count, updated_count

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()        

if __name__ == "__main__":
    pois = load_pois()

    print(f"CSV 校验通过，共读取 {len(pois)} 个 POI：")

    for poi in pois:
        print(
            f"- {poi['name']} | "
            f"{poi['category']} | "
            f"{poi['longitude']}, {poi['latitude']}"
        )

    existing_names = load_existing_place_names()

    print()
    print(f"导入前数据库共有 {len(existing_names)} 个 POI")

    inserted_count, updated_count = sync_pois(pois)

    print()
    print("数据库同步完成：")
    print(f"- 新增：{inserted_count}")
    print(f"- 更新：{updated_count}")