"""TS-07.1: canonical fixtures, temporary tactics and kickoff eligibility."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from types import SimpleNamespace

import pytest

from football_manager.dev_ui.session import DevelopmentSession
from football_manager.services.match_result_contract import record_managed_match
from football_manager.ui_shell.server import FootballUIHandler, UIRuntime
from tools.stress_world_calendar import create_world


def _score(fixture):
    return SimpleNamespace(
        home_club_id=fixture.home_club_id, away_club_id=fixture.away_club_id,
        home_goals=2, away_goals=1, penalties_home=0, penalties_away=0,
    )


def _request_handler(session):
    handler = object.__new__(FootballUIHandler)
    handler.runtime = UIRuntime(session)
    fixture_id = session._active_match.fixture.fixture_id
    return handler, fixture_id


def _tactic_command(handler, fid, command):
    return handler._match_command({"action": "match_tactic", "fixture_id": fid, "command": command})


def test_canonical_fixture_rejects_swapped_identity_before_world_mutation():
    world, _ = create_world(leagues=1, seed=6077)
    actual = next(iter(world.fixtures.values()))
    forged = replace(actual, home_club_id=actual.away_club_id, away_club_id=actual.home_club_id)
    prior = world.to_dict()
    with pytest.raises(ValueError, match="canonical|participants|identity"):
        record_managed_match(world, forged, _score(forged))
    assert world.to_dict() == prior
    assert world.fixtures[actual.fixture_id] is actual


def test_canonical_fixture_rejects_unknown_id_even_with_valid_participants():
    world, _ = create_world(leagues=1, seed=6077)
    actual = next(iter(world.fixtures.values()))
    unknown = replace(actual, fixture_id="unknown-world-match")
    prior = world.to_dict()
    with pytest.raises((ValueError, KeyError), match="unknown|canonical"):
        record_managed_match(world, unknown, _score(unknown))
    assert world.to_dict() == prior


def test_canonical_fixture_accepts_equivalent_fixture_value():
    world, _ = create_world(leagues=1, seed=6077)
    actual = next(iter(world.fixtures.values()))
    equivalent = replace(actual)
    outcome = record_managed_match(world, equivalent, _score(actual))
    assert outcome.fixture_id == actual.fixture_id
    assert outcome.home_goals == 2
    assert outcome.away_goals == 1


def test_match_only_team_instruction_is_used_then_permanent_tactic_restored(monkeypatch):
    session = DevelopmentSession()
    handler, fid = _request_handler(session)
    original_tactic = deepcopy(session.home_tactic)
    original_lineup = (
        session.home_lineup.formation,
        tuple((entry.slot_id, entry.player.id) for entry in session.home_lineup.starters),
        tuple(player.id for player in session.home_lineup.bench),
    )
    _tactic_command(handler, fid, {
        "action": "team_instruction", "group": "out_of_possession",
        "field": "defensive_line_width", "value": "very_low",
    })
    old_sim = DevelopmentSession.quick_simulate
    seen = []

    def observed_sim(self):
        seen.append(self.home_tactic.team_instructions.out_of_possession.defensive_line_width)
        return old_sim(self)

    monkeypatch.setattr(DevelopmentSession, "quick_simulate", observed_sim)
    summary = handler._match_command({"action": "quick_sim", "fixture_id": fid})
    assert summary["status"] == "finished"
    assert seen and seen[0].name == "VERY_LOW"
    assert handler.runtime.session.home_tactic == original_tactic
    actual_lineup = handler.runtime.session.home_lineup
    assert (actual_lineup.formation,
            tuple((entry.slot_id, entry.player.id) for entry in actual_lineup.starters),
            tuple(player.id for player in actual_lineup.bench)) == original_lineup
    assert handler.runtime.match_commands == []
    assert session.home_tactic == original_tactic  # the original session was never mutated


def test_match_only_role_and_player_instruction_do_not_leak(monkeypatch):
    session = DevelopmentSession()
    handler, fid = _request_handler(session)
    original = deepcopy(session.home_tactic)
    slot = next(s for s in session.home_lineup.formation.slots if len(session.role_options_for_slot(s.slot_id)) > 1)
    role = next(r.role_id for r in session.role_options_for_slot(slot.slot_id)
                if r.role_id != session.home_tactic.role_for_slot(slot.slot_id).role_id)
    _tactic_command(handler, fid, {"action": "role", "slot_id": slot.slot_id, "role_id": role})
    _tactic_command(handler, fid, {
        "action": "player_instruction", "slot_id": slot.slot_id,
        "field": "marking", "value": "position:ST",
    })
    seen = []
    original_sim = DevelopmentSession.quick_simulate

    def observed_sim(self):
        assignment = self.home_tactic.role_assignments[slot.slot_id]
        seen.append((assignment.role_id, assignment.overrides.marking.target_id))
        return original_sim(self)

    monkeypatch.setattr(DevelopmentSession, "quick_simulate", observed_sim)
    handler._match_command({"action": "quick_sim", "fixture_id": fid})
    assert seen == [(role, "ST")]
    assert handler.runtime.session.home_tactic == original


def test_match_only_formation_and_bench_swap_restore_permanent_selection():
    session = DevelopmentSession()
    handler, fid = _request_handler(session)
    old_formation = session.home_lineup.formation.formation_id
    old_tactic = deepcopy(session.home_tactic)
    old_players = tuple(p.id for p in session.home_lineup.selected_players)
    target_formation = next(f for f, _ in session.available_formations if f != old_formation)
    _tactic_command(handler, fid, {"action": "formation", "id": target_formation})
    view = handler._match_command({"action": "reset_match_tactics", "fixture_id": fid})
    assert view["managed"]["formation_id"] == old_formation
    view = _tactic_command(handler, fid, {"action": "formation", "id": target_formation})
    _tactic_command(handler, fid, {
        "action": "swap_bench", "starter_id": view["managed"]["starters"][0]["id"],
        "bench_id": view["managed"]["bench"][0]["id"],
    })
    handler._match_command({"action": "quick_sim", "fixture_id": fid})
    final = handler.runtime.session
    assert final.home_lineup.formation.formation_id == old_formation
    assert tuple(p.id for p in final.home_lineup.selected_players) == old_players
    assert final.home_tactic == old_tactic


@pytest.mark.parametrize("on_bench", [False, True])
def test_injury_after_lineup_creation_blocks_kickoff_without_state_change(on_bench):
    session = DevelopmentSession()
    player = session.home_lineup.bench[0] if on_bench else session.home_lineup.starters[0].player
    player.state.injury = "KNEE"
    before = session._world.to_dict()
    seed = session._seed
    with pytest.raises(ValueError, match="unavailable|injur"):
        session.quick_simulate()
    assert session._world.to_dict() == before
    assert session._seed == seed
    assert not session.match_played
    player.state.injury = None
    assert session.quick_simulate().home_goals >= 0


def test_cloned_player_with_same_id_is_rejected_at_kickoff():
    session = DevelopmentSession()
    entry = session.home_lineup.starters[0]
    impostor = deepcopy(entry.player)
    impostor.state.fitness = 10
    session.home_lineup = replace(
        session.home_lineup,
        starters=(replace(entry, player=impostor), *session.home_lineup.starters[1:]),
    )
    prior = session._world.to_dict()
    with pytest.raises(ValueError, match="canonical|squad|identity"):
        session.quick_simulate()
    assert session._world.to_dict() == prior
    assert not session.match_played


def test_distinct_clubs_may_use_side_scoped_player_ids():
    # The existing spatial engine explicitly supports IDs scoped by club/side.
    # TS-07.1 validates canonical identity *within* each club, without imposing
    # a global uniqueness rule that would break valid spatial snapshots.
    session = DevelopmentSession()
    player_copy = deepcopy(session.home_lineup.starters[0].player)
    session.away_club.squad.add(player_copy)
    entry = session.away_lineup.starters[0]
    session.away_lineup = replace(
        session.away_lineup,
        starters=(replace(entry, player=player_copy), *session.away_lineup.starters[1:]),
    )
    snapshot = session._build_snapshot()
    assert snapshot.home_team.club_id != snapshot.away_team.club_id
    assert {p.player_id for p in snapshot.home_team.starters} & {
        p.player_id for p in snapshot.away_team.starters
    }


def test_valid_default_lineup_still_plays_without_manual_changes():
    session = DevelopmentSession()
    fixture_id = session._active_match.fixture.fixture_id
    result = session.quick_simulate()
    saved = session._world.results[fixture_id]
    assert (saved.home_goals, saved.away_goals) == (result.home_goals, result.away_goals)
