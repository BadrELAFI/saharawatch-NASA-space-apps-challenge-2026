"""Verify prominent country explanations and preservation in illustrated reports."""
import csv
import io
import json
import zipfile
from pathlib import Path
from playwright.sync_api import sync_playwright,expect

with sync_playwright() as p:
    executable=Path.home()/'.cache/ms-playwright/chromium-1255/chrome-linux64/chrome'
    browser=p.chromium.launch(headless=True,executable_path=str(executable) if executable.exists() else None,
                             args=['--no-sandbox','--enable-unsafe-swiftshader'])
    page=browser.new_page(viewport={'width':1550,'height':1400})
    errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
    page.goto('http://localhost:8501')
    verdict=page.locator('.briefing-verdict')
    verdict.wait_for(timeout=60000)
    page.wait_for_function("document.querySelector('.js-plotly-plot')?._fullLayout?.map?._subplot?.map?.loaded()",timeout=60000)
    expect(verdict.locator('h3')).to_have_text('Persistent rainfall deficit')
    assert page.locator('.js-plotly-plot').first.bounding_box()['y'] < verdict.bounding_box()['y']
    assert '32.3% below' in verdict.inner_text() and '2023–2025' in verdict.inner_text()
    assert '2025 increased' in verdict.inner_text()
    page.screenshot(path='assets/country-briefing.png',full_page=True)
    page.get_by_role('button',name='Stop',exact=True).wait_for(state='hidden',timeout=30000)
    page.get_by_role('combobox',name='Country briefing',exact=True).scroll_into_view_if_needed()
    page.get_by_role('combobox',name='Country briefing',exact=True).click()
    page.get_by_role('option',name='Saudi Arabia',exact=True).click()
    expect(verdict.locator('h3')).to_have_text('No multi-year rainfall deficit',timeout=30000)
    assert '41.8% above' in verdict.inner_text() and '2025 decreased' in verdict.inner_text()
    expect(page.get_by_role('combobox',name='Country',exact=True)).to_have_value('Saudi Arabia')
    page.get_by_text('Compare recent precipitation conditions across countries',exact=True).click()
    with page.expect_download() as download:
        page.get_by_role('button',name='Download country rainfall briefings · CSV',exact=True).click()
    rows=list(csv.DictReader(io.StringIO(Path(download.value.path()).read_text())))
    assert len(rows)==11 and all(r['recent_start']=='2023' and r['recent_end']=='2025' for r in rows)
    page.get_by_role('tab',name='04 / Field notebook',exact=True).click()
    page.get_by_role('button',name='＋ Pin this evidence to the notebook',exact=True).click()
    page.get_by_text('Evidence pinned with its location, period, baseline, and uncertainty.',exact=True).wait_for()
    page.get_by_role('button',name='Build illustrated investigation report',exact=True).click()
    page.get_by_role('button',name='Download illustrated report · ZIP',exact=True).wait_for(timeout=60000)
    with page.expect_download() as download:
        page.get_by_role('button',name='Download illustrated report · ZIP',exact=True).click()
    with zipfile.ZipFile(download.value.path()) as z:
        evidence=json.loads(z.read('evidence.json'))[0]
        assert evidence['recent_country_briefing']['country']=='Saudi Arabia'
        assert evidence['recent_country_briefing']['recent_end']==2025
        assert '41.8% above' in evidence['recent_country_explanation']
        recent=list(csv.DictReader(io.StringIO(z.read('data/clue_01_recent_country.csv').decode())))
        assert [r['year'] for r in recent]==['2023','2024','2025']
    assert not page.locator('[data-testid="stException"]').count()
    mobile=browser.new_page(viewport={'width':390,'height':844},is_mobile=True,has_touch=True)
    mobile.on('pageerror',lambda e:errors.append(str(e)))
    mobile.goto('http://localhost:8501');mobile.locator('.briefing-verdict').wait_for(timeout=60000)
    assert not mobile.evaluate('document.documentElement.scrollWidth > window.innerWidth')
    assert not errors,errors
    print('Real country narratives, 11-country CSV, pinned briefing archive and mobile layout: passed')
    browser.close()
