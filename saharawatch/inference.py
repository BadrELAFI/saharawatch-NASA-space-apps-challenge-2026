"""Named inference methods and paired regional slope-difference testing."""
import warnings
import numpy as np
import xarray as xr
import pymannkendall as mk
from .analysis import trend, MIN_TREND_YEARS, NEAR_ZERO_MM
from .trend_diagnostics import hac_trend

METHODS=['OLS','Newey–West HAC','Modified Mann–Kendall']


def mann_kendall_trend(years,values,alpha=.05):
    x,y=np.asarray(years,float),np.asarray(values,float)
    valid=np.isfinite(x)&np.isfinite(y);x,y=x[valid],y[valid]
    base=dict(trend(x,y,alpha),method=METHODS[2],line_label='Sen slope',reason='')
    base.update(low=np.nan,high=np.nan)
    if len(y)<MIN_TREND_YEARS or not np.all(np.diff(x)==1):
        base.update(p=np.nan,slope=np.nan,decade=np.nan,intercept=np.nan,relative=np.nan,change=np.nan,
                    status='Insufficient data',reason='Modified MK requires ten consecutive valid annual observations.')
        return base
    if np.ptp(y)==0:
        base.update(p=1.,slope=0.,decade=0.,intercept=float(y[0]),relative=0. if y.mean()>=NEAR_ZERO_MM else np.nan,change=0.,tau=0.,variance=0.)
        return base
    with warnings.catch_warnings(record=True):
        warnings.simplefilter('always')
        # Keep the autocorrelation screen fixed so displayed p-values do not change with the decision threshold.
        fit=mk.hamed_rao_modification_test(y,alpha=.05,lag=min(3,len(y)-1))
    slope=float(fit.slope)
    p=float(fit.p) if np.isfinite(fit.var_s) and fit.var_s>0 else np.nan
    base.update(slope=slope,decade=slope*10,intercept=float(fit.intercept-slope*x[0]),
                relative=100*slope*10/y.mean() if y.mean()>=NEAR_ZERO_MM else np.nan,
                change=slope*(x[-1]-x[0]),p=p,tau=float(fit.Tau),variance=float(fit.var_s))
    base['status']=('Insufficient data' if not np.isfinite(p) else
                    ('Statistically significant increase' if slope>0 else 'Statistically significant decrease')
                    if p<alpha else 'No statistically significant trend detected')
    if not np.isfinite(p): base['reason']='The modified variance is invalid; no significance result is reported.'
    return base


def analyze_trend(years,values,alpha=.05,method='OLS'):
    if method==METHODS[0]:return dict(trend(years,values,alpha),method=method,reason='')
    if method==METHODS[1]:return hac_trend(years,values,alpha)
    if method==METHODS[2]:return mann_kendall_trend(years,values,alpha)
    raise ValueError('Unknown inference method.')


def inference_grid(annual,method='OLS'):
    def fit(y):
        r=analyze_trend(annual.year.values,y,method=method)
        return np.array([r[k] for k in ['decade','p','relative']])
    return xr.apply_ufunc(fit,annual,input_core_dims=[['year']],output_core_dims=[['stat']],vectorize=True).assign_coords(stat=['decade','p','relative'])


def slope_difference(first,second,alpha=.05):
    """Fit first-minus-second over common years, preserving cross-region covariance."""
    a,b=xr.align(first,second,join='inner')
    result=hac_trend(a.year.values,(a-b).values,alpha)
    result['comparison']='First minus second, common-year OLS slope difference with Newey–West HAC'
    return result
