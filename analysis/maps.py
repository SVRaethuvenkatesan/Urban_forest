"""Maps and spatial charts for the location based stakeholder questions.

04  Q4  Heat vulnerability against renewal cost, by precinct
05  Q4  Map of where heat risk and renewal cost overlap
06  Q5  Map and priority list of tree groups to renew first
Also writes the interactive map and GeoJSON layers.
"""
import json

import folium
from adjustText import adjust_text
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib import patheffects
from matplotlib.patches import Patch

from utils import (
    AQUA, BASELINE, BLUE, GEOJSON_DIR, INK, INK_MUTED, INK_SECONDARY, MAP_DIR,
    NEUTRAL, ORANGE, SURFACE, THOUSANDS, add_header, apply_style, draw_geojson,
    geojson_bounds, query, save, thousands, tree_type,
)

HALO = [patheffects.withStroke(linewidth=3, foreground=SURFACE)]

GROUPS = {
    "both": ("Higher heat risk and higher renewal cost", ORANGE),
    "cost": ("Higher renewal cost only", BLUE),
    "heat": ("Higher heat risk only", AQUA),
    "neither": ("Lower on both", NEUTRAL),
    "small": ("Too small to rank", SURFACE),
}


def load_precincts():
    """Scorecard with precinct outlines and a heat and cost group for each precinct."""
    precincts = query(
        """
        SELECT s.*,
               ST_AsGeoJSON(pa.geom) AS geom_mga,
               ST_AsGeoJSON(ST_Transform(pa.geom, 4326), 6) AS geom_wgs84,
               ST_X(ST_PointOnSurface(pa.geom)) AS label_x,
               ST_Y(ST_PointOnSurface(pa.geom)) AS label_y
        FROM mart.precinct_scorecard AS s
        JOIN mart.precinct_area AS pa USING (precinct)
        ORDER BY s.cliff_rank NULLS LAST, s.precinct
        """
    )
    ranked = precincts[~precincts["low_confidence"]]
    heat_mid = ranked["avg_hvi_score"].median()
    cost_mid = ranked["near_term_cost_per_ha"].median()
    high_heat = precincts["avg_hvi_score"] > heat_mid
    high_cost = precincts["near_term_cost_per_ha"] > cost_mid
    precincts["group"] = np.select(
        [precincts["low_confidence"], high_heat & high_cost, high_cost, high_heat],
        ["small", "both", "cost", "heat"], default="neither",
    )
    precincts.attrs.update(heat_mid=heat_mid, cost_mid=cost_mid)
    return precincts


def load_micro_cliffs():
    return query(
        """
        SELECT cluster_rank, tree_count, replacement_cost_aud, dominant_genus,
               dominant_genus_share, precinct, located_in, avg_hvi_score, footprint_m2,
               ST_X(ST_Centroid(geom)) AS x, ST_Y(ST_Centroid(geom)) AS y,
               ST_AsGeoJSON(ST_Transform(geom, 4326), 6) AS geom_wgs84
        FROM mart.micro_cliff
        WHERE horizon = 'near_term'
        ORDER BY cluster_rank
        """
    )


def overlap_names(precincts):
    names = precincts.loc[precincts["group"] == "both"].sort_values("cliff_rank")["precinct"].tolist()
    return ", ".join(names[:-1]) + f" and {names[-1]}" if len(names) > 1 else "".join(names)


