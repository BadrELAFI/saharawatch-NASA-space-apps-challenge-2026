"""A connected evidence board; presentation state never alters pinned observations."""
import hashlib
import json
import math

import streamlit as st

from .data import ROOT

RELATIONS = {'supports': 'Supports', 'challenges': 'Challenges', 'context': 'Provides context'}
ASSETS = ROOT / 'assets/evidence-board'


def clue_id(clue):
    return hashlib.sha256(json.dumps(clue, sort_keys=True, allow_nan=False).encode()).hexdigest()[:20]


def normalize_board(value, ids):
    """Keep valid positions and relationships for current, immutable clue IDs."""
    value = value if isinstance(value, dict) else {}
    positions = value.get('positions', {})
    positions = positions if isinstance(positions, dict) else {}
    clean = {'positions': {}, 'connections': []}
    for index, identity in enumerate(ids):
        original = positions.get(identity, {})
        original = original if isinstance(original, dict) else {}
        position = {'x': 55+(index % 3)*365, 'y': 65+(index // 3)*390, 'pinned': False}
        for axis, maximum in [('x', 900), ('y', 12000)]:
            coordinate = original.get(axis)
            if isinstance(coordinate, (float, int)) and not isinstance(coordinate, bool) and math.isfinite(coordinate):
                position[axis] = round(max(20, min(maximum, coordinate)), 1)
        position['pinned'] = original.get('pinned') is True
        clean['positions'][identity] = position
    edges = value.get('connections', [])
    pairs = set()
    for edge in edges if isinstance(edges, list) else []:
        if not isinstance(edge, dict):
            continue
        source, target, relation = (edge.get(key) for key in ['source', 'target', 'relation'])
        if not all(isinstance(item, str) for item in [source, target, relation]):
            continue
        if source not in clean['positions'] or target not in clean['positions'] or source == target:
            continue
        if relation not in RELATIONS or (source, target) in pairs:
            continue
        pairs.add((source, target))
        clean['connections'].append(dict(source=source, target=target, relation=relation))
    return clean


def _save_board():
    result = st.session_state.get('evidence_board_component', {})
    value = result.get('board') if isinstance(result, dict) else getattr(result, 'board', None)
    ids = [clue_id(clue) for clue in st.session_state.get('clues', [])]
    st.session_state['evidence_board'] = normalize_board(value, ids)


board_component = st.components.v2.component(
    'saharawatch.evidence_board',
    html='<div class="evidence-board-root"></div>',
    css=(ASSETS / 'board.css').read_text(),
    js=(ASSETS / 'board.js').read_text(),
)


def render_evidence_board(clues):
    cards = [dict(id=clue_id(clue), number=index+1, **{key: clue.get(key, '') for key in [
        'location', 'period', 'baseline', 'hypothesis', 'assessment', 'status', 'trend_mm_decade',
        'p_value', 'confidence_interval', 'inference_method', 'notes', 'source', 'source_sha256',
        'country_weighting', 'annual_data']}) for index, clue in enumerate(clues)]
    state = normalize_board(st.session_state.get('evidence_board'), [card['id'] for card in cards])
    st.session_state['evidence_board'] = state
    st.caption('Drag a card by its heading. Press its red pushpin to lock or unlock it. '
               'Choose a relationship, then press Connect on two cards. '
               'Keyboard: focus a heading and use arrow keys to move it; Space toggles its pin.')
    board_component(data=dict(cards=cards, board=state, relations=RELATIONS),
                    default={'board': state}, key='evidence_board_component',
                    on_board_change=_save_board, height='content')
    st.caption('Connections record your interpretation, not a statistical test or causal finding. '
               'Board positions and connections stay in this session; download a copy before closing it.')
    archive = dict(schema='saharawatch-evidence-board-v1', board=state,
                   evidence=[dict(id=clue_id(clue), snapshot=clue) for clue in clues])
    st.download_button('Download evidence board · JSON', json.dumps(archive, indent=2, allow_nan=False),
                       file_name='saharawatch_evidence_board.json', mime='application/json',
                       disabled=not clues, key='download_evidence_board', on_click='ignore')
    return state
