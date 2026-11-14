# SAHARAWATCH
## Full Project Specification — NASA Space Apps Challenge 2026

**Project:** SaharaWatch — MENA Drought & Climate Trend Intelligence Platform  
**Challenge:** Be An Earth System Trend Detective!  
**Development approach:** AI-assisted development using OpenAI Codex  
**Target:** Functional, visually impressive hackathon MVP  
**Priority:** Scientific correctness, interactive exploration, visual quality, and reliability

---

# 1. Project Vision

Build **SaharaWatch**, an interactive geospatial analytics platform that allows users to investigate historical drought-related changes across the Middle East and North Africa (MENA).

The platform should transform real Earth observation data into accessible, meaningful insights, helping users understand:

- Where precipitation is increasing or decreasing.
- How rainfall patterns have evolved over decades.
- Which regions experience unusually dry or wet conditions.
- How the intensity and frequency of precipitation deficits have changed.
- Whether observed long-term trends are statistically significant.
- How different geographic regions compare.
- How changes in precipitation may relate to other Earth system variables, such as temperature, when such data is available.

The project is not intended to predict future droughts.

It is an **exploratory environmental intelligence platform** for detecting, visualizing, comparing, and explaining historical environmental trends.

## Central Question

**How have drought-related precipitation patterns changed across MENA, where are these changes most pronounced, and are the detected trends statistically significant?**

## Intended Users

- Environmental scientists and researchers.
- University students.
- Climate educators.
- Policymakers exploring regional patterns.
- Journalists investigating environmental changes.
- General users interested in climate and water resources.

Users should not need programming or statistical knowledge to investigate environmental changes.

---

# 2. Relationship to NASA's Challenge

The application must address the core requirements of "Be An Earth System Trend Detective!"

| Challenge question | SaharaWatch solution |
|---|---|
| What is changing? | Precipitation and, optionally, additional environmental variables |
| Where is it changing? | Interactive map covering MENA |
| How is it changing? | Historical time-series visualization |
| How much is it changing? | Trend slopes, anomalies and relative changes |
| Is it significant? | Statistical hypothesis testing and confidence intervals |

The application must be a **reusable interactive tool**, rather than a static report about drought.

Users must be able to change locations, temporal windows, and analysis indicators and receive newly calculated results.

Precipitation is the flagship use case. Design the internal architecture so additional measured Earth science variables can be added without rebuilding the dashboard.

---

# 3. Geographic Scope

## 3.1 Initial Study Area

Cover the Middle East and North Africa using an approximate geographic bounding box:

- Minimum latitude: 10° N
- Maximum latitude: 43° N
- Minimum longitude: 18° W
- Maximum longitude: 63° E

This rectangle is an initial computational extent, not a precise definition of MENA.

It includes locations outside the intended study region.

## 3.2 Geographic Navigation

Support several levels of exploration.

**Level 1: MENA overview**

Display spatial precipitation patterns across the entire region.

**Level 2: Country investigation**

Allow users to select countries, initially:

- Morocco
- Algeria
- Tunisia
- Libya
- Egypt
- Mauritania
- Saudi Arabia
- Jordan
- Iraq
- Iran
- United Arab Emirates

Additional countries can be supported if boundary data is available.

**Level 3: Grid-cell investigation**

Allow users to examine the time series for an individual geographic grid cell.

The map's spatial precision must reflect the actual dataset resolution.

Do not present 2.5° grid cells as high-resolution city, province, or agricultural-field observations.

## 3.3 Geographic Data Integrity

Implement two clear geographic selection modes:

1. **Grid-cell selection:** Choose the nearest precipitation grid cell to a coordinate.
2. **Country aggregation:** Aggregate grid-cell values within a country mask, using latitude-appropriate area weights.

If country masking is unavailable, provide clearly labeled rectangular regional averages instead.

Do not represent a rectangular bounding-box average as an exact national average.