def heat_vs_renewal_cost(precincts):
    """Q4. One dot per precinct: heat vulnerability against renewal cost per hectare."""
    heat_mid, cost_mid = precincts.attrs["heat_mid"], precincts.attrs["cost_mid"]
    x, y = precincts["avg_hvi_score"], precincts["near_term_cost_per_ha"]
    sizes = 60 + 1100 * precincts["tree_count"] / precincts["tree_count"].max()

    fig, ax = plt.subplots(figsize=(12, 7.5))
    add_header(
        fig,
        f"{overlap_names(precincts)} face both higher heat risk and higher renewal cost",
        "Each dot is a precinct, sized by its number of trees. The shaded corner is where to act first.",
        question="Q4  Urban heat officer: where does canopy loss coincide with heat vulnerability?",
    )
    x_max, y_max = x.max() * 1.06, y.max() * 1.15
    ax.fill_between([heat_mid, x_max], cost_mid, y_max, color=ORANGE, alpha=0.08, linewidth=0)
    ax.text(x_max - 0.02, y_max * 0.97, "Act first: hotter and costlier", ha="right", va="top",
            fontsize=10.5, color=ORANGE, fontweight="bold")
    ax.axvline(heat_mid, color=BASELINE, linestyle="--", linewidth=1)
    ax.axhline(cost_mid, color=BASELINE, linestyle="--", linewidth=1)

    solid = ~precincts["low_confidence"]
    colors = [ORANGE if g == "both" else BLUE for g in precincts["group"]]
    ax.scatter(x[solid], y[solid], s=sizes[solid], c=np.array(colors)[solid], alpha=0.85,
               edgecolor=SURFACE, linewidth=2)
    ax.scatter(x[~solid], y[~solid], s=sizes[~solid], facecolor="none", edgecolor=INK_MUTED,
               linewidth=1.5)

    ax.set_xlim(x.min() - 0.08, x_max)
    ax.set_ylim(-y.max() * 0.1, y_max)
    labels = [ax.text(row.avg_hvi_score + 0.02, row.near_term_cost_per_ha,
                      row.precinct + (" (small)" if row.low_confidence else ""),
                      fontsize=9, color=INK_SECONDARY, path_effects=HALO)
              for row in precincts.itertuples()]
    adjust_text(labels, x=x.to_numpy(), y=y.to_numpy(), ax=ax, expand=(1.3, 1.6),
                arrowprops={"arrowstyle": "-", "color": BASELINE, "lw": 0.8})

    ax.yaxis.set_major_formatter(THOUSANDS)
    ax.set_xlabel("How heat vulnerable residents are  (Heat Vulnerability Index, 1 = low, 5 = high)")
    ax.set_ylabel("Replacement cost due in 20 years, per hectare")
    save(fig, "04_heat_vs_renewal_cost.png",
         note="Dashed lines mark the middle precinct on each measure. Hollow dots are precincts with under "
              "100 trees. Replacement costs are estimates.")


def heat_and_cost_map(precincts):
    """Q4. Precincts coloured by whether heat risk and renewal cost overlap."""
    fig = plt.figure(figsize=(12, 9))
    add_header(
        fig,
        f"Where heat risk and renewal cost overlap: {overlap_names(precincts)}",
        "Precincts are compared with the middle precinct on heat vulnerability and on renewal cost per hectare.",
        question="Q4  Urban heat officer: where does canopy loss coincide with heat vulnerability?",
    )
    ax = fig.add_axes((0.01, 0.05, 0.98, 0.80))

    for row in precincts.sort_values("area_ha", ascending=False).itertuples():
        label, color = GROUPS[row.group]
        draw_geojson(ax, row.geom_mga, facecolor=color, edgecolor=SURFACE if row.group != "small" else INK_MUTED,
                     linewidth=1.5 if row.group != "small" else 0.8, alpha=0.9,
                     hatch="///" if row.group == "small" else None)
    for row in precincts.itertuples():
        ax.text(row.label_x, row.label_y, row.precinct, ha="center", va="center",
                fontsize=8.5 if row.group != "small" else 7.5,
                fontweight="bold" if row.group == "both" else "normal",
                color=INK, path_effects=HALO)

    xmin, ymin, xmax, ymax = geojson_bounds(precincts["geom_mga"])
    ax.set_xlim(xmin, xmax + (xmax - xmin) * 0.35)
    ax.set_ylim(ymin, ymax)
    ax.set_aspect("equal")
    ax.axis("off")
    handles = [Patch(facecolor=color, edgecolor=INK_MUTED if key == "small" else color,
                     hatch="///" if key == "small" else None, label=label)
               for key, (label, color) in GROUPS.items()]
    ax.legend(handles=handles, loc="upper right", fontsize=10, title="Precinct group",
              title_fontsize=10.5)
    save(fig, "05_heat_and_cost_map.png", top=None,
         note="Precinct shapes are drawn around their trees, not official boundaries, and may overlap. "
              "Replacement costs are estimates.")


