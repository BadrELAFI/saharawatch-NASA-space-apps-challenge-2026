"""Curated, local satellite evidence with explicit acquisition and rainfall support."""
import base64
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


def render_satellite_comparison(monthly, metadata):
    st.markdown('### Satellite evidence / A landscape, one year apart')
    st.write('Look beyond the rainfall chart. Slide between two February views of the Casablanca region, '
             'then cross-examine the rainfall record below.')
    if not st.toggle('Open the satellite before/after reveal', key='satellite_enabled'):
        return
    try:
        manifest, payloads = load_satellite_pair()
    except (OSError, ValueError, KeyError, TypeError) as exc:
        st.error(f'Satellite evidence is unavailable: {exc}. Restore data/satellite from the project checkout.')
        return
    st.caption('BEFORE · 12 February 2023 · Aqua MODIS   /   AFTER · 19 February 2024 · Terra MODIS')
    st.caption('Drag the divider, tap a point on the image, or focus the slider and use the arrow keys. '
               'North is up; both views show the same 9–6° W, 31–34° N extent.')
    position = st.session_state.get('satellite_position', 50)
    show_grid = st.session_state.get('satellite_show_grid', False)
    images = [dict(image, src='data:image/jpeg;base64,'+base64.b64encode(payload).decode())
              for image, payload in zip(manifest['images'], payloads, strict=True)]
    comparison_component(data=dict(images=images, position=position, show_grid=show_grid,
                                   grid_svg=rainfall_cell_overlay(monthly.lat.values, monthly.lon.values, manifest['bbox'])),
                         default=dict(position=position, show_grid=show_grid), key='satellite_comparison',
                         on_position_change=_save_comparison, on_show_grid_change=_save_comparison,
                         height='content')
    st.caption('NASA GIBS / Aqua and Terra MODIS · True-color browse imagery · '
               'Same season, different dates and satellite overpass conditions. Clouds, haze and snow remain visible.')
    st.write('The earlier view appears greener across parts of the coastal plain. Treat that as a visual clue: '
             'these images do not measure vegetation health, reservoir volume, or rainfall, and do not establish what caused the difference.')
    try:
        frame, summary, figure, cell = rainfall_context(monthly, manifest)
    except ValueError as exc:
        st.warning(f'The satellite images remain available, but rainfall context could not be prepared: {exc}')
        return
    st.markdown('#### Follow the rainfall evidence')
    st.caption(f'Nearest GPCP cell to Casablanca · center {cell[0]:.2f}° N, {cell[1]:.2f}° E · '
               '2.5° × 2.5° support. This is a coarse grid-cell record, not a city measurement. '
               'Sidebar country, analysis period and baseline do not change this curated comparison.')
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
        st.markdown(f'[NASA’s published comparison]({manifest["context_url"]}) · '
                    f'[NASA GIBS documentation]({manifest["documentation_url"]})')
        for image in manifest['images']:
            st.markdown(f'[{image["date"]} · {image["platform"]} MODIS · original GIBS request]({image["url"]})')
            st.caption('SHA-256: '+image['sha256'])
        st.caption(f'Identical EPSG:4326 extent and {manifest["width"]} × {manifest["height"]} output pixels. '
                   'Output pixels do not imply finer sensor resolution. Images are bundled locally; no imagery requests run on interaction.')
    st.download_button('Download satellite evidence · ZIP',
                       evidence_archive(manifest, payloads, frame, summary, cell, metadata),
                       file_name='saharawatch_satellite_evidence.zip', mime='application/zip',
                       key='satellite_download', on_click='ignore')
