"""Verify all six case entries, quiz feedback, saved missions and mobile navigation."""
import json
import os
from pathlib import Path

from playwright.sync_api import sync_playwright, expect, TimeoutError as PlaywrightTimeoutError


with sync_playwright() as p:
    executable = Path.home()/'.cache/ms-playwright/chromium-1255/chrome-linux64/chrome'
    browser = p.chromium.launch(headless=True,
        executable_path=str(executable) if executable.exists() else None,
        args=['--no-sandbox', '--enable-unsafe-swiftshader'])
    page = browser.new_page(viewport={'width':1440, 'height':1200}, has_touch=True)
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.goto(os.environ.get('SAHARAWATCH_TEST_URL', 'http://localhost:8501'))
    page.get_by_role('tab', name='03 / Case files', exact=True).click(timeout=60000)

    def idle():
        page.get_by_role('button', name='Stop', exact=True).wait_for(state='hidden', timeout=30000)

    def choose(title):
        idle()
        selector = page.get_by_role('combobox', name='Choose a case', exact=True)
        selector.scroll_into_view_if_needed()
        selector.click()
        # A Streamlit rerun can close a just-opened dropdown after a field blur.
        try:
            page.get_by_role('option', name=title, exact=True).wait_for(state='visible', timeout=3000)
        except PlaywrightTimeoutError:
            idle()
            selector.click()
        page.get_by_role('option', name=title, exact=True).click()
        expect(page.get_by_role('heading', name=title, exact=True).filter(visible=True)).to_be_visible(timeout=30000)
        idle()

    titles = ['Case 001 / Is Morocco becoming drier?', 'Case 002 / Across the border',
              'Case 003 / The dry-year files', 'Case 004 / Follow the strongest trail',
              'Case 005 / Has the rain returned?', 'Case 006 / What changed from space?']
    for title in titles:
        choose(title)
        expect(page.get_by_role('heading', name=title, exact=True).filter(visible=True)).to_be_visible()
        expect(page.get_by_role('button', name='Open quiz', exact=True)).to_be_visible()
    choose(titles[0])
    page.get_by_role('textbox', name='Your first hypothesis', exact=True).fill('Rainfall may be decreasing.')
    page.get_by_role('button', name='Open quiz', exact=True).click()
    expect(page.get_by_role('heading', name='Clue 1 / Read the fitted direction', exact=True)).to_be_visible()
    idle()
    expect(page.get_by_role('button', name='Reveal next clue →', exact=True)).to_be_disabled()
    # Deliberately choose a wrong answer and verify explanatory feedback still allows progress.
    page.get_by_text('Flat', exact=True).click()
    page.get_by_role('button', name='Check my answer', exact=True).click()
    expect(page.get_by_text('You chose “Flat”.', exact=False)).to_be_visible()
    idle()
    page.get_by_role('button', name='Pin this clue to Field notebook', exact=True).click()
    expect(page.get_by_text('Clue pinned. It is available in Field notebook and the connected evidence board.', exact=True)).to_be_visible()
    idle()
    page.get_by_role('button', name='Reveal next clue →', exact=True).click()
    expect(page.get_by_role('heading', name='Clue 2 / Weigh the uncertainty', exact=True)).to_be_visible()
    idle()
    page.get_by_text('No statistically significant direction detected', exact=True).click()
    page.get_by_role('button', name='Check my answer', exact=True).click()
    expect(page.get_by_role('button', name='Reveal next clue →', exact=True)).to_be_enabled()
    idle()
    page.get_by_role('button', name='Reveal next clue →', exact=True).click()
    page.get_by_text('No, attribution needs additional evidence', exact=True).click()
    page.get_by_role('button', name='Check my answer', exact=True).click()
    expect(page.get_by_role('button', name='Finish quiz →', exact=True)).to_be_enabled()
    idle()
    page.get_by_role('button', name='Finish quiz →', exact=True).click()
    expect(page.get_by_text('Case complete ·', exact=False)).to_be_visible()
    idle()
    with page.expect_download() as download:
        page.get_by_role('button', name='Download solved quiz · JSON', exact=True).click()
    report = json.loads(Path(download.value.path()).read_text())
    assert report['schema'] == 'saharawatch-case-quiz-v1'
    assert len(report['answers']) == 3 and not report['answers'][0]['correct']
    assert report['context']['source_sha256']
    choose(titles[1]); choose(titles[0])
    expect(page.get_by_text('Case complete ·', exact=False)).to_be_visible()
    page.get_by_role('button', name='Investigate this case on your own', exact=True).click()
    expect(page.get_by_role('textbox', name='Working hypothesis for this case', exact=True)).to_have_value('Rainfall may be decreasing.')
    idle()
    page.get_by_role('textbox', name='Evidence note', exact=True).fill('The slope and uncertainty need separate interpretation.')
    page.get_by_role('button', name='Pin current evidence to Field notebook', exact=True).click()
    expect(page.get_by_text('1 pinned evidence item(s) for this case.', exact=False)).to_be_visible()
    idle()
    page.get_by_role('textbox', name='Your conclusion', exact=True).fill('The trend direction alone does not establish a robust conclusion.')
    page.get_by_role('textbox', name='One limitation or alternative explanation', exact=True).fill('Coarse country-average rainfall hides local differences.')
    page.get_by_role('textbox', name='Your conclusion', exact=True).focus()
    expect(page.get_by_role('button', name='Save investigation', exact=True)).to_be_enabled()
    idle()
    page.get_by_role('button', name='Save investigation', exact=True).click()
    expect(page.get_by_role('button', name='Download investigation · JSON', exact=True)).to_be_visible()
    idle()
    with page.expect_download() as download:
        page.get_by_role('button', name='Download investigation · JSON', exact=True).click()
    mission = json.loads(Path(download.value.path()).read_text())
    assert mission['schema'] == 'saharawatch-independent-investigation-v1'
    assert len(mission['evidence']) == 1 and mission['limitation']
    choose(titles[2]); choose(titles[0])
    expect(page.get_by_role('textbox', name='Your conclusion', exact=True)).to_have_value(mission['conclusion'])
    gallery = page.locator('[data-testid="stExpander"]').filter(has=page.get_by_text('Browse all six cases', exact=True))
    gallery.get_by_role('button', name='Open '+titles[-1], exact=True).scroll_into_view_if_needed()
    gallery.screenshot(path='assets/case-library.png')
    page.set_viewport_size({'width':390, 'height':844})
    page.get_by_text('Browse all six cases', exact=True).click()
    choose(titles[2])
    expect(page.get_by_role('textbox', name='Working hypothesis for this case', exact=True)).to_be_visible()
    assert not page.evaluate('document.documentElement.scrollWidth > window.innerWidth')
    page.get_by_role('combobox', name='Choose a case', exact=True).scroll_into_view_if_needed()
    page.screenshot(path='assets/case-library-mobile.png', full_page=True)
    assert not page.locator('[data-testid="stException"]').count()
    assert not errors, errors
    print('Six-case library: quiz gates and feedback, case switching, notebook pins, JSON reports, saved drafts and mobile passed')
    browser.close()