def where_to_start_map(precincts, micro_cliffs, top_n=15):
    """Q5. Groups of neighbouring trees due together, with a priority list for crews."""
    top = micro_cliffs.head(top_n)
    rest = micro_cliffs.iloc[top_n:]
    lead_precinct = top["precinct"].mode().iloc[0]

    fig = plt.figure(figsize=(15, 9))
    add_header(
        fig,
        f"Start with {len(micro_cliffs)} groups of neighbouring trees that are due together",
        f"Each dot is a group of at least 5 trees within 15 m of each other, all due in the next 20 years. "
        f"The largest are park plantings in {lead_precinct}.",
        question="Q5  Arborist operations lead: which streets and blocks should crews renew first?",
    )
    ax_map = fig.add_axes((0.01, 0.05, 0.55, 0.80))
    ax_table = fig.add_axes((0.58, 0.05, 0.41, 0.78))

    for row in precincts.itertuples():
        draw_geojson(ax_map, row.geom_mga, facecolor="#f0efec", edgecolor=BASELINE, linewidth=0.8)
        ax_map.text(row.label_x, row.label_y, row.precinct, ha="center", va="center", fontsize=7.5,
                    color=INK_MUTED, path_effects=HALO)

    scale = 350 / micro_cliffs["tree_count"].max()
    ax_map.scatter(rest["x"], rest["y"], s=12 + rest["tree_count"] * scale, color=BLUE, alpha=0.6,
                   edgecolor=SURFACE, linewidth=0.8, label="Tree group due in 20 years")
    ax_map.scatter(top["x"], top["y"], s=12 + top["tree_count"] * scale, color=ORANGE,
                   edgecolor=SURFACE, linewidth=1.5, label=f"Top {top_n} largest groups")
    xmin, ymin, xmax, ymax = geojson_bounds(precincts["geom_mga"])
    ax_map.set_xlim(xmin, xmax)
    ax_map.set_ylim(ymin, ymax)
    numbers = [ax_map.text(row.x, row.y, str(row.cluster_rank), fontsize=9, fontweight="bold",
                           color=INK, path_effects=HALO)
               for row in top.itertuples()]
    adjust_text(numbers, x=top["x"].to_numpy(), y=top["y"].to_numpy(), ax=ax_map,
                expand=(1.6, 1.8), arrowprops={"arrowstyle": "-", "color": INK_MUTED, "lw": 0.6})
    ax_map.set_aspect("equal")
    ax_map.axis("off")
    ax_map.legend(loc="lower left", fontsize=10)

    ax_table.axis("off")
    header = ["#", "Precinct", "Setting", "Trees", "Main tree type", "Est. cost"]
    rows = [[str(r.cluster_rank), r.precinct, r.located_in or "", str(r.tree_count),
             tree_type(r.dominant_genus), thousands(r.replacement_cost_aud)]
            for r in top.itertuples()]
    table = ax_table.table(cellText=rows, colLabels=header, loc="upper left", cellLoc="left",
                           colWidths=[0.06, 0.24, 0.1, 0.09, 0.37, 0.12])
    table.auto_set_font_size(False)
    table.set_fontsize(9.5)
    table.scale(1, 1.6)
    for (row_index, _), cell in table.get_celld().items():
        cell.set_edgecolor(BASELINE)
        cell.set_linewidth(0.5)
        cell.set_facecolor("#f4f3ef" if row_index == 0 else SURFACE)
        if row_index == 0:
            cell.set_text_props(fontweight="bold", color=INK)
    ax_table.set_title("Priority list for field crews", loc="left", fontsize=12, fontweight="bold")

    save(fig, "06_where_to_start_map.png", top=None,
         note="Locations of every group are in outputs/tables/micro_cliffs_near_term.csv. "
              "Replacement costs are estimates.")


def feature_collection(frame, geometry_column, properties):
    features = []
    for record in frame.to_dict("records"):
        props = {}
        for key in properties:
            value = record[key]
            if isinstance(value, np.integer):
                value = int(value)
            elif isinstance(value, (np.floating, float)):
                value = None if np.isnan(value) else round(float(value), 4)
            elif isinstance(value, np.bool_):
                value = bool(value)
            elif value is None or value is pd.NA:
                value = None
            props[key] = value
        features.append({"type": "Feature", "geometry": json.loads(record[geometry_column]),
                         "properties": props})
    return {"type": "FeatureCollection", "features": features}


