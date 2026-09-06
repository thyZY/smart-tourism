\encoding UTF8
-- Smart Tourism demo place seed data
-- Assumes the "places" table and PostGIS extension already exist.

-- 南京博物院
UPDATE places
SET
    name = '南京博物院',
    category = '博物馆',
    address = '南京市玄武区中山东路321号',
    rating = NULL,
    geom = ST_SetSRID(ST_MakePoint(118.7921, 32.0407), 4326)
WHERE name = '南京博物院';

INSERT INTO places (name, category, address, rating, geom)
SELECT
    '南京博物院',
    '博物馆',
    '南京市玄武区中山东路321号',
    NULL,
    ST_SetSRID(ST_MakePoint(118.7921, 32.0407), 4326)
WHERE NOT EXISTS (
    SELECT 1 FROM places WHERE name = '南京博物院'
);


-- 夫子庙
UPDATE places
SET
    name = '夫子庙',
    category = '历史文化',
    address = '南京市秦淮区贡院街152号',
    rating = NULL,
    geom = ST_SetSRID(ST_MakePoint(118.7877, 32.0270), 4326)
WHERE name = '夫子庙';

INSERT INTO places (name, category, address, rating, geom)
SELECT
    '夫子庙',
    '历史文化',
    '南京市秦淮区贡院街152号',
    NULL,
    ST_SetSRID(ST_MakePoint(118.7877, 32.0270), 4326)
WHERE NOT EXISTS (
    SELECT 1 FROM places WHERE name = '夫子庙'
);


-- 中山陵
UPDATE places
SET
    name = '中山陵',
    category = '陵园景区',
    address = '南京市玄武区石象路7号',
    rating = NULL,
    geom = ST_SetSRID(ST_MakePoint(118.8487, 32.0593), 4326)
WHERE name = '中山陵';

INSERT INTO places (name, category, address, rating, geom)
SELECT
    '中山陵',
    '陵园景区',
    '南京市玄武区石象路7号',
    NULL,
    ST_SetSRID(ST_MakePoint(118.8487, 32.0593), 4326)
WHERE NOT EXISTS (
    SELECT 1 FROM places WHERE name = '中山陵'
);