"""
sectors.py
----------
Sector-level GHG/CO₂ emissions breakdown for selected European countries.

Writes to database
------------------
    stg_sector_shares — normalised sector proportions for all countries
"""
from __future__ import annotations

import logging
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns
from dataclasses import dataclass
from enum import Enum
from typing import Callable

from config import COUNTRIES, FIG_DIR, ITALY_SECTORS_PATH, UBA_SECTORS_PATH
from db import Database
from plot_utils import save_fig

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger(__name__)

YEAR = 2023

SECTOR_ORDER = [
    "Transport", "Industry", "Agriculture", "Energy",
    "Residential and Commercial", "Waste", "LULUCF",
    "Manufacturing", "Fugitive Emissions", "Aviation and Shipping",
    "Other Fuel Combustion",
]


class Gas(str, Enum):
    CO2 = "CO2"
    GHG = "GHG"


@dataclass
class CountrySource:
    country: str
    gas: Gas
    source_note: str
    load: Callable[[], dict[str, float]]

    def to_long(self, year: int) -> pd.DataFrame:
        data = self.load()
        total = sum(data.values())
        if total <= 0:
            raise ValueError(f"{self.country}: sector values sum to zero or negative.")
        df = pd.DataFrame({
            "Country":    self.country,
            "Year":       year,
            "Gas":        self.gas.value,
            "Sector":     list(data.keys()),
            "Amount":     list(data.values()),
            "source_note": self.source_note,
        })
        df["Proportion"] = df["Amount"] / total
        prop_sum = df["Proportion"].sum()
        if abs(prop_sum - 1.0) > 0.02:
            raise ValueError(f"{self.country}: proportions sum to {prop_sum:.4f}, expected ~1.0")
        return df


def proportions_from_total(d: dict, total_key: str) -> dict:
    total = d[total_key]
    return {k: v / total for k, v in d.items() if k != total_key}


# ---------------------------------------------------------------------------
# Country loaders
# ---------------------------------------------------------------------------

def _load_spain() -> dict[str, float]:
    return {
        "Transport":                  0.325,
        "Industry":                   0.186,
        "Agriculture":                0.122,
        "Energy":                     0.114,
        "Residential and Commercial": 0.085,
        "Waste":                      0.051,
    }


def _load_france() -> dict[str, float]:
    return {
        "Transport":                  0.34,
        "Industry":                   0.17,
        "Residential and Commercial": 0.15,
        "Agriculture":                0.21,
        "Energy":                     0.09,
        "Waste":                      0.04,
    }


def _load_germany() -> dict[str, float]:
    DE_SECTORS = ["1_ENERGY", "2_INDUSTRY", "3_AGRICULTURE", "4_LULUCF", "5_WASTE"]
    DE_RENAME  = {"1_ENERGY": "Energy", "2_INDUSTRY": "Industry",
                  "3_AGRICULTURE": "Agriculture", "4_LULUCF": "LULUCF", "5_WASTE": "Waste"}
    df = pd.read_csv(UBA_SECTORS_PATH,
                     usecols=["Substances", "D_SOURCE_CATEGORIES", "TIME_PERIOD", "OBS_VALUE"])
    df["D_SOURCE_CATEGORIES"] = df["D_SOURCE_CATEGORIES"].str.strip()
    df["Substances"]          = df["Substances"].str.strip()
    df = df[
        (df["D_SOURCE_CATEGORIES"].isin(DE_SECTORS)) &
        (df["TIME_PERIOD"] == YEAR) &
        (df["Substances"] == "Carbon dioxide")
    ]
    if df.empty:
        raise ValueError(f"No German CO₂ data found for year {YEAR}.")
    return (
        df.set_index("D_SOURCE_CATEGORIES")["OBS_VALUE"]
        .apply(pd.to_numeric, errors="coerce").dropna()
        .rename(DE_RENAME).to_dict()
    )


