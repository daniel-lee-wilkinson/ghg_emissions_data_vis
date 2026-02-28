const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
  ImageRun, Header, Footer, AlignmentType, HeadingLevel, BorderStyle,
  WidthType, ShadingType, VerticalAlign, PageNumber, PageBreak,
  TabStopType, TabStopPosition, LevelFormat, TableOfContents
} = require('docx');
const fs = require('fs');
const path = require('path');

// ---------------------------------------------------------------------------
// Config
// ---------------------------------------------------------------------------
const CONTENT_WIDTH = 9360; // US Letter - 1" margins each side (DXA)
const ACCENT   = "1F4E79";  // dark navy
const ACCENT2  = "2E75B6";  // mid blue
const LIGHT_BG = "D6E4F0";  // light blue for header cells
const FIG_DIR  = "/home/daniel/PycharmProjects/PythonProject/Figures";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function heading1(text) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_1,
    children: [new TextRun({ text, font: "Arial", size: 32, bold: true, color: ACCENT })],
    spacing: { before: 360, after: 160 },
    border: { bottom: { style: BorderStyle.SINGLE, size: 6, color: ACCENT2, space: 4 } },
  });
}

function heading2(text) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_2,
    children: [new TextRun({ text, font: "Arial", size: 26, bold: true, color: ACCENT2 })],
    spacing: { before: 280, after: 120 },
  });
}

function body(text, opts = {}) {
  return new Paragraph({
    children: [new TextRun({ text, font: "Arial", size: 22, ...opts })],
    spacing: { before: 80, after: 80 },
    alignment: AlignmentType.JUSTIFIED,
  });
}

function caption(text) {
  return new Paragraph({
    children: [new TextRun({ text, font: "Arial", size: 18, italics: true, color: "555555" })],
    spacing: { before: 60, after: 200 },
    alignment: AlignmentType.CENTER,
  });
}

function spacer() {
  return new Paragraph({ children: [new TextRun("")], spacing: { before: 80, after: 80 } });
}

function pageBreak() {
  return new Paragraph({ children: [new PageBreak()], spacing: { before: 0, after: 0 } });
}

// Scale image to fit content width, preserving aspect ratio
function figureImage(filename, captionText, maxWidthPx = CONTENT_WIDTH) {
  const imgPath = path.join(FIG_DIR, filename);
  const data = fs.readFileSync(imgPath);
  // Read actual dims from filename lookup
  const dims = IMAGE_DIMS[filename];
  const aspect = dims.h / dims.w;
  const widthDxa  = maxWidthPx;
  const heightDxa = Math.round(widthDxa * aspect);
  return [
    new Paragraph({
      children: [new ImageRun({
        type: "png",
        data,
        transformation: { width: widthDxa / 20, height: heightDxa / 20 }, // DXA/20 ≈ pt → px at 96dpi
        altText: { title: captionText, description: captionText, name: filename }
      })],
      alignment: AlignmentType.CENTER,
      spacing: { before: 160, after: 60 },
    }),
    caption(captionText),
  ];
}

// Image pixel dimensions (from introspection)
const IMAGE_DIMS = {
  "agricultural_gross_production_index.png": { w: 2552, h: 1638 },
  "fruit_veg_production_index.png":          { w: 2552, h: 1638 },
  "top_item_every_5_years_by_country.png":   { w: 2710, h: 2157 },
  "fig1_emissions_intensity.png":                      { w: 997,  h: 1628 },
  "fig2_emissions_index.png":                { w: 1002, h: 1628 },
  "ghg_emissions_by_sector_heatmap.png":     { w: 2290, h: 1857 },
};

// ---------------------------------------------------------------------------
// Table builders
// ---------------------------------------------------------------------------
const cellBorder = { style: BorderStyle.SINGLE, size: 1, color: "CCCCCC" };
const borders = { top: cellBorder, bottom: cellBorder, left: cellBorder, right: cellBorder };
const cellMargins = { top: 80, bottom: 80, left: 120, right: 120 };

