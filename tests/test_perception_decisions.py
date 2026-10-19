from __future__ import annotations

from dataclasses import replace

import pytest

from football_manager.domain import Level, PassLength, PlayerInstructions
from football_manager.simulation import ActionType, SpatialMatchEngine, TeamSide, Vector2

from test_spatial_core import make_snapshot


def _home_owner(engine: SpatialMatchEngine, slot_id: str = "cm"):
    engine.set_team_possession(TeamSide.HOME)
    owner = engine.state.player_for_slot(TeamSide.HOME, slot_id)
    engine.give_ball_to(owner.agent_id)
    return owner


def _option(engine: SpatialMatchEngine, action_type: ActionType, target_agent_id: str | None = None):
    for item in engine.decision_options(engine.state.ball.owner_agent_id or ""):
        if item.action_type is action_type and (
            target_agent_id is None or item.target_agent_id == target_agent_id
        ):
            return item
    raise AssertionError(f"missing option {action_type} target={target_agent_id}")


def _replace_home_in_possession(snapshot, **changes):
    instructions = snapshot.home_team.tactic.team_instructions
    in_possession = replace(instructions.in_possession, **changes)
    team_instructions = replace(instructions, in_possession=in_possession)
    tactic = replace(snapshot.home_team.tactic, team_instructions=team_instructions)
    return replace(snapshot, home_team=replace(snapshot.home_team, tactic=tactic))


def _replace_home_player(snapshot, slot_id: str, **changes):
    starters = tuple(
        replace(player, **changes) if player.assigned_slot_id == slot_id else player
        for player in snapshot.home_team.starters
    )
    return replace(snapshot, home_team=replace(snapshot.home_team, starters=starters))


def test_perception_excludes_self_and_returns_nearby_players_sorted_by_distance() -> None:
    engine = SpatialMatchEngine(make_snapshot(seed=200))
    owner = _home_owner(engine)
    perception = engine.perceive(owner.agent_id)

    assert all(item.agent_id != owner.agent_id for item in perception.teammates)
    assert all(item.agent_id != owner.agent_id for item in perception.opponents)
    assert list(perception.teammates) == sorted(
        perception.teammates, key=lambda item: (item.distance_m, item.agent_id)
    )
    assert perception.awareness_radius_m > 38.0


def test_nearby_opponents_create_more_pressure_and_less_space() -> None:
    engine = SpatialMatchEngine(make_snapshot(seed=201))
    owner = _home_owner(engine)
    opponent = engine.state.player_for_slot(TeamSide.AWAY, "cm")

    opponent.location = owner.location + Vector2(2.0, 0.0)
    high = engine.perceive(owner.agent_id)
    opponent.location = owner.location + Vector2(15.0, 0.0)
    low = engine.perceive(owner.agent_id)

    assert high.pressure > low.pressure
    assert high.local_space < low.local_space
    assert high.pressure > 0.5


def test_opponent_between_players_closes_passing_lane() -> None:
    engine = SpatialMatchEngine(make_snapshot(seed=202))
    owner = _home_owner(engine)
    receiver = engine.state.player_for_slot(TeamSide.HOME, "st")
    blocker = engine.state.player_for_slot(TeamSide.AWAY, "cm")

    owner.location = Vector2(45.0, 34.0)
    receiver.location = Vector2(65.0, 34.0)
    for opponent in engine.state.away_players:
        opponent.location = Vector2(90.0, 60.0)
    blocker.location = Vector2(55.0, 34.0)
    blocked = engine.perceive(owner.agent_id).lane_to(receiver.agent_id)

    blocker.location = Vector2(55.0, 45.0)
    open_lane = engine.perceive(owner.agent_id).lane_to(receiver.agent_id)

    assert blocked.lane_openness < open_lane.lane_openness
    assert blocked.lane_openness == pytest.approx(0.0)
    assert open_lane.lane_openness == pytest.approx(1.0)


def test_receiver_space_reflects_defender_proximity() -> None:
    engine = SpatialMatchEngine(make_snapshot(seed=203))
    owner = _home_owner(engine)
    receiver = engine.state.player_for_slot(TeamSide.HOME, "rcm")
    marker = engine.state.player_for_slot(TeamSide.AWAY, "lcm")

    marker.location = receiver.location + Vector2(1.5, 0.0)
    marked = engine.perceive(owner.agent_id).lane_to(receiver.agent_id)
    marker.location = receiver.location + Vector2(14.0, 0.0)
    free = engine.perceive(owner.agent_id).lane_to(receiver.agent_id)

    assert marked.receiver_space < free.receiver_space


