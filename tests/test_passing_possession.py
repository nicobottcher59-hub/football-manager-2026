from __future__ import annotations

from dataclasses import replace

import pytest

from football_manager.domain import Level
from football_manager.simulation import (
    ActionType,
    PassOutcome,
    PlayerDecision,
    SpatialMatchEngine,
    TeamSide,
    Vector2,
)

from test_spatial_core import make_snapshot


def _freeze_all(engine: SpatialMatchEngine) -> None:
    for agent in engine.state.players.values():
        engine.set_player_velocity(agent.agent_id, Vector2.zero())


def _open_short_pass_engine(seed: int = 300) -> tuple[SpatialMatchEngine, object, object]:
    engine = SpatialMatchEngine(make_snapshot(seed=seed))
    _freeze_all(engine)
    passer = engine.state.player_for_slot(TeamSide.HOME, "cm")
    receiver = engine.state.player_for_slot(TeamSide.HOME, "rcm")
    passer.location = Vector2(40.0, 34.0)
    receiver.location = Vector2(52.0, 34.0)
    for opponent in engine.state.away_players:
        opponent.location = Vector2(92.0, 62.0)
    engine.give_ball_to(passer.agent_id)
    _freeze_all(engine)
    return engine, passer, receiver


def _decision(passer, receiver, action_type: ActionType = ActionType.SHORT_PASS) -> PlayerDecision:
    return PlayerDecision(
        agent_id=passer.agent_id,
        action_type=action_type,
        target_agent_id=receiver.agent_id,
        utility=80.0,
        considered_options=5,
    )


def _replace_home_in_possession(snapshot, **changes):
    instructions = snapshot.home_team.tactic.team_instructions
    in_possession = replace(instructions.in_possession, **changes)
    team_instructions = replace(instructions, in_possession=in_possession)
    tactic = replace(snapshot.home_team.tactic, team_instructions=team_instructions)
    return replace(snapshot, home_team=replace(snapshot.home_team, tactic=tactic))


def _low_first_touch_snapshot(seed: int):
    snapshot = make_snapshot(seed=seed)
    starters = []
    for player in snapshot.home_team.starters:
        if player.assigned_slot_id == "rcm":
            technical = replace(player.attributes.technical, first_touch=1, technique=1)
            mental = replace(player.attributes.mental, composure=1, anticipation=1)
            physical = replace(player.attributes.physical, balance=1)
            attributes = replace(
                player.attributes,
                technical=technical,
                mental=mental,
                physical=physical,
            )
            player = replace(player, attributes=attributes)
        starters.append(player)
    return replace(
        snapshot,
        home_team=replace(snapshot.home_team, starters=tuple(starters)),
    )


def test_starting_pass_detaches_ball_from_passer_but_keeps_team_possession() -> None:
    engine, passer, receiver = _open_short_pass_engine()

    active = engine.start_pass(_decision(passer, receiver))

    assert engine.state.ball.owner_agent_id is None
    assert engine.state.possession.owner_agent_id is None
    assert engine.state.possession.team_side is TeamSide.HOME
    assert engine.state.ball.last_touch_agent_id == passer.agent_id
    assert not any(agent.has_ball for agent in engine.state.players.values())
    assert active.profile.passer_agent_id == passer.agent_id
    assert active.profile.receiver_agent_id == receiver.agent_id


def test_pass_ball_moves_through_space_instead_of_teleporting() -> None:
    engine, passer, receiver = _open_short_pass_engine()
    active = engine.start_pass(_decision(passer, receiver))
    target = active.profile.actual_target

    engine.step()

    assert engine.active_pass is not None
    assert engine.state.ball.location != passer.location
    assert engine.state.ball.location != target
    assert passer.location.distance_to(engine.state.ball.location) < passer.location.distance_to(target)


