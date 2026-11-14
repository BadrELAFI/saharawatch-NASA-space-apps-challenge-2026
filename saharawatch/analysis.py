"""OLS inference on annual totals and baseline anomalies; no synthetic observations."""
import numpy as np
import xarray as xr
from scipy import stats

MIN_TREND_YEARS = 10
MIN_BASELINE_YEARS = 10
NEAR_ZERO_MM = 10.0


def trend(years, values, alpha=0.05):
    x, y = np.asarray(years, float), np.asarray(values, float)
    valid = np.isfinite(x) & np.isfinite(y)
    x, y = x[valid], y[valid]
    n = len(y)
    empty = dict(n=n, mean=float(np.mean(y)) if n else np.nan, slope=np.nan, intercept=np.nan,
                 decade=np.nan, relative=np.nan, p=np.nan, low=np.nan, high=np.nan,
                 change=np.nan, lag1=np.nan, status='Insufficient data')
    if n < MIN_TREND_YEARS or len(np.unique(x)) != n:
        return empty
    if np.ptp(y) == 0:
        slope, intercept, p, stderr = 0., float(y[0]), 1., 0.
    else:
        fit = stats.linregress(x, y)
        slope, intercept, p, stderr = fit.slope, fit.intercept, fit.pvalue, fit.stderr
    margin = stats.t.ppf(0.975, n - 2) * stderr
    residual = y - (intercept + slope * x)
    lag1 = np.nan
    if np.std(residual) > 1e-9 and np.all(np.diff(x) == 1):
        lag1 = float(np.corrcoef(residual[:-1], residual[1:])[0, 1])
    status = ('Statistically significant increase' if slope > 0 else 'Statistically significant decrease') if p < alpha else 'No statistically significant trend detected'
    return dict(n=n, mean=float(y.mean()), slope=float(slope), intercept=float(intercept),
                decade=float(slope * 10), relative=float(100 * slope * 10 / y.mean()) if y.mean() >= NEAR_ZERO_MM else np.nan,
                p=float(p), low=float((slope-margin)*10), high=float((slope+margin)*10),
                change=float(slope*(x[-1]-x[0])), lag1=lag1, status=status)


def trend_grid(annual):
    def calculate(y):
        result = trend(annual.year.values, y)
        return np.array([result[k] for k in ('decade', 'p', 'relative')])
    return xr.apply_ufunc(calculate, annual, input_core_dims=[['year']], output_core_dims=[['stat']],
                          vectorize=True).assign_coords(stat=['decade', 'p', 'relative'])


def fdr_bh(pvalues, alpha=0.05):
    """Benjamini–Hochberg over finite p-values only, maintaining original shape."""
    p = np.asarray(pvalues, float)
    finite = np.isfinite(p)
    values = p[finite]
    sig = np.zeros(p.shape, dtype=bool)
    if not values.size:
        return sig
    ordered = np.sort(values)
    accepted = ordered <= alpha * np.arange(1, len(values)+1) / len(values)
    if accepted.any():
        sig[finite] = values <= ordered[np.flatnonzero(accepted)[-1]]
    return sig


def annual_anomalies(annual, baseline_start, baseline_end):
    baseline = annual.sel(year=slice(baseline_start, baseline_end))
    if baseline_start >= baseline_end:
        raise ValueError('Baseline start must be before baseline end.')
    if baseline.sizes['year'] != baseline_end - baseline_start + 1:
        raise ValueError('Baseline years are unavailable.')
    enough = baseline.count('year') >= MIN_BASELINE_YEARS
    mean = baseline.mean('year').where(enough)
    std = baseline.std('year', ddof=1).where(enough)
    anomaly = annual - mean
    z = anomaly / std.where(std > 1e-9)
    return anomaly, z, mean


def monthly_anomalies(monthly, baseline_start, baseline_end):
    base = monthly.sel(time=slice(f'{baseline_start}-01-01', f'{baseline_end}-12-31'))
    grouped = base.groupby('time.month')
    mean = grouped.mean('time').where(grouped.count('time') >= MIN_BASELINE_YEARS)
    return monthly.groupby('time.month') - mean
