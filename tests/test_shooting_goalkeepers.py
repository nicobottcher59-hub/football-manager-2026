from __future__ import annotations

from dataclasses import replace

import pytest

from football_manager.domain import GoalkeepingAttributes
from football_manager.simulation import (
    ActionType,
    ChanceOrigin,
    PlayerDecision,
    ShotBodyPart,
    ShotOutcome,
    SpatialMatchEngine,
    TeamSide,
    Vector2,
)

from test_spatial_core import make_snapshot


def _decision(shooter) -> PlayerDecision:
    return PlayerDecision(
        agent_id=shooter.agent_id,
        action_type=ActionType.SHOOT,
        target_agent_id=None,
        utility=85.0,
        considered_options=8,
    )


def _freeze_all(engine: SpatialMatchEngine) -> None:
    for agent in engine.state.players.values():
        engine.set_player_velocity(agent.agent_id, Vector2.zero())


def _replace_starter(snapshot, side: TeamSide, slot_id: str, transform):
    team = snapshot.home_team if side is TeamSide.HOME else snapshot.away_team
    starters = tuple(
        transform(player) if player.assigned_slot_id == slot_id else player
        for player in team.starters
    )
    new_team = replace(team, starters=starters)
    if side is TeamSide.HOME:
        return replace(snapshot, home_team=new_team)
    return replace(snapshot, away_team=new_team)


def _with_finishing(snapshot, quality: int):
    def transform(player):
        technical = replace(
            player.attributes.technical,
            finishing=quality,
            long_shots=quality,
            technique=quality,
            shot_power=quality,
        )
        mental = replace(
            player.attributes.mental,
            composure=quality,
            decisions=quality,
        )
        return replace(
            player,
            attributes=replace(
                player.attributes,
                technical=technical,
                mental=mental,
            ),
        )

    return _replace_starter(snapshot, TeamSide.HOME, "st", transform)


def _with_shot_power(snapshot, quality: int):
    def transform(player):
        technical = replace(player.attributes.technical, shot_power=quality)
        return replace(
            player,
            attributes=replace(player.attributes, technical=technical),
        )

    return _replace_starter(snapshot, TeamSide.HOME, "st", transform)


def _with_header_quality(snapshot, quality: int):
    def transform(player):
        technical = replace(
            player.attributes.technical,
            heading=quality,
            finishing=quality,
        )
        mental = replace(
            player.attributes.mental,
            anticipation=quality,
            bravery=quality,
            composure=quality,
        )
        physical = replace(player.attributes.physical, jumping_reach=quality)
        return replace(
            player,
            attributes=replace(
                player.attributes,
                technical=technical,
                mental=mental,
                physical=physical,
            ),
        )

    return _replace_starter(snapshot, TeamSide.HOME, "st", transform)


def _with_goalkeeper_quality(snapshot, quality: int):
    def transform(player):
        goalkeeping = GoalkeepingAttributes(
            reflexes=quality,
            handling=quality,
            one_on_ones=quality,
            aerial_reach=quality,
            command_of_area=quality,
            kicking=quality,
            throwing=quality,
            goalkeeper_positioning=quality,
        )
        return replace(
            player,
            attributes=replace(player.attributes, goalkeeping=goalkeeping),
        )

    return _replace_starter(snapshot, TeamSide.AWAY, "gk", transform)


def _shot_engine(
    *,
    seed: int = 5601,
    snapshot=None,
    shooter_location: Vector2 = Vector2(88.0, 34.0),
    goalkeeper_location: Vector2 = Vector2(103.5, 34.0),
):
    engine = SpatialMatchEngine(snapshot or make_snapshot(seed=seed))
    _freeze_all(engine)
    shooter = engine.state.player_for_slot(TeamSide.HOME, "st")
    goalkeeper = engine.state.player_for_slot(TeamSide.AWAY, "gk")
    shooter.location = shooter_location
    goalkeeper.location = goalkeeper_location
    for opponent in engine.state.away_players:
        if opponent.agent_id != goalkeeper.agent_id:
            opponent.location = Vector2(35.0, 62.0)
    engine.give_ball_to(shooter.agent_id)
    _freeze_all(engine)
    return engine, shooter, goalkeeper


