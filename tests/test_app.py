from streamlit.testing.v1 import AppTest
from saharawatch.data import RAW, ROOT
import pytest

pytestmark=pytest.mark.skipif(not RAW.exists(),reason='Requires downloaded GPCP')


def test_dashboard_starts_and_updates():
    at=AppTest.from_file(ROOT / 'app.py').run(timeout=30)
    assert not at.exception
    assert len(at.metric)>=4
    original=at.metric[0].value
    at.slider(key='period').set_range(1991,2020).run(timeout=30)
    assert not at.exception
    assert at.metric[3].value=='30'
    assert at.metric[0].value!=original
    at.radio(key='mode').set_value('Country aggregation').run(timeout=30)
    assert not at.exception
    at.selectbox(key='country').set_value('United Arab Emirates').run(timeout=30)
    assert not at.exception
    assert at.metric[3].value=='30'
    at.radio(key='resolution').set_value('Monthly').run(timeout=30)
    assert not at.exception


def test_maps_baselines_comparison_and_presets():
    at=AppTest.from_file(ROOT / 'app.py').run(timeout=30)
    for name in ['Linear trend','Relative trend','Annual anomaly','Standardized anomaly','Trend significance']:
        at.selectbox(key='indicator').set_value(name).run(timeout=30)
        assert not at.exception, name
    at.radio(key='correction').set_value('Raw p-values').run(timeout=30)
    assert not at.exception
    at.slider(key='baseline').set_range(1981,2010).run(timeout=30)
    assert not at.exception
    at.toggle(key='normalize_compare').set_value(True).run(timeout=30)
    assert not at.exception
    at.button(key='preset_morocco').click().run(timeout=30)
    assert not at.exception
    assert at.radio(key='mode').value=='Country aggregation'
    assert at.selectbox(key='country').value=='Morocco'
    at.slider(key='baseline').set_range(2001,2005).run(timeout=30)
    assert not at.exception
    assert any('at least 10' in w.value for w in at.warning)


def test_missing_dataset_gives_actionable_error(tmp_path):
    # Exercise the real entrypoint error state without changing the downloaded dataset.
    from unittest.mock import patch
    import saharawatch.data
    at=AppTest.from_file(ROOT / 'app.py')
    with patch.object(saharawatch.data,'RAW',tmp_path / 'missing.nc'), patch.object(saharawatch.data,'load_data',side_effect=FileNotFoundError('GPCP file missing. Run: python scripts/prepare_data.py')):
        at.run(timeout=30)
    assert not at.exception
    assert any('prepare_data.py' in e.value for e in at.error)


def test_detective_tools_and_notebook_preserve_evidence_context():
    at = AppTest.from_file(ROOT / 'app.py').run(timeout=30)
    at.button(key='inspect_driest').click().run(timeout=30)
    assert not at.exception
    assert at.selectbox(key='indicator').value == 'Annual anomaly'
    from saharawatch.data import load_data, grid_series
    import numpy as np
    _, annual, _ = load_data()
    selected = grid_series(annual.sel(year=slice(2001, 2024)), 31.25, -6.25)
    expected_year = int(selected.year.values[np.argmin(selected.values)])
    assert at.selectbox(key='anomaly_year').value == expected_year
    at.button(key='challenge_evidence').click().run(timeout=30)
    assert at.selectbox(key='indicator').value == 'Trend significance'
    at.button(key='pin_evidence').click().run(timeout=30)
    assert not at.exception
    clue = dict(at.session_state['clues'][0])
    assert clue['period'] == '2001–2024'
    assert clue['baseline'] == '2001–2020'
    assert clue['observation_year'] == expected_year
    at.button(key='pin_evidence').click().run(timeout=30)
    assert len(at.session_state['clues']) == 1
    at.slider(key='period').set_range(1991, 2020).run(timeout=30)
    assert at.session_state['clues'][0] == clue
    at.button(key='pin_evidence').click().run(timeout=30)
    assert len(at.session_state['clues']) == 2
    at.button(key='remove_clue_0').click().run(timeout=30)
    assert len(at.session_state['clues']) == 1
    assert at.session_state['clues'][0]['period'] == '1991–2020'
    assert not at.exception


def test_hypothesis_distinguishes_opposing_and_inconclusive_evidence():
    at = AppTest.from_file(ROOT / 'app.py').run(timeout=30)
    at.radio(key='hypothesis').set_value('Rainfall is increasing').run(timeout=30)
    at.button(key='pin_evidence').click().run(timeout=30)
    assert 'opposite direction' in at.session_state['clues'][0]['assessment']
    at.selectbox(key='alpha').set_value(0.01).run(timeout=30)
    at.button(key='pin_evidence').click().run(timeout=30)
    assert at.session_state['clues'][1]['assessment'].startswith('Inconclusive:')
    assert not at.exception


def test_deficit_views_and_spi_controls():
    at=AppTest.from_file(ROOT / 'app.py').run(timeout=30)
    at.selectbox(key='indicator').set_value('Relative anomaly').run(timeout=30)
    assert not at.exception
    at.radio(key='deficit_resolution').set_value('Monthly').run(timeout=30)
    at.selectbox(key='deficit_metric').set_value('Standardized anomaly (σ)').run(timeout=30)
    assert not at.exception
    at.checkbox(key='enable_spi').set_value(True).run(timeout=30)
    assert not at.exception
    assert 'spi_chart' in [e.key for e in at.get('plotly_chart')]
    at.selectbox(key='spi_scale').set_value(12).run(timeout=30)
    assert not at.exception
    assert 'spi_chart' in [e.key for e in at.get('plotly_chart')]
    at.radio(key='mode').set_value('Country aggregation').run(timeout=30)
    assert not at.exception
    assert 'spi_chart' in [e.key for e in at.get('plotly_chart')]
    at.slider(key='spi_calibration').set_range(2001,2020).run(timeout=30)
    assert not at.exception
    assert any('choose at least 30' in e.value for e in at.info)
    assert 'spi_chart' not in [e.key for e in at.get('plotly_chart')]
    # Anomalies still render with the shorter, independent SPI calibration window.
    assert 'departure_chart' in [e.key for e in at.get('plotly_chart')]
