"""Exercise the desk landing, physical exhibits, optional audio and reduced-motion flow."""
import os
from pathlib import Path
from playwright.sync_api import sync_playwright,expect

def wait_for_desk(page):
    page.wait_for_function("""() => document.querySelector('[data-testid="stApp"]')?.getAttribute('data-test-script-state') === 'notRunning'
        && document.querySelectorAll('[role="tab"]').length === 8
        && document.querySelector('[role="tab"][aria-selected="true"]')?.textContent === "Detective's desk"
        """,timeout=60000)
    expect(page.locator('.office-intro')).to_be_visible()

with sync_playwright() as p:
    executable=Path.home()/'.cache/ms-playwright/chromium-1255/chrome-linux64/chrome'
    browser=p.chromium.launch(headless=True,executable_path=str(executable) if executable.exists() else None,
                             args=['--no-sandbox','--enable-unsafe-swiftshader'])
    page=browser.new_page(viewport={'width':1500,'height':1300},has_touch=True)
    errors=[]
    page.on('pageerror',lambda error:errors.append(str(error)))
    page.goto(os.environ.get('SAHARAWATCH_TEST_URL','http://localhost:8501'))
    expect(page.get_by_role('tab',name="Detective's desk",exact=True)).to_have_attribute('aria-selected','true',timeout=60000)
    expect(page.locator('.st-key-landing_files .file-folder')).to_have_count(6)
    expect(page.locator('.office-effects')).to_have_attribute('data-ready','true')
    wait_for_desk(page)
    assert page.evaluate('window.saharaOffice.context === null && window.saharaOffice.plays === 0')
    page.set_viewport_size({'width':1500,'height':2350})
    page.screenshot(path='assets/office-landing.png',full_page=True)
    page.set_viewport_size({'width':1500,'height':1300})
    page.get_by_role('button',name='Open Case 002 / Across the border',exact=True).click()
    expect(page.get_by_role('combobox',name='Choose a case',exact=True)).to_have_value('Case 002 / Across the border',timeout=30000)
    assert page.evaluate('window.saharaOffice.plays === 0')
    page.get_by_role('button',name='Explore rainfall',exact=True).click()
    expect(page.locator('.st-key-exhibit_atlas')).to_be_visible(timeout=30000)
    page.wait_for_function("document.querySelector('.js-plotly-plot')?._fullLayout?.map?._subplot?.map?.loaded()",timeout=60000)
    page.locator('.st-key-exhibit_atlas').screenshot(path='assets/office-field-map.png')
    page.get_by_role('button',name='Compare satellite images',exact=True).click()
    expect(page.locator('.st-key-exhibit_satellite_photos')).to_be_visible()
    for image in page.locator('.satellite-frame img').all():
        expect(image).to_have_js_property('naturalWidth',900)
        assert image.evaluate('(node)=>getComputedStyle(node).filter') == 'none'
    page.locator('.st-key-exhibit_satellite_photos').screenshot(path='assets/office-photographs.png')
    page.get_by_role('button',name="Detective's desk",exact=True).click()
    page.get_by_text('Desk sounds',exact=True).click()
    expect(page.locator('.office-effects')).to_have_attribute('data-sound','enabled')
    folder=page.get_by_role('button',name='Open Case 001 / Is Morocco becoming drier?',exact=True)
    folder.focus()
    folder.press('Enter')
    expect(page.get_by_role('combobox',name='Choose a case',exact=True)).to_have_value('Case 001 / Is Morocco becoming drier?')
    page.wait_for_function('window.saharaOffice.plays >= 1 && window.saharaOffice.lastKind === "paper"')
    assert page.evaluate('window.saharaOffice.context.state') == 'running'
    page.get_by_role('textbox',name='Your first hypothesis',exact=True).fill('I need to examine the evidence.')
    page.get_by_role('button',name='Open quiz',exact=True).click()
    for index,choice in enumerate(['Decrease','Decrease','Yes, it attributes the change']):
        form=page.locator('[data-testid="stForm"]').filter(visible=True)
        form.get_by_text(choice,exact=True).click()
        page.get_by_role('button',name='Check my answer',exact=True).click()
        next_button=page.get_by_role('button',name='Reveal next clue →' if index<2 else 'Finish quiz →',exact=True)
        expect(next_button).to_be_enabled()
        next_button.click()
    expect(page.locator('.filed-stamp')).to_have_text('ASSESSMENT FILED')
    page.wait_for_function('window.saharaOffice.lastKind === "stamp"')
    page.get_by_text('Desk sounds',exact=True).click()
    expect(page.locator('.office-effects')).to_have_attribute('data-sound','muted')
    played=page.evaluate('window.saharaOffice.plays')
    page.get_by_role('button',name="Detective's desk",exact=True).click()
    wait_for_desk(page)
    page.emulate_media(reduced_motion='reduce')
    page.set_viewport_size({'width':390,'height':844})
    page.get_by_role('button',name='Open Case 005 / Has the rain returned?',exact=True).tap()
    expect(page.get_by_role('combobox',name='Choose a case',exact=True)).to_have_value('Case 005 / Has the rain returned?',timeout=30000)
    assert page.evaluate('window.saharaOffice.plays') == played
    expect(page.locator('.st-key-case_desk .is-open .folder-cover')).to_have_css('animation-name','none')
    assert not page.evaluate('document.documentElement.scrollWidth > window.innerWidth')
    page.get_by_role('button',name="Detective's desk",exact=True).click()
    wait_for_desk(page)
    page.locator('[data-testid="stMain"]').evaluate('(node)=>node.scrollTop=0')
    page.screenshot(path='assets/office-landing-mobile.png',full_page=True)
    assert not page.locator('[data-testid="stException"]').count()
    assert not errors,errors
    print('Office: desk landing, file selection, paper and photo exhibits, default mute, opt-in audio, keyboard-safe navigation, reduced motion and mobile passed')
    browser.close()
