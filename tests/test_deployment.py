"""Check browser discovery without requiring a developer's installed browser path."""
from saharawatch.reports import configure_report_browser


def test_report_browser_respects_explicit_configuration(monkeypatch):
    monkeypatch.setenv('BROWSER_PATH','/custom/chrome')
    monkeypatch.setattr('saharawatch.reports.shutil.which',lambda name:None)
    assert configure_report_browser()=='/custom/chrome'


def test_report_browser_finds_system_chromium(monkeypatch):
    monkeypatch.setenv('BROWSER_PATH','')
    monkeypatch.setattr('saharawatch.reports.shutil.which',lambda name:'/usr/bin/chromium' if name=='chromium' else None)
    assert configure_report_browser()=='/usr/bin/chromium'


def test_report_browser_finds_any_playwright_revision(monkeypatch,tmp_path):
    monkeypatch.setenv('BROWSER_PATH','')
    monkeypatch.setenv('PLAYWRIGHT_BROWSERS_PATH',str(tmp_path))
    monkeypatch.setattr('saharawatch.reports.shutil.which',lambda name:None)
    browser=tmp_path/'chromium-9999/chrome-linux64/chrome'
    browser.parent.mkdir(parents=True)
    browser.write_text('#!/bin/sh\n')
    browser.chmod(0o755)
    assert configure_report_browser()==str(browser)
