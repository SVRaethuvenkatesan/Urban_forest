"""Recompute the precinct ranking under alternative assumptions.

Uses the same method as sql/08_build_precinct_scorecard.sql. The base case
must reproduce the stored score before any scenario is written.
"""
import numpy as np
import pandas as pd

from utils import TABLE_DIR, query

SCENARIOS = {
    "Base case": {},
    "Heat weighted double": {"weights": (1, 1, 2)},
    "Cost weighted double": {"weights": (2, 1, 1)},
    "Share weighted double": {"weights": (1, 2, 1)},
    "Heat excluded": {"weights": (1, 1, 0)},
    "Near term 10 years": {"horizon": 10},
    "Measured DBH only": {"cost": "measured"},
    "Flat cost per tree": {"cost": "flat"},
}


def load_inputs():
    """Per precinct inputs for every ranked (not low confidence) precinct."""
    return query(
        """
        SELECT
            pa.precinct,
            pa.area_ha,
            pa.tree_count,
            COUNT(*) FILTER (WHERE f.renewal_window_code = 'lt10') AS trees_10,
            COUNT(*) FILTER (WHERE f.is_near_term) AS trees_20,
            COALESCE(SUM(f.replacement_cost_aud) FILTER (WHERE f.renewal_window_code = 'lt10'), 0) AS cost_10,
            COALESCE(SUM(f.replacement_cost_aud) FILTER (WHERE f.is_near_term), 0) AS cost_20,
            COALESCE(SUM(f.replacement_cost_aud)
                FILTER (WHERE f.is_near_term AND f.dbh_source = 'measured'), 0) AS cost_20_measured,
            AVG(h.hvi_score) AS avg_hvi_score
        FROM mart.precinct_area AS pa
        JOIN mart.precinct_scorecard AS s ON s.precinct = pa.precinct AND NOT s.low_confidence
        JOIN core.tree AS t ON t.precinct = pa.precinct
        JOIN core.tree_feature AS f USING (tree_id)
        JOIN core.tree_hvi AS h USING (tree_id)
        GROUP BY pa.precinct, pa.area_ha, pa.tree_count
        """
    )


def percent_rank(series):
    """Equivalent of the SQL PERCENT_RANK window function."""
    n = len(series)
    return (series.rank(method="min") - 1) / (n - 1) if n > 1 else series * 0


def score(inputs, weights=(1, 1, 1), horizon=20, cost="modelled"):
    """Compute the cliff index and rank for one scenario."""
    trees = inputs[f"trees_{horizon}"]
    if cost == "measured":
        near_cost = inputs["cost_20_measured"]
    elif cost == "flat":
        near_cost = trees.astype(float)
    else:
        near_cost = inputs[f"cost_{horizon}"]

    components = pd.DataFrame({
        "cost_density": percent_rank(near_cost / inputs["area_ha"]),
        "near_term_share": percent_rank(trees / inputs["tree_count"]),
        "heat": percent_rank(inputs["avg_hvi_score"].fillna(0)),
    })
    w = np.array(weights, dtype=float)
    index = 100 * (components.to_numpy() @ w) / w.sum()
    result = pd.DataFrame({"precinct": inputs["precinct"], "cliff_index": index})
    result["cliff_rank"] = result["cliff_index"].rank(method="min", ascending=False).astype(int)
    return result


def main():
    inputs = load_inputs()

    frames = []
    for name, options in SCENARIOS.items():
        result = score(inputs, **options)
        result.insert(1, "scenario", name)
        frames.append(result)
    results = pd.concat(frames, ignore_index=True)

    stored = query("SELECT precinct, cliff_index FROM mart.precinct_scorecard WHERE NOT low_confidence")
    base = results[results["scenario"] == "Base case"].merge(stored, on="precinct", suffixes=("", "_sql"))
    mismatch = (base["cliff_index"] - base["cliff_index_sql"]).abs().max()
    if mismatch > 0.1:
        raise AssertionError(f"Base scenario does not reproduce the SQL index (max difference {mismatch:.3f})")

    results["cliff_index"] = results["cliff_index"].round(1)
    TABLE_DIR.mkdir(parents=True, exist_ok=True)
    results.to_csv(TABLE_DIR / "rank_sensitivity.csv", index=False)
    print(f"Saved {TABLE_DIR / 'rank_sensitivity.csv'} ({len(SCENARIOS)} scenarios)")


if __name__ == "__main__":
    main()
