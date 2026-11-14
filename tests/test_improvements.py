import io
import json
import zipfile
import numpy as np
import pandas as pd
import pytest
import xarray as xr
from shapely.geometry import box,mapping
from scipy import stats
import pymannkendall as mk
from saharawatch.data import ROOT,RAW,country_mask,country_weights,regional_series,load_data,grid_series
from saharawatch.inference import analyze_trend,inference_grid,slope_difference
from saharawatch.temperature import parse_power,annual_temperature,fetch_temperature
from saharawatch.reports import build_report_archive
from saharawatch.plots import history_figure


def test_fractional_overlap_includes_partial_cell_and_preserves_missingness():
    grid=xr.DataArray([[10.,20.],[30.,40.]],dims=('lat','lon'),coords={'lat':[11.25,13.75],'lon':[1.25,3.75]})
    feature={'geometry':mapping(box(.1,10.1,.5,10.5))}
    assert not country_mask(grid,feature).any()
    w=country_weights(grid,feature,'Fractional area')
    assert int((w>0).sum())==1 and float(w.sum())>0
    assert float(regional_series(grid,w))==10
    grid.values[0,0]=np.nan
    assert np.isnan(regional_series(grid,w))


def test_fractional_areas_partition_a_cell():
    grid=xr.DataArray([[1.]],dims=('lat','lon'),coords={'lat':[11.25],'lon':[1.25]})
    full=country_weights(grid,{'geometry':mapping(box(0,10,2.5,12.5))},'Fractional area')
    left=country_weights(grid,{'geometry':mapping(box(0,10,1.25,12.5))},'Fractional area')
    right=country_weights(grid,{'geometry':mapping(box(1.25,10,2.5,12.5))},'Fractional area')
    assert float(full.sum())==pytest.approx(float(left.sum()+right.sum()),rel=1e-10)


def test_modified_mk_matches_reference_and_guards_calendar_gaps():
    x=np.arange(1981,2021)
    y=100+np.arange(40)*.8+8*np.sin(np.arange(40)/2)
    got=analyze_trend(x,y,method='Modified Mann–Kendall')
    ref=mk.hamed_rao_modification_test(y,alpha=.05,lag=3)
    assert got['p']==pytest.approx(ref.p)
    assert got['decade']==pytest.approx(ref.slope*10)
    assert np.isnan(got['low']) and np.isnan(got['high'])
    assert np.isnan(analyze_trend(np.delete(x,5),np.delete(y,5),method='Modified Mann–Kendall')['p'])
    assert analyze_trend(x,np.ones(40),method='Modified Mann–Kendall')['p']==1


def test_paired_difference_keeps_shared_covariance():
    years=np.arange(1981,2021)
    shared=50*np.sin(np.arange(40)/3)
    a=xr.DataArray(400+shared+np.arange(40)*3,dims='year',coords={'year':years})
    b=xr.DataArray(200+shared+np.arange(40),dims='year',coords={'year':years})
    result=slope_difference(a,b)
    assert result['decade']==pytest.approx(20)
    assert result['p']<.01 and result['n']==40
    same=slope_difference(a,a)
    assert same['p']==1 and same['decade']==0
    a.values[3]=np.nan
    assert np.isnan(slope_difference(a,b)['p'])


def test_temperature_calendar_weighting_and_source_validation():
    data=xr.DataArray(np.arange(12,dtype=float),dims='time',coords={'time':pd.date_range('2000-01-01',periods=12,freq='MS')})
    expected=np.average(data.values,weights=data.time.dt.days_in_month.values)
    assert float(annual_temperature(data).sel(year=2000))==pytest.approx(expected)
    data.values[1]=np.nan
    assert np.isnan(annual_temperature(data)).all()
    with pytest.raises(ValueError):parse_power({'parameters':{'T2M':{'units':'K'}}})


@pytest.mark.skipif(not (ROOT/'data/raw/power/31.25_-6.25_1981_2024.json').exists(),reason='Requires retained actual NASA POWER response')
def test_real_nasa_temperature_schema_and_alignment():
    m,a,provenance=fetch_temperature(31.25,-6.25,1981,2024)
    assert m.size==44*12 and a.size==44 and np.isfinite(a).all()
    assert provenance['header']['sources']==['MERRA2']
    assert m.attrs['units']=='°C'
    assert float(m.sel(time='1981-01-01'))==4.19  # Retained original API observation, not a demo value.


