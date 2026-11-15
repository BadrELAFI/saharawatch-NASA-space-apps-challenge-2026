"""A shared case library with guided quizzes and independent evidence missions."""
import base64
import copy
import json

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from .case_catalog import CASES, case_title, build_quiz, country_series, clean_json
from .analysis import annual_anomalies
from .briefing import recent_assessment, assessment_text
from .inference import analyze_trend
from .guided import render_live_investigation
from .plots import history_figure
from .satellite import load_satellite_pair, active_satellite_pair, rainfall_context, restore_satellite_controls
from .navigation import activate_workspace
from .case_folders import render_folders
from .exhibits import exhibit, filed_stamp

PATHS = ['Answer the quiz', 'Investigate on your own']


def choose_case(key, path=PATHS[0]):
    st.session_state.update(library_case=key, case_path=path)
    activate_workspace('03 / Case files')


def open_satellite_workspace():
    restore_satellite_controls()
    activate_workspace('Satellite images')


def restart_quiz(key):
    st.session_state.get('case_attempts', {}).pop(key, None)
    for widget in list(st.session_state):
        if widget.startswith(f'quiz_{key}_'):
            del st.session_state[widget]


def move_quiz(key, step):
    st.session_state['case_attempts'][key]['step'] = step


def pin_snapshot(snapshot):
    clues = st.session_state.setdefault('clues', [])
    if snapshot not in clues:
        clues.append(copy.deepcopy(snapshot))


def descriptive_snapshot(context, title, explanation, charts, **extra):
    return dict(location=context['location'], period=context['period'], baseline=context['baseline'],
                source=context['source'], source_sha256=context['source_sha256'],
                source_status=context.get('source_status', ''), case_id=context['case_id'],
                evidence_kind='case investigation', country_weighting=context['country_weighting'],
                hypothesis='', status=title, assessment=explanation, notes='',
                trend_mm_decade='Not assessed', p_value='Not assessed', confidence_interval='Not assessed',
                inference_method=context['inference_method'], annual_data=context.get('annual_data', []),
                chart_json=charts, **extra)


