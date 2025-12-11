-- Derive renewal window, planning horizon, trunk diameter and replacement
-- cost for every tree.
--
-- Renewal window comes from the text band. The numeric code defaults to 50
-- for the 21 percent of trees never assessed, so it cannot be trusted alone.
--
-- Missing trunk diameters (55 percent) are imputed as the median of measured
-- trees in the same genus and age class, falling back to the age class, then
-- the whole register. dbh_source records which level was used.

WITH measured AS (
    SELECT genus, age_description, dbh_cm
    FROM core.tree
    WHERE dbh_cm IS NOT NULL
),
genus_age_median AS (
    SELECT genus, age_description,
           percentile_cont(0.5) WITHIN GROUP (ORDER BY dbh_cm) AS median_dbh_cm
    FROM measured
    GROUP BY genus, age_description
    HAVING COUNT(*) >= ref.param('imputation_min_sample')
),
age_median AS (
    SELECT age_description,
           percentile_cont(0.5) WITHIN GROUP (ORDER BY dbh_cm) AS median_dbh_cm
    FROM measured
    GROUP BY age_description
),
overall_median AS (
    SELECT percentile_cont(0.5) WITHIN GROUP (ORDER BY dbh_cm) AS median_dbh_cm
    FROM measured
),
modelled AS (
    SELECT
        t.tree_id,
        t.precinct,
        t.ule_label,
        COALESCE(t.dbh_cm, ga.median_dbh_cm, a.median_dbh_cm, o.median_dbh_cm)::NUMERIC AS dbh_cm_model,
        CASE
            WHEN t.dbh_cm IS NOT NULL         THEN 'measured'
            WHEN ga.median_dbh_cm IS NOT NULL THEN 'imputed_genus_age'
            WHEN a.median_dbh_cm IS NOT NULL  THEN 'imputed_age'
            ELSE 'imputed_overall'
        END AS dbh_source
    FROM core.tree AS t
    LEFT JOIN genus_age_median AS ga
           ON ga.genus = t.genus AND ga.age_description = t.age_description
    LEFT JOIN age_median AS a
           ON a.age_description = t.age_description
    CROSS JOIN overall_median AS o
)
INSERT INTO core.tree_feature (
    tree_id, renewal_window_code, horizon, is_assessed, is_near_term,
    precinct_in_scope, dbh_cm_model, dbh_source, cost_band_code,
    replacement_cost_aud
)
SELECT
    m.tree_id,
    w.renewal_window_code,
    w.horizon,
    w.horizon <> 'not_assessed',
    w.is_near_term,
    ex.precinct IS NULL,
    ROUND(m.dbh_cm_model, 1),
    m.dbh_source,
    b.cost_band_code,
    b.cost_aud
FROM modelled AS m
JOIN ref.renewal_window AS w
  ON w.source_label IS NOT DISTINCT FROM m.ule_label
JOIN ref.replacement_cost_band AS b
  ON b.dbh_range_cm @> m.dbh_cm_model
LEFT JOIN ref.excluded_precinct AS ex
  ON ex.precinct = m.precinct;

ANALYZE core.tree_feature;
