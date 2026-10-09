-- Optional, backward-compatible POI access-point metadata (Stage 13).
-- Run once against your local PostGIS database before populating reviewed points.
-- Existing places.geom is unchanged and remains the visual/map marker position.
--
-- Example FORMAT ONLY -- NOT verified coordinates; DO NOT use as live data:
-- {
--   "pedestrian": {
--     "status": "reviewed", "name": "<verified entrance label>",
--     "lng": 0.0, "lat": 0.0,
--     "source_url": "https://<independent official/source page>",
--     "reviewed_on": "2026-10-10"
--   },
--   "auto": {...}
-- }
--
-- The application accepts a specific mode only if status='reviewed', source
-- URL and review date are present, coordinate is sane and <=10km from
-- places.geom. It does NOT verify the external source contents automatically.
-- Missing, draft, invalid or other-mode records continue using places.geom.
-- Never treat a map centroid as a confirmed official entrance.

ALTER TABLE places ADD COLUMN IF NOT EXISTS routing_access JSONB;

-- Optional structural safety; records with invalid shape should not be saved.
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conname = 'places_routing_access_object_chk'
      AND conrelid = 'places'::regclass
  ) THEN
    ALTER TABLE places ADD CONSTRAINT places_routing_access_object_chk
      CHECK (routing_access IS NULL OR jsonb_typeof(routing_access) = 'object');
  END IF;
END
$$;

-- Audit the source coverage after you populate some entries:
-- SELECT name, routing_access FROM places WHERE routing_access IS NOT NULL;
