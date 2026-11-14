"""Precipitation departures and validated SPI; these are distinct indicators."""
import warnings
import numpy as np
import pandas as pd
import xarray as xr
from .analysis import MIN_BASELINE_YEARS

MIN_SPI_YEARS = 30
MIN_SPI_POSITIVE = 20


def anomaly_statistics(data: xr.DataArray, start: int, end: int) -> xr.Dataset:
    """Compare annual totals or monthly accumulations with a fixed reference period."""
    if start >= end:
        raise ValueError('Baseline start must be before baseline end.')
    monthly = 'time' in data.dims
    dim = 'time' if monthly else 'year'
    available = data.time.dt.year.values if monthly else data.year.values
    if start < available.min() or end > available.max():
        raise ValueError('Baseline years are unavailable.')
    if monthly:
        base = data.sel(time=slice(f'{start}-01-01',f'{end}-12-31')).groupby('time.month')
        mean, std, count = base.mean('time'), base.std('time',ddof=1), base.count('time')
        # Label-based selection aligns each observation with its calendar month.
        month = data.time.dt.month
        mean, std, count = (a.reindex(month=np.arange(1,13)).sel(month=month) for a in (mean,std,count))
    else:
        base = data.sel(year=slice(start,end))
        if base.sizes['year'] != end-start+1:
            raise ValueError('Baseline years are unavailable.')
        mean, std, count = base.mean(dim), base.std(dim,ddof=1), base.count(dim)
    enough = count >= MIN_BASELINE_YEARS
    mean = mean.where(enough)
    std = std.where(enough)
    anomaly = data-mean
    # Explicit stability policy: 1 mm/month or 10 mm/year minimum expected rainfall.
    minimum = 1. if monthly else 10.
    relative = 100*anomaly/mean.where(mean >= minimum)
    standardized = anomaly/std.where(std>1e-9)
    result = xr.Dataset(dict(observed=data,expected=mean,anomaly=anomaly,
                             relative_anomaly=relative,standardized_anomaly=standardized,baseline_count=count))
    result.attrs.update(baseline_start=start,baseline_end=end,relative_minimum_mm=minimum,
                        standardized_definition='(observed - baseline mean) / baseline sample standard deviation; not SPI')
    for name in ['observed','expected','anomaly']:
        result[name].attrs['units']='mm'
    result.relative_anomaly.attrs['units']='%'
    result.standardized_anomaly.attrs['units']='1'
    return result


def negative_anomaly_frequency(z: xr.DataArray, threshold: float = -1.5) -> dict:
    """Only valid observations enter the denominator; missing is never a non-event."""
    if not np.isfinite(threshold) or threshold >= 0:
        raise ValueError('The negative-anomaly threshold must be finite and below zero.')
    values = np.asarray(z.values,float)
    valid = np.isfinite(values)
    n = int(valid.sum())
    count = int(np.sum(values[valid] <= threshold))
    return dict(count=count,valid=n,percent=100*count/n if n else np.nan,threshold=threshold)


def spi_series(monthly: xr.DataArray, scale: int, start: int, end: int) -> xr.Dataset:
    """Gamma SPI via climate-indices, with per-calendar-month reliability gates.

    Accumulation precedes calibration slicing, so antecedent months are retained.
    Skipped timestamps are reindexed as missing months, never joined into one window.
    """
    from climate_indices import compute, indices
    if monthly.dims != ('time',) or monthly.attrs.get('units') != 'mm':
        raise ValueError('SPI needs a single monthly accumulated precipitation series in mm.')
    if scale not in (3,12):
        raise ValueError('Supported SPI accumulation scales are 3 and 12 months.')
    if start>end or end-start+1<MIN_SPI_YEARS:
        raise ValueError('SPI requires a calibration period of at least 30 years.')
    dates=pd.DatetimeIndex(monthly.time.values)
    if not dates.is_monotonic_increasing or dates.to_period('M').has_duplicates:
        raise ValueError('SPI timestamps must be unique, chronological monthly observations.')
    if start<dates[0].year or end>dates[-1].year or (end==dates[-1].year and dates[-1].month<12):
        raise ValueError('SPI calibration must be fully covered by the monthly record.')
    # Normalize labels to month starts, pad the first year, and expose temporal gaps.
    aligned=monthly.assign_coords(time=dates.to_period('M').to_timestamp()).reindex(
        time=pd.date_range(f'{dates[0].year}-01-01',dates[-1].to_period('M').to_timestamp(),freq='MS'))
    aligned=aligned.where(np.isfinite(aligned)&(aligned>=0))
    accumulated=aligned.rolling(time=scale,min_periods=scale).sum()
    calibration=accumulated.sel(time=slice(f'{start}-01-01',f'{end}-12-31'))
    grouped=calibration.groupby('time.month')
    count=grouped.count('time').reindex(month=np.arange(1,13),fill_value=0)
    positive=(calibration>0).groupby('time.month').sum('time').reindex(month=np.arange(1,13),fill_value=0)
    positive_std=calibration.where(calibration>0).groupby('time.month').std('time',ddof=1).reindex(month=np.arange(1,13))
    eligible=(count>=MIN_SPI_YEARS)&(positive>=MIN_SPI_POSITIVE)&(positive_std>1e-9)
    score=np.full(aligned.size,np.nan)
    messages=[]
    fit_p=np.full(12,np.nan)
    if bool(eligible.any()):
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter('always')
            diagnostics=indices.fit_diagnostics(aligned.values.copy(),scale,indices.Distribution.gamma,
                int(aligned.time.dt.year.values[0]),start,end,compute.Periodicity.monthly)
            fit_p=np.asarray(diagnostics.ks_p_value)
            eligible=eligible & xr.DataArray(np.isfinite(fit_p)&(fit_p>=.05),coords={'month':np.arange(1,13)},dims='month')
            score=np.asarray(indices.spi(aligned.values.copy(),scale,indices.Distribution.gamma,
                int(aligned.time.dt.year.values[0]),start,end,compute.Periodicity.monthly,
                zero_handling='classic'),float)
        messages=sorted(set(str(w.message) for w in caught))
    result=xr.DataArray(score,coords={'time':aligned.time},dims='time').where(
        eligible.sel(month=aligned.time.dt.month) & np.isfinite(accumulated))
    if 'month' in result.coords:
        result=result.drop_vars('month')
    ds=xr.Dataset(dict(spi=result,accumulation_mm=accumulated,calibration_count=count,
                       positive_count=positive,eligible_month=eligible,
                       fit_ks_p=xr.DataArray(fit_p,coords={'month':np.arange(1,13)},dims='month')))
    ds.attrs.update(scale_months=scale,calibration_start=start,calibration_end=end,
                    method='climate-indices 3.1.0 gamma; classic calibration zero probability; clipped to ±3.09',
                    warnings='; '.join(messages))
    return ds