function headerCell(text, widthDxa) {
  return new TableCell({
    borders,
    width: { size: widthDxa, type: WidthType.DXA },
    shading: { fill: LIGHT_BG, type: ShadingType.CLEAR },
    margins: cellMargins,
    children: [new Paragraph({
      children: [new TextRun({ text, font: "Arial", size: 20, bold: true, color: ACCENT })],
      alignment: AlignmentType.CENTER,
    })],
  });
}

function dataCell(text, widthDxa, align = AlignmentType.CENTER, shade = "FFFFFF") {
  return new TableCell({
    borders,
    width: { size: widthDxa, type: WidthType.DXA },
    shading: { fill: shade, type: ShadingType.CLEAR },
    margins: cellMargins,
    children: [new Paragraph({
      children: [new TextRun({ text: String(text ?? "—"), font: "Arial", size: 20 })],
      alignment: align,
    })],
  });
}

// --- Table 1: Agricultural production index summary ---
function buildAgTable() {
  const colW = [2500, 1715, 1715, 1715, 1715];
  const data = [
    ["France",  "101.77", "101.32", "-0.4",  "↔"],
    ["Germany", "99.62",  "97.50",  "-2.1",  "↓"],
    ["Italy",   "103.58", "98.11",  "-5.3",  "↓"],
    ["Spain",   "78.10",  "101.64", "+30.1", "↑"],
  ];
  return new Table({
    width: { size: CONTENT_WIDTH, type: WidthType.DXA },
    columnWidths: colW,
    rows: [
      new TableRow({ children: [
        headerCell("Country", colW[0]),
        headerCell("Index 1990", colW[1]),
        headerCell("Index 2017", colW[2]),
        headerCell("Change (%)", colW[3]),
        headerCell("Trend", colW[4]),
      ]}),
      ...data.map((r, i) => new TableRow({
        children: r.map((v, j) => dataCell(v, colW[j], j === 0 ? AlignmentType.LEFT : AlignmentType.CENTER, i % 2 === 0 ? "FFFFFF" : "F5F9FC"))
      }))
    ],
  });
}

// --- Table 2: Emissions % change 1990-2021 ---
function buildEmissionsTable() {
  const colW = [1800, 1890, 1890, 1890, 1890];
  const data = [
    ["CH4",  "-22.7%", "-41.9%", "-23.4%", "+12.8%"],
    ["CO2",  "-2.4%",  "+31.0%", "-18.3%", "+61.4%"],
    ["N2O",  "-17.8%", "-27.6%", "-25.0%", "+6.7%"],
  ];
  return new Table({
    width: { size: CONTENT_WIDTH, type: WidthType.DXA },
    columnWidths: colW,
    rows: [
      new TableRow({ children: [
        headerCell("Gas", colW[0]),
        headerCell("France", colW[1]),
        headerCell("Germany", colW[2]),
        headerCell("Italy", colW[3]),
        headerCell("Spain", colW[4]),
      ]}),
      ...data.map((r, i) => new TableRow({
        children: r.map((v, j) => dataCell(v, colW[j], AlignmentType.CENTER, i % 2 === 0 ? "FFFFFF" : "F5F9FC"))
      }))
    ],
  });
}

// --- Table 3: Sector shares ---
function buildSectorTable() {
  const colW = [2560, 1700, 1700, 1700, 1700];
  const data = [
    ["Agriculture",              "21.0%", "0.4%",  "—",     "13.8%"],
    ["Aviation & Shipping",      "—",     "—",     "5.0%",  "—"],
    ["Energy",                   "9.0%",  "84.4%", "23.8%", "12.9%"],
    ["Industry",                 "17.0%", "5.7%",  "1.9%",  "21.1%"],
    ["LULUCF",                   "—",     "9.6%",  "14.9%", "—"],
    ["Manufacturing",            "—",     "—",     "10.0%", "—"],
    ["Other Fuel Combustion",    "—",     "—",     "2.1%",  "—"],
    ["Residential & Commercial", "15.0%", "—",     "13.6%", "9.6%"],
    ["Transport",                "34.0%", "—",     "28.8%", "36.8%"],
    ["Waste",                    "4.0%",  "—",     "—",     "5.8%"],
  ];
  return new Table({
    width: { size: CONTENT_WIDTH, type: WidthType.DXA },
    columnWidths: colW,
    rows: [
      new TableRow({ children: [
        headerCell("Sector", colW[0]),
        headerCell("France", colW[1]),
        headerCell("Germany", colW[2]),
        headerCell("Italy", colW[3]),
        headerCell("Spain", colW[4]),
      ]}),
      ...data.map((r, i) => new TableRow({
        children: r.map((v, j) => dataCell(v, colW[j], j === 0 ? AlignmentType.LEFT : AlignmentType.CENTER, i % 2 === 0 ? "FFFFFF" : "F5F9FC"))
      }))
    ],
  });
}

