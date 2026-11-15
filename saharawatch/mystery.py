"""A staged investigation whose evidence is frozen when its envelope is opened."""
import json

import numpy as np
import pandas as pd
import plotly.graph_objects as go

from .briefing import recent_assessment, deficit_footprint
from .data import country_weights, regional_series
from .plots import style, CYAN, AMBER, map_figure


VERDICTS = [
    'Persistent rainfall deficit',
    'Multi-year rainfall deficit',
    'No multi-year rainfall deficit',
    'Insufficient data',
]
LIMITS = ('This case assesses historical precipitation only. It does not establish agricultural '
          'or hydrological drought, its causes, or future conditions. Country averages use coarse '
          '2.5° cells and do not describe every town or farm.')


def build_mystery(annual, feature, metadata, end, bstart, bend, weighting):
    """Keep observations, figures and provenance together, independent of later filters."""
    weights = country_weights(annual, feature, weighting)
    full = regional_series(annual, weights)
    assessment = recent_assessment(full, end, 3, bstart, bend)
    footprint = deficit_footprint(annual, weights, end, 3, bstart, bend)
    baseline = full.sel(year=slice(bstart, bend)).dropna('year')
    mean = float(baseline.mean()) if baseline.size >= 10 else np.nan
    first = end-2
    history = full.sel(year=slice(int(full.year.min()), end))
    figure = go.Figure(go.Scatter(x=history.year.values, y=history.values,
                                 mode='lines+markers', line_color=CYAN, name='Annual rainfall'))
    if np.isfinite(mean):
        figure.add_hline(y=mean, line_dash='dot', line_color=AMBER,
                         annotation_text=f'{bstart}–{bend} baseline mean')
    figure.add_vrect(x0=first-.5, x1=end+.5, fillcolor=AMBER, opacity=.12, line_width=0)
    figure.update_yaxes(title_text='Annual rainfall (mm)')
    history_json = style(figure, 330).to_json()

    observed = full.reindex(year=np.arange(first, end+1))
    cumulative = (observed-mean).cumsum('year', skipna=False)
    figure = go.Figure(go.Bar(x=observed.year.values, y=cumulative.values,
                              marker_color=[AMBER if v < 0 else CYAN for v in cumulative.values],
                              name='Accumulated departure'))
    figure.add_hline(y=0, line_color=CYAN)
    figure.update_xaxes(dtick=1)
    figure.update_yaxes(title_text='Cumulative departure from baseline (mm)')
    cumulative_json = style(figure, 300).to_json()

    base = annual.sel(year=slice(bstart, bend))
    recent = annual.reindex(year=np.arange(first, end+1))
    valid = (base.count('year') >= 10) & (recent.count('year') == 3) & (weights > 0)
    expected = (base.mean('year')*3).where(valid)
    total = recent.sum('year', skipna=False).where(valid)
    figure = map_figure(total-expected, 'Three-year accumulated rainfall departure', 'mm',
                        f'{first}–{end} vs. {bstart}–{bend}', feature=feature,
                        diverging=True, observed=total, expected=expected)
    figure.update_layout(map=dict(center=dict(lat=31.5, lon=-7), zoom=3.5))
    return dict(country='Morocco', period=f'{first}–{end}', baseline=f'{bstart}–{bend}',
                end=end, baseline_start=bstart, baseline_end=bend, weighting=weighting,
                source=f'GPCP {metadata["version"]} / NOAA PSL', source_sha256=metadata['sha256'],
                coverage=f'{metadata["start"]} to {metadata["end"]}',
                source_note=metadata.get('attributes', {}).get('data_comment', metadata.get('data_comment', '')),
                assessment=assessment, footprint=footprint,
                annual_data=json.loads(pd.DataFrame({'year':history.year.values,
                                                     'precipitation_mm':history.values}).to_json(orient='records')),
                charts=[history_json, cumulative_json, figure.to_json()])
