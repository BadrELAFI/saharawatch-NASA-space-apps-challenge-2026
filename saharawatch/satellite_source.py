"""Explicit dated GIBS requests with time-domain checks and validated disk caching."""
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timezone
import hashlib
import io
import json
import os
from pathlib import Path
import xml.etree.ElementTree as ET

import numpy as np
from PIL import Image, UnidentifiedImageError
import requests
import streamlit as st

from .data import ROOT

ENDPOINT = 'https://gibs.earthdata.nasa.gov/wms/epsg4326/best/wms.cgi'
CACHE = ROOT/'data/raw/satellite'
BBOX = [-9, 31, -6, 34]
SIZE = 900
PLATFORMS = ['Terra', 'Aqua']


def layer_name(platform):
    if platform not in PLATFORMS:
        raise ValueError('Choose Terra or Aqua MODIS.')
    return f'MODIS_{platform}_CorrectedReflectance_TrueColor'


def parse_availability(payload, platform):
    root = ET.fromstring(payload)
    ns = {'w':'http://www.opengis.net/wms'}
    for layer in root.findall('.//w:Layer', ns):
        name = layer.find('w:Name', ns)
        if name is None or name.text != layer_name(platform):
            continue
        dimension = next((d for d in layer.findall('w:Dimension', ns) if d.get('name') == 'time'), None)
        if dimension is None or not dimension.text:
            break
        ranges = []
        for item in dimension.text.split(','):
            parts = item.strip().split('/')
            first = date.fromisoformat(parts[0][:10])
            last = date.fromisoformat(parts[1][:10]) if len(parts) > 1 else first
            if len(parts) > 2 and parts[2] != 'P1D':
                raise ValueError('The imagery service did not describe a daily image record.')
            ranges.append([first.isoformat(), last.isoformat()])
        return dict(platform=platform, ranges=ranges, first=min(r[0] for r in ranges),
                    last=max(r[1] for r in ranges), checked_at=datetime.now(timezone.utc).isoformat(), stale=False)
    raise ValueError('The imagery service did not report dates for this satellite.')


@st.cache_data(show_spinner=False, ttl=86400, max_entries=2)
def imagery_availability(platform):
    """Metadata is fetched only when the user asks to choose comparison years."""
    layer_name(platform)
    path = CACHE/f'availability-{platform}.json'
    try:
        response = requests.get(ENDPOINT, params=dict(service='WMS', request='GetCapabilities', version='1.3.0'), timeout=(8, 30))
        response.raise_for_status()
        availability = parse_availability(response.content, platform)
    except (requests.RequestException, ValueError, ET.ParseError) as exc:
        if path.exists():
            availability = json.loads(path.read_text())
            availability['stale'] = True
            return availability
        raise ValueError('NASA’s date catalogue could not be reached. Try again or use the ready-made example.') from exc
    CACHE.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix('.json.part')
    temporary.write_text(json.dumps(availability, indent=2))
    os.replace(temporary, path)
    return availability


def comparison_dates(before_year, after_year, month, day, availability):
    try:
        before, after = date(before_year, month, day), date(after_year, month, day)
    except ValueError as exc:
        raise ValueError('Choose a day that exists in both selected years and the selected month.') from exc
    if before >= after:
        raise ValueError('Choose an after year later than the before year.')
    today = datetime.now(timezone.utc).date()
    for value in (before, after):
        if value > today:
            raise ValueError('Future satellite images are unavailable. Choose earlier dates.')
        if not any(first <= value.isoformat() <= last for first, last in availability['ranges']):
            raise ValueError(f'{value:%d %B %Y} is outside the satellite’s reported coverage or falls in a data gap. Choose another month or day.')
    return before, after


def validate_image(payload):
    if len(payload) > 6_000_000:
        raise ValueError('NASA returned an unexpectedly large image.')
    try:
        with Image.open(io.BytesIO(payload)) as image:
            if image.format != 'PNG' or image.size != (SIZE, SIZE):
                raise ValueError('NASA returned an unsupported image format or extent size.')
            pixels = np.asarray(image.convert('RGBA'))
    except (UnidentifiedImageError, OSError) as exc:
        raise ValueError('NASA returned no readable satellite image for the requested date.') from exc
    valid = pixels[:, :, 3] > 0
    coverage = float(valid.mean()*100)
    if not valid.any() or np.ptp(pixels[:, :, :3][valid]) == 0:
        raise ValueError('No usable image pixels were returned for this date and region. Try a different day.')
    return coverage


def fetch_image(platform, acquired, cache=CACHE):
    """Preserve original PNG responses, exact requests and checksums; no date substitution."""
    layer = layer_name(platform)
    params = dict(service='WMS', version='1.1.1', request='GetMap', layers=layer,
                  styles='', srs='EPSG:4326', bbox=','.join(map(str, BBOX)),
                  width=SIZE, height=SIZE, format='image/png', transparent='TRUE', time=acquired.isoformat())
    url = requests.Request('GET', ENDPOINT, params=params).prepare().url
    cache = Path(cache)
    filename = f'casablanca-{platform.lower()}-{acquired.isoformat()}.png'
    image_path, metadata_path = cache/filename, cache/(filename+'.json')
    if image_path.exists() and metadata_path.exists():
        recorded, payload = json.loads(metadata_path.read_text()), image_path.read_bytes()
        if recorded.get('url') == url and hashlib.sha256(payload).hexdigest() == recorded.get('sha256'):
            validate_image(payload)
            return recorded, payload
    try:
        response = requests.get(ENDPOINT, params=params, timeout=(8, 35))
        response.raise_for_status()
    except requests.RequestException as exc:
        raise ValueError(f'Could not load the {acquired.isoformat()} image from NASA. Your displayed comparison has been kept.') from exc
    payload = response.content
    coverage = validate_image(payload)
    recorded = dict(file=filename, date=acquired.isoformat(), platform=platform, instrument='MODIS',
                    layer=layer, url=url, sha256=hashlib.sha256(payload).hexdigest(),
                    retrieved_at=datetime.now(timezone.utc).isoformat(), valid_image_area_pct=coverage)
    cache.mkdir(parents=True, exist_ok=True)
    temporary = image_path.with_suffix('.png.part')
    temporary.write_bytes(payload)
    os.replace(temporary, image_path)
    temporary = metadata_path.with_suffix('.json.part')
    temporary.write_text(json.dumps(recorded, indent=2))
    os.replace(temporary, metadata_path)
    return recorded, payload


def fetch_comparison(platform, before, after, availability):
    # Validate again at the network boundary rather than relying on UI constraints.
    if before.month != after.month or before.day != after.day:
        raise ValueError('Choose the same calendar month and day for both years.')
    comparison_dates(before.year, after.year, before.month, before.day, availability)
    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda d: fetch_image(platform, d), [before, after]))
    manifest = dict(schema='saharawatch-satellite-pair-v1', pair_kind='custom',
                    title='Your Casablanca satellite comparison', source='NASA EOSDIS Global Imagery Browse Services (GIBS)',
                    credit=f'NASA GIBS / {platform} MODIS', projection='EPSG:4326', bbox=BBOX,
                    width=SIZE, height=SIZE, images=[result[0] for result in results],
                    documentation_url='https://nasa-gibs.github.io/gibs-api-docs/access-basics/',
                    context_url='https://worldview.earthdata.nasa.gov/',
                    review='User-selected dates; not manually reviewed for cloud cover. Valid-image area describes nontransparent pixels, not cloud-free area.',
                    limits='The views use the same satellite, month/day, projection and geographic extent. Clouds, haze, snow, overpass conditions and land management may still affect appearance. True-color images do not quantify vegetation health, reservoir volume or rainfall, or establish a cause of change.')
    return manifest, [result[1] for result in results]
