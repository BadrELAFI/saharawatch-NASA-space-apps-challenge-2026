"""Verify Features 5–7 against a running local dashboard."""
from pathlib import Path
import csv
from io import StringIO
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    executable=Path.home()/'.cache/ms-playwright/chromium-1255/chrome-linux64/chrome'
    browser=p.chromium.launch(headless=True,executable_path=str(executable) if executable.exists() else None,
                             args=['--no-sandbox','--enable-unsafe-swiftshader'])
    page=browser.new_page(viewport={'width':1550,'height':1200})
    errors=[]
    page.on('pageerror',lambda e:errors.append(str(e)))
    page.goto('http://localhost:8501')
    page.get_by_text('Statistical trend diagnostics · Feature 5',exact=True).wait_for(timeout=60000)
    page.get_by_text('Statistical trend diagnostics · Feature 5',exact=True).click()
    with page.expect_download() as download:
        page.get_by_role('button',name='Download trend diagnostics · CSV',exact=True).click()
    rows=list(csv.DictReader(StringIO(Path(download.value.path()).read_text())))
    assert len(rows)==3 and any('HAC' in r['method'] for r in rows) and any('MK' in r['method'] for r in rows)
    print('Feature 5: OLS/HAC diagnostics exported')
    page.get_by_role('tab',name='02 / Cross-examine',exact=True).click()
    page.get_by_role('radiogroup',name='Comparison geography',exact=True).get_by_text('Grid cells',exact=True).click()
    page.get_by_role('spinbutton',name='Second cell latitude (° N)',exact=True).wait_for()
    with page.expect_download() as download:
        page.get_by_role('button',name='Download regional comparison · CSV',exact=True).click()
    rows=list(csv.DictReader(StringIO(Path(download.value.path()).read_text())))
    assert len(rows)==2 and all('°' in r['selection'] for r in rows)
    print('Feature 6: two grid-cell summaries exported')
    page.get_by_role('tab',name='03 / Case files',exact=True).click()
    page.get_by_role('heading',name='Explore a Climate Mystery',exact=True).wait_for()
    titles=['Case 001 / Is Morocco becoming drier?','Case 002 / Across the border','Case 003 / The dry-year files','Case 004 / Follow the strongest trail']
    for i,title in enumerate(titles):
        card=page.locator('[data-testid="stVerticalBlock"]').filter(has=page.get_by_role('heading',name=title,exact=True)).last
        card.get_by_role('button',name='Open this case',exact=True).click()
        if i==0:
            page.get_by_text('Morocco: ',exact=False).last.wait_for(timeout=30000)
        elif i==1:
            page.get_by_role('combobox',name='Compare Morocco with',exact=True).wait_for(timeout=30000)
        elif i==2:
            page.get_by_role('combobox',name='Investigate a historical year',exact=True).wait_for(timeout=30000)
        else:
            page.get_by_role('button',name='Download ranked trend cells · CSV',exact=True).wait_for(timeout=30000)
        assert page.locator('[data-testid="stException"]').count()==0
    page.wait_for_function("[...document.querySelectorAll('.js-plotly-plot')].some(p => p.data?.[0]?.name === 'Absolute trend rank' && p._fullLayout?.map?._subplot?.map?.loaded())",timeout=60000)
    with page.expect_download() as download:
        page.get_by_role('button',name='Download ranked trend cells · CSV',exact=True).click()
    rows=list(csv.DictReader(StringIO(Path(download.value.path()).read_text())))
    assert len(rows)==416 and rows[0]['rank']=='1'
    magnitudes=[float(r['absolute_trend_mm_decade']) for r in rows]
    assert magnitudes==sorted(magnitudes,reverse=True)
    assert not errors,errors
    print('Feature 7: four cases rendered; ranked map loaded; all 416 cells exported in magnitude order')
    browser.close()
