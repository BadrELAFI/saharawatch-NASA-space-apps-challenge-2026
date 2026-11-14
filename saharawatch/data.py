"""Validate GPCP monthly rates and preserve missingness through aggregation."""
from pathlib import Path
import json
import numpy as np
import pandas as pd
import xarray as xr
from shapely.geometry import Point, shape

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / 'data/raw/precip.mon.mean.nc'
SOURCE = 'https://psl.noaa.gov/thredds/fileServer/Datasets/gpcp/precip.mon.mean.nc'
EXTENT = (-18, 63, 10, 43)
VARIABLES = {'precip': {'label': 'Precipitation', 'monthly_units': 'mm', 'annual_units': 'mm/year', 'aggregation': 'sum'}}


def normalize_longitude(data):
    return data.assign_coords(lon=((data.lon + 180) % 360) - 180).sortby('lon').sortby('lat')


def validate(ds: xr.Dataset) -> xr.DataArray:
    candidates = [name for name, var in ds.data_vars.items()
                  if name == 'precip' or var.attrs.get('standard_name') == 'precipitation_flux']
    if len(candidates) != 1:
        raise ValueError(f'Expected one precipitation variable; found {list(ds.data_vars)}.')
    rate = ds[candidates[0]]
    if set(rate.dims) != {'time', 'lat', 'lon'}:
        raise ValueError(f'Expected time, lat, lon dimensions; found {rate.dims}.')
    if rate.attrs.get('units', '').strip().lower() not in {'mm/day', 'mm/d', 'mm day-1'}:
        raise ValueError(f'Unsupported precipitation units: {rate.attrs.get("units")!r}; expected mm/day.')
    for coord in ('lat', 'lon'):
        values = rate[coord].values
        if values.ndim != 1 or len(values) < 2 or not np.isfinite(values).all() or len(np.unique(values)) != len(values):
            raise ValueError(f'Invalid {coord} coordinates.')
        if not np.allclose(np.diff(np.sort(values)), 2.5):
            raise ValueError(f'{coord} does not have the expected GPCP 2.5° resolution.')
    if np.any(np.abs(rate.lat.values) > 90) or np.any(rate.lon.values < -180) or np.any(rate.lon.values > 360):
        raise ValueError('Coordinates outside geographic bounds.')
    dates = pd.DatetimeIndex(rate.time.values)
    periods = dates.to_period('M')
    if dates.hasnans or not dates.is_monotonic_increasing or periods.has_duplicates:
        raise ValueError('Monthly timestamps must be unique and increasing.')
    if len(dates) < 12:
        raise ValueError('At least twelve monthly observations are required.')
    return rate.transpose('time', 'lat', 'lon')


def monthly_totals(rate: xr.DataArray) -> xr.DataArray:
    valid_range = rate.attrs.get('valid_range', [0, np.inf])
    clean = rate.where(np.isfinite(rate) & (rate >= max(0, valid_range[0])) & (rate <= valid_range[1]))
    totals = clean * clean.time.dt.days_in_month
    totals.attrs = {'units': 'mm', 'long_name': 'Monthly accumulated precipitation'}
    return totals


def annual_totals(monthly: xr.DataArray) -> xr.DataArray:
    # Count per cell, not just per time axis: one missing month invalidates its year.
    grouped = monthly.groupby('time.year')
    annual = grouped.sum('time', skipna=True).where(grouped.count('time') == 12)
    annual.attrs = {'units': 'mm/year', 'long_name': 'Complete-year precipitation total'}
    return annual


def load_data(path=RAW):
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError('GPCP file missing. Run: python scripts/prepare_data.py')
    try:
        with xr.open_dataset(path, drop_variables=['time_bnds']) as ds:
            rate = validate(ds)
            metadata = {'source': SOURCE, 'title': ds.attrs.get('title', ''),
                        'version': ds.attrs.get('version', ds.attrs.get('source', 'See dataset attributes')),
                        'attributes': dict(ds.attrs), 'variable_attributes': dict(rate.attrs),
                        'dimensions': dict(ds.sizes), 'start': str(rate.time.values[0])[:10],
                        'end': str(rate.time.values[-1])[:10]}
            normalized = normalize_longitude(rate)
            subset = normalized.sel(lat=slice(10, 43), lon=slice(-18, 63)).load()
    except (OSError, TypeError) as exc:
        raise ValueError(f'Cannot read GPCP NetCDF: {exc}') from exc
    if not subset.sizes['lat'] or not subset.sizes['lon']:
        raise ValueError('The dataset does not cover MENA.')
    monthly = monthly_totals(subset)
    return monthly, annual_totals(monthly), metadata


def complete_years(monthly):
    dates = pd.DatetimeIndex(monthly.time.values)
    counts = pd.Series(1, index=dates).groupby(dates.year).sum()
    return [int(year) for year, count in counts.items() if count == 12]


def select_period(annual, start, end):
    if start >= end:
        raise ValueError('Start year must be before end year.')
    selected = annual.sel(year=slice(start, end))
    if selected.sizes['year'] != end - start + 1:
        raise ValueError('Requested years are unavailable.')
    return selected


def boundaries():
    path = ROOT / 'data/boundaries/countries.geojson'
    if not path.exists():
        return {}
    features = json.loads(path.read_text())['features']
    wanted = ['Morocco', 'Algeria', 'Tunisia', 'Libya', 'Egypt', 'Mauritania',
              'Saudi Arabia', 'Jordan', 'Iraq', 'Iran', 'United Arab Emirates']
    return {f['properties']['ADMIN']: f for f in features if f['properties']['ADMIN'] in wanted}


def country_mask(data, feature):
    geometry = shape(feature['geometry'])
    return xr.DataArray([[geometry.covers(Point(float(lon), float(lat))) for lon in data.lon.values]
                         for lat in data.lat.values], coords={'lat': data.lat, 'lon': data.lon}, dims=('lat', 'lon'))


def regional_series(data, mask):
    """Fixed mask and weights; a missing member makes the regional value missing."""
    n = int(mask.sum())
    if n == 0:
        raise ValueError('No GPCP cell centers inside this boundary. Select a grid cell instead.')
    weights = np.cos(np.deg2rad(data.lat)).broadcast_like(mask).where(mask, 0)
    result = (data.where(mask) * weights).sum(('lat', 'lon'), skipna=True) / weights.sum()
    return result.where(data.where(mask).count(('lat', 'lon')) == n)


def grid_series(data, lat, lon):
    if not 10 <= lat <= 43 or not -18 <= lon <= 63:
        raise ValueError('Coordinates must be inside the MENA study extent.')
    return data.sel(lat=lat, lon=lon, method='nearest')