def test_goal_direction_respects_home_and_away_orientation() -> None:
    engine = SpatialMatchEngine(make_snapshot(seed=204))
    home = engine.state.player_for_slot(TeamSide.HOME, "cm")
    away = engine.state.player_for_slot(TeamSide.AWAY, "cm")

    assert engine.perceive(home.agent_id).goal_direction.x > 0
    assert engine.perceive(away.agent_id).goal_direction.x < 0


def test_give_ball_to_synchronizes_ball_possession_and_player_flag() -> None:
    engine = SpatialMatchEngine(make_snapshot(seed=205))
    owner = _home_owner(engine, "rcm")

    assert engine.state.ball.owner_agent_id == owner.agent_id
    assert engine.state.possession.owner_agent_id == owner.agent_id
    assert engine.state.possession.team_side is TeamSide.HOME
    assert engine.state.ball.location == owner.location
    assert owner.has_ball
    assert sum(agent.has_ball for agent in engine.state.players.values()) == 1


def test_ball_follows_owner_during_fixed_step_movement() -> None:
    engine = SpatialMatchEngine(make_snapshot(seed=206))
    owner = _home_owner(engine, "cm")
    engine.set_player_velocity(owner.agent_id, Vector2(4.0, 0.0))

    engine.step()

    assert engine.state.ball.location == owner.location
    assert engine.state.ball.velocity == owner.velocity


def test_possession_decisions_require_actual_ball_owner() -> None:
    engine = SpatialMatchEngine(make_snapshot(seed=207))
    engine.set_team_possession(TeamSide.HOME)
    cm = engine.state.player_for_slot(TeamSide.HOME, "cm")

    with pytest.raises(ValueError, match="own the ball"):
        engine.decision_options(cm.agent_id)


def test_ball_owner_receives_context_valid_basic_options() -> None:
    engine = SpatialMatchEngine(make_snapshot(seed=208))
    owner = _home_owner(engine, "cm")
    options = engine.decision_options(owner.agent_id)
    action_types = {item.action_type for item in options}

    assert ActionType.HOLD in action_types
    assert ActionType.CARRY in action_types
    assert any(
        action in action_types
        for action in (ActionType.SHORT_PASS, ActionType.PROGRESSIVE_PASS, ActionType.LONG_PASS)
    )


def test_blocked_lane_reduces_pass_spatial_value_and_utility() -> None:
    engine = SpatialMatchEngine(make_snapshot(seed=209))
    owner = _home_owner(engine)
    receiver = engine.state.player_for_slot(TeamSide.HOME, "st")
    blocker = engine.state.player_for_slot(TeamSide.AWAY, "cm")
    owner.location = Vector2(45.0, 34.0)
    receiver.location = Vector2(67.0, 34.0)

    for opponent in engine.state.away_players:
        opponent.location = Vector2(90.0, 60.0)
    blocker.location = Vector2(56.0, 45.0)
    open_option = _option(engine, ActionType.PROGRESSIVE_PASS, receiver.agent_id)
    blocker.location = Vector2(56.0, 34.0)
    blocked_option = _option(engine, ActionType.PROGRESSIVE_PASS, receiver.agent_id)

    assert blocked_option.factors.spatial_value < open_option.factors.spatial_value
    assert blocked_option.factors.risk > open_option.factors.risk
    assert blocked_option.utility < open_option.utility


def test_team_pass_length_changes_short_pass_tactical_fit() -> None:
    short_snapshot = _replace_home_in_possession(
        make_snapshot(seed=210), pass_length=PassLength.VERY_SHORT
    )
    long_snapshot = _replace_home_in_possession(
        make_snapshot(seed=210), pass_length=PassLength.VERY_LONG
    )
    short_engine = SpatialMatchEngine(short_snapshot)
    long_engine = SpatialMatchEngine(long_snapshot)
    short_owner = _home_owner(short_engine, "cm")
    long_owner = _home_owner(long_engine, "cm")

    # Force one equivalent close receiver so the same action exists in both states.
    short_receiver = short_engine.state.player_for_slot(TeamSide.HOME, "rcm")
    long_receiver = long_engine.state.player_for_slot(TeamSide.HOME, "rcm")
    short_receiver.location = short_owner.location + Vector2(10.0, 1.0)
    long_receiver.location = long_owner.location + Vector2(10.0, 1.0)

    short_option = _option(short_engine, ActionType.SHORT_PASS, short_receiver.agent_id)
    long_option = _option(long_engine, ActionType.SHORT_PASS, long_receiver.agent_id)

    assert short_option.factors.tactical_fit > long_option.factors.tactical_fit