For country averages, mask cells using country boundaries and use cosine-of-latitude weighting as an approximate grid-cell area correction.

For fractional boundary cells, document the limitations of a center-point inclusion mask.

---

# 4. Data Sources

## 4.1 Primary Dataset: GPCP Monthly Precipitation

Use the Global Precipitation Climatology Project (GPCP) monthly precipitation dataset distributed through NOAA Physical Sciences Laboratory.

**Official dataset URL:**

https://psl.noaa.gov/thredds/fileServer/Datasets/gpcp/precip.mon.mean.nc

**Dataset information:**

https://www.psl.noaa.gov/data/gridded/data.gpcp.html

Specifications:

| Property | Value |
|---|---|
| Format | NetCDF |
| Coverage | Global |
| Spatial resolution | 2.5° × 2.5° |
| Temporal resolution | Monthly |
| Historical coverage | 1979 onward |
| Variable | `precip` |
| Units | mm/day |
| Dimensions | time × latitude × longitude |
| Approximate file size | 20 MB |

This dataset combines satellite observations and gauge-based precipitation information.

The downloaded file must be used as the primary precipitation data source.

**Important:** The dataset is distributed by NOAA and uses a multi-source precipitation analysis associated with the NASA-supported GPCP effort. Describe its origin accurately. Do not misleadingly call every value a direct NASA satellite measurement.

## 4.2 Data Loading Requirements

The application should:

1. Locate the dataset in `data/raw/precip.mon.mean.nc`.
2. Validate that it is a readable NetCDF file.
3. Inspect available dimensions and variables.
4. Identify the precipitation variable using metadata where possible.
5. Read the precipitation units.
6. Convert longitude coordinates from 0–360° to −180–180°.
7. Sort geographic coordinates.
8. Subset the dataset to MENA.
9. Filter the requested historical period.
10. Handle missing and invalid values.
11. Cache processed data for subsequent analysis.

Use **xarray**, **NumPy**, and **Pandas**.

Do not download or process the global dataset on every dashboard interaction.

## 4.3 Default Time Period

Default analysis window:

**January 2001 – December 2024**

Allow users to select other periods available in the downloaded dataset.

Validate that:

- Start year is before end year.
- Required months are available.
- A minimum reasonable amount of data exists for trend testing.
- Results from incomplete years are handled appropriately.

## 4.4 Unit Conversion

GPCP's precipitation variable represents average monthly precipitation rate in mm/day.

For each month, calculate:

`monthly_precipitation_mm = precipitation_mm_per_day × days_in_month`

Annual rainfall totals must be calculated by summing monthly precipitation totals across complete years.

Annual temperature, if introduced later, must be averaged rather than summed.

Never mix precipitation rates and precipitation accumulation without explicit unit conversion.

## 4.5 Additional Earth Science Variable

The architecture should accommodate additional datasets through a generic variable registry.

Recommended secondary variable:

**Near-surface air temperature (`T2M`) from NASA POWER/MERRA-2**, provided the data can be obtained and aligned with precipitation spatially and temporally.

Do not fetch hundreds of POWER requests on dashboard startup.

Implement this variable only after the GPCP workflow is complete.

If temperature data is not available, the application must remain functional using precipitation.

Do not invent, synthesize, or substitute environmental measurements to create the appearance of multi-variable support.

---

# 5. Core Application Experience

The interface should resemble a polished environmental intelligence platform rather than a basic university exercise.

## 5.1 Main Dashboard Layout

Use a widescreen layout.

**Header**

- SaharaWatch logo or wordmark.
- Subtitle: "Earth System Trend Intelligence for MENA."
- Dataset source indicator.
- Historical period indicator.
- Data resolution information.

**Sidebar / Control Panel**

- Geographic region selector.
- Country selector.
- Environmental variable selector.
- Analysis indicator selector.
- Start and end year controls.
- Statistical significance threshold.
- Baseline period settings.
- Reset filters button.

**Main Content**

