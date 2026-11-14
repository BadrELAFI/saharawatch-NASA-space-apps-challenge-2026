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
