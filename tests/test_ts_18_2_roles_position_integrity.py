"""TS-18.2: preserve canonical role, position and ACT contracts in live matches."""
from __future__ import annotations

from dataclasses import replace

import pytest

from football_manager.domain import (
    CurrentRatingContext,
    Position,
    get_role,
)
from football_manager.fast_simulation.engine import FastMatchSimulator, _TeamRuntime
from football_manager.fast_simulation.profiles import build_fast_team_profile
from football_manager.services import build_match_snapshot
from football_manager.simulation import MatchFlowController, SpatialMatchEngine, TeamSide
from test_match_snapshot import make_context, make_side


def _match(*, chemistry: float = 65.0, bench_role: float = 0.0, bench_chemistry: float = 65.0):
    home_club, home_lineup, home_tactic = make_side("home", "home")
    away_club, away_lineup, away_tactic = make_side("away", "away")
    starter = home_lineup.player_for_slot("st")
    starter.tactical_familiarity.set_role_score("advanced_forward", 100)
    starter.tactical_familiarity.set_role_score("target_forward", 0)
    starter.tactical_familiarity.set_tactic_score(home_tactic.tactic_id, 90)
    reserve = home_lineup.bench[0]
    reserve.positional_familiarity.set_score(Position.ST, 90)
    reserve.tactical_familiarity.set_role_score("advanced_forward", bench_role)
    reserve.tactical_familiarity.set_tactic_score(home_tactic.tactic_id, 90)
    return (
        build_match_snapshot(
            match_id="ts-18-2-role-fixture",
            seed=18202,
            context=make_context(),
            home_club=home_club,
            home_lineup=home_lineup,
            home_tactic=home_tactic,
            away_club=away_club,
            away_lineup=away_lineup,
            away_tactic=away_tactic,
            home_chemistry_by_player={starter.id: chemistry, reserve.id: bench_chemistry},
        ),
        starter,
        reserve,
    )


def _reassign_role(tactic, slot_id: str, role_id: str):
    role = get_role(role_id)
    return replace(
        tactic,
        slots=tuple(
            replace(
                slot,
                role_id=role.role_id,
                role_name=role.name,
                effective_instructions=role.default_instructions,
            ) if slot.slot_id == slot_id else slot
            for slot in tactic.slots
        ),
    )


def test_spatial_role_switch_applies_new_role_familiarity_and_preserves_chemistry():
    snapshot, starter, _ = _match(chemistry=95)
    engine = SpatialMatchEngine(snapshot)
    role_tactic = _reassign_role(snapshot.home_team.tactic, "st", "target_forward")
    expected = starter.current_rating(
        CurrentRatingContext(
            assigned_position=Position.ST,
            role_id="target_forward",
            tactic_id=role_tactic.tactic_id,
            chemistry=95,
        )
    )

    engine.set_runtime_tactic(TeamSide.HOME, role_tactic)
    actual = engine.state.player_for_slot(TeamSide.HOME, "st").player
    assert actual.overall_rating == expected.overall
    assert actual.current_rating == expected.current
    assert actual.role_context.role_familiarity == 0


def test_runtime_role_switch_back_restores_exact_rating_without_accumulation():
    snapshot, _, _ = _match(chemistry=88)
    engine = SpatialMatchEngine(snapshot)
    original = snapshot.home_team.player("home-st")
    alternate = _reassign_role(snapshot.home_team.tactic, "st", "target_forward")
    for _ in range(3):
        engine.set_runtime_tactic(TeamSide.HOME, alternate)
        engine.set_runtime_tactic(TeamSide.HOME, snapshot.home_team.tactic)
    assigned = engine.state.player_for_slot(TeamSide.HOME, "st").player
    assert assigned.overall_rating == original.overall_rating
    assert assigned.current_rating == original.current_rating


def test_spatial_substitute_is_rated_for_new_role_not_natural_position():
    snapshot, _, reserve = _match(bench_role=0, bench_chemistry=25)
    flow = MatchFlowController(snapshot)
    flow.start()
    outgoing = flow.engine.state.player_for_slot(TeamSide.HOME, "st")
    incoming = snapshot.home_team.bench[0]
    expected = reserve.current_rating(
        CurrentRatingContext(
            assigned_position=Position.ST,
            role_id="advanced_forward",
            tactic_id=snapshot.home_team.tactic.tactic_id,
            chemistry=25,
        )
    )
    new_agent_id = flow.make_substitution(TeamSide.HOME, outgoing.agent_id, incoming.player_id)
    actual = flow.engine.state.agent(new_agent_id).player
    assert actual.overall_rating == expected.overall
    assert actual.current_rating == expected.current


@pytest.mark.parametrize("role_familiarity", [0.0, 65.0, 100.0])
def test_fast_extra_time_bench_assignment_uses_exact_existing_act_formula(role_familiarity):
    snapshot, _, reserve = _match(bench_role=role_familiarity, bench_chemistry=95)
    team = snapshot.home_team
    runtime = _TeamRuntime(team=team, profile=build_fast_team_profile(team))
    incoming = team.bench[0]
    outgoing = team.player("home-st")
    expected = reserve.current_rating(
        CurrentRatingContext(
            assigned_position=Position.ST,
            role_id="advanced_forward",
            tactic_id=team.tactic.tactic_id,
            chemistry=95,
        )
    )
    assigned = FastMatchSimulator()._assign_bench_player(runtime, incoming, outgoing)
    assert assigned.overall_rating == expected.overall
    assert assigned.current_rating == expected.current
    assert assigned.role_context.position_familiarity == reserve.familiarity_for(Position.ST)
    assert assigned.role_context.role_suitability == pytest.approx(
        reserve.overall_breakdown_for(Position.ST, "advanced_forward").attribute_fit
    )


def test_invalid_runtime_role_change_preserves_all_previous_agent_assignments():
    snapshot, _, _ = _match()
    engine = SpatialMatchEngine(snapshot)
    invalid = _reassign_role(snapshot.home_team.tactic, "st", "target_forward")
    invalid = _reassign_role(invalid, "lw", "goalkeeper")
    before = tuple(
        (agent.agent_id, agent.assigned_position, agent.player)
        for agent in engine.state.players.values()
    )
    with pytest.raises(ValueError, match="not compatible"):
        engine.set_runtime_tactic(TeamSide.HOME, invalid)
    after = tuple(
        (agent.agent_id, agent.assigned_position, agent.player)
        for agent in engine.state.players.values()
    )
    assert after == before
    assert engine.runtime_tactic(TeamSide.HOME) is snapshot.home_team.tactic