- Large interactive map.
- Summary metric cards.
- Historical time-series chart.
- Trend analysis.
- Seasonal and anomaly visualizations.
- Regional comparison.
- Scientific interpretation.
- Dataset and methodology information.

Use consistent layout, typography, spacing, and color systems.

## 5.2 Visual Design

Suggested style:

- Dark navy background.
- Deep blue surfaces.
- Cyan highlights for interactive controls.
- Amber/orange for dry anomalies.
- Blue/teal for wet anomalies.
- Clear statistical uncertainty indicators.
- Large, legible numerical summaries.

Avoid arbitrary decorative effects.

The map and time-series visualizations should be the visual focus.

Use tasteful animations or transitions only if they do not hurt performance.

Use actual data in every scientific visualization. Never insert artificial drought statistics for visual impact.

---

# 6. Feature 1 — Interactive Drought Trend Map

This is the centerpiece of SaharaWatch.

## 6.1 Objective

Display geographic differences in precipitation behavior across MENA.

Users should immediately be able to identify regions with:

- Increasing precipitation.
- Decreasing precipitation.
- Unusually dry conditions.
- Unusually wet conditions.
- Statistically significant trends.
- Insufficient observations.

## 6.2 Map Indicators

Allow the user to choose between:

**A. Mean Annual Precipitation**

Show annual precipitation climatology in mm/year.

**B. Long-Term Precipitation Trend**

Show the fitted linear trend of annual precipitation totals in mm/decade.

**C. Relative Precipitation Trend**

Show trend magnitude as a percentage of the historical mean per decade.

Use caution where mean rainfall approaches zero.

**D. Precipitation Anomaly**

Show the difference between precipitation in a selected year and the historical baseline average.

**E. Standardized Anomaly**

Display how unusual precipitation conditions are relative to historical variability.

Label these as standardized anomalies, not SPI.

**F. Statistical Significance**

Show grid cells with statistically significant long-term trends.

## 6.3 Map Rendering

Use Plotly-based geographic maps or an equivalent robust geospatial library.

Because the dataset is a relatively coarse regular grid, prioritize accurate representation of its cells.

Choose grid-based rendering or another method that preserves actual data resolution.

Do not interpolate values merely to make the map look more detailed.

The interface must support:

- Zooming.
- Panning.
- Geographic tooltips.
- Color-scale legends.
- Switching indicators.
- Country navigation.

For map interaction, prefer direct grid-cell selection if reliably supported.

If map clicks require unstable libraries or JavaScript workarounds, implement selection through a region/country dropdown and coordinate lookup first.

## 6.4 Grid Cell Tooltip

A tooltip should display:

- Grid-cell latitude and longitude.
- Selected indicator value.
- Units.
- Analysis period.
- Trend significance, if relevant.

Never show fabricated results.

## 6.5 Statistical Maps

Significance should not be inferred merely from the intensity of the trend color.

Provide a separate significance layer or clearly defined marking convention.

Explain that individual grid-cell hypothesis tests across a large map involve a multiple-comparisons problem.

If feasible, provide a False Discovery Rate correction using Benjamini–Hochberg.

Clearly distinguish raw p-values from corrected significance results.

---

# 7. Feature 2 — Historical Rainfall Explorer

## 7.1 Objective

Allow users to see how precipitation has changed over time for the selected location or region.

## 7.2 Time-Series Chart

Plot:

- Historical annual precipitation totals.
- A linear trend line.
- An optional multi-year moving average.
- A baseline reference line.

The chart should show:

- X-axis: Year.
- Y-axis: Annual precipitation in mm.
- Interactive hover information.
- Clear legend.
- Units.
- Selected region name.

Allow monthly and annual views.

For monthly data, preserve the distinction between seasonality and long-term changes.

## 7.3 Trend Summary

Calculate and display:

- Total years analyzed.
- Mean annual precipitation.
- Linear trend slope in mm/year.
- Linear trend slope in mm/decade.
- Relative trend in %/decade, when meaningful.
- Estimated total fitted change over the selected period.
- p-value.
- Confidence interval.
- Statistical significance classification.

