"""
clean_dat.py
------------
GHG emissions analysis for selected European countries.

Writes to database
------------------
    stg_gdp                — World Bank GDP
    mart_emissions_index   — emissions with intensity and 1990 index
    mart_percent_change    — % change 1990 → latest
    mart_index_slopes      — OLS slope per country / gas
"""
from __future__ import annotations

import logging
import matplotlib
matplotlib.use("Agg")

import numpy as np
import pandas as pd
import seaborn as sns
from schemas import EmissionsWithGDPSchema, EmissionsIndexSchema, PercentChangeSchema, IndexSlopesSchema

from config import (
    COUNTRIES, EMISSIONS_PATH, FIG_DIR,
    GDP_DATE_RANGE, GDP_INDICATOR,
)
from db import Database
from loaders import fetch_world_bank_gdp, load_emissions, load_m49_lookup
from plot_utils import annotate_line_ends, save_fig

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger(__name__)

UNSD_M49_URL = "https://unstats.un.org/unsd/methodology/m49/overview/"
METRIC_EMISSIONS = "Emissions (kt)"
METRIC_INTENSITY = "Emissions Intensity (kt / M USD GDP)"


# ---------------------------------------------------------------------------
# Transforms
# ---------------------------------------------------------------------------

def add_iso3(emissions: pd.DataFrame, m49_lookup: pd.DataFrame) -> pd.DataFrame:
    out = emissions.merge(
        m49_lookup[["m49_code_str", "ISO3"]],
        left_on="area_code_str", right_on="m49_code_str", how="left",
    ).drop(columns=["m49_code_str"])
    missing = out["ISO3"].isna().sum()
    if missing:
        log.warning("%d rows could not be matched to an ISO3 code.", missing)
    return out

@pa.check_output(EmissionsWithGDPSchema)
def merge_gdp(emissions: pd.DataFrame, gdp: pd.DataFrame) -> pd.DataFrame:
    out = emissions.merge(
        gdp[["ISO3", "Year", "GDP_constant_USD"]], on=["ISO3", "Year"], how="left"
    )
    n_dropped = out["GDP_constant_USD"].isna().sum()
    if n_dropped:
        log.warning("Dropping %d rows with no GDP data.", n_dropped)
    return out.dropna(subset=["GDP_constant_USD"]).copy()

