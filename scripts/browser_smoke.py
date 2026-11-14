"""Optional browser verification. Run against an already running local Streamlit server."""
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[1]
with sync_playwright() as p:
    executable=Path.home()/'.cache/ms-playwright/chromium-1255/chrome-linux64/chrome'
    browser=p.chromium.launch(headless=True,executable_path=str(executable) if executable.exists() else None,
                               args=['--no-sandbox','--enable-unsafe-swiftshader'])
    page=browser.new_page(viewport={'width':1550,'height':1450},device_scale_factor=1)
    errors=[]
    page.on('pageerror',lambda error:errors.append(str(error)))
    page.goto('http://localhost:8501')
    page.get_by_role('heading',name='Follow the rainfall. Find the change.').wait_for(timeout=60000)
    page.locator('.js-plotly-plot').first.wait_for(timeout=60000)
    page.wait_for_function("document.querySelector('.js-plotly-plot')?._fullLayout?.map?._subplot?.map?.loaded()",timeout=60000)
    assert page.locator('[data-testid="stException"]').count()==0
    print('Desktop plots:',page.locator('.js-plotly-plot').count())
    print('Map WebGL canvases:',page.locator('.maplibregl-canvas').count())
    print('Browser errors:',errors)
    assert not errors
    page.screenshot(path=str(ROOT/'assets/dashboard.png'),full_page=True)
    for name in ['Linear trend','Annual anomaly','Trend significance']:
        page.get_by_role('combobox',name='Map indicator',exact=True).click()
        page.get_by_role('option',name=name,exact=True).click()
        page.wait_for_timeout(600)
        assert page.locator('[data-testid="stException"]').count()==0
    print('Browser indicator switching: passed')
    # Country selection exercises server-side boundary aggregation.
    page.get_by_text('Country aggregation',exact=True).click()
    page.get_by_role('heading',name='Morocco · country mask').wait_for(timeout=30000)
    print('Country mask selection: passed')
    page.get_by_role('tab',name='Regional comparison',exact=True).click()
    page.get_by_role('heading',name='Different regions. A shared record.').wait_for(timeout=30000)
    page.screenshot(path=str(ROOT/'assets/comparison.png'))
    page.get_by_role('tab',name='Data & methodology',exact=True).click()
    page.get_by_role('heading',name='Observations first. Methods in the open.').wait_for(timeout=30000)
    assert page.locator('[data-testid="stException"]').count()==0
    # New narrow viewport verifies automatic sidebar collapse and horizontal overflow.
    mobile=browser.new_page(viewport={'width':390,'height':844},device_scale_factor=1,is_mobile=True,has_touch=True)
    mobile.on('pageerror',lambda error:errors.append(str(error)))
    mobile.goto('http://localhost:8501')
    mobile.get_by_role('heading',name='Follow the rainfall. Find the change.').wait_for(timeout=60000)
    mobile.wait_for_function("document.querySelector('.js-plotly-plot')?._fullLayout?.map?._subplot?.map?.loaded()",timeout=60000)
    assert mobile.locator('[data-testid="stException"]').count()==0
    overflow=mobile.evaluate('document.documentElement.scrollWidth > window.innerWidth')
    assert not overflow,'Mobile layout overflows horizontally'
    mobile.screenshot(path=str(ROOT/'assets/mobile.png'),full_page=True)
    print('Mobile 390px viewport: passed; no horizontal overflow')
    assert not errors,errors
    browser.close()
