"""Curated, local satellite evidence with explicit acquisition and rainfall support."""
import base64
import calendar
from datetime import date
import hashlib
import io
import json
import math
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from .data import ROOT, grid_series
from .plots import style, CYAN, AMBER
from .satellite_source import imagery_availability, comparison_dates, fetch_comparison, PLATFORMS
from .exhibits import exhibit

ASSETS = ROOT/'assets/satellite-comparison'
PAIR = ROOT/'data/satellite'


@st.cache_data(show_spinner=False)
def load_satellite_pair(folder=PAIR):
    """Reject absent, corrupt or incompatible bundled evidence; never fetch on interaction."""
    folder = Path(folder)
    manifest = json.loads((folder/'manifest.json').read_text())
    if (manifest.get('schema') != 'saharawatch-satellite-pair-v1'
            or manifest.get('projection') != 'EPSG:4326'
            or manifest.get('bbox') != [-9, 31, -6, 34]
            or len(manifest.get('images', [])) != 2):
        raise ValueError('The satellite pair has unsupported geographic metadata.')
    payloads = []
    dates = []
    for image in manifest['images']:
        filename = image['file']
        if Path(filename).name != filename or not filename.endswith('.jpg'):
            raise ValueError('The satellite image filename is invalid.')
        payload = (folder/filename).read_bytes()
        if not payload.startswith(b'\xff\xd8\xff') or hashlib.sha256(payload).hexdigest() != image['sha256']:
            raise ValueError('The satellite image does not match its recorded checksum.')
        dates.append(pd.Timestamp(image['date']))
        payloads.append(payload)
    if dates[0] >= dates[1]:
        raise ValueError('The satellite images must be ordered before then after.')
    return manifest, payloads


def rainfall_cell_overlay(latitudes, longitudes, bbox):
    """Project the true GPCP support into the same geographic image rectangle."""
    west, south, east, north = bbox
    elements = []
    for lat in latitudes:
        for lon in longitudes:
            if lon+1.25 <= west or lon-1.25 >= east or lat+1.25 <= south or lat-1.25 >= north:
                continue
            x = 100*(lon-1.25-west)/(east-west)
            y = 100*(north-lat-1.25)/(north-south)
            width, height = 250/(east-west), 250/(north-south)
            elements.append(f'<rect x="{x:.6f}" y="{y:.6f}" width="{width:.6f}" height="{height:.6f}" '
                            'fill="none" stroke="#fff5df" stroke-width=".35" stroke-dasharray="1.3 1"/>')
    return '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" aria-label="GPCP cell boundaries">'+''.join(elements)+'</svg>'


def rainfall_context(monthly, manifest):
    """Monthly observations at the actual nearest coarse cell, never a city estimate."""
    series = grid_series(monthly, 33.59, -7.62)
    dates = [pd.Timestamp(image['date']) for image in manifest['images']]
    first = (dates[0].to_period('M')-12).start_time
    last = (dates[-1].to_period('M')+1).start_time
    calendar = pd.date_range(first, last, freq='MS', inclusive='left')
    # Dataset timestamps are normalized by month; absent months stay explicit gaps.
    indexed = pd.Series(series.values, index=pd.DatetimeIndex(series.time.values).to_period('M').to_timestamp())
    observations = indexed.reindex(calendar)
    frame = pd.DataFrame({'month':calendar, 'precipitation_mm':observations.values})
    figure = go.Figure(go.Bar(x=calendar, y=observations.values, marker_color=CYAN,
                              name='Monthly rainfall', hovertemplate='%{x|%b %Y}: %{y:.1f} mm<extra></extra>'))
    summary = []
    for index, date in enumerate(dates):
        color = CYAN if index == 0 else AMBER
        figure.add_vline(x=date.timestamp()*1000, line_color=color, line_dash='dot')
        figure.add_annotation(x=date, y=1, xref='x', yref='paper',
                              text=f'{"Before" if index == 0 else "After"} · {date:%d %b %Y}',
                              showarrow=False, yshift=12, font_color=color)
        preceding = pd.date_range((date.to_period('M')-6).start_time,
                                  date.to_period('M').start_time, freq='MS', inclusive='left')
        values = indexed.reindex(preceding)
        valid = int(np.isfinite(values).sum())
        summary.append(dict(image_date=date.strftime('%Y-%m-%d'),
                            rainfall_period=f'{preceding[0]:%Y-%m} to {preceding[-1]:%Y-%m}',
                            complete_months=valid,
                            precipitation_mm=float(values.sum()) if valid == 6 else None))
    figure.update_yaxes(title_text='Monthly rainfall (mm)', rangemode='tozero')
    return frame, summary, style(figure, 300), (float(series.lat), float(series.lon))


