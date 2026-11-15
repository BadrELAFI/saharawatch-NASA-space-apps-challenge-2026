"""A staged investigation whose evidence is frozen when its envelope is opened."""
import copy
import html
import json

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from .briefing import recent_assessment, assessment_text, deficit_footprint
from .data import country_weights, regional_series
from .plots import style, CYAN, AMBER, map_figure


VERDICTS = [
    'Persistent rainfall deficit',
    'Multi-year rainfall deficit',
    'No multi-year rainfall deficit',
    'Insufficient data',
]
STAGES = ['Your prediction', 'The annual record', 'The accumulated evidence',
          'The geographic footprint', 'Your verdict', 'Case assessment']
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


def restart_mystery():
    for key in list(st.session_state):
        if key.startswith('mystery_'):
            del st.session_state[key]


def move_stage(stage):
    st.session_state['mystery_stage'] = stage


def pin_mystery_clue(index):
    case = st.session_state['mystery_case']
    titles = ['The annual record', 'The accumulated evidence', 'The geographic footprint']
    # Partial clues must not reveal the final assessment through the notebook.
    evidence = [
        'Inspect annual variability and compare the shaded three-year period with the fixed baseline mean.',
        ('The final bar is the sum of annual departures over the case period. '
         'A rising final segment can coexist with a negative accumulated balance.'),
        ('Cell departures compare each included cell with its own baseline; '
         'a national mean can conceal geographic differences.'),
    ]
    snapshot = dict(location='Morocco · playable mystery', evidence_kind='playable mystery',
                    period=case['period'], baseline=case['baseline'],
                    source=case['source'], source_sha256=case['source_sha256'], coverage=case['coverage'],
                    source_status=case['source_note'], scientific_limits=LIMITS,
                    country_weighting=case['weighting'], hypothesis=st.session_state['mystery_prediction_saved'],
                    status=titles[index], assessment=evidence[index], notes='',
                    trend_mm_decade='Not assessed in this case', p_value='Not assessed',
                    confidence_interval='Not assessed', inference_method='Descriptive precipitation comparison',
                    annual_data=copy.deepcopy(case['annual_data']),
                    chart_json={f'mystery_clue_{index+1}':case['charts'][index]})
    clues = st.session_state.setdefault('clues', [])
    if snapshot not in clues:
        clues.append(snapshot)


