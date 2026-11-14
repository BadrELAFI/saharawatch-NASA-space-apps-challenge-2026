"""Browser check for precipitation departures, SPI controls, and exported real data."""
import csv
from io import StringIO
from pathlib import Path
from playwright.sync_api import sync_playwright,expect

with sync_playwright() as p:
    executable=Path.home()/'.cache/ms-playwright/chromium-1255/chrome-linux64/chrome'
    browser=p.chromium.launch(headless=True,executable_path=str(executable) if executable.exists() else None,
                             args=['--no-sandbox','--enable-unsafe-swiftshader'])
    page=browser.new_page(viewport={'width':1550,'height':1450})
    errors=[]
    page.on('pageerror',lambda e:errors.append(str(e)))
    page.goto('http://localhost:8501')
    page.get_by_role('tab',name='06 / Rainfall deficits & SPI',exact=True).wait_for(timeout=60000)
    page.get_by_role('tab',name='06 / Rainfall deficits & SPI',exact=True).click()
    page.get_by_role('radiogroup',name='Anomaly time scale',exact=True).get_by_text('Monthly',exact=True).click()
    page.get_by_role('combobox',name='Departure measure',exact=True).click()
    page.get_by_role('option',name='Relative anomaly (%)',exact=True).click()
    page.get_by_text('Enable validated gamma SPI',exact=True).click()
    page.get_by_role('combobox',name='SPI accumulation scale',exact=True).wait_for(timeout=60000)
    expect(page.get_by_role('button',name='Download SPI observations · CSV')).to_be_enabled(timeout=60000)
    for scale in ['SPI-3','SPI-12']:
        page.get_by_role('combobox',name='SPI accumulation scale',exact=True).click()
        page.get_by_role('option',name=scale,exact=True).click()
        page.wait_for_function("scale => [...document.querySelectorAll('.js-plotly-plot')].some(p => p.layout?.yaxis?.title?.text === scale + ' (dimensionless)')",arg=scale,timeout=30000)
        with page.expect_download() as downloaded:
            page.get_by_role('button',name='Download SPI observations · CSV').click()
        rows=list(csv.DictReader(StringIO(Path(downloaded.value.path()).read_text())))
        assert len(rows)==288 and len({r['time'] for r in rows})==288
        assert all(r['spi']!='' and r['scale_months']==scale[4:] for r in rows)
        print(scale+': rendered; 288 unique observed months exported')
    assert not page.locator('[data-testid="stException"]').count()
    page.get_by_role('heading',name='Precipitation deficits & drought indicators').scroll_into_view_if_needed()
    page.screenshot(path='assets/drought-indicators.png',full_page=True)
    assert not errors,errors
    print('Relative anomalies, SPI-3, SPI-12, and browser errors: passed')
    browser.close()
