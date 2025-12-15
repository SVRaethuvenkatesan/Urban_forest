"""Diagnostic k distance plot used to choose the DBSCAN radius.

Not part of the pipeline. Run after the pipeline when revisiting the
dbscan_eps_m parameter: python analysis/tune_dbscan_eps.py
"""
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from sklearn.neighbors import NearestNeighbors

from utils import BLUE, INK_SECONDARY, ORANGE, apply_style, query

OUTPUT = Path("outputs/diagnostics/k_distance_plot.png")


def main():
    params = query(
        """
        SELECT parameter, value FROM ref.model_parameter
        WHERE parameter IN ('dbscan_eps_m', 'dbscan_min_points')
        """
    ).set_index("parameter")["value"]
    min_points = int(params["dbscan_min_points"])
    eps = float(params["dbscan_eps_m"])

    coords = query(
        """
        SELECT ST_X(t.geom) AS x, ST_Y(t.geom) AS y
        FROM core.tree AS t
        JOIN core.tree_feature AS f USING (tree_id)
        WHERE f.is_near_term AND f.precinct_in_scope
        """
    )[["x", "y"]].to_numpy()

    # The query point is its own first neighbour, so ask for k plus one.
    distances, _ = NearestNeighbors(n_neighbors=min_points + 1).fit(coords).kneighbors(coords)
    k_distance = np.sort(distances[:, -1])

    apply_style()
    fig, ax = plt.subplots(figsize=(9, 5.5))
    ax.plot(k_distance, color=BLUE, linewidth=2)
    ax.axhline(eps, color=ORANGE, linewidth=1.5, linestyle="--")
    ax.text(0, eps, f" Chosen eps {eps:.0f} m", va="bottom", color=INK_SECONDARY, fontsize=9)
    ax.set_ylim(0, np.percentile(k_distance, 97))
    ax.set_xlabel("Near term trees, sorted by distance")
    ax.set_ylabel(f"Distance to neighbour {min_points} (m)")
    ax.set_title("DBSCAN k distance plot for near term trees")
    fig.tight_layout()

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUTPUT, dpi=150)
    print(f"Saved {OUTPUT}")


if __name__ == "__main__":
    main()
