"""Scientific fixtures are test-only; application series come from real GPCP."""
import warnings
import numpy as np
import pandas as pd
import pytest
import xarray as xr
from scipy import stats
from climate_indices import compute, indices
from saharawatch.drought import anomaly_statistics, negative_anomaly_frequency, spi_series
from saharawatch.data import RAW, load_data, grid_series, regional_series, country_mask, boundaries


def monthly_fixture():
    rng=np.random.default_rng(125)
    y=rng.gamma(2.,20.,45*12)
    # Full dry years exercise the discrete zero-mass correction at both scales.
    for year in [1983,1994,2005,2016]:
        y[(year-1980)*12:(year-1979)*12]=0
    return xr.DataArray(y,coords={'time':pd.date_range('1980-01-01',periods=y.size,freq='MS')},dims='time',attrs={'units':'mm'})


def test_monthly_departures_group_by_calendar_month_and_guard_relative():
    times=pd.date_range('2001-01-01',periods=21*12,freq='MS')
    values=np.tile(np.arange(1,13)*10.,21)
    values[-12:]+=10
    m=xr.DataArray(values,coords={'time':times},dims='time',attrs={'units':'mm'})
    got=anomaly_statistics(m,2001,2020)
    assert float(got.expected.sel(time='2021-01-01'))==10
    assert float(got.expected.sel(time='2021-07-01'))==70
    assert float(got.relative_anomaly.sel(time='2021-01-01'))==100
    assert float(got.anomaly.sel(time='2021-07-01'))==10
    assert np.isnan(got.standardized_anomaly).all()  # Calendar-month baseline is constant.
    m.values[:]=0.5
    assert np.isnan(anomaly_statistics(m,2001,2020).relative_anomaly).all()


def test_annual_departures_baseline_sample_std_and_insufficient():
    a=xr.DataArray(np.arange(20.)*10,coords={'year':np.arange(2001,2021)},dims='year')
    got=anomaly_statistics(a,2001,2010)
    assert float(got.expected)==45
    assert float(got.relative_anomaly.sel(year=2020))==pytest.approx(100*145/45)
    assert float(got.standardized_anomaly.sel(year=2001))==pytest.approx(-45/np.std(np.arange(10)*10,ddof=1))
    assert np.isnan(anomaly_statistics(a,2001,2009).anomaly).all()
    assert np.isnan(anomaly_statistics(a*0,2001,2010).relative_anomaly).all()
    with pytest.raises(ValueError): anomaly_statistics(a,1990,2020)


def test_frequency_denominator_omits_missing_and_threshold_is_inclusive():
    z=xr.DataArray([-2.,-1.5,-1.,np.nan,np.inf,1.])
    result=negative_anomaly_frequency(z,-1.5)
    assert result['count']==2 and result['valid']==4 and result['percent']==50
    assert np.isnan(negative_anomaly_frequency(xr.DataArray([np.nan]))['percent'])
    with pytest.raises(ValueError): negative_anomaly_frequency(z,0)


@pytest.mark.parametrize('scale',[3,12])
def test_spi_matches_library_and_independent_gamma_reference(scale):
    m=monthly_fixture()
    got=spi_series(m,scale,1981,2020)
    assert bool(got.eligible_month.any())
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter('always')
        direct=indices.spi(m.values.copy(),scale,indices.Distribution.gamma,1980,1981,2020,compute.Periodicity.monthly)
    if scale==12:
        assert any('goodness-of-fit' in str(w.message) for w in caught)
        assert not bool(got.eligible_month.all())
    allowed=got.eligible_month.sel(month=got.time.dt.month).values
    direct=np.where(allowed,direct,np.nan)
    np.testing.assert_allclose(got.spi.values,direct,atol=1e-10,equal_nan=True)
    accumulated=pd.Series(m.values,index=pd.DatetimeIndex(m.time.values)).rolling(scale,min_periods=scale).sum()
    expected=np.full(len(m),np.nan)
    for month in range(1,13):
        calibration=accumulated.loc['1981':'2020']
        calibration=calibration[calibration.index.month==month].dropna().values
        p0=np.mean(calibration==0)
        positives=calibration[calibration>0]
        # Independent Thom gamma-shape approximation used by the reference package.
        mean=positives.mean()
        a=np.log(mean)-np.log(positives).mean()
        alpha=(1+np.sqrt(1+4*a/3))/(4*a)
        beta=mean/alpha
        positions=accumulated.index.month==month
        p=p0+(1-p0)*stats.gamma.cdf(accumulated.values[positions],a=alpha,scale=beta)
        expected[positions]=np.clip(stats.norm.ppf(p),-3.09,3.09)
    expected=np.where(allowed,expected,np.nan)
    np.testing.assert_allclose(got.spi.values,expected,atol=1e-8,equal_nan=True)
    assert np.isnan(got.spi.values[~allowed]).all()
    assert np.isnan(got.spi.values[:scale-1]).all()


def test_spi_does_not_bridge_missing_month_and_keeps_antecedent_rain():
    m=monthly_fixture().drop_sel(time=pd.Timestamp('2023-03-01'))
    got=spi_series(m,3,1981,2020)
    assert np.isnan(got.spi.sel(time=slice('2023-03-01','2023-05-01'))).all()
    assert np.isfinite(got.spi.sel(time='2023-06-01'))
    # January 2021 must retain November and December 2020 when accumulating.
    original=monthly_fixture()
    expected=float(original.sel(time=slice('2020-11-01','2021-01-01')).sum())
    assert float(got.accumulation_mm.sel(time='2021-01-01'))==pytest.approx(expected)


def test_spi_refuses_short_baseline_and_degenerate_data():
    m=monthly_fixture()
    with pytest.raises(ValueError,match='30'): spi_series(m,3,2001,2020)
    with pytest.raises(ValueError,match='covered'): spi_series(m,3,1970,2000)
    with pytest.raises(ValueError,match='mm'): spi_series(m.assign_attrs(units='mm/day'),3,1981,2020)
    zeros=spi_series(xr.zeros_like(m),12,1981,2020)
    assert np.isnan(zeros.spi).all() and not bool(zeros.eligible_month.any())
    constant=spi_series(xr.ones_like(m),3,1981,2020)
    assert np.isnan(constant.spi).all()


@pytest.mark.skipif(not RAW.exists(),reason='Requires real downloaded GPCP')
def test_spi_real_gpcp_grid_and_country():
    m,_,_=load_data()
    for s in [grid_series(m,31.25,-6.25),regional_series(m,country_mask(m,boundaries()['Morocco']))]:
        assert s.attrs['units']=='mm'
        for scale in [3,12]:
            got=spi_series(s,scale,1981,2010)
            assert got.eligible_month.all()
            assert np.isfinite(got.spi.sel(time=slice('2001','2024'))).all()
            direct=indices.spi(s.values.copy(),scale,indices.Distribution.gamma,1979,1981,2010,compute.Periodicity.monthly)
            np.testing.assert_allclose(got.spi.values,direct,atol=1e-10,equal_nan=True)