def test_shot_requires_a_shoot_decision() -> None:
    engine, shooter, _ = _shot_engine()
    decision = replace(_decision(shooter), action_type=ActionType.HOLD)

    with pytest.raises(ValueError, match="requires a shoot decision"):
        engine.start_shot(decision)


def test_starting_shot_detaches_ball_but_keeps_attacking_team_possession_in_flight() -> None:
    engine, shooter, _ = _shot_engine()

    engine.start_shot(_decision(shooter))

    assert engine.state.ball.owner_agent_id is None
    assert engine.state.possession.owner_agent_id is None
    assert engine.state.possession.team_side is TeamSide.HOME
    assert engine.state.ball.last_touch_agent_id == shooter.agent_id
    assert not any(agent.has_ball for agent in engine.state.players.values())


def test_shot_ball_moves_through_space_instead_of_teleporting_to_goal() -> None:
    engine, shooter, _ = _shot_engine()
    active = engine.start_shot(_decision(shooter))
    target = active.profile.actual_target

    engine.step()

    assert engine.active_shot is not None
    assert engine.state.ball.location != shooter.location
    assert engine.state.ball.location != target
    assert shooter.location.distance_to(engine.state.ball.location) < shooter.location.distance_to(target)


def test_shot_profile_exposes_contextual_xg_between_zero_and_one() -> None:
    engine, shooter, _ = _shot_engine()

    profile = engine.start_shot(_decision(shooter)).profile

    assert 0.0 < profile.xg < 1.0
    assert profile.distance_m > 0.0
    assert profile.shot_angle_radians > 0.0
    assert 0.0 <= profile.pressure <= 1.0


def test_closer_central_chance_has_higher_xg_than_long_range_chance() -> None:
    close, close_shooter, _ = _shot_engine(seed=5611, shooter_location=Vector2(94.0, 34.0))
    far, far_shooter, _ = _shot_engine(seed=5611, shooter_location=Vector2(73.0, 34.0))

    close_xg = close.start_shot(_decision(close_shooter)).profile.xg
    far_xg = far.start_shot(_decision(far_shooter)).profile.xg

    assert close_xg > far_xg


def test_wide_angle_chance_has_lower_xg_than_central_chance() -> None:
    central, central_shooter, _ = _shot_engine(seed=5612, shooter_location=Vector2(88.0, 34.0))
    wide, wide_shooter, _ = _shot_engine(seed=5612, shooter_location=Vector2(88.0, 9.0))

    central_xg = central.start_shot(_decision(central_shooter)).profile.xg
    wide_xg = wide.start_shot(_decision(wide_shooter)).profile.xg

    assert central_xg > wide_xg


def test_pressure_reduces_xg_from_the_same_shot_location() -> None:
    open_engine, open_shooter, _ = _shot_engine(seed=5613)
    pressured, pressured_shooter, _ = _shot_engine(seed=5613)
    marker = pressured.state.player_for_slot(TeamSide.AWAY, "cm")
    marker.location = pressured_shooter.location + Vector2(0.0, 3.0)

    open_xg = open_engine.start_shot(_decision(open_shooter)).profile.xg
    pressured_profile = pressured.start_shot(_decision(pressured_shooter)).profile

    assert pressured_profile.pressure > 0.0
    assert pressured_profile.xg < open_xg


