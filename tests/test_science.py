"""Synthetic fixtures verify calculations; dashboard observations always come from GPCP."""
import numpy as np
import pandas as pd
import pytest
import xarray as xr
from scipy import stats
from saharawatch.data import (monthly_totals, annual_totals, normalize_longitude, regional_series,
                              grid_series, validate, load_data, RAW, select_period, country_mask, boundaries)
from saharawatch.analysis import trend, trend_grid, annual_anomalies, monthly_anomalies, fdr_bh


def rates(start='2000-01-01',months=24):
    return xr.DataArray(np.full((months,2,2),2.),dims=('time','lat','lon'),
                        coords={'time':pd.date_range(start,periods=months,freq='MS'),'lat':[11.25,13.75],'lon':[1.25,3.75]},attrs={'units':'mm/day'})


def test_calendar_conversion_and_complete_years():
    m = monthly_totals(rates())
    assert float(m.sel(time='2000-04-01')[0,0]) == 60
    assert float(m.sel(time='2000-02-01')[0,0]) == 58
    a = annual_totals(m)
    np.testing.assert_allclose(a.sel(year=2000),732)
    np.testing.assert_allclose(a.sel(year=2001),730)


def test_missing_month_and_invalid_values_do_not_become_zero():
    r = rates(); r.values[1,0,0]=np.nan; r.values[2,0,1]=-1
    r.attrs['valid_range']=[0,100]; r.values[3,1,0]=999
    a = annual_totals(monthly_totals(r))
    assert np.isnan(a.sel(year=2000).values[0,0])
    assert np.isnan(a.sel(year=2000).values[0,1])
    assert np.isnan(a.sel(year=2000).values[1,0])
    assert np.isfinite(a.sel(year=2000).values[1,1])
    a = annual_totals(monthly_totals(rates(months=23)))
    assert np.isnan(a.sel(year=2001)).all()
    a = annual_totals(monthly_totals(rates().drop_sel(time=pd.Timestamp('2000-04-01'))))
    assert np.isnan(a.sel(year=2000)).all()


def test_longitude_normalization_and_nearest_cell():
    r = rates().assign_coords(lon=[351.25,353.75])
    normal = normalize_longitude(r)
    np.testing.assert_equal(normal.lon.values,[-8.75,-6.25])
    assert float(grid_series(normal,12,-6).lon) == -6.25
    assert float(grid_series(normal,12,-6).lat) == 11.25
    with pytest.raises(ValueError): grid_series(normal,0,0)


def test_regression_and_confidence_interval_match_reference():
    x = np.arange(2001,2025)
    y = 400+2*(x-2001)+np.sin(x)*20
    got = trend(x,y)
    expected=stats.linregress(x,y)
    assert got['slope']==pytest.approx(expected.slope)
    assert got['p']==pytest.approx(expected.pvalue)
    margin=stats.t.ppf(.975,len(x)-2)*expected.stderr
    assert got['low']==pytest.approx((expected.slope-margin)*10)
    assert got['high']==pytest.approx((expected.slope+margin)*10)
    assert got['change']==pytest.approx(expected.slope*23)


def test_known_slope_constant_and_insufficient():
    x=np.arange(1980,2000)
    assert trend(x,3*(x-1980)+10)['decade']==pytest.approx(30)
    constant=trend(x,np.ones(20))
    assert constant['p']==1 and constant['slope']==0
    assert constant['status']=='No statistically significant trend detected'
    assert trend(x[:9],np.ones(9))['status']=='Insufficient data'
    assert np.isnan(trend(x,np.zeros(20))['relative'])
    missing=np.full(20,np.nan)
    assert trend(x,missing)['n']==0


def test_area_weighting_and_fixed_membership():
    d=xr.DataArray([[10.,20.],[30.,40.]],dims=('lat','lon'),coords={'lat':[10.,60.],'lon':[0,1]})
    mask=xr.ones_like(d,dtype=bool)
    got=float(regional_series(d,mask))
    w=np.cos(np.deg2rad([10,60]))
    assert got==pytest.approx((15*w[0]+35*w[1])/w.sum())
    d.values[0,0]=np.nan
    assert np.isnan(regional_series(d,mask))
    with pytest.raises(ValueError): regional_series(d,xr.zeros_like(mask))


def test_annual_anomaly_baseline_and_zero_variance():
    a=xr.DataArray(np.arange(20.)*10,dims='year',coords={'year':np.arange(2001,2021)})
    anomaly,z,mean=annual_anomalies(a,2001,2010)
    assert float(mean)==45
    assert float(anomaly.sel(year=2001))==-45
    assert float(anomaly.sel(year=2020))==145
    assert float(z.sel(year=2001))==pytest.approx(-45/np.std(np.arange(10)*10,ddof=1))
    _,z,_=annual_anomalies(xr.ones_like(a),2001,2010)
    assert np.isnan(z).all()
    _,_,mean=annual_anomalies(a,2001,2005)
    assert np.isnan(mean)


