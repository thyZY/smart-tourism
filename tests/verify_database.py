"""Check fresh schema and repeatable seed inside a rolled-back transaction."""
import os
from pathlib import Path
from uuid import uuid4
import psycopg2
from psycopg2 import sql
from dotenv import load_dotenv

root = Path(__file__).resolve().parents[1]
load_dotenv(root / 'backend' / '.env')
conn = psycopg2.connect(**{key: os.environ[env] for key, env in {
    'host': 'DB_HOST', 'port': 'DB_PORT', 'dbname': 'DB_NAME',
    'user': 'DB_USER', 'password': 'DB_PASSWORD'
}.items()})
try:
    with conn.cursor() as cur:
        schema = 'qa_' + uuid4().hex
        cur.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(schema)))
        cur.execute(sql.SQL('SET LOCAL search_path TO {}, public').format(sql.Identifier(schema)))
        cur.execute("SET LOCAL client_encoding TO 'UTF8'")
        for _ in range(2):
            for name in ('schema.sql', 'seed.sql'):
                content = (root / 'database' / name).read_text(encoding='utf-8-sig')
                assert content.startswith('\\encoding UTF8')
                cur.execute(content.split('\n', 1)[1])
            cur.execute('SELECT name, ST_SRID(geom) FROM places ORDER BY id')
            assert cur.fetchall() == [('南京博物院', 4326), ('夫子庙', 4326), ('中山陵', 4326)]
        cur.execute('SELECT indexdef FROM pg_indexes WHERE schemaname = %s AND indexname = %s',
                    (schema, 'idx_places_geom'))
        assert 'USING gist (geom)' in cur.fetchone()[0]
    print('PASS: fresh schema, UTF8 names, seed twice = 3 POIs, GiST index; transaction rolled back')
finally:
    conn.rollback()
    conn.close()