def test_real_defenders_in_shot_lane_reduce_xg() -> None:
    clear, clear_shooter, _ = _shot_engine(seed=5614, shooter_location=Vector2(84.0, 34.0))
    blocked, blocked_shooter, _ = _shot_engine(seed=5614, shooter_location=Vector2(84.0, 34.0))
    blocked.state.player_for_slot(TeamSide.AWAY, "cm").location = Vector2(91.0, 34.0)
    blocked.state.player_for_slot(TeamSide.AWAY, "rcm").location = Vector2(96.0, 34.4)

    clear_profile = clear.start_shot(_decision(clear_shooter)).profile
    blocked_profile = blocked.start_shot(_decision(blocked_shooter)).profile

    assert blocked_profile.blocker_count > clear_profile.blocker_count
    assert blocked_profile.xg < clear_profile.xg


def test_finishing_quality_changes_execution_but_not_pre_shot_xg() -> None:
    poor_snapshot = _with_finishing(make_snapshot(seed=5615), 25)
    elite_snapshot = _with_finishing(make_snapshot(seed=5615), 95)
    poor, poor_shooter, _ = _shot_engine(snapshot=poor_snapshot)
    elite, elite_shooter, _ = _shot_engine(snapshot=elite_snapshot)

    poor_profile = poor.start_shot(_decision(poor_shooter)).profile
    elite_profile = elite.start_shot(_decision(elite_shooter)).profile

    assert elite_profile.xg == pytest.approx(poor_profile.xg)
    assert elite_profile.execution_quality > poor_profile.execution_quality
    assert elite_profile.target_error_m < poor_profile.target_error_m


def test_shot_power_changes_actual_ball_speed_not_xg() -> None:
    low_snapshot = _with_shot_power(make_snapshot(seed=5616), 20)
    high_snapshot = _with_shot_power(make_snapshot(seed=5616), 95)
    low, low_shooter, _ = _shot_engine(snapshot=low_snapshot)
    high, high_shooter, _ = _shot_engine(snapshot=high_snapshot)

    low_profile = low.start_shot(_decision(low_shooter)).profile
    high_profile = high.start_shot(_decision(high_shooter)).profile

    assert high_profile.shot_speed_mps > low_profile.shot_speed_mps
    assert high_profile.expected_travel_seconds < low_profile.expected_travel_seconds
    assert high_profile.xg == pytest.approx(low_profile.xg)


def test_header_is_a_distinct_body_part_and_uses_a_different_chance_model() -> None:
    foot, foot_shooter, _ = _shot_engine(seed=5617, shooter_location=Vector2(93.0, 34.0))
    head, head_shooter, _ = _shot_engine(seed=5617, shooter_location=Vector2(93.0, 34.0))

    foot_profile = foot.start_shot(_decision(foot_shooter), body_part=ShotBodyPart.FOOT).profile
    head_profile = head.start_shot(_decision(head_shooter), body_part=ShotBodyPart.HEAD).profile

    assert head_profile.body_part is ShotBodyPart.HEAD
    assert head_profile.xg < foot_profile.xg
    assert head_profile.shot_speed_mps < foot_profile.shot_speed_mps
    assert head_profile.origin_height_m > foot_profile.origin_height_m


def test_heading_attributes_change_header_execution_quality() -> None:
    poor_snapshot = _with_header_quality(make_snapshot(seed=5618), 25)
    elite_snapshot = _with_header_quality(make_snapshot(seed=5618), 95)
    poor, poor_shooter, _ = _shot_engine(snapshot=poor_snapshot, shooter_location=Vector2(93.0, 34.0))
    elite, elite_shooter, _ = _shot_engine(snapshot=elite_snapshot, shooter_location=Vector2(93.0, 34.0))

    poor_profile = poor.start_shot(_decision(poor_shooter), body_part=ShotBodyPart.HEAD).profile
    elite_profile = elite.start_shot(_decision(elite_shooter), body_part=ShotBodyPart.HEAD).profile

    assert elite_profile.execution_quality > poor_profile.execution_quality