@st.cache_data(show_spinner=False, max_entries=8)
def evidence_archive(manifest, payloads, rainfall, summary, cell, metadata):
    evidence = dict(manifest, rainfall_context=dict(
        cell_latitude=cell[0], cell_longitude=cell[1], resolution_degrees=2.5,
        source=f'GPCP {metadata["version"]} / NOAA PSL', source_sha256=metadata['sha256'],
        source_status=metadata.get('attributes', {}).get('data_comment', ''),
        summary=summary, scope='Nearest grid cell to Casablanca; not city rainfall or event attribution.',
        temporal_limit='Image-month totals include observations after acquisition. Six-month totals exclude the acquisition month.'))
    out = io.BytesIO()
    with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as archive:
        archive.writestr('evidence.json', json.dumps(evidence, indent=2, allow_nan=False))
        archive.writestr('rainfall.csv', rainfall.to_csv(index=False))
        for image, payload in zip(manifest['images'], payloads, strict=True):
            archive.writestr(image['file'], payload)
    return out.getvalue()


def _save_comparison():
    value = st.session_state.get('satellite_comparison', {})
    position = value.get('position', 50)
    if isinstance(position, (float, int)) and math.isfinite(position):
        st.session_state['satellite_position'] = max(0, min(100, round(position)))
    st.session_state['satellite_show_grid'] = value.get('show_grid') is True


comparison_component = st.components.v2.component(
    'saharawatch.satellite_comparison', html='<div class="satellite-comparison-root"></div>',
    css=(ASSETS/'comparison.css').read_text(), js=(ASSETS/'comparison.js').read_text())


def active_satellite_pair():
    return st.session_state.get('satellite_active_pair') or load_satellite_pair()


def remember_satellite_preferences():
    preferences = st.session_state['satellite_preferences']
    for field in preferences:
        if 'satellite_'+field in st.session_state:
            preferences[field] = st.session_state['satellite_'+field]


def restore_satellite_controls():
    """Restore committed form values before remounting this workspace's widgets."""
    for field,value in st.session_state.get('satellite_preferences',{}).items():
        st.session_state['satellite_'+field] = value


def choose_satellite_pair():
    preferences = st.session_state.setdefault('satellite_preferences', dict(mode='Recommended example',platform='Terra',
        before_year=2023,after_year=2024,month=2,day=19))
    for field,value in preferences.items():
        st.session_state.setdefault('satellite_'+field,value)
    modes = ['Recommended example', 'Choose years']
    mode = st.radio('Choose images', modes, index=modes.index(preferences['mode']), horizontal=True,
                    key='satellite_mode',on_change=remember_satellite_preferences)
    if mode == 'Recommended example':
        st.caption('Start with two visually reviewed February views: 2023 versus 2024. No download is needed.')
        return load_satellite_pair()
    existing = st.session_state.get('satellite_custom_pair') or load_satellite_pair()
    platform = st.selectbox('Satellite for both images', PLATFORMS, index=PLATFORMS.index(preferences['platform']), key='satellite_platform',
                            help='Using the same satellite makes the comparison more consistent.',on_change=remember_satellite_preferences)
    try:
        with st.spinner('Checking which image dates NASA provides…'):
            availability = imagery_availability(platform)
    except (ValueError, OSError) as exc:
        st.warning(str(exc))
        st.caption('Your displayed comparison is unchanged. Use the recommended example to explore without a connection.')
        return existing
    first, last = date.fromisoformat(availability['first']), date.fromisoformat(availability['last'])
    years = list(range(first.year, last.year+1))
    before_default = max(years[0],min(years[-1],preferences['before_year']))
    after_default = max(years[0],min(years[-1],preferences['after_year']))
    for field,default in [('before_year',before_default),('after_year',after_default)]:
        if st.session_state['satellite_'+field] not in years:
            st.session_state['satellite_'+field] = default
    st.caption(f'{platform} MODIS record: {first:%d %b %Y}–{last:%d %b %Y}. '
               'Choose the same month and day in two different years to limit seasonal differences.')
    if availability.get('stale'):
        st.caption('Using the last saved date catalogue because NASA is currently unreachable. Previously downloaded images remain available.')
    with st.form('satellite_year_form'):
        before, after = st.columns(2)
        before_year = before.selectbox('Before year', years, index=years.index(before_default), key='satellite_before_year')
        after_year = after.selectbox('After year', years, index=years.index(after_default), key='satellite_after_year')
        month_col, day_col = st.columns(2)
        month = month_col.selectbox('Month for both images', list(range(1,13)), index=preferences['month']-1,
                                     format_func=lambda value:calendar.month_name[value], key='satellite_month')
        day = day_col.number_input('Day of month', 1, 31, preferences['day'], key='satellite_day')
        submitted = st.form_submit_button('Load comparison', type='primary')
    st.caption('Press Load comparison to apply these controls. Until then, the images below remain your last loaded comparison. '
               'Dragging the divider does not download imagery.')
    if submitted:
        remember_satellite_preferences()
        try:
            first_date, last_date = comparison_dates(before_year, after_year, month, day, availability)
            with st.spinner(f'Loading {first_date:%d %b %Y} and {last_date:%d %b %Y} from NASA…'):
                existing = fetch_comparison(platform, first_date, last_date, availability)
            st.session_state['satellite_custom_pair'] = existing
            st.session_state['satellite_position'] = 50
            st.session_state.pop('satellite_comparison', None)
        except (ValueError, OSError) as exc:
            st.warning(str(exc)+' The images below have not been changed.')
    return existing


