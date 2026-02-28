"""
tests/test_schemas.py
---------------------
Tests for Pandera schema validation (schemas.py).

These tests verify that:
  - Valid data passes without error
  - Invalid data raises SchemaError with a useful message
  - Custom dataframe-level checks work correctly
"""
from __future__ import annotations

import pandas as pd
import pandera as pa
import pytest


# ---------------------------------------------------------------------------
# EmissionsSchema
# ---------------------------------------------------------------------------

class TestEmissionsSchema:

    def _valid_df(self):
        return pd.DataFrame({
            "Area":          ["Italy", "France"],
            "Element":       ["CH4",   "CO2"],
            "Year":          [1990,    2000],
            "Value":         [100.0,   200.0],
            "area_code_str": ["380",   "250"],
        })

    def test_valid_data_passes(self):
        from schemas import EmissionsSchema
        df = self._valid_df()
        result = EmissionsSchema.validate(df)
        assert len(result) == 2

    def test_invalid_element_raises(self):
        from schemas import EmissionsSchema
        df = self._valid_df()
        df.loc[0, "Element"] = "Emissions (CH4)"  # unwrapped form
        with pytest.raises(pa.errors.SchemaError):
            EmissionsSchema.validate(df)

    def test_invalid_area_code_format_raises(self):
        from schemas import EmissionsSchema
        df = self._valid_df()
        df.loc[0, "area_code_str"] = "4"  # not zero-padded
        with pytest.raises(pa.errors.SchemaError):
            EmissionsSchema.validate(df)

    def test_future_year_raises(self):
        from schemas import EmissionsSchema
        df = self._valid_df()
        df.loc[0, "Year"] = 2200
        with pytest.raises(pa.errors.SchemaError):
            EmissionsSchema.validate(df)

    def test_null_value_is_allowed(self):
        from schemas import EmissionsSchema
        df = self._valid_df()
        df.loc[0, "Value"] = None
        result = EmissionsSchema.validate(df)
        assert pd.isna(result.loc[0, "Value"])

    def test_extra_columns_allowed(self):
        from schemas import EmissionsSchema
        df = self._valid_df()
        df["extra"] = "ignore_me"
        result = EmissionsSchema.validate(df)
        assert "extra" in result.columns  # strict=False preserves extras


# ---------------------------------------------------------------------------
# EmissionsWithGDPSchema
# ---------------------------------------------------------------------------

class TestEmissionsWithGDPSchema:

    def _valid_df(self):
        return pd.DataFrame({
            "Area":             ["Italy"],
            "Element":          ["CH4"],
            "Year":             [1990],
            "Value":            [100.0],
            "area_code_str":    ["380"],
            "ISO3":             ["ITA"],
            "GDP_constant_USD": [1_000_000_000.0],
        })

    def test_valid_data_passes(self):
        from schemas import EmissionsWithGDPSchema
        df = self._valid_df()
        result = EmissionsWithGDPSchema.validate(df)
        assert len(result) == 1

    def test_invalid_iso3_format_raises(self):
        from schemas import EmissionsWithGDPSchema
        df = self._valid_df()
        df.loc[0, "ISO3"] = "it"  # lowercase, wrong length
        with pytest.raises(pa.errors.SchemaError):
            EmissionsWithGDPSchema.validate(df)

    def test_negative_gdp_raises(self):
        from schemas import EmissionsWithGDPSchema
        df = self._valid_df()
        df.loc[0, "GDP_constant_USD"] = -500.0
        with pytest.raises(pa.errors.SchemaError):
            EmissionsWithGDPSchema.validate(df)

    def test_zero_gdp_raises(self):
        from schemas import EmissionsWithGDPSchema
        df = self._valid_df()
        df.loc[0, "GDP_constant_USD"] = 0.0
        with pytest.raises(pa.errors.SchemaError):
            EmissionsWithGDPSchema.validate(df)


# ---------------------------------------------------------------------------
# FAOStatSchema
# ---------------------------------------------------------------------------

class TestFAOStatSchema:

    def test_valid_data_passes(self):
        from schemas import FAOStatSchema
        df = pd.DataFrame({
            "Area":    ["Italy", "France"],
            "Element": ["GPI",   "GPI"],
            "Year":    [1990,    2017],
            "Value":   [103.58,  101.77],
        })
        result = FAOStatSchema.validate(df)
        assert len(result) == 2

    def test_null_values_allowed(self):
        from schemas import FAOStatSchema
        df = pd.DataFrame({
            "Area": ["Italy"], "Element": ["GPI"],
            "Year": [1990], "Value": [None],
        })
        result = FAOStatSchema.validate(df)
        assert pd.isna(result["Value"].iloc[0])


# ---------------------------------------------------------------------------
# SectorShareSchema — including custom dataframe check
# ---------------------------------------------------------------------------

