-- Build the precinct marts and the canopy cliff priority score.
--
-- Precinct area is the convex hull of its trees, as no official boundaries
-- are published, so per hectare figures are indicative.
--
-- The score is 100 times the weighted mean of three percentile ranks:
-- near term cost per hectare, near term share of trees and average heat
-- vulnerability. Percentile ranks keep any one measure from dominating.
-- Precincts below the confidence threshold are reported but not ranked.

-- Precinct area ------------------------------------------------------------
INSERT INTO mart.precinct_area (precinct, tree_count, area_ha, geom)
SELECT precinct, tree_count, ROUND((ST_Area(hull) / 10000.0)::NUMERIC, 2), hull
FROM (
    SELECT t.precinct, COUNT(*) AS tree_count, ST_ConvexHull(ST_Collect(t.geom)) AS hull
    FROM core.tree AS t
    JOIN core.tree_feature AS f USING (tree_id)
    WHERE f.precinct_in_scope
    GROUP BY t.precinct
) AS hulls
WHERE GeometryType(hull) = 'POLYGON'
  AND ST_Area(hull) > 0;

-- Precinct by renewal window, zero filled ----------------------------------
INSERT INTO mart.precinct_window (
    precinct, renewal_window_code, tree_count, tree_share,
    replacement_cost_aud, imputed_cost_share, avg_hvi_score
)
WITH aggregated AS (
    SELECT
        t.precinct,
        f.renewal_window_code,
        COUNT(*) AS tree_count,
        SUM(f.replacement_cost_aud) AS replacement_cost_aud,
        SUM(f.replacement_cost_aud) FILTER (WHERE f.dbh_source <> 'measured') AS imputed_cost_aud,
        AVG(h.hvi_score) AS avg_hvi_score
    FROM core.tree AS t
    JOIN core.tree_feature AS f USING (tree_id)
    JOIN core.tree_hvi AS h USING (tree_id)
    GROUP BY t.precinct, f.renewal_window_code
)
SELECT
    pa.precinct,
    w.renewal_window_code,
    COALESCE(a.tree_count, 0),
    ROUND(COALESCE(a.tree_count, 0)::NUMERIC / pa.tree_count, 4),
    COALESCE(a.replacement_cost_aud, 0),
    ROUND(COALESCE(a.imputed_cost_aud, 0) / NULLIF(a.replacement_cost_aud, 0), 4),
    ROUND(a.avg_hvi_score, 2)
FROM mart.precinct_area AS pa
CROSS JOIN ref.renewal_window AS w
LEFT JOIN aggregated AS a
       ON a.precinct = pa.precinct
      AND a.renewal_window_code = w.renewal_window_code;

-- Precinct scorecard -------------------------------------------------------
INSERT INTO mart.precinct_scorecard (
    precinct, tree_count, area_ha, near_term_trees, near_term_share,
    near_term_cost_aud, near_term_cost_per_ha, near_term_trees_per_ha,
    scheduled_cost_aud, not_assessed_cost_aud, avg_hvi_score,
    hvi_classified_share, near_term_clustered_share, not_assessed_share,
    imputed_dbh_share, low_confidence, pct_cost_density,
    pct_near_term_share, pct_heat, cliff_index, cliff_rank
)
WITH metrics AS (
    SELECT
        pa.precinct,
        pa.tree_count,
        pa.area_ha,
        COUNT(*) FILTER (WHERE f.is_near_term) AS near_term_trees,
        COALESCE(SUM(f.replacement_cost_aud) FILTER (WHERE f.is_near_term), 0) AS near_term_cost_aud,
        COALESCE(SUM(f.replacement_cost_aud) FILTER (WHERE f.is_assessed), 0) AS scheduled_cost_aud,
        COALESCE(SUM(f.replacement_cost_aud) FILTER (WHERE NOT f.is_assessed), 0) AS not_assessed_cost_aud,
        AVG(h.hvi_score) AS avg_hvi_score,
        AVG((h.hvi_score IS NOT NULL)::INT) AS hvi_classified_share,
        AVG((c.cluster_id IS NOT NULL)::INT) FILTER (WHERE f.is_near_term) AS near_term_clustered_share,
        AVG((NOT f.is_assessed)::INT) AS not_assessed_share,
        AVG((f.dbh_source <> 'measured')::INT) AS imputed_dbh_share
    FROM mart.precinct_area AS pa
    JOIN core.tree AS t ON t.precinct = pa.precinct
    JOIN core.tree_feature AS f USING (tree_id)
    JOIN core.tree_hvi AS h USING (tree_id)
    LEFT JOIN core.tree_cluster AS c USING (tree_id)
    GROUP BY pa.precinct, pa.tree_count, pa.area_ha
),
derived AS (
    SELECT
        m.*,
        m.near_term_trees::NUMERIC / m.tree_count AS near_term_share,
        m.near_term_cost_aud / m.area_ha AS near_term_cost_per_ha,
        m.near_term_trees / m.area_ha AS near_term_trees_per_ha,
        m.tree_count < ref.param('low_confidence_tree_threshold') AS low_confidence
    FROM metrics AS m
),
ranked AS (
    -- Partitioning by low_confidence keeps small precincts out of the
    -- percentile distribution used for ranking.
    SELECT
        d.*,
        PERCENT_RANK() OVER w_cost  AS pct_cost_density,
        PERCENT_RANK() OVER w_share AS pct_near_term_share,
        PERCENT_RANK() OVER w_heat  AS pct_heat
    FROM derived AS d
    WINDOW
        w_cost  AS (PARTITION BY d.low_confidence ORDER BY d.near_term_cost_per_ha),
        w_share AS (PARTITION BY d.low_confidence ORDER BY d.near_term_share),
        w_heat  AS (PARTITION BY d.low_confidence ORDER BY COALESCE(d.avg_hvi_score, 0))
),
scored AS (
    SELECT
        r.*,
        100 * (
              ref.param('weight_cost_density')    * r.pct_cost_density
            + ref.param('weight_near_term_share') * r.pct_near_term_share
            + ref.param('weight_heat')            * r.pct_heat
        ) / (
              ref.param('weight_cost_density')
            + ref.param('weight_near_term_share')
            + ref.param('weight_heat')
        ) AS cliff_index
    FROM ranked AS r
)
SELECT
    precinct,
    tree_count,
    area_ha,
    near_term_trees,
    ROUND(near_term_share, 4),
    near_term_cost_aud,
    ROUND(near_term_cost_per_ha, 2),
    ROUND(near_term_trees_per_ha, 2),
    scheduled_cost_aud,
    not_assessed_cost_aud,
    ROUND(avg_hvi_score, 2),
    ROUND(hvi_classified_share, 4),
    ROUND(near_term_clustered_share, 4),
    ROUND(not_assessed_share, 4),
    ROUND(imputed_dbh_share, 4),
    low_confidence,
    CASE WHEN NOT low_confidence THEN ROUND(pct_cost_density::NUMERIC, 4) END,
    CASE WHEN NOT low_confidence THEN ROUND(pct_near_term_share::NUMERIC, 4) END,
    CASE WHEN NOT low_confidence THEN ROUND(pct_heat::NUMERIC, 4) END,
    CASE WHEN NOT low_confidence THEN ROUND(cliff_index::NUMERIC, 1) END,
    CASE WHEN NOT low_confidence
         THEN RANK() OVER (PARTITION BY low_confidence ORDER BY cliff_index DESC)
    END
FROM scored;
