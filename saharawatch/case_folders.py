"""Decorative case-file covers; native Streamlit buttons provide the interaction."""
import html
import streamlit as st

from .case_catalog import CASES


def render_folders(selected, solved, saved, on_select, landing=False):
    root = 'landing_files' if landing else 'case_desk'
    with st.container(key=root):
        st.html('<div class="desk-heading"><span>THE DETECTIVE’S DESK / OPEN CASES</span><em>Pick a folder. Follow the evidence.</em></div>')
        columns = st.columns(2,gap='large')
        for index,key in enumerate(CASES):
            with columns[index % 2].container(key=('file_case_landing_' if landing else 'file_case_')+key):
                st.html(folder_markup(key,key == selected,key in solved,key in saved))
                case=CASES[key]
                st.button(f'Open Case {case["number"]} / {case["title"]}',
                          key=('desk_open_' if landing else 'preset_')+key,
                          on_click=on_select,args=(key,),width='stretch')


def folder_markup(key, selected, quiz_complete, investigation_saved):
    case = CASES[key]
    index = list(CASES).index(key)
    status = 'FILE OPEN' if selected else 'CLICK TO OPEN'
    progress = ('QUIZ SOLVED' if quiz_complete else 'QUIZ UNFINISHED')+' / '+('NOTES FILED' if investigation_saved else 'AWAITING NOTES')
    return f'''<div class="file-folder folder-variant-{index}{' is-open' if selected else ''}" aria-hidden="true">
      <div class="folder-back"><span class="folder-tab">CASE / {case['number']}</span></div>
      <div class="folder-sheet sheet-under"></div>
      <div class="folder-sheet sheet-main">
        <span class="sheet-heading">CLIMATE DETECTIVE BUREAU / FIELD NOTES</span>
        <span class="sheet-title">{html.escape(case['title'])}</span>
        <span class="sheet-question">{html.escape(case['question'])}</span>
        <span class="sheet-progress">{progress}</span>
        <span class="sheet-instruction">Your evidence &amp; investigation continue below ↓</span>
      </div>
      <div class="folder-cover">
        <span class="folder-fold"></span><span class="coffee-ring"></span><span class="coffee-drop"></span>
        <span class="folder-bureau">SAHARAWATCH / INVESTIGATION DIVISION</span>
        <span class="folder-number">FILE No. {case['number']}</span>
        <span class="folder-title">{html.escape(case['title'])}</span>
        <span class="folder-pencil">{html.escape(case['difficulty'])} · approx. {case['minutes']} min</span>
        <span class="folder-stamp">EVIDENCE<br>ENCLOSED</span>
        <span class="folder-action">{status} <span>↗</span></span>
      </div>
      <span class="folder-clip"></span>
      <span class="folder-open-label">{case['number']} / {html.escape(case['title'])}</span>
    </div>'''
