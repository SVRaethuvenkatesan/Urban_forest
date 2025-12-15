"""Charts written for a non technical audience, one per stakeholder question.

00  Key findings at a glance
01  Q1  How much renewal spend falls due, and when?
02  Q2  Which precincts should be renewed first?
03  Q3  When are each precinct's trees due?
07  Q6  Which tree types drive the near term liability?
08  Q7  How complete is the data?
09  Q8  Does the ranking hold if assumptions change?

Maps (04 to 06) are produced by maps.py.
"""
import json

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.patches import FancyBboxPatch
from matplotlib.ticker import PercentFormatter

from utils import (
    BASELINE, BLUE, CITY_TOTAL, GRID, INK, INK_MUTED, INK_SECONDARY, MILLIONS,
    NEUTRAL, ORANGE, PANEL, SEQUENTIAL_BLUE, SURFACE, TABLE_DIR, add_header,
    apply_style, millions, number_word, query, renewal_windows, save, tree_type,
)

DRIVER_LABELS = {
    "pct_cost_density": "Main reason: high replacement cost",
    "pct_near_term_share": "Main reason: many trees due soon",
    "pct_heat": "Main reason: heat vulnerable residents",
}
GENUS_PLURAL = {"Eucalyptus": "Gum trees", "Ulmus": "Elms", "Acacia": "Wattles", "Platanus": "Plane trees"}
SOURCE_SHORT = "Replacement costs are estimates."


def key_findings():
    """A one page summary of the headline numbers."""
    figures = json.loads((TABLE_DIR / "key_figures.json").read_text())
    top = figures["top_precincts"][:3]

    fig = plt.figure(figsize=(13, 6.4))
    add_header(
        fig,
        "Melbourne's urban forest: renewal at a glance",
        f"{figures['trees_in_scope']:,} council trees analysed across 17 precincts",
    )

    tiles = [
        (millions(figures["peak_reactive_aud_per_year"]) + " a year",
         "Peak cost in years 21 to 30 if trees\nare replaced only when they fail", ORANGE),
        (millions(figures["levelled_budget_aud_per_year"], decimals=2) + " a year",
         "Steady budget, starting now, that\nreplaces every tree on time", BLUE),
        (f"{figures['near_term_trees']:,} trees",
         "Due for renewal within\nthe next 20 years", INK),
        (f"{figures['not_assessed_trees']:,} trees",
         "Never assessed, so not yet\nin any renewal budget", INK),
    ]
    width, gap, left, bottom, height = 0.225, 0.02, 0.015, 0.52, 0.27
    for i, (value, caption, color) in enumerate(tiles):
        x = left + i * (width + gap)
        fig.patches.append(FancyBboxPatch((x, bottom), width, height, transform=fig.transFigure,
                                          boxstyle="round,pad=0,rounding_size=0.012",
                                          facecolor=PANEL, edgecolor=GRID, linewidth=1))
        fig.text(x + 0.018, bottom + height - 0.06, value, fontsize=22, fontweight="bold",
                 color=color, va="top")
        fig.text(x + 0.018, bottom + 0.045, caption, fontsize=10.5, color=INK_SECONDARY, va="bottom")

    priorities = "    ".join(f"{p['rank']}. {p['precinct']}" for p in top)
    fig.text(0.015, 0.42, "Renew first", fontsize=11, fontweight="bold", color=INK_MUTED)
    fig.text(0.015, 0.36, priorities, fontsize=15, fontweight="bold", color=INK)
    fig.text(0.015, 0.25,
             f"Start on the ground with {figures['near_term_micro_cliffs']} groups of neighbouring trees "
             f"that are due together ({figures['near_term_trees_in_micro_cliffs']:,} trees).",
             fontsize=11, color=INK_SECONDARY)
    fig.text(0.015, 0.19,
             f"Close the data gap: {millions(figures['not_assessed_cost_aud'])} of replacement cost sits with "
             "trees that have never been assessed.",
             fontsize=11, color=INK_SECONDARY)
    save(fig, "00_key_findings.png", top=None)


