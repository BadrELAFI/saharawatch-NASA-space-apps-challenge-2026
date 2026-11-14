import numpy as np
import pytest
from scipy import stats
from saharawatch.trend_diagnostics import hac_trend


def test_hac_covariance_matches_independent_newey_west_calculation():
    x=np.arange(1981,2021,dtype=float)
    y=400+1.4*(x-x[0])+12*np.sin(np.arange(40)/3)
    got=hac_trend(x,y,maxlags=3)
    design=np.column_stack((np.ones(len(x)),x-x.mean()))
    beta=np.linalg.lstsq(design,y,rcond=None)[0]
    residual=y-design@beta
    scores=design*residual[:,None]
    meat=scores.T@scores
    for lag in range(1,4):
        cross=scores[lag:].T@scores[:-lag]
        meat+=(1-lag/4)*(cross+cross.T)
    bread=np.linalg.inv(design.T@design)
    covariance=bread@meat@bread*len(x)/(len(x)-2)
    se=np.sqrt(covariance[1,1])
    assert got['p']==pytest.approx(2*stats.t.sf(abs(beta[1]/se),len(x)-2))
    assert got['low']==pytest.approx(10*(beta[1]-stats.t.ppf(.975,len(x)-2)*se))
    assert got['high']==pytest.approx(10*(beta[1]+stats.t.ppf(.975,len(x)-2)*se))


def test_hac_gaps_constant_and_insufficient_data():
    x=np.arange(2000,2020)
    constant=hac_trend(x,np.ones(20))
    assert constant['p']==1 and constant['decade']==0
    y=np.arange(20,dtype=float); y[10]=np.nan
    assert np.isnan(hac_trend(x,y)['p'])
    assert 'consecutive' in hac_trend(x,y)['reason']
    assert np.isnan(hac_trend(x[:5],y[:5])['p'])
    with pytest.raises(ValueError): hac_trend(x,np.arange(20),maxlags=20)
