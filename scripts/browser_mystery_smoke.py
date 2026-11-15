"""Exercise the staged case, frozen evidence, export and mobile layout in a browser."""
import json
import os
from pathlib import Path

from playwright.sync_api import sync_playwright, expect


with sync_playwright() as p:
    executable = Path.home()/'.cache/ms-playwright/chromium-1255/chrome-linux64/chrome'
    browser = p.chromium.launch(headless=True,
        executable_path=str(executable) if executable.exists() else None,
        args=['--no-sandbox', '--enable-unsafe-swiftshader'])
    page = browser.new_page(viewport={'width':1440, 'height':1100})
    def idle():
        page.get_by_role('button', name='Stop', exact=True).wait_for(state='hidden', timeout=30000)
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.goto(os.environ.get('SAHARAWATCH_TEST_URL', 'http://localhost:8501'))
    page.get_by_role('tab', name='03 / Case files', exact=True).click(timeout=60000)
    expect(page.get_by_text('Case 005 / Has the rain returned?', exact=True)).to_be_visible()
    page.get_by_text('I need more evidence', exact=True).click()
    page.get_by_role('button', name='Break the seal & reveal clue 1', exact=True).click()
    expect(page.get_by_text('Clue 1 / A year is only one piece of the story', exact=True)).to_be_visible(timeout=30000)
    idle()
    page.get_by_role('button', name='Pin this clue to Field notebook', exact=True).click()
    expect(page.get_by_text('Clue pinned. Find it on the connected evidence board in Field notebook.', exact=True)).to_be_visible()
    idle()
    page.get_by_role('button', name='Reveal next clue →', exact=True).click()
    expect(page.get_by_text('Clue 2 / Keep a running balance', exact=True)).to_be_visible()
    idle()
    page.get_by_role('button', name='Reveal next clue →', exact=True).click()
    expect(page.get_by_text('Clue 3 / Cross-examine the national average', exact=True)).to_be_visible()
    idle()
    map_plot = page.locator('[data-testid="stPlotlyChart"]').filter(visible=True).last
    expect(map_plot).to_be_visible()
    page.get_by_text('Clue 3 / Cross-examine the national average', exact=True).scroll_into_view_if_needed()
    page.screenshot(path='assets/playable-mystery.png', full_page=True)
    page.get_by_role('button', name='Weigh the evidence →', exact=True).click()
    expect(page.get_by_role('button', name='Submit verdict & unseal the assessment', exact=True)).to_be_visible()
    idle()
    page.locator('[data-testid="stForm"]').filter(visible=True).get_by_text('Persistent rainfall deficit', exact=True).click()
    page.get_by_role('button', name='Submit verdict & unseal the assessment', exact=True).click()
    expect(page.get_by_text('Your verdict matches the calculated assessment. The evidence supports this description of the period.', exact=True)).to_be_visible()
    with page.expect_download() as download:
        page.get_by_role('button', name='Download the solved case · JSON', exact=True).click()
    case = json.loads(Path(download.value.path()).read_text())
    assert case['schema'] == 'saharawatch-playable-mystery-v1'
    assert case['prediction'] == 'I need more evidence'
    assert case['verdict'] == case['assessment']['status']
    assert case['assessment']['annual_years'] == [2023, 2024, 2025]
    assert case['source_note'] and case['source_sha256']
    for chart in case['charts']:
        assert json.loads(chart)['data']
    page.get_by_role('tab', name='04 / Field notebook', exact=True).click()
    expect(page.get_by_role('heading', name='Pinned evidence · 01', exact=True)).to_be_visible()
    page.get_by_role('tab', name='03 / Case files', exact=True).click()
    page.set_viewport_size({'width':390, 'height':844})
    page.get_by_role('button', name='Restart this mystery', exact=True).click()
    expect(page.get_by_role('button', name='Break the seal & reveal clue 1', exact=True)).to_be_visible()
    assert not page.evaluate('document.documentElement.scrollWidth > window.innerWidth')
    page.screenshot(path='assets/playable-mystery-mobile.png', full_page=True)
    assert not page.locator('[data-testid="stException"]').count()
    assert not errors, errors
    print('Playable mystery: clues, notebook pin, verdict, JSON download, restart and mobile layout passed')
    browser.close()
