"""
config.py — single source of truth for shared constants across all scripts.
"""
from pathlib import Path

# Countries included in all analyses. Add new countries here only.
COUNTRIES: list[str] = ["Italy", "Spain", "France", "Germany"]

# Output directory for all figures
FIG_DIR: Path = Path("Figures")
FIG_DIR.mkdir(parents=True, exist_ok=True)

# FAOSTAT agricultural data
FAOSTAT_WEST_PATH   = "FAOSTAT_data_western_europe.csv"
FAOSTAT_SOUTH_PATH  = "FAOSTAT_southern_europe.csv"
FAOSTAT_FV_PATH     = "FAOSTAT_data_fruit_veg.csv"
FAOSTAT_ALL_AG_PATH = "FAOSTAT_data_all_ag.csv"

# Emissions data
EMISSIONS_PATH = "data.csv"

# Sector-level data
UBA_SECTORS_PATH   = "UBA_sectors.csv"
ITALY_SECTORS_PATH = "italy_co-emissions-by-sector.csv"

# World Bank GDP
GDP_INDICATOR  = "NY.GDP.MKTP.KD"   # constant 2015 USD
GDP_DATE_RANGE = "1990:2024"
