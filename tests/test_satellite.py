"""Check imagery integrity, geographic support, and time-aligned rainfall evidence."""
import io
import json
import shutil
import zipfile
from xml.etree import ElementTree

import numpy as np
import pandas as pd
import pytest
import xarray as xr
from PIL import Image
from streamlit.testing.v1 import AppTest

from saharawatch.data import RAW, ROOT
from saharawatch.satellite import (PAIR, load_satellite_pair, rainfall_context,
                                  rainfall_cell_overlay, evidence_archive)


def example_monthly():
    dates = pd.date_range('2022-01-01', '2024-02-01', freq='MS')
    return xr.DataArray(np.full((len(dates), 1, 1), 10.), dims=('time', 'lat', 'lon'),
                        coords={'time':dates, 'lat':[33.75], 'lon':[-8.75]})


def test_bundled_imagery_has_matching_dimensions_dates_and_provenance():
    manifest, payloads = load_satellite_pair()
    assert manifest['bbox'] == [-9, 31, -6, 34]
    assert [image['date'] for image in manifest['images']] == ['2023-02-12', '2024-02-19']
    assert [image['platform'] for image in manifest['images']] == ['Aqua', 'Terra']
    for payload in payloads:
        image = Image.open(io.BytesIO(payload))
        assert image.size == (manifest['width'], manifest['height']) == (900, 900)
        image.verify()


def test_corrupt_or_missing_images_are_never_replaced_with_synthetic_evidence(tmp_path):
    shutil.copytree(PAIR, tmp_path/'pair')
    folder = tmp_path/'pair'
    filename = json.loads((folder/'manifest.json').read_text())['images'][0]['file']
    (folder/filename).write_bytes(b'\xff\xd8\xffcorrupted')
    load_satellite_pair.clear()
    with pytest.raises(ValueError, match='checksum'):
        load_satellite_pair(folder)
    with pytest.raises(FileNotFoundError):
        load_satellite_pair(tmp_path/'absent')


def test_rainfall_uses_six_full_preceding_months_and_retains_gaps():
    monthly = example_monthly()
    manifest, _ = load_satellite_pair()
    frame, summary, figure, cell = rainfall_context(monthly, manifest)
    assert cell == (33.75, -8.75)
    assert [row['rainfall_period'] for row in summary] == ['2022-08 to 2023-01', '2023-08 to 2024-01']
    assert [row['precipitation_mm'] for row in summary] == [60, 60]
    assert len(figure.layout.shapes) == 2
    # A very wet acquisition month must not affect the six-month context.
    monthly.loc[dict(time='2023-02-01')] = 999
    assert rainfall_context(monthly, manifest)[1][0]['precipitation_mm'] == 60
    monthly = monthly.drop_sel(time='2023-10-01')
    frame, summary, _, _ = rainfall_context(monthly, manifest)
    assert summary[1]['precipitation_mm'] is None and summary[1]['complete_months'] == 5
    assert pd.isna(frame.loc[frame.month == '2023-10-01', 'precipitation_mm']).all()


def test_grid_overlay_uses_real_cell_extents_and_archive_keeps_original_images():
    manifest, payloads = load_satellite_pair()
    svg = ElementTree.fromstring(rainfall_cell_overlay([31.25, 33.75], [-8.75, -6.25, 1.25], manifest['bbox']))
    cells = list(svg)
    assert len(cells) == 4
    assert float(cells[0].get('width')) == pytest.approx(100*2.5/3)
    frame, summary, _, cell = rainfall_context(example_monthly(), manifest)
    archive = evidence_archive(manifest, payloads, frame, summary, cell,
                              dict(version='test', sha256='rainfall-checksum', attributes={}))
    with zipfile.ZipFile(io.BytesIO(archive)) as zipped:
        evidence = json.loads(zipped.read('evidence.json'))
        assert evidence['rainfall_context']['source_sha256'] == 'rainfall-checksum'
        assert evidence['rainfall_context']['resolution_degrees'] == 2.5
        for image, payload in zip(manifest['images'], payloads, strict=True):
            assert zipped.read(image['file']) == payload
        assert len(pd.read_csv(zipped.open('rainfall.csv'))) == len(frame)


@pytest.mark.skipif(not RAW.exists(), reason='Requires downloaded GPCP')
def test_satellite_workspace_is_direct_and_independent_of_rainfall_filters():
    at = AppTest.from_file(ROOT/'app.py').run(timeout=30)
    assert not at.exception
    assert 'satellite_rainfall' not in [e.key for e in at.get('plotly_chart')]
    at.button(key='go_satellite').click().run(timeout=30)
    assert not at.exception
    original = [metric.value for metric in at.metric if metric.label.startswith('Six complete months')]
    assert 'satellite_rainfall' in [e.key for e in at.get('plotly_chart')]
    at.slider(key='period').set_range(1991, 2020).run(timeout=30)
    at.slider(key='baseline').set_range(1981, 2010).run(timeout=30)
    assert not at.exception
    assert [metric.value for metric in at.metric if metric.label.startswith('Six complete months')] == original
    at.slider(key='baseline').set_range(2001,2005).run(timeout=30)
    assert not at.exception
    assert 'satellite_rainfall' in [e.key for e in at.get('plotly_chart')]
    at.slider(key='baseline').set_range(1981,2010).run(timeout=30)
    at.button(key='go_cases').click().run(timeout=30)
    assert not at.exception
    assert 'satellite_rainfall' not in [e.key for e in at.get('plotly_chart')]