## 7.4 Scientific Interpretation

Generate deterministic text based on statistical results.

Example template:

"Between {start_year} and {end_year}, annual precipitation in {region} exhibited an estimated trend of {slope} mm per decade. The associated p-value was {p_value}. Under the selected significance threshold, this trend is classified as {significance_status}."

Add contextual interpretation only when supported.

A statistically non-significant trend must not be described as proof that there is no environmental change.

---

# 8. Feature 3 — Precipitation Anomaly Detection

## 8.1 Objective

Help users recognize unusually dry or wet periods compared with historical conditions.

## 8.2 Baseline

Default reference period:

**2001–2020**

Allow configurable baseline periods where enough data exists.

Use a consistent baseline for temporal comparisons.

For monthly analysis, compare the current month against the historical average for the same calendar month.

For annual analysis, compare annual precipitation totals against historical annual totals.

## 8.3 Anomaly Formula

`anomaly_mm = observed_precipitation_mm - baseline_mean_mm`

Relative anomaly:

`anomaly_pct = 100 × anomaly_mm / baseline_mean_mm`

Avoid relative anomaly calculations when the denominator is zero or too small to give a meaningful result.

## 8.4 Visualization

Display:

- Historical precipitation anomaly bar chart.
- Negative anomalies in dry-condition colors.
- Positive anomalies in wet-condition colors.
- A horizontal zero reference.
- Tooltip showing observed, expected, and anomalous precipitation.

## 8.5 Annual Anomaly Map

Allow users to select a year.

For each cell:

1. Calculate the selected year's precipitation.
2. Calculate baseline average annual precipitation.
3. Calculate the difference.
4. Display the geographic distribution of anomalies.

This should make it possible to visually investigate historic dry years across MENA.

---

# 9. Feature 4 — Drought Indicators

## 9.1 MVP Indicator

Start with precipitation anomalies and standardized anomalies.

The standardized anomaly should be clearly defined as:

`z = (observed - historical_mean) / historical_std`

Use appropriate baseline grouping.

Do not compute standardized anomalies when variance is zero or baseline sample sizes are insufficient.

**A standardized anomaly is not equivalent to a formal SPI calculation.**

## 9.2 Advanced Indicator: SPI

If time permits, implement the Standardized Precipitation Index.

Support:

- SPI-3: Short-term precipitation conditions.
- SPI-12: Longer-term precipitation conditions.

A valid implementation requires:

- Accumulated precipitation over the selected time scale.
- Suitable probability distributions.
- Calendar-month-specific fitting.
- Handling zero precipitation values.
- Sufficient historical observations.
- Validation against reference implementations.

Use a reputable scientific Python implementation if available and compatible.

Do not substitute ordinary z-scores and call them SPI.

If the available historical baseline or implementation cannot support a scientifically defensible SPI result, hide this feature and retain precipitation anomalies instead.

## 9.3 Drought Frequency

Optionally calculate the number or percentage of years or months showing a deficit beyond a clearly defined threshold.

If using standardized anomalies, label the metric:

"Frequency of severe negative precipitation anomalies."

Do not call it official drought frequency unless a recognized drought-index definition is applied.

---

# 10. Feature 5 — Statistical Trend Detection

## 10.1 Main Method

Use linear regression on annual precipitation totals.

Implement using SciPy or equivalent.

Model:

`P(t) = β0 + β1 × t + ε`

Where:

- `P(t)` is annual precipitation.
- `β0` is the intercept.
- `β1` is the linear trend.
- `t` is the year.
- `ε` is residual variation.

Report trend slopes in mm/decade.

## 10.2 Significance Testing

Default significance threshold:

`alpha = 0.05`

Display:

- Estimated trend slope.
- p-value.
- 95% confidence interval.
- Significance result.
- Sample size.

