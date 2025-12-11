-- Detect micro cliffs: groups of trees that stand close together and are due
-- for renewal in the same planning horizon.
-- DBSCAN is partitioned by horizon so a cluster means shared timing, not just
-- dense planting. Unassessed trees and excluded precincts are left out.

INSERT INTO core.tree_cluster (tree_id, horizon, cluster_id)
SELECT
    t.tree_id,
    f.horizon,
    ST_ClusterDBSCAN(
        t.geom,
        eps       := ref.param('dbscan_eps_m')::DOUBLE PRECISION,
        minpoints := ref.param('dbscan_min_points')::INTEGER
    ) OVER (PARTITION BY f.horizon)
FROM core.tree AS t
JOIN core.tree_feature AS f USING (tree_id)
WHERE f.is_assessed
  AND f.precinct_in_scope;

ANALYZE core.tree_cluster;

-- One row per cluster. The footprint is the buffered concave hull of its trees.
WITH members AS (
    SELECT c.horizon, c.cluster_id, t.geom, t.genus, t.precinct, t.located_in,
           f.replacement_cost_aud, h.hvi_score
    FROM core.tree_cluster AS c
    JOIN core.tree AS t USING (tree_id)
    JOIN core.tree_feature AS f USING (tree_id)
    LEFT JOIN core.tree_hvi AS h USING (tree_id)
    WHERE c.cluster_id IS NOT NULL
),
genus_counts AS (
    SELECT horizon, cluster_id, genus, COUNT(*) AS n,
           ROW_NUMBER() OVER (PARTITION BY horizon, cluster_id ORDER BY COUNT(*) DESC, genus) AS genus_rank
    FROM members
    GROUP BY horizon, cluster_id, genus
),
clusters AS (
    SELECT
        horizon,
        cluster_id,
        COUNT(*) AS tree_count,
        SUM(replacement_cost_aud) AS replacement_cost_aud,
        MODE() WITHIN GROUP (ORDER BY precinct) AS precinct,
        MODE() WITHIN GROUP (ORDER BY located_in) AS located_in,
        AVG(hvi_score) AS avg_hvi_score,
        ST_Buffer(
            ST_ConcaveHull(ST_Collect(geom), 0.8),
            ref.param('micro_cliff_buffer_m')::DOUBLE PRECISION,
            'quad_segs=4'
        ) AS geom
    FROM members
    GROUP BY horizon, cluster_id
)
INSERT INTO mart.micro_cliff (
    horizon, cluster_id, cluster_rank, tree_count, replacement_cost_aud,
    footprint_m2, trees_per_ha, dominant_genus, dominant_genus_share,
    precinct, located_in, avg_hvi_score, geom
)
SELECT
    c.horizon,
    c.cluster_id,
    RANK() OVER (PARTITION BY c.horizon
                 ORDER BY c.tree_count DESC, c.replacement_cost_aud DESC, c.cluster_id),
    c.tree_count,
    c.replacement_cost_aud,
    ROUND(ST_Area(c.geom)::NUMERIC, 1),
    ROUND((c.tree_count / (ST_Area(c.geom) / 10000.0))::NUMERIC, 1),
    g.genus,
    ROUND(g.n::NUMERIC / c.tree_count, 3),
    c.precinct,
    c.located_in,
    ROUND(c.avg_hvi_score, 2),
    c.geom
FROM clusters AS c
JOIN genus_counts AS g
  ON g.horizon = c.horizon AND g.cluster_id = c.cluster_id AND g.genus_rank = 1;
