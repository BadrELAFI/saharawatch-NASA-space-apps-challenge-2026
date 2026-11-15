"""The desk routes to real casework and keeps existing evidence and sound preferences."""
import copy

import pytest
from streamlit.testing.v1 import AppTest

from saharawatch.data import ROOT,RAW


@pytest.mark.skipif(not RAW.exists(),reason='Requires downloaded GPCP')
def test_desk_folder_routes_to_casework_and_preserves_another_attempt():
    at=AppTest.from_file(ROOT/'app.py').run(timeout=30)
    assert not at.exception
    assert at.toggle(key='desk_sounds').value is False
    assert len([button for button in at.button if button.key and button.key.startswith('desk_open_')])==6
    at.button(key='desk_open_compare').click().run(timeout=30)
    assert at.session_state['workspace_tab']=='03 / Case files'
    assert at.selectbox(key='library_case').value=='compare'
    at.text_input(key='quiz_compare_prediction').set_value('The countries may have different rainfall histories.')
    next(b for b in at.button if b.label=='Open quiz').click().run(timeout=30)
    original=copy.deepcopy(at.session_state['case_attempts']['compare'])
    at.button(key='go_desk').click().run(timeout=30)
    at.toggle(key='desk_sounds').set_value(True).run(timeout=30)
    at.button(key='desk_open_recent').click().run(timeout=30)
    assert not at.exception
    assert at.selectbox(key='library_case').value=='recent'
    assert at.toggle(key='desk_sounds').value is True
    assert at.session_state['case_attempts']['compare']==original
