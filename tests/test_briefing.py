"""Test recent-condition explanations independently of environmental measurements."""
import numpy as np
import xarray as xr
import pytest
from saharawatch.briefing import recent_assessment,assessment_text,deficit_footprint
from saharawatch.data import ROOT,RAW,load_data,country_mask,regional_series,boundaries
from streamlit.testing.v1 import AppTest


def sample(recent):
    return xr.DataArray(np.r_[np.tile([80.,100.,120.,100.],5),recent],dims='year',coords={'year':np.arange(2001,2024)})


def test_persistent_deficit_has_clear_conclusion_and_correct_accumulation():
    r=recent_assessment(sample([60,70,80]),2023,3,2001,2020)
    assert r['status']=='Persistent rainfall deficit'
    assert r['total_mm']==210 and r['expected_mm']==300
    assert r['departure_pct']==-30 and r['dry_years']==3
    assert r['reference_windows']==18 and r['historical_percentile']==0
    text=assessment_text('Example',r)
    assert 'every year in 2021–2023 was drier' in text
    assert '30.0% below' in text and 'lower than every one' in text


def test_mixed_and_wet_periods_are_not_called_persistent_deficits():
    mixed=recent_assessment(sample([50,130,90]),2023,3,2001,2020)
    assert mixed['status']=='Multi-year rainfall deficit' and mixed['dry_years']==2
    assert 'did not persist in every year' in assessment_text('Example',mixed)
    wet=recent_assessment(sample([80,140,150]),2023,3,2001,2020)
    assert wet['status']=='No multi-year rainfall deficit' and wet['dry_years']==1
    assert 'did not show an overall rainfall deficit' in assessment_text('Example',wet)


def test_missing_recent_year_is_not_skipped_or_extrapolated():
    full=sample([60,70,80]).drop_sel(year=2022)
    r=recent_assessment(full,2023,3,2001,2020)
    assert r['status']=='Insufficient data' and r['valid_recent_years']==2
    assert np.isnan(r['total_mm']) and r['dry_years'] is None
    assert 'not extrapolated' in assessment_text('Example',r)


def test_reference_windows_respect_baseline_and_do_not_bridge_missing_years():
    full=sample([60,70,80]);full.loc[dict(year=2010)]=np.nan
    r=recent_assessment(full,2023,3,2001,2020)
    assert r['reference_windows']==15  # Three overlapping windows touch the missing year.
    assert r['expected_mm']==pytest.approx(float(full.sel(year=slice(2001,2020)).mean())*3)
    with pytest.raises(ValueError):recent_assessment(full,2023,3,2020,2001)


def test_arid_and_constant_baselines_withhold_unstable_metrics():
    full=sample([0,0,0])*0
    r=recent_assessment(full,2023,3,2001,2020)
    assert r['status']=='No multi-year rainfall deficit'
    assert np.isnan(r['departure_pct']) and np.isnan(r['historical_percentile'])
    assert r['severe_years'] is None
    r=recent_assessment(sample([60,70,80]),2023,3,2001,2010)
    assert np.isnan(r['historical_percentile'])  # Only eight baseline three-year windows.
    assert recent_assessment(sample([60,70,80]),2023,3,2001,2009)['status']=='Insufficient data'


def test_spatial_footprint_reports_valid_coverage_and_weighted_dry_area():
    years=np.arange(2001,2024)
    values=np.full((23,1,2),100.)
    values[-3:,0,:]=[50.,150.]
    annual=xr.DataArray(values,dims=('year','lat','lon'),coords={'year':years,'lat':[31.25],'lon':[-6.25,-3.75]})
    weights=xr.DataArray([[3.,1.]],dims=('lat','lon'),coords={'lat':annual.lat,'lon':annual.lon})
    result=deficit_footprint(annual,weights,2023,3,2001,2020)
    assert result['deficit_area_pct']==75 and result['coverage_pct']==100
    annual.values[-1,0,1]=np.nan
    result=deficit_footprint(annual,weights,2023,3,2001,2020)
    assert result['deficit_area_pct']==100 and result['coverage_pct']==75


@pytest.mark.skipif(not RAW.exists(),reason='Requires real GPCP')
def test_real_morocco_and_saudi_briefings_use_last_complete_years():
    _,annual,_=load_data()
    results={}
    for country in ['Morocco','Saudi Arabia']:
        series=regional_series(annual,country_mask(annual,boundaries()[country]))
        r=recent_assessment(series,2025,3,2001,2020)
        reference=float(series.sel(year=slice(2001,2020)).mean())*3
        observed=float(series.sel(year=slice(2023,2025)).sum())
        assert r['departure_pct']==pytest.approx(100*(observed-reference)/reference)
        results[country]=r
    assert results['Morocco']['status']=='Persistent rainfall deficit'
    assert results['Saudi Arabia']['status']=='No multi-year rainfall deficit'


@pytest.mark.skipif(not RAW.exists(),reason='Requires real GPCP')
def test_country_briefing_controls_and_pinned_context():
    at=AppTest.from_file(ROOT/'app.py').run(timeout=30)
    assert not at.exception
    assert at.selectbox(key='brief_end').value==2025
    assert at.selectbox(key='brief_length').value==3
    at.selectbox(key='brief_country').set_value('Saudi Arabia').run(timeout=30)
    assert not at.exception
    assert at.radio(key='mode').value=='Country aggregation'
    assert at.selectbox(key='country').value=='Saudi Arabia'
    at.button(key='pin_evidence').click().run(timeout=30)
    briefing=at.session_state['clues'][-1]['recent_country_briefing']
    assert briefing['country']=='Saudi Arabia' and briefing['recent_end']==2025
    assert briefing['status']=='No multi-year rainfall deficit'
    at.selectbox(key='brief_length').set_value(5).run(timeout=30)
    assert not at.exception
    assert at.session_state['clues'][-1]['recent_country_briefing']==briefing


def test_explanation_distinguishes_recent_recovery_from_persistent_deficit():
    r=recent_assessment(sample([60,70,80]),2023,3,2001,2020)
    text=assessment_text('Example',r)
    assert r['status']=='Persistent rainfall deficit'
    assert '2023 increased to 80.0 mm from 70.0 mm in 2022' in text
    assert 'below the 100.0 mm baseline annual mean' in text


def test_no_cumulative_deficit_does_not_hide_a_dry_latest_year():
    r=recent_assessment(sample([180,150,50]),2023,3,2001,2020)
    text=assessment_text('Example',r)
    assert r['status']=='No multi-year rainfall deficit'
    assert '2023 decreased to 50.0 mm from 150.0 mm in 2022' in text
    assert 'below the 100.0 mm baseline annual mean' in text
