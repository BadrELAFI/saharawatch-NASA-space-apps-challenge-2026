"""Browser-side rainfall playback with fixed spatial and temporal scales."""
import html

import numpy as np
import plotly.graph_objects as go
import streamlit as st
import xarray as xr

from .drought import anomaly_statistics
from .plots import AMBER, CYAN, map_figure


def rainfall_history_figure(annual, series, years, baseline_start, baseline_end,
                           label, selected=None, feature=None, duration=800):
    """Animate only supplied complete years; never interpolate missing values."""
    years = [int(year) for year in years]
    if not years or years != sorted(set(years)):
        raise ValueError('Playback needs unique, chronological complete years.')
    departures = anomaly_statistics(annual, baseline_start, baseline_end)
    anomalies = departures.anomaly.sel(year=years).transpose('year', 'lat', 'lon')
    observed = annual.sel(year=years).transpose('year', 'lat', 'lon')
    expected = departures.expected.transpose('lat', 'lon')
    timeline = series.sel(year=years)
    local = anomaly_statistics(series, baseline_start, baseline_end)
    finite = anomalies.values[np.isfinite(anomalies.values)]
    limit = max(float(np.max(np.abs(finite))), 1.) if finite.size else 1.
    baseline = f'{baseline_start}–{baseline_end}'

    def hover(year):
        return ('<b>%{customdata[0]:.2f}° N, %{customdata[1]:.2f}° E</b>'
                f'<br>{year} vs. {baseline} baseline'
                '<br>Rainfall anomaly: %{z:.1f} mm'
                '<br>Observed: %{customdata[3]:.1f} mm'
                '<br>Baseline: %{customdata[4]:.1f} mm<extra></extra>')

    fig = map_figure(anomalies.sel(year=years[0]), 'Annual anomaly', 'mm',
                     f'{years[0]} vs. {baseline} baseline', selected=selected,
                     feature=feature, diverging=True,
                     observed=observed.sel(year=years[0]), expected=expected)
    fig.data[0].update(zmin=-limit, zmax=limit, hovertemplate=hover(years[0]))
    fig.data[0].colorbar.update(y=.71, len=.5)
    # Static geography is sent once. Frames update only measured values and cursors.
    centers = np.asarray(fig.data[1].customdata)
    rainfall = timeline.values
    valid_rainfall = rainfall[np.isfinite(rainfall)]
    baseline_mean = float(local.expected)
    ceiling = max(float(np.max(valid_rainfall)) if valid_rainfall.size else 0.,
                  baseline_mean if np.isfinite(baseline_mean) else 0., 1.) * 1.1
    calendar = np.arange(years[0], years[-1]+1)
    fig.add_trace(go.Scatter(x=calendar, y=timeline.reindex(year=calendar).values, mode='lines+markers',
                            line=dict(color=CYAN, width=2), marker_size=4,
                            connectgaps=False, name='Annual rainfall',
                            hovertemplate='%{x}: %{y:.1f} mm<extra></extra>'))
    if np.isfinite(baseline_mean):
        fig.add_trace(go.Scatter(x=[years[0], years[-1]], y=[baseline_mean]*2,
                                mode='lines', line=dict(color='#8b784f', dash='dot'),
                                name='Baseline mean',
                                hovertemplate='Baseline mean: %{y:.1f} mm<extra></extra>'))
    cursor_index = len(fig.data)
    fig.add_trace(go.Scatter(x=[years[0]]*2, y=[0, ceiling], mode='lines',
                            line=dict(color=AMBER, width=1, dash='dot'),
                            hoverinfo='skip', showlegend=False))
    marker_index = len(fig.data)
    fig.add_trace(go.Scatter(x=[years[0]], y=[rainfall[0]], mode='markers',
                            marker=dict(size=12, color=AMBER), showlegend=False,
                            hovertemplate='%{x}: %{y:.1f} mm<extra></extra>'))

    def year_title(index):
        value = rainfall[index]
        departure = float(local.anomaly.sel(year=years[index]))
        detail = (f'{value:,.1f} mm · {departure:+,.1f} mm from baseline'
                  if np.isfinite(value) and np.isfinite(departure)
                  else 'Insufficient data at selected location')
        return dict(text=f'<b>{years[index]}</b> · Annual rainfall<br><sup>{detail}</sup>',
                    x=0, xanchor='left', font_size=15)

    frames = []
    for index, year in enumerate(years):
        z = anomalies.sel(year=year).values.ravel()
        custom = np.column_stack((centers, np.full(len(centers), np.nan),
                                  observed.sel(year=year).values.ravel(), expected.values.ravel()))
        frames.append(go.Frame(name=str(year), traces=[0, 1, cursor_index, marker_index],
            data=[go.Choroplethmap(z=z, customdata=custom.tolist(), hovertemplate=hover(year)),
                  go.Scattermap(text=[f'{year}: {v:+.1f} mm' if np.isfinite(v)
                                      else f'{year}: Insufficient data' for v in z]),
                  go.Scatter(x=[year]*2, y=[0, ceiling]),
                  go.Scatter(x=[year], y=[rainfall[index]])],
            layout=dict(title=year_title(index), sliders=[dict(active=index)])))
    fig.frames = frames
    fig.data[1].text = frames[0].data[1].text
    immediate = dict(mode='immediate', frame=dict(duration=0, redraw=True), transition=dict(duration=0))
    fig.update_layout(
        height=800, margin=dict(l=45, r=25, t=55, b=100), title=year_title(0),
        map_domain=dict(x=[0, 1], y=[.40, 1]),
        xaxis=dict(domain=[0, .94], anchor='y', range=[years[0]-.5, years[-1]+.5],
                   tickformat='d', fixedrange=True, nticks=7),
        yaxis=dict(domain=[.12, .28], anchor='x', range=[0, ceiling],
                   title_text='Rainfall (mm)', fixedrange=True, nticks=4),
        annotations=[dict(x=0, y=.32, xref='paper', yref='paper', xanchor='left',
                          showarrow=False, text=html.escape(label), font_size=12)],
        sliders=[dict(active=0, x=0, len=.95, y=.01, pad=dict(t=20),
                      currentvalue=dict(prefix='Year: ', font_size=13),
                      steps=[dict(label=str(year), method='animate', execute=False,
                                  args=[[str(year)], immediate])
                             for year in years])],
        updatemenus=[dict(type='buttons', direction='right', x=0, y=.065,
                         xanchor='left', yanchor='bottom', showactive=False,
                         bgcolor='#e2d2b3', bordercolor='#8b784f',
                         buttons=[dict(label='▶ Play', method='animate', execute=False,
                                       args=[None, dict(mode='immediate', fromcurrent=True,
                                             frame=dict(duration=duration, redraw=True),
                                             transition=dict(duration=0))]),
                                  dict(label='Ⅱ Pause', method='animate', execute=False, args=[[None], immediate]),
                                  dict(label='↺ Start', method='animate', execute=False, args=[[str(years[0])], immediate])])])
    return fig


