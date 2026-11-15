"""Verify actual playback, pause, year scrubbing, scales, and mobile layout."""
import os
from pathlib import Path

import numpy as np
from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT = """() => {
    const g = document.querySelector('.js-plotly-plot');
    return {
        year: Number(g.layout.title.text.match(/\\d{4}/)[0]),
        cursor: g.data[g.data.length - 2].x[0],
        marker: g.data[g.data.length - 1].x[0],
        scrubber: Number(g.layout.sliders[0].steps[g.layout.sliders[0].active].label),
        z: Array.from(g._fullData[0].z),
        low: g._fullData[0].zmin, high: g._fullData[0].zmax,
        x: g.layout.xaxis.range, y: g.layout.yaxis.range,
        count: g._transitionData._frames.length,
    };
}"""


def open_playback(page):
    page.goto(os.environ.get('SAHARAWATCH_TEST_URL', 'http://localhost:8501'))
    page.get_by_role('button',name='Explore rainfall',exact=True).click(timeout=60000)
    page.get_by_text('Open the rainfall time machine', exact=True).click(timeout=60000)
    element = page.locator('iframe[title="Animated rainfall map and synchronized location timeline"]')
    element.wait_for(timeout=60000)
    element.scroll_into_view_if_needed()
    frame = element.element_handle().content_frame()
    frame.wait_for_function(
        "document.querySelector('.js-plotly-plot')?._fullLayout?.map?._subplot?.map?.loaded()",
        timeout=60000)
    return element, frame


with sync_playwright() as p:
    executable = Path.home()/'.cache/ms-playwright/chromium-1255/chrome-linux64/chrome'
    browser = p.chromium.launch(headless=True,
        executable_path=str(executable) if executable.exists() else None,
        args=['--no-sandbox', '--enable-unsafe-swiftshader'])
    page = browser.new_page(viewport={'width':1550, 'height':1200})
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.on('console', lambda message: errors.append(message.text)
            if message.type == 'error' and 'Rainfall playback failed:' in message.text else None)
    element, frame = open_playback(page)
    first = frame.evaluate(SNAPSHOT)
    page.wait_for_timeout(1200)
    assert frame.evaluate(SNAPSHOT)['year'] == first['year'], 'Playback must start paused'
    frame.get_by_text('▶ Play', exact=True).click()
    frame.wait_for_function(
        "year => Number(document.querySelector('.js-plotly-plot').layout.title.text.match(/\\d{4}/)[0]) > year",
        arg=first['year'], timeout=15000)
    frame.get_by_text('Ⅱ Pause', exact=True).click()
    page.wait_for_timeout(1000)  # Let an in-flight redraw complete.
    paused = frame.evaluate(SNAPSHOT)
    page.wait_for_timeout(1600)
    assert frame.evaluate(SNAPSHOT)['year'] == paused['year']
    assert paused['year'] == paused['cursor'] == paused['marker'] == paused['scrubber']
    assert paused['z'] != first['z'], 'Map observations must change with the year'
    for key in ['low', 'high', 'x', 'y']:
        assert paused[key] == first[key], f'{key} changed during playback'
    # Use the visible scrubber, rather than invoking Plotly.animate directly.
    rail = frame.locator('.slider-rail-touch-rect').bounding_box()
    frame.locator('.slider-rail-touch-rect').click(position={'x':rail['width']*.7, 'y':rail['height']/2})
    page.wait_for_timeout(800)
    scrubbed = frame.evaluate(SNAPSHOT)
    assert scrubbed['year'] > paused['year']
    assert scrubbed['year'] == scrubbed['cursor'] == scrubbed['marker'] == scrubbed['scrubber']
    frame.get_by_text('↺ Start', exact=True).click()
    page.wait_for_timeout(800)
    restarted = frame.evaluate(SNAPSHOT)
    assert restarted['year'] == restarted['scrubber'] == first['year']
    np.testing.assert_allclose(restarted['z'], first['z'], equal_nan=True)
    element.screenshot(path=str(ROOT/'assets/rainfall-history.png'))
    page.get_by_text('Current analysis period', exact=True).click()
    frame = page.locator('iframe[title="Animated rainfall map and synchronized location timeline"]').element_handle().content_frame()
    frame.wait_for_function("document.querySelector('.js-plotly-plot')?._transitionData?._frames?.length === 24",
                            timeout=30000)
    assert frame.evaluate(SNAPSHOT)['year'] == 2001
    expect(page.locator('[data-testid="stException"]')).to_have_count(0)
    print('Desktop: real map updates, linked timeline, pause, scrub, restart, fixed scales, period change passed')

    mobile = browser.new_page(viewport={'width':390, 'height':844}, is_mobile=True, has_touch=True)
    mobile.on('pageerror', lambda error: errors.append(str(error)))
    _, mobile_frame = open_playback(mobile)
    assert not mobile.evaluate('document.documentElement.scrollWidth > innerWidth')
    assert not mobile_frame.evaluate('document.documentElement.scrollWidth > innerWidth')
    mobile_frame.get_by_text('▶ Play', exact=True).click()
    mobile.wait_for_timeout(1800)
    mobile_frame.get_by_text('Ⅱ Pause', exact=True).click()
    mobile.wait_for_timeout(1000)
    expect(mobile.locator('[data-testid="stException"]')).to_have_count(0)
    print('Mobile: 390px viewport and controls passed')
    assert not errors, errors
    print('No browser errors')
    browser.close()