// ---------------------------------------------------------------------------
// Header / Footer
// ---------------------------------------------------------------------------
function makeHeader() {
  return new Header({
    children: [
      new Paragraph({
        children: [
          new TextRun({ text: "GHG Emissions & Agricultural Production in Europe", font: "Arial", size: 18, color: "777777" }),
        ],
        border: { bottom: { style: BorderStyle.SINGLE, size: 4, color: ACCENT2, space: 4 } },
        spacing: { after: 0 },
        alignment: AlignmentType.RIGHT,
      })
    ]
  });
}

function makeFooter() {
  return new Footer({
    children: [
      new Paragraph({
        children: [
          new TextRun({ text: "Page ", font: "Arial", size: 18, color: "777777" }),
          new TextRun({ children: [PageNumber.CURRENT], font: "Arial", size: 18, color: "777777" }),
          new TextRun({ text: " of ", font: "Arial", size: 18, color: "777777" }),
          new TextRun({ children: [PageNumber.TOTAL_PAGES], font: "Arial", size: 18, color: "777777" }),
        ],
        alignment: AlignmentType.CENTER,
        border: { top: { style: BorderStyle.SINGLE, size: 4, color: "CCCCCC", space: 4 } },
        spacing: { before: 80 },
      })
    ]
  });
}

