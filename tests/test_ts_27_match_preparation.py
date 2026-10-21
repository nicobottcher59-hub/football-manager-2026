"""TS-27: match preparation, set-piece priorities and bounded AI coach behaviour."""
from copy import deepcopy

import pytest

from football_manager.dev_ui.session import DevelopmentSession
from football_manager.fast_simulation import FastMatchSimulator, build_fast_team_profile
from football_manager.fast_simulation.ai_coaching import adjusted_profile, coach_for_match
from football_manager.fast_simulation.engine import _TeamRuntime
from football_manager.persistence.manager_career import validate_manager_session
from football_manager.persistence.session_codec import GRAPH_VERSION, capture_manager_graph, restore_manager_graph
from football_manager.services.match_preparation import ROLES, opponent_report, set_piece_view
from football_manager.ui_shell.models import apply_squad_command, squad_read_model
from football_manager.ui_shell.match import prematch_read_model
from football_manager.ui_shell.models import UIRosterAdmin


@pytest.fixture(scope='module')
def world():
    return DevelopmentSession(world_seed=6606)


def test_current_opponent_report_is_grounded(world):
    result = opponent_report(world)
    assert result['available']
    assert result['opponent'] == world.away_club.name
    assert result['formation'] == world.away_tactic.formation.name
    assert all(p['name'] in {q.full_name for q in world.away_lineup.starting_players}
               for p in result['key_players'])
    assert not result['recent']
    view = squad_read_model(world)
    assert view['match_preparation'] == result
    prematch = prematch_read_model(world, UIRosterAdmin())
    assert prematch['tactical']['match_preparation']['opponent'] == result['opponent']


def test_set_piece_commands_validate_and_keep_order(world):
    session = deepcopy(world)
    starters = [p for p in session.home_lineup.starting_players if p.primary_position.value != 'GK']
    a, b = starters[:2]
    apply_squad_command(session, {'action': 'set_piece', 'role': 'penalties', 'player_id': a.id, 'rank': 0})
    apply_squad_command(session, {'action': 'set_piece', 'role': 'penalties', 'player_id': b.id, 'rank': 1})
    assert session.set_piece_orders['penalties'] == (a.id, b.id, '')
    apply_squad_command(session, {'action': 'set_piece', 'role': 'penalties', 'player_id': a.id, 'rank': 1})
    assert session.set_piece_orders['penalties'] == ('', a.id, '')
    for payload in (
        {'role': 'none', 'rank': 0, 'player_id': a.id},
        {'role': 'penalties', 'rank': 3, 'player_id': a.id},
        {'role': 'penalties', 'rank': True, 'player_id': a.id},
        {'role': 'penalties', 'rank': 0, 'player_id': 'unknown'},
        {'role': 'penalties', 'rank': 0, 'player_id': 25},
    ):
        before = deepcopy(session.set_piece_orders)
        with pytest.raises(ValueError):
            apply_squad_command(session, {'action': 'set_piece', **payload})
        assert before == session.set_piece_orders
    validate_manager_session(session)


def test_effective_set_piece_order_falls_back_to_starter(world):
    session = deepcopy(world)
    substitute = session.home_lineup.bench[0]
    apply_squad_command(session, {'action': 'set_piece', 'role': 'free_kicks', 'player_id': substitute.id})
    view = set_piece_view(session)
    row = next(r for r in view['roles'] if r['role'] == 'free_kicks')
    assert row['fallback']
    assert row['effective_id'] in {p.id for p in session.home_lineup.starting_players}
    assert substitute.id not in {r['effective_id'] for r in view['roles']}
    assert all(key in session.set_piece_orders for key in ROLES)