Use descriptive labels:

- Statistically significant increase.
- Statistically significant decrease.
- No statistically significant trend detected.
- Insufficient data.

## 10.3 Statistical Limitations

Climate and precipitation data may violate assumptions of independent regression residuals.

At minimum:

- Aggregate monthly data to annual totals for initial trend analysis.
- Document that ordinary least-squares p-values are exploratory.
- Avoid overconfident scientific claims.

If feasible, assess serial correlation and use an appropriate robust inference approach.

For larger-scale maps, consider multiple-testing correction.

## 10.4 Additional Trend Methods

Optional:

- Theil–Sen robust slope estimator.
- Mann–Kendall trend test with appropriate autocorrelation treatment.

These should not delay the basic implementation.

The central goal is a transparent, reproducible statistical workflow.

---

# 11. Feature 6 — Regional Comparison

## 11.1 Objective

Allow the user to compare environmental trends across different regions.

For example:

- Morocco vs. Algeria.
- Morocco vs. Tunisia.
- North Africa vs. Arabian Peninsula.
- Two selected geographic grid cells.

## 11.2 Comparison Dashboard

Display two regions side by side.

For each region, show:

- Mean annual precipitation.
- Linear trend.
- Statistical significance.
- Recent annual anomaly.
- Historical chart.

Provide a shared-axis comparison when both regions have the same units.

Offer normalized anomalies for comparing geographically different precipitation climates.

## 11.3 Interpretation

The application should identify:

- Whether both regions have trends in the same direction.
- Which has the larger absolute trend.
- Which has a larger relative trend, when meaningful.
- Whether each individual trend is statistically significant.

Do not claim that the two regional trends differ significantly unless an explicit statistical test of their difference has been performed.

---

# 12. Feature 7 — Guided Investigation

Create a section called:

**"Explore a Climate Mystery"**

This helps users who don't know where to start.

Provide preset investigations such as:

**Investigation A: Is Morocco Becoming Drier?**

Automatically select Morocco and display its historical precipitation trend, anomalies, and significance results.

**Investigation B: Different Regions, Different Trends**

Compare selected areas of Morocco and Algeria or Tunisia.

**Investigation C: Detect Historical Dry Periods**

Let users select a year and see precipitation anomalies across MENA.

**Investigation D: Where Are Rainfall Trends Strongest?**

Show a map ranking grid cells by the absolute magnitude of their fitted precipitation trends.

These investigations must use live calculations from the loaded dataset.

Do not hardcode numerical conclusions.

---

# 13. Feature 8 — Interpretation and Explainability

Every major visualization should have an accompanying explanation.

Prefer deterministic explanations based on computed metrics.

Use clear statements such as:

"The selected grid cell exhibits a negative linear precipitation trend over the analyzed period."

"Although the estimated slope is negative, the available data do not provide strong enough statistical evidence to classify the trend as significant at the selected threshold."

"The highlighted region experienced precipitation below its historical reference average during the selected year."

Do not equate:

- Correlation with causation.
- Dry climate with drought.
- One dry year with a long-term drying trend.
- A significant precipitation trend with proof of climate change attribution.
- Non-significance with proof of no change.

An AI language model is optional.

If added later, it should receive structured statistical outputs and explain them without modifying or inventing measurements.

The MVP must not depend on paid AI APIs.

---

# 14. Technology Stack

## Frontend and Application Framework

**Streamlit**

Reason:

- Fast development.
- Native Python integration.
- Interactive controls.
- Easy cloud deployment.
- Appropriate for a hackathon.

## Visualization

- Plotly for charts and geographic maps.
- Streamlit components for dashboard controls.

## Data Processing

- xarray.
- NumPy.
- Pandas.
- netCDF4 or h5netcdf.

## Statistical Analysis

- SciPy.
- statsmodels, if robust standard errors or additional methods are implemented.

## Geographic Processing

