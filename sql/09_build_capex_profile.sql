-- Build the annual renewal spend profile and the levelled budget.
--
-- Reactive spend replaces each tree within its renewal window, spread evenly
-- across the window's years. Years count from the life expectancy
-- assessment, not calendar years. Unassessed trees cannot be scheduled and
-- are excluded.
--
-- The levelled budget is the smallest flat annual amount that never falls
-- behind cumulative need: max over t of (cumulative cost to year t / t).

WITH years AS (
    SELECT generate_series(1, (SELECT MAX(end_year) FROM ref.renewal_window))::SMALLINT AS year_offset
),
window_cost AS (
    SELECT t.precinct, w.start_year, w.end_year, SUM(f.replacement_cost_aud) AS cost_aud
    FROM core.tree_feature AS f
    JOIN core.tree AS t USING (tree_id)
    JOIN ref.renewal_window AS w USING (renewal_window_code)
    JOIN mart.precinct_area AS pa ON pa.precinct = t.precinct
    WHERE f.is_assessed
    GROUP BY t.precinct, w.start_year, w.end_year
),
annual_by_precinct AS (
    SELECT wc.precinct, y.year_offset,
           SUM(wc.cost_aud / (wc.end_year - wc.start_year + 1)) AS reactive_cost_aud
    FROM window_cost AS wc
    JOIN years AS y ON y.year_offset BETWEEN wc.start_year AND wc.end_year
    GROUP BY wc.precinct, y.year_offset
),
annual AS (
    SELECT p.precinct, y.year_offset, COALESCE(a.reactive_cost_aud, 0) AS reactive_cost_aud
    FROM (SELECT DISTINCT precinct FROM window_cost) AS p
    CROSS JOIN years AS y
    LEFT JOIN annual_by_precinct AS a
           ON a.precinct = p.precinct AND a.year_offset = y.year_offset
    UNION ALL
    SELECT 'All precincts', year_offset, SUM(reactive_cost_aud)
    FROM annual_by_precinct
    GROUP BY year_offset
),
cumulative AS (
    SELECT precinct, year_offset, reactive_cost_aud,
           SUM(reactive_cost_aud) OVER (PARTITION BY precinct ORDER BY year_offset) AS cumulative_reactive_aud
    FROM annual
),
levelled AS (
    SELECT precinct, MAX(cumulative_reactive_aud / year_offset) AS levelled_budget_aud
    FROM cumulative
    GROUP BY precinct
)
INSERT INTO mart.capex_profile (
    precinct, year_offset, reactive_cost_aud, cumulative_reactive_aud,
    levelled_budget_aud, cumulative_levelled_aud
)
SELECT
    c.precinct,
    c.year_offset,
    ROUND(c.reactive_cost_aud, 2),
    ROUND(c.cumulative_reactive_aud, 2),
    ROUND(l.levelled_budget_aud, 2),
    ROUND(l.levelled_budget_aud * c.year_offset, 2)
FROM cumulative AS c
JOIN levelled AS l USING (precinct);
