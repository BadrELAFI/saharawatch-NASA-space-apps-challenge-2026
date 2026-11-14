"""Exercise real dragging, red pins, relationships, persistence, exports and touch."""
import json
import os
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]


def open_notebook(page):
    page.goto(os.environ.get('SAHARAWATCH_TEST_URL', 'http://localhost:8501'))
    page.get_by_role('tab', name='04 / Field notebook', exact=True).click(timeout=60000)


def download_board(page):
    expect(page.locator('.board-status')).to_contain_text('Board saved', timeout=30000)
    with page.expect_download() as pending:
        page.get_by_role('button', name='Download evidence board · JSON', exact=True).click()
    return json.loads(Path(pending.value.path()).read_text())


def position(card):
    return card.evaluate('(node) => ({x:parseFloat(node.style.left), y:parseFloat(node.style.top)})')


def drag(page, card, dx, dy):
    grip = card.locator('.card-grip')
    grip.scroll_into_view_if_needed()
    box = grip.bounding_box()
    x, y = box['x']+45, box['y']+25
    page.mouse.move(x, y); page.mouse.down()
    page.mouse.move(x+dx, y+dy, steps=12); page.mouse.up()
    page.wait_for_timeout(1000)


with sync_playwright() as p:
    executable = Path.home()/'.cache/ms-playwright/chromium-1255/chrome-linux64/chrome'
    browser = p.chromium.launch(headless=True,
        executable_path=str(executable) if executable.exists() else None,
        args=['--no-sandbox', '--enable-unsafe-swiftshader'])
    page = browser.new_page(viewport={'width':1550, 'height':1200})
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    open_notebook(page)
    expect(page.get_by_text('Every case starts with a clue.', exact=True)).to_be_visible()
    page.get_by_role('button', name='＋ Pin this evidence to the notebook').click()
    expect(page.locator('.evidence-card')).to_have_count(1)
    note = '<img src=x onerror="window.boardInjection=true"> A second interpretation.'
    page.get_by_role('textbox', name='Field notes', exact=True).fill(note)
    page.get_by_role('button', name='＋ Pin this evidence to the notebook').click()
    expect(page.locator('.evidence-card')).to_have_count(2)
    first, second = page.locator('.evidence-card').nth(0), page.locator('.evidence-card').nth(1)
    original = download_board(page)
    original_snapshot = original['evidence']
    initial = position(first)
    drag(page, first, 95, 120)
    moved = position(first)
    assert moved['x'] > initial['x']+50 and moved['y'] > initial['y']+70
    page.get_by_role('button', name='Pin clue 01', exact=True).click()
    expect(page.get_by_role('button', name='Unpin clue 01', exact=True)).to_have_attribute('aria-pressed', 'true')
    drag(page, first, 70, 70)
    assert position(first) == moved, 'Pinned cards must stay locked'
    page.get_by_role('combobox', name='Evidence relationship').select_option('challenges')
    page.get_by_role('button', name='Connect clue 01', exact=True).click()
    page.get_by_role('button', name='Connect clue 02', exact=True).click()
    expect(page.locator('.string-line')).to_have_count(1)
    connected = download_board(page)
    assert connected['board']['connections'] == [dict(source=original['evidence'][0]['id'],
        target=original['evidence'][1]['id'], relation='challenges')], connected['board']
    assert connected['evidence'] == original_snapshot
    assert connected['board']['positions'][original['evidence'][0]['id']]['pinned']
    string_label = page.locator('.string-label').bounding_box()
    assert string_label['y']+string_label['height'] <= min(first.bounding_box()['y'], second.bounding_box()['y']), 'Connection label must stay above its cards'
    second.locator('summary').click()
    expect(second.locator('.card-detail-text')).to_contain_text(note)
    assert not page.evaluate('window.boardInjection || false')
    second.locator('summary').click()
    page.get_by_text('Country aggregation', exact=True).click()
    page.wait_for_timeout(1500)
    persisted = download_board(page)
    assert persisted['board'] == connected['board']
    assert persisted['evidence'] == original_snapshot
    with page.expect_download() as markdown:
        page.get_by_role('button', name='Download the case report · Markdown', exact=True).click()
    assert 'Clue 01 → Clue 02: Challenges' in Path(markdown.value.path()).read_text()
    page.locator('.board-scroll').screenshot(path=str(ROOT/'assets/evidence-board.png'))
    page.get_by_role('button', name='Unpin clue 01', exact=True).click()
    expect(page.get_by_role('button', name='Pin clue 01', exact=True)).to_have_attribute('aria-pressed', 'false')
    expect(page.locator('.board-status')).to_contain_text('Board saved')
    grip = first.locator('.card-grip'); grip.focus(); grip.press('ArrowRight')
    page.wait_for_timeout(1000)
    assert position(first)['x'] > moved['x'], 'Keyboard movement must work'
    page.get_by_role('button', name='Remove connection from clue 01 to clue 02', exact=True).click()
    expect(page.locator('.string-line')).to_have_count(0)
    expect(page.locator('.board-status')).to_contain_text('Board saved')
    page.get_by_role('button', name='Connect clue 01', exact=True).click()
    page.get_by_role('button', name='Connect clue 02', exact=True).click()
    expect(page.locator('.string-line')).to_have_count(1)
    expect(page.locator('.board-status')).to_contain_text('Board saved')
    expander = page.locator('[data-testid="stExpander"]').filter(has_text='Clue 01 ·')
    expander.locator('summary').click()
    expander.get_by_role('button', name='Remove this clue', exact=True).click()
    expect(page.locator('.evidence-card')).to_have_count(1)
    expect(page.locator('.string-line')).to_have_count(0)
    final = download_board(page)
    assert final['evidence'][0]['id'] == original['evidence'][1]['id']
    assert len(final['board']['positions']) == 1 and final['board']['connections'] == []
    expect(page.locator('[data-testid="stException"]')).to_have_count(0)
    print('Desktop: drag, pin lock, labeled strings, rerun persistence, safe notes, exports, keyboard and deletion passed')

    mobile = browser.new_page(viewport={'width':390, 'height':844}, is_mobile=True, has_touch=True)
    mobile.on('pageerror', lambda error: errors.append(str(error)))
    open_notebook(mobile)
    mobile.get_by_role('button', name='＋ Pin this evidence to the notebook').click()
    mobile_card = mobile.locator('.evidence-card').first
    expect(mobile_card).to_be_visible()
    grip = mobile_card.locator('.card-grip'); grip.scroll_into_view_if_needed()
    before = position(mobile_card); box = grip.bounding_box(); x, y = box['x']+50, box['y']+25
    client = mobile.context.new_cdp_session(mobile)
    client.send('Input.dispatchTouchEvent', {'type':'touchStart', 'touchPoints':[{'x':x, 'y':y}]})
    for step in range(1, 9):
        client.send('Input.dispatchTouchEvent', {'type':'touchMove', 'touchPoints':[{'x':x+step*4, 'y':y+step*8}]})
    client.send('Input.dispatchTouchEvent', {'type':'touchEnd', 'touchPoints':[]})
    mobile.wait_for_timeout(1200)
    after = position(mobile_card)
    assert after['x'] > before['x'] and after['y'] > before['y'], 'Touch dragging must move the card'
    mobile.get_by_role('button', name='Pin clue 01', exact=True).tap()
    expect(mobile.get_by_role('button', name='Unpin clue 01', exact=True)).to_have_attribute('aria-pressed', 'true')
    assert not mobile.evaluate('document.documentElement.scrollWidth > innerWidth')
    expect(mobile.locator('[data-testid="stException"]')).to_have_count(0)
    print('Mobile: touch dragging, red pin, contained board scrolling passed')
    assert not errors, errors
    print('No browser errors')
    browser.close()