- GeoJSON country boundaries.
- GeoPandas and Shapely only if required.
- Avoid introducing complex GIS frameworks when simpler solutions are adequate.

## Testing

- pytest.

## Deployment

- Streamlit Community Cloud.

No Kubernetes, Kafka, Spark, Airflow, authentication system, or complex microservices are needed.

---

# 15. Proposed Project Architecture

Use a modular and maintainable directory structure.

```text
saharawatch/
│
├── app.py
│
├── requirements.txt
├── README.md
├── .gitignore
│
├── data/
│   ├── raw/
│   │   └── precip.mon.mean.nc
│   │
│   └── processed/
│       └── mena_precipitation.nc
│
├── src/
│   ├── __init__.py
│   │
│   ├── data/
│   │   ├── __init__.py
│   │   ├── loader.py
│   │   ├── preprocessing.py
│   │   └── geographic.py
│   │
│   ├── analysis/
│   │   ├── __init__.py
│   │   ├── trends.py
│   │   ├── anomalies.py
│   │   ├── statistics.py
│   │   └── drought.py
│   │
│   ├── visualization/
│   │   ├── __init__.py
│   │   ├── maps.py
│   │   └── charts.py
│   │
│   ├── components/
│   │   ├── __init__.py
│   │   ├── sidebar.py
│   │   ├── metrics.py
│   │   └── explanations.py
│   │
│   └── config.py
│
├── scripts/
│   ├── prepare_data.py
│   └── validate_data.py
│
├── tests/
│   ├── test_preprocessing.py
│   ├── test_trends.py
│   └── test_anomalies.py
│
└── assets/
    └── styles.css
```

This is a suggested structure, not an excuse to create unnecessary abstraction.

Only create modules actually required by the implementation.

---

# 16. Data Processing Pipeline

Implement the following processing sequence.

## Stage 1 — Load

Read the NetCDF file using xarray.

Validate coordinates, dimensions, variable names, units, and available dates.

## Stage 2 — Geographic Preprocessing

Normalize longitude.

Select MENA bounding box.

Apply country or regional masks when appropriate.

Ensure latitude and longitude are correctly sorted.

## Stage 3 — Temporal Preprocessing

Select the requested time period.

Convert monthly mean precipitation rates into accumulated monthly precipitation.

Identify missing months.

Calculate annual totals only from complete annual records, unless an explicitly documented alternative is justified.

## Stage 4 — Derived Indicators

Compute:

- Historical mean precipitation.
- Annual rainfall totals.
- Monthly anomalies.
- Annual anomalies.
- Standardized anomalies.
- Linear trends.
- Statistical significance.

## Stage 5 — Geographic Aggregation

Compute regional statistics using appropriate spatial weights and masks.

Do not blindly average every cell in a country bounding box.

## Stage 6 — Visualization

Pass preprocessed arrays and analytical results to visualization functions.

Avoid recalculating all trends during cosmetic interface interactions.

## Stage 7 — Caching

Cache:

- Loaded datasets.
- Geographic subsets.
- Commonly requested aggregated series.
- Long-term trend grids.

Use Streamlit caching carefully, distinguishing cached resources from cached computed data.

Do not cache mutable dataset objects in ways that cause state corruption.

---

# 17. Performance Requirements

The application must remain responsive on an ordinary laptop.

Target behavior:

- Load the processed MENA dataset without excessive memory usage.
- Avoid repeated global NetCDF parsing.
- Reuse calculated trend grids.
- Avoid unnecessary requests to external services.
- Run core analysis without a GPU.
- Make dropdown and chart interactions responsive.

Prefer vectorized NumPy/xarray calculations over Python loops for grid-wide analysis.

A global GPCP dataset of roughly 20 MB is manageable on a standard laptop; do not introduce distributed computing.

---

# 18. Data Validation and Testing

Implement automated tests for the most important scientific calculations.

## Required Tests

**Unit conversion**

Verify that a monthly precipitation rate of 2 mm/day for a 30-day month becomes 60 mm.

