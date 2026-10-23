"""TS-FIX-05 | Group exchange invariants and the Tactics drag/click contract."""
from copy import deepcopy
from pathlib import Path

import pytest

from football_manager.dev_ui.session import DevelopmentSession
from football_manager.ui_shell.models import UIRosterAdmin, squad_read_model, apply_squad_command
from football_manager.ui_shell.transactions import apply_squad_command_atomically
from football_manager.persistence.session_codec import GRAPH_VERSION, capture_manager_graph, restore_manager_graph


ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def base():
    return DevelopmentSession()


@pytest.fixture
def session(base):
    return deepcopy(base)


def _groups(model):
    return ({p['id'] for p in model['starters']},
            {p['id'] for p in model['bench']},
            {p['id'] for p in model['outside']})


def _valid(model, before):
    starters, bench, reserves = _groups(model)
    original = set().union(*_groups(before))
    assert len(starters) == 11
    assert len(bench) == len(before['bench']) == 7
    assert len(starters | bench | reserves) == len(original)
    assert not starters & bench and not starters & reserves and not bench & reserves
    assert starters | bench | reserves == original
    assert model['formation'] == before['formation']
    assert [slot['slot_id'] for slot in model['slots']] == [slot['slot_id'] for slot in before['slots']]
    assert [slot['role_id'] for slot in model['slots']] == [slot['role_id'] for slot in before['slots']]


def test_bench_to_reserve_exchange_is_bidirectional_and_keeps_all_members(session):
    initial = squad_read_model(session)
    old_bench = initial['bench'][0]['id']
    old_reserve = initial['outside'][0]['id']
    modified = apply_squad_command(session, {
        'action': 'swap_reserve', 'player_id': old_bench, 'reserve_id': old_reserve,
    })
    _valid(modified, initial)
    assert old_reserve in _groups(modified)[1]
    assert old_bench in _groups(modified)[2]
    restored = apply_squad_command(session, {
        'action': 'swap_reserve', 'player_id': old_reserve, 'reserve_id': old_bench,
    })
    assert [p['id'] for p in restored['bench']] == [p['id'] for p in initial['bench']]
    _valid(restored, initial)


def test_reserve_replaces_starting_slot_without_changing_tactic_or_bench(session):
    original = squad_read_model(session)
    old = original['starters'][3]
    reserve = original['outside'][0]
    changed = apply_squad_command(session, {
        'action': 'swap_reserve', 'player_id': old['id'], 'reserve_id': reserve['id'],
    })
    _valid(changed, original)
    assert next(p for p in changed['starters'] if p['slot_id'] == old['slot_id'])['id'] == reserve['id']
    assert old['id'] in _groups(changed)[2]
    assert [p['id'] for p in changed['bench']] == [p['id'] for p in original['bench']]
    assert session.home_lineup.player_for_slot(old['slot_id']).id == reserve['id']


def test_all_three_roster_groups_can_exchange_repeatedly(session):
    original = squad_read_model(session)
    starter = original['starters'][0]
    bench = original['bench'][0]
    reserve = original['outside'][0]
    a = apply_squad_command(session, {'action': 'swap_starters',
                                       'first': original['starters'][0]['slot_id'],
                                       'second': original['starters'][1]['slot_id']})
    _valid(a, original)
    b = apply_squad_command(session, {'action': 'swap_bench',
                                       'starter_id': starter['id'], 'bench_id': bench['id']})
    _valid(b, original)
    c = apply_squad_command(session, {'action': 'swap_reserve',
                                       'player_id': starter['id'], 'reserve_id': reserve['id']})
    _valid(c, original)
    d = apply_squad_command(session, {'action': 'swap_reserve',
                                       'player_id': bench['id'], 'reserve_id': starter['id']})
    _valid(d, original)


