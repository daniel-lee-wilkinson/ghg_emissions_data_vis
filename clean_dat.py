import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import requests
from pathlib import Path

# -----------------------------
# Config
# -----------------------------
DATA_PATH = "data.csv"
COUNTRIES = ["Germany", "France", "Italy", "Spain"]

GDP_INDICATOR = "NY.GDP.MKTP.KD"  # GDP (constant 2015 USD)
GDP_DATE_RANGE = "1990:2024"

UNSD_M49_URL = "https://unstats.un.org/unsd/methodology/m49/overview/"

METRIC_EMISSIONS = "Emissions (kt)"
METRIC_INTENSITY = "Emissions Intensity (kt per Million $USD GDP)"

out_path = "/home/daniel/PycharmProjects/PythonProject/Figures"
# -----------------------------
# Helpers
# -----------------------------
def load_emissions(path: str) -> pd.DataFrame:
    cols = ["Area Code (M49)", "Area", "Element Code", "Element", "Year Code", "Year", "Value"]
    df = pd.read_csv(path, usecols=cols).copy()

    df["Year"] = pd.to_numeric(df["Year"], errors="coerce")
    df["Value"] = pd.to_numeric(df["Value"], errors="coerce")

    df["Area Code (M49)"] = df["Area Code (M49)"].astype("category")
    df["area_code_str"] = df["Area Code (M49)"].astype(int).astype(str).str.zfill(3)
    df["Element"] = df["Element"].str.replace(r"^Emissions \((.+)\)$", r"\1", regex=True)
    return df


def load_unsd_m49_lookup(url: str) -> pd.DataFrame:
    tables = pd.read_html(url)
    m49 = next(t for t in tables if "M49 Code" in t.columns).copy()

    m49["m49_code_str"] = m49["M49 Code"].astype(str).str.zfill(3)
    m49["ISO3"] = m49["ISO-alpha3 Code"].astype(str).str.strip()

    return m49[["m49_code_str", "Region Name", "ISO3"]].drop_duplicates()


def add_continent_and_iso3(emissions: pd.DataFrame, m49_lookup: pd.DataFrame) -> pd.DataFrame:
    out = emissions.merge(
        m49_lookup,
        left_on="area_code_str",
        right_on="m49_code_str",
        how="left"
    ).drop(columns=["m49_code_str"])

    out = out.rename(columns={"Region Name": "Continent"})
    return out


def fetch_world_bank_gdp(indicator: str, date_range: str) -> pd.DataFrame:
    url = (
        f"https://api.worldbank.org/v2/country/all/indicator/{indicator}"
        f"?date={date_range}&format=json&per_page=20000"
    )
    resp = requests.get(url).json()
    if len(resp) < 2:
        raise ValueError(resp)

    gdp = pd.DataFrame(resp[1])[["countryiso3code", "country", "date", "value"]].copy()
    gdp.columns = ["ISO3", "Country_WB", "Year", "GDP_constant_USD"]

    gdp["ISO3"] = gdp["ISO3"].astype(str).str.strip()
    gdp["Year"] = pd.to_numeric(gdp["Year"], errors="coerce")
    gdp["GDP_constant_USD"] = pd.to_numeric(gdp["GDP_constant_USD"], errors="coerce")

    gdp = gdp.dropna(subset=["ISO3", "Year", "GDP_constant_USD"]).copy()
    gdp["Year"] = gdp["Year"].astype(int)
    return gdp


def merge_gdp(emissions: pd.DataFrame, gdp: pd.DataFrame) -> pd.DataFrame:
    out = emissions.merge(
        gdp[["ISO3", "Year", "GDP_constant_USD"]],
        on=["ISO3", "Year"],
        how="left"
    )
    out = out.dropna(subset=["Year", "GDP_constant_USD"]).copy()
    out["Year"] = out["Year"].astype(int)
    return out