def render_quiz(key, annual, monthly, countries, metadata, years, start, end, bstart, bend, alpha, method, weighting):
    if key == 'satellite':
        st.caption('The quiz uses the fixed 2023/2024 training example. To choose other years, use Satellite images.')
        st.button('Open satellite workspace', key='quiz_satellite_workspace', on_click=open_satellite_workspace)
    attempts = st.session_state.setdefault('case_attempts', {})
    attempt = attempts.get(key)
    prefix = f'quiz_{key}_'
    if attempt is None:
        st.write('Make a prediction, inspect three clues, and answer a question after each one. '
                 'Each explanation uses the evidence in your opened attempt. You can continue after an incorrect answer.')
        st.caption('Opening a quiz freezes its observations, reference period, method and source. Sidebar changes affect the next attempt.')
        with st.form(prefix+'open'):
            prediction = st.text_input('Your first hypothesis', placeholder='What do you expect to find? “I need more evidence” is welcome.', key=prefix+'prediction')
            observation = st.selectbox('Observation year', list(range(start, end+1)), index=end-start,
                                       key=prefix+'year') if key == 'anomaly' else end
            opened = st.form_submit_button('Open quiz', type='primary')
        if opened:
            if not prediction.strip():
                st.warning('Record a hypothesis, including “I need more evidence”, before opening the quiz.')
                return
            try:
                with st.spinner('Sealing the observations for this attempt…'):
                    context = build_quiz(key, annual, monthly, countries, metadata, start, end, bstart, bend,
                                         alpha, method, weighting, observation, years)
                    if key == 'satellite':
                        manifest, payloads = load_satellite_pair()
                        context['image_previews'] = [base64.b64encode(payload).decode() for payload in payloads]
                attempts[key] = dict(context=context, prediction=prediction.strip(), step=0, answers=[])
                st.rerun()
            except (OSError, ValueError, KeyError) as exc:
                st.warning(f'This quiz cannot be opened with the available evidence: {exc}')
        return

    context, step = attempt['context'], attempt['step']
    st.caption(f'Frozen attempt · {context["location"]} · {context["period"]} · baseline {context["baseline"]} · '
               f'{context["inference_method"]} · {context["country_weighting"]} weighting')
    if context['source_status']:
        st.caption('Source status: '+context['source_status'])
    st.progress(len(attempt['answers'])/3, text=f'{len(attempt["answers"])} / 3 questions answered')
    if step < 3:
        clue = context['clues'][step]
        st.markdown(f'#### Clue {step+1} / {clue["title"]}')
        if key == 'satellite' and step == 0:
            for col, image, encoded in zip(st.columns(2), context['satellite_manifest']['images'], context['image_previews']):
                col.image(base64.b64decode(encoded), caption=f'{image["date"]} · {image["platform"]} MODIS', width='stretch')
        if clue['chart']:
            with exhibit(f'EXHIBIT {step+1:02d}',clue['title'],prefix+f'exhibit_{step}'):
                st.plotly_chart(go.Figure(json.loads(clue['chart'])), width='stretch', theme=None, key=prefix+f'chart_{step}')
        if clue['evidence']:
            st.write(clue['evidence'])
        answered = len(attempt['answers']) > step
        if not answered:
            with st.form(prefix+f'question_{step}'):
                choice = st.radio(clue['prompt'], clue['options'], index=None, key=prefix+f'choice_{step}')
                submitted = st.form_submit_button('Check my answer', type='primary')
            if submitted:
                if choice is None:
                    st.warning('Choose an answer before checking the evidence.')
                else:
                    attempt['answers'].append(dict(choice=choice, correct=choice == clue['correct']))
                    st.rerun()
        else:
            response = attempt['answers'][step]
            if response['correct']:
                st.success('Your answer matches the evidence: '+clue['correct'])
            else:
                st.info(f'You chose “{response["choice"]}”. The supported answer is “{clue["correct"]}”. '+clue['feedback'][response['choice']])
            st.write(clue['explanation'])
            snapshot = descriptive_snapshot(context, clue['title'], clue['explanation'],
                         {f'case_{key}_clue_{step+1}':clue['chart']} if clue['chart'] else {},
                         quiz_prediction=attempt['prediction'], quiz_answer=response['choice'])
            st.button('Pin this clue to Field notebook', key=prefix+f'pin_{step}', on_click=pin_snapshot, args=(snapshot,))
            if snapshot in st.session_state.get('clues', []):
                st.caption('Clue pinned. It is available in Field notebook and the connected evidence board.')
        previous, following = st.columns(2)
        previous.button('← Previous clue', disabled=step == 0, key=prefix+'back', on_click=move_quiz, args=(key, step-1))
        following.button('Reveal next clue →' if step < 2 else 'Finish quiz →', disabled=not answered,
                         key=prefix+'next', on_click=move_quiz, args=(key, step+1))
    else:
        st.session_state.setdefault('completed_quizzes', {})[key] = copy.deepcopy(attempt)
        score = sum(answer['correct'] for answer in attempt['answers'])
        filed_stamp()
        st.success(f'Case complete · {score} / 3 answers matched the evidence on the first try.')
        st.write('Your first hypothesis: **'+attempt['prediction']+'**')
        st.write('What would you revise now? A thoughtful change of mind is part of an investigation.')
        for clue, response in zip(context['clues'], attempt['answers']):
            with st.expander(clue['title']):
                st.write('Your answer: '+response['choice'])
                st.write('Supported answer: '+clue['correct'])
                st.write(clue['explanation'])
        st.caption(context['limits'])
        st.download_button('Download solved quiz · JSON', json.dumps(dict(schema='saharawatch-case-quiz-v1', **attempt), indent=2, allow_nan=False),
                           file_name=f'saharawatch_case_{CASES[key]["number"]}_quiz.json', mime='application/json', on_click='ignore', key=prefix+'download')
        st.button('Investigate this case on your own', key=prefix+'investigate', on_click=choose_case, args=(key, PATHS[1]), type='primary')
        st.button('Review the clues', key=prefix+'review', on_click=move_quiz, args=(key, 0))
    st.button('Restart quiz with current settings', key=prefix+'restart', on_click=restart_quiz, args=(key,))
    st.caption('Quiz progress and completed cases stay in this browser session. Download a report before closing it. Restarting retains completed reports and pinned clues.')


