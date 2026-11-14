"""Local QA: actual map click, inference, fractional weighting, rich report, real POWER."""
import csv
import io
import zipfile
from pathlib import Path
from playwright.sync_api import sync_playwright,expect

with sync_playwright() as p:
    executable=Path.home()/'.cache/ms-playwright/chromium-1255/chrome-linux64/chrome'
    browser=p.chromium.launch(headless=True,executable_path=str(executable) if executable.exists() else None,
                             args=['--no-sandbox','--enable-unsafe-swiftshader'])
    page=browser.new_page(viewport={'width':1550,'height':1200})
    errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
    page.goto('http://localhost:8501')
    page.wait_for_function("document.querySelector('.js-plotly-plot')?._fullLayout?.map?._subplot?.map?.loaded()",timeout=60000)
    canvas=page.locator('.maplibregl-canvas').first;canvas.scroll_into_view_if_needed();bounds=canvas.bounding_box()
    pixel=page.evaluate("document.querySelector('.js-plotly-plot')._fullLayout.map._subplot.map.project([11.25,28.75])")
    page.mouse.click(bounds['x']+pixel['x'],bounds['y']+pixel['y'])
    expect(page.get_by_role('spinbutton',name='Longitude (° E)',exact=True)).to_have_value('11.25',timeout=30000)
    expect(page.get_by_role('spinbutton',name='Latitude (° N)',exact=True)).to_have_value('28.75',timeout=30000)
    print('Map click selects actual cell coordinates')
    for method in ['Newey–West HAC','Modified Mann–Kendall']:
        page.get_by_role('combobox',name='Trend inference',exact=True).click()
        page.get_by_role('option',name=method,exact=True).click()
        expect(page.get_by_role('combobox',name='Trend inference',exact=True)).to_have_value(method)
    page.get_by_role('combobox',name='Map indicator',exact=True).click()
    page.get_by_role('option',name='Trend significance',exact=True).click()
    page.get_by_role('radiogroup',name='Selection mode',exact=True).get_by_text('Country aggregation',exact=True).click()
    page.get_by_role('combobox',name='Country weighting',exact=True).click()
    page.get_by_role('option',name='Fractional area',exact=True).click()
    page.get_by_role('heading',name='Morocco · country mask',exact=True).wait_for(timeout=30000)
    print('Robust inference and fractional country aggregation render')
    page.get_by_role('tab',name='04 / Field notebook',exact=True).click()
    page.get_by_role('button',name='＋ Pin this evidence to the notebook',exact=True).click()
    page.get_by_text('Evidence pinned with its location, period, baseline, and uncertainty.',exact=True).wait_for()
    page.get_by_role('button',name='Build illustrated investigation report',exact=True).click()
    page.get_by_role('button',name='Download illustrated report · ZIP',exact=True).wait_for(timeout=60000)
    with page.expect_download() as download:
        page.get_by_role('button',name='Download illustrated report · ZIP',exact=True).click()
    with zipfile.ZipFile(download.value.path()) as z:
        assert z.read('charts/clue_01_rainfall.png').startswith(b'\x89PNG')
        assert z.read('charts/clue_01_anomalies.png').startswith(b'\x89PNG')
        assert b'data:image/png;base64,' in z.read('report.html')
        assert b'Modified Mann' in z.read('evidence.json')
        assert b'Fractional area' in z.read('evidence.json')
        assert 'data/clue_01.csv' in z.namelist()
    print('Illustrated report downloaded with pinned methods, data and PNG charts')
    page.get_by_role('radiogroup',name='Selection mode',exact=True).get_by_text('Grid cell',exact=True).click()
    page.get_by_role('combobox',name='Environmental variable',exact=True).click()
    page.get_by_role('option',name='Temperature at 2 m · NASA POWER',exact=True).click()
    page.get_by_role('heading',name='Temperature at 2 m · NASA POWER / MERRA-2',exact=True).wait_for(timeout=30000)
    page.get_by_role('button',name='Load real temperature observations',exact=True).click()
    page.get_by_role('button',name='Download aligned temperature and rainfall · CSV',exact=True).wait_for(timeout=120000)
    with page.expect_download() as download:
        page.get_by_role('button',name='Download aligned temperature and rainfall · CSV',exact=True).click()
    rows=list(csv.DictReader(io.StringIO(Path(download.value.path()).read_text())))
    assert len(rows)==24 and all(r['temperature_c'] for r in rows)
    with page.expect_download() as download:
        page.get_by_role('button',name='Download temperature provenance · JSON',exact=True).click()
    assert 'MERRA2' in Path(download.value.path()).read_text()
    assert page.locator('[data-testid="stException"]').count()==0
    assert not errors,errors
    print('Real NASA POWER temperature and GPCP rainfall aligned and exported; no browser errors')
    browser.close()