def _load_italy() -> dict[str, float]:
    IT_SECTOR_COLS = [
        "Buildings", "Industry", "Land-use change and forestry",
        "Other fuel combustion", "Transport", "Manufacturing and construction",
        "Fugitive emissions", "Electricity and heat", "Aviation and shipping",
    ]
    IT_RENAME = {
        "Buildings":                      "Residential and Commercial",
        "Land-use change and forestry":   "LULUCF",
        "Other fuel combustion":          "Other Fuel Combustion",
        "Manufacturing and construction": "Manufacturing",
        "Fugitive emissions":             "Fugitive Emissions",
        "Electricity and heat":           "Energy",
        "Aviation and shipping":          "Aviation and Shipping",
    }
    df = pd.read_csv(ITALY_SECTORS_PATH)
    row = df[df["Year"] == YEAR]
    if row.empty:
        raise ValueError(f"No Italy data found for year {YEAR}.")
    long = (
        row.melt(id_vars=["Year"], value_vars=IT_SECTOR_COLS,
                 var_name="Sector", value_name="Amount")
        .assign(Amount=lambda d: pd.to_numeric(d["Amount"], errors="coerce"))
        .dropna(subset=["Amount"])
    )
    long["Sector"] = long["Sector"].replace(IT_RENAME)
    return long.set_index("Sector")["Amount"].to_dict()


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

COUNTRY_SOURCES: list[CountrySource] = [
    CountrySource("Spain",   Gas.GHG, "Statista 2023", _load_spain),
    CountrySource("France",  Gas.GHG, "CITEPA 2024",   _load_france),
    CountrySource("Germany", Gas.CO2, "UBA 2023",      _load_germany),
    CountrySource("Italy",   Gas.CO2, "OWiD 2023",     _load_italy),
]

registry_countries = {s.country for s in COUNTRY_SOURCES}
for c in COUNTRIES:
    if c not in registry_countries:
        log.warning("'%s' is in COUNTRIES but has no CountrySource entry.", c)

# ---------------------------------------------------------------------------
# Combine, validate, write
# ---------------------------------------------------------------------------

frames = []
for source in COUNTRY_SOURCES:
    df = source.to_long(YEAR)
    frames.append(df)
    log.info("Loaded %s: %d sectors, proportions sum = %.4f",
             source.country, len(df), df["Proportion"].sum())

df_combined = pd.concat(frames, ignore_index=True)

# Warn on missing canonical sectors
for source in COUNTRY_SOURCES:
    present = set(df_combined.loc[df_combined["Country"] == source.country, "Sector"])
    absent  = set(SECTOR_ORDER) - present
    if absent:
        log.warning("%s: missing sectors (NaN in heatmap): %s",
                    source.country, sorted(absent))

# Write to database
with Database() as db:
    db.write("stg_sector_shares", df_combined)

# ---------------------------------------------------------------------------
# Heatmap
# ---------------------------------------------------------------------------

df_plot = df_combined[
    df_combined["Sector"].isin(SECTOR_ORDER) & df_combined["Proportion"].notna()
].copy()
df_plot["Sector"] = pd.Categorical(df_plot["Sector"], categories=SECTOR_ORDER, ordered=True)

df_heat = (
    df_plot.pivot_table(index="Sector", columns="Country",
                        values="Proportion", aggfunc="sum")
    .reindex(SECTOR_ORDER)
)

gas_notes = " | ".join(
    f"{s.country} ({s.source_note}, {s.gas.value})" for s in COUNTRY_SOURCES
)

fig, ax = plt.subplots(figsize=(8, 6))
sns.heatmap(df_heat, annot=True, fmt=".1%", cbar=True,
            cmap="Blues", linewidths=0.5, ax=ax)
ax.set_title(
    f"GHG / CO₂ sector shares ({YEAR})\n"
    "Note: Germany and Italy are CO₂-only; Spain and France are full GHG.",
    fontsize=10, pad=12,
)
fig.text(0.5, -0.02, f"Data: {gas_notes}", ha="center", fontsize=7, color="#555555")
plt.tight_layout()
save_fig(fig, FIG_DIR / "ghg_emissions_by_sector_heatmap.png")