def render_playable_mystery(annual, countries, metadata, years, bstart, bend, weighting):
    st.markdown('### Case 005 / Has the rain returned?')
    st.write('A better year can look like the end of a dry spell. What does the full evidence say? '
             'Make a prediction, uncover three clues, and decide whether Morocco’s three-year rainfall total shows a deficit.')
    case = st.session_state.get('mystery_case')
    if case is None:
        st.caption(f'Sealed envelope · Morocco · {years[-1]-2}–{years[-1]} · '
                   f'baseline {bstart}–{bend} · {weighting} weighting')
        st.write('Your question: is rainfall over these three years below the amount expected from the baseline? '
                 'The case uses the latest three complete calendar years, independently of the analysis-period slider.')
        with st.form('mystery_open_form'):
            prediction = st.radio('Before opening the envelope, what do you expect?',
                                  ['A three-year rainfall deficit', 'No three-year rainfall deficit',
                                   'I need more evidence'], index=None, key='mystery_prediction')
            opened = st.form_submit_button('Break the seal & reveal clue 1',
                                           disabled='Morocco' not in countries, type='primary')
        if 'Morocco' not in countries:
            st.info('This case needs the Morocco boundary. Other investigations remain available below.')
        if opened:
            if prediction is None:
                st.warning('Record a prediction, including “I need more evidence”, before opening the case.')
            else:
                try:
                    case = build_mystery(annual, countries['Morocco'], metadata,
                                         years[-1], bstart, bend, weighting)
                except ValueError as exc:
                    st.warning(f'The case could not be opened: {exc}')
                    return
                st.session_state.update(mystery_case=case, mystery_stage=1,
                                        mystery_prediction_saved=prediction)
                st.rerun()
        return

    stage = st.session_state['mystery_stage']
    st.html(f'<div class="mystery-dossier"><p class="eyebrow">Envelope opened / Morocco · '
            f'{html.escape(case["period"])}</p><h3>{html.escape(STAGES[stage])}</h3>'
            f'<p>Your first impression: {html.escape(st.session_state["mystery_prediction_saved"])}</p></div>')
    st.progress(min(stage, 4)/4, text=f'{min(stage, 3)} / 3 clues revealed · '
                + ('assessment revealed' if stage == 5 else 'verdict recorded' if stage == 4 and 'mystery_verdict_saved' in st.session_state else 'follow the evidence'))
    st.caption(f'Frozen case · baseline {case["baseline"]} · {case["weighting"]} weighting · '
               f'{case["source"]}. Sidebar changes do not alter an open case. Restart to use new settings.')
    if case['source_note']:
        st.caption('Source status: '+case['source_note'])

    if stage in (1, 2, 3):
        prompts = [
            ('Clue 1 / A year is only one piece of the story',
             'The shaded interval is your case period. Compare each year with the dotted baseline. '
             'Did rainfall improve? Is improvement the same as returning to the baseline?'),
            ('Clue 2 / Keep a running balance',
             'Each bar adds another year’s departure from the baseline mean. '
             'Below zero means the rainfall received so far is below the baseline expectation. '
             'An improving year does not necessarily erase the earlier deficit.'),
            ('Clue 3 / Cross-examine the national average',
             'Rust cells received less rainfall than their own three-year baseline expectation; '
             'green cells received more. Blank cells have insufficient observations or are outside the country mask.'),
        ]
        title, prompt = prompts[stage-1]
        st.markdown('#### '+title)
        st.write(prompt)
        st.plotly_chart(go.Figure(json.loads(case['charts'][stage-1])), width='stretch',
                        theme=None, key=f'mystery_chart_{stage}')
        if stage == 2:
            st.dataframe(pd.DataFrame({'Year':case['assessment']['annual_years'],
                                       'Observed rainfall (mm)':case['assessment']['annual_mm']}),
                         hide_index=True, width='stretch')
        if stage == 3:
            footprint = case['footprint']
            if np.isfinite(footprint['deficit_area_pct']):
                st.write(f'{footprint["deficit_area_pct"]:.1f}% of the valid weighted country area had a deficit; '
                         f'valid spatial coverage: {footprint["coverage_pct"]:.1f}%.')
            else:
                st.info('Insufficient spatial coverage to describe the deficit footprint.')
        st.button('Pin this clue to Field notebook', key=f'mystery_pin_{stage}',
                  on_click=pin_mystery_clue, args=(stage-1,))
        if any(clue.get('chart_json', {}).get(f'mystery_clue_{stage}') == case['charts'][stage-1]
               for clue in st.session_state.get('clues', [])):
            st.caption('Clue pinned. Find it on the connected evidence board in Field notebook.')
    elif stage == 4:
        st.write('Choose the statement supported by all three clues. Persistent means every assessed year '
                 'was below the baseline mean; a multi-year deficit means the total was below expectation '
                 'but at least one year was not below the mean. “No multi-year deficit” does not mean every year was wet.')
        with st.form('mystery_verdict_form'):
            verdict = st.radio('What is your verdict?', VERDICTS, index=None, key='mystery_verdict')
            submitted = st.form_submit_button('Submit verdict & unseal the assessment', type='primary')
        if submitted:
            if verdict is None:
                st.warning('Choose a verdict before revealing the assessment.')
            else:
                st.session_state.update(mystery_verdict_saved=verdict, mystery_stage=5)
                st.rerun()
    else:
        assessment = case['assessment']
        matched = st.session_state['mystery_verdict_saved'] == assessment['status']
        st.markdown('#### '+assessment['status'])
        st.write(assessment_text('Morocco', assessment))
        if matched:
            st.success('Your verdict matches the calculated assessment. The evidence supports this description of the period.')
        else:
            st.info(f'You chose “{st.session_state["mystery_verdict_saved"]}”. '
                    'Compare it with the calculated assessment above; revising a hypothesis is part of the investigation.')
        st.write('Your initial prediction: **'+st.session_state['mystery_prediction_saved']+'**')
        st.write('What remains open? A recent rainfall balance does not answer whether there is a long-term trend. '
                 'Use the live Morocco case below to investigate that separate question.')
        st.caption(LIMITS)
        report = dict(schema='saharawatch-playable-mystery-v1', **case,
                      prediction=st.session_state['mystery_prediction_saved'],
                      verdict=st.session_state['mystery_verdict_saved'], scientific_limits=LIMITS)
        # Convert nonfinite scientific values to JSON null, as in notebook exports.
        report_json = pd.Series(report).to_json(indent=2, force_ascii=False)
        st.download_button('Download the solved case · JSON', report_json,
                           file_name='saharawatch_morocco_mystery.json', mime='application/json',
                           key='mystery_download', on_click='ignore')

    previous, following, restart = st.columns(3)
    previous.button('← Previous clue', key='mystery_back', disabled=stage == 1,
                    on_click=move_stage, args=(stage-1,))
    if stage < 4:
        following.button('Weigh the evidence →' if stage == 3 else 'Reveal next clue →',
                         key='mystery_next', on_click=move_stage, args=(stage+1,), type='primary')
    restart.button('Restart this mystery', key='mystery_restart', on_click=restart_mystery)