def test_snapshot_sides_and_shootout_priority(world):
    session = deepcopy(world)
    eligible = [e.player for e in session.home_lineup.starters if e.player.primary_position.value != 'GK']
    chosen = eligible[-1]
    apply_squad_command(session, {'action': 'set_piece', 'role': 'penalties', 'player_id': chosen.id})
    snapshot = session._build_snapshot()
    our_side = snapshot.home_team if snapshot.home_team.club_id == session.home_club.id else snapshot.away_team
    other_side = snapshot.away_team if our_side is snapshot.home_team else snapshot.home_team
    assert our_side.set_piece_preferences['penalties'][0] == chosen.id
    assert not other_side.set_piece_preferences
    runtime = _TeamRuntime(our_side, build_fast_team_profile(our_side))
    ordered = FastMatchSimulator()._penalty_takers(runtime, 90)
    assert ordered[0].player_id == chosen.id
    assert len({p.player_id for p in ordered}) == len(ordered)


def test_ai_coaches_are_stable_bounded_and_distinct(world):
    a = coach_for_match(6606, 'home', 'constant_press', 'fixture1')
    b = coach_for_match(6606, 'home', 'constant_press', 'fixture1')
    assert a == b
    assert a.approach in ('attacking', 'cautious', 'balanced', 'pragmatic')
    snap = world._build_snapshot()
    profile = build_fast_team_profile(snap.away_team)
    updated = adjusted_profile(profile, a, importance=.85, opponent_current=62)
    assert abs(updated.risk_when_leading - profile.risk_when_leading) <= 12
    assert abs(updated.time_wasting - profile.time_wasting) <= 15
    assert abs(updated.urgency_when_trailing - profile.urgency_when_trailing) <= 17
    assert updated.attack == profile.attack and updated.defense == profile.defense
    assert updated.tactical_features == profile.tactical_features
    assert (updated.risk_when_leading, updated.time_wasting, updated.urgency_when_trailing) != (profile.risk_when_leading, profile.time_wasting, profile.urgency_when_trailing)


def test_engine_seed_repeatability_and_no_live_state_mutation(world):
    session = deepcopy(world)
    snapshot = session._build_snapshot()
    coach = coach_for_match(session._world.seed, session.away_club.id,
                            session.away_tactic.preset_origin.value, session._active_match.fixture.fixture_id)
    coaches = {session.away_club.id: coach}
    engine = FastMatchSimulator()
    result_a = engine.simulate(snapshot, ai_coaches=coaches)
    result_b = engine.simulate(snapshot, ai_coaches=coaches)
    assert result_a == result_b
    assert result_a.home_goals >= 0 and result_a.away_goals >= 0
    assert snapshot.away_team.set_piece_preferences == {}
    assert session.home_lineup.starters[0].player.state.is_available


def test_simulation_and_persistence(world):
    session = deepcopy(world)
    player = session.home_lineup.starters[3].player
    apply_squad_command(session, {'action': 'set_piece', 'role': 'captain', 'player_id': player.id})
    result = session.quick_simulate()
    assert result.home_goals >= 0
    graph = capture_manager_graph(session)
    assert graph['version'] == GRAPH_VERSION == 24
    recovered = restore_manager_graph(graph)
    assert recovered.set_piece_orders['captain'][0] == player.id
    validate_manager_session(recovered)


def test_v19_graph_migration_restores_default_orders(world):
    original = capture_manager_graph(world)
    graph = deepcopy(original)
    graph['version'] = 19
    root_node = graph['nodes'][graph['root']['$ref']]
    root_node['items'] = [item for item in root_node['items'] if item[0] != 'set_piece_orders']
    recovered = restore_manager_graph(graph)
    assert all(values == ('','','') for values in recovered.set_piece_orders.values())
    validate_manager_session(recovered)


def test_goalkeeper_can_be_explicit_captain_and_penalty_taker(world):
    session = deepcopy(world)
    keeper = next(e.player for e in session.home_lineup.starters if e.player.primary_position.value == 'GK')
    apply_squad_command(session, {'action': 'set_piece', 'role': 'captain', 'player_id': keeper.id})
    apply_squad_command(session, {'action': 'set_piece', 'role': 'penalties', 'player_id': keeper.id})
    view = set_piece_view(session)
    by_role = {r['role']: r for r in view['roles']}
    assert by_role['captain']['effective_id'] == keeper.id
    assert by_role['penalties']['effective_id'] == keeper.id
    snapshot = session._build_snapshot()
    our_side = snapshot.home_team if snapshot.home_team.club_id == session.home_club.id else snapshot.away_team
    runtime = _TeamRuntime(our_side, build_fast_team_profile(our_side))
    assert FastMatchSimulator()._penalty_takers(runtime, 90)[0].player_id == keeper.id


