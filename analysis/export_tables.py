"""Export the result tables and headline figures cited in the brief."""
import json

from utils import CITY_TOTAL, TABLE_DIR, query, tree_type


def main():
    TABLE_DIR.mkdir(parents=True, exist_ok=True)

    scorecard = query("SELECT * FROM mart.precinct_scorecard ORDER BY cliff_rank NULLS LAST, precinct")
    scorecard.to_csv(TABLE_DIR / "precinct_scorecard.csv", index=False)

    window = query(
        """
        SELECT pw.precinct, w.label AS renewal_window, pw.tree_count, pw.tree_share,
               pw.replacement_cost_aud, pw.imputed_cost_share, pw.avg_hvi_score
        FROM mart.precinct_window AS pw
        JOIN ref.renewal_window AS w USING (renewal_window_code)
        ORDER BY pw.precinct, w.sort_order
        """
    )
    window.to_csv(TABLE_DIR / "precinct_window.csv", index=False)

    micro_cliffs = query(
        """
        SELECT cluster_rank, precinct, located_in, tree_count, dominant_genus,
               dominant_genus_share, replacement_cost_aud, footprint_m2,
               trees_per_ha, avg_hvi_score,
               ROUND(ST_Y(ST_Transform(ST_Centroid(geom), 4326))::NUMERIC, 6) AS latitude,
               ROUND(ST_X(ST_Transform(ST_Centroid(geom), 4326))::NUMERIC, 6) AS longitude
        FROM mart.micro_cliff
        WHERE horizon = 'near_term'
        ORDER BY cluster_rank
        LIMIT 25
        """
    )
    micro_cliffs.insert(4, "tree_type", micro_cliffs["dominant_genus"].map(tree_type))
    micro_cliffs.to_csv(TABLE_DIR / "micro_cliffs_near_term.csv", index=False)

    capex = query(
        """
        SELECT ((year_offset - 1) / 10) * 10 + 1 AS decade_start,
               ((year_offset - 1) / 10) * 10 + 10 AS decade_end,
               SUM(reactive_cost_aud) AS reactive_cost_aud,
               SUM(levelled_budget_aud) AS levelled_cost_aud
        FROM mart.capex_profile
        WHERE precinct = %s
        GROUP BY 1, 2
        ORDER BY 1
        """,
        (CITY_TOTAL,),
    )
    capex.to_csv(TABLE_DIR / "capex_by_decade.csv", index=False)

    city = query(
        """
        SELECT MAX(levelled_budget_aud) AS levelled_budget_aud,
               MAX(reactive_cost_aud) AS peak_reactive_aud,
               SUM(reactive_cost_aud) FILTER (WHERE year_offset <= 20) AS near_term_reactive_aud
        FROM mart.capex_profile
        WHERE precinct = %s
        """,
        (CITY_TOTAL,),
    ).iloc[0]
    totals = query(
        """
        SELECT COUNT(*) AS trees,
               COUNT(*) FILTER (WHERE f.is_near_term) AS near_term_trees,
               COUNT(*) FILTER (WHERE NOT f.is_assessed) AS not_assessed_trees,
               COUNT(*) FILTER (WHERE f.dbh_source <> 'measured') AS imputed_dbh_trees,
               SUM(f.replacement_cost_aud) FILTER (WHERE f.is_near_term) AS near_term_cost_aud,
               SUM(f.replacement_cost_aud) FILTER (WHERE NOT f.is_assessed) AS not_assessed_cost_aud
        FROM core.tree_feature AS f
        WHERE f.precinct_in_scope
        """
    ).iloc[0]
    near_term_clusters = query(
        """
        SELECT COUNT(*) AS clusters, SUM(tree_count) AS clustered_trees
        FROM mart.micro_cliff
        WHERE horizon = 'near_term'
        """
    ).iloc[0]

    ranked = scorecard[~scorecard["low_confidence"]]
    watch = scorecard[scorecard["low_confidence"]]
    top = ranked.head(5)
    key_figures = {
        "trees_in_scope": int(totals.trees),
        "near_term_trees": int(totals.near_term_trees),
        "near_term_cost_aud": round(float(totals.near_term_cost_aud)),
        "not_assessed_trees": int(totals.not_assessed_trees),
        "not_assessed_cost_aud": round(float(totals.not_assessed_cost_aud)),
        "imputed_dbh_trees": int(totals.imputed_dbh_trees),
        "levelled_budget_aud_per_year": round(float(city.levelled_budget_aud)),
        "peak_reactive_aud_per_year": round(float(city.peak_reactive_aud)),
        "near_term_reactive_aud_20_years": round(float(city.near_term_reactive_aud)),
        "near_term_micro_cliffs": int(near_term_clusters.clusters),
        "near_term_trees_in_micro_cliffs": int(near_term_clusters.clustered_trees),
        "top_precincts": [
            {
                "rank": int(r.cliff_rank),
                "precinct": r.precinct,
                "cliff_index": float(r.cliff_index),
                "near_term_cost_aud": round(float(r.near_term_cost_aud)),
                "near_term_share": float(r.near_term_share),
                "avg_hvi_score": float(r.avg_hvi_score),
            }
            for r in top.itertuples()
        ],
        "watch_list": [
            {
                "precinct": r.precinct,
                "tree_count": int(r.tree_count),
                "near_term_trees": int(r.near_term_trees),
                "near_term_share": float(r.near_term_share),
            }
            for r in watch.itertuples()
        ],
    }
    with open(TABLE_DIR / "key_figures.json", "w") as f:
        json.dump(key_figures, f, indent=2)

    print(f"Saved tables to {TABLE_DIR}")


if __name__ == "__main__":
    main()