**Annual aggregation**

Verify that twelve complete monthly totals sum to the correct annual precipitation.

**Incomplete records**

Verify that incomplete annual records are excluded or flagged appropriately.

**Longitude conversion**

Verify correct conversion from 0–360° to −180–180°.

**Linear trends**

Create a synthetic time series with a known positive slope and confirm the regression returns the expected result.

**No-trend example**

Test a constant or near-constant series and ensure the application does not return misleading significance values.

**Anomalies**

For a known baseline mean, verify positive and negative deviations.

**Missing values**

Ensure NaNs and fill values do not produce false zeros or invalid trend results.

**Geographic selection**

Ensure coordinates resolve to the intended grid cell.

**Regional aggregation**

Verify weighted aggregation on a small synthetic grid.

## Validation Requirements

Before considering the project complete, confirm:

- No invented precipitation data.
- Correct precipitation units.
- Correct geographic coordinates.
- Correct temporal filtering.
- Correct baseline handling.
- Scientifically reasonable trend output.
- Working charts.
- Visible data attribution.
- Honest uncertainty descriptions.

---

# 19. Deployment and Reproducibility

The project must be runnable locally using:

```bash
pip install -r requirements.txt
streamlit run app.py
```

Document Python version and dependencies.

The raw dataset should not be assumed to exist on every user's machine.

Implement an optional setup script that:

1. Checks whether the dataset exists.
2. Downloads it from the official source if missing.
3. Verifies that the downloaded file is usable.
4. Prepares the MENA subset.

Do not start large remote downloads without notifying the user through the interface.

For deployment, either:

- Include a compact processed MENA NetCDF file, provided repository hosting permits it, or
- Download and cache the source dataset during initial application setup.

Do not require NASA Earthdata credentials for the GPCP MVP.

Include proper dataset attribution in the README and application footer.

---

# 20. Interface Sections

The finished application should have these sections:

## A. Overview

High-level MENA precipitation map and summary.

## B. Trend Explorer

Interactive geographic trend map, time-series chart, slopes, p-values, and uncertainty.

## C. Drought & Anomalies

Historical precipitation deficits, standardized anomalies, and optional SPI.

## D. Compare Regions

Side-by-side comparison of two selected locations or regions.

## E. About the Science

Dataset details, analytical methods, statistical limitations, resolution, and source attribution.

These can be implemented as Streamlit tabs rather than separate pages.

---

# 21. MVP Priorities

The hackathon deadline is extremely close, so implementation must be phased.

## Phase 1 — Mandatory MVP

Implement before anything else:

- Load real GPCP precipitation data.
- Extract MENA.
- Convert precipitation to correct units.
- Display an interactive geographic precipitation map.
- Allow geographic selection.
- Display historical annual precipitation.
- Fit a linear trend.
- Report slope, p-value, and statistical significance.
- Allow users to change the analysis period.
- Provide meaningful data-source attribution.

The project must run end-to-end after Phase 1.

## Phase 2 — High-Impact Improvements

Once Phase 1 works:

- Precipitation anomaly map.
- Country-level exploration.
- Regional comparison.
- Statistical significance map.
- Improved visual styling.
- Guided investigations.
- Clear uncertainty explanations.

## Phase 3 — Optional Enhancements

Only if time remains:

- Formal SPI drought indicators.
- Temperature as a second Earth science variable.
- Advanced statistical tests.
- Export investigation summaries.
- AI-assisted natural-language interpretation.
- Additional explanatory visualizations.

Do not sacrifice a complete, reliable MVP to partially implement advanced features.

---

# 22. Scientific and Ethical Requirements

The system must be transparent about its data and limitations.

**Important constraints:**