class TestSectorShareSchema:

    def _valid_df(self):
        return pd.DataFrame({
            "Country":    ["Spain",      "Spain",     "France",     "France"],
            "Year":       [2023,         2023,        2023,         2023],
            "Gas":        ["GHG",        "GHG",       "GHG",        "GHG"],
            "Sector":     ["Transport",  "Industry",  "Transport",  "Industry"],
            "Amount":     [0.6,          0.4,         0.5,          0.5],
            "Proportion": [0.6,          0.4,         0.5,          0.5],
        })

    def test_valid_data_passes(self):
        from schemas import SectorShareSchema
        df = self._valid_df()
        result = SectorShareSchema.validate(df)
        assert len(result) == 4

    def test_invalid_gas_raises(self):
        from schemas import SectorShareSchema
        df = self._valid_df()
        df.loc[0, "Gas"] = "N2O"  # not in allowed values for sector shares
        with pytest.raises(pa.errors.SchemaError):
            SectorShareSchema.validate(df)

    def test_negative_proportion_raises(self):
        from schemas import SectorShareSchema
        df = self._valid_df()
        df.loc[0, "Proportion"] = -0.1
        with pytest.raises(pa.errors.SchemaError):
            SectorShareSchema.validate(df)

    def test_proportion_above_one_raises(self):
        from schemas import SectorShareSchema
        df = self._valid_df()
        df.loc[0, "Proportion"] = 1.5
        with pytest.raises(pa.errors.SchemaError):
            SectorShareSchema.validate(df)

    def test_proportions_not_summing_to_one_raises(self):
        from schemas import SectorShareSchema
        df = self._valid_df()
        # Make Spain's proportions sum to 0.5 instead of 1.0
        df.loc[df["Country"] == "Spain", "Proportion"] = 0.25
        with pytest.raises(pa.errors.SchemaError):
            SectorShareSchema.validate(df)

    def test_negative_amount_raises(self):
        from schemas import SectorShareSchema
        df = self._valid_df()
        df.loc[0, "Amount"] = -10.0
        with pytest.raises(pa.errors.SchemaError):
            SectorShareSchema.validate(df)


# ---------------------------------------------------------------------------
# GDPSchema
# ---------------------------------------------------------------------------

class TestGDPSchema:

    def test_valid_data_passes(self):
        from schemas import GDPSchema
        df = pd.DataFrame({
            "ISO3":             ["ITA", "FRA"],
            "Year":             [1990,  2000],
            "GDP_constant_USD": [1e9,   2e9],
        })
        result = GDPSchema.validate(df)
        assert len(result) == 2

    def test_lowercase_iso3_raises(self):
        from schemas import GDPSchema
        df = pd.DataFrame({
            "ISO3": ["ita"], "Year": [1990], "GDP_constant_USD": [1e9]
        })
        with pytest.raises(pa.errors.SchemaError):
            GDPSchema.validate(df)


# ---------------------------------------------------------------------------
# PercentChangeSchema
# ---------------------------------------------------------------------------

class TestPercentChangeSchema:

    def test_valid_data_passes(self):
        from schemas import PercentChangeSchema
        df = pd.DataFrame({
            "Area":           ["Italy",  "Spain"],
            "Element":        ["CH4",    "CO2"],
            "value_1990":     [100.0,    200.0],
            "value_latest":   [80.0,     300.0],
            "percent_change": [-20.0,    50.0],
            "latest_year":    [2021,     2021],
        })
        result = PercentChangeSchema.validate(df)
        assert len(result) == 2

    def test_unknown_gas_raises(self):
        from schemas import PercentChangeSchema
        df = pd.DataFrame({
            "Area": ["Italy"], "Element": ["SF6"],
            "value_1990": [100.0], "value_latest": [80.0],
            "percent_change": [-20.0], "latest_year": [2021],
        })
        with pytest.raises(pa.errors.SchemaError):
            PercentChangeSchema.validate(df)


# ---------------------------------------------------------------------------
# lazy=True — collect ALL failures before raising
# ---------------------------------------------------------------------------

class TestLazyValidation:

    def test_lazy_mode_collects_all_failures(self):
        """
        lazy=True defers raising until all checks are run,
        returning a SchemaErrors with a failure_cases DataFrame.
        Useful for reporting all data quality issues at once.
        """
        from schemas import EmissionsSchema
        df = pd.DataFrame({
            "Area":          ["Italy",          "France"],
            "Element":       ["Emissions (CH4)", "INVALID"],  # both bad
            "Year":          [1990,              2200],        # 2200 also bad
            "Value":         [100.0,             200.0],
            "area_code_str": ["380",             "4"],         # "4" bad
        })
        with pytest.raises(pa.errors.SchemaErrors) as exc_info:
            EmissionsSchema.validate(df, lazy=True)

        failure_cases = exc_info.value.failure_cases
        assert len(failure_cases) > 0
        assert "failure_case" in failure_cases.columns