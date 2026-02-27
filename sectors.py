import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path

# -----------------------------
# Config
# -----------------------------
YEAR = 2023
FIG_DIR = Path("Figures")
FIG_DIR.mkdir(parents=True, exist_ok=True)

SECTOR_ORDER = [
    "Transport",
    "Industry",
    "Agriculture",
    "Energy",
    "Residential and Commercial",
    "Waste",
    "LULUCF",
    "Manufacturing",
    "Fugitive Emissions",
    "Aviation and Shipping",
    "Other Fuel Combustion",
]

# -----------------------------
# Helpers
# -----------------------------
def sector_dict_to_long(d: dict, country: str, year: int) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Country": country,
            "Year": year,
            "Sector": [str(k).strip() for k in d.keys()],
            "Proportion": list(d.values()),
        }
    )


def proportions_from_total(d: dict, total_key: str) -> dict:
    total = d[total_key]
    return {k: v / total for k, v in d.items() if k != total_key}


# -----------------------------
# Spain (Statista, 2023) - proportions already
# -----------------------------
spain_sectors = {
    "Transport": 0.325,
    "Industry": 0.186,
    "Agriculture": 0.122,
    "Energy": 0.114,
    "Residential and Commercial": 0.085,
    "Waste": 0.051,
    "Other": 0.118,
}

# -----------------------------
# Germany (UBA, 2023) -> proportions (CO2 only)
# -----------------------------
de_data = pd.read_csv("UBA_sectors.csv", sep=",")

DE_COLS = ["Substances", "D_SOURCE_CATEGORIES", "TIME_PERIOD", "OBS_VALUE"]
DE_SECTORS = ["1_ENERGY", "2_INDUSTRY", "3_AGRICULTURE", "4_LULUCF", "5_WASTE", "TOTAL"]
DE_SUBSTANCE = "Carbon dioxide"

de_data = de_data[DE_COLS]
de_data["D_SOURCE_CATEGORIES"] = de_data["D_SOURCE_CATEGORIES"].astype(str).str.strip()
de_data["Substances"] = de_data["Substances"].astype(str).str.strip()

de_data = de_data[de_data["D_SOURCE_CATEGORIES"].isin(DE_SECTORS)]
de_data = de_data[de_data["TIME_PERIOD"] == YEAR]
de_data = de_data[de_data["Substances"] == DE_SUBSTANCE]

germany_abs = (
    de_data.set_index("D_SOURCE_CATEGORIES")["OBS_VALUE"]
    .apply(pd.to_numeric, errors="coerce")
    .to_dict()
)

germany_props = proportions_from_total(germany_abs, total_key="TOTAL")

DE_RENAME = {
    "1_ENERGY": "Energy",
    "2_INDUSTRY": "Industry",
    "3_AGRICULTURE": "Agriculture",
    "4_LULUCF": "LULUCF",
    "5_WASTE": "Waste",
}
germany_sectors = {DE_RENAME[k]: v for k, v in germany_props.items() if k in DE_RENAME}

# -----------------------------
# France (you stated 2024, but we align to YEAR for plotting)
# -----------------------------
france_sectors = {
    "Transport": 0.34,
    "Industry": 0.17,
    "Residential and Commercial": 0.15,
    "Agriculture": 0.21,
    "Energy": 0.09,
    "Waste": 0.04,
}

# -----------------------------
# Italy (CSV, 2023) -> proportions
# -----------------------------
italy_wide = pd.read_csv("italy_co-emissions-by-sector.csv")
italy_wide = italy_wide[italy_wide["Year"] == YEAR].copy()

IT_SECTOR_COLS = [
    "Buildings",
    "Industry",
    "Land-use change and forestry",
    "Other fuel combustion",
    "Transport",
    "Manufacturing and construction",
    "Fugitive emissions",
    "Electricity and heat",
    "Aviation and shipping",
]

IT_RENAME = {
    "Buildings": "Residential and Commercial",  # adjust if your intended schema differs
    "Industry": "Industry",
    "Land-use change and forestry": "LULUCF",
    "Other fuel combustion": "Other Fuel Combustion",
    "Transport": "Transport",
    "Manufacturing and construction": "Manufacturing",
    "Fugitive emissions": "Fugitive Emissions",
    "Electricity and heat": "Energy",
    "Aviation and shipping": "Aviation and Shipping",
}

italy_long = italy_wide.melt(
    id_vars=["Year"],
    value_vars=IT_SECTOR_COLS,
    var_name="Sector",
    value_name="Amount",
)

italy_long["Sector"] = italy_long["Sector"].astype(str).str.strip()
italy_long["Amount"] = pd.to_numeric(italy_long["Amount"], errors="coerce")
italy_long = italy_long.dropna(subset=["Amount"])

italy_total = italy_long.groupby("Year")["Amount"].transform("sum")
italy_long["Proportion"] = italy_long["Amount"] / italy_total
italy_long["Sector"] = italy_long["Sector"].replace(IT_RENAME)

italy_sectors = (
    italy_long.groupby("Sector", as_index=False)["Proportion"].sum()
    .set_index("Sector")["Proportion"]
    .to_dict()
)

# -----------------------------
# Combine to one long dataframe
# -----------------------------
df_plot = pd.concat(
    [
        sector_dict_to_long(spain_sectors, "Spain", YEAR),
        sector_dict_to_long(germany_sectors, "Germany", YEAR),
        sector_dict_to_long(france_sectors, "France", YEAR),
        sector_dict_to_long(italy_sectors, "Italy", YEAR),
    ],
    ignore_index=True,
)

# Clean + filter
df_plot["Sector"] = df_plot["Sector"].astype(str).str.strip()
df_plot = df_plot[(df_plot["Sector"] != "Other") & (df_plot["Proportion"].notna())]
df_plot = df_plot[df_plot["Proportion"] > 0]

df_plot["Sector"] = pd.Categorical(df_plot["Sector"], categories=SECTOR_ORDER, ordered=True)

# -----------------------------
# Heatmap
# -----------------------------
df_heat = (
    df_plot.pivot_table(index="Sector", columns="Country", values="Proportion", aggfunc="sum")
    .reindex(SECTOR_ORDER)
)

plt.figure(figsize=(8, 6))
sns.heatmap(df_heat, annot=True, fmt=".1%", cbar=True, cmap="Blues", linewidths=0.5)
plt.title(f"GHG sector shares ({YEAR})")
plt.suptitle("Data sources: Spain (Statista, 2023), Germany (UBA, 2023), France (2024), Italy (Our World in Data, 2023)", fontsize=8)
plt.tight_layout()
plt.savefig(FIG_DIR / "ghg_emissions_by_sector_heatmap.png", bbox_inches="tight")
plt.close()