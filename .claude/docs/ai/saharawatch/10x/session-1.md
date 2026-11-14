# SaharaWatch: additions with a wow effect

Session 1 | 2026-11-14

## Current value

SaharaWatch investigates historical MENA rainfall using GPCP observations, with point temperature exploration through NASA POWER. Its distinctive visual language is a detective's casebook. Existing features already include guided mysteries, country briefings, statistical diagnostics, paired comparisons, SPI, evidence pins, and illustrated report exports.

Evidence reviewed: `README.md`, `app.py`, `saharawatch/plots.py`, `assets/dashboard.png`. No usage analytics or user interviews were available; audience appeal and priorities below are product judgments. Existing uncommitted implementation work was left untouched.

## Massive opportunity

### Satellite evidence investigations

Pair selected rainfall episodes with carefully curated satellite imagery of the same area. Let visitors drag a before/after divider and then inspect the rainfall record. NASA Worldview/GIBS supplies historical imagery, subject to each layer's coverage: https://github.com/nasa-gibs/worldview

Why: links an abstract record to a visible place. High effort; strong exploratory bet. Imagery dates, seasons, clouds, and spatial support must be explicit. A visual difference alone does not establish rainfall causation. Begin with one vetted location and episode rather than an unrestricted imagery search.

## Medium opportunities

### 1. Rainfall time machine — highest priority

Animate annual anomaly maps through complete years from the available record, with play/pause, a year scrubber, and a synchronized selected-country timeline. Keep the baseline, color scale, and geographic extent fixed across frames; show gaps and provisional status. Clicking an interesting year opens the existing investigation tools.

Why: makes spatial variability and chronology immediately legible while reusing the existing data. Moderate effort; highest recommended priority. Annual evolution must not be presented as proof of a trend.

### 2. A short narrated case — strong

Extend an existing Morocco mystery into a four-step presentation: question, history, recent episode, verdict. Each step highlights the corresponding map or chart and ends with a computed conclusion, including inconclusive outcomes. Use templated text grounded in calculated values; a language model is unnecessary.

Why: gives first-time visitors a clear path through an otherwise dense workspace. Moderate effort. Measure whether visitors finish and can explain the conclusion.

### 3. Evidence relationship board — strong

Arrange existing notebook clues as connected cards: hypothesis, observed deficit, longer-term trend, uncertainty, conclusion. User-selected links mean supports, challenges, or provides context. Reuse immutable evidence snapshots and source metadata.

Why: makes the detective theme functional and creates a memorable presentation artifact. Moderate effort. Visual links must not imply causal relationships or automatically assign certainty.

## Small gems

### Prediction before reveal — high priority

Ask visitors whether they expect rainfall to be rising, falling, or unclear before revealing the selected location's record. Compare the guess with the computed evidence, preserving inconclusive results. Low effort; adds participation to existing cases.

### Shareable case card — strong

Extend current reports with a compact image containing location, time period, one key calculated finding, a mini-chart, uncertainty, and attribution. Start with image download; URL restoration needs explicit state encoding and an available deployment. Low to moderate effort; complements rather than duplicates illustrated reports.

## Recommended priority

1. Build the rainfall time machine for immediate visual impact.
2. Add prediction-before-reveal to an existing case for quick engagement.
3. Build one short guided presentation around that case.
4. Explore one curated satellite comparison after confirming coverage and interpretation.
5. Consider the evidence board when notebook usage supports the investment.

## Assumptions and validation

- Demo visitors and Space Apps reviewers are an inferred audience from the README, not confirmed users.
- Proposed effort levels are relative estimates, not delivery commitments.
- Validate that a first-time visitor can identify the main finding and its limitations after a one-minute demonstration.
- Check animation performance in Streamlit/Plotly with fixed-scale frames before expanding scope.
- No implementation or deployment was requested or performed.