def test_open_short_pass_completes_and_transfers_control() -> None:
    engine, passer, receiver = _open_short_pass_engine(seed=1)
    engine.start_pass(_decision(passer, receiver))

    result = engine.resolve_active_pass()

    assert result.outcome is PassOutcome.COMPLETED
    assert result.controller_agent_id == receiver.agent_id
    assert engine.state.ball.owner_agent_id == receiver.agent_id
    assert engine.state.possession.owner_agent_id == receiver.agent_id
    assert engine.state.possession.team_side is TeamSide.HOME
    assert receiver.has_ball
    assert not passer.has_ball
    assert engine.state.ball.last_touch_agent_id == receiver.agent_id


def test_same_seed_and_same_pass_produce_same_profile_and_outcome() -> None:
    first, first_passer, first_receiver = _open_short_pass_engine(seed=310)
    second, second_passer, second_receiver = _open_short_pass_engine(seed=310)

    first_active = first.start_pass(_decision(first_passer, first_receiver))
    second_active = second.start_pass(_decision(second_passer, second_receiver))
    first_result = first.resolve_active_pass()
    second_result = second.resolve_active_pass()

    assert first_active.profile == second_active.profile
    assert first_result == second_result
    assert first.state.signature() == second.state.signature()


def test_heavy_passer_pressure_reduces_execution_quality_and_increases_error() -> None:
    open_engine, open_passer, open_receiver = _open_short_pass_engine(seed=311)
    pressured_engine, pressured_passer, pressured_receiver = _open_short_pass_engine(seed=311)
    marker = pressured_engine.state.player_for_slot(TeamSide.AWAY, "cm")
    marker.location = pressured_passer.location + Vector2(0.0, 2.0)

    open_profile = open_engine.start_pass(_decision(open_passer, open_receiver)).profile
    pressured_profile = pressured_engine.start_pass(
        _decision(pressured_passer, pressured_receiver)
    ).profile

    assert pressured_profile.passer_pressure > 0.5
    assert pressured_profile.execution_quality < open_profile.execution_quality
    assert pressured_profile.target_error_m > open_profile.target_error_m


def test_team_pass_speed_changes_actual_ball_speed_and_travel_time() -> None:
    slow_snapshot = _replace_home_in_possession(make_snapshot(seed=312), pass_speed=Level.VERY_LOW)
    fast_snapshot = _replace_home_in_possession(make_snapshot(seed=312), pass_speed=Level.VERY_HIGH)
    slow = SpatialMatchEngine(slow_snapshot)
    fast = SpatialMatchEngine(fast_snapshot)
    for engine in (slow, fast):
        _freeze_all(engine)
        passer = engine.state.player_for_slot(TeamSide.HOME, "cm")
        receiver = engine.state.player_for_slot(TeamSide.HOME, "rcm")
        passer.location = Vector2(40.0, 34.0)
        receiver.location = Vector2(52.0, 34.0)
        for opponent in engine.state.away_players:
            opponent.location = Vector2(92.0, 62.0)
        engine.give_ball_to(passer.agent_id)
        _freeze_all(engine)

    slow_passer = slow.state.player_for_slot(TeamSide.HOME, "cm")
    slow_receiver = slow.state.player_for_slot(TeamSide.HOME, "rcm")
    fast_passer = fast.state.player_for_slot(TeamSide.HOME, "cm")
    fast_receiver = fast.state.player_for_slot(TeamSide.HOME, "rcm")
    slow_profile = slow.start_pass(_decision(slow_passer, slow_receiver)).profile
    fast_profile = fast.start_pass(_decision(fast_passer, fast_receiver)).profile

    assert fast_profile.ball_speed_mps > slow_profile.ball_speed_mps
    assert fast_profile.expected_travel_seconds < slow_profile.expected_travel_seconds


def test_receiver_current_movement_is_used_to_lead_the_pass() -> None:
    engine, passer, receiver = _open_short_pass_engine(seed=313)
    engine.set_player_velocity(receiver.agent_id, Vector2(3.0, 0.0))

    profile = engine.start_pass(_decision(passer, receiver)).profile

    assert profile.intended_target.x > receiver.location.x


