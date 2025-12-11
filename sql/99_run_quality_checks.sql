-- Quality gate. Any failed check raises an exception and stops the pipeline
-- before reports are produced. Passing checks are logged as notices.

DO $$
DECLARE
    staged       BIGINT;
    loaded       BIGINT;
    featured     BIGINT;
    joined       BIGINT;
    classified   NUMERIC;
    unmatched    BIGINT;
    bad_shares   BIGINT;
    leaked       BIGINT;
    capex_total  NUMERIC;
    cost_total   NUMERIC;
    bad_index    BIGINT;
BEGIN
    -- 1. At most 0.5 percent of source rows may be dropped on load.
    SELECT COUNT(*) INTO staged FROM staging.trees_raw;
    SELECT COUNT(*) INTO loaded FROM core.tree;
    IF loaded = 0 OR loaded < staged * 0.995 THEN
        RAISE EXCEPTION 'Load completeness failed: % of % rows loaded', loaded, staged;
    END IF;
    RAISE NOTICE 'Load completeness: % of % rows loaded', loaded, staged;

    -- 2. Exactly one feature row and one heat zone row per tree.
    SELECT COUNT(*) INTO featured FROM core.tree_feature;
    SELECT COUNT(*) INTO joined FROM core.tree_hvi;
    IF featured <> loaded OR joined <> loaded THEN
        RAISE EXCEPTION 'Row parity failed: trees %, features %, heat joins %', loaded, featured, joined;
    END IF;
    RAISE NOTICE 'Row parity: % trees, features and heat joins', loaded;

    -- 3. At least 95 percent of trees have a heat vulnerability score.
    SELECT AVG((hvi_score IS NOT NULL)::INT), COUNT(*) FILTER (WHERE match_method = 'unmatched')
      INTO classified, unmatched
      FROM core.tree_hvi;
    IF classified < 0.95 THEN
        RAISE EXCEPTION 'Heat coverage failed: % percent classified', ROUND(classified * 100, 1);
    END IF;
    RAISE NOTICE 'Heat coverage: % percent classified, % unmatched', ROUND(classified * 100, 1), unmatched;

    -- 4. Excluded precincts never reach the scorecard.
    SELECT COUNT(*) INTO leaked
      FROM mart.precinct_scorecard
      JOIN ref.excluded_precinct USING (precinct);
    IF leaked > 0 THEN
        RAISE EXCEPTION 'Scope failed: % excluded precincts in the scorecard', leaked;
    END IF;
    RAISE NOTICE 'Scope: no excluded precincts in the scorecard';

    -- 5. Renewal window shares sum to one for every precinct.
    SELECT COUNT(*) INTO bad_shares
      FROM (SELECT precinct FROM mart.precinct_window
            GROUP BY precinct HAVING ABS(SUM(tree_share) - 1) > 0.001) AS s;
    IF bad_shares > 0 THEN
        RAISE EXCEPTION 'Window shares failed for % precincts', bad_shares;
    END IF;
    RAISE NOTICE 'Window shares: all precincts sum to 1';

    -- 6. The spend profile reconciles to the scheduled replacement cost.
    SELECT SUM(reactive_cost_aud) INTO capex_total
      FROM mart.capex_profile WHERE precinct = 'All precincts';
    SELECT SUM(scheduled_cost_aud) INTO cost_total FROM mart.precinct_scorecard;
    IF ABS(capex_total - cost_total) > 100 THEN
        RAISE EXCEPTION 'Capex reconciliation failed: % against %', capex_total, cost_total;
    END IF;
    RAISE NOTICE 'Capex reconciliation: % AUD scheduled', ROUND(cost_total);

    -- 7. Ranked precincts score 0 to 100; small precincts are unranked.
    SELECT COUNT(*) INTO bad_index
      FROM mart.precinct_scorecard
     WHERE (NOT low_confidence AND (cliff_index IS NULL OR cliff_index NOT BETWEEN 0 AND 100))
        OR (low_confidence AND cliff_index IS NOT NULL);
    IF bad_index > 0 THEN
        RAISE EXCEPTION 'Priority score failed for % precincts', bad_index;
    END IF;
    RAISE NOTICE 'Priority score: all ranked precincts within 0 to 100';
END
$$;
