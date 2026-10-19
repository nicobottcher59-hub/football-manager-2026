from __future__ import annotations

from collections import Counter
from dataclasses import replace

import pytest

from examples.demo_match_factory import build_demo_snapshot
from football_manager.domain import (
    Formation,
    FormationSlot,
    Position,
    RoleExecutionSnapshot,
    TacticalSlotSnapshot,
    analyze_tactical_style,
    default_role_for_position,
)
from football_manager.simulation import (
    ActionType,
    MatchEventType,
    MatchFlowController,
    PlayerDecision,
    SpatialMatchEngine,
    TeamSide,
    Vector2,
)


@pytest.fixture(scope="module")
def integrated_match():
    flow = MatchFlowController(build_demo_snapshot(seed=5901))
    result = flow.run_to_completion()
    return flow, result


def _event_side(event) -> TeamSide | None:
    if event.side is not None:
        return event.side
    actor = event.actor_agent_id or ""
    if actor.startswith("home:"):
        return TeamSide.HOME
    if actor.startswith("away:"):
        return TeamSide.AWAY
    return None


def _xy(event) -> tuple[float, float] | None:
    x = event.value("x")
    y = event.value("y")
    if x is None or y is None:
        return None
    return float(x), float(y)


def test_integrated_match_has_human_scale_action_density(integrated_match) -> None:
    _, result = integrated_match
    attempts = [
        event
        for event in result.events
        if event.event_type is MatchEventType.PASS and event.value("status") == "attempt"
    ]
    assert 400 <= len(attempts) <= 1400

    by_minute: Counter[int] = Counter()
    for event in attempts:
        by_minute[int(event.tick * 0.25 // 60.0)] += 1
    assert max(by_minute.values()) <= 20


def test_both_teams_reach_opposition_half_and_final_third(integrated_match) -> None:
    _, result = integrated_match
    home_x: list[float] = []
    away_x: list[float] = []
    for event in result.events:
        coords = _xy(event)
        if coords is None:
            continue
        side = _event_side(event)
        if side is TeamSide.HOME:
            home_x.append(coords[0])
        elif side is TeamSide.AWAY:
            away_x.append(coords[0])

    assert home_x and away_x
    assert max(home_x) > 70.0
    assert min(away_x) < 35.0


def test_shots_and_crosses_are_spatially_auditable(integrated_match) -> None:
    flow, result = integrated_match
    pitch = flow.engine.state.pitch
    shots = [event for event in result.events if event.event_type is MatchEventType.SHOT]
    assert shots
    for event in shots:
        coords = _xy(event)
        assert coords is not None
        x, y = coords
        assert 0.0 <= y <= pitch.width_m
        if _event_side(event) is TeamSide.HOME:
            assert x >= pitch.length_m - 36.1
        else:
            assert x <= 36.1

    crosses = [
        event
        for event in result.events
        if event.event_type is MatchEventType.CROSS and event.value("status") == "attempt"
    ]
    for event in crosses:
        coords = _xy(event)
        assert coords is not None
        x, y = coords
        assert min(y, pitch.width_m - y) <= 17.1
        if _event_side(event) is TeamSide.HOME:
            assert x / pitch.length_m >= 0.579
        else:
            assert (pitch.length_m - x) / pitch.length_m >= 0.579


def test_default_added_time_is_capped_and_display_does_not_overrun(integrated_match) -> None:
    _, result = integrated_match
    added_events = [event for event in result.events if event.event_type is MatchEventType.ADDED_TIME]
    assert len(added_events) == 2
    announced = [int(event.value("seconds") or 0) // 60 for event in added_events]
    assert all(0 <= minutes <= 5 for minutes in announced)

    first_announced, second_announced = announced
    for event in result.events:
        label = event.time_label
        if label.startswith("45+"):
            shown = int(label.split("+")[1].rstrip("'"))
            assert shown <= first_announced
        if label.startswith("90+"):
            shown = int(label.split("+")[1].rstrip("'"))
            assert shown <= second_announced


def test_red_cards_are_not_systemic_in_reference_match(integrated_match) -> None:
    _, result = integrated_match
    red_cards = [
        event
        for event in result.events
        if event.event_type is MatchEventType.CARD
        and event.value("card") in {"red", "second_yellow_red"}
    ]
    assert len(red_cards) <= 1


def test_autonomous_cross_target_is_not_a_centre_back() -> None:
    engine = SpatialMatchEngine(build_demo_snapshot(seed=5991))
    winger = engine.state.player_for_slot(TeamSide.HOME, "rw")
    striker = engine.state.player_for_slot(TeamSide.HOME, "st")
    winger.location = Vector2(76.0, 7.0)
    striker.location = Vector2(88.0, 32.0)
    engine.give_ball_to(winger.agent_id)

    active = engine.start_cross(
        PlayerDecision(
            agent_id=winger.agent_id,
            action_type=ActionType.CROSS,
            target_agent_id=None,
            utility=80.0,
            considered_options=1,
        )
    )
    receiver = engine.state.agent(active.profile.receiver_agent_id)
    assert receiver.assigned_position not in {
        Position.GK,
        Position.RB,
        Position.RCB,
        Position.CB,
        Position.LCB,
        Position.LB,
    }


def test_runtime_substitution_replaces_player_without_mutating_snapshot() -> None:
    snapshot = build_demo_snapshot(seed=5992)
    original_starter_ids = tuple(player.player_id for player in snapshot.home_team.starters)
    flow = MatchFlowController(snapshot)
    flow.start()  # start first half without scheduling the opening action
    outgoing = flow.engine.state.player_for_slot(TeamSide.HOME, "st")
    incoming = next(player for player in flow.available_substitutes(TeamSide.HOME) if player.assigned_position is None and "ST" in player.player_id)

    new_agent_id = flow.make_substitution(TeamSide.HOME, outgoing.agent_id, incoming.player_id)

    assert len(flow.engine.state.active_players_for_side(TeamSide.HOME)) == 11
    assert outgoing.agent_id not in flow.engine.state.players
    assert new_agent_id in flow.engine.state.players
    assert flow.substitutions_remaining(TeamSide.HOME) == snapshot.context.competition.substitution_limit - 1
    assert flow.events[-1].event_type is MatchEventType.SUBSTITUTION
    assert tuple(player.player_id for player in snapshot.home_team.starters) == original_starter_ids


def _4231_tactic(snapshot):
    base = snapshot.home_team.tactic
    formation = Formation(
        formation_id="runtime-4231",
        name="4-2-3-1",
        slots=tuple(
            FormationSlot(slot.slot_id, Position.AM if slot.slot_id == "cm" else slot.position)
            for slot in snapshot.home_team.formation.slots
        ),
    )
    slots = []
    for formation_slot in formation.slots:
        old = base.slot(formation_slot.slot_id)
        if formation_slot.slot_id == "cm":
            role = default_role_for_position(Position.AM)
            slots.append(
                TacticalSlotSnapshot(
                    slot_id="cm",
                    position=Position.AM,
                    role_id=role.role_id,
                    role_name=role.name,
                    effective_instructions=role.default_instructions,
                )
            )
        else:
            slots.append(old)
    return replace(
        base,
        formation=formation,
        slots=tuple(slots),
        style=analyze_tactical_style(base.team_instructions),
    )


def test_runtime_formation_role_and_position_change_are_real_but_snapshot_stays_frozen() -> None:
    snapshot = build_demo_snapshot(seed=5993)
    flow = MatchFlowController(snapshot)
    flow.step()
    tactic = _4231_tactic(snapshot)

    flow.apply_runtime_tactic(TeamSide.HOME, tactic, label="4-2-3-1 test")

    cm = flow.engine.state.player_for_slot(TeamSide.HOME, "cm")
    assert flow.engine.runtime_tactic(TeamSide.HOME).formation.name == "4-2-3-1"
    assert cm.assigned_position is Position.AM
    assert cm.player.assigned_position is Position.AM
    assert cm.player.role_context is not None
    assert flow.events[-1].event_type is MatchEventType.TACTICAL_CHANGE
    assert snapshot.home_team.formation.name != "4-2-3-1"


def test_same_seed_and_same_manager_intervention_stay_deterministic() -> None:
    snapshot = build_demo_snapshot(seed=5994)
    first = MatchFlowController(snapshot)
    second = MatchFlowController(snapshot)
    first.start()
    second.start()

    first_out = first.engine.state.player_for_slot(TeamSide.HOME, "st")
    second_out = second.engine.state.player_for_slot(TeamSide.HOME, "st")
    first_in = next(player for player in first.available_substitutes(TeamSide.HOME) if "ST" in player.player_id)
    second_in = next(player for player in second.available_substitutes(TeamSide.HOME) if "ST" in player.player_id)
    first.make_substitution(TeamSide.HOME, first_out.agent_id, first_in.player_id)
    second.make_substitution(TeamSide.HOME, second_out.agent_id, second_in.player_id)

    for _ in range(120):
        first.step()
        second.step()

    assert first.engine.state.signature() == second.engine.state.signature()
    assert first.events == second.events

def test_requested_substitution_waits_for_restart_then_applies() -> None:
    snapshot = build_demo_snapshot(seed=5995)
    flow = MatchFlowController(snapshot)
    flow.start()
    outgoing = flow.engine.state.player_for_slot(TeamSide.HOME, "st")
    incoming = next(player for player in flow.available_substitutes(TeamSide.HOME) if "ST" in player.player_id)

    immediate = flow.request_substitution(TeamSide.HOME, outgoing.agent_id, incoming.player_id)
    assert immediate is False
    assert flow.pending_substitution_count(TeamSide.HOME) == 1
    assert outgoing.agent_id in flow.engine.state.players

    flow.award_restart(flow.events[-1].restart_type or "throw_in", TeamSide.HOME, location=Vector2(50.0, 0.0))

    assert flow.pending_substitution_count(TeamSide.HOME) == 0
    assert outgoing.agent_id not in flow.engine.state.players
    assert any(event.event_type is MatchEventType.SUBSTITUTION for event in flow.events)
