-- Add tourism semantic attributes without changing existing spatial fields.
-- PostgreSQL migration: safe to run after checking current schema.

ALTER TABLE places
    ADD COLUMN IF NOT EXISTS visit_duration INTEGER,
    ADD COLUMN IF NOT EXISTS indoor BOOLEAN,
    ADD COLUMN IF NOT EXISTS tags TEXT[],
    ADD COLUMN IF NOT EXISTS description TEXT,
    ADD COLUMN IF NOT EXISTS best_time VARCHAR(100);
