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
        migration = (root / 'database' / 'migrations' / 'add_tourism_metadata.sql').read_text(encoding='utf-8')
        for _ in range(2):
            cur.execute(migration)
        cur.execute("SELECT column_name FROM information_schema.columns WHERE table_schema = %s AND table_name = 'places'", (schema,))
        actual_columns = {row[0] for row in cur.fetchall()}
        assert {'visit_duration', 'indoor', 'tags', 'description', 'best_time'} <= actual_columns
        cur.execute("UPDATE places SET visit_duration = 150, indoor = TRUE, tags = ARRAY['历史', '展览'] WHERE name = '南京博物院'")
        cur.execute("SELECT visit_duration, indoor, tags FROM places WHERE name = '南京博物院'")
        assert cur.fetchone() == (150, True, ['历史', '展览'])
    print('PASS: fresh schema, seed twice, repeated metadata migration and typed columns; transaction rolled back')
finally:
    conn.rollback()
    conn.close()