def add_intensity(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["emissions_per_million_usd"] = out["Value"] / (out["GDP_constant_USD"] / 1_000_000)
    return out


def add_index_1990(df: pd.DataFrame, value_col: str, group_cols: list[str], out_col: str) -> pd.DataFrame:
    """
    Creates an index (1990 = 100) for `value_col` within each group in group_cols.
    """
    base = (
        df[df["Year"] == 1990]
        .groupby(group_cols, as_index=False)[value_col]
        .mean()
        .rename(columns={value_col: f"{value_col}_1990"})
    )
    out = df.merge(base, on=group_cols, how="left")
    out[out_col] = out[value_col] / out[f"{value_col}_1990"] * 100
    return out

def save_fig(fig, out_path: str | Path, dpi: int = 300):
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=dpi, bbox_inches="tight")
    plt.close(fig)


def plot_emissions_and_intensity_facets(df: pd.DataFrame, countries: list[str], out_path=None) -> None:
    palette = dict(zip(countries, sns.color_palette("colorblind", n_colors=len(countries))))

    plot_df = pd.concat(
        [
            df[["Area", "Element", "Year", "Value"]]
            .rename(columns={"Value": "Y"})
            .assign(Metric=METRIC_EMISSIONS),

            df[["Area", "Element", "Year", "emissions_per_million_usd"]]
            .rename(columns={"emissions_per_million_usd": "Y"})
            .assign(Metric=METRIC_INTENSITY),
        ],
        ignore_index=True
    ).dropna(subset=["Year", "Y"])

    with sns.axes_style("ticks"):
        f = sns.relplot(
            data=plot_df,
            x="Year",
            y="Y",
            hue="Area",
            hue_order=countries,
            palette=palette,
            row="Element",
            col="Metric",
            col_order=[METRIC_EMISSIONS, METRIC_INTENSITY],
            kind="line",
            height=3.5,
            aspect=1.4,
            linewidth=1.0,
            legend=False,
            facet_kws={"sharex": True, "sharey": False},
        )

    f.set_titles(row_template="{row_name}", col_template="{col_name}")
    f.set_axis_labels("Year", "")

    yr_max = int(plot_df["Year"].max())
    f.axes.flat[0].set_xlim(1990, yr_max)

    for ax in f.axes.flat:
        sns.despine(ax=ax, offset=8)
        data_lines = [l for l in ax.get_lines() if len(l.get_xdata()) > 2]
        for line, country in zip(data_lines, countries):
            xdata = np.asarray(line.get_xdata(), dtype=float)
            ydata = np.asarray(line.get_ydata(), dtype=float)
            valid = ~(np.isnan(xdata) | np.isnan(ydata))
            if valid.any():
                ax.annotate(
                    country,
                    xy=(xdata[valid][-1], ydata[valid][-1]),
                    xytext=(5, 0),
                    textcoords="offset points",
                    va="center",
                    fontsize=7,
                    color=line.get_color(),
                    annotation_clip=False,
                )

    if out_path is not None:
        save_fig(f.fig, out_path)

    return f





def plot_emissions_index_facets(df, countries, index_col, out_path=None):
    palette = dict(zip(countries, sns.color_palette("colorblind", n_colors=len(countries))))

    with sns.axes_style("ticks"):
        g = sns.relplot(
            data=df.dropna(subset=[index_col]),
            x="Year",
            y=index_col,
            hue="Area",
            hue_order=countries,
            palette=palette,
            row="Element",
            kind="line",
            height=3.5,
            aspect=1.6,
            linewidth=1.0,
            legend=False,
            facet_kws={"sharex": True, "sharey": True},
        )

    g.set_titles(row_template="{row_name}")

    yr_max = int(df.loc[df[index_col].notna(), "Year"].max())
    g.axes.flat[0].set_xlim(1990, yr_max)

    for ax in g.axes.flat:
        sns.despine(ax=ax, offset=8)
        data_lines = [l for l in ax.get_lines() if len(l.get_xdata()) > 2]
        for line, country in zip(data_lines, countries):
            xdata = np.asarray(line.get_xdata(), dtype=float)
            ydata = np.asarray(line.get_ydata(), dtype=float)
            valid = ~(np.isnan(xdata) | np.isnan(ydata))
            if valid.any():
                ax.annotate(
                    country,
                    xy=(xdata[valid][-1], ydata[valid][-1]),
                    xytext=(5, 0),
                    textcoords="offset points",
                    va="center",
                    fontsize=7,
                    color=line.get_color(),
                    annotation_clip=False,
                )
        # Reference line added last so it is not picked up by the label loop
        ax.axhline(100, linestyle="--", color="#999999", linewidth=0.7, alpha=0.4, zorder=0)

    g.set_axis_labels("Year", "Emissions Index (1990 = 100)")

    if out_path is not None:
        save_fig(g.fig, out_path)

    return g

