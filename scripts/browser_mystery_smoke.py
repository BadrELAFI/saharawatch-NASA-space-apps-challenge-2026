"""Exercise Case 005 through the shared three-question quiz and notebook flow."""
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
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.goto(os.environ.get('SAHARAWATCH_TEST_URL', 'http://localhost:8501'))
    page.get_by_role('tab', name='03 / Case files', exact=True).click(timeout=60000)
    page.get_by_role('combobox', name='Choose a case', exact=True).click()
    page.get_by_role('option', name='Case 005 / Has the rain returned?', exact=True).click()
    expect(page.get_by_role('heading', name='Case 005 / Has the rain returned?', exact=True).filter(visible=True)).to_be_visible(timeout=30000)
    page.get_by_role('textbox', name='Your first hypothesis', exact=True).fill('I need more evidence')
    page.get_by_role('button', name='Open quiz', exact=True).click()
    for step, choice in enumerate(['Below baseline', 'Below expectation', 'Persistent rainfall deficit']):
        form = page.locator('[data-testid="stForm"]').filter(visible=True)
        expect(form).to_be_visible()
        page.get_by_role('button', name='Stop', exact=True).wait_for(state='hidden', timeout=30000)
        form.get_by_text(choice, exact=True).click()
        page.get_by_role('button', name='Check my answer', exact=True).click()
        expect(page.get_by_text('Your answer matches the evidence:', exact=False)).to_be_visible()
        page.get_by_role('button', name='Stop', exact=True).wait_for(state='hidden', timeout=30000)
        page.get_by_role('button', name='Pin this clue to Field notebook', exact=True).click()
        expect(page.get_by_text('Clue pinned. It is available in Field notebook and the connected evidence board.', exact=True)).to_be_visible()
        page.get_by_role('button', name='Stop', exact=True).wait_for(state='hidden', timeout=30000)
        if step == 2:
            page.screenshot(path='assets/playable-mystery.png', full_page=True)
        page.get_by_role('button', name='Reveal next clue →' if step < 2 else 'Finish quiz →', exact=True).click()
    expect(page.get_by_text('Case complete · 3 / 3 answers matched the evidence on the first try.', exact=True)).to_be_visible()
    page.get_by_role('button', name='Stop', exact=True).wait_for(state='hidden', timeout=30000)
    with page.expect_download() as download:
        page.get_by_role('button', name='Download solved quiz · JSON', exact=True).click()
    report = json.loads(Path(download.value.path()).read_text())
    assert report['schema'] == 'saharawatch-case-quiz-v1'
    assert report['context']['recent_assessment']['status'] == 'Persistent rainfall deficit'
    assert report['context']['source_sha256'] and len(report['answers']) == 3
    page.get_by_role('tab', name='04 / Field notebook', exact=True).click()
    expect(page.get_by_role('heading', name='Pinned evidence · 03', exact=True)).to_be_visible()
    page.get_by_role('tab', name='03 / Case files', exact=True).click()
    page.get_by_role('button', name='Restart quiz with current settings', exact=True).click()
    expect(page.get_by_role('button', name='Open quiz', exact=True)).to_be_visible()
    page.set_viewport_size({'width':390, 'height':844})
    assert not page.evaluate('document.documentElement.scrollWidth > window.innerWidth')
    page.get_by_role('combobox', name='Choose a case', exact=True).scroll_into_view_if_needed()
    page.screenshot(path='assets/playable-mystery-mobile.png', full_page=True)
    assert not page.locator('[data-testid="stException"]').count()
    assert not errors, errors
    print('Case 005 quiz: three evidence questions, notebook pins, export, restart and mobile passed')
    browser.close()