def test_departed_set_piece_candidate_does_not_break_career_saves(world):
    session = deepcopy(world)
    # A squad departure may leave a valid, previously assigned ID behind.
    session.set_piece_orders['captain'] = ('former-member-id', '', '')
    validate_manager_session(session)
    row = next(r for r in set_piece_view(session)['roles'] if r['role'] == 'captain')
    assert row['fallback'] and row['effective_id'] != 'former-member-id'
    assert any(p['id'] == 'former-member-id' for p in set_piece_view(session)['players'])
    restored = restore_manager_graph(capture_manager_graph(session))
    assert restored.set_piece_orders['captain'][0] == 'former-member-id'


def test_failed_atomic_squad_response_rolls_back_set_piece_selection(world, monkeypatch):
    from football_manager.ui_shell.transactions import apply_squad_command_atomically
    import football_manager.ui_shell.models as model_module
    session = deepcopy(world)
    player_id = session.home_lineup.starters[3].player.id
    before = deepcopy(session.set_piece_orders)
    revision = session.tactical_studio.revision
    def fail_render(*args, **kwargs):
        raise ValueError('synthetic read model failure')
    monkeypatch.setattr(model_module, 'squad_read_model', fail_render)
    with pytest.raises(ValueError, match='synthetic'):
        apply_squad_command_atomically(session, {'action': 'set_piece', 'role': 'captain', 'player_id': player_id}, UIRosterAdmin())
    assert session.set_piece_orders == before
    assert session.tactical_studio.revision == revision


def test_existing_v19_sqlite_slot_migrates_set_piece_preferences(world, tmp_path):
    from dataclasses import replace
    from football_manager.persistence.manager_career import manager_career_document, load_manager_career
    from football_manager.persistence.sqlite_repository import SQLiteSaveRepository
    original = manager_career_document(world)
    state, ui = original.sections
    older_graph = deepcopy(state.payload)
    older_graph['version'] = 19
    older_root = older_graph['nodes'][older_graph['root']['$ref']]
    older_root['items'] = [item for item in older_root['items'] if item[0] != 'set_piece_orders']
    document_v19 = replace(original, sections=(replace(state, version=19, payload=older_graph), ui))
    repository = SQLiteSaveRepository(tmp_path / 'career.sqlite3')
    repository.save('old-slot', 'Legacy TS-26.1', document_v19, expected_revision=0)
    recovered = load_manager_career(repository, 'old-slot').session
    assert all(x == ('', '', '') for x in recovered.set_piece_orders.values())
    assert recovered.home_club.squad.players[0].id == world.home_club.squad.players[0].id
    validate_manager_session(recovered)


def test_http_squad_and_match_endpoints_expose_persisted_preparation(world):
    from threading import Thread
    from urllib.request import Request, urlopen
    from football_manager.ui_shell.server import create_server
    import json
    server = create_server(port=0, session=deepcopy(world))
    port = server.server_port
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with urlopen(f'http://127.0.0.1:{port}/api/squad', timeout=10) as response:
            squad = json.load(response)
        assert squad['match_preparation']['available']
        assert squad['set_pieces']['supported']
        player_id = squad['starters'][0]['id']
        request = Request(f'http://127.0.0.1:{port}/api/squad',
                          data=json.dumps({'action': 'set_piece', 'role': 'captain',
                                           'rank': 0, 'player_id': player_id}).encode('utf-8'),
                          headers={'Content-Type': 'application/json'})
        with urlopen(request, timeout=10) as response:
            updated = json.load(response)
        assert next(r for r in updated['set_pieces']['roles'] if r['role'] == 'captain')['orders'][0] == player_id
        with urlopen(f'http://127.0.0.1:{port}/api/match', timeout=10) as response:
            prematch = json.load(response)
        assert prematch['tactical']['set_pieces']['supported']
        assert prematch['tactical']['match_preparation']['available']
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()