def test_individual_dribble_frequency_changes_dribble_tactical_fit() -> None:
    snapshot = make_snapshot(seed=211)
    player = snapshot.home_team.player_for_slot("cm")
    base = player.effective_instructions or PlayerInstructions()
    low_snapshot = _replace_home_player(
        snapshot,
        "cm",
        effective_instructions=replace(base, dribbling_frequency=Level.VERY_LOW),
    )
    high_snapshot = _replace_home_player(
        snapshot,
        "cm",
        effective_instructions=replace(base, dribbling_frequency=Level.VERY_HIGH),
    )
    low_engine = SpatialMatchEngine(low_snapshot)
    high_engine = SpatialMatchEngine(high_snapshot)
    low_owner = _home_owner(low_engine)
    high_owner = _home_owner(high_engine)
    low_defender = low_engine.state.player_for_slot(TeamSide.AWAY, "cm")
    high_defender = high_engine.state.player_for_slot(TeamSide.AWAY, "cm")
    low_defender.location = low_owner.location + Vector2(3.0, 0.0)
    high_defender.location = high_owner.location + Vector2(3.0, 0.0)

    low = _option(low_engine, ActionType.DRIBBLE)
    high = _option(high_engine, ActionType.DRIBBLE)

    assert high.factors.tactical_fit > low.factors.tactical_fit
    assert high.utility > low.utility


def test_dribble_option_requires_a_nearby_opponent() -> None:
    engine = SpatialMatchEngine(make_snapshot(seed=212))
    owner = _home_owner(engine)
    for opponent in engine.state.away_players:
        opponent.location = Vector2(95.0, opponent.location.y)
    assert ActionType.DRIBBLE not in {item.action_type for item in engine.decision_options(owner.agent_id)}

    engine.state.player_for_slot(TeamSide.AWAY, "cm").location = owner.location + Vector2(3.0, 0.0)
    assert ActionType.DRIBBLE in {item.action_type for item in engine.decision_options(owner.agent_id)}


def test_shot_option_only_appears_in_plausible_attacking_range() -> None:
    engine = SpatialMatchEngine(make_snapshot(seed=213))
    owner = _home_owner(engine, "st")
    owner.location = Vector2(48.0, 34.0)
    engine.state.ball.location = owner.location
    assert ActionType.SHOOT not in {item.action_type for item in engine.decision_options(owner.agent_id)}

    owner.location = Vector2(82.0, 34.0)
    engine.state.ball.location = owner.location
    assert ActionType.SHOOT in {item.action_type for item in engine.decision_options(owner.agent_id)}


def test_cross_option_requires_wide_advanced_location() -> None:
    engine = SpatialMatchEngine(make_snapshot(seed=214))
    owner = _home_owner(engine, "rw")
    owner.location = Vector2(70.0, 8.0)
    engine.state.ball.location = owner.location
    assert ActionType.CROSS in {item.action_type for item in engine.decision_options(owner.agent_id)}

    owner.location = Vector2(70.0, 34.0)
    engine.state.ball.location = owner.location
    assert ActionType.CROSS not in {item.action_type for item in engine.decision_options(owner.agent_id)}


def test_clearance_is_context_valid_in_own_defensive_third() -> None:
    engine = SpatialMatchEngine(make_snapshot(seed=215))
    owner = _home_owner(engine, "lcb")
    owner.location = Vector2(18.0, 30.0)
    engine.state.ball.location = owner.location

    assert ActionType.CLEARANCE in {item.action_type for item in engine.decision_options(owner.agent_id)}


def test_same_seed_and_same_state_choose_same_decision() -> None:
    first = SpatialMatchEngine(make_snapshot(seed=216))
    second = SpatialMatchEngine(make_snapshot(seed=216))
    first_owner = _home_owner(first)
    second_owner = _home_owner(second)

    assert first.decide(first_owner.agent_id) == second.decide(second_owner.agent_id)


def test_decision_selection_does_not_execute_or_move_the_ball() -> None:
    engine = SpatialMatchEngine(make_snapshot(seed=217))
    owner = _home_owner(engine)
    before_signature = engine.state.signature()
    before_ball = engine.state.ball.location

    decision = engine.decide(owner.agent_id)

    assert decision.considered_options > 0
    assert engine.state.signature() == before_signature
    assert engine.state.ball.location == before_ball
    assert engine.state.ball.owner_agent_id == owner.agent_id
