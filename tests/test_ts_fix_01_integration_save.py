"""TS-FIX-01: calendar/quick routes, migration and SQLite continuation."""
from copy import deepcopy
from datetime import date, timedelta
from dataclasses import replace

import pytest
from football_manager.dev_ui.session import DevelopmentSession
from football_manager.persistence.session_codec import GRAPH_VERSION, capture_manager_graph, restore_manager_graph
from football_manager.persistence.manager_career import validate_manager_session, save_manager_career, load_manager_career
from football_manager.persistence import SQLiteSaveRepository
from football_manager.ui_shell.progression import simulate_until
from football_manager.services.player_development import advance_world_development


@pytest.fixture(scope='module')
def base():
    return DevelopmentSession()


def test_quick_and_calendar_both_delegate_the_managed_team(base):
    quick, calendar = deepcopy(base), deepcopy(base)
    result = quick.quick_simulate()
    captured = []
    original = calendar._simulator.simulate
    def record(*args, **kwargs):
        match = original(*args, **kwargs)
        captured.append(match)
        return match
    calendar._simulator.simulate = record
    progress = simulate_until(calendar, calendar.current_date)
    assert progress['managed_matches'] == 1
    managed = next(r for r in captured if base.home_club.id in (r.home_club_id, r.away_club_id))
    assert result == managed
    assert any(s.club_id == base.home_club.id for s in managed.substitutions)
    for club_id in (managed.home_club_id, managed.away_club_id):
        assert any(s.club_id == club_id for s in managed.substitutions)


def test_quick_explicit_nondelegation_preserves_managed_selection(base):
    s = deepcopy(base)
    result = s.quick_simulate(delegate_team=False)
    assert all(sub.club_id != s.home_club.id for sub in result.substitutions)
    assert result.substitutions


def test_legacy_v25_migration_preserves_players_results_and_sharpness(base):
    original = deepcopy(base)
    original.quick_simulate()
    graph = capture_manager_graph(original)
    graph['version'] = 25
    for node in graph['nodes']:
        if node.get('class') == 'football_manager.domain.youth_academy:YouthSystem':
            for field in ('match_clock', 'recent_participation', 'state_dates'):
                node['fields'].pop(field)
        elif node.get('class') == 'football_manager.domain.match_context:CompetitionContextSnapshot':
            for field in ('substitution_window_limit', 'extra_time_additional_windows'):
                node['fields'].pop(field)
    loaded = restore_manager_graph(graph)
    assert loaded._world.results == original._world.results
    assert loaded.last_result == original.last_result
    assert loaded._world_squads.youth.match_clock == loaded.current_date
    assert all(a.state.match_sharpness == b.state.match_sharpness
               for cid, academy in original._world_squads.youth.academies.items()
               for a, b in zip(academy.u17.values(), loaded._world_squads.youth.academies[cid].u17.values()))
    validate_manager_session(loaded)


def test_sqlite_roundtrip_preserves_rhythm_ledger_and_future_results(base, tmp_path):
    s = deepcopy(base)
    s.quick_simulate()
    s.continue_to_next_match()
    repo = SQLiteSaveRepository(tmp_path / 'fix01.sqlite3')
    save_manager_career(repo, slot_id='fix01', display_name='TS-FIX-01', session=s, expected_revision=0)
    loaded = load_manager_career(repo, 'fix01').session
    assert capture_manager_graph(loaded)['version'] == GRAPH_VERSION == 26
    assert loaded._world_squads.youth == s._world_squads.youth
    assert loaded.quick_simulate() == s.quick_simulate()
    validate_manager_session(loaded)
    target = loaded.current_date + timedelta(days=3)
    advance_world_development(loaded._world, target)
    advance_world_development(s._world, target)
    assert loaded._world_squads.youth == s._world_squads.youth
