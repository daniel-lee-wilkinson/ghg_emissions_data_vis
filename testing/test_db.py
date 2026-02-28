"""
tests/test_db.py
----------------
Unit tests for the DuckDB database layer (db.py).

All tests use in-memory databases so nothing touches the filesystem.
"""
from __future__ import annotations

import pytest
import pandas as pd

from db import Database, TABLE_SCHEMAS


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def db():
    """Fresh in-memory database for each test."""
    with Database(":memory:") as database:
        yield database


@pytest.fixture
def sample_emissions_df() -> pd.DataFrame:
    return pd.DataFrame({
        "Area":          ["Italy", "France"],
        "area_code_m49": [380,     250],
        "area_code_str": ["380",   "250"],
        "Element":       ["CH4",   "CO2"],
        "Year":          [1990,    1990],
        "Value":         [100.0,   200.0],
    })


@pytest.fixture
def sample_ag_df() -> pd.DataFrame:
    return pd.DataFrame({
        "Area":    ["Italy",  "France"],
        "Element": ["GPI",    "GPI"],
        "Year":    [1990,     1990],
        "Value":   [103.58,   101.77],
    })


@pytest.fixture
def sample_sector_df() -> pd.DataFrame:
    return pd.DataFrame({
        "Country":     ["Spain",      "Spain"],
        "Year":        [2023,         2023],
        "Gas":         ["GHG",        "GHG"],
        "Sector":      ["Transport",  "Industry"],
        "Amount":      [0.325,        0.186],
        "Proportion":  [0.635,        0.365],
        "source_note": ["Statista",   "Statista"],
    })


# ---------------------------------------------------------------------------
# Connection and initialisation
# ---------------------------------------------------------------------------

class TestDatabaseInit:

    def test_opens_without_error(self):
        with Database(":memory:") as db:
            assert db is not None

    def test_all_tables_created_on_init(self, db):
        tables = db.tables()
        for expected in TABLE_SCHEMAS:
            assert expected in tables, f"Missing table: {expected}"

    def test_tables_are_initially_empty(self, db):
        counts = db.row_counts()
        assert (counts["rows"] == 0).all()


# ---------------------------------------------------------------------------
# Write
# ---------------------------------------------------------------------------

class TestWrite:

    def test_write_inserts_rows(self, db, sample_emissions_df):
        db.write("stg_emissions", sample_emissions_df)
        result = db.read("stg_emissions")
        assert len(result) == 2

    def test_write_replace_clears_previous_data(self, db, sample_emissions_df):
        db.write("stg_emissions", sample_emissions_df)
        db.write("stg_emissions", sample_emissions_df.iloc[:1])
        result = db.read("stg_emissions")
        assert len(result) == 1

    def test_write_append_adds_rows(self, db, sample_emissions_df):
        db.write("stg_emissions", sample_emissions_df)
        db.write("stg_emissions", sample_emissions_df, mode="append")
        result = db.read("stg_emissions")
        assert len(result) == 4

    def test_write_raises_on_unknown_table(self, db, sample_emissions_df):
        with pytest.raises(ValueError, match="Unknown table"):
            db.write("nonexistent_table", sample_emissions_df)

    def test_write_raises_on_missing_columns(self, db):
        bad_df = pd.DataFrame({"wrong_col": [1, 2]})
        with pytest.raises(ValueError, match="missing columns"):
            db.write("stg_emissions", bad_df)

    def test_write_ag_production(self, db, sample_ag_df):
        db.write("stg_ag_production", sample_ag_df)
        result = db.read("stg_ag_production")
        assert len(result) == 2
        assert set(result["Area"]) == {"Italy", "France"}

    def test_write_sector_shares(self, db, sample_sector_df):
        db.write("stg_sector_shares", sample_sector_df)
        result = db.read("stg_sector_shares")
        assert len(result) == 2
        assert "Proportion" in result.columns


# ---------------------------------------------------------------------------
# Read
# ---------------------------------------------------------------------------

