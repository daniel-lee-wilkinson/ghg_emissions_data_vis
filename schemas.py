"""
schemas.py
----------
Pandera schema definitions for every DataFrame that flows through
the pipeline. Validation is applied at the boundary of each loader
and transform, catching bad data as early as possible.

Usage
-----
    # Validate explicitly
    from schemas import EmissionsSchema
    df = EmissionsSchema.validate(df)

    # Or decorate a function so it validates input/output automatically
    @pa.check_output(EmissionsSchema)
    def load_emissions(path): ...

Schema hierarchy
----------------
    RawEmissionsSchema      — as loaded from data.csv (Element still wrapped)
    EmissionsSchema         — after load_emissions() (Element unwrapped, M49 padded)
    EmissionsWithGDPSchema  — after merge_gdp()
    EmissionsIndexSchema    — after add_index_1990()
    FAOStatSchema           — production index CSVs
    SectorShareSchema       — normalised sector proportions
    GDPSchema               — World Bank GDP
"""
from __future__ import annotations

import pandera as pa
from pandera.typing import Series


# ---------------------------------------------------------------------------
# Emissions
# ---------------------------------------------------------------------------

class RawEmissionsSchema(pa.DataFrameModel):
    """data.csv as read off disk — Element still has 'Emissions (X)' wrapper."""
    Area:             Series[str]
    Element:          Series[str] = pa.Field(str_matches=r"^Emissions \((CH4|CO2|N2O)\)$")
    Year:             Series[int] = pa.Field(ge=1900, le=2100)
    Value:            Series[float] = pa.Field(nullable=True)

    class Config:
        coerce = True
        strict = False   # allow extra columns (e.g. Element Code, Year Code)


# schemas.py
class EmissionsSchema(pa.DataFrameModel):
    Area:          Series[str]
    Element:       Series[str]                          # ← remove isin here
    Year:          int = pa.Field(ge=1900, le=2100)
    Value:         Series[float] = pa.Field(nullable=True)
    area_code_str: Series[str] = pa.Field(str_matches=r"^\d{3}$")

    class Config:
        coerce = True
        strict = False


class EmissionsWithGDPSchema(EmissionsSchema):
    ISO3:             Series[str] = pa.Field(str_matches=r"^[A-Z]{3}$")
    GDP_constant_USD: Series[float] = pa.Field(gt=0)

    @pa.dataframe_check
    def valid_element_values(cls, df):
        return df["Element"].isin(["CH4", "CO2", "N2O"]).all()

    class Config:
        coerce = True
        strict = False


class EmissionsIndexSchema(EmissionsWithGDPSchema):
    """After add_index_1990() — adds intensity and index columns."""
    emissions_per_million_usd:  Series[float] = pa.Field(ge=0, nullable=True)
    Emissions_index_1990_100:   Series[float] = pa.Field(ge=0, nullable=True)

    class Config:
        coerce = True
        strict = False


# ---------------------------------------------------------------------------
# Agricultural production
# ---------------------------------------------------------------------------

class FAOStatSchema(pa.DataFrameModel):
    """FAOSTAT production index CSVs after load_faostat()."""
    Area:    Series[str]
    Element: Series[str]
    Year:    Series[int] = pa.Field(ge=1960, le=2030)
    Value:   Series[float] = pa.Field(nullable=True)

    class Config:
        coerce = True
        strict = False


class FAOStatItemsSchema(FAOStatSchema):
    """All-items production index — includes commodity columns."""
    item_code_cpc: Series[str] = pa.Field(nullable=True)
    Item:          Series[str] = pa.Field(nullable=True)

    class Config:
        coerce = True
        strict = False


# ---------------------------------------------------------------------------
# Sector shares
# ---------------------------------------------------------------------------

class SectorShareSchema(pa.DataFrameModel):
    """Output of CountrySource.to_long() — one row per country / sector."""
    Country:    Series[str]
    Year:       Series[int] = pa.Field(ge=2000, le=2030)
    Gas:        Series[str] = pa.Field(isin=["CO2", "GHG"])
    Sector:     Series[str]
    Amount:     Series[float] = pa.Field(ge=0)
    Proportion: Series[float] = pa.Field(ge=0, le=1)

    @pa.dataframe_check
    def proportions_sum_to_one_per_country(cls, df):
        """Each country's proportions must sum to approximately 1.0."""
        sums = df.groupby("Country")["Proportion"].sum()
        return ((sums - 1.0).abs() < 0.02).all()

    class Config:
        coerce = True
        strict = False


# ---------------------------------------------------------------------------
# GDP
# ---------------------------------------------------------------------------

class GDPSchema(pa.DataFrameModel):
    """World Bank GDP data after fetch_world_bank_gdp()."""
    ISO3:             Series[str] = pa.Field(str_matches=r"^[A-Z]{3}$")
    Year:             Series[int] = pa.Field(ge=1960, le=2030)
    GDP_constant_USD: Series[float] = pa.Field(gt=0)

    class Config:
        coerce = True
        strict = False


# ---------------------------------------------------------------------------
# Mart schemas — what should come OUT of the pipeline
# ---------------------------------------------------------------------------

class PercentChangeSchema(pa.DataFrameModel):
    """mart_percent_change — one row per country / gas."""
    Area:           Series[str]
    Element:        Series[str] = pa.Field(isin=["CH4", "CO2", "N2O"])
    value_1990:     Series[float] = pa.Field(gt=0)
    value_latest:   Series[float] = pa.Field(gt=0)
    percent_change: Series[float]
    latest_year:    Series[int] = pa.Field(ge=1991)

    class Config:
        coerce = True
        strict = False


class IndexSlopesSchema(pa.DataFrameModel):
    """mart_index_slopes — one row per country / gas."""
    Area:         Series[str]
    Element:      Series[str] = pa.Field(isin=["CH4", "CO2", "N2O"])
    Annual_slope: Series[float]

    class Config:
        coerce = True
        strict = False