# SaharaWatch: the next wow features

Session 2 | 2026-11-15

## Recommendation

**Build a playable climate mystery first. Add a satellite before/after reveal for the strongest visual moment. Build a trend robustness explorer for the feature that makes SaharaWatch intellectually distinctive.**

The rainfall time machine and connected evidence board already exist, so they are foundations for these ideas rather than proposed additions.

## Current value and evidence

SaharaWatch combines historical MENA rainfall investigation with a detective's casebook interface. It already has country briefings, annual anomaly playback, a connected evidence board, guided cases, SPI, statistical diagnostics, point temperature observations, and illustrated reports.

Reviewed: `README.md`, `app.py`, `saharawatch/guided.py`, `saharawatch/time_machine.py`, `saharawatch/briefing.py`, and the previous strategy session. In particular, guided cases currently expose live charts and computed interpretations; notebook hypotheses currently compare a selected direction against the trend. Neither constitutes the staged, prediction-before-reveal experience proposed below.

No audience interviews or usage analytics were available. Priorities are product judgments for an inferred audience of demo visitors, learners, and Space Apps reviewers. Effort estimates are relative, not delivery commitments.

## Medium opportunities

### 1. Playable climate mysteries — best next build

**Experience:** Open a sealed case titled “One wet year: has the dry spell ended?” Make a guess before seeing the evidence. Uncover three clues: the annual record, accumulated deficits, and the spatial footprint. Pin the clues, choose a verdict, then reveal the calculated assessment and its limitations.

**Wow moment:** The visitor solves something. The charts become evidence with a purpose, and the cork board becomes the record of their reasoning.

**First version:** One Morocco case, four short stages, existing data and calculations, deterministic narration. Freeze the case's data snapshot and filters so its wording stays consistent. Allow “insufficient evidence” as a valid conclusion. Keep the larger explorer accessible after the reveal.

**Impact / reach / frequency:** High for first-time visitors; medium repeat use unless new cases are added. Strong differentiation through the existing detective theme. A curated case library can compound over time.

**Effort:** Medium. **Score:** Must do.

### 2. “Does this conclusion hold up?” — strongest scientific signature

**Experience:** Select a country and see a triangular heatmap of analysis start and end years. Each square shows the estimated trend for that window. Hover to inspect sample size and uncertainty; click to open the corresponding investigation. Switch inference methods to examine classification sensitivity separately from trend magnitude.

**Wow moment:** A dramatic drying claim visibly weakens or persists as the visitor changes the period. Statistical choices become something they can inspect.

**First version:** Country series only, minimum supported record length, cached calculations, and a clear legend separating trend direction from evidence strength. Do not turn the fraction of significant windows into a probability that a claim is true; overlapping windows are dependent and the exploration involves many comparisons.

**Impact / reach / frequency:** High for analytical users; medium for casual visitors. Useful in every investigation. Easy to imitate visually, but careful interpretation strengthens the product's identity.

**Effort:** Medium. **Score:** Must do after the playable case.

### 3. A rainfall fingerprint for every place

**Experience:** Render each country's complete-year anomalies as a compact strip of colored tiles, one per year. Hover reveals the observation and reference period. Select two countries and their strips align; choose a dry episode and it lights up across all countries.

**Wow moment:** Decades of climate history become a recognizable visual signature. Visitors can spot shared dry periods without navigating multiple charts.

**First version:** Eleven country rows, fixed anomaly scale, visible missing data, shared baseline, click-through to existing charts. Describe simultaneous anomalies without suggesting they establish a shared cause.

**Impact / reach / frequency:** Broad reach, useful on each visit, moderate differentiation. Reuses the current observations and makes a strong screenshot.

**Effort:** Low–medium. **Score:** Strong; best visual quick win.

## Massive opportunities

### 4. Satellite evidence reveal — biggest visual wow

**Experience:** Choose a vetted episode, then drag a before/after divider over satellite imagery while a synchronized rainfall chart marks the image dates. A magnifier reveals the image source and acquisition date.

**Wow moment:** The abstract rainfall investigation connects to a visible landscape.

NASA GIBS provides satellite-data visualizations through standard services; its catalog can support investigation of candidate layers. Availability, dates, and useful detail must be checked for the chosen location before committing to a story. [NASA GIBS overview](https://nasa-gibs.github.io/gibs-api-docs/), [visualization catalog](https://nasa-gibs.github.io/gibs-api-docs/available-visualizations/).

**First version:** One carefully checked location with two comparable, same-season images. Cache an attributed pair for a dependable demo where source terms permit. Show the coarse rainfall cell outline alongside the detailed image. Image changes may have several causes; the interface should ask what other evidence would be needed.

**Impact / reach / frequency:** Very high demo appeal and broad reach; occasional use until the case collection grows. Curation is the lasting asset.

**Effort:** Medium for a curated pair; high for unrestricted exploration. **Score:** Strong strategic bet.

### 5. Follow a dry episode through the Earth system

**Experience:** Three synchronized tracks show rainfall, soil moisture, and vegetation condition over a common supported period. Scrubbing the timeline reveals agreement, disagreement, and possible delays between the indicators.

**Wow moment:** Visitors investigate how different observations tell different parts of the same episode instead of assuming rainfall alone describes its impacts.

NASA describes SMAP/SMOS-based soil moisture datasets and NASA ARSET includes precipitation, soil moisture, vegetation, and temperature among drought-monitoring observations. These establish relevant candidate sources, not a validated MENA integration. [NASA soil moisture data](https://earth.gsfc.nasa.gov/hydro/data/nasa-usda-global-soil-moisture-data), [NASA ARSET training](https://appliedsciences.nasa.gov/sites/default/files/2024-07/Drought_Part4_FINAL.pdf).

**First version:** One region and episode, quality-screened observations, explicit overlapping coverage, consistent spatial aggregation, and separate indicator baselines. Treat lags as descriptive; do not animate a causal chain or synthesize an unvalidated risk score.

**Impact / reach / frequency:** Potentially transformative for deeper investigations. High integration cost and scientific interpretation risk. Curated, reproducible multi-source cases compound in value.

**Effort:** High. **Score:** Explore after the core experience is validated.

## Small gems

### 6. “Find my next clue”

After a country briefing, suggest one transparent investigative action: inspect the driest observed year, compare an adjacent country, inspect spatial disagreement, or test a different period. Explain the numerical trigger and open the existing view in one click. No language model is necessary.

**Why powerful:** Helps visitors navigate a dense app and makes it feel responsive to what they discover. High reach and frequency, modest differentiation. **Effort:** Low–medium. **Score:** Strong.

### 7. A case postcard worth sharing

Export a compact, polished image: case title, country outline, rainfall fingerprint, one computed finding, assessment period, uncertainty, and source. Give it the existing parchment-and-ink treatment. Build it from pinned evidence so it remains reproducible.

**Why powerful:** Visitors leave with an artifact they can show someone. This adds a concise visual format to existing illustrated reports. Start with download; reproducible links require deployed hosting and state restoration. **Effort:** Low–medium. **Score:** Strong.

## Recommended priority

| Order | Feature | Main payoff |
| --- | --- | --- |
| 1 | Playable climate mystery | Makes the detective identity functional and engaging |
| 2 | Rainfall fingerprints | Fast visual impact using existing observations |
| 3 | Trend robustness explorer | Distinctive scientific interaction |
| 4 | One satellite evidence reveal | Memorable visual centerpiece |
| 5 | Next-clue suggestions and postcards | Better discovery and sharing |
| Explore | Multiple Earth-system indicators | Expands the scientific scope |

For a presentation, the ideal sequence is: **make a guess → reveal the rainfall history → inspect a satellite pair → challenge the conclusion → export the case.** Each step should work without an external request during the demo once its evidence is prepared.

## Validation and next steps

- Prototype one staged mystery before expanding the case library. Check whether a first-time visitor can finish it and explain the finding and one limitation within roughly two minutes.
- Test whether fingerprints help visitors find an interesting episode faster than the existing atlas alone.
- Check useful imagery coverage before selecting a satellite case; no suitable imagery pair was verified in this session.
- Validate robustness-view wording with a scientific reviewer before treating it as a teaching tool.
- Keep generic chatbots, decorative 3D globes, and unsupported climate forecasts out of the first iteration: the strongest opportunity here is the investigation experience.

No application code was changed or deployment performed.
