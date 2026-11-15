"""Six evidence-led cases and reproducible, calculated quiz questions."""
import json

import numpy as np
import pandas as pd
import plotly.graph_objects as go

from .analysis import annual_anomalies
from .data import country_weights, regional_series
from .guided import rank_trend_cells
from .inference import analyze_trend, inference_grid, slope_difference
from .mystery import build_mystery, VERDICTS, LIMITS
from .briefing import assessment_text
from .plots import history_figure, anomaly_figure, map_figure, style, CYAN, AMBER
from .satellite import load_satellite_pair, rainfall_context


CASES = {
    'morocco': dict(number='001', title='Is Morocco becoming drier?', difficulty='Beginner', minutes=4,
                    question='Does the long-term rainfall record support a drying trend?',
                    hints=['Compare the fitted slope with annual variability.', 'Check the p-value against α.',
                           'Try another analysis period. Does the conclusion hold?']),
    'compare': dict(number='002', title='Across the border', difficulty='Intermediate', minutes=5,
                    question='Do Morocco and Algeria tell the same rainfall story?',
                    hints=['Use a common period and baseline.', 'Absolute rainfall and standardized anomalies answer different questions.',
                           'Two different slopes need a formal difference test.']),
    'anomaly': dict(number='003', title='The dry-year files', difficulty='Beginner', minutes=4,
                    question='How unusual was the selected year?',
                    hints=['Compare the year with its own reference climate.', 'Check the baseline sample size and variability.',
                           'A single dry year cannot establish a long-term trend.']),
    'trends': dict(number='004', title='Follow the strongest trail', difficulty='Advanced', minutes=6,
                   question='Does the largest trend also have strong statistical evidence?',
                   hints=['Separate magnitude from significance.', 'Check FDR flags as well as raw p-values.',
                          'The rectangular ranking includes ocean cells.']),
    'recent': dict(number='005', title='Has the rain returned?', difficulty='Beginner', minutes=4,
                   question='Did a better year erase a three-year rainfall deficit?',
                   hints=['Improvement and recovery to the baseline are different.', 'Add the departures across all three years.',
                          'A national mean can hide spatial differences.']),
    'satellite': dict(number='006', title='What changed from space?', difficulty='Intermediate', minutes=5,
                      question='What do the satellite views show, and what remains unproven?',
                      hints=['Check the acquisition dates and platforms.', 'Compare imagery detail with rainfall-cell support.',
                             'Clouds, overpass conditions and land management can affect appearance.']),
}


def case_title(key):
    case = CASES[key]
    return f'Case {case["number"]} / {case["title"]}'


def clean_json(value):
    """Normalize numpy values and nonfinite observations for portable exports."""
    return json.loads(pd.Series(value).to_json())


def question(title, prompt, options, correct, explanation, chart=None, evidence='', misconception=''):
    feedback = {}
    for option in options:
        if option == correct:
            continue
        if option == 'Insufficient data':
            feedback[option] = 'The displayed observations support an answer for this quantity. Check the stated sample and calculation before withholding a conclusion.'
        elif correct == 'Insufficient data':
            feedback[option] = 'The required observations or reference variability are unavailable. A direction, category or threshold result cannot be inferred from the gaps.'
        elif option in ('Decrease', 'Increase', 'Flat'):
            feedback[option] = 'Read the sign of the fitted slope, then assess uncertainty separately. The annual ups and downs are a different quantity.'
        elif option == 'Smallest p-value':
            feedback[option] = 'A p-value concerns evidence against the null model. This ranking uses absolute rainfall trend magnitude.'
        elif option == 'Highest drought risk':
            feedback[option] = 'Rainfall change alone cannot rank drought risk; vulnerability, exposure and other indicators are missing.'
        else:
            feedback[option] = misconception or 'Compare this choice with the observation and the supported answer below; avoid extending the claim beyond what was measured.'
    return dict(title=title, prompt=prompt, options=options, correct=correct,
                explanation=explanation, chart=chart.to_json() if chart is not None else None,
                evidence=evidence, feedback=feedback, misconception=misconception or
                'Distinguish the measured quantity from the broader claim. The evidence above supports the stated answer only.')


