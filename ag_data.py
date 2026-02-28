"""
ag_data.py
----------
Agricultural Gross Production Index analysis for selected European countries.

Writes to database
------------------
    stg_ag_production  — gross production index
    stg_fv_production  — fruit & vegetable production index
    stg_ag_items       — commodity-level production index
    mart_top_ag_items  — top commodity per country per 5-year bin
"""
from __future__ import annotations

import logging
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

from config import (
    COUNTRIES, FAOSTAT_ALL_AG_PATH, FAOSTAT_FV_PATH,
    FAOSTAT_SOUTH_PATH, FAOSTAT_WEST_PATH, FIG_DIR,
)
from db import Database
from loaders import EXTRA_AG_COLS, load_faostat, load_faostat_multi
from plot_utils import figure, save_fig

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Load data
# ---------------------------------------------------------------------------

ag_data = load_faostat_multi(
    paths=[FAOSTAT_WEST_PATH, FAOSTAT_SOUTH_PATH],
    countries=COUNTRIES,
)
fv_data     = load_faostat(FAOSTAT_FV_PATH, COUNTRIES)
all_ag_data = load_faostat(FAOSTAT_ALL_AG_PATH, COUNTRIES, extra_cols=EXTRA_AG_COLS)

# ---------------------------------------------------------------------------
# Write staging tables
# ---------------------------------------------------------------------------

with Database() as db:
    db.write("stg_ag_production", ag_data)
    db.write("stg_fv_production", fv_data)
    db.write("stg_ag_items", all_ag_data.rename(columns={"Item Code (CPC)": "item_code_cpc"}))

# ---------------------------------------------------------------------------
# Figures 1 & 2
# ---------------------------------------------------------------------------

with figure(figsize=(10, 6)) as (fig, ax):
    sns.lineplot(data=ag_data, x="Year", y="Value",
                 hue="Area", hue_order=COUNTRIES, marker="o", ax=ax)
    ax.set_title("Agricultural Gross Production Index (2014–2016 = 100)")
    ax.set_xlabel("Year")
    ax.set_ylabel("Gross Production Index")
    ax.legend(title="Country")
    save_fig(fig, FIG_DIR / "agricultural_gross_production_index.png")

with figure(figsize=(10, 6)) as (fig, ax):
    sns.lineplot(data=fv_data, x="Year", y="Value",
                 hue="Area", hue_order=COUNTRIES, marker="o", ax=ax)
    ax.set_title("Fruit and Vegetable Production Index (2014–2016 = 100)")
    ax.set_xlabel("Year")
    ax.set_ylabel("Production Index")
    ax.legend(title="Country")
    save_fig(fig, FIG_DIR / "fruit_veg_production_index.png")

# ---------------------------------------------------------------------------
# Figure 3 — top item per 5-year bin
# ---------------------------------------------------------------------------
import matplotlib.patheffects as pe
from matplotlib.gridspec import GridSpec

df = all_ag_data.copy()
df["Year"]  = pd.to_numeric(df["Year"],  errors="coerce")
df["Value"] = pd.to_numeric(df["Value"], errors="coerce")
df = df.dropna(subset=["Year", "Value"])

