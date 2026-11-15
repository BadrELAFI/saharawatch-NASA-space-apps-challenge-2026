"""Verify the mystery teaches cumulative deficits without drifting evidence."""
import copy
import base64
import json

import numpy as np
import pytest
import xarray as xr
import plotly.graph_objects as go
from streamlit.testing.v1 import AppTest

from saharawatch.data import ROOT, RAW
from saharawatch.mystery import build_mystery


def example(recent):
    values = np.r_[np.tile([80., 100., 120., 100.], 5), recent]
    annual = xr.DataArray(values[:, None, None], dims=('year', 'lat', 'lon'),
                          coords={'year':np.arange(2001, 2024), 'lat':[31.25], 'lon':[-6.25]})
    feature = dict(type='Feature', properties={}, geometry=dict(type='Polygon',
                   coordinates=[[[-8, 30], [-4, 30], [-4, 33], [-8, 33], [-8, 30]]]))
    metadata = dict(version='test', sha256='test-checksum', start='2001-01-01',
                    end='2023-12-31', data_comment='Interim test observations')
    return annual, feature, metadata


@pytest.mark.parametrize('recent,expected', [
    ([60, 70, 80], 'Persistent rainfall deficit'),
    ([50, 130, 90], 'Multi-year rainfall deficit'),
    ([80, 140, 150], 'No multi-year rainfall deficit'),
    ([60, np.nan, 80], 'Insufficient data'),
])
def test_mystery_uses_observations_and_preserves_missing_data(recent, expected):
    annual, feature, metadata = example(recent)
    case = build_mystery(annual, feature, metadata, 2023, 2001, 2020, 'Center-point')
    assert case['assessment']['status'] == expected
    assert case['period'] == '2021–2023'
    assert case['source_sha256'] == 'test-checksum'
    figure = go.Figure(json.loads(case['charts'][1]))
    # Reconstruct Plotly's encoded arrays to check the actual cumulative balance.
    encoded = figure.data[0].y
    bars = (np.frombuffer(base64.b64decode(encoded['bdata']), dtype=encoded['dtype'])
            if isinstance(encoded, dict) else np.asarray(encoded, dtype=float))
    np.testing.assert_allclose(bars, np.cumsum(np.asarray(recent)-100), equal_nan=True)
    if expected == 'Insufficient data':
        assert case['assessment']['annual_mm'][1] is None
        assert np.isnan(case['assessment']['total_mm'])
    else:
        assert case['assessment']['departure_mm'] == pytest.approx(sum(recent)-300)
    # Mutating the live input cannot alter an already opened case.
    saved = copy.deepcopy(case)
    annual.values[:] = 999
    assert case['annual_data'] == saved['annual_data']
    assert case['charts'] == saved['charts']


@pytest.mark.skipif(not RAW.exists(), reason='Requires downloaded GPCP')
def test_recent_rainfall_quiz_preserves_calculated_deficit_and_pins():
    at = AppTest.from_file(ROOT/'app.py').run(timeout=30)
    at.selectbox(key='library_case').set_value('recent').run(timeout=30)
    at.text_input(key='quiz_recent_prediction').set_value('I need more evidence')
    next(b for b in at.button if b.label == 'Open quiz').click().run(timeout=30)
    assert not at.exception
    original = copy.deepcopy(at.session_state['case_attempts']['recent']['context'])
    assert original['recent_assessment']['status'] == 'Persistent rainfall deficit'
    at.slider(key='baseline').set_range(1981, 2010).run(timeout=30)
    assert at.session_state['case_attempts']['recent']['context'] == original
    for step in range(3):
        clue = original['clues'][step]
        assert at.button(key='quiz_recent_next').disabled
        at.radio(key=f'quiz_recent_choice_{step}').set_value(clue['correct'])
        next(b for b in at.button if b.label == 'Check my answer').click().run(timeout=30)
        assert not at.exception
        at.button(key=f'quiz_recent_pin_{step}').click().run(timeout=30)
        at.button(key='quiz_recent_next').click().run(timeout=30)
    assert not at.exception
    assert len(at.session_state['clues']) == 3
    assert 'recent' in at.session_state['completed_quizzes']
    assert all(a['correct'] for a in at.session_state['completed_quizzes']['recent']['answers'])
    at.button(key='quiz_recent_restart').click().run(timeout=30)
    assert 'recent' not in at.session_state['case_attempts']
    assert len(at.session_state['clues']) == 3
    assert 'recent' in at.session_state['completed_quizzes']
