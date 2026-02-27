import csv
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt

# Analysis of agricultural gross production index for Western and Southern Europe
# data source explainer: https://files-faostat.fao.org/production/QI/QI_e.pdf
# base period 2014-2016 = 100

west_ag_data = pd.read_csv("FAOSTAT_data_western_europe.csv")

# select only the columns we need
relevant_columns = ["Area", "Element", "Unit", "Value", "Year"]
west_ag_data = west_ag_data[relevant_columns]

south_ag_data = pd.read_csv("FAOSTAT_southern_europe.csv")
south_ag_data = south_ag_data[relevant_columns]

# join the two datasets together
ag_data = pd.concat([west_ag_data, south_ag_data], ignore_index=True)



selected_countries = ["Italy", "Spain", "France", "Germany"]
ag_data["Area"] = ag_data["Area"].astype(str).str.strip()
ag_data = ag_data[ag_data["Area"].isin(selected_countries)]


# print unique years in the dataset
print(ag_data["Year"].unique()) # 1990 to 2017

# facetted line plot of the agricultural gross production index for each country over time
# the figure should have a high ratio of meaning to ink as explained by Tufte, so we will use a simple line plot with markers and a legend

plt.figure(figsize=(10, 6))
sns.lineplot(data=ag_data, x="Year", y="Value", hue="Area", marker="o")
plt.title("Agricultural Gross Production Index (2014-2016=100) for Selected European Countries")
plt.xlabel("Year")
plt.ylabel("Gross Production Index")
plt.legend(title="Country")
plt.savefig("Figures/agricultural_gross_production_index.png")


fv_data = pd.read_csv("FAOSTAT_data_fruit_veg.csv")
fv_data = fv_data[relevant_columns]
fv_data = fv_data[fv_data["Area"].isin(selected_countries)]


# plot the fruit and vegetable production index for the selected countries following Tufte's principles of data visualization
plt.figure(figsize=(10, 6))
sns.lineplot(data=fv_data, x="Year", y="Value", hue="Area", marker="o")
plt.title("Fruit and Vegetable Production Index (2014-2016=100) for Selected European Countries")
plt.xlabel("Year")
plt.ylabel("Production Index")
plt.legend(title="Country")
plt.savefig("Figures/fruit_veg_production_index.png")


# read in all_ag data
all_ag_data = pd.read_csv("FAOSTAT_data_all_ag.csv")


ag_data_columns = ["Area", "Element", "Unit", "Value", "Year", "Item Code (CPC)", "Item"]
all_ag_data = all_ag_data[ag_data_columns]
# strip whitespace from Area column and filter to selected countries
all_ag_data["Area"] = all_ag_data["Area"].astype(str).str.strip()
all_ag_data = all_ag_data[all_ag_data["Area"].isin(selected_countries)]



# how many times does each Item Code (CPC) appear for each counry in all_ag_data?
item_code_counts = (all_ag_data
    .groupby(["Area", "Year", "Item Code (CPC)", "Item"])
    .size()
    .reset_index(name="counts")
)
print(item_code_counts)

# compute the top item code for each country in each year including Item Code (CPC), Item and Value
tmp = all_ag_data.dropna(subset=["Value"]).copy()
top_item_codes = (tmp
    .sort_values(["Area", "Year", "Value"], ascending=[True, True, False])
    .drop_duplicates(subset=["Area", "Year"])
)

print(top_item_codes[["Area", "Year", "Item Code (CPC)", "Item", "Value"]])


df = all_ag_data.copy()

# Ensure types are usable
df["Year"] = pd.to_numeric(df["Year"], errors="coerce")
df["Value"] = pd.to_numeric(df["Value"], errors="coerce")
df = df.dropna(subset=["Year", "Value"])

# 5-year bins labelled by their start year: 1990, 1995, 2000, ...
start_year = 1990
df["year_bin"] = start_year + ((df["Year"] - start_year) // 5) * 5

# (1) Average Value per item within each (Area, year_bin)
bin_item_avg = (df
    .groupby(["Area", "year_bin", "Item Code (CPC)", "Item"], as_index=False)
    .agg(avg_value=("Value", "mean"))
)

# (2) Pick the top item per (Area, year_bin)
# sort so top avg_value comes first, then drop duplicates
top_item_per_bin = (bin_item_avg
    .sort_values(["Area", "year_bin", "avg_value"], ascending=[True, True, False])
    .drop_duplicates(subset=["Area", "year_bin"])
    .reset_index(drop=True)
)

print(top_item_per_bin.sort_values(["Area", "year_bin"]))

# (3) Facetted plot: one facet per country (Area)
g = sns.FacetGrid(
    top_item_per_bin,
    col="Area",
    col_wrap=2,
    sharey=False,      # often helpful because levels differ a lot by country
    height=3.5,
    aspect=1.3
)

# line + points
g.map_dataframe(sns.lineplot, x="year_bin", y="avg_value")
g.map_dataframe(sns.scatterplot, x="year_bin", y="avg_value")

# annotate points with the item name so you "show what the top item is"
for ax, (area, sub) in zip(g.axes.flatten(), top_item_per_bin.groupby("Area")):
    sub = sub.sort_values("year_bin")
    for _, r in sub.iterrows():
        ax.annotate(
            text=str(r["Item"]),
            xy=(r["year_bin"], r["avg_value"]),
            xytext=(3, 3),
            textcoords="offset points",
            fontsize=8
        )
    ax.set_title(area)
    ax.set_xlabel("Year (5-year bins)")
    ax.set_ylabel("Avg Value of top item")

g.fig.suptitle("Top agricultural item by 5-year bin (mean Value within bin)", y=1.02)
plt.tight_layout()
g.figure.savefig("Figures/top_item_every_5_years_by_country.png", bbox_inches="tight")
plt.close(g.figure) 


# Germany's agricultural gross production index is lowest of Italy and France.
# No data available for Spain.
# France consistently has the highest gross production index, dominated over most of the period by hemp. 
# Italy's gross production index is dominated by horse meat, which is the top item for most of the period, but has declined in recent years.