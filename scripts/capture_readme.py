"""Capture the current dashboard, rainfall playback and connected notebook for the README."""
import os
from pathlib import Path

from playwright.sync_api import sync_playwright, expect

ROOT=Path(__file__).resolve().parents[1]

with sync_playwright() as p:
    executable=Path.home()/'.cache/ms-playwright/chromium-1255/chrome-linux64/chrome'
    browser=p.chromium.launch(headless=True,executable_path=str(executable) if executable.exists() else None,
                             args=['--no-sandbox','--enable-unsafe-swiftshader'])
    page=browser.new_page(viewport={'width':1550,'height':1450})
    page.goto(os.environ.get('SAHARAWATCH_TEST_URL','http://localhost:8501'))
    page.get_by_role('button',name='Explore rainfall',exact=True).click(timeout=60000)
    page.get_by_role('heading',name='The curious case of the missing rain.',exact=True).wait_for(timeout=60000)
    page.wait_for_function("document.querySelector('.js-plotly-plot')?._fullLayout?.map?._subplot?.map?.loaded()",timeout=60000)
    page.screenshot(path=str(ROOT/'assets/dashboard.png'),full_page=True)
    page.get_by_role('tab',name='04 / Field notebook',exact=True).click()
    page.get_by_role('textbox',name='Field notes',exact=True).fill('A single dry year does not establish a long-term drying trend.')
    page.get_by_role('button',name='＋ Pin this evidence to the notebook',exact=True).click()
    expect(page.locator('.evidence-card')).to_have_count(1)
    page.get_by_text('I am still investigating',exact=True).click()
    page.get_by_role('button',name='Stop',exact=True).wait_for(state='hidden',timeout=30000)
    page.get_by_role('button',name='＋ Pin this evidence to the notebook',exact=True).click()
    expect(page.locator('.evidence-card')).to_have_count(2)
    page.get_by_role('combobox',name='Evidence relationship',exact=True).select_option('context')
    page.get_by_role('button',name='Connect clue 01',exact=True).click()
    page.get_by_role('button',name='Connect clue 02',exact=True).click()
    expect(page.locator('.string-line')).to_have_count(1)
    expect(page.locator('.board-status')).to_contain_text('Board saved',timeout=30000)
    page.locator('.board-scroll').screenshot(path=str(ROOT/'assets/evidence-board.png'))
    page.get_by_role('tab',name='01 / Evidence atlas',exact=True).click()
    page.get_by_text('Open the rainfall time machine',exact=True).click()
    element=page.locator('iframe[title="Animated rainfall map and synchronized location timeline"]')
    element.wait_for(timeout=60000)
    element.scroll_into_view_if_needed()
    frame=element.element_handle().content_frame()
    frame.wait_for_function("document.querySelector('.js-plotly-plot')?._fullLayout?.map?._subplot?.map?.loaded()",timeout=60000)
    element.screenshot(path=str(ROOT/'assets/rainfall-history.png'))
    assert not page.locator('[data-testid="stException"]').count()
    print('README dashboard, connected evidence board and rainfall playback screenshots refreshed.')
    browser.close()
