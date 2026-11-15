"""Date selection must preserve provenance, gaps and the last successfully loaded pair."""
import copy
from datetime import date
import io
from unittest.mock import Mock, patch

import numpy as np
from PIL import Image
import pytest
import requests
from streamlit.testing.v1 import AppTest

from saharawatch.data import ROOT, RAW
from saharawatch.satellite import load_satellite_pair
from saharawatch.satellite_source import (parse_availability, comparison_dates,
    validate_image, fetch_image, fetch_comparison)


def availability():
    return dict(platform='Terra', first='2000-02-24', last='2026-11-15', stale=False,
                ranges=[['2000-02-24','2016-02-18'], ['2016-02-27','2026-11-15']])


def png(coverage=1.):
    pixels = np.zeros((900,900,4), dtype=np.uint8)
    pixels[:int(900*coverage),:,0] = np.arange(900,dtype=np.uint16)%255
    pixels[:int(900*coverage),:,3] = 255
    out = io.BytesIO()
    Image.fromarray(pixels).save(out,format='PNG')
    return out.getvalue()


def test_time_domains_preserve_actual_gaps_and_reject_invalid_dates():
    xml = b'''<WMS_Capabilities xmlns="http://www.opengis.net/wms"><Capability><Layer><Layer>
    <Name>MODIS_Terra_CorrectedReflectance_TrueColor</Name>
    <Dimension name="time">2000-02-24/2016-02-18/P1D,2016-02-27/2026-11-15/P1D</Dimension>
    </Layer></Layer></Capability></WMS_Capabilities>'''
    result = parse_availability(xml,'Terra')
    assert result['ranges'] == availability()['ranges']
    assert comparison_dates(2022,2024,2,19,result) == (date(2022,2,19),date(2024,2,19))
    for before,after,month,day,message in [(2024,2022,2,19,'later'), (2000,2024,2,19,'gap'),
        (2016,2024,2,20,'gap'), (2023,2024,2,29,'exists'), (2022,2099,2,19,'Future')]:
        with pytest.raises(ValueError,match=message):
            comparison_dates(before,after,month,day,result)


def test_blank_and_wrong_size_responses_are_not_used_as_satellite_evidence():
    assert validate_image(png(.5)) == 50
    with pytest.raises(ValueError,match='usable'):
        validate_image(png(0))
    with pytest.raises(ValueError,match='readable'):
        validate_image(b'<ServiceException>Missing</ServiceException>')
    out = io.BytesIO()
    Image.new('RGBA',(100,100)).save(out,format='PNG')
    with pytest.raises(ValueError,match='size'):
        validate_image(out.getvalue())


def test_exact_dated_requests_are_cached_with_original_bytes_and_checksums(tmp_path):
    response = Mock(content=png())
    response.raise_for_status.return_value = None
    with patch('saharawatch.satellite_source.requests.get',return_value=response) as get:
        first, payload = fetch_image('Terra',date(2022,2,19),tmp_path)
        second, reused = fetch_image('Terra',date(2022,2,19),tmp_path)
    assert get.call_count == 1
    assert payload == reused == response.content and first == second
    params = get.call_args.kwargs['params']
    assert params['time'] == '2022-02-19' and params['layers'] == 'MODIS_Terra_CorrectedReflectance_TrueColor'
    assert params['transparent'] == 'TRUE'
    assert first['date'] == '2022-02-19' and first['valid_image_area_pct'] == 100
    assert first['sha256'] and first['url']
    with patch('saharawatch.satellite_source.requests.get',side_effect=requests.Timeout):
        with pytest.raises(ValueError,match='kept'):
            fetch_image('Aqua',date(2022,2,19),tmp_path)


def test_pair_does_not_fallback_to_other_dates_when_one_image_is_missing():
    def fetch(platform, acquired):
        if acquired.year == 2024:
            raise ValueError('No usable pixels')
        return dict(date=acquired.isoformat()), png()
    with patch('saharawatch.satellite_source.fetch_image',side_effect=fetch):
        with pytest.raises(ValueError,match='usable'):
            fetch_comparison('Terra',date(2022,2,19),date(2024,2,19),availability())


@pytest.mark.skipif(not RAW.exists(), reason='Requires downloaded GPCP')
def test_year_controls_apply_atomically_and_keep_selection_across_workspaces():
    import saharawatch.satellite as satellite
    manifest, payloads = load_satellite_pair()
    custom = copy.deepcopy(manifest)
    custom.update(pair_kind='custom')
    custom['images'][0]['date'] = '2022-02-19'
    custom['images'][0]['platform'] = 'Terra'
    at = AppTest.from_file(ROOT/'app.py').run(timeout=30)
    at.button(key='go_cases').click().run(timeout=30)
    at.selectbox(key='library_case').set_value('satellite').run(timeout=30)
    at.radio(key='case_path').set_value('Investigate on your own').run(timeout=30)
    at.text_area(key='mission_satellite_hypothesis').set_value('The visual difference may have several explanations.').run(timeout=30)
    at.button(key='mission_satellite_workspace').click().run(timeout=30)
    assert not at.exception and at.session_state['workspace_tab'] == 'Satellite images'
    with patch.object(satellite,'imagery_availability',return_value=availability()), patch.object(satellite,'fetch_comparison',return_value=(custom,payloads)) as fetch:
        at.radio(key='satellite_mode').set_value('Choose years').run(timeout=30)
        at.selectbox(key='satellite_before_year').set_value(2024)
        at.selectbox(key='satellite_after_year').set_value(2022)
        next(b for b in at.button if b.label == 'Load comparison').click().run(timeout=30)
        assert not at.exception and not fetch.called
        assert at.session_state['satellite_active_pair'][0]['images'][0]['date'] == '2023-02-12'
        at.selectbox(key='satellite_before_year').set_value(2022)
        at.selectbox(key='satellite_after_year').set_value(2024)
        next(b for b in at.button if b.label == 'Load comparison').click().run(timeout=30)
        assert not at.exception and fetch.call_count == 1
        assert at.session_state['satellite_active_pair'][0]['images'][0]['date'] == '2022-02-19'
        fetch.side_effect = ValueError('Image unavailable')
        at.selectbox(key='satellite_before_year').set_value(2021)
        next(b for b in at.button if b.label == 'Load comparison').click().run(timeout=30)
        assert at.session_state['satellite_active_pair'][0] == custom
        at.button(key='go_cases').click().run(timeout=30)
        assert not at.exception
        assert at.selectbox(key='library_case').value == 'satellite'
        assert at.radio(key='case_path').value == 'Investigate on your own'
        assert at.text_area(key='mission_satellite_hypothesis').value.startswith('The visual difference')
        at.button(key='mission_satellite_pin').click().run(timeout=30)
        assert at.session_state['clues'][-1]['period'] == '2022-02-19 / 2024-02-19'
        at.button(key='go_satellite').click().run(timeout=30)
        assert at.radio(key='satellite_mode').value == 'Choose years'
        assert at.selectbox(key='satellite_before_year').value == 2021
        assert at.session_state['satellite_active_pair'][0] == custom