class TestRead:

    def test_read_returns_dataframe(self, db, sample_emissions_df):
        db.write("stg_emissions", sample_emissions_df)
        result = db.read("stg_emissions")
        assert isinstance(result, pd.DataFrame)

    def test_read_values_match_written(self, db, sample_emissions_df):
        db.write("stg_emissions", sample_emissions_df)
        result = db.read("stg_emissions")
        assert set(result["Area"]) == {"Italy", "France"}
        assert set(result["Element"]) == {"CH4", "CO2"}

    def test_read_empty_table_returns_empty_df(self, db):
        result = db.read("stg_emissions")
        assert isinstance(result, pd.DataFrame)
        assert len(result) == 0


# ---------------------------------------------------------------------------
# Query
# ---------------------------------------------------------------------------

class TestQuery:

    def test_query_filters_rows(self, db, sample_emissions_df):
        db.write("stg_emissions", sample_emissions_df)
        result = db.query("SELECT * FROM stg_emissions WHERE Area = 'Italy'")
        assert len(result) == 1
        assert result["Area"].iloc[0] == "Italy"

    def test_query_aggregation(self, db, sample_emissions_df):
        db.write("stg_emissions", sample_emissions_df)
        result = db.query("SELECT SUM(Value) AS total FROM stg_emissions")
        assert pytest.approx(result["total"].iloc[0]) == 300.0

    def test_query_across_tables(self, db, sample_emissions_df, sample_ag_df):
        db.write("stg_emissions", sample_emissions_df)
        db.write("stg_ag_production", sample_ag_df)
        result = db.query("""
            SELECT e.Area, e.Value AS emissions, a.Value AS ag_index
            FROM stg_emissions e
            JOIN stg_ag_production a
              ON e.Area = a.Area AND e.Year = a.Year
            WHERE e.Element = 'CH4'
        """)
        assert len(result) == 1
        assert result["Area"].iloc[0] == "Italy"


# ---------------------------------------------------------------------------
# Schema validation
# ---------------------------------------------------------------------------

class TestSchemaValidation:

    def test_column_names_case_insensitive_match(self, db):
        """Columns with different casing should be renamed to match schema."""
        df = pd.DataFrame({
            "area":          ["Italy"],
            "area_code_m49": [380],
            "area_code_str": ["380"],
            "element":       ["CH4"],
            "year":          [1990],
            "value":         [100.0],
        })
        db.write("stg_emissions", df)
        result = db.read("stg_emissions")
        assert "Area" in result.columns

    def test_extra_columns_are_silently_dropped(self, db, sample_emissions_df):
        """Extra columns not in the schema should be dropped without error."""
        df = sample_emissions_df.copy()
        df["extra_column"] = "should_be_dropped"
        db.write("stg_emissions", df)
        result = db.read("stg_emissions")
        assert "extra_column" not in result.columns

    def test_integer_year_preserved(self, db, sample_emissions_df):
        db.write("stg_emissions", sample_emissions_df)
        result = db.read("stg_emissions")
        assert pd.api.types.is_integer_dtype(result["Year"])

    def test_float_value_preserved(self, db, sample_emissions_df):
        db.write("stg_emissions", sample_emissions_df)
        result = db.read("stg_emissions")
        assert pd.api.types.is_float_dtype(result["Value"])


# ---------------------------------------------------------------------------
# row_counts and tables
# ---------------------------------------------------------------------------

class TestIntrospection:

    def test_row_counts_returns_all_tables(self, db):
        counts = db.row_counts()
        assert len(counts) == len(TABLE_SCHEMAS)
        assert "table" in counts.columns
        assert "rows" in counts.columns

    def test_row_counts_updates_after_write(self, db, sample_emissions_df):
        db.write("stg_emissions", sample_emissions_df)
        counts = db.row_counts()
        emissions_count = counts.loc[counts["table"] == "stg_emissions", "rows"].iloc[0]
        assert emissions_count == 2

    def test_tables_returns_list_of_strings(self, db):
        tables = db.tables()
        assert isinstance(tables, list)
        assert all(isinstance(t, str) for t in tables)


# ---------------------------------------------------------------------------
# Context manager
# ---------------------------------------------------------------------------

class TestContextManager:

    def test_context_manager_closes_connection(self):
        with Database(":memory:") as db:
            db.write("stg_ag_production", pd.DataFrame({
                "Area": ["Italy"], "Element": ["GPI"],
                "Year": [1990], "Value": [100.0]
            }))
        # After exit, connection should be closed — further queries should fail
        with pytest.raises(Exception):
            db.read("stg_ag_production")