def test_cutback_origin_is_higher_quality_than_equivalent_cross_origin() -> None:
    cross, cross_shooter, _ = _shot_engine(seed=5619, shooter_location=Vector2(93.0, 34.0))
    cutback, cutback_shooter, _ = _shot_engine(seed=5619, shooter_location=Vector2(93.0, 34.0))

    cross_xg = cross.start_shot(
        _decision(cross_shooter),
        chance_origin=ChanceOrigin.CROSS,
    ).profile.xg
    cutback_xg = cutback.start_shot(
        _decision(cutback_shooter),
        chance_origin=ChanceOrigin.CUTBACK,
    ).profile.xg

    assert cutback_xg > cross_xg


def test_fast_transition_can_raise_xg_without_changing_player_attributes() -> None:
    slow, slow_shooter, _ = _shot_engine(seed=5620)
    fast, fast_shooter, _ = _shot_engine(seed=5620)

    slow_xg = slow.start_shot(_decision(slow_shooter), transition_speed=0.0).profile.xg
    fast_xg = fast.start_shot(_decision(fast_shooter), transition_speed=1.0).profile.xg

    assert fast_xg > slow_xg


def test_goalkeeper_out_of_position_increases_xg_for_same_chance() -> None:
    set_engine, set_shooter, _ = _shot_engine(seed=5621, goalkeeper_location=Vector2(103.5, 34.0))
    stranded, stranded_shooter, _ = _shot_engine(seed=5621, goalkeeper_location=Vector2(99.0, 48.0))

    set_profile = set_engine.start_shot(_decision(set_shooter)).profile
    stranded_profile = stranded.start_shot(_decision(stranded_shooter)).profile

    assert stranded_profile.goalkeeper_position_disadvantage > set_profile.goalkeeper_position_disadvantage
    assert stranded_profile.xg > set_profile.xg


def test_better_goalkeeper_increases_save_probability_but_not_xg() -> None:
    weak_snapshot = _with_goalkeeper_quality(make_snapshot(seed=5622), 25)
    strong_snapshot = _with_goalkeeper_quality(make_snapshot(seed=5622), 95)
    weak, weak_shooter, _ = _shot_engine(snapshot=weak_snapshot)
    strong, strong_shooter, _ = _shot_engine(snapshot=strong_snapshot)

    weak_profile = weak.start_shot(_decision(weak_shooter)).profile
    strong_profile = strong.start_shot(_decision(strong_shooter)).profile
    weak_save = weak.shooting.save_probability(weak.state, weak_profile)
    strong_save = strong.shooting.save_probability(strong.state, strong_profile)

    assert strong_profile.xg == pytest.approx(weak_profile.xg)
    assert strong_profile.goalkeeper_quality > weak_profile.goalkeeper_quality
    assert strong_save > weak_save


def test_goalkeeper_physically_reacts_toward_shot_target() -> None:
    engine, shooter, goalkeeper = _shot_engine(seed=5623)
    active = engine.start_shot(_decision(shooter))
    start = goalkeeper.location

    engine.advance_ticks(2)

    assert goalkeeper.location != start
    assert goalkeeper.location.distance_to(active.profile.goalkeeper_target_location) < start.distance_to(active.profile.goalkeeper_target_location)


def test_defender_on_real_shot_path_can_block_and_create_rebound() -> None:
    engine, shooter, _ = _shot_engine(seed=1, shooter_location=Vector2(84.0, 34.0))
    blocker = engine.state.player_for_slot(TeamSide.AWAY, "cm")
    active = engine.start_shot(_decision(shooter))
    blocker.location = active.profile.origin + (active.profile.actual_target - active.profile.origin).scale(0.40)

    result = engine.resolve_active_shot()

    assert result.outcome is ShotOutcome.BLOCKED
    assert result.blocker_agent_id == blocker.agent_id
    assert result.rebound_location is not None
    assert engine.state.ball.owner_agent_id is None


def test_seeded_on_target_save_transfers_control_to_goalkeeper() -> None:
    engine, shooter, goalkeeper = _shot_engine(seed=6)
    engine.start_shot(_decision(shooter))

    result = engine.resolve_active_shot()

    assert result.outcome is ShotOutcome.SAVED
    assert result.on_target
    assert result.controller_agent_id == goalkeeper.agent_id
    assert engine.state.ball.owner_agent_id == goalkeeper.agent_id
    assert engine.state.possession.team_side is TeamSide.AWAY


