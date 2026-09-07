\encoding UTF8

-- Smart Tourism database schema

CREATE EXTENSION IF NOT EXISTS postgis;

CREATE TABLE IF NOT EXISTS places (
    id integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name varchar(100) NOT NULL,
    category varchar(50) NOT NULL,
    address varchar(255),
    rating numeric(2,1),
    geom geometry(Point, 4326) NOT NULL,

    CONSTRAINT places_rating_check
        CHECK (rating >= 0 AND rating <= 5)
);

CREATE INDEX IF NOT EXISTS idx_places_geom
ON places
USING GIST (geom);