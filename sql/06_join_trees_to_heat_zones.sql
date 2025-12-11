-- Assign each tree to the heat vulnerability zone that contains it.
-- Trees on a shared boundary keep one zone: classified first, then lowest
-- SA1 code. Trees outside every zone take the nearest zone within the
-- fallback distance. match_method records how each tree was matched.

INSERT INTO core.tree_hvi (tree_id, sa1_code, hvi_score, match_method, match_distance_m)
SELECT
    t.tree_id,
    COALESCE(within_zone.sa1_code, nearest_zone.sa1_code),
    COALESCE(within_zone.hvi_score, nearest_zone.hvi_score),
    CASE
        WHEN within_zone.sa1_code IS NOT NULL  THEN 'within'
        WHEN nearest_zone.sa1_code IS NOT NULL THEN 'nearest'
        ELSE 'unmatched'
    END,
    CASE
        WHEN within_zone.sa1_code IS NOT NULL THEN 0
        ELSE ROUND(nearest_zone.distance_m::NUMERIC, 1)
    END
FROM core.tree AS t
LEFT JOIN LATERAL (
    SELECT z.sa1_code, z.hvi_score
    FROM core.hvi_zone AS z
    WHERE ST_Covers(z.geom, t.geom)
    ORDER BY z.hvi_score IS NULL, z.sa1_code
    LIMIT 1
) AS within_zone ON TRUE
LEFT JOIN LATERAL (
    SELECT z.sa1_code, z.hvi_score, ST_Distance(z.geom, t.geom) AS distance_m
    FROM core.hvi_zone AS z
    WHERE within_zone.sa1_code IS NULL
      AND ST_DWithin(z.geom, t.geom, ref.param('hvi_fallback_max_distance_m'))
    ORDER BY z.geom <-> t.geom
    LIMIT 1
) AS nearest_zone ON TRUE;

ANALYZE core.tree_hvi;
