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
def test_playable_case_gates_reveals_pins_frozen_evidence_and_restarts():
    at = AppTest.from_file(ROOT/'app.py').run(timeout=30)
    assert not at.exception
    assert not any(e.key.startswith('mystery_chart') for e in at.get('plotly_chart'))
    open_button = lambda: next(b for b in at.button if b.label == 'Break the seal & reveal clue 1')
    open_button().click().run(timeout=30)
    assert 'mystery_case' not in at.session_state
    at.radio(key='mystery_prediction').set_value('No three-year rainfall deficit')
    open_button().click().run(timeout=30)
    assert not at.exception
    case = copy.deepcopy(at.session_state['mystery_case'])
    assert case['assessment']['status'] == 'Persistent rainfall deficit'
    assert [e.key for e in at.get('plotly_chart') if e.key.startswith('mystery_chart')] == ['mystery_chart_1']
    at.button(key='mystery_pin_1').click().run(timeout=30)
    assert not at.exception
    at.button(key='mystery_pin_1').click().run(timeout=30)
    assert len(at.session_state['clues']) == 1
    assert at.session_state['clues'][0]['status'] == 'The annual record'
    # Later sidebar edits preserve the case, including its reference climate.
    at.slider(key='baseline').set_range(1981, 2010).run(timeout=30)
    at.slider(key='period').set_range(1991, 2020).run(timeout=30)
    assert at.session_state['mystery_case']['charts'] == case['charts']
    assert at.session_state['mystery_case']['baseline'] == '2001–2020'
    for stage in (2, 3):
        at.button(key='mystery_next').click().run(timeout=30)
        assert not at.exception
        assert f'mystery_chart_{stage}' in [e.key for e in at.get('plotly_chart')]
        at.button(key=f'mystery_pin_{stage}').click().run(timeout=30)
    assert len(at.session_state['clues']) == 3
    at.button(key='mystery_next').click().run(timeout=30)
    submit = lambda: next(b for b in at.button if b.label == 'Submit verdict & unseal the assessment')
    submit().click().run(timeout=30)
    assert at.session_state['mystery_stage'] == 4
    at.radio(key='mystery_verdict').set_value('No multi-year rainfall deficit')
    submit().click().run(timeout=30)
    assert not at.exception
    assert at.session_state['mystery_stage'] == 5
    assert any('revising a hypothesis' in e.value for e in at.info)
    at.button(key='mystery_back').click().run(timeout=30)
    at.radio(key='mystery_verdict').set_value('Persistent rainfall deficit')
    submit().click().run(timeout=30)
    assert any('Your verdict matches' in e.value for e in at.success)
    at.button(key='mystery_restart').click().run(timeout=30)
    assert not at.exception
    assert 'mystery_case' not in at.session_state
    assert len(at.session_state['clues']) == 3
    assert at.radio(key='mystery_prediction').value is None
    assert '1981–2010' in next(e.value for e in at.caption if 'Sealed envelope' in e.value)
