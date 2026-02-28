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

g = sns.FacetGrid(top_item_per_bin, col="Area", col_order=COUNTRIES,
                  col_wrap=2, sharey=False, height=3.5, aspect=1.3)
g.map_dataframe(sns.lineplot,    x="year_bin", y="avg_value")
g.map_dataframe(sns.scatterplot, x="year_bin", y="avg_value")

for ax, country in zip(g.axes.flatten(), COUNTRIES):
    sub = top_item_per_bin[top_item_per_bin["Area"] == country].sort_values("year_bin")
    for _, row in sub.iterrows():
        ax.annotate(str(row["Item"]), xy=(row["year_bin"], row["avg_value"]),
                    xytext=(3, 3), textcoords="offset points", fontsize=8)
    ax.set_title(country)
    ax.set_xlabel("Year (5-year bins)")
    ax.set_ylabel("Avg value of top item")

g.fig.suptitle("Top agricultural item by 5-year bin", y=1.02)
plt.tight_layout()
save_fig(g.fig, FIG_DIR / "top_item_every_5_years_by_country.png")