def test_blocker_on_ball_path_can_intercept_and_flip_possession() -> None:
    engine, passer, receiver = _open_short_pass_engine(seed=1)
    blocker = engine.state.player_for_slot(TeamSide.AWAY, "cm")
    blocker.location = Vector2(46.0, 34.0)
    engine.start_pass(_decision(passer, receiver))

    result = engine.resolve_active_pass()

    assert result.outcome is PassOutcome.INTERCEPTED
    assert result.interception_agent_id == blocker.agent_id
    assert result.controller_agent_id == blocker.agent_id
    assert engine.state.ball.owner_agent_id == blocker.agent_id
    assert engine.state.possession.team_side is TeamSide.AWAY
    assert engine.state.possession.owner_agent_id == blocker.agent_id


def test_interception_happens_before_original_pass_travel_time_finishes() -> None:
    engine, passer, receiver = _open_short_pass_engine(seed=1)
    blocker = engine.state.player_for_slot(TeamSide.AWAY, "cm")
    blocker.location = Vector2(46.0, 34.0)
    active = engine.start_pass(_decision(passer, receiver))

    result = engine.resolve_active_pass()

    assert result.outcome is PassOutcome.INTERCEPTED
    assert result.travel_seconds < active.profile.expected_travel_seconds


def test_receiver_moving_away_after_pass_start_can_make_pass_misplaced() -> None:
    engine, passer, receiver = _open_short_pass_engine(seed=314)
    # Keep all non-target teammates away from the expected endpoint too.
    for teammate in engine.state.home_players:
        if teammate.agent_id not in {passer.agent_id, receiver.agent_id}:
            teammate.location = Vector2(10.0, 8.0)
    engine.start_pass(_decision(passer, receiver))
    receiver.location = Vector2(75.0, 55.0)

    result = engine.resolve_active_pass()

    assert result.outcome is PassOutcome.MISPLACED
    assert result.controller_agent_id is None
    assert engine.state.ball.owner_agent_id is None
    assert engine.state.possession.owner_agent_id is None
    assert engine.state.possession.team_side is None


def test_poor_first_touch_under_pressure_can_create_bad_control() -> None:
    engine = SpatialMatchEngine(_low_first_touch_snapshot(seed=301))
    _freeze_all(engine)
    passer = engine.state.player_for_slot(TeamSide.HOME, "cm")
    receiver = engine.state.player_for_slot(TeamSide.HOME, "rcm")
    passer.location = Vector2(40.0, 34.0)
    receiver.location = Vector2(52.0, 34.0)
    for opponent in engine.state.away_players:
        opponent.location = Vector2(92.0, 62.0)
    pressure_player = engine.state.player_for_slot(TeamSide.AWAY, "cm")
    pressure_player.location = Vector2(52.0, 37.2)
    engine.give_ball_to(passer.agent_id)
    _freeze_all(engine)
    engine.start_pass(_decision(passer, receiver))

    result = engine.resolve_active_pass()

    assert result.outcome is PassOutcome.BAD_CONTROL
    assert result.first_touch_quality is not None
    assert result.first_touch_probability is not None
    assert result.first_touch_probability < 0.5
    assert engine.state.ball.owner_agent_id is None
    assert engine.state.possession.team_side is None
    assert engine.state.ball.last_touch_agent_id == receiver.agent_id


def test_completed_pass_exposes_first_touch_quality_and_probability() -> None:
    engine, passer, receiver = _open_short_pass_engine(seed=1)
    engine.start_pass(_decision(passer, receiver))

    result = engine.resolve_active_pass()

    assert result.outcome is PassOutcome.COMPLETED
    assert result.first_touch_quality is not None
    assert result.first_touch_probability is not None
    assert 0.0 <= result.first_touch_quality <= 100.0
    assert 0.0 <= result.first_touch_probability <= 1.0


