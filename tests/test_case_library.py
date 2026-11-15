"""Exercise meaningful quiz answers, frozen attempts and independent investigation drafts."""
import copy
import json

import numpy as np
import pandas as pd
import pytest
import xarray as xr
from streamlit.testing.v1 import AppTest

from saharawatch.case_catalog import CASES, build_quiz, trend_answer
from saharawatch.data import ROOT, RAW


def example():
    years = np.arange(2001, 2025)
    values = np.stack([50+2*(years-2001), 100-(years-2001)], axis=-1)[:, None, :]
    annual = xr.DataArray(values.astype(float), dims=('year', 'lat', 'lon'),
                          coords={'year':years, 'lat':[31.25], 'lon':[-6.25, -3.75]})
    dates = pd.date_range('2000-01-01', '2024-12-01', freq='MS')
    monthly = xr.DataArray(np.full((len(dates), 1, 2), 10.), dims=('time', 'lat', 'lon'),
                           coords={'time':dates, 'lat':[31.25], 'lon':[-6.25, -3.75]})
    def feature(west, east):
        return dict(type='Feature', properties={}, geometry=dict(type='Polygon',
            coordinates=[[[west, 30], [east, 30], [east, 33], [west, 33], [west, 30]]]))
    countries = {'Morocco':feature(-8, -5), 'Algeria':feature(-5, -2)}
    metadata = dict(version='test', sha256='source-checksum', start='2000-01-01', end='2024-12-31', attributes={})
    return annual, monthly, countries, metadata, years


@pytest.mark.parametrize('key', list(CASES))
def test_all_six_quizzes_have_three_supported_questions_and_portable_evidence(key):
    annual, monthly, countries, metadata, years = example()
    quiz = build_quiz(key, annual, monthly, countries, metadata, 2001, 2024, 2001, 2020,
                      .05, 'OLS', 'Center-point', 2024, years.tolist())
    assert len(quiz['clues']) == 3
    for clue in quiz['clues']:
        assert clue['correct'] in clue['options']
        assert clue['explanation'] and clue['misconception']
    assert quiz['source_sha256'] == 'source-checksum'
    json.dumps(quiz, allow_nan=False)
    if key == 'morocco':
        assert [c['correct'] for c in quiz['clues'][:2]] == ['Increase', 'Increase']
    elif key == 'compare':
        assert quiz['clues'][0]['correct'] == 'Morocco'
    elif key == 'anomaly':
        assert quiz['clues'][0]['correct'] == 'At or above baseline'
    elif key == 'recent':
        assert quiz['clues'][2]['correct'] == 'No multi-year rainfall deficit'
    original = copy.deepcopy(quiz)
    annual.values[:] = np.nan
    assert quiz == original


def test_quiz_distinguishes_direction_uncertainty_and_missing_evidence():
    assert trend_answer(dict(p=.8, slope=-1), .05) == 'No statistically significant direction detected'
    assert trend_answer(dict(p=np.nan, slope=-1), .05) == 'Insufficient data'
    annual, monthly, countries, metadata, years = example()
    annual.values[-1, 0, 0] = np.nan
    quiz = build_quiz('anomaly', annual, monthly, countries, metadata, 2001, 2024, 2001, 2020,
                      .05, 'OLS', 'Center-point', 2024, years.tolist())
    assert quiz['clues'][0]['correct'] == 'Insufficient data'


@pytest.mark.skipif(not RAW.exists(), reason='Requires downloaded GPCP')
def test_quiz_gate_feedback_case_switching_and_independent_mission():
    at = AppTest.from_file(ROOT/'app.py').run(timeout=30)
    assert not at.exception
    assert at.selectbox(key='library_case').options == [f'Case {case["number"]} / {case["title"]}' for case in CASES.values()]
    assert at.selectbox(key='library_case').value == 'morocco'
    at.text_input(key='quiz_morocco_prediction').set_value('Rainfall may be decreasing')
    next(b for b in at.button if b.label == 'Open quiz').click().run(timeout=30)
    context = copy.deepcopy(at.session_state['case_attempts']['morocco']['context'])
    assert at.button(key='quiz_morocco_next').disabled
    for step in range(3):
        clue = context['clues'][step]
        choice = next(option for option in clue['options'] if option != clue['correct']) if step == 0 else clue['correct']
        at.radio(key=f'quiz_morocco_choice_{step}').set_value(choice)
        next(b for b in at.button if b.label == 'Check my answer').click().run(timeout=30)
        assert not at.exception
        if step == 0:
            assert any('supported answer' in item.value for item in at.info)
        at.button(key='quiz_morocco_next').click().run(timeout=30)
    assert 'morocco' in at.session_state['completed_quizzes']
    at.selectbox(key='library_case').set_value('compare').run(timeout=30)
    at.selectbox(key='library_case').set_value('morocco').run(timeout=30)
    assert at.session_state['case_attempts']['morocco']['context'] == context
    at.button(key='quiz_morocco_investigate').click().run(timeout=30)
    assert at.radio(key='case_path').value == 'Investigate on your own'
    assert at.text_area(key='mission_morocco_hypothesis').value == 'Rainfall may be decreasing'
    assert at.button(key='mission_morocco_save').disabled
    at.selectbox(key='mission_morocco_country').set_value('Tunisia').run(timeout=30)
    at.text_input(key='mission_morocco_note').set_value('Compare the fitted direction with uncertainty').run(timeout=30)
    at.button(key='mission_morocco_pin').click().run(timeout=30)
    assert not at.exception
    pinned = copy.deepcopy(at.session_state['clues'][-1])
    at.text_area(key='mission_morocco_conclusion').set_value('The selected record needs careful interpretation.').run(timeout=30)
    at.text_area(key='mission_morocco_limitation').set_value('The country average hides spatial variability.').run(timeout=30)
    at.button(key='mission_morocco_save').click().run(timeout=30)
    assert not at.exception
    saved = at.session_state['saved_missions']['morocco']
    assert saved['evidence'][0] == pinned and saved['evidence'][0]['location'] == 'Tunisia'
    json.dumps(saved, allow_nan=False)
    at.selectbox(key='library_case').set_value('anomaly').run(timeout=30)
    at.selectbox(key='library_case').set_value('morocco').run(timeout=30)
    assert at.text_area(key='mission_morocco_conclusion').value == saved['conclusion']
    assert at.selectbox(key='mission_morocco_country').value == 'Tunisia'
    at.slider(key='mission_morocco_period').set_range(1991, 2020).run(timeout=30)
    assert at.session_state['saved_missions']['morocco'] == saved
    assert at.session_state['clues'][-1] == pinned