def render_mission(key, annual, monthly, countries, metadata, years, start, end, bstart, bend, alpha, method, weighting):
    prefix = f'mission_{key}_'
    st.write('Build your own argument. Choose the evidence, record what supports or challenges your hypothesis, '
             'then write a conclusion and one limitation. Completion tracks the work you record; it does not grade your scientific conclusion.')
    previous = st.session_state.get('case_attempts', {}).get(key, {})
    # Streamlit removes unrendered widget keys. Store editable drafts separately per case.
    drafts = st.session_state.setdefault('mission_drafts', {})
    draft = drafts.setdefault(key, dict(hypothesis=previous.get('prediction', ''), conclusion='', limitation='',
                                       country='Morocco' if 'Morocco' in countries else next(iter(countries), ''),
                                       partner='Algeria', period=[start, end], baseline=[bstart, bend],
                                       note='', relationship='Provides context', length=3, observation_year=end))
    def keep_draft(field):
        draft[field] = st.session_state[prefix+field]
    for field in ('hypothesis', 'conclusion', 'limitation', 'country', 'partner', 'period', 'baseline', 'note', 'relationship', 'length', 'observation_year'):
        st.session_state.setdefault(prefix+field, draft[field])
    hypothesis = st.text_area('Working hypothesis for this case', key=prefix+'hypothesis', on_change=keep_draft, args=('hypothesis',))
    with st.expander('Optional investigation hints'):
        for hint in CASES[key]['hints']:
            st.write('• '+hint)
    if not countries and key != 'satellite':
        st.warning('Country boundaries are required for these country investigation tools.')
        return
    if key == 'satellite':
        context = dict(case_id=key, location='Casablanca region · satellite comparison', period='',
                       baseline='Not used for imagery', country_weighting='Not applicable',
                       inference_method='Descriptive satellite and rainfall comparison', source=f'GPCP {metadata["version"]} / NOAA PSL',
                       source_sha256=metadata['sha256'], source_status=metadata.get('attributes', {}).get('data_comment', ''))
        st.info('Compare images in the Satellite images workspace, then return here to record your reasoning. Your selected dates and hypothesis are kept.')
        st.button('Open satellite workspace', key='mission_satellite_workspace', on_click=open_satellite_workspace, type='primary')
        try:
            manifest, payloads = active_satellite_pair()
        except (OSError, ValueError, KeyError) as exc:
            st.warning(f'Satellite evidence is unavailable: {exc}')
            return
        dates = [image['date'] for image in manifest['images']]
        context['period'] = ' / '.join(dates)
        st.caption(f'Current evidence: {dates[0]} → {dates[1]}. Change the image years in Satellite images.')
        rainfall, summary, figure, cell = rainfall_context(monthly,manifest)
        charts = {'satellite_rainfall':figure.to_json()}
        context.update(rainfall_cell=list(cell),rainfall_summary=summary,
                       rainfall_data=json.loads(rainfall.to_json(orient='records',date_format='iso')))
        context['satellite_manifest'] = manifest
        explanation = f'Satellite images acquired on {dates[0]} and {dates[1]} supply visual context; their difference does not establish rainfall causation.'
    else:
        controls = st.columns(2)
        if key == 'trends':
            name = 'Morocco' if 'Morocco' in countries else next(iter(countries))
            controls[0].caption('Ranking geography: complete MENA rectangle, including ocean cells.')
        else:
            name = controls[0].selectbox('Investigation country', sorted(countries), key=prefix+'country', on_change=keep_draft, args=('country',))
        period = controls[1].slider('Investigation period', years[0], years[-1], key=prefix+'period', on_change=keep_draft, args=('period',))
        baseline = st.slider('Investigation reference baseline', years[0], years[-1], key=prefix+'baseline', on_change=keep_draft, args=('baseline',))
        a, b = period
        bs, be = baseline
        if a >= b or be-bs+1 < 10:
            st.warning('Choose an ordered investigation period and a baseline spanning at least ten years.')
            return
        full = country_series(annual, countries, name, weighting)
        series = full.sel(year=slice(a, b))
        fit = analyze_trend(series.year.values, series.values, alpha, method)
        _, _, mean = annual_anomalies(full, bs, be)
        chart = history_figure(series, fit, float(mean))
        country_chart = chart
        extra_charts = {}
        context = dict(case_id=key, location=name, period=f'{a}–{b}', baseline=f'{bs}–{be}', country_weighting=weighting,
                       inference_method=method, source=f'GPCP {metadata["version"]} / NOAA PSL', source_sha256=metadata['sha256'],
                       source_status=metadata.get('attributes', {}).get('data_comment', ''),
                       alpha=alpha, annual_data=json.loads(pd.DataFrame({'year':series.year.values, 'precipitation_mm':series.values}).to_json(orient='records')))
        st.caption(f'Investigation settings above are independent of the sidebar period and baseline. Method: {method} · α={alpha} · {weighting} weighting.')
        if key in ('morocco', 'compare', 'anomaly', 'trends'):
            partners = [n for n in countries if n != name]
            if key == 'compare' and partners:
                if st.session_state[prefix+'partner'] not in partners:
                    st.session_state[prefix+'partner'] = partners[0]
                partner = st.selectbox('Comparison country', sorted(partners), key=prefix+'partner', on_change=keep_draft, args=('partner',))
                context['comparison_country'] = partner
            else:
                partner = None
            # Retain existing, tested chart and export tools while allowing another primary country.
            view = render_live_investigation(annual, countries, a, b, bs, be, alpha, key,
                method=method, weighting=weighting, primary=name, partner=partner, year_key=prefix+'observation_year')
            if not view:
                st.info('Choose settings with a supported evidence view before pinning this investigation.')
                return
            chart = view.pop('chart')
            context.update(clean_json(view))
            if key == 'anomaly':
                draft['observation_year'] = context['observation_year']
            if key == 'trends':
                context['location'] = 'MENA rectangular grid · includes ocean'
                context['annual_data'] = []
            elif key == 'anomaly':
                context['location'] = f'MENA anomaly map · {name} country history'
                country_chart.add_vline(x=context['observation_year'], line_dash='dot')
                st.caption(f'{name} country context for the selected year; the regional map includes ocean cells.')
                st.plotly_chart(country_chart, width='stretch', theme=None, key=prefix+'country_history')
                extra_charts['country_history'] = country_chart.to_json()
            elif key == 'compare' and partner:
                context['location'] = f'{name} and {partner}'
        else:
            length = st.selectbox('Assessment length', [3, 5, 10], key=prefix+'length', on_change=keep_draft, args=('length',))
            assessment = recent_assessment(full, b, length, bs, be)
            st.plotly_chart(chart, width='stretch', theme=None, key=prefix+'history')
            st.write(assessment_text(name, assessment))
            context['recent_assessment'] = clean_json(assessment)
        explanation = (f'{name}: {fit["status"]}. ' if key == 'morocco' else 'Descriptive evidence for '+context['location']+'. ')+f'Period {a}–{b}; baseline {bs}–{be}.'
        charts = {'investigation_rainfall':chart.to_json(), **extra_charts}
    relationship = st.selectbox('How does this evidence relate to your hypothesis?',
                               ['Provides context', 'Supports', 'Challenges'], key=prefix+'relationship', on_change=keep_draft, args=('relationship',))
    note = st.text_input('Evidence note', placeholder='Which observation matters, and why?', key=prefix+'note', on_change=keep_draft, args=('note',))
    snapshot = descriptive_snapshot(context, case_title(key), explanation, charts,
                                    mission_case=key, evidence_context=clean_json(context), interpretation=relationship)
    snapshot.update(hypothesis=hypothesis.strip(), notes=note.strip())
    st.button('Pin current evidence to Field notebook', key=prefix+'pin', on_click=pin_snapshot, args=(snapshot,),
              disabled=not hypothesis.strip() or (key == 'satellite' and 'satellite_active_pair' not in st.session_state))
    evidence = [clue for clue in st.session_state.get('clues', []) if clue.get('mission_case') == key]
    st.caption(f'{len(evidence)} pinned evidence item(s) for this case. Pins retain the original observations and settings; removing them in Field notebook updates this mission.')
    conclusion = st.text_area('Your conclusion', key=prefix+'conclusion', on_change=keep_draft, args=('conclusion',))
    limitation = st.text_area('One limitation or alternative explanation', key=prefix+'limitation', on_change=keep_draft, args=('limitation',))
    checks = [bool(hypothesis.strip()), bool(evidence), bool(conclusion.strip()), bool(limitation.strip())]
    st.progress(sum(checks)/4, text=f'{sum(checks)} / 4 investigation steps recorded')
    st.caption(' · '.join(('✓ ' if done else '○ ')+label for done, label in zip(checks, ['Hypothesis', 'Pinned evidence', 'Conclusion', 'Limitation'])))
    if st.button('Save investigation', disabled=not all(checks), key=prefix+'save', type='primary'):
        st.session_state.setdefault('saved_missions', {})[key] = copy.deepcopy(dict(
            schema='saharawatch-independent-investigation-v1', case_id=key, title=case_title(key),
            hypothesis=hypothesis.strip(), conclusion=conclusion.strip(), limitation=limitation.strip(), evidence=evidence,
            completion_note='Required investigation steps recorded; the written conclusion has not been automatically graded.'))
    saved = st.session_state.get('saved_missions', {}).get(key)
    if saved:
        filed_stamp('INVESTIGATION FILED')
        st.success('Investigation saved in this session. Download it to keep the evidence and your reasoning.')
        st.download_button('Download investigation · JSON', json.dumps(saved, indent=2, allow_nan=False),
                           file_name=f'saharawatch_case_{CASES[key]["number"]}_investigation.json',
                           mime='application/json', on_click='ignore', key=prefix+'download')
        st.caption('The download is the saved snapshot. Save again after editing to update it.')