// ---------------------------------------------------------------------------
// Document assembly
// ---------------------------------------------------------------------------
const doc = new Document({
  styles: {
    default: { document: { run: { font: "Arial", size: 22 } } },
    paragraphStyles: [
      {
        id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 32, bold: true, font: "Arial", color: ACCENT },
        paragraph: { spacing: { before: 360, after: 160 }, outlineLevel: 0 },
      },
      {
        id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 26, bold: true, font: "Arial", color: ACCENT2 },
        paragraph: { spacing: { before: 280, after: 120 }, outlineLevel: 1 },
      },
    ]
  },

  sections: [{
    properties: {
      page: {
        size: { width: 12240, height: 15840 },
        margin: { top: 1440, right: 1440, bottom: 1440, left: 1440 }
      }
    },
    headers: { default: makeHeader() },
    footers: { default: makeFooter() },

    children: [

      // ── Title page ──────────────────────────────────────────────────────
      spacer(), spacer(), spacer(),
      new Paragraph({
        children: [new TextRun({ text: "GHG Emissions and Agricultural Production", font: "Arial", size: 52, bold: true, color: ACCENT })],
        alignment: AlignmentType.CENTER,
        spacing: { before: 0, after: 200 },
      }),
      new Paragraph({
        children: [new TextRun({ text: "in Selected European Countries", font: "Arial", size: 40, bold: true, color: ACCENT2 })],
        alignment: AlignmentType.CENTER,
        spacing: { before: 0, after: 400 },
      }),
      new Paragraph({
        children: [new TextRun({ text: "Italy · Spain · France · Germany", font: "Arial", size: 24, italics: true, color: "555555" })],
        alignment: AlignmentType.CENTER,
        spacing: { before: 0, after: 200 },
      }),
      new Paragraph({
        children: [new TextRun({ text: "Analysis period: 1990–2023", font: "Arial", size: 22, color: "777777" })],
        alignment: AlignmentType.CENTER,
        spacing: { before: 0, after: 800 },
      }),
      new Paragraph({
        children: [new TextRun({ text: `Generated: ${new Date().toLocaleDateString('en-GB', {day:'numeric',month:'long',year:'numeric'})}`, font: "Arial", size: 20, color: "999999" })],
        alignment: AlignmentType.CENTER,
      }),
      pageBreak(),

      // ── Table of Contents ───────────────────────────────────────────────
      heading1("Contents"),
      new TableOfContents("Table of Contents", {
        hyperlink: true,
        headingStyleRange: "1-2",
      }),
      pageBreak(),

      // ── 1. Introduction ─────────────────────────────────────────────────
      heading1("1. Introduction"),
      body("This report examines two interrelated dimensions of environmental and agricultural performance across four major Western European economies — Italy, Spain, France, and Germany — over the period 1990 to 2023. The first dimension concerns greenhouse gas (GHG) emissions from agricultural land, analysed by gas type (CH\u2084, CO\u2082, and N\u2082O) and expressed both in absolute kilotonnes and as an index relative to 1990. The second dimension concerns agricultural production performance, measured using the FAOSTAT Gross Production Index, which tracks changes in the volume of agricultural output relative to the 2014\u20132016 base period."),
      spacer(),
      body("The four countries selected represent the largest agricultural economies in Western Europe and exhibit significant structural differences in their emissions profiles and farming systems. Germany is characterised by intensive arable and livestock production; France by a diverse mixed system including significant livestock, cereals, and speciality crops; Italy by a Mediterranean model centred on horticulture, viticulture, and olive production; and Spain by a rapidly expanding irrigated fruit and vegetable sector alongside traditional dryland cereal farming."),
      spacer(),
      body("The report is structured as follows. Section 2 describes the data sources used. Section 3 explains the methodological choices made in processing and presenting the data. Section 4 presents results across the three analytical dimensions: agricultural production indices, emissions trends, and sector-level emissions breakdowns. Section 5 interprets the key findings and highlights cross-country differences. Section 6 concludes with a summary of the main observations and directions for further analysis."),

      // ── 2. Data Sources ─────────────────────────────────────────────────
      pageBreak(),
      heading1("2. Data Sources"),

      heading2("2.1 FAOSTAT Production Indices"),
      body("Agricultural production index data were obtained from the FAOSTAT Production Indices dataset (domain code: QI), published by the Food and Agriculture Organization of the United Nations. The gross production index measures the volume of agricultural production relative to the base period 2014\u20132016, which is set to 100. The data cover all primary agricultural commodities and are aggregated at the country level. Data were sourced separately for Western Europe (including France and Germany) and Southern Europe (including Italy and Spain) and combined prior to analysis. The series runs from 1990 to 2017 for the four countries in scope."),
      spacer(),
      body("A separate FAOSTAT extract was used to examine individual commodity-level production indices, enabling identification of the single highest-value commodity per country within each 5-year period. Fruit and vegetable production indices were also obtained as a separate sub-aggregate from the same FAOSTAT domain."),

      heading2("2.2 FAOSTAT Emissions Totals"),
      body("Country-level agricultural greenhouse gas emissions data were obtained from the FAOSTAT Emissions Totals dataset (domain code: GT). The dataset provides emissions estimates for three gases — methane (CH\u2084), carbon dioxide (CO\u2082), and nitrous oxide (N\u2082O) — sourced from FAO Tier 1 estimation methodology. Values are expressed in kilotonnes (kt). The time series runs from 1990 to 2021 for all four countries."),

      heading2("2.3 Sector-Level Emissions (2023)"),
      body("Sector-level emissions data for 2023 were assembled from multiple heterogeneous sources, as no single harmonised cross-country dataset was available at the required granularity. Germany's sector breakdown was obtained from the German Environment Agency (Umweltbundesamt, UBA) and covers CO\u2082 emissions only across the energy, industry, agriculture, LULUCF, and waste sectors. Italy's sector breakdown was obtained from Our World in Data (sourced from the Global Carbon Project) and covers CO\u2082 across nine sectors. France's and Spain's sector proportions were obtained from CITEPA (2024) and Statista (2023) respectively, and represent full GHG baskets rather than CO\u2082 alone."),
      spacer(),
      body("It should be noted that this cross-source heterogeneity introduces a comparability limitation: Germany and Italy figures represent CO\u2082 only, while France and Spain represent all GHGs. This is clearly flagged in the heatmap visualisation and in the interpretation section."),

      heading2("2.4 World Bank GDP (Supplementary)"),
      body("GDP data in constant 2015 US dollars were obtained from the World Bank Development Indicators API (indicator: NY.GDP.MKTP.KD) to support emissions intensity calculations. Country codes were matched using the UNSD M49 classification table."),

      // ── 3. Methodology ──────────────────────────────────────────────────
      pageBreak(),
      heading1("3. Methodology"),

      heading2("3.1 Agricultural Production Index"),
      body("The FAOSTAT Gross Production Index uses the Laspeyres formula, with international commodity prices in the 2014\u20132016 base period as weights. An index value above 100 indicates production above the base period average; below 100 indicates below. The western and southern European FAOSTAT files were concatenated and deduplicated prior to country-level filtering. Spain is absent from the gross production index series due to data unavailability in the source files."),
      spacer(),
      body("For the commodity-level analysis, all item-level production index values were averaged within 5-year bins (1990\u20131994, 1995\u20131999, etc.). The single commodity with the highest mean value within each bin was identified as the dominant item for that country-period combination."),

      heading2("3.2 Emissions Analysis"),
      body("Absolute emissions (kt) were plotted by gas type for each country over the period 1990\u20132021. An index series was constructed by expressing each year's emissions as a percentage of the 1990 baseline value, separately for each country-gas combination. This normalisation allows direct comparison of the rate of change across countries that differ substantially in absolute emission magnitudes."),
      spacer(),
      body("Percentage change from 1990 to the most recent available year (2021) was calculated as: ((V\u2082\u2080\u2082\u2081 \u2212 V\u2081\u2099\u2099\u2080) / V\u2081\u2099\u2099\u2080) \u00d7 100. An ordinary least squares linear slope was also fitted to the index series for each country-gas pair to characterise the average annual trend direction."),

      heading2("3.3 Sector-Level Analysis"),
      body("Sector proportions were computed by dividing each sector's absolute value by the country total. Where data were provided as proportions (France, Spain), they were renormalised to sum to 1.0 after excluding unmappable categories (Spain's 'Other' sector, representing 11.8% of the total, was excluded on this basis). All sector names were mapped to a canonical taxonomy to enable cross-country comparison in the heatmap visualisation."),

      heading2("3.4 Software"),
      body("All data processing and visualisation was performed in Python 3 using pandas for data manipulation and seaborn/matplotlib for plotting. The report was generated programmatically using the docx JavaScript library. Code is structured across modular files: config.py (shared constants), loaders.py (data ingestion), plot_utils.py (plotting helpers), ag_data.py, clean_dat.py, sectors.py (analysis scripts), and run_all.py (orchestration)."),

      // ── 4. Results ──────────────────────────────────────────────────────
      pageBreak(),
      heading1("4. Results"),

      heading2("4.1 Agricultural Gross Production Index"),
      body("Figure 1 shows the aggregate gross agricultural production index for France, Germany, and Italy from 1990 to 2017 (Spain is not available in this series). All three countries show relatively stable indices across the period, hovering close to or below 100 for most of the series before converging near the base period level by 2015\u20132017."),
      spacer(),
      ...figureImage("agricultural_gross_production_index.png", "Figure 1. Agricultural Gross Production Index (2014\u20132016 = 100) for France, Germany, and Italy, 1990\u20132017."),

      body("Table 1 summarises the index values at the start and end of the available series, together with the percentage change over the period. Spain, whose data are available in the broader commodity-level dataset, shows the strongest growth (+30.1%), consistent with the major expansion of its irrigated agriculture sector over this period. Italy shows the largest decline (-5.3%) among the three countries with full series data."),
      spacer(),
      buildAgTable(),
      caption("Table 1. Agricultural Gross Production Index: 1990 and 2017 values and percentage change."),
      spacer(),

      body("Figure 2 shows the fruit and vegetable production sub-index, which reveals more differentiated trajectories than the aggregate. Spain again shows strong growth, while France and Italy exhibit more varied patterns across the series."),
      spacer(),
      ...figureImage("fruit_veg_production_index.png", "Figure 2. Fruit and Vegetable Production Index (2014\u20132016 = 100) for selected countries, 1990\u20132017."),

      body("Figure 3 presents the dominant agricultural commodity (by average production index value) for each country within successive 5-year bins. France is consistently dominated by hemp across most of the period, reflecting its position as Europe's largest hemp producer. Italy shows horse meat as the top commodity for much of the 1990s and 2000s, with a shift to other commodities in later periods. Germany's dominant commodity rotates between linseed, currants, mixed grain, and soya beans, suggesting a more diversified commodity structure."),
      spacer(),
      ...figureImage("top_item_every_5_years_by_country.png", "Figure 3. Highest-value agricultural commodity per country by 5-year bin (mean production index value within bin)."),

      pageBreak(),
      heading2("4.2 GHG Emissions Trends"),
      body("Figure 4 presents absolute agricultural GHG emissions (kt) by gas for each country over 1990\u20132021. Germany consistently records the highest absolute CH\u2084 and N\u2082O emissions, reflecting the scale of its livestock sector, while France records the highest CO\u2082 emissions. Spain shows an upward trend across all three gases, in contrast to the declining or stable profiles of the other three countries."),
      spacer(),
      ...figureImage("fig1_emissions_intensity.png", "Figure 4. Agricultural GHG emissions (kt) by gas type, 1990\u20132021."),

      body("Figure 5 re-expresses the same data as an index relative to 1990, facilitating direct comparison of rates of change. The divergence between Spain and the other three countries is particularly clear in this view: Spain is the only country to show sustained increases in all three gases over the full period. Germany shows the steepest declines in CH\u2084 and N\u2082O."),
      spacer(),
      ...figureImage("fig2_emissions_index.png", "Figure 5. Agricultural GHG emissions index (1990 = 100) by gas type and country, 1990\u20132021."),

      body("Table 2 summarises the percentage change in each gas from 1990 to 2021. The most striking figure is Spain's CO\u2082 increase of +61.4%, which is substantially larger than any other country-gas combination. Germany's CH\u2084 reduction of \u221241.9% represents the single largest reduction."),
      spacer(),
      buildEmissionsTable(),
      caption("Table 2. Percentage change in agricultural GHG emissions (kt) from 1990 to 2021, by gas and country."),

      pageBreak(),
      heading2("4.3 Sector-Level Emissions Breakdown (2023)"),
      body("Figure 6 presents a heatmap of sector shares of emissions for 2023. Blank cells indicate that the sector either does not appear in the source data for that country or was not reported separately. The dominance of energy in Germany's CO\u2082 profile (84.4%) reflects the CO\u2082-only scope of the UBA data, which concentrates mass in the energy sector relative to a full GHG basket."),
      spacer(),
      ...figureImage("ghg_emissions_by_sector_heatmap.png", "Figure 6. Sector shares of GHG/CO\u2082 emissions, 2023. Note: Germany and Italy are CO\u2082-only; France and Spain represent full GHG baskets."),

      body("Table 3 presents the same data in tabular form. Transport is the largest sector for France (34.0%) and Spain (36.8%), consistent with the broader European pattern in GHG accounting. Italy's largest reported sector is Energy (23.8%), followed by Transport (28.8%). Germany's sectoral breakdown is dominated by Energy under the CO\u2082-only scope."),
      spacer(),
      buildSectorTable(),
      caption("Table 3. Sector shares of emissions (%), 2023. \u2014 indicates sector not reported or not mappable for that country."),

      // ── 5. Interpretation ───────────────────────────────────────────────
      pageBreak(),
      heading1("5. Interpretation"),

      heading2("5.1 Spain as a Structural Outlier"),
      body("Across both the agricultural production and emissions analyses, Spain consistently diverges from the pattern shown by France, Germany, and Italy. Its agricultural gross production index grew by approximately 30% between 1990 and 2017, while the other three countries were broadly flat or slightly declining. Over the same broad period, its agricultural CO\u2082 emissions grew by 61.4% and its CH\u2084 by 12.8%, in contrast to declines recorded elsewhere."),
      spacer(),
      body("This pattern is consistent with the well-documented expansion of Spain's irrigated horticultural and fruit sector \u2014 particularly in Andaluc\u00eda and the Levante \u2014 which has transformed it into one of Europe's largest producers of fresh produce for export. Irrigation-intensive production and associated land use change, machinery use, and cold-chain logistics contribute to higher CO\u2082 emissions per unit of output than the traditional dryland systems they have partly displaced."),

      heading2("5.2 Germany's Emissions Reductions"),
      body("Germany shows the steepest percentage reductions in CH\u2084 and N\u2082O among the four countries \u2014 gases primarily associated with livestock (enteric fermentation and manure management) and synthetic fertiliser use. These reductions likely reflect structural changes in the livestock sector following German reunification in 1990, which resulted in significant contraction of East German livestock numbers, as well as subsequent efficiency gains in fertiliser application and manure management technologies over the following three decades."),
      spacer(),
      body("The counterintuitive increase in Germany's CO\u2082 from agricultural land (+31.0%) warrants caution in interpretation: the FAOSTAT CO\u2082 series for agricultural land captures soil carbon dynamics and land use change rather than combustion emissions, and can be subject to revision as estimation methodologies improve."),

      heading2("5.3 France and Italy: Stable but Diverging"),
      body("France and Italy both show broadly flat agricultural production indices and modest emissions reductions over the period. France's production index is dominated at the commodity level by hemp, reflecting a niche but large-volume industrial crop rather than mainstream food production \u2014 this artefact of the index weighting methodology means caution is required when interpreting the commodity-level results as representative of France's overall agricultural structure."),
      spacer(),
      body("Italy's shift away from horse meat and towards chick peas and mushrooms as the highest-value commodity in the production index in later periods likely reflects a combination of declining horse meat consumption and the growing importance of plant-based proteins in Italian food systems, consistent with broader dietary shifts in Southern Europe."),

      heading2("5.4 Data Comparability Limitations"),
      body("The sector-level analysis is the most limited in terms of cross-country comparability. The mixture of CO\u2082-only (Germany, Italy) and full-GHG (France, Spain) sources means that sector shares are not directly comparable across countries. In particular, agriculture's share appears very small for Germany (0.4%) because agricultural methane and nitrous oxide \u2014 which are the dominant agricultural GHGs \u2014 are excluded from the CO\u2082-only UBA series. A fully comparable analysis would require a harmonised dataset such as the UNFCCC National Inventory Submissions or the EEA's UNFCCC-aligned reporting."),

      // ── 6. Conclusion ───────────────────────────────────────────────────
      pageBreak(),
      heading1("6. Conclusion"),
      body("This report has analysed agricultural production indices and GHG emissions trends for Italy, Spain, France, and Germany over the period 1990\u20132023. The main findings are as follows."),
      spacer(),
      body("First, Spain stands out as the single country showing sustained growth in both agricultural output and GHG emissions, driven by the expansion of its irrigated horticultural sector. This growth trajectory contrasts sharply with the broadly flat or declining emissions and production indices seen in the other three countries."),
      spacer(),
      body("Second, Germany has achieved the largest reductions in livestock-related emissions (CH\u2084, N\u2082O) among the four countries, likely reflecting post-reunification structural change in its livestock sector as well as subsequent efficiency improvements."),
      spacer(),
      body("Third, the commodity-level analysis reveals interesting artefacts of the production index methodology \u2014 notably the dominance of hemp in France's index \u2014 that underscore the importance of examining sub-aggregate data alongside country totals."),
      spacer(),
      body("Fourth, the sector-level emissions breakdown is limited in comparability due to the use of heterogeneous data sources. A priority for future work would be to replace the current patchwork of national sources with a harmonised cross-country dataset, ideally the UNFCCC National Inventory Submissions processed through a common pipeline."),
      spacer(),
      body("Future extensions of this analysis could incorporate: (i) emissions intensity metrics (emissions per unit of agricultural output), combining the production index and emissions data already available; (ii) expansion to a broader set of European countries using the existing extensible code architecture; and (iii) alignment of the emissions series with the sector breakdown to provide a consistent multi-dimensional view of each country's agricultural emissions profile over time."),

    ]
  }]
});

// ---------------------------------------------------------------------------
// Write
// ---------------------------------------------------------------------------
Packer.toBuffer(doc).then(buffer => {
  fs.writeFileSync("/home/daniel/PycharmProjects/PythonProject/european_ghg_agriculture_report.docx", buffer);
  console.log("Report written successfully.");
});
