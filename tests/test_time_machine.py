import numpy as np
import pytest
import xarray as xr

from saharawatch.time_machine import rainfall_history_figure


def test_playback_preserves_values_missingness_alignment_and_fixed_scales():
    years = np.arange(2000, 2013)
    values = np.full((13, 2, 2), 100.)
    values[-1, 0, 0] = 900.
    values[3, 0, 1] = np.nan
    values[4, 0, 0] = np.nan
    annual = xr.DataArray(values, dims=('year', 'lat', 'lon'),
                          coords={'year': years, 'lat': [31.25, 33.75], 'lon': [-6.25, -3.75]})
    series = annual.sel(lat=31.25, lon=-6.25)
    fig = rainfall_history_figure(annual, series, list(years), 2000, 2011, 'Selected cell')
    assert fig.data[0].zmin == -800 and fig.data[0].zmax == 800
    assert fig.layout.xaxis.range == (1999.5, 2012.5)
    assert fig.layout.yaxis.range == pytest.approx((0, 990.))
    cursor, marker = fig.frames[0].traces[-2:]
    for year, frame in zip(years, fig.frames):
        assert frame.name == str(year)
        np.testing.assert_allclose(frame.data[0].z, (annual.sel(year=year)-100).values.ravel())
        custom = np.asarray(frame.data[0].customdata)
        np.testing.assert_allclose(custom[:, 3], annual.sel(year=year).values.ravel())
        np.testing.assert_allclose(custom[:, 4], 100.)
        assert frame.data[2].x == (year, year)
        assert frame.data[3].x == (year,)
        np.testing.assert_allclose(frame.data[3].y, [float(series.sel(year=year))])
        assert str(year) in frame.data[0].hovertemplate
        assert not frame.layout.yaxis.range  # Frames cannot rescale the timeline.
        assert frame.traces[-2:] == (cursor, marker)
    assert 'Insufficient data' in fig.frames[3].data[1].text[1]
    assert 'Insufficient data' in fig.frames[4].layout.title.text
    assert fig.layout.sliders[0].steps[-1].args[0] == ('2012',)
    assert fig.layout.updatemenus[0].buttons[0].args[1]['frame']['redraw']
    fig.to_json()  # Includes frames and serializes missing observations safely.


def test_playback_uses_only_requested_years_and_keeps_external_baseline():
    years = np.arange(2000, 2013)
    annual = xr.DataArray(np.arange(13)[:, None, None]*10.+100, dims=('year', 'lat', 'lon'),
                          coords={'year': years, 'lat': [31.25], 'lon': [-6.25]})
    fig = rainfall_history_figure(annual, annual[:, 0, 0], [2011, 2012], 2000, 2009, 'Cell')
    assert [frame.name for frame in fig.frames] == ['2011', '2012']
    np.testing.assert_allclose(fig.frames[0].data[0].z, [65.])
    np.testing.assert_allclose(fig.frames[1].data[0].z, [75.])
    assert '2000–2009 baseline' in fig.frames[1].data[0].hovertemplate
    gaps = rainfall_history_figure(annual, annual[:, 0, 0], [2010, 2012], 2000, 2009, 'Cell')
    history = next(trace for trace in gaps.data if trace.name == 'Annual rainfall')
    np.testing.assert_allclose(history.y, [200., np.nan, 220.])
    assert not history.connectgaps
    with pytest.raises(ValueError, match='chronological'):
        rainfall_history_figure(annual, annual[:, 0, 0], [2012, 2011], 2000, 2009, 'Cell')


def test_no_baseline_support_stays_missing_with_finite_display_ranges():
    years = np.arange(2000, 2012)
    annual = xr.DataArray(np.full((12, 1, 1), np.nan), dims=('year', 'lat', 'lon'),
                          coords={'year': years, 'lat': [31.25], 'lon': [-6.25]})
    fig = rainfall_history_figure(annual, annual[:, 0, 0], list(years), 2000, 2011, 'Cell')
    assert fig.data[0].zmin == -1 and fig.data[0].zmax == 1
    assert np.isfinite(fig.layout.yaxis.range).all()
    assert all(np.isnan(frame.data[0].z).all() for frame in fig.frames)
    assert all('Insufficient data' in frame.layout.title.text for frame in fig.frames)