def export_geojson(precincts, micro_cliffs):
    GEOJSON_DIR.mkdir(parents=True, exist_ok=True)
    precincts = precincts.assign(group_label=precincts["group"].map(lambda g: GROUPS[g][0]),
                                 fill=precincts["group"].map(lambda g: GROUPS[g][1]))
    micro_cliffs = micro_cliffs.assign(tree_type=micro_cliffs["dominant_genus"].map(tree_type))
    precinct_layer = feature_collection(precincts, "geom_wgs84", [
        "precinct", "cliff_rank", "cliff_index", "tree_count", "area_ha", "near_term_trees",
        "near_term_share", "near_term_cost_aud", "near_term_cost_per_ha", "avg_hvi_score",
        "low_confidence", "group_label", "fill",
    ])
    cliff_layer = feature_collection(micro_cliffs, "geom_wgs84", [
        "cluster_rank", "precinct", "located_in", "tree_count", "tree_type",
        "dominant_genus_share", "replacement_cost_aud", "footprint_m2", "avg_hvi_score",
    ])
    for name, layer in [("precinct_scorecard", precinct_layer), ("micro_cliffs_near_term", cliff_layer)]:
        with open(GEOJSON_DIR / f"{name}.geojson", "w") as f:
            json.dump(layer, f)
    print(f"Saved GeoJSON layers to {GEOJSON_DIR}")
    return precinct_layer, cliff_layer


def interactive_map(precinct_layer, cliff_layer):
    hvi = query(
        """
        SELECT z.sa2_name, z.hvi_score,
               ST_AsGeoJSON(ST_Transform(ST_SimplifyPreserveTopology(z.geom, 5), 4326), 6) AS geom
        FROM core.hvi_zone AS z
        WHERE z.hvi_score IS NOT NULL
          AND z.geom && (SELECT ST_Extent(geom) FROM mart.precinct_area)
        """
    )
    hvi_layer = feature_collection(hvi, "geom", ["sa2_name", "hvi_score"])
    heat_colors = {1: "#fde5d6", 2: "#f7b99b", 3: "#ec835a", 4: "#d95926", 5: "#a3360d"}

    fmap = folium.Map(location=[-37.806, 144.95], zoom_start=13, tiles="OpenStreetMap")
    folium.GeoJson(
        hvi_layer, name="Heat vulnerability of residents", show=False,
        style_function=lambda f: {"fillColor": heat_colors[f["properties"]["hvi_score"]],
                                  "color": "#ffffff", "weight": 0.3, "fillOpacity": 0.55},
        tooltip=folium.GeoJsonTooltip(["sa2_name", "hvi_score"], ["Area", "Heat vulnerability (1 to 5)"]),
    ).add_to(fmap)
    folium.GeoJson(
        precinct_layer, name="Precinct priority",
        style_function=lambda f: {"fillColor": f["properties"]["fill"], "color": "#52514e",
                                  "weight": 1, "fillOpacity": 0.5},
        tooltip=folium.GeoJsonTooltip(
            ["precinct", "cliff_rank", "cliff_index", "group_label", "near_term_trees", "near_term_cost_aud"],
            ["Precinct", "Priority rank", "Priority score", "Group", "Trees due in 20 years",
             "Cost due in 20 years (AUD)"],
            localize=True,
        ),
    ).add_to(fmap)
    folium.GeoJson(
        cliff_layer, name="Tree groups due together",
        style_function=lambda f: {"fillColor": ORANGE, "color": ORANGE, "weight": 1, "fillOpacity": 0.7},
        tooltip=folium.GeoJsonTooltip(
            ["cluster_rank", "precinct", "located_in", "tree_count", "tree_type", "replacement_cost_aud"],
            ["Rank", "Precinct", "Setting", "Trees", "Main tree type", "Est. cost (AUD)"],
            localize=True,
        ),
    ).add_to(fmap)
    folium.LayerControl(collapsed=False).add_to(fmap)

    MAP_DIR.mkdir(parents=True, exist_ok=True)
    path = MAP_DIR / "canopy_cliff_map.html"
    fmap.save(str(path))
    print(f"Saved {path}")


def main():
    apply_style()
    precincts = load_precincts()
    micro_cliffs = load_micro_cliffs()
    heat_vs_renewal_cost(precincts)
    heat_and_cost_map(precincts)
    where_to_start_map(precincts, micro_cliffs)
    interactive_map(*export_geojson(precincts, micro_cliffs))


if __name__ == "__main__":
    main()