@pytest.mark.skipif(not RAW.exists(),reason='Requires actual GPCP')
def test_illustrated_report_contains_pinned_data_and_png_charts():
    _,annual,_=load_data()
    s=grid_series(annual.sel(year=slice(2001,2024)),31.25,-6.25)
    result=analyze_trend(s.year.values,s.values)
    rows=json.loads(pd.DataFrame({'year':s.year.values,'precipitation_mm':s.values}).to_json(orient='records'))
    chart=history_figure(s,result).to_json()
    clue={'location':'Grid cell <test>','notes':'<script>untrusted</script>','annual_data':rows,'chart_json':{'rainfall':chart}}
    archive=build_report_archive([clue])
    with zipfile.ZipFile(io.BytesIO(archive)) as z:
        assert z.read('charts/clue_01_rainfall.png').startswith(b'\x89PNG')
        html=z.read('report.html').decode()
        assert 'data:image/png;base64,' in html and '<script>untrusted' not in html
        assert '&lt;script&gt;' in html
        frame=pd.read_csv(io.BytesIO(z.read('data/clue_01.csv')))
        np.testing.assert_allclose(frame.precipitation_mm,s.values)


@pytest.mark.skipif(not RAW.exists(),reason='Requires actual GPCP')
def test_robust_methods_propagate_to_map_comparisons_and_notebook():
    from streamlit.testing.v1 import AppTest
    at=AppTest.from_file(ROOT/'app.py').run(timeout=30)
    for method in ['Newey–West HAC','Modified Mann–Kendall']:
        at.selectbox(key='inference_method').set_value(method).run(timeout=30)
        at.selectbox(key='indicator').set_value('Trend significance').run(timeout=30)
        assert not at.exception
        at.button(key='pin_evidence').click().run(timeout=30)
        assert at.session_state['clues'][-1]['inference_method']==method
        assert at.session_state['clues'][-1]['chart_json']
    at.radio(key='mode').set_value('Country aggregation').run(timeout=30)
    at.selectbox(key='weighting').set_value('Fractional area').run(timeout=30)
    assert not at.exception
    assert any('Fractional area' in e.value for e in at.caption)


@pytest.mark.skipif(not (ROOT/'data/raw/power/31.25_-6.25_1981_2024.json').exists(),reason='Requires retained NASA POWER response')
def test_temperature_dashboard_uses_real_cached_power_data():
    from streamlit.testing.v1 import AppTest
    at=AppTest.from_file(ROOT/'app.py').run(timeout=30)
    at.slider(key='period').set_range(1981,2024).run(timeout=30)
    at.selectbox(key='variable').set_value('t2m').run(timeout=30)
    assert not at.exception
    assert not at.get('plotly_chart')  # Nothing is loaded or rendered before explicit user request.
    at.button(key='load_temperature').click().run(timeout=30)
    assert not at.exception
    assert 'temperature_history' in [e.key for e in at.get('plotly_chart')]


def test_map_inference_values_match_selected_methods_at_actual_coordinates():
    years=np.arange(1981,2021)
    values=100+np.arange(40)*.8+8*np.sin(np.arange(40)/2)
    annual=xr.DataArray(np.stack([values,values*.5],axis=-1)[:,None,:],dims=('year','lat','lon'),
                        coords={'year':years,'lat':[31.25],'lon':[-6.25,-3.75]})
    pvalues=[]
    for method in ['OLS','Newey–West HAC','Modified Mann–Kendall']:
        mapped=inference_grid(annual,method)
        selected=analyze_trend(years,values,method=method)
        assert float(mapped.sel(lat=31.25,lon=-6.25,stat='p'))==pytest.approx(selected['p'])
        assert float(mapped.sel(lat=31.25,lon=-6.25,stat='decade'))==pytest.approx(selected['decade'])
        pvalues.append(selected['p'])
    assert not np.isclose(pvalues[0],pvalues[1],atol=1e-12)


def test_modified_mk_p_value_is_independent_of_user_decision_threshold():
    years=np.arange(1981,2021)
    y=100+np.arange(40)*.8+8*np.sin(np.arange(40)/2)
    a=analyze_trend(years,y,alpha=.01,method='Modified Mann–Kendall')
    b=analyze_trend(years,y,alpha=.10,method='Modified Mann–Kendall')
    assert a['p']==pytest.approx(b['p'])