def render_case_library(annual, monthly, countries, metadata, years, start, end, bstart, bend, alpha, method, weighting, preset):
    preferences = st.session_state.setdefault('library_preferences',dict(case='morocco',path=PATHS[0]))
    st.session_state.setdefault('library_case',preferences['case'])
    st.session_state.setdefault('case_path',preferences['path'])
    st.subheader('Explore a Climate Mystery')
    st.write('Pick a question, then choose guided learning or an independent investigation. Satellite comparisons have their own workspace in the navigation above.')
    st.caption('STEP 1 · Choose your question')
    selected = st.selectbox('Choose a case', list(CASES), format_func=case_title, key='library_case')
    st.caption('STEP 2 · Choose how to explore')
    path = st.radio('Choose your path', PATHS, horizontal=True, key='case_path')
    preferences.update(case=selected,path=path)
    st.caption('Quiz: follow three clues with explanations.' if path == PATHS[0] else
               'Independent investigation: choose evidence, pin observations, and save your reasoning.')
    case = CASES[selected]
    solved = st.session_state.get('completed_quizzes', {})
    saved = st.session_state.get('saved_missions', {})
    st.caption(f'{case["difficulty"]} · about {case["minutes"]} minutes · '
               f'{"Quiz complete" if selected in solved else "Quiz not completed"} · '
               f'{"Investigation saved" if selected in saved else "Investigation not saved"}')
    st.caption(f'Your session: {len(solved)}/6 quizzes completed · {len(saved)}/6 investigations saved. '
               'Progress is session-only; a fresh investigation clears it.')
    with st.expander('Browse all six cases',expanded=True):
        render_folders(selected,solved,saved,preset)
    st.markdown('### '+case_title(selected))
    st.write(case['question'])
    if path == PATHS[0]:
        render_quiz(selected, annual, monthly, countries, metadata, years, start, end, bstart, bend, alpha, method, weighting)
    else:
        render_mission(selected, annual, monthly, countries, metadata, years, start, end, bstart, bend, alpha, method, weighting)
