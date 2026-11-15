import numpy as np
import xarray as xr
import pytest
from streamlit.testing.v1 import AppTest
from saharawatch.guided import rank_trend_cells
from saharawatch.data import ROOT,RAW


def test_ranking_uses_absolute_magnitude_excludes_missing_and_breaks_ties():
    slopes=np.array([[-40.,10.],[40.,np.nan]])
    p=np.array([[.01,.7],[.4,np.nan]])
    grid=xr.DataArray(np.stack([slopes,p],axis=-1),dims=('lat','lon','stat'),
                      coords={'lat':[11.25,13.75],'lon':[-6.25,-3.75],'stat':['decade','p']})
    rank,frame=rank_trend_cells(grid)
    assert list(frame.trend_mm_decade)==[-40.,40.,10.]
    assert list(frame['rank'])==[1,2,3]
    assert float(rank.sel(lat=11.25,lon=-6.25))==1
    assert np.isnan(rank.sel(lat=13.75,lon=-3.75))
    assert list(frame.fdr_significant)==[True,False,False]
    # A stronger slope does not automatically receive a significance flag.
    assert frame.iloc[1].absolute_trend_mm_decade==40 and not frame.iloc[1].fdr_significant


@pytest.mark.skipif(not RAW.exists(),reason='Requires downloaded GPCP')
def test_all_guided_cases_render_live_results_and_preserve_period():
    at=AppTest.from_file(ROOT/'app.py').run(timeout=30)
    at.slider(key='period').set_range(1991,2020).run(timeout=30)
    at.radio(key='case_path').set_value('Investigate on your own').run(timeout=30)
    for case,plot in [('morocco','guided_morocco_history'),('compare','guided_comparison'),
                      ('anomaly','guided_anomaly_map'),('trends','guided_rank_map')]:
        at.button(key='preset_'+case).click().run(timeout=30)
        assert not at.exception,case
        assert tuple(at.slider(key='period').value)==(1991,2020)
        assert plot in [e.key for e in at.get('plotly_chart')]
    at.slider(key='mission_trends_period').set_range(2020,2024).run(timeout=30)
    assert not at.exception
    assert any('enough valid annual' in e.value for e in at.info)