@st.cache_data(show_spinner=False, max_entries=8,
               hash_funcs={xr.DataArray: lambda data: data.to_dict()})
def playback_html(annual, series, years, baseline_start, baseline_end, label,
                  selected, feature, duration):
    fig = rainfall_history_figure(annual, series, years, baseline_start, baseline_end,
                                 label, selected, feature, duration)
    # Streamlit's native chart serialization does not carry animation frames.
    # Bundle Plotly locally so playback needs no CDN or remote map tiles.
    return fig.to_html(include_plotlyjs=True, full_html=True, auto_play=False,
                       div_id='rainfall-time-machine',
                       post_script="""
                       const plot = document.getElementById('{plot_id}');
                       // Plotly rejects interrupted animation promises with undefined.
                       // Handle cancellation on our controls without masking real errors.
                       function animate(args) {
                           Plotly.animate(plot, ...args).catch(error => {
                               if (error !== undefined) console.error('Rainfall playback failed:', error);
                           });
                       }
                       plot.on('plotly_buttonclicked', event => animate(event.button.args));
                       plot.on('plotly_sliderchange', event => animate(event.step.args));
                       """,
                       config=dict(responsive=True, scrollZoom=False, displaylogo=False,
                                   displayModeBar=False))


def render_time_machine(annual, series, complete_years, start, end, baseline_start,
                        baseline_end, label, metadata, selected=None, feature=None):
    st.markdown('### The rainfall time machine')
    st.write('Watch the years unfold. Follow the map and the moving marker on your rainfall timeline.')
    scope_col, speed_col = st.columns([2, 1])
    scope = scope_col.radio('Playback period', ['Full available record', 'Current analysis period'],
                            horizontal=True, key='playback_period')
    speed = speed_col.selectbox('Playback speed', ['Normal', 'Slow', 'Fast'], key='playback_speed')
    years = [year for year in complete_years if scope == 'Full available record' or start <= year <= end]
    st.caption(f'{years[0]}–{years[-1]} · Fixed {baseline_start}–{baseline_end} baseline · '
               'Terracotta: below baseline · Green: above baseline')
    with st.spinner('Preparing the rainfall record…'):
        document = playback_html(annual, series, years, baseline_start, baseline_end, label,
                                 selected, feature, {'Normal':800, 'Slow':1400, 'Fast':400}[speed])
    st.iframe(document, height=820, alt='Animated rainfall map and synchronized location timeline')
    st.caption('Press Play, Pause, or Start, or drag the year scrubber. Playback starts paused. '
               'Map colors and timeline axes stay fixed across all frames. Unfilled cells and '
               'timeline gaps indicate insufficient data; no values are interpolated. '
               'Annual totals require 12 valid months. Year-to-year variability alone does not establish a trend.')
    st.caption('Source status: '+metadata['attributes'].get('data_comment', 'Provisional status not specified.'))
    st.caption('Playback follows the location and baseline selected in the sidebar. '
               'To investigate a playback year below, choose an anomaly map indicator and its Observation year.')