def trend_answer(result, alpha):
    if not np.isfinite(result['p']):
        return 'Insufficient data'
    if result['p'] >= alpha:
        return 'No statistically significant direction detected'
    return 'Decrease' if result['slope'] < 0 else 'Increase'


def country_series(annual, countries, name, weighting):
    if name not in countries:
        raise ValueError(f'{name} boundaries are unavailable.')
    return regional_series(annual, country_weights(annual, countries[name], weighting))


def build_quiz(key, annual, monthly, countries, metadata, start, end, bstart, bend,
               alpha, method, weighting, observation_year, complete_years):
    """Every numerical answer is calculated once from the opened attempt's data."""
    context = dict(case_id=key, title=case_title(key), location='Morocco', period=f'{start}–{end}',
                   baseline=f'{bstart}–{bend}', alpha=alpha, inference_method=method,
                   country_weighting=weighting, observation_year=observation_year,
                   source=f'GPCP {metadata["version"]} / NOAA PSL', source_sha256=metadata['sha256'],
                   source_status=metadata.get('attributes', {}).get('data_comment', ''), limits=LIMITS,
                   annual_data=[], clues=[])
    if key == 'satellite':
        manifest, _ = load_satellite_pair()
        frame, summary, chart, cell = rainfall_context(monthly, manifest)
        context.update(location='Casablanca region · curated satellite pair', period='2023-02-12 / 2024-02-19',
                       satellite_manifest=manifest, rainfall_cell=list(cell),
                       rainfall_data=json.loads(frame.to_json(orient='records', date_format='iso')))
        context['clues'] = [
            question('Read the image labels', 'Were both views acquired by the same satellite?',
                     ['Yes, both are Terra', 'No: Aqua before, Terra after', 'The platforms are unknown'],
                     'No: Aqua before, Terra after',
                     'The manifest records Aqua MODIS on 12 February 2023 and Terra MODIS on 19 February 2024.',
                     evidence='Before: 2023-02-12 · Aqua MODIS. After: 2024-02-19 · Terra MODIS. Same February season and identical geographic extent.',
                     misconception='Same-season, aligned images can still differ in satellite and overpass conditions.'),
            question('Connect the rainfall record', 'Does the rainfall chart measure conditions at individual farms?',
                     ['Yes, its detail matches the imagery', 'No, it represents a 2.5° GPCP cell', 'It measures reservoir volume'],
                     'No, it represents a 2.5° GPCP cell',
                     f'The rainfall cell is centered at {cell[0]:.2f}° N, {cell[1]:.2f}° E. The six full months before each image total '
                     f'{summary[0]["precipitation_mm"]} and {summary[1]["precipitation_mm"]} mm (None means unavailable).', chart,
                     misconception='Detailed imagery does not increase the spatial resolution of a separate rainfall dataset.'),
            question('Set the boundary of the claim', 'Do visual differences establish that rainfall alone caused the landscape change?',
                     ['Yes, the images prove the cause', 'No, other evidence and explanations are needed', 'No landscape comparison is possible'],
                     'No, other evidence and explanations are needed',
                     'True-color images supply visual context. Clouds, haze, overpass conditions and land management also affect appearance. '
                     'Monthly totals cannot resolve rainfall timing within the acquisition day.',
                     evidence=manifest['limits'], misconception='Association and visual contrast do not establish causation.'),
        ]
        return clean_json(context)

    if key == 'recent':
        case = build_mystery(annual, countries['Morocco'], metadata, complete_years[-1], bstart, bend, weighting)
        r = case['assessment']
        last = r['annual_mm'][-1]
        mean = r.get('baseline_annual_mean_mm', np.nan)
        relation = 'Insufficient data' if last is None or not np.isfinite(mean) else 'Below baseline' if last < mean else 'At or above baseline'
        balance = 'Insufficient data' if not np.isfinite(r['departure_mm']) else 'Below expectation' if r['departure_mm'] < -1e-9 else 'At or above expectation'
        context.update(period=case['period'], annual_data=case['annual_data'], recent_assessment=r)
        specs = [
            ('A year is only one piece of the story', 'How does the latest year compare with the baseline annual mean?',
             ['Below baseline', 'At or above baseline', 'Insufficient data'], relation,
             f'Latest annual rainfall: {last} mm; baseline mean: {mean:.1f} mm. Improvement from a previous year does not imply recovery.'),
            ('Keep a running balance', 'Where does the three-year rainfall balance end?',
             ['Below expectation', 'At or above expectation', 'Insufficient data'], balance,
             f'Observed accumulation: {r["total_mm"]:.1f} mm; expected: {r["expected_mm"]:.1f} mm; departure: {r["departure_mm"]:.1f} mm.'),
            ('Cross-examine the national average', 'Which assessment fits the three-year national record?',
             VERDICTS, r['status'], assessment_text('Morocco', r)),
        ]
        context['clues'] = [question(*spec, chart=go.Figure(json.loads(case['charts'][i]))) for i, spec in enumerate(specs)]
        return clean_json(context)

    if key == 'trends':
        grid = inference_grid(annual.sel(year=slice(start, end)), method)
        ranks, frame = rank_trend_cells(grid, alpha)
        winner = frame.iloc[0] if not frame.empty else None
        answer = 'Insufficient data' if winner is None else 'Yes' if winner.fdr_significant else 'No'
        chart = map_figure(ranks, 'Absolute trend rank', 'Rank', f'{start}–{end}', pvalues=grid.sel(stat='p'))
        chart.data[0].reversescale = True
        detail = ('No cells have a supported trend estimate.' if winner is None else
                  f'Rank 1: {winner.latitude:.2f}° N, {winner.longitude:.2f}° E; '
                  f'{winner.trend_mm_decade:.2f} mm/decade; raw p={winner.raw_p:.4g}; FDR flag={bool(winner.fdr_significant)}.')
        context.update(location='MENA rectangular grid · includes ocean', ranked_cells=json.loads(frame.to_json(orient='records')))
        context['clues'] = [
            question('Follow the magnitude', 'What earns rank 1?', ['Largest absolute trend', 'Smallest p-value', 'Highest drought risk'],
                     'Largest absolute trend', detail+' Ranking is based on the absolute fitted rainfall change, not statistical evidence or impacts.', chart),
            question('Challenge the evidence', 'Does the rank-1 cell pass the selected map FDR threshold?', ['Yes', 'No', 'Insufficient data'],
                     answer, detail+f' FDR classification uses α={alpha}; the raw p-value is a different quantity.', evidence=detail),
            question('Check the scope', 'Does a top-ranked cell establish the highest national drought risk?',
                     ['Yes', 'No, trend magnitude is not drought risk', 'Only if its p-value is small'],
                     'No, trend magnitude is not drought risk', 'The ranking includes ocean cells. Drought risk also needs exposure, vulnerability and additional environmental evidence.'),
        ]
        return clean_json(context)

    full = country_series(annual, countries, 'Morocco', weighting)
    series = full.sel(year=slice(start, end))
    fit = analyze_trend(series.year.values, series.values, alpha, method)
    anomalies, z, base = annual_anomalies(full, bstart, bend)
    context['annual_data'] = json.loads(pd.DataFrame({'year':full.year.values, 'precipitation_mm':full.values}).to_json(orient='records'))
    if key == 'morocco':
        direction = 'Insufficient data' if not np.isfinite(fit['decade']) else 'Decrease' if fit['decade'] < 0 else 'Increase' if fit['decade'] > 0 else 'Flat'
        detail = f'{method} estimate: {fit["decade"]:.2f} mm/decade; p={fit["p"]:.4g}; α={alpha}; n={fit["n"]}.'
        context['clues'] = [
            question('Read the fitted direction', 'Which direction does the fitted rainfall slope point?', ['Decrease', 'Increase', 'Flat', 'Insufficient data'],
                     direction, detail+' A fitted direction alone does not establish statistical evidence.', history_figure(series, fit, float(base))),
            question('Weigh the uncertainty', 'What does the selected trend test support?',
                     ['Decrease', 'Increase', 'No statistically significant direction detected', 'Insufficient data'],
                     trend_answer(fit, alpha), detail+' Nonsignificance does not prove that rainfall is unchanged.',
                     evidence=detail, misconception='Separate the sign of an estimate from the uncertainty of that estimate.'),
            question('Consider another explanation', 'Does this trend test establish the cause of any rainfall change?',
                     ['Yes, it attributes the change', 'No, attribution needs additional evidence'],
                     'No, attribution needs additional evidence', 'A historical trend test does not separate possible causes or predict future rainfall.'),
        ]
    elif key == 'compare':
        other = country_series(annual, countries, 'Algeria', weighting)
        pair = other.sel(year=slice(start, end))
        other_fit = analyze_trend(pair.year.values, pair.values, alpha, method)
        magnitudes = [fit['decade'], other_fit['decade']]
        magnitude_answer = ('Insufficient data' if not np.isfinite(magnitudes).all() else 'Equal within numerical precision'
                            if np.isclose(abs(magnitudes[0]), abs(magnitudes[1])) else 'Morocco' if abs(magnitudes[0]) > abs(magnitudes[1]) else 'Algeria')
        chart = go.Figure()
        for name, data, color in [('Morocco', series, CYAN), ('Algeria', pair, AMBER)]:
            chart.add_trace(go.Scatter(x=data.year.values, y=data.values, name=name, line_color=color))
        chart.update_yaxes(title_text='Annual rainfall (mm)')
        difference = slope_difference(series, pair, alpha)
        answer = 'Insufficient data' if not np.isfinite(difference['p']) else 'A significant linear slope difference' if difference['p'] < alpha else 'No significant linear slope difference detected'
        context.update(location='Morocco and Algeria', paired_test=difference)
        context['clues'] = [
            question('Compare the fitted magnitudes', 'Which country has the larger absolute fitted trend magnitude?',
                     ['Morocco', 'Algeria', 'Equal within numerical precision', 'Insufficient data'], magnitude_answer,
                     f'Morocco: {fit["decade"]:.2f}; Algeria: {other_fit["decade"]:.2f} mm/decade. Magnitude is descriptive.', style(chart, 330)),
            question('Choose the right comparison', 'Do two different fitted slopes alone prove a significant difference?', ['Yes', 'No, use a paired difference test'],
                     'No, use a paired difference test', 'The paired test uses common-year first-minus-second rainfall and retains covariance between regions.'),
            question('Read the paired test', 'What does the paired Newey–West HAC test support?',
                     ['A significant linear slope difference', 'No significant linear slope difference detected', 'Insufficient data'], answer,
                     f'Common-year linear slope difference: {difference["decade"]:.2f} mm/decade; p={difference["p"]:.4g}; α={alpha}; n={difference["n"]}. '
                     'The test concerns linear slopes, independently of the method selected for each individual series.'),
        ]
    elif key == 'anomaly':
        value, standardized = float(anomalies.sel(year=observation_year)), float(z.sel(year=observation_year))
        answer = 'Insufficient data' if not np.isfinite(value) else 'Below baseline' if value < 0 else 'At or above baseline'
        severity = 'Insufficient data' if not np.isfinite(standardized) else 'Yes' if standardized <= -1.5 else 'No'
        context['clues'] = [
            question('Open the annual file', f'Was {observation_year} below its baseline annual mean?',
                     ['Below baseline', 'At or above baseline', 'Insufficient data'], answer,
                     f'{observation_year} rainfall departure: {value:.1f} mm relative to {bstart}–{bend}.',
                     anomaly_figure(anomalies.sel(year=series.year), False, series, base)),
            question('Put the anomaly in context', 'Does its standardized anomaly meet the −1.5 threshold?', ['Yes', 'No', 'Insufficient data'], severity,
                     f'Standardized anomaly: {standardized:.2f} σ. The threshold is a descriptive negative-anomaly screen, not an official drought declaration or SPI.'),
            question('Avoid the one-year trap', 'Can one unusually dry year establish a long-term drying trend?', ['Yes', 'No, examine the multi-year record'],
                     'No, examine the multi-year record', 'An anomaly describes a departure in one year; a trend describes change across a record.'),
        ]
    else:
        raise ValueError('Unknown case.')
    return clean_json(context)
