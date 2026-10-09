-- Stage 14: OPTIONAL local import of *draft research*, NOT a routing migration.
-- Source research: data/entrance_evidence/xuanwu_lake_20261010.json
-- You do NOT need to run this for the current road app to work.
-- It only saves candidate names and links for later manual review.
-- No 'reviewed' status, no routing lng/lat and no automotive entry
-- are created. Existing actual reviewed data is never overwritten.
--
-- Requires the routing_access JSONB field already installed in Stage 13.
BEGIN;

UPDATE places
SET routing_access = jsonb_set(
    COALESCE(routing_access, '{}'::jsonb),
    '{pedestrian}',
    jsonb_build_object(
        'status', 'draft',
        'review_batch', 'xuanwu_lake_20261010',
        'activation', 'blocked_pending_WGS84_and_walkway_review',
        'candidate_entrances', jsonb_build_array(
            jsonb_build_object(
                'name', '玄武湖景区（玄武门）',
                'source_url', 'https://www.amap.com/place/B00190B4FQ',
                'official_source', 'https://www.xuanwuhu.net/lyfw/lyfw2.aspx',
                'coordinate_system', 'GCJ-02_from_platform_NOT_WGS84'
            ),
            jsonb_build_object(
                'name', '玄武湖景区（解放门）',
                'source_url', 'https://ditu.amap.com/place/B0019095PK',
                'official_source', 'https://www.xuanwuhu.net/lyfw/detail.aspx?id=207',
                'coordinate_system', 'GCJ-02_from_platform_NOT_WGS84'
            )
        )
    ),
    true
)
WHERE name = '玄武湖公园'
  AND (
    routing_access IS NULL
    OR routing_access -> 'pedestrian' IS NULL
    OR routing_access -> 'pedestrian' ->> 'status' = 'draft'
  );

-- Confirm only this particular POI has a staged draft, and that no
-- reviewed routing point was accidentally created by this script:
SELECT id, name, routing_access -> 'pedestrian' ->> 'status' AS status,
       routing_access -> 'pedestrian' ->> 'review_batch' AS batch
FROM places WHERE name = '玄武湖公园';

COMMIT;

-- The read-only API GET /api/routing/access-coverage should STILL
-- report 0 reviewed points unless other unrelated entrances were approved.
