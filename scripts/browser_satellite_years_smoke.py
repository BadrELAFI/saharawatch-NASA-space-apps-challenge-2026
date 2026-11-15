"""Verify direct discovery, real custom-year imagery, safe errors and casework handoff."""
import hashlib
import json
import os
import re
from pathlib import Path
import zipfile

from playwright.sync_api import sync_playwright, expect, TimeoutError as PlaywrightTimeoutError


with sync_playwright() as p:
    executable = Path.home()/'.cache/ms-playwright/chromium-1255/chrome-linux64/chrome'
    browser = p.chromium.launch(headless=True,executable_path=str(executable) if executable.exists() else None,
                               args=['--no-sandbox','--enable-unsafe-swiftshader'])
    page = browser.new_page(viewport={'width':1440,'height':1400})
    errors = []
    page.on('pageerror',lambda error:errors.append(str(error)))
    page.goto(os.environ.get('SAHARAWATCH_TEST_URL','http://localhost:8501'))
    page.get_by_role('button',name='Compare satellite images',exact=True).click(timeout=60000)
    expect(page.locator('.satellite-frame')).to_be_visible(timeout=30000)
    expect(page.get_by_text('Showing: 2023-02-12 (Aqua) → 2024-02-19 (Terra)',exact=True)).to_be_visible()
    page.get_by_text('Choose years',exact=True).click()
    page.get_by_role('combobox',name='Before year',exact=True).wait_for(timeout=60000)

    def select(label, option):
        selector = page.get_by_role('combobox',name=label,exact=True)
        for attempt in range(3):
            page.get_by_role('button',name='Stop',exact=True).wait_for(state='hidden',timeout=30000)
            selector.scroll_into_view_if_needed()
            selector.click()
            selector.fill(option)
            try:
                page.get_by_role('option',name=option,exact=True).click(timeout=3000)
                break
            except PlaywrightTimeoutError:
                page.keyboard.press('Escape')
                if attempt == 2:
                    raise
        expect(selector).to_have_value(option)

    select('Before year','2022')
    select('After year','2024')
    page.get_by_role('button',name='Load comparison',exact=True).click()
    expect(page.get_by_text('Showing: 2022-02-19 (Terra) → 2024-02-19 (Terra)',exact=True)).to_be_visible(timeout=90000)
    pictures = page.locator('.satellite-frame img')
    expect(pictures).to_have_count(2)
    for picture in pictures.all():
        expect(picture).to_have_js_property('naturalWidth',900,timeout=30000)
        expect(picture).to_have_attribute('src',re.compile('^data:image/png'))
    page.get_by_role('button',name='Stop',exact=True).wait_for(state='hidden',timeout=30000)
    page.get_by_role('heading',name='Compare satellite images',exact=True).scroll_into_view_if_needed()
    page.screenshot(path='assets/satellite-year-controls.png',full_page=True)
    with page.expect_download() as download:
        page.get_by_role('button',name='Download satellite evidence · ZIP',exact=True).click()
    with zipfile.ZipFile(download.value.path()) as archive:
        manifest = json.loads(archive.read('evidence.json'))
        assert [image['date'] for image in manifest['images']] == ['2022-02-19','2024-02-19']
        assert all(image['platform'] == 'Terra' for image in manifest['images'])
        for image in manifest['images']:
            assert hashlib.sha256(archive.read(image['file'])).hexdigest() == image['sha256']
        assert manifest['rainfall_context']['summary'][0]['image_date'] == '2022-02-19'
    select('Before year','2024')
    page.get_by_role('button',name='Load comparison',exact=True).click()
    expect(page.get_by_text('Choose an after year later than the before year.',exact=False)).to_be_visible()
    expect(page.get_by_text('Showing: 2022-02-19 (Terra) → 2024-02-19 (Terra)',exact=True)).to_be_visible()
    page.get_by_role('button',name='Investigate this comparison',exact=True).click()
    expect(page.get_by_text('Current evidence: 2022-02-19 → 2024-02-19.',exact=False)).to_be_visible()
    hypothesis = page.get_by_role('textbox',name='Working hypothesis for this case',exact=True)
    hypothesis.fill('The images alone cannot establish a cause.')
    hypothesis.press('Tab')
    expect(page.get_by_role('button',name='Pin current evidence to Field notebook',exact=True)).to_be_enabled()
    page.get_by_role('button',name='Stop',exact=True).wait_for(state='hidden',timeout=30000)
    page.get_by_role('button',name='Open satellite workspace',exact=True).click()
    expect(page.get_by_text('Showing: 2022-02-19 (Terra) → 2024-02-19 (Terra)',exact=True)).to_be_visible()
    expect(page.get_by_role('combobox',name='Before year',exact=True)).to_have_value('2024')
    page.set_viewport_size({'width':390,'height':844})
    page.get_by_role('heading',name='Compare satellite images',exact=True).scroll_into_view_if_needed()
    assert not page.evaluate('document.documentElement.scrollWidth > window.innerWidth')
    form = page.locator('[data-testid="stForm"]').filter(visible=True)
    form.evaluate('(element) => element.scrollIntoView({block:"center"})')
    form.screenshot(path='assets/satellite-year-controls-mobile.png')
    assert not page.locator('[data-testid="stException"]').count()
    assert not errors,errors
    print('Satellite years: direct access, actual 2022/2024 Terra images, ZIP provenance, invalid-year handling, case handoff and mobile passed')
    browser.close()