def renewal_spend_by_year():
    """Q1. Annual cost if trees are replaced at end of life, against a steady budget."""
    capex = query(
        "SELECT * FROM mart.capex_profile WHERE precinct = %s ORDER BY year_offset", (CITY_TOTAL,)
    )
    figures = json.loads((TABLE_DIR / "key_figures.json").read_text())
    years = capex["year_offset"]
    spend = capex["reactive_cost_aud"]
    budget = capex["levelled_budget_aud"].iloc[0]
    near = spend[years <= 20].max()
    peak = spend.max()
    cliff_share = spend[(years > 20) & (years <= 40)].sum() / spend.sum()

    fig, ax = plt.subplots(figsize=(12, 6.8))
    add_header(
        fig,
        f"Renewal costs jump {number_word(round(peak / near))} times higher after year 20",
        f"A steady {millions(budget, decimals=2)} a year, starting now, replaces every tree on time and "
        "avoids the spike.",
        question="Q1  Capital works planner: how much renewal spend falls due, and when?",
    )

    ax.axvspan(20.5, 40.5, color=ORANGE, alpha=0.07, linewidth=0)
    ax.text(30.5, peak * 1.13, f"The cliff: {cliff_share:.0%} of the cost falls in these 20 years",
            ha="center", fontsize=10, color=ORANGE, fontweight="bold")
    ax.bar(years, spend, width=0.8, color=BLUE, label="Cost if trees are replaced only at end of life")
    ax.axhline(budget, color=ORANGE, linewidth=2.5, label="Steady annual budget")
    ax.text(60.5, budget, f" {millions(budget, decimals=2)}\n a year", va="center", ha="left",
            color=ORANGE, fontsize=10, fontweight="bold")

    for start in range(1, 61, 10):
        value = spend[years == start].iloc[0]
        ax.text(start + 4.5, value + peak * 0.02, f"{millions(value)}/yr", ha="center",
                fontsize=9, color=INK_SECONDARY)

    ax.yaxis.set_major_formatter(MILLIONS)
    ax.set_ylim(0, peak * 1.2)
    ax.set_xlim(0, 64)
    ax.set_xticks([1, 10, 20, 30, 40, 50, 60])
    ax.set_xlabel("Years from now")
    ax.set_ylabel("Replacement cost per year")
    ax.grid(axis="x", visible=False)
    ax.legend(loc="upper left")

    note = (f"Years count from Council's life expectancy assessment. Excludes "
            f"{millions(figures['not_assessed_cost_aud'])} for {figures['not_assessed_trees']:,} trees "
            "never assessed. Costs are estimates.")
    save(fig, "01_renewal_spend_by_year.png", note=note)


def precinct_priority_ranking():
    """Q2. Priority score by precinct, with the main reason for each score."""
    scorecard = query(
        "SELECT * FROM mart.precinct_scorecard WHERE NOT low_confidence ORDER BY cliff_rank DESC, precinct DESC"
    )
    watch = query("SELECT precinct, tree_count FROM mart.precinct_scorecard WHERE low_confidence ORDER BY precinct")
    top_three = scorecard.nsmallest(3, "cliff_rank")["precinct"].tolist()

    fig, ax = plt.subplots(figsize=(12, 7.5))
    add_header(
        fig,
        f"{top_three[0]}, {top_three[1]} and {top_three[2]} should be renewed first",
        "Priority score out of 100, combining trees due in 20 years, their replacement cost per hectare "
        "and residents' heat vulnerability.",
        question="Q2  Asset manager: which precincts face a canopy cliff?",
    )

    y = np.arange(len(scorecard))
    colors = [ORANGE if p in top_three else BLUE for p in scorecard["precinct"]]
    ax.barh(y, scorecard["cliff_index"], height=0.68, color=colors)
    for yi, row in zip(y, scorecard.itertuples()):
        driver = max(DRIVER_LABELS, key=lambda c: getattr(row, c))
        ax.text(row.cliff_index + 1, yi, f"{row.cliff_index:.0f}", va="center", fontsize=10,
                fontweight="bold", color=INK)
        ax.text(row.cliff_index + 5.5, yi, DRIVER_LABELS[driver], va="center",
                fontsize=9, color=INK_MUTED)

    ax.set_yticks(y, [f"{int(r.cliff_rank)}.  {r.precinct}" for r in scorecard.itertuples()])
    ax.set_xlim(0, 118)
    ax.set_xticks([0, 20, 40, 60, 80, 100])
    ax.set_xlabel("Priority score (higher means renew sooner)")
    ax.grid(axis="y", visible=False)
    ax.tick_params(axis="y", length=0)

    small = ", ".join(f"{r.precinct} ({r.tree_count} trees)" for r in watch.itertuples())
    save(fig, "02_precinct_priority_ranking.png",
         note=f"Too small to rank reliably: {small}. " + SOURCE_SHORT)


