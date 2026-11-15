"""Check real image rendering, accessible wiping, preserved state and offline export."""
import hashlib
import json
import os
from pathlib import Path
import zipfile

from playwright.sync_api import sync_playwright, expect


with sync_playwright() as p:
    executable = Path.home()/'.cache/ms-playwright/chromium-1255/chrome-linux64/chrome'
    browser = p.chromium.launch(headless=True,
        executable_path=str(executable) if executable.exists() else None,
        args=['--no-sandbox', '--enable-unsafe-swiftshader'])
    page = browser.new_page(viewport={'width':1440, 'height':1400}, has_touch=True)
    errors, external_images = [], []
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.on('request', lambda request: external_images.append(request.url)
            if 'gibs.earthdata.nasa.gov' in request.url else None)
    page.goto(os.environ.get('SAHARAWATCH_TEST_URL', 'http://localhost:8501'))
    page.get_by_role('button', name='Compare satellite images', exact=True).click(timeout=60000)
    frame = page.locator('.satellite-frame')
    expect(frame).to_be_visible(timeout=30000)
    expect(page.locator('.satellite-frame img')).to_have_count(2)
    for picture in page.locator('.satellite-frame img').all():
        expect(picture).to_have_js_property('naturalWidth',900)
    slider = page.get_by_role('slider', name='Reveal the earlier satellite image', exact=True)
    expect(slider).to_have_value('50')
    slider.focus()
    slider.press('ArrowRight')
    expect(slider).to_have_value('51')
    expect(page.locator('.satellite-comparison-root')).to_have_attribute('data-saved-position','51')
    page.get_by_role('button', name='Stop', exact=True).wait_for(state='hidden', timeout=30000)
    frame.scroll_into_view_if_needed()
    box = frame.bounding_box()
    page.mouse.move(box['x']+box['width']*.5, box['y']+box['height']*.5)
    page.mouse.down()
    page.mouse.move(box['x']+box['width']*.75, box['y']+box['height']*.5)
    page.mouse.up()
    expect(slider).to_have_value('75')
    expect(page.locator('.satellite-comparison-root')).to_have_attribute('data-saved-position','75')
    page.get_by_role('checkbox', name='Show GPCP rainfall cells (2.5°)', exact=True).check()
    expect(page.locator('.satellite-grid')).to_be_visible()
    expect(page.locator('.satellite-comparison-root')).to_have_attribute('data-saved-grid','true')
    assert page.locator('.satellite-grid rect').count() == 4
    page.get_by_role('button', name='Stop', exact=True).wait_for(state='hidden', timeout=30000)
    expect(slider).to_have_value('75')
    page.locator('.satellite-comparison-root').evaluate('(element) => element.scrollIntoView({block:"center"})')
    page.locator('.satellite-comparison-root').screenshot(path='assets/satellite-comparison.png')
    with page.expect_download() as download:
        page.get_by_role('button', name='Download satellite evidence · ZIP', exact=True).click()
    with zipfile.ZipFile(download.value.path()) as archive:
        evidence = json.loads(archive.read('evidence.json'))
        for image in evidence['images']:
            assert hashlib.sha256(archive.read(image['file'])).hexdigest() == image['sha256']
        assert evidence['rainfall_context']['cell_latitude'] == 33.75
        assert evidence['rainfall_context']['cell_longitude'] == -8.75
        assert evidence['rainfall_context']['summary'][1]['precipitation_mm'] > 0
        assert '2024-02-01' in archive.read('rainfall.csv').decode()
    # Switching tabs preserves the component's wipe position and cell overlay.
    page.get_by_role('tab', name='04 / Field notebook', exact=True).click()
    page.get_by_role('tab', name='Satellite images', exact=True).click()
    expect(slider).to_have_value('75')
    expect(page.get_by_role('checkbox', name='Show GPCP rainfall cells (2.5°)', exact=True)).to_be_checked()
    page.set_viewport_size({'width':390, 'height':844})
    frame.scroll_into_view_if_needed()
    slider.focus()
    slider.press('Home')
    expect(slider).to_have_value('0')
    expect(page.locator('.satellite-comparison-root')).to_have_attribute('data-saved-position','0')
    slider.press('End')
    expect(slider).to_have_value('100')
    expect(page.locator('.satellite-comparison-root')).to_have_attribute('data-saved-position','100')
    frame.scroll_into_view_if_needed()
    box = frame.bounding_box()
    frame.tap(position={'x':box['width']*.5, 'y':box['height']*.5})
    expect(slider).to_have_value('50')
    expect(page.locator('.satellite-comparison-root')).to_have_attribute('data-saved-position','50')
    assert not page.evaluate('document.documentElement.scrollWidth > window.innerWidth')
    frame.scroll_into_view_if_needed()
    page.locator('.satellite-comparison-root').screenshot(path='assets/satellite-comparison-mobile.png')
    assert not external_images, external_images
    assert not page.locator('[data-testid="stException"]').count()
    assert not errors, errors
    print('Satellite comparison: real imagery, keyboard and drag controls, grid alignment, state, ZIP and mobile passed')
    browser.close()
