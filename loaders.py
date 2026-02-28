"""
loaders.py — reusable data-loading helpers shared across all scripts.

Each function is pure: it takes a path (or URL/params) and returns a
cleaned DataFrame. No global state, no side effects.
"""
from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('Agg')  # non-interactive backend, no display needed
import pandas as pd
import requests
from schemas import EmissionsSchema, FAOStatSchema
import pandera as pa
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# FAOSTAT helpers
# ---------------------------------------------------------------------------

BASE_FAOSTAT_COLS = ["Area", "Element", "Unit", "Value", "Year"]
EXTRA_AG_COLS     = ["Item Code (CPC)", "Item"]

@pa.check_output(FAOStatSchema)
def load_faostat(
    path: str | Path,
    countries: list[str],
    extra_cols: list[str] | None = None,
) -> pd.DataFrame:
    """
    Load a FAOSTAT CSV, keep only the requested columns and filter to
    `countries`. Whitespace in the Area column is stripped automatically.

    Parameters
    ----------
    path        : path to the CSV file
    countries   : list of country names to retain
    extra_cols  : additional column names beyond the standard five
    """
    cols = BASE_FAOSTAT_COLS + (extra_cols or [])
    df = pd.read_csv(path, usecols=cols)
    df["Area"] = df["Area"].astype(str).str.strip()

    loaded   = set(df["Area"].unique())
    missing  = set(countries) - loaded
    if missing:
        log.warning("Countries not found in %s: %s", path, sorted(missing))

    return df[df["Area"].isin(countries)].reset_index(drop=True)


def load_faostat_multi(
    paths: list[str | Path],
    countries: list[str],
    extra_cols: list[str] | None = None,
) -> pd.DataFrame:
    """
    Load and concatenate multiple FAOSTAT files that share the same schema.
    Deduplicates rows in case a country appears in more than one regional file.
    """
    frames = [load_faostat(p, countries, extra_cols) for p in paths]
    combined = pd.concat(frames, ignore_index=True)
    key_cols = BASE_FAOSTAT_COLS + (extra_cols or [])
    return combined.drop_duplicates(subset=key_cols).reset_index(drop=True)


# ---------------------------------------------------------------------------
# Emissions (data.csv)
# ---------------------------------------------------------------------------
@pa.check_output(EmissionsSchema)
def load_emissions(path: str | Path) -> pd.DataFrame:
    """
    Load the FAOSTAT emissions CSV. Strips 'Emissions (X)' wrappers from
    Element names and creates a zero-padded string M49 code for merging.
    """
    cols = ["Area Code (M49)", "Area", "Element Code", "Element",
            "Year Code", "Year", "Value"]
    df = pd.read_csv(path, usecols=cols)

    df["Year"]  = pd.to_numeric(df["Year"],  errors="coerce")
    df["Value"] = pd.to_numeric(df["Value"], errors="coerce")

    # "Emissions (CH4)" → "CH4"
    df["Element"] = df["Element"].str.replace(
        r"^Emissions \((.+)\)$", r"\1", regex=True
    )
    df["area_code_str"] = (
        pd.to_numeric(df["Area Code (M49)"], errors="coerce")
        .astype("Int64")
        .astype(str)
        .str.zfill(3)
    )
    return df


# ---------------------------------------------------------------------------
# M49 country-code lookup  (cached: static data, no need to re-fetch)
# ---------------------------------------------------------------------------

M49_CACHE_PATH = Path("m49_lookup.csv")

@lru_cache(maxsize=1)
def load_m49_lookup(url: str) -> pd.DataFrame:
    """
    Return a tidy M49 → ISO3 mapping. On first call the UNSD page is scraped
    and the result written to M49_CACHE_PATH. Subsequent calls (same process
    or future runs) read from that file instead of hitting the network.
    """
    if M49_CACHE_PATH.exists():
        log.info("Loading M49 lookup from cache: %s", M49_CACHE_PATH)
        return pd.read_csv(M49_CACHE_PATH, dtype=str)

    log.info("Fetching M49 lookup from %s", url)
    tables = pd.read_html(url)
    m49 = next(t for t in tables if "M49 Code" in t.columns).copy()

    m49["m49_code_str"] = m49["M49 Code"].astype(str).str.zfill(3)
    m49["ISO3"] = m49["ISO-alpha3 Code"].astype(str).str.strip()
    m49 = m49[["m49_code_str", "Region Name", "ISO3"]].drop_duplicates()

    m49["m49_code_str"] = m49["m49_code_str"].astype(str)  # ensure consistent type on reload
    m49.to_csv(M49_CACHE_PATH, index=False)
    log.info("M49 lookup cached to %s", M49_CACHE_PATH)
    return m49

# ---------------------------------------------------------------------------
# World Bank GDP  (cached per indicator + date_range combination)
# ---------------------------------------------------------------------------

@lru_cache(maxsize=None)
def fetch_world_bank_gdp(indicator: str, date_range: str) -> pd.DataFrame:
    """
    Fetch GDP data from the World Bank API for all countries.
    Result is cached per (indicator, date_range) pair so repeated calls
    within a session (e.g. from a notebook) do not hit the network again.
    """
    url = (
        f"https://api.worldbank.org/v2/country/all/indicator/{indicator}"
        f"?date={date_range}&format=json&per_page=20000"
    )
    log.info("Fetching World Bank GDP: %s", url)
    resp = requests.get(url, timeout=30).json()
    if len(resp) < 2:
        raise ValueError(f"Unexpected World Bank API response: {resp}")

    gdp = pd.DataFrame(resp[1])[
        ["countryiso3code", "country", "date", "value"]
    ].copy()
    gdp.columns = ["ISO3", "Country_WB", "Year", "GDP_constant_USD"]

    gdp["ISO3"]             = gdp["ISO3"].astype(str).str.strip()
    gdp["Year"]             = pd.to_numeric(gdp["Year"], errors="coerce")
    gdp["GDP_constant_USD"] = pd.to_numeric(gdp["GDP_constant_USD"], errors="coerce")

    gdp = gdp.dropna(subset=["ISO3", "Year", "GDP_constant_USD"]).copy()
    gdp["Year"] = gdp["Year"].astype(int)
    return gdp