def trees_due_by_precinct():
    """Q3. Share of each precinct's trees reaching end of life in each period."""
    windows = renewal_windows()
    labels = {
        "lt10": "Under\n10 years", "y11_20": "11 to 20\nyears", "y21_30": "21 to 30\nyears",
        "y31_40": "31 to 40\nyears", "gt40": "Over\n40 years", "not_assessed": "Never\nassessed",
    }
    data = query(
        """
        SELECT pw.precinct, pw.renewal_window_code, pw.tree_share, s.tree_count,
               s.near_term_share, s.low_confidence
        FROM mart.precinct_window AS pw
        JOIN mart.precinct_scorecard AS s USING (precinct)
        """
    )
    order = (data[["precinct", "tree_count", "near_term_share", "low_confidence"]]
             .drop_duplicates().sort_values("near_term_share", ascending=False))
    matrix = (data.pivot(index="precinct", columns="renewal_window_code", values="tree_share")
              .loc[order["precinct"], windows["renewal_window_code"]])

    fig, ax = plt.subplots(figsize=(12, 9))
    add_header(
        fig,
        "Most precincts have their largest group of trees due in 21 to 30 years",
        "Share of each precinct's trees by when they reach end of life. Darker means a larger share.",
        question="Q3  Asset manager: what does each precinct's renewal profile look like?",
    )
    cmap = LinearSegmentedColormap.from_list("blue", SEQUENTIAL_BLUE)
    ax.imshow(matrix.to_numpy(), cmap=cmap, vmin=0, vmax=0.6, aspect="auto")
    for i in range(matrix.shape[0]):
        for j in range(matrix.shape[1]):
            value = matrix.iat[i, j]
            ax.text(j, i, f"{value:.0%}", ha="center", va="center", fontsize=9.5,
                    color=SURFACE if value > 0.35 else INK)

    rows = [f"{r.precinct}{' (small)' if r.low_confidence else ''}   {r.tree_count:,} trees"
            for r in order.itertuples()]
    ax.set_yticks(range(len(rows)), rows)
    ax.set_xticks(range(len(windows)), [labels[c] for c in windows["renewal_window_code"]])
    ax.xaxis.tick_top()
    ax.tick_params(length=0)
    ax.grid(False)
    for spine in ax.spines.values():
        spine.set_visible(False)

    near_columns = int(windows["is_near_term"].sum())
    ax.add_patch(plt.Rectangle((-0.5, -0.5), near_columns, len(rows), fill=False,
                               edgecolor=ORANGE, linewidth=2.5))
    ax.text(near_columns / 2 - 0.5, len(rows) - 0.2, "Due in the next 20 years", ha="center",
            va="top", color=ORANGE, fontsize=10, fontweight="bold")
    save(fig, "03_trees_due_by_precinct.png")


def tree_types_due_soon():
    """Q6. Tree types that make up the next 20 years of renewal."""
    species = query(
        """
        SELECT t.genus, COUNT(*) AS trees, SUM(f.replacement_cost_aud) AS cost_aud
        FROM core.tree AS t
        JOIN core.tree_feature AS f USING (tree_id)
        WHERE f.is_near_term AND f.precinct_in_scope
        GROUP BY t.genus
        ORDER BY trees DESC
        """
    )
    top_n = 10
    top = species.head(top_n).copy()
    top["label"] = top["genus"].map(tree_type)
    rest = species.iloc[top_n:]
    top.loc[len(top)] = [None, rest["trees"].sum(), rest["cost_aud"].sum(), "All other types"]
    top = top.iloc[::-1].reset_index(drop=True)
    total = species["trees"].sum()
    lead = species.head(2)
    costliest = species.nlargest(1, "cost_aud").iloc[0]
    if costliest.genus in lead["genus"].values and costliest.genus != lead.genus.iloc[0]:
        subtitle = (f"{GENUS_PLURAL.get(costliest.genus, tree_type(costliest.genus))} cost the most to "
                    "replace: fewer trees, but larger ones.")
    else:
        subtitle = "Number of trees due and their estimated replacement cost, by tree type."

    fig, (ax_trees, ax_cost) = plt.subplots(1, 2, figsize=(12, 7), sharey=True)
    add_header(
        fig,
        f"{GENUS_PLURAL.get(lead.genus.iloc[0], tree_type(lead.genus.iloc[0]))} and "
        f"{GENUS_PLURAL.get(lead.genus.iloc[1], tree_type(lead.genus.iloc[1])).lower()} make up "
        f"{lead.trees.sum() / total:.0%} of trees due in the next 20 years",
        subtitle,
        question="Q6  Urban forest strategist: which species drive the near term liability?",
    )
    y = np.arange(len(top))
    colors = [NEUTRAL if lbl == "All other types" else BLUE for lbl in top["label"]]

    ax_trees.barh(y, top["trees"], height=0.68, color=colors)
    for yi, value in zip(y, top["trees"]):
        ax_trees.text(value, yi, f"  {value:,.0f}  ({value / total:.0%})", va="center", fontsize=9.5)
    ax_trees.set_yticks(y, top["label"])
    ax_trees.set_xlim(0, top["trees"].max() * 1.4)
    ax_trees.set_title("Number of trees", loc="left", fontsize=11, color=INK_SECONDARY)
    ax_trees.set_xticks([])
    ax_trees.spines["bottom"].set_visible(False)

    ax_cost.barh(y, top["cost_aud"], height=0.68, color=colors)
    for yi, value in zip(y, top["cost_aud"]):
        ax_cost.text(value, yi, f"  {millions(value)}", va="center", fontsize=9.5)
    ax_cost.set_xlim(0, top["cost_aud"].max() * 1.3)
    ax_cost.set_title("Estimated replacement cost", loc="left", fontsize=11, color=INK_SECONDARY)
    ax_cost.set_xticks([])
    ax_cost.spines["bottom"].set_visible(False)
    for ax in (ax_trees, ax_cost):
        ax.grid(False)
        ax.tick_params(axis="y", length=0)
    save(fig, "07_tree_types_due_soon.png")