def compute_percent_change_1990_to_latest(df: pd.DataFrame) -> pd.DataFrame:
    latest_year = int(df["Year"].max())

    wide = (
        df[df["Year"].isin([1990, latest_year])]
        .groupby(["Area", "Element", "Year"])["Value"]
        .mean()
        .unstack()
    )
    wide["percent_change"] = (wide[latest_year] - wide[1990]) / wide[1990] * 100
    wide["latest_year"] = latest_year
    return wide.reset_index()


def compute_index_slopes(df: pd.DataFrame, index_col: str) -> pd.DataFrame:
    rows = []
    for (area, element), g in df.dropna(subset=[index_col]).groupby(["Area", "Element"]):
        x = g["Year"].to_numpy()
        y = g[index_col].to_numpy()
        slope, _intercept = np.polyfit(x, y, 1)
        rows.append({"Area": area, "Element": element, "Annual_slope": slope})
    return pd.DataFrame(rows)


# -----------------------------
# Pipeline
# -----------------------------
emissions = load_emissions(DATA_PATH)

# Quick structural check (ignores Element)
print("Expected Area-Year combos (ignoring Element):", emissions["Year"].nunique() * emissions["Area Code (M49)"].nunique())
print("Actual rows:", len(emissions))

m49_lookup = load_unsd_m49_lookup(UNSD_M49_URL)
emissions = add_continent_and_iso3(emissions, m49_lookup)

print("Continent values (sample):", emissions["Continent"].dropna().unique()[:10])
print("ISO3 missing rows:", emissions["ISO3"].isna().sum())

gdp = fetch_world_bank_gdp(GDP_INDICATOR, GDP_DATE_RANGE)
print("GDP rows:", len(gdp))
print("GDP year range:", gdp["Year"].min(), "-", gdp["Year"].max())

# Keep only the countries you care about early to reduce noise
emissions_we = emissions[emissions["Area"].isin(COUNTRIES)].copy()

# Merge GDP + compute intensity
emissions_we = merge_gdp(emissions_we, gdp)
emissions_we = add_intensity(emissions_we)

# Plot: emissions vs intensity (3 rows x 2 cols)
plot_emissions_and_intensity_facets(emissions_we, COUNTRIES, out_path=f"{out_path}/fig1_emissions_intensity.png")

# Emissions index (1990=100) per country x gas
emissions_we = emissions_we.dropna(subset=["Year", "Value"]).copy()
emissions_we["Year"] = emissions_we["Year"].astype(int)

emissions_we = add_index_1990(
    emissions_we,
    value_col="Value",
    group_cols=["Area", "Element"],
    out_col="Emissions_index_1990_100"
)

plot_emissions_index_facets(emissions_we, COUNTRIES, "Emissions_index_1990_100", out_path=f"{out_path}/fig2_emissions_index.png")

# Summary + slopes (on emissions, per gas)
pct_change = compute_percent_change_1990_to_latest(emissions_we)
print(pct_change.sort_values(["Element", "Area"]))

slopes = compute_index_slopes(emissions_we, "Emissions_index_1990_100")
print(slopes.sort_values(["Element", "Area"]))