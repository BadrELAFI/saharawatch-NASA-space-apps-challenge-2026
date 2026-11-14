import copy
import json

from saharawatch.evidence_board import clue_id, normalize_board


def test_board_preserves_identity_when_other_clues_are_added_or_removed():
    first = {'location': 'Morocco', 'period': '2001–2024', 'notes': 'A dry year is not a trend.'}
    second = dict(first, period='1991–2020')
    first_id, second_id = clue_id(first), clue_id(second)
    assert first_id == clue_id(dict(reversed(list(first.items()))))
    assert first_id != second_id
    board = {'positions': {first_id: {'x': 140, 'y': 260, 'pinned': True},
                           second_id: {'x': 600, 'y': 150, 'pinned': False}},
             'connections': [{'source': first_id, 'target': second_id, 'relation': 'challenges'}]}
    original = copy.deepcopy(board)
    clean = normalize_board(board, [first_id, second_id])
    assert clean == board and board == original
    removed = normalize_board(clean, [second_id])
    assert removed['positions'] == {second_id: board['positions'][second_id]}
    assert removed['connections'] == []
    expanded = normalize_board(clean, [first_id, second_id, 'new'])
    assert expanded['positions'][first_id] == board['positions'][first_id]
    assert expanded['connections'] == board['connections']


def test_invalid_browser_state_cannot_create_dangling_or_invalid_connections():
    state = {'positions': {'a': {'x': float('nan'), 'y': float('inf'), 'pinned': 'yes'},
                           'b': {'x': -100, 'y': 90000, 'pinned': True},
                           'removed': {'x': 1, 'y': 2}},
             'connections': [None, {'source': [], 'target': 'b', 'relation': 'supports'},
                 {'source': 'a', 'target': 'a', 'relation': 'supports'},
                 {'source': 'a', 'target': 'removed', 'relation': 'supports'},
                 {'source': 'a', 'target': 'b', 'relation': 'causes'},
                 {'source': 'a', 'target': 'b', 'relation': 'supports'},
                 {'source': 'a', 'target': 'b', 'relation': 'supports'}]}
    clean = normalize_board(state, ['a', 'b'])
    assert set(clean['positions']) == {'a', 'b'}
    assert clean['positions']['a'] == {'x': 55, 'y': 65, 'pinned': False}
    assert clean['positions']['b'] == {'x': 20, 'y': 12000, 'pinned': True}
    assert clean['connections'] == [{'source': 'a', 'target': 'b', 'relation': 'supports'}]
    json.dumps(clean, allow_nan=False)
    assert normalize_board({'positions': [], 'connections': {}}, ['a']) == normalize_board(None, ['a'])