def render_satellite_comparison(monthly, metadata):
    st.subheader('Compare satellite images')
    st.write('Explore the Casablanca region from space. Start with the example or choose two years, '
             'then drag the divider to see what changed.')
    try:
        manifest, payloads = choose_satellite_pair()
    except (OSError, ValueError, KeyError, TypeError) as exc:
        st.error(f'The satellite example could not be opened: {exc}. Restore data/satellite from the project checkout.')
        return
    st.session_state['satellite_active_pair'] = (manifest, payloads)
    before, after = manifest['images']
    st.markdown(f'**Showing: {before["date"]} ({before["platform"]}) → {after["date"]} ({after["platform"]})**')
    st.caption('Drag the divider, tap a point on the image, or focus the slider and use the arrow keys. '
               'North is up; both views show the same 9–6° W, 31–34° N extent.')
    position = st.session_state.get('satellite_position', 50)
    show_grid = st.session_state.get('satellite_show_grid', False)
    images = [dict(image, src=('data:image/png;base64,' if payload.startswith(b'\x89PNG') else 'data:image/jpeg;base64,')+base64.b64encode(payload).decode())
              for image, payload in zip(manifest['images'], payloads, strict=True)]
    with exhibit('PHOTOGRAPHIC EVIDENCE',before['date']+' / '+after['date'],'satellite_photos',kind='photographs'):
        comparison_component(data=dict(images=images, position=position, show_grid=show_grid,
                                   grid_svg=rainfall_cell_overlay(monthly.lat.values, monthly.lon.values, manifest['bbox'])),
                         default=dict(position=position, show_grid=show_grid), key='satellite_comparison',
                         on_position_change=_save_comparison, on_show_grid_change=_save_comparison,
                         height='content')
    st.caption(manifest['credit']+' · True-color browse imagery · '
               'Same season, different dates and satellite overpass conditions. Clouds, haze and snow remain visible.')
    st.write('What differences do you notice? Treat them as visual clues. Images alone do not measure '
             'vegetation health, reservoir volume or rainfall, or establish what caused a change.')
    for image in manifest['images']:
        if 'valid_image_area_pct' in image and image['valid_image_area_pct'] < 99.9:
            st.caption(f'{image["date"]}: {image["valid_image_area_pct"]:.1f}% of the image area has pixels. '
                       'Blank areas contain no imagery; this percentage does not measure cloud-free coverage.')
    try:
        frame, summary, figure, cell = rainfall_context(monthly, manifest)
    except ValueError as exc:
        st.warning(f'The satellite images remain available, but rainfall context could not be prepared: {exc}')
        return manifest, payloads
    st.markdown('#### Follow the rainfall evidence')
    st.caption(f'Nearest GPCP cell to Casablanca · center {cell[0]:.2f}° N, {cell[1]:.2f}° E · '
               '2.5° × 2.5° support. This is a coarse grid-cell record, not a city measurement. '
               'Use the image controls above to change comparison dates. Rainfall filters in the sidebar do not change them.')
    with exhibit('FIELD RECORD', 'Rainfall around the acquisition dates','satellite_rainfall'):
        st.plotly_chart(figure, width='stretch', theme=None, key='satellite_rainfall')
    columns = st.columns(2)
    for index, row in enumerate(summary):
        value = f'{row["precipitation_mm"]:.1f} mm' if row['precipitation_mm'] is not None else 'Unavailable'
        columns[index].metric(f'Six complete months before {row["image_date"]}', value)
        columns[index].caption(f'{row["rainfall_period"]} · {row["complete_months"]}/6 valid months')
    st.caption('Six-month totals exclude the acquisition month. Monthly bars for February include days '
               'after image acquisition; the chart cannot resolve the timing of individual rain events. '
               'Missing months remain gaps and withhold the corresponding six-month total.')
    note = metadata.get('attributes', {}).get('data_comment', '')
    if note:
        st.caption('GPCP source status: '+note)
    with st.expander('Image sources, alignment & scientific limits'):
        st.write(manifest['limits'])
        st.write(manifest['review'])
        st.markdown(f'[NASA image context]({manifest["context_url"]}) · '
                    f'[NASA GIBS documentation]({manifest["documentation_url"]})')
        for image in manifest['images']:
            st.markdown(f'[{image["date"]} · {image["platform"]} MODIS · original GIBS request]({image["url"]})')
            st.caption('SHA-256: '+image['sha256'])
        st.caption(f'Identical EPSG:4326 extent and {manifest["width"]} × {manifest["height"]} output pixels. '
                   'Output pixels do not imply finer sensor resolution. The example is bundled; custom downloads are cached locally.')
    st.download_button('Download satellite evidence · ZIP',
                       evidence_archive(manifest, payloads, frame, summary, cell, metadata),
                       file_name='saharawatch_satellite_evidence.zip', mime='application/zip',
                       key='satellite_download', on_click='ignore')
    return manifest, payloads