def data_confidence():
    """Q7. Assessment and measurement gaps behind each precinct's figures."""
    scorecard = query("SELECT * FROM mart.precinct_scorecard ORDER BY not_assessed_share")
    y = np.arange(len(scorecard))
    worst = scorecard[~scorecard["low_confidence"]].nlargest(3, "not_assessed_share")["precinct"].tolist()

    fig, ax = plt.subplots(figsize=(12, 8))
    add_header(
        fig,
        f"{worst[0]}, {worst[1]} and {worst[2]} have the most unassessed trees",
        "Unassessed trees cannot be scheduled for renewal. Estimated trunk sizes make cost figures less certain.",
        question="Q7  Finance and risk: how reliable are these numbers?",
    )
    pairs = scorecard[["not_assessed_share", "imputed_dbh_share"]]
    ax.hlines(y, pairs.min(axis=1), pairs.max(axis=1), color=BASELINE, linewidth=1.5, zorder=1)
    ax.scatter(scorecard["not_assessed_share"], y, s=80, color=BLUE, zorder=3,
               edgecolor=SURFACE, linewidth=2, label="Trees never assessed for remaining life")
    ax.scatter(scorecard["imputed_dbh_share"], y, s=80, color=ORANGE, zorder=3,
               edgecolor=SURFACE, linewidth=2, label="Trees whose trunk size was estimated, not measured")

    ax.set_yticks(y, [f"{r.precinct}{' (small)' if r.low_confidence else ''}" for r in scorecard.itertuples()])
    ax.set_xlim(0, 1.02)
    ax.xaxis.set_major_formatter(PercentFormatter(1.0))
    ax.set_xlabel("Share of the precinct's trees")
    ax.legend(loc="lower right")
    ax.grid(axis="y", visible=False)
    ax.tick_params(axis="y", length=0)
    save(fig, "08_data_confidence.png")


def ranking_robustness():
    """Q8. Range of each precinct's rank across alternative assumptions."""
    results = pd.read_csv(TABLE_DIR / "rank_sensitivity.csv")
    base = results[results["scenario"] == "Base case"].set_index("precinct")["cliff_rank"]
    spread = results.groupby("precinct")["cliff_rank"].agg(["min", "max"])
    order = base.sort_values(ascending=False).index
    y = {precinct: i for i, precinct in enumerate(order)}
    leader = order[-1]
    alternatives = results["scenario"].nunique() - 1

    fig, ax = plt.subplots(figsize=(12, 7.8))
    add_header(
        fig,
        f"{leader} stays in the top {number_word(spread.loc[leader, 'max'])} whatever assumptions we change",
        f"Blue dot: rank in the main result. Grey dots: rank under {alternatives} alternative assumptions. "
        "Short bars mean a stable rank.",
        question="Q8  Executive sponsor: is the ranking robust to our assumptions?",
    )
    for precinct in order:
        ax.hlines(y[precinct], spread.loc[precinct, "min"], spread.loc[precinct, "max"],
                  color=NEUTRAL, linewidth=7, zorder=1, capstyle="round")
    others = results[results["scenario"] != "Base case"]
    ax.scatter(others["cliff_rank"], others["precinct"].map(y), s=26, color=INK_MUTED, zorder=2,
               label="Alternative assumption")
    ax.scatter(base[order], [y[p] for p in order], s=95, color=BLUE, edgecolor=SURFACE,
               linewidth=2, zorder=3, label="Main result")

    ax.set_yticks(range(len(order)), order)
    ax.set_xlim(0.5, len(order) + 0.5)
    ax.set_xticks(range(1, len(order) + 1))
    ax.set_xlabel("Rank (1 means renew first)")
    ax.legend(loc="upper right")
    ax.grid(axis="y", visible=False)
    ax.tick_params(axis="y", length=0)

    note = ("Alternatives: double weight on heat, cost or share of trees due; heat left out; next 10 years "
            "instead of 20; measured trunks only; same cost for every tree.")
    save(fig, "09_ranking_robustness.png", note=note)



def main():
    apply_style()
    key_findings()
    renewal_spend_by_year()
    precinct_priority_ranking()
    trees_due_by_precinct()
    tree_types_due_soon()
    data_confidence()
    ranking_robustness()


if __name__ == "__main__":
    main()
