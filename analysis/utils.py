"""Shared database access, chart styling and output helpers."""
import json
import os
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402
import psycopg2  # noqa: E402
from matplotlib.patches import PathPatch  # noqa: E402
from matplotlib.path import Path as MplPath  # noqa: E402
from matplotlib.ticker import FuncFormatter  # noqa: E402

OUTPUT_DIR = Path("outputs")
FIGURE_DIR = OUTPUT_DIR / "figures"
TABLE_DIR = OUTPUT_DIR / "tables"
MAP_DIR = OUTPUT_DIR / "maps"
GEOJSON_DIR = OUTPUT_DIR / "geojson"

CITY_TOTAL = "All precincts"

SOURCE_NOTE = (
    "Source: City of Melbourne tree register; Victorian Heat Vulnerability Index 2018. "
    "Replacement costs are estimates."
)

# Validated palette: categorical colours are used in this fixed order.
SURFACE = "#fcfcfb"
PANEL = "#f4f3ef"
INK = "#0b0b0b"
INK_SECONDARY = "#52514e"
INK_MUTED = "#898781"
GRID = "#e1e0d9"
BASELINE = "#c3c2b7"
BLUE, ORANGE, AQUA = "#2a78d6", "#eb6834", "#1baf7a"
SERIES = [BLUE, ORANGE, AQUA]
NEUTRAL = "#dcdad3"
SEQUENTIAL_BLUE = ["#f4f8fd", "#cde2fb", "#86b6ef", "#3987e5", "#1c5cab", "#0d366b"]

# Everyday names for the genera that appear most often in the results.
GENUS_NAMES = {
    "Acacia": "Wattle", "Acer": "Maple", "Agonis": "Willow myrtle",
    "Allocasuarina": "She-oak", "Angophora": "Apple myrtle", "Banksia": "Banksia",
    "Brachychiton": "Kurrajong", "Callistemon": "Bottlebrush", "Casuarina": "She-oak",
    "Corymbia": "Spotted gum", "Eucalyptus": "Gum tree", "Ficus": "Fig",
    "Fraxinus": "Ash", "Geijera": "Wilga", "Lophostemon": "Brush box",
    "Melaleuca": "Paperbark", "Myoporum": "Boobialla", "Pittosporum": "Pittosporum",
    "Platanus": "Plane tree", "Populus": "Poplar", "Pyrus": "Ornamental pear",
    "Quercus": "Oak", "Schinus": "Peppercorn", "Tristaniopsis": "Water gum",
    "Ulmus": "Elm",
}


def tree_type(genus):
    """Everyday name with the genus in brackets, for example Elm (Ulmus)."""
    if not genus:
        return "Unknown"
    everyday = GENUS_NAMES.get(genus)
    return f"{everyday} ({genus})" if everyday and everyday != genus else genus


def number_word(n):
    """Spell out whole numbers from two to ten, as in running text."""
    words = {2: "two", 3: "three", 4: "four", 5: "five", 6: "six", 7: "seven", 8: "eight",
             9: "nine", 10: "ten"}
    return words.get(int(n), str(int(n)))


def connect():
    return psycopg2.connect(os.environ["DATABASE_URL"])


def query(sql, params=None):
    """Run a query and return a DataFrame, converting Decimal columns to float."""
    with connect() as conn, conn.cursor() as cur:
        cur.execute(sql, params)
        columns = [c.name for c in cur.description]
        df = pd.DataFrame(cur.fetchall(), columns=columns)
    for col in df.columns:
        if df[col].dtype == object and df[col].map(lambda v: hasattr(v, "as_tuple")).any():
            df[col] = df[col].astype(float)
    return df


def renewal_windows():
    return query(
        """
        SELECT renewal_window_code, label, horizon, is_near_term, start_year, end_year
        FROM ref.renewal_window
        ORDER BY sort_order
        """
    )


def apply_style():
    plt.rcParams.update({
        "figure.facecolor": SURFACE,
        "axes.facecolor": SURFACE,
        "savefig.facecolor": SURFACE,
        "font.family": "DejaVu Sans",
        "font.size": 10.5,
        "text.parse_math": False,
        "text.color": INK,
        "axes.labelcolor": INK_SECONDARY,
        "axes.edgecolor": BASELINE,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.grid": True,
        "axes.axisbelow": True,
        "grid.color": GRID,
        "grid.linewidth": 0.8,
        "xtick.color": INK_MUTED,
        "ytick.color": INK_MUTED,
        "xtick.labelcolor": INK_SECONDARY,
        "ytick.labelcolor": INK_SECONDARY,
        "legend.frameon": False,
    })


def millions(value, _pos=None, decimals=1):
    return f"${value / 1e6:,.{decimals}f}M"


def thousands(value, _pos=None):
    return f"${value / 1e3:,.0f}k"


MILLIONS = FuncFormatter(millions)
THOUSANDS = FuncFormatter(thousands)


def add_header(fig, title, subtitle, question=None):
    """Headline finding, a plain language subtitle and the stakeholder question."""
    if question:
        fig.text(0.015, 0.985, question.upper(), ha="left", va="top", fontsize=8.5,
                 color=INK_MUTED, fontweight="bold")
    fig.text(0.015, 0.955, title, ha="left", va="top", fontsize=16, fontweight="bold", color=INK)
    fig.text(0.015, 0.905, subtitle, ha="left", va="top", fontsize=11, color=INK_SECONDARY)


def save(fig, filename, note=SOURCE_NOTE, top=0.86):
    """Add the footnote, fit the layout below the header and save."""
    FIGURE_DIR.mkdir(parents=True, exist_ok=True)
    fig.text(0.015, 0.012, note, ha="left", va="bottom", fontsize=8.5, color=INK_MUTED)
    if top is not None:
        fig.tight_layout(rect=(0, 0.04, 1, top))
    path = FIGURE_DIR / filename
    fig.savefig(path, dpi=150)
    plt.close(fig)
    print(f"Saved {path}")


def draw_geojson(ax, geometry, **kwargs):
    """Draw a GeoJSON Polygon or MultiPolygon, holes included."""
    geom = json.loads(geometry) if isinstance(geometry, str) else geometry
    polygons = geom["coordinates"] if geom["type"] == "MultiPolygon" else [geom["coordinates"]]
    vertices, codes = [], []
    for polygon in polygons:
        for ring in polygon:
            vertices.extend(ring)
            codes.extend([MplPath.MOVETO] + [MplPath.LINETO] * (len(ring) - 2) + [MplPath.CLOSEPOLY])
    patch = PathPatch(MplPath(vertices, codes), **kwargs)
    ax.add_patch(patch)
    return patch


def geojson_bounds(geometries):
    """Return (xmin, ymin, xmax, ymax) across GeoJSON geometries."""
    xs, ys = [], []
    for geometry in geometries:
        geom = json.loads(geometry) if isinstance(geometry, str) else geometry
        polygons = geom["coordinates"] if geom["type"] == "MultiPolygon" else [geom["coordinates"]]
        for polygon in polygons:
            for x, y in polygon[0]:
                xs.append(x)
                ys.append(y)
    return min(xs), min(ys), max(xs), max(ys)