START_YEAR   = 1990
df["year_bin"] = START_YEAR + ((df["Year"] - START_YEAR) // 5) * 5

bin_item_avg = (
    df.groupby(["Area", "year_bin", "Item Code (CPC)", "Item"], as_index=False)
    .agg(avg_value=("Value", "mean"))
)

top_item_per_bin = (
    bin_item_avg
    .sort_values(["Area", "year_bin", "avg_value"], ascending=[True, True, False])
    .drop_duplicates(subset=["Area", "year_bin"])
    .reset_index(drop=True)
)

with Database() as db:
    db.write("mart_top_ag_items",
             top_item_per_bin[["Area", "year_bin", "Item", "avg_value"]])

# Only plot countries that actually have data
plot_countries = [c for c in COUNTRIES
                  if c in top_item_per_bin["Area"].values]

BLUE       = "#1B4F8A"
BLUE_LIGHT = "#D0DEF0"
GREY_TEXT  = "#444444"
STROKE     = [pe.withStroke(linewidth=3, foreground="white")]

fig = plt.figure(figsize=(16, 8))
fig.patch.set_facecolor("white")

gs = GridSpec(2, len(plot_countries), figure=fig,
              height_ratios=[3, 1.2],
              hspace=0.08, wspace=0.35,
              top=0.88, bottom=0.04,
              left=0.06, right=0.98)

for col, country in enumerate(plot_countries):
    sub = (top_item_per_bin[top_item_per_bin["Area"] == country]
           .sort_values("year_bin").reset_index(drop=True))
    n = len(sub)

    # ── Chart ──────────────────────────────────────────────────────────
    ax = fig.add_subplot(gs[0, col])
    ax.plot(sub["year_bin"], sub["avg_value"], color=BLUE, lw=2.2, zorder=2)
    ax.scatter(sub["year_bin"], sub["avg_value"], color=BLUE, s=60, zorder=3)
    ax.fill_between(sub["year_bin"], sub["avg_value"], alpha=0.08, color=BLUE)

    # Label first and last point only
    for i, row in sub.iterrows():
        if i not in (0, n - 1):
            continue
        label = row["Item"]
        if len(label) > 22:
            label = label[:20] + "…"
        dy = 14 if i == 0 else -14
        va = "bottom" if i == 0 else "top"
        ax.annotate(label, xy=(row["year_bin"], row["avg_value"]),
                    xytext=(0, dy), textcoords="offset points",
                    fontsize=7.5, va=va, ha="center", color=GREY_TEXT,
                    path_effects=STROKE, annotation_clip=False)

    # Number each dot
    for i, row in sub.iterrows():
        ax.annotate(str(i + 1), xy=(row["year_bin"], row["avg_value"]),
                    xytext=(0, 0), textcoords="offset points",
                    fontsize=6.5, va="center", ha="center",
                    color="white", fontweight="bold", annotation_clip=False)

    ax.set_title(country, fontsize=13, fontweight="bold", color=BLUE, pad=10)
    if col == 0:
        ax.set_ylabel("Avg production index value", fontsize=8.5, color="#555")
    ax.spines[["top", "right"]].set_visible(False)
    ax.spines[["left", "bottom"]].set_color("#CCCCCC")
    ax.tick_params(colors="#555", labelsize=8)
    ax.set_xticks(sub["year_bin"])
    ax.set_xticklabels(sub["year_bin"].astype(int), rotation=40, ha="right")
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f"{x:,.0f}"))
    ymin, ymax = sub["avg_value"].min(), sub["avg_value"].max()
    pad = (ymax - ymin) * 0.3 if ymax != ymin else ymax * 0.3 or 1
    ax.set_ylim(ymin - pad * 0.5, ymax + pad)

    # ── Table ──────────────────────────────────────────────────────────
    tax = fig.add_subplot(gs[1, col])
    tax.axis("off")

    rows_data = []
    for i, row in sub.iterrows():
        item = row["Item"]
        if len(item) > 30:
            item = item[:28] + "…"
        rows_data.append([str(i + 1), str(int(row["year_bin"])), item])

    tbl = tax.table(
        cellText=rows_data,
        colLabels=["#", "Period", "Top commodity"],
        loc="center",
        cellLoc="left",
    )
    tbl.auto_set_font_size(False)
    tbl.set_fontsize(7.5)
    tbl.scale(1, 1.35)

    for j in range(3):
        tbl[0, j].set_facecolor(BLUE)
        tbl[0, j].set_text_props(color="white", fontweight="bold")
        tbl[0, j].set_edgecolor("white")

    for i in range(1, len(rows_data) + 1):
        for j in range(3):
            tbl[i, j].set_facecolor(BLUE_LIGHT if i % 2 == 0 else "white")
            tbl[i, j].set_edgecolor("#e0e0e0")
            tbl[i, j].set_text_props(color=GREY_TEXT)

    tbl.auto_set_column_width([0, 1, 2])

fig.suptitle("Top agricultural commodity per 5-year period",
             fontsize=14, fontweight="bold", color="#111", y=0.96)
fig.savefig(FIG_DIR / "top_item_every_5_years_by_country.png",
            dpi=150, bbox_inches="tight", facecolor="white")
plt.close(fig)