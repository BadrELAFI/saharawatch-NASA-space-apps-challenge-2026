"""The office landing scene and its quiet, optional interaction soundtrack."""
import html

import streamlit as st

from .data import ROOT
from .case_folders import render_folders

ASSETS=ROOT/'assets/office'
effects_component=st.components.v2.component('saharawatch.office_effects',
    html='<span class="office-effects" aria-hidden="true"></span>',
    css='.office-effects{display:none}',js=(ASSETS/'effects.js').read_text())


def render_effects(enabled):
    effects_component(data=dict(enabled=bool(enabled)),key='office_effects',height=1)


def render_desk(open_case,open_workspace):
    st.html('''<section class="office-intro"><div><p class="eyebrow">SaharaWatch / The Climate Detective Bureau</p>
    <h1>The curious case<br>of the <em>missing rain.</em></h1>
    <p class="office-subtitle">The office is quiet. The evidence is waiting.<br>Open a file and find out what the rainfall record really says.</p></div>
    <div class="banker-lamp" aria-hidden="true"><i class="lamp-glow"></i><i class="lamp-shade"></i><i class="lamp-neck"></i><i class="lamp-base"></i></div></section>''')
    with st.container(key='office_scene'):
        clues=st.session_state.get('clues',[])
        if clues:
            cards=[(clue['location'],clue['status']) for clue in clues[-3:]]
            label=f'{len(clues)} pinned observations / your evidence room'
        else:
            cards=[('OBSERVE','Inspect the record'),('QUESTION','Look for another explanation'),('CONNECT','Pin what you discover')]
            label='The evidence room / a place for your next discovery'
        notes=''.join(f'<div class="wall-note"><b>{html.escape(title)}</b><span>{html.escape(detail)}</span></div>' for title,detail in cards)
        st.html(f'<div class="office-wall"><span class="wall-label">{html.escape(label)}</span><div class="wall-notes">{notes}</div><span class="wall-thread" aria-hidden="true"></span></div>')
        st.caption('YOUR DESK · Choose a case file. Its evidence and questions open inside.')
        render_folders(st.session_state.get('last_open_folder'),
                       st.session_state.get('completed_quizzes',{}),st.session_state.get('saved_missions',{}),open_case,landing=True)
        st.html('<div class="instrument-label">FIELD INSTRUMENTS / TAKE A CLOSER LOOK</div>')
        with st.container(key='desk_instruments'):
            tools=st.columns(3)
            tools[0].button('⌖ Open the field map',key='desk_map',on_click=open_workspace,args=('01 / Evidence atlas',),width='stretch')
            tools[1].button('▧ Inspect satellite photographs',key='desk_photos',on_click=open_workspace,args=('Satellite images',),width='stretch')
            tools[2].button('⌁ Visit the evidence board',key='desk_board',on_click=open_workspace,args=('04 / Field notebook',),width='stretch')
