"""Verify that physical folder covers remain usable case-selection controls."""
import os
from pathlib import Path
from playwright.sync_api import sync_playwright,expect

with sync_playwright() as p:
    executable=Path.home()/'.cache/ms-playwright/chromium-1255/chrome-linux64/chrome'
    browser=p.chromium.launch(headless=True,executable_path=str(executable) if executable.exists() else None,
                             args=['--no-sandbox','--enable-unsafe-swiftshader'])
    page=browser.new_page(viewport={'width':1440,'height':1500},has_touch=True)
    errors=[]
    page.on('pageerror',lambda error:errors.append(str(error)))
    page.goto(os.environ.get('SAHARAWATCH_TEST_URL','http://localhost:8501'))
    page.get_by_role('button',name='Quizzes & investigations',exact=True).click(timeout=60000)
    desk=page.locator('.st-key-case_desk')
    expect(desk.locator('.file-folder')).to_have_count(6)
    page.get_by_role('button',name='Open Case 002 / Across the border',exact=True).click()
    expect(page.get_by_role('combobox',name='Choose a case',exact=True)).to_have_value('Case 002 / Across the border')
    expect(desk.locator('.folder-variant-1')).to_have_class('file-folder folder-variant-1 is-open')
    expect(desk.locator('.is-open')).to_have_count(1)
    cover=desk.locator('.is-open .folder-cover')
    cover.evaluate('(node)=>Promise.all(node.getAnimations().map(animation=>animation.finished))')
    desk.evaluate('(node)=>node.scrollIntoView({block:"center"})')
    desk.screenshot(path='assets/case-folders.png')
    button=page.get_by_role('button',name='Open Case 004 / Follow the strongest trail',exact=True)
    button.focus();button.press('Enter')
    expect(page.get_by_role('combobox',name='Choose a case',exact=True)).to_have_value('Case 004 / Follow the strongest trail')
    expect(desk.locator('.folder-variant-3')).to_have_class('file-folder folder-variant-3 is-open')
    page.emulate_media(reduced_motion='reduce')
    page.set_viewport_size({'width':390,'height':844})
    page.get_by_role('button',name='Open Case 005 / Has the rain returned?',exact=True).tap()
    expect(page.get_by_role('combobox',name='Choose a case',exact=True)).to_have_value('Case 005 / Has the rain returned?')
    expect(desk.locator('.folder-variant-4 .folder-cover')).to_have_css('animation-name','none')
    assert not page.evaluate('document.documentElement.scrollWidth > window.innerWidth')
    desk.locator('.folder-variant-4').scroll_into_view_if_needed()
    desk.locator('.folder-variant-4').screenshot(path='assets/case-folder-mobile.png')
    expect(page.get_by_role('button',name='Open quiz',exact=True)).to_be_visible()
    assert not page.locator('[data-testid="stException"]').count()
    assert not errors,errors
    print('Case folders: six files, full-cover click, opening state, keyboard, touch, reduced motion and mobile passed')
    browser.close()