1. The application is a historical analysis tool, not a drought forecasting system.
2. Precipitation deficits are indicators relevant to meteorological drought, not comprehensive measures of agricultural or hydrological drought.
3. GPCP's 2.5° grid cannot support highly localized claims about cities or individual farms.
4. Statistical significance does not establish causality.
5. A non-significant result does not prove a variable is unchanged.
6. Results near zero historical precipitation need special handling.
7. Downloaded data may contain missing values or provisional observations.
8. Dataset versions and reference periods must be documented.
9. Country and regional results must reflect the actual geographical aggregation method.
10. The interface must not display fabricated measurements, conclusions, or scientific certainty.

---

# 23. README Requirements

Create a professional GitHub README explaining:

- Project overview.
- NASA Space Apps challenge alignment.
- The environmental problem.
- Why MENA matters as a case study.
- Core features.
- Technology stack.
- Dataset provenance.
- Installation instructions.
- Data preparation instructions.
- How to run locally.
- Statistical methodology.
- Known limitations.
- Screenshots.
- Potential future improvements.

Describe GPCP attribution accurately.

If additional NASA datasets are integrated, document them separately.

---

# 24. Acceptance Criteria

The MVP is considered complete when:

- [ ] The app starts successfully.
- [ ] A real historical precipitation dataset loads.
- [ ] MENA geographic coverage is correct.
- [ ] A map displays actual precipitation values or derived indicators.
- [ ] A user can select a location or region.
- [ ] The selected location has a historical precipitation chart.
- [ ] The chart changes when the user changes the time period.
- [ ] A statistical trend is calculated correctly.
- [ ] The trend's magnitude and significance are visible.
- [ ] Units and scientific limitations are communicated.
- [ ] The application remains responsive.
- [ ] No synthetic data is presented as real climate evidence.
- [ ] README and source attribution are complete.

The enhanced submission should also include:

- [ ] Interactive anomaly visualization.
- [ ] Regional comparisons.
- [ ] Statistical significance mapping.
- [ ] Guided climate investigations.
- [ ] A second real Earth science variable, if feasible.

---

# 25. Instructions for Codex

You are acting as a senior full-stack Python developer, geospatial data engineer, and scientific computing specialist.

Your responsibility is to build SaharaWatch as a functional, reproducible, visually polished application for the NASA Space Apps Challenge 2026.

**Development rules:**

1. Inspect the existing project before making changes.
2. Check whether `precip.mon.mean.nc` is already present.
3. Do not replace the supplied dataset with synthetic data.
4. Verify the NetCDF schema and units rather than assuming them.
5. Build the working data-processing pipeline first.
6. Develop the Streamlit dashboard incrementally.
7. Prioritize scientific correctness over visual complexity.
8. Write modular, readable, maintainable Python.
9. Use type hints where useful.
10. Implement tests for statistical and precipitation calculations.
11. Avoid unnecessary frameworks and infrastructure.
12. Do not require paid services.
13. Handle missing files and malformed data gracefully.
14. Keep geographic and statistical terminology accurate.
15. Run tests and validate the actual application after major changes.
16. Do not claim a feature works unless it has been tested.
17. Do not silently replace a failed operation with mock values.
18. Keep all visualizations connected to real calculations.
19. Document important implementation decisions.
20. Favor finishing the MVP over adding partially working features.

**Execution order:**

First, inspect the dataset and implement reliable loading and preprocessing.

Second, implement annual rainfall aggregation and trend analysis with tests.

Third, create the geographic map, location controls, and historical chart.

Fourth, implement anomalies and regional comparisons.

Fifth, improve visual design, documentation, and deployment.

Finally, implement remaining optional features only if the core project is stable.

**Final objective:**

Deliver an end-to-end working SaharaWatch application that allows users to investigate how precipitation patterns across MENA have changed over time, identify the magnitude and spatial distribution of those changes, and evaluate their statistical significance using real Earth science data.

The application should be visually compelling, scientifically responsible, easy to explore, and demonstrable during a short hackathon presentation.

**Begin implementation immediately. Do not stop after producing a plan. Implement Phase 1 first, test it, then proceed to subsequent phases as time and project stability permit.**