def test_two_substitutes_can_switch_places(session):
    original = squad_read_model(session)
    first, second = original['bench'][:2]
    changed = apply_squad_command(session, {'action': 'swap_bench_slots',
                                             'first_id': first['id'], 'second_id': second['id']})
    _valid(changed, original)
    assert changed['bench'][0]['id'] == second['id']
    assert changed['bench'][1]['id'] == first['id']
    assert [p['id'] for p in changed['starters']] == [p['id'] for p in original['starters']]


@pytest.mark.parametrize('issue', ['unknown-reserve','active-reserve','unknown-outgoing','unknown-bench'])
def test_invalid_commands_do_not_modify_lineup(session, issue):
    original = squad_read_model(session)
    outgoing = original['starters'][0]['id']
    reserve = original['outside'][0]['id']
    cmd = {'action':'swap_reserve', 'player_id':outgoing, 'reserve_id':reserve}
    if issue == 'unknown-reserve':cmd['reserve_id'] = 'not-on-roster'
    elif issue == 'active-reserve':cmd['reserve_id'] = original['bench'][0]['id']
    elif issue == 'unknown-outgoing':cmd['player_id'] = original['outside'][1]['id']
    elif issue == 'unknown-bench':cmd = {'action':'swap_bench_slots','first_id':outgoing,'second_id':original['bench'][0]['id']}
    with pytest.raises(ValueError):
        apply_squad_command_atomically(session, cmd, UIRosterAdmin())
    assert [p['id'] for p in squad_read_model(session)['starters']] == [p['id'] for p in original['starters']]
    assert [p['id'] for p in squad_read_model(session)['bench']] == [p['id'] for p in original['bench']]


def test_injured_or_suspended_reserve_is_ineligible_and_rollback_safe(session):
    before = squad_read_model(session)
    reserve = next(p for p in session.home_club.squad.players if p.id == before['outside'][0]['id'])
    for injury, suspension in [('ankle strain',0), (None,1)]:
        reserve.state.injury = injury
        reserve.state.suspended_matches = suspension
        for outgoing in [before['starters'][0]['id'], before['bench'][0]['id']]:
            with pytest.raises(ValueError, match='injured or suspended'):
                apply_squad_command_atomically(session, {'action':'swap_reserve',
                    'player_id':outgoing, 'reserve_id':reserve.id}, UIRosterAdmin())
            assert [p.id for p in session.home_lineup.selected_players] == [
                p['id'] for p in before['starters'] + before['bench']]


def test_selection_survives_version_29_save_restore(session):
    initial = squad_read_model(session)
    replacement = initial['outside'][0]['id']
    slot = initial['starters'][2]['slot_id']
    apply_squad_command(session, {'action':'swap_reserve',
        'player_id':initial['starters'][2]['id'], 'reserve_id':replacement})
    graph = capture_manager_graph(session)
    assert graph['version'] == GRAPH_VERSION == 29
    restored = restore_manager_graph(graph)
    assert restored.home_lineup.player_for_slot(slot).id == replacement
    assert len(restored.home_lineup.selected_players) == 18
    assert len({p.id for p in restored.home_lineup.selected_players}) == 18


def test_frontend_has_all_three_draggable_zones_and_click_fallback():
    js = (ROOT / 'frontend/public/squad/squad.js').read_text(encoding='utf-8')
    html = (ROOT / 'frontend/public/squad/embed.html').read_text(encoding='utf-8')
    css = (ROOT / 'frontend/public/squad/ts_fix_05.css').read_text(encoding='utf-8')
    assert all(term in js for term in ('data-player-slot', 'data-bench', 'data-outside',
                                       'draggable="true"', 'swap_reserve', 'swap_bench_slots'))
    assert 'squadExchange(first,second)' in js
    assert 'selectedCandidate' in js and 'exchangePlayers(selectedCandidate' in js
    assert all(term in js for term in ("'dragstart'", "'dragover'", "'drop'", "'dragend'"))
    assert 'ts_fix_05.css' in html
    assert '.fm-drop-valid' in css and '.fm-outside-player' in css