def test_long_pass_is_faster_but_harder_to_execute_than_short_pass() -> None:
    short, short_passer, short_receiver = _open_short_pass_engine(seed=315)
    long, long_passer, long_receiver = _open_short_pass_engine(seed=315)

    short_profile = short.start_pass(
        _decision(short_passer, short_receiver, ActionType.SHORT_PASS)
    ).profile
    long_profile = long.start_pass(
        _decision(long_passer, long_receiver, ActionType.LONG_PASS)
    ).profile

    assert long_profile.ball_speed_mps > short_profile.ball_speed_mps
    assert long_profile.execution_quality < short_profile.execution_quality
    assert long_profile.target_error_m > short_profile.target_error_m


def test_pass_start_rejects_non_pass_decisions() -> None:
    engine, passer, _ = _open_short_pass_engine(seed=316)
    decision = PlayerDecision(
        agent_id=passer.agent_id,
        action_type=ActionType.HOLD,
        target_agent_id=None,
        utility=80.0,
        considered_options=5,
    )

    with pytest.raises(ValueError, match="only execute pass decisions"):
        engine.start_pass(decision)


def test_pass_start_rejects_opponent_as_receiver() -> None:
    engine, passer, _ = _open_short_pass_engine(seed=317)
    opponent = engine.state.player_for_slot(TeamSide.AWAY, "st")
    decision = _decision(passer, opponent)

    with pytest.raises(ValueError, match="receiver must be a teammate"):
        engine.start_pass(decision)


def test_cannot_start_second_pass_while_first_is_in_flight() -> None:
    engine, passer, receiver = _open_short_pass_engine(seed=318)
    decision = _decision(passer, receiver)
    engine.start_pass(decision)

    with pytest.raises(ValueError, match="another pass is in flight"):
        engine.start_pass(decision)


def test_resolve_active_pass_requires_an_active_pass() -> None:
    engine, _, _ = _open_short_pass_engine(seed=319)

    with pytest.raises(ValueError, match="no active pass"):
        engine.resolve_active_pass()


def test_multiple_completed_passes_can_form_a_real_possession_sequence() -> None:
    engine = SpatialMatchEngine(make_snapshot(seed=301))
    _freeze_all(engine)
    cm = engine.state.player_for_slot(TeamSide.HOME, "cm")
    rcm = engine.state.player_for_slot(TeamSide.HOME, "rcm")
    rw = engine.state.player_for_slot(TeamSide.HOME, "rw")
    cm.location = Vector2(40.0, 34.0)
    rcm.location = Vector2(52.0, 34.0)
    rw.location = Vector2(64.0, 24.0)
    for opponent in engine.state.away_players:
        opponent.location = Vector2(95.0, 62.0)
    engine.give_ball_to(cm.agent_id)
    _freeze_all(engine)

    engine.start_pass(_decision(cm, rcm))
    first = engine.resolve_active_pass()
    engine.start_pass(_decision(rcm, rw))
    second = engine.resolve_active_pass()

    assert first.outcome is PassOutcome.COMPLETED
    assert second.outcome is PassOutcome.COMPLETED
    assert engine.state.ball.owner_agent_id == rw.agent_id
    assert engine.state.possession.owner_agent_id == rw.agent_id


def test_fixed_tick_chunking_preserves_pass_resolution() -> None:
    first, first_passer, first_receiver = _open_short_pass_engine(seed=320)
    second, second_passer, second_receiver = _open_short_pass_engine(seed=320)
    first.start_pass(_decision(first_passer, first_receiver))
    second.start_pass(_decision(second_passer, second_receiver))

    # Same fixed-step path: one engine consumed one tick at a time, the other in
    # a larger playback chunk. Neither changes internal simulation precision.
    for _ in range(4):
        first.advance_ticks(1)
    second.advance_ticks(4)

    assert first.last_pass_result == second.last_pass_result
    assert first.state.signature() == second.state.signature()
