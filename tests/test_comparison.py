import numpy as np
import pytest
import xarray as xr
from saharawatch.comparison import comparison_summary, comparison_interpretation
from saharawatch.data import ROOT,RAW
from streamlit.testing.v1 import AppTest


def test_summary_uses_selected_years_and_fixed_baseline():
    data=xr.DataArray(100+np.arange(30)*2.,dims='year',coords={'year':np.arange(1991,2021)})
    r=comparison_summary(data,'A',2001,2020,1991,2010)
    assert r['n']==20 and r['decade']==pytest.approx(20)
    assert r['recent_anomaly_mm']==pytest.approx(float(data.sel(year=2020)-data.sel(year=slice(1991,2010)).mean()))
    s=comparison_summary(data*2,'B',2001,2020,1991,2010)
    interpretation=comparison_interpretation(r,s)
    assert 'same direction' in interpretation
    assert 'B has the larger estimated absolute' in interpretation
    assert 'relative trend in %/decade magnitudes are equal' in interpretation
    assert 'do not test' in interpretation


def test_opposite_near_zero_and_insufficient_comparisons():
    a=dict(selection='A',decade=10.,relative=5.)
    b=dict(selection='B',decade=-30.,relative=np.nan)
    text=comparison_interpretation(a,b)
    assert 'opposite directions' in text and 'B has the larger' in text
    assert 'Relative trend comparison is unavailable' in text
    assert 'insufficient' in comparison_interpretation(a,dict(b,decade=np.nan))


@pytest.mark.skipif(not RAW.exists(),reason='Requires downloaded GPCP')
def test_grid_cell_comparison_and_normalized_chart():
    at=AppTest.from_file(ROOT/'app.py').run(timeout=30)
    at.radio(key='comparison_mode').set_value('Grid cells').run(timeout=30)
    assert not at.exception
    at.number_input(key='compare_lat_1').set_value(36.25).run(timeout=30)
    at.number_input(key='compare_lon_1').set_value(11.25).run(timeout=30)
    at.toggle(key='normalize_compare').set_value(True).run(timeout=30)
    assert not at.exception
    plots=[e.key for e in at.get('plotly_chart')]
    assert all(k in plots for k in ['comparison_history_0','comparison_history_1','comparison'])
    at.slider(key='period').set_range(2020,2024).run(timeout=30)
    assert not at.exception
    assert any('insufficient observations to compare' in e.value for e in at.markdown)
