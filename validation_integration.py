"""
validation_integration.py
--------------------------
Shows exactly where to add Pandera validation into loaders.py
and clean_dat.py. These are not new files — copy the relevant
snippets into the existing functions.

Three integration patterns are shown:
  1. Explicit validate() call inside a function
  2. @pa.check_output decorator — validates what a function returns
  3. @pa.check_input decorator  — validates what a function receives
"""
import pandera as pa
from schemas import (
    EmissionsSchema,
    EmissionsWithGDPSchema,
    EmissionsIndexSchema,
    FAOStatSchema,
    SectorShareSchema,
    GDPSchema,
    PercentChangeSchema,
    IndexSlopesSchema,
)

# ===========================================================================
# Pattern 1 — explicit validate() call
# Useful when you want to catch errors at a specific point and get a clear
# error message showing exactly which rows/columns failed.
# ===========================================================================

# In loaders.py, at the end of load_emissions():
#
#   def load_emissions(path):
#       ...
#       return EmissionsSchema.validate(df)   # ← add this line
#
# If any row has Element = "Emissions (CH4)" instead of "CH4",
# or area_code_str = "4" instead of "004", it raises immediately:
#
#   SchemaError: column 'Element' failed validator isin(['CH4', 'CO2', 'N2O'])


# ===========================================================================
# Pattern 2 — @pa.check_output decorator
# Cleaner: the schema is declared at the function definition,
# validation runs automatically on every call.
# ===========================================================================

# In loaders.py:
#
#   @pa.check_output(EmissionsSchema)
#   def load_emissions(path: str | Path) -> pd.DataFrame:
#       ...
#
# In clean_dat.py:
#
#   @pa.check_output(EmissionsWithGDPSchema)
#   def merge_gdp(emissions: pd.DataFrame, gdp: pd.DataFrame) -> pd.DataFrame:
#       ...
#
#   @pa.check_output(EmissionsIndexSchema)
#   def add_index_1990(df, value_col, group_cols, out_col) -> pd.DataFrame:
#       ...
#
#   @pa.check_output(PercentChangeSchema)
#   def compute_percent_change(df: pd.DataFrame) -> pd.DataFrame:
#       ...
#
#   @pa.check_output(IndexSlopesSchema)
#   def compute_index_slopes(df, index_col) -> pd.DataFrame:
#       ...


# ===========================================================================
# Pattern 3 — @pa.check_input decorator
# Validates the DataFrame argument before the function body runs.
# Useful to confirm you're not passing uncleaned data into a transform.
# ===========================================================================

# In clean_dat.py:
#
#   @pa.check_input(EmissionsSchema, "emissions")   # validates 'emissions' arg
#   @pa.check_output(EmissionsWithGDPSchema)
#   def merge_gdp(emissions: pd.DataFrame, gdp: pd.DataFrame) -> pd.DataFrame:
#       ...


# ===========================================================================
# What a validation failure looks like
# ===========================================================================
#
#   pandera.errors.SchemaError: expected series 'Element' to be in
#   {'CH4', 'CO2', 'N2O'}, got ['Emissions (CH4)', 'Emissions (CO2)']
#   at index [0, 1, 2, ...]
#
# The error includes:
#   - which column failed
#   - which validator failed
#   - which row indices failed
#   - the actual values that caused the failure
#
# You can also get a full failure report without raising:
#
#   try:
#       EmissionsSchema.validate(df, lazy=True)
#   except pa.errors.SchemaErrors as e:
#       print(e.failure_cases)   # DataFrame of all failures at once


# ===========================================================================
# Custom dataframe-level checks (beyond column-level)
# ===========================================================================
#
# SectorShareSchema already has one:
#
#   @pa.dataframe_check
#   def proportions_sum_to_one_per_country(cls, df):
#       sums = df.groupby("Country")["Proportion"].sum()
#       return ((sums - 1.0).abs() < 0.02).all()
#
# You can add similar checks to any schema, e.g.:
#
#   @pa.dataframe_check
#   def no_duplicate_country_year(cls, df):
#       """Each (Area, Year, Element) combination should appear once."""
#       return ~df.duplicated(subset=["Area", "Year", "Element"]).any()