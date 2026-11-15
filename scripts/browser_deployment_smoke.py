"""Verify a deployed app through real data, satellite imagery and a rendered report."""
import io
import os
from pathlib import Path
import zipfile

from playwright.sync_api import expect, sync_playwright


with sync_playwright() as p:
    installed=Path.home()/'.cache/ms-playwright/chromium-1255/chrome-linux64/chrome'
    browser=p.chromium.launch(headless=True,executable_path=str(installed) if installed.exists() else None,
        args=['--no-sandbox','--enable-unsafe-swiftshader'])
    page=browser.new_page(viewport={'width':1500,'height':1200})
    errors=[]
    page.on('pageerror',lambda error:errors.append(str(error)))
    page.goto(os.environ.get('SAHARAWATCH_TEST_URL','http://localhost:8501'))
    expect(page.locator('.office-intro')).to_be_visible(timeout=60000)
    expect(page.locator('.st-key-landing_files .file-folder')).to_have_count(6)
    expect(page.get_by_role('switch',name='Desk sounds',exact=True)).not_to_be_checked()
    page.get_by_role('button',name='Explore rainfall',exact=True).click()
    expect(page.locator('.st-key-exhibit_atlas')).to_be_visible(timeout=60000)
    page.wait_for_function("document.querySelector('.js-plotly-plot')?._fullLayout?.map?._subplot?.map?.loaded()",timeout=60000)
    page.get_by_role('tab',name='04 / Field notebook',exact=True).click()
    page.get_by_role('textbox',name='Field notes',exact=True).fill('Deployment verification: retain the observed rainfall evidence.')
    page.get_by_role('button',name='＋ Pin this evidence to the notebook',exact=True).click()
    page.get_by_role('button',name='Build illustrated investigation report',exact=True).click()
    download_button=page.get_by_role('button',name='Download illustrated report · ZIP',exact=True)
    expect(download_button).to_be_visible(timeout=90000)
    with page.expect_download() as download:
        download_button.click()
    with zipfile.ZipFile(io.BytesIO(Path(download.value.path()).read_bytes())) as archive:
        assert archive.read('charts/clue_01_rainfall.png').startswith(b'\x89PNG')
        assert archive.read('charts/clue_01_anomalies.png').startswith(b'\x89PNG')
        assert b'data:image/png;base64,' in archive.read('report.html')
        assert b'Deployment verification' in archive.read('evidence.json')
    page.get_by_role('button',name='Compare satellite images',exact=True).click()
    expect(page.locator('.st-key-exhibit_satellite_photos')).to_be_visible(timeout=30000)
    expect(page.locator('.satellite-frame img')).to_have_count(2)
    for image in page.locator('.satellite-frame img').all():
        expect(image).to_have_js_property('naturalWidth',900)
    assert not page.locator('[data-testid="stException"]').count()
    assert not errors,errors
    browser.close()
    print('Deployment passed: desk, default mute, real rainfall map, pinned evidence, Chromium report download and bundled satellite images.')
