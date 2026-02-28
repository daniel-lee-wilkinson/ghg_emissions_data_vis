"""
db.py
-----
DuckDB database layer for the European GHG + Agriculture pipeline.

Schema
------
Staging tables (raw, minimally cleaned):
    stg_emissions         — FAOSTAT emissions by country / gas / year
    stg_ag_production     — FAOSTAT gross production index
    stg_fv_production     — FAOSTAT fruit & vegetable production index
    stg_ag_items          — FAOSTAT all-items production index (commodity level)
    stg_sector_shares     — sector-level emissions proportions (all countries)
    stg_gdp               — World Bank GDP (constant 2015 USD)

Mart tables (transformed, analysis-ready):
    mart_emissions_index  — emissions indexed to 1990 = 100, with intensity
    mart_percent_change   — % change 1990 → latest year per country / gas
    mart_index_slopes     — OLS annual slope of emissions index
    mart_top_ag_items     — top commodity per country per 5-year bin

Usage
-----
    from db import Database

    db = Database()                        # opens pipeline.db (creates if absent)
    db = Database(":memory:")              # in-memory, useful for tests

    db.write("stg_emissions", df)          # replace table
    db.write("stg_emissions", df, "append")
    df = db.read("stg_emissions")
    df = db.query("SELECT * FROM stg_emissions WHERE Area = 'Italy'")
    db.close()

    # or use as a context manager
    with Database() as db:
        db.write("stg_emissions", df)
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Literal

import duckdb
import pandas as pd

from config import FIG_DIR

log = logging.getLogger(__name__)

DB_PATH = Path("pipeline.db")

# Canonical schema definitions — enforced on every write
# Maps table name → list of (column, duckdb_type) tuples
TABLE_SCHEMAS: dict[str, list[tuple[str, str]]] = {
    # ------------------------------------------------------------------
    # Staging
    # ------------------------------------------------------------------
    "stg_emissions": [
        ("Area",            "VARCHAR"),
        ("area_code_m49",   "INTEGER"),
        ("area_code_str",   "VARCHAR"),
        ("Element",         "VARCHAR"),   # CH4 | CO2 | N2O
        ("Year",            "INTEGER"),
        ("Value",           "DOUBLE"),    # kt
    ],
    "stg_ag_production": [
        ("Area",    "VARCHAR"),
        ("Element", "VARCHAR"),
        ("Year",    "INTEGER"),
        ("Value",   "DOUBLE"),    # index (2014-2016 = 100)
    ],
    "stg_fv_production": [
        ("Area",    "VARCHAR"),
        ("Element", "VARCHAR"),
        ("Year",    "INTEGER"),
        ("Value",   "DOUBLE"),
    ],
    "stg_ag_items": [
        ("Area",             "VARCHAR"),
        ("Element",          "VARCHAR"),
        ("Year",             "INTEGER"),
        ("Value",            "DOUBLE"),
        ("item_code_cpc",    "VARCHAR"),
        ("Item",             "VARCHAR"),
    ],
    "stg_sector_shares": [
        ("Country",    "VARCHAR"),
        ("Year",       "INTEGER"),
        ("Gas",        "VARCHAR"),   # CO2 | GHG
        ("Sector",     "VARCHAR"),
        ("Amount",     "DOUBLE"),
        ("Proportion", "DOUBLE"),
        ("source_note","VARCHAR"),
    ],
    "stg_gdp": [
        ("ISO3",             "VARCHAR"),
        ("Country_WB",       "VARCHAR"),
        ("Year",             "INTEGER"),
        ("GDP_constant_USD", "DOUBLE"),
    ],
    # ------------------------------------------------------------------
    # Marts
    # ------------------------------------------------------------------
    "mart_emissions_index": [
        ("Area",                     "VARCHAR"),
        ("Element",                  "VARCHAR"),
        ("Year",                     "INTEGER"),
        ("Value",                    "DOUBLE"),
        ("GDP_constant_USD",         "DOUBLE"),
        ("emissions_per_million_usd","DOUBLE"),
        ("Emissions_index_1990_100", "DOUBLE"),
    ],
    "mart_percent_change": [
        ("Area",          "VARCHAR"),
        ("Element",       "VARCHAR"),
        ("value_1990",    "DOUBLE"),
        ("value_latest",  "DOUBLE"),
        ("percent_change","DOUBLE"),
        ("latest_year",   "INTEGER"),
    ],
    "mart_index_slopes": [
        ("Area",         "VARCHAR"),
        ("Element",      "VARCHAR"),
        ("Annual_slope", "DOUBLE"),
    ],
    "mart_top_ag_items": [
        ("Area",      "VARCHAR"),
        ("year_bin",  "INTEGER"),
        ("Item",      "VARCHAR"),
        ("avg_value", "DOUBLE"),
    ],
}


class Database:
    """
    Thin wrapper around a DuckDB connection.

    All writes go through _validate_and_cast() which aligns the DataFrame
    to the declared schema before writing, catching column mismatches early.
    """

    def __init__(self, path: str | Path = DB_PATH) -> None:
        self._path = str(path)
        self._con = duckdb.connect(self._path)
        log.info("Opened DuckDB database at %s", self._path)
        self._initialise_schema()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def write(
        self,
        table: str,
        df: pd.DataFrame,
        mode: Literal["replace", "append"] = "replace",
    ) -> None:
        """
        Write a DataFrame to `table`.

        Parameters
        ----------
        table : canonical table name (must exist in TABLE_SCHEMAS)
        df    : data to write — columns are validated against the schema
        mode  : 'replace' drops and recreates the table; 'append' inserts
        """
        if table not in TABLE_SCHEMAS:
            raise ValueError(
                f"Unknown table '{table}'. "
                f"Valid tables: {sorted(TABLE_SCHEMAS)}"
            )
        df = self._validate_and_cast(table, df)
        if mode == "replace":
            self._con.execute(f"DROP TABLE IF EXISTS {table}")

        # Register df as a temporary view then INSERT or CREATE from it
        self._con.register("_staging", df)
        if mode == "replace":
            cols_ddl = ", ".join(
                f"{col} {dtype}"
                for col, dtype in TABLE_SCHEMAS[table]
            )
            self._con.execute(
                f"CREATE TABLE {table} AS SELECT * FROM _staging"
            )
        else:
            self._con.execute(f"INSERT INTO {table} SELECT * FROM _staging")

        self._con.unregister("_staging")
        n = self._con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        log.info("Wrote %d rows → %s (%s)", len(df), table, mode)
        log.debug("Table %s now has %d total rows", table, n)

    def read(self, table: str) -> pd.DataFrame:
        """Read an entire table into a DataFrame."""
        return self._con.execute(f"SELECT * FROM {table}").df()

    def query(self, sql: str) -> pd.DataFrame:
        """Execute arbitrary SQL and return results as a DataFrame."""
        return self._con.execute(sql).df()

    def tables(self) -> list[str]:
        """List all tables currently in the database."""
        result = self._con.execute(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = 'main' ORDER BY table_name"
        ).fetchall()
        return [r[0] for r in result]

    def row_counts(self) -> pd.DataFrame:
        """Return a summary of row counts for all tables."""
        rows = []
        for table in self.tables():
            n = self._con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            rows.append({"table": table, "rows": n})
        return pd.DataFrame(rows)

    def close(self) -> None:
        self._con.close()
        log.info("Closed DuckDB connection")

    def __enter__(self) -> "Database":
        return self

    def __exit__(self, *_) -> None:
        self.close()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _initialise_schema(self) -> None:
        """Create any missing tables as empty shells on first open."""
        existing = set(self.tables())
        for table, cols in TABLE_SCHEMAS.items():
            if table not in existing:
                cols_ddl = ", ".join(f"{col} {dtype}" for col, dtype in cols)
                self._con.execute(
                    f"CREATE TABLE IF NOT EXISTS {table} ({cols_ddl})"
                )
        log.debug("Schema initialised — %d tables", len(TABLE_SCHEMAS))

    def _validate_and_cast(
        self, table: str, df: pd.DataFrame
    ) -> pd.DataFrame:
        """
        Align df to the declared schema:
          - Rename columns to canonical names (case-insensitive match)
          - Check all required columns are present
          - Select only schema columns (drops extras)
          - Cast to declared dtypes where possible
        """
        schema_cols = [col for col, _ in TABLE_SCHEMAS[table]]

        # Build a case-insensitive rename map
        df_cols_lower = {c.lower(): c for c in df.columns}
        rename_map = {}
        for schema_col in schema_cols:
            if schema_col not in df.columns and schema_col.lower() in df_cols_lower:
                rename_map[df_cols_lower[schema_col.lower()]] = schema_col
        if rename_map:
            df = df.rename(columns=rename_map)

        missing = set(schema_cols) - set(df.columns)
        if missing:
            raise ValueError(
                f"Table '{table}': missing columns {sorted(missing)}. "
                f"DataFrame has: {sorted(df.columns.tolist())}"
            )

        # Cast dtypes
        dtype_map = {
            "VARCHAR": "string",
            "INTEGER": "Int64",
            "DOUBLE":  "float64",
        }
        result = df[schema_cols].copy()
        for col, duck_type in TABLE_SCHEMAS[table]:
            pd_type = dtype_map.get(duck_type)
            if pd_type:
                try:
                    result[col] = result[col].astype(pd_type)
                except (ValueError, TypeError) as e:
                    log.warning("Could not cast %s.%s to %s: %s", table, col, pd_type, e)

        return result