@pa.check_output(EmissionsIndexSchema)
def add_intensity(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["emissions_per_million_usd"] = out["Value"] / (out["GDP_constant_USD"] / 1_000_000)
    return out


def add_index_1990(
    df: pd.DataFrame, value_col: str, group_cols: list[str], out_col: str
) -> pd.DataFrame:
    base_col = f"_base_{value_col}"
    base = (
        df[df["Year"] == 1990]
        .groupby(group_cols, as_index=False)[value_col]
        .mean()
        .rename(columns={value_col: base_col})
    )
    out = df.merge(base, on=group_cols, how="left")
    out[out_col] = out[value_col] / out[base_col] * 100
    return out.drop(columns=[base_col])


@pa.check_output(PercentChangeSchema)
def compute_percent_change(df: pd.DataFrame) -> pd.DataFrame:
    latest = int(df["Year"].max())
    wide = (
        df[df["Year"].isin([1990, latest])]
        .groupby(["Area", "Element", "Year"])["Value"]
        .mean()
        .unstack()
    )
    wide["percent_change"] = (wide[latest] - wide[1990]) / wide[1990] * 100
    wide["latest_year"] = latest
    return wide.reset_index().rename(columns={1990: "value_1990", latest: "value_latest"})


@pa.check_output(IndexSlopesSchema)
def compute_index_slopes(df: pd.DataFrame, index_col: str) -> pd.DataFrame:
    rows = []
    for (area, element), g in df.dropna(subset=[index_col]).groupby(["Area", "Element"]):
        slope, _ = np.polyfit(g["Year"].to_numpy(), g[index_col].to_numpy(), 1)
        rows.append({"Area": area, "Element": element, "Annual_slope": slope})
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Plotting
# ---------------------------------------------------------------------------

def _make_palette(countries: list[str]) -> dict:
    return dict(zip(countries, sns.color_palette("colorblind", n_colors=len(countries))))


def plot_emissions_and_intensity(df, countries, out_path=None):
    palette = _make_palette(countries)
    plot_df = pd.concat([
        df[["Area", "Element", "Year", "Value"]]
            .rename(columns={"Value": "Y"}).assign(Metric=METRIC_EMISSIONS),
        df[["Area", "Element", "Year", "emissions_per_million_usd"]]
            .rename(columns={"emissions_per_million_usd": "Y"}).assign(Metric=METRIC_INTENSITY),
    ], ignore_index=True).dropna(subset=["Year", "Y"])

    with sns.axes_style("ticks"):
        f = sns.relplot(
            data=plot_df, x="Year", y="Y",
            hue="Area", hue_order=countries, palette=palette,
            row="Element", col="Metric",
            col_order=[METRIC_EMISSIONS, METRIC_INTENSITY],
            kind="line", height=3.5, aspect=1.4, linewidth=1.0,
            legend=False, facet_kws={"sharex": True, "sharey": False},
        )

    for j, col_val in enumerate(f.col_names):
        f.axes[0, j].set_title(col_val)
    for i in range(1, len(f.row_names)):
        for j in range(len(f.col_names)):
            f.axes[i, j].set_title("")
    for i, row_val in enumerate(f.row_names):
        f.axes[i, 0].annotate(row_val, xy=(0, 0.5), xycoords="axes fraction",
            xytext=(-0.22, 0.5), textcoords="axes fraction",
            ha="right", va="center", fontsize=9, annotation_clip=False)

    f.set_axis_labels("Year", "")
    f.fig.subplots_adjust(wspace=0.4)
    f.axes.flat[0].set_xlim(1990, int(plot_df["Year"].max()))
    for ax in f.axes.flat:
        sns.despine(ax=ax, offset=8)
        annotate_line_ends(ax, countries, palette)

    if out_path is not None:
        save_fig(f.fig, out_path)
    return f


def plot_emissions_index(df, countries, index_col, out_path=None):
    palette = _make_palette(countries)
    with sns.axes_style("ticks"):
        g = sns.relplot(
            data=df.dropna(subset=[index_col]), x="Year", y=index_col,
            hue="Area", hue_order=countries, palette=palette,
            row="Element", kind="line", height=3.5, aspect=1.6,
            linewidth=1.0, legend=False,
            facet_kws={"sharex": True, "sharey": True},
        )

    g.axes[0, 0].set_title("Emissions Index (1990 = 100)")
    for i in range(1, len(g.row_names)):
        g.axes[i, 0].set_title("")
    for i, row_val in enumerate(g.row_names):
        g.axes[i, 0].annotate(row_val, xy=(0, 0.5), xycoords="axes fraction",
            xytext=(-0.22, 0.5), textcoords="axes fraction",
            ha="right", va="center", fontsize=9, annotation_clip=False)

    g.axes.flat[0].set_xlim(1990, int(df.loc[df[index_col].notna(), "Year"].max()))
    g.set_axis_labels("Year", "")
    for ax in g.axes.flat:
        sns.despine(ax=ax, offset=8)
        annotate_line_ends(ax, countries, palette)
        ax.axhline(100, linestyle="--", color="#999999", linewidth=0.7, alpha=0.4, zorder=0)
        ax.set_ylabel("")

    if out_path is not None:
        save_fig(g.fig, out_path)
    return g


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

# 1. Load
emissions   = load_emissions(EMISSIONS_PATH)
m49_lookup  = load_m49_lookup(UNSD_M49_URL)
emissions   = add_iso3(emissions, m49_lookup)
emissions_eu = emissions[emissions["Area"].isin(COUNTRIES)].copy()

# 2. GDP
gdp          = fetch_world_bank_gdp(GDP_INDICATOR, GDP_DATE_RANGE)
emissions_eu = merge_gdp(emissions_eu, gdp)
emissions_eu = add_intensity(emissions_eu)

# 3. Index
emissions_eu = (
    emissions_eu.dropna(subset=["Year", "Value"])
    .assign(Year=lambda d: d["Year"].astype(int))
)
emissions_eu = add_index_1990(
    emissions_eu, value_col="Value",
    group_cols=["Area", "Element"],
    out_col="Emissions_index_1990_100",
)

# 4. Analytics
pct_change = compute_percent_change(emissions_eu)
slopes     = compute_index_slopes(emissions_eu, "Emissions_index_1990_100")

log.info("\nPercent change 1990 → latest:\n%s",
         pct_change.sort_values(["Element", "Area"]).to_string(index=False))
log.info("\nAnnual index slopes:\n%s",
         slopes.sort_values(["Element", "Area"]).to_string(index=False))

# 5. Write to database
with Database() as db:
    db.write("stg_gdp", gdp)
    db.write("mart_emissions_index", emissions_eu[[
        "Area", "Element", "Year", "Value",
        "GDP_constant_USD", "emissions_per_million_usd",
        "Emissions_index_1990_100",
    ]])
    db.write("mart_percent_change", pct_change)
    db.write("mart_index_slopes",   slopes)

# 6. Figures
plot_emissions_and_intensity(
    emissions_eu, COUNTRIES,
    out_path=FIG_DIR / "fig1_emissions_intensity.png",
)
plot_emissions_index(
    emissions_eu, COUNTRIES, "Emissions_index_1990_100",
    out_path=FIG_DIR / "fig2_emissions_index.png",
)