def test_monthly_anomalies_compare_same_calendar_month():
    r=rates(months=240)[:,0,0]
    m=monthly_totals(r)
    got=monthly_anomalies(m,2000,2019)
    assert float(got.sel(time='2000-01-01'))==0
    assert float(got.sel(time='2000-04-01'))==0
    # February leap-day differences remain real accumulation differences.
    assert float(got.sel(time='2000-02-01'))>0


def test_bh_and_grid_regression():
    p=np.array([.001,.01,.03,.2,np.nan])
    np.testing.assert_equal(fdr_bh(p),[True,True,True,False,False])
    np.testing.assert_equal(fdr_bh(np.array([np.nan,.8,.9])),[False,False,False])
    annual=annual_totals(monthly_totals(rates(months=240)))
    grid=trend_grid(annual)
    for lat in annual.lat.values:
        for lon in annual.lon.values:
            s=annual.sel(lat=lat,lon=lon)
            assert float(grid.sel(lat=lat,lon=lon,stat='decade'))==pytest.approx(trend(s.year,s)['decade'])


def test_schema_rejects_units_and_duplicate_months():
    ds=rates().to_dataset(name='precip')
    validate(ds)
    ds.precip.attrs['units']='kelvin'
    with pytest.raises(ValueError,match='units'): validate(ds)
    ds=rates().to_dataset(name='precip')
    ds=ds.assign_coords(time=[ds.time.values[0]]*24)
    with pytest.raises(ValueError,match='timestamps'): validate(ds)


@pytest.mark.skipif(not RAW.exists(),reason='Run scripts/prepare_data.py to test real GPCP')
def test_real_gpcp_end_to_end():
    monthly,annual,metadata=load_data()
    assert metadata['version']=='V2.3'
    assert monthly.shape[1:]==(13,32)
    assert -18<=float(monthly.lon.min())<0<float(monthly.lon.max())<=63
    selected=select_period(annual,2001,2024)
    s=grid_series(selected,31.25,-6.25)
    assert np.isfinite(s).all() and s.sizes['year']==24
    result=trend(s.year,s)
    assert result['n']==24 and np.isfinite(result['p'])
    # Independently read raw mm/day, validating the full unit-conversion path.
    with xr.open_dataset(RAW,drop_variables=['time_bnds']) as ds:
        raw=ds.precip.sel(lat=31.25,lon=353.75).sel(time=slice('2001-01-01','2001-12-31'))
        expected=float((raw*raw.time.dt.days_in_month).sum())
    assert float(s.sel(year=2001))==pytest.approx(expected)
    with pytest.raises(ValueError): select_period(annual,2024,2001)


def test_country_mask_uses_polygon_not_bounding_rectangle():
    from shapely.geometry import Polygon, mapping
    d=xr.DataArray(np.ones((2,2)),dims=('lat','lon'),coords={'lat':[0.5,1.5],'lon':[0.5,1.5]})
    feature={'geometry':mapping(Polygon([(0,0),(2,0),(0,2),(0,0)]))}
    mask=country_mask(d,feature)
    assert bool(mask.sel(lat=.5,lon=.5))
    assert not bool(mask.sel(lat=1.5,lon=1.5))


def test_fdr_matches_scipy_reference():
    p=np.array([.0001,.004,.015,.045,.3,.9])
    adjusted=stats.false_discovery_control(p,method='bh')
    np.testing.assert_equal(fdr_bh(p),adjusted<=.05)


def test_malformed_and_missing_files_fail_clearly(tmp_path):
    path=tmp_path/'not-netcdf.nc'
    path.write_text('This is not precipitation data.')
    with pytest.raises(ValueError): load_data(path)
    with pytest.raises(FileNotFoundError,match='prepare_data.py'): load_data(tmp_path/'missing.nc')


@pytest.mark.skipif(not RAW.exists(),reason='Requires downloaded GPCP')
def test_all_requested_country_series_and_incomplete_year():
    from saharawatch.data import complete_years
    monthly,annual,_=load_data()
    countries=boundaries()
    assert len(countries)==11
    for name,feature in countries.items():
        mask=country_mask(annual,feature)
        assert int(mask.sum())>0,name
        series=regional_series(annual,mask).sel(year=slice(2001,2024))
        assert np.isfinite(series).all(),name
        assert trend(series.year,series)['n']==24,name
    if monthly.time.dt.month.values[-1]!=12:
        year=int(monthly.time.dt.year.values[-1])
        assert year not in complete_years(monthly)
        assert np.isnan(annual.sel(year=year)).all()
