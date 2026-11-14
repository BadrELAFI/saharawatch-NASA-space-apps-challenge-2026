"""Explicit alternatives to exploratory independent-residual OLS inference."""
import numpy as np
import pandas as pd
from scipy import stats
import streamlit as st
from statsmodels.regression.linear_model import OLS
from .analysis import trend, MIN_TREND_YEARS


def hac_trend(years, values, alpha=.05, maxlags=None):
    """Newey–West/Bartlett covariance with small-sample correction and t inference.

    A gap in valid calendar years makes positional HAC inappropriate; refuse it.
    """
    x,y=np.asarray(years,float),np.asarray(values,float)
    finite=np.isfinite(x)&np.isfinite(y)
    x,y=x[finite],y[finite]
    base=trend(x,y,alpha)
    result=dict(base,method='OLS with Newey–West HAC',maxlags=None,reason='')
    if len(y)<MIN_TREND_YEARS or not np.all(np.diff(x)==1):
        result.update(p=np.nan,low=np.nan,high=np.nan,status='Insufficient data',
                      reason='HAC requires at least ten valid, consecutive annual observations.')
        return result
    lag=int(np.floor(4*(len(y)/100)**(2/9))) if maxlags is None else maxlags
    if not isinstance(lag,(int,np.integer)) or not 0<=lag<len(y)-2:
        raise ValueError('HAC lag must be an integer between zero and n−3.')
    result['maxlags']=int(lag)
    if np.ptp(y)==0:
        return result
    fit=OLS(y,np.column_stack((np.ones(len(x)),x-x.mean()))).fit(
        cov_type='HAC',cov_kwds={'maxlags':int(lag),'kernel':'bartlett','use_correction':True},use_t=True)
    low,high=fit.conf_int(alpha=.05)[1]*10
    p=float(fit.pvalues[1])
    result.update(p=p,low=float(low),high=float(high),status=(
        'Statistically significant increase' if base['slope']>0 else 'Statistically significant decrease')
        if p<alpha else 'No statistically significant trend detected')
    return result


def render_trend_diagnostics(series, alpha, label):
    with st.expander('Statistical trend diagnostics · Feature 5'):
        ordinary=trend(series.year.values,series.values,alpha)
        robust=hac_trend(series.year.values,series.values,alpha)
        rows=[]
        from .inference import mann_kendall_trend
        modified=mann_kendall_trend(series.year.values,series.values,alpha)
        for name,r in [('OLS · independent residuals',ordinary),('OLS · Newey–West HAC',robust),('Hamed–Rao modified MK · Sen slope',modified)]:
            rows.append(dict(method=name,years=r['n'],slope_mm_decade=r['decade'],p_value=r['p'],
                             ci95_low_mm_decade=r['low'],ci95_high_mm_decade=r['high'],classification=r['status']))
        frame=pd.DataFrame(rows)
        st.dataframe(frame,hide_index=True,width='stretch')
        if robust['reason']:
            st.info(robust['reason'])
        else:
            st.caption(f'HAC lag: {robust["maxlags"]} annual steps. Bartlett kernel; n/(n−2) covariance correction; '
                       'Student-t inference with n−2 degrees of freedom. Default lag = floor(4 × (n/100)^(2/9)). '
                       'This adjusts uncertainty for short-range serial correlation and heteroskedasticity; it does not change the fitted OLS slope or establish causality. '
                       'Small climate samples can still give uncertain inference. The sidebar inference method applies to the atlas, country comparisons, and notebook snapshots. Modified MK adjusts rank-test variance using significant detrended-rank autocorrelations at up to three lags; its Sen slope has no adjusted confidence interval here. Results can be unstable in small samples.')
        finite=np.isfinite(series.values)
        if finite.sum()>=MIN_TREND_YEARS:
            slope=stats.theilslopes(series.values[finite],series.year.values[finite],alpha=.95)
            st.write(f'Theil–Sen outlier-resistant slope: **{slope.slope*10:.2f} mm/decade**.')
            st.caption('Theil–Sen is a descriptive slope cross-check here; no autocorrelation-adjusted significance test or confidence interval is claimed for it.')
        frame['selection']=label
        frame['analysis_start']=int(series.year.min()); frame['analysis_end']=int(series.year.max())
        frame['alpha']=alpha; frame['hac_maxlags']=[None,robust['maxlags'],None]
        st.download_button('Download trend diagnostics · CSV',frame.to_csv(index=False),
                           file_name='saharawatch_trend_diagnostics.csv',mime='text/csv',key='trend_diagnostics_export')