def test_seeded_parry_creates_genuine_loose_rebound() -> None:
    engine, shooter, _ = _shot_engine(seed=1)
    engine.start_shot(_decision(shooter))

    result = engine.resolve_active_shot()

    assert result.outcome is ShotOutcome.PARRIED
    assert result.on_target
    assert result.rebound_location is not None
    assert engine.state.ball.owner_agent_id is None
    assert engine.state.possession.team_side is None


def test_seeded_goal_is_distinct_from_xg_and_save_resolution() -> None:
    engine, shooter, _ = _shot_engine(seed=5602)
    profile = engine.start_shot(_decision(shooter)).profile

    result = engine.resolve_active_shot()

    assert result.outcome is ShotOutcome.GOAL
    assert result.on_target
    assert result.xg == profile.xg
    assert result.save_probability is not None
    assert engine.state.ball.owner_agent_id is None
    assert engine.state.possession.team_side is None


def test_forced_off_target_geometry_resolves_as_off_target() -> None:
    engine, shooter, _ = _shot_engine(seed=5624)
    active = engine.start_shot(_decision(shooter))
    half = engine.shooting.config.goal_width_m / 2.0
    active.profile = replace(
        active.profile,
        actual_target_y=active.profile.goal_centre_y + half + 1.0,
        actual_target_height_m=1.0,
    )

    result = engine.resolve_active_shot()

    assert result.outcome is ShotOutcome.OFF_TARGET
    assert not result.on_target


def test_forced_post_contact_resolves_as_woodwork_and_rebounds() -> None:
    engine, shooter, _ = _shot_engine(seed=5625)
    active = engine.start_shot(_decision(shooter))
    half = engine.shooting.config.goal_width_m / 2.0
    active.profile = replace(
        active.profile,
        actual_target_y=active.profile.goal_centre_y + half + 0.04,
        actual_target_height_m=1.1,
    )

    result = engine.resolve_active_shot()

    assert result.outcome is ShotOutcome.WOODWORK
    assert result.rebound_location is not None
    assert engine.state.ball.owner_agent_id is None


def test_same_seed_same_setup_produces_same_shot_profile_result_and_state() -> None:
    first, first_shooter, _ = _shot_engine(seed=5626)
    second, second_shooter, _ = _shot_engine(seed=5626)

    first_profile = first.start_shot(_decision(first_shooter)).profile
    second_profile = second.start_shot(_decision(second_shooter)).profile
    first_result = first.resolve_active_shot()
    second_result = second.resolve_active_shot()

    assert first_profile == second_profile
    assert first_result == second_result
    assert first.state.signature() == second.state.signature()


def test_away_team_shoots_toward_x_zero() -> None:
    engine = SpatialMatchEngine(make_snapshot(seed=5627))
    _freeze_all(engine)
    shooter = engine.state.player_for_slot(TeamSide.AWAY, "st")
    goalkeeper = engine.state.player_for_slot(TeamSide.HOME, "gk")
    shooter.location = Vector2(17.0, 34.0)
    goalkeeper.location = Vector2(1.5, 34.0)
    for opponent in engine.state.home_players:
        if opponent.agent_id != goalkeeper.agent_id:
            opponent.location = Vector2(70.0, 62.0)
    engine.give_ball_to(shooter.agent_id)
    _freeze_all(engine)

    profile = engine.start_shot(_decision(shooter)).profile

    assert profile.goal_x == 0.0
    assert profile.actual_target.x == 0.0
    assert profile.goalkeeper_agent_id == goalkeeper.agent_id


def test_ball_height_is_part_of_deterministic_match_state_signature() -> None:
    engine, _, _ = _shot_engine(seed=5628)
    before = engine.state.signature()
    engine.state.ball.height_m = 1.25

    assert engine.state.signature() != before
