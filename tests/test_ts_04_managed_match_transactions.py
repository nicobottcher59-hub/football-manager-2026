"""TS-04: managed match commits world, views, and player state atomically."""
from copy import deepcopy

import pytest

from football_manager.dev_ui import DevelopmentSession


def _player_snapshot(session):
    return [
        (p.id, deepcopy(p.state), deepcopy(p.positional_familiarity),
         deepcopy(p.tactical_familiarity), p.primary_position)
        for club in (session.home_club, session.away_club)
        for p in club.squad.players
    ]


def _session_snapshot(s):
    return {
        "world": s._world.to_dict(),
        "players": _player_snapshot(s),
        "seed": s._seed,
        "match_played": s.match_played,
        "last_result": s.last_result,
        "managed_schedule": dict(s._managed_schedule),
        "season_calendar": s._season_calendar,
        "league_results": list(s._league_results),
        "efl_divisions": dict(s._efl_divisions),
        "efl_results": deepcopy(s._efl_results),
        "efl_current_round": dict(s._efl_current_round),
    }


def test_record_result_error_restores_players_world_views_and_seed(monkeypatch):
    s = DevelopmentSession()
    fixture_id = s._active_match.fixture.fixture_id
    old_state_reference = s.home_club.squad.players[0].state
    old_pos_reference = s.home_club.squad.players[0].positional_familiarity
    before = _session_snapshot(s)
    actual = s._world.record_result

    def fail_after_world_write(*args, **kwargs):
        actual(*args, **kwargs)
        raise RuntimeError("injected failure after world write")

    monkeypatch.setattr(s._world, "record_result", fail_after_world_write)
    with pytest.raises(RuntimeError, match="after world write"):
        s.quick_simulate()
    assert _session_snapshot(s) == before
    assert s.home_club.squad.players[0].state is old_state_reference
    assert s.home_club.squad.players[0].positional_familiarity is old_pos_reference
    assert fixture_id not in s._world.results
    monkeypatch.undo()
    result = s.quick_simulate()
    assert s._world.results[fixture_id].home_goals == result.home_goals
    assert s.match_played


def test_failed_world_view_refresh_rolls_back_after_result_was_recorded(monkeypatch):
    s = DevelopmentSession()
    before = _session_snapshot(s)
    actual = s._sync_world_view

    def fail_after_partial_refresh():
        actual()
        raise RuntimeError("injected view refresh failure")

    monkeypatch.setattr(s, "_sync_world_view", fail_after_partial_refresh)
    with pytest.raises(RuntimeError, match="view refresh"):
        s.quick_simulate()
    assert _session_snapshot(s) == before
    assert s._world._active_journal is None


def test_failure_during_player_mutation_restores_partially_updated_players(monkeypatch):
    s = DevelopmentSession()
    before = _session_snapshot(s)
    actual = s._persist_position_experience
    count = 0

    def fail_after_learning(*args, **kwargs):
        nonlocal count
        actual(*args, **kwargs)
        count += 1
        if count == 1:
            raise RuntimeError("injected player-learning failure")

    monkeypatch.setattr(s, "_persist_position_experience", fail_after_learning)
    with pytest.raises(RuntimeError, match="player-learning"):
        s.quick_simulate()
    assert _session_snapshot(s) == before


def test_successful_match_still_resolves_deterministically():
    one, two = DevelopmentSession(), DevelopmentSession()
    a = one.quick_simulate()
    b = two.quick_simulate()
    assert (a.home_goals, a.away_goals, a.penalties_home, a.penalties_away) == (
        b.home_goals, b.away_goals, b.penalties_home, b.penalties_away)
    assert one._world.to_dict() == two._world.to_dict()
    assert _player_snapshot(one) == _player_snapshot(two)
