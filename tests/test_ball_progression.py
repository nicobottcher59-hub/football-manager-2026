from __future__ import annotations

from dataclasses import replace

import pytest

from football_manager.domain import (
    CrossType,
    InPossessionPosition,
    Level,
    PlayerInstructions,
)
from football_manager.simulation import (
    ActionType,
    CarryOutcome,
    CrossOutcome,
    DribbleOutcome,
    PlayerDecision,
    RunType,
    SpatialMatchEngine,
    TeamSide,
    Vector2,
)

from test_spatial_core import make_snapshot


def _decision(agent, action: ActionType, target=None) -> PlayerDecision:
    return PlayerDecision(
        agent_id=agent.agent_id,
        action_type=action,
        target_agent_id=target.agent_id if target is not None else None,
        utility=80.0,
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


def _with_player_instructions(snapshot, side: TeamSide, slot_id: str, **changes):
    def transform(player):
        base = player.effective_instructions or PlayerInstructions()
        return replace(player, effective_instructions=replace(base, **changes))

    return _replace_starter(snapshot, side, slot_id, transform)


def _replace_home_in_possession(snapshot, **changes):
    team = snapshot.home_team
    instructions = team.tactic.team_instructions
    in_possession = replace(instructions.in_possession, **changes)
    tactic = replace(
        team.tactic,
        team_instructions=replace(instructions, in_possession=in_possession),
    )
    return replace(snapshot, home_team=replace(team, tactic=tactic))


def _with_dribble_attributes(
    snapshot,
    *,
    attacker_quality: int,
    defender_quality: int,
):
    def attacker_transform(player):
        tech = replace(
            player.attributes.technical,
            dribbling=attacker_quality,
            technique=attacker_quality,
            first_touch=attacker_quality,
        )
        mental = replace(
            player.attributes.mental,
            decisions=attacker_quality,
            composure=attacker_quality,
        )
        physical = replace(
            player.attributes.physical,
            agility=attacker_quality,
            acceleration=attacker_quality,
            balance=attacker_quality,
        )
        return replace(
            player,
            attributes=replace(
                player.attributes,
                technical=tech,
                mental=mental,
                physical=physical,
            ),
        )

    def defender_transform(player):
        tech = replace(player.attributes.technical, tackling=defender_quality)
        mental = replace(
            player.attributes.mental,
            anticipation=defender_quality,
            positioning=defender_quality,
        )
        physical = replace(
            player.attributes.physical,
            agility=defender_quality,
            acceleration=defender_quality,
            balance=defender_quality,
            strength=defender_quality,
        )
        return replace(
            player,
            attributes=replace(
                player.attributes,
                technical=tech,
                mental=mental,
                physical=physical,
            ),
        )

    snapshot = _replace_starter(snapshot, TeamSide.HOME, "cm", attacker_transform)
    return _replace_starter(snapshot, TeamSide.AWAY, "cm", defender_transform)


def _carry_engine(seed: int = 5501, snapshot=None):
    engine = SpatialMatchEngine(snapshot or make_snapshot(seed=seed))
    _freeze_all(engine)
    carrier = engine.state.player_for_slot(TeamSide.HOME, "cm")
    carrier.location = Vector2(42.0, 34.0)
    for opponent in engine.state.away_players:
        opponent.location = Vector2(95.0, 62.0)
    engine.give_ball_to(carrier.agent_id)
    _freeze_all(engine)
    return engine, carrier


def _dribble_engine(seed: int = 5502, snapshot=None):
    engine = SpatialMatchEngine(snapshot or make_snapshot(seed=seed))
    _freeze_all(engine)
    attacker = engine.state.player_for_slot(TeamSide.HOME, "cm")
    defender = engine.state.player_for_slot(TeamSide.AWAY, "cm")
    attacker.location = Vector2(50.0, 34.0)
    defender.location = Vector2(53.0, 34.0)
    for agent in engine.state.away_players:
        if agent.agent_id != defender.agent_id:
            agent.location = Vector2(96.0, 62.0)
    engine.give_ball_to(attacker.agent_id)
    _freeze_all(engine)
    return engine, attacker, defender


def _cross_engine(seed: int = 5503, snapshot=None, *, byline: bool = False):
    engine = SpatialMatchEngine(snapshot or make_snapshot(seed=seed))
    _freeze_all(engine)
    crosser = engine.state.player_for_slot(TeamSide.HOME, "rw")
    striker = engine.state.player_for_slot(TeamSide.HOME, "st")
    crosser.location = Vector2(94.0 if byline else 78.0, 8.0)
    striker.location = Vector2(91.0, 34.0)
    for teammate in engine.state.home_players:
        if teammate.agent_id not in {crosser.agent_id, striker.agent_id}:
            teammate.location = Vector2(40.0, 55.0)
    for opponent in engine.state.away_players:
        opponent.location = Vector2(20.0, 62.0)
    engine.give_ball_to(crosser.agent_id)
    _freeze_all(engine)
    return engine, crosser, striker


def test_carry_requires_a_carry_decision() -> None:
    engine, carrier = _carry_engine()

    with pytest.raises(ValueError, match="requires a carry decision"):
        engine.start_carry(_decision(carrier, ActionType.HOLD))


def test_carry_profile_moves_forward_to_real_spatial_target() -> None:
    engine, carrier = _carry_engine()

    active = engine.start_carry(_decision(carrier, ActionType.CARRY))

    assert active.profile.target.x > carrier.location.x
    assert active.profile.distance_m > 0.0
    assert active.profile.speed_mps > 0.0
    assert 0.0 <= active.profile.retain_probability <= 1.0


def test_carry_moves_player_and_ball_through_fixed_ticks() -> None:
    engine, carrier = _carry_engine(seed=5504)
    start = carrier.location
    engine.start_carry(_decision(carrier, ActionType.CARRY))

    engine.advance_ticks(4)

    assert carrier.location.x > start.x
    assert engine.state.ball.owner_agent_id == carrier.agent_id
    assert engine.state.ball.location == carrier.location


def test_carry_resolves_without_teleport_and_keeps_or_loses_control_explicitly() -> None:
    engine, carrier = _carry_engine(seed=5505)
    active = engine.start_carry(_decision(carrier, ActionType.CARRY))

    result = engine.resolve_active_carry()

    assert engine.active_carry is None
    assert result.distance_covered_m <= active.profile.distance_m + 1.0
    assert result.outcome in {CarryOutcome.COMPLETED, CarryOutcome.LOOSE_BALL}
    if result.outcome is CarryOutcome.COMPLETED:
        assert engine.state.ball.owner_agent_id == carrier.agent_id
    else:
        assert engine.state.ball.owner_agent_id is None


def test_same_seed_produces_same_carry_profile_and_result() -> None:
    first, first_carrier = _carry_engine(seed=5506)
    second, second_carrier = _carry_engine(seed=5506)

    first_active = first.start_carry(_decision(first_carrier, ActionType.CARRY))
    second_active = second.start_carry(_decision(second_carrier, ActionType.CARRY))
    first_result = first.resolve_active_carry()
    second_result = second.resolve_active_carry()

    assert first_active.profile == second_active.profile
    assert first_result == second_result
    assert first.state.signature() == second.state.signature()


def test_attack_space_instruction_changes_real_carry_distance_not_attributes() -> None:
    low_snapshot = _with_player_instructions(
        make_snapshot(seed=5507),
        TeamSide.HOME,
        "cm",
        attack_space=Level.VERY_LOW,
    )
    high_snapshot = _with_player_instructions(
        make_snapshot(seed=5507),
        TeamSide.HOME,
        "cm",
        attack_space=Level.VERY_HIGH,
    )
    low, low_carrier = _carry_engine(snapshot=low_snapshot)
    high, high_carrier = _carry_engine(snapshot=high_snapshot)

    low_profile = low.start_carry(_decision(low_carrier, ActionType.CARRY)).profile
    high_profile = high.start_carry(_decision(high_carrier, ActionType.CARRY)).profile

    assert high_profile.distance_m > low_profile.distance_m
    assert (
        high_carrier.player.attributes.technical.dribbling
        == low_carrier.player.attributes.technical.dribbling
    )


def test_carry_target_can_avoid_pressure_in_straight_ahead_lane() -> None:
    engine, carrier = _carry_engine(seed=5508)
    blocker = engine.state.player_for_slot(TeamSide.AWAY, "cm")
    blocker.location = Vector2(49.0, 34.0)
    _freeze_all(engine)

    target = engine.start_carry(_decision(carrier, ActionType.CARRY)).profile.target

    assert target.y != pytest.approx(34.0)


def test_off_ball_plan_requires_team_possession() -> None:
    engine = SpatialMatchEngine(make_snapshot(seed=5509))
    engine.set_team_possession(TeamSide.AWAY)

    assert engine.off_ball_run_plan(TeamSide.HOME) == ()


def test_off_ball_run_plan_excludes_goalkeeper_and_ball_carrier() -> None:
    engine, carrier = _carry_engine(seed=5510)

    runs = engine.off_ball_run_plan(TeamSide.HOME, max_runners=10)
    runner_ids = {run.runner_agent_id for run in runs}

    assert carrier.agent_id not in runner_ids
    assert engine.state.player_for_slot(TeamSide.HOME, "gk").agent_id not in runner_ids


def test_forward_runs_instruction_changes_run_distance_and_priority() -> None:
    low_snapshot = _with_player_instructions(
        make_snapshot(seed=5511),
        TeamSide.HOME,
        "lw",
        forward_runs=Level.LOW,
        attack_space=Level.LOW,
    )
    high_snapshot = _with_player_instructions(
        make_snapshot(seed=5511),
        TeamSide.HOME,
        "lw",
        forward_runs=Level.VERY_HIGH,
        attack_space=Level.VERY_HIGH,
    )
    low = SpatialMatchEngine(low_snapshot)
    high = SpatialMatchEngine(high_snapshot)
    low.give_ball_to(low.state.player_for_slot(TeamSide.HOME, "cm").agent_id)
    high.give_ball_to(high.state.player_for_slot(TeamSide.HOME, "cm").agent_id)

    low_run = next(run for run in low.off_ball_run_plan(TeamSide.HOME, max_runners=10) if run.runner_agent_id.endswith(":home-lw"))
    high_run = next(run for run in high.off_ball_run_plan(TeamSide.HOME, max_runners=10) if run.runner_agent_id.endswith(":home-lw"))

    assert high_run.priority > low_run.priority
    assert high_run.origin.distance_to(high_run.target) > low_run.origin.distance_to(low_run.target)


def test_fullback_overlaps_when_winger_moves_inside() -> None:
    snapshot = _replace_home_in_possession(make_snapshot(seed=5512), overlap_frequency=Level.VERY_HIGH)
    snapshot = _with_player_instructions(
        snapshot,
        TeamSide.HOME,
        "lw",
        in_possession_position=InPossessionPosition.INSIDE,
    )
    engine = SpatialMatchEngine(snapshot)
    engine.give_ball_to(engine.state.player_for_slot(TeamSide.HOME, "cm").agent_id)

    lb_run = next(
        run
        for run in engine.off_ball_run_plan(TeamSide.HOME, max_runners=10)
        if run.runner_agent_id.endswith(":home-lb")
    )

    assert lb_run.run_type is RunType.OVERLAP
    assert lb_run.target.y < lb_run.origin.y


def test_fullback_underlaps_when_winger_stays_wide() -> None:
    snapshot = _replace_home_in_possession(make_snapshot(seed=5513), overlap_frequency=Level.VERY_HIGH)
    snapshot = _with_player_instructions(
        snapshot,
        TeamSide.HOME,
        "lw",
        in_possession_position=InPossessionPosition.WIDE,
    )
    engine = SpatialMatchEngine(snapshot)
    engine.give_ball_to(engine.state.player_for_slot(TeamSide.HOME, "cm").agent_id)

    lb_run = next(
        run
        for run in engine.off_ball_run_plan(TeamSide.HOME, max_runners=10)
        if run.runner_agent_id.endswith(":home-lb")
    )

    assert lb_run.run_type is RunType.UNDERLAP
    assert lb_run.target.y > lb_run.origin.y


def test_started_off_ball_run_moves_runner_without_teleporting() -> None:
    engine = SpatialMatchEngine(make_snapshot(seed=5514))
    carrier = engine.state.player_for_slot(TeamSide.HOME, "cm")
    engine.give_ball_to(carrier.agent_id)
    runs = engine.start_off_ball_runs(TeamSide.HOME, max_runners=1)
    assert len(runs) == 1
    runner = engine.state.agent(runs[0].runner_agent_id)
    start = runner.location
    target = runs[0].target

    engine.advance_ticks(4)

    assert runner.location != start
    assert runner.location.distance_to(target) < start.distance_to(target)
    assert runner.location.distance_to(start) < runs[0].speed_mps * 1.1


def test_dribble_requires_nearby_opponent() -> None:
    engine, attacker = _carry_engine(seed=5515)

    with pytest.raises(ValueError, match="no opponent is close enough"):
        engine.dribble_profile(attacker.agent_id)


def test_better_dribbler_has_higher_success_probability_against_same_defender() -> None:
    weak_snapshot = _with_dribble_attributes(
        make_snapshot(seed=5516), attacker_quality=35, defender_quality=70
    )
    strong_snapshot = _with_dribble_attributes(
        make_snapshot(seed=5516), attacker_quality=95, defender_quality=70
    )
    weak, weak_attacker, _ = _dribble_engine(snapshot=weak_snapshot)
    strong, strong_attacker, _ = _dribble_engine(snapshot=strong_snapshot)

    assert (
        strong.dribble_profile(strong_attacker.agent_id).success_probability
        > weak.dribble_profile(weak_attacker.agent_id).success_probability
    )


def test_same_seed_and_setup_produce_same_dribble_result() -> None:
    first, first_attacker, _ = _dribble_engine(seed=5517)
    second, second_attacker, _ = _dribble_engine(seed=5517)

    first_result = first.attempt_dribble(_decision(first_attacker, ActionType.DRIBBLE))
    second_result = second.attempt_dribble(_decision(second_attacker, ActionType.DRIBBLE))

    assert first_result == second_result
    assert first.state.signature() == second.state.signature()


def test_successful_dribble_starts_spatial_escape_carry_instead_of_teleporting() -> None:
    snapshot = _with_dribble_attributes(
        make_snapshot(seed=2), attacker_quality=95, defender_quality=25
    )
    engine, attacker, _ = _dribble_engine(snapshot=snapshot)
    start = attacker.location

    result = engine.attempt_dribble(_decision(attacker, ActionType.DRIBBLE))

    assert result.outcome is DribbleOutcome.BEATS_DEFENDER
    assert attacker.location == start
    assert engine.active_carry is not None
    engine.advance_ticks(4)
    assert attacker.location.x > start.x


def test_failed_dribble_can_transfer_control_to_defender() -> None:
    snapshot = _with_dribble_attributes(
        make_snapshot(seed=1), attacker_quality=25, defender_quality=95
    )
    engine, attacker, defender = _dribble_engine(snapshot=snapshot)

    result = engine.attempt_dribble(_decision(attacker, ActionType.DRIBBLE))

    assert result.outcome in {DribbleOutcome.DEFENDER_WINS, DribbleOutcome.LOOSE_BALL}
    if result.outcome is DribbleOutcome.DEFENDER_WINS:
        assert engine.state.ball.owner_agent_id == defender.agent_id
        assert engine.state.possession.team_side is TeamSide.AWAY
    else:
        assert engine.state.ball.owner_agent_id is None


def test_mixed_cross_near_byline_becomes_cutback() -> None:
    engine, crosser, striker = _cross_engine(seed=5518, byline=True)

    profile = engine.start_cross(_decision(crosser, ActionType.CROSS, striker)).profile

    assert profile.cross_type is CrossType.CUTBACK
    assert profile.max_height_m < 0.5


def test_explicit_high_cross_keeps_high_cross_type_and_height() -> None:
    snapshot = _with_player_instructions(
        make_snapshot(seed=5519),
        TeamSide.HOME,
        "rw",
        cross_type=CrossType.HIGH,
    )
    engine, crosser, striker = _cross_engine(snapshot=snapshot)

    profile = engine.start_cross(_decision(crosser, ActionType.CROSS, striker)).profile

    assert profile.cross_type is CrossType.HIGH
    assert profile.max_height_m >= 3.0


def test_high_cross_ball_has_nonzero_height_during_flight() -> None:
    snapshot = _with_player_instructions(
        make_snapshot(seed=5520),
        TeamSide.HOME,
        "rw",
        cross_type=CrossType.HIGH,
    )
    engine, crosser, striker = _cross_engine(snapshot=snapshot)
    engine.start_cross(_decision(crosser, ActionType.CROSS, striker))

    engine.step()

    assert engine.active_cross is not None
    assert engine.state.ball.height_m > 0.0


def test_open_cross_resolves_to_explicit_outcome_and_same_spatial_ball_state() -> None:
    engine, crosser, striker = _cross_engine(seed=5521)
    engine.start_cross(_decision(crosser, ActionType.CROSS, striker))

    result = engine.resolve_active_cross()

    assert result.outcome in {
        CrossOutcome.COMPLETED,
        CrossOutcome.INTERCEPTED,
        CrossOutcome.MISPLACED,
        CrossOutcome.BAD_CONTROL,
    }
    assert engine.active_cross is None
    assert engine.state.ball.height_m == 0.0


def test_defender_on_cross_path_can_intercept() -> None:
    snapshot = _with_player_instructions(
        make_snapshot(seed=1),
        TeamSide.HOME,
        "rw",
        cross_type=CrossType.LOW,
    )
    engine, crosser, striker = _cross_engine(snapshot=snapshot)
    blocker = engine.state.player_for_slot(TeamSide.AWAY, "cm")
    blocker.location = Vector2(84.0, 20.0)
    _freeze_all(engine)
    engine.start_cross(_decision(crosser, ActionType.CROSS, striker))

    result = engine.resolve_active_cross()

    assert result.outcome is CrossOutcome.INTERCEPTED
    assert result.interception_agent_id == blocker.agent_id
    assert engine.state.possession.team_side is TeamSide.AWAY


def test_pressure_reduces_cross_execution_quality() -> None:
    open_engine, open_crosser, open_striker = _cross_engine(seed=5522)
    pressured_engine, pressured_crosser, pressured_striker = _cross_engine(seed=5522)
    marker = pressured_engine.state.player_for_slot(TeamSide.AWAY, "cm")
    marker.location = pressured_crosser.location + Vector2(0.0, 2.0)
    _freeze_all(pressured_engine)

    open_profile = open_engine.start_cross(
        _decision(open_crosser, ActionType.CROSS, open_striker)
    ).profile
    pressured_profile = pressured_engine.start_cross(
        _decision(pressured_crosser, ActionType.CROSS, pressured_striker)
    ).profile

    assert pressured_profile.execution_quality < open_profile.execution_quality
    assert pressured_profile.target_error_m > open_profile.target_error_m


def test_same_seed_and_cross_setup_are_reproducible() -> None:
    first, first_crosser, first_striker = _cross_engine(seed=5523)
    second, second_crosser, second_striker = _cross_engine(seed=5523)

    first_active = first.start_cross(_decision(first_crosser, ActionType.CROSS, first_striker))
    second_active = second.start_cross(_decision(second_crosser, ActionType.CROSS, second_striker))
    first_result = first.resolve_active_cross()
    second_result = second.resolve_active_cross()

    assert first_active.profile == second_active.profile
    assert first_result == second_result
    assert first.state.signature() == second.state.signature()


def test_progressive_pass_leads_forward_runner_more_than_short_pass() -> None:
    snapshot = _with_player_instructions(
        make_snapshot(seed=5524),
        TeamSide.HOME,
        "rw",
        forward_runs=Level.VERY_HIGH,
        attack_space=Level.VERY_HIGH,
    )
    short = SpatialMatchEngine(snapshot)
    progressive = SpatialMatchEngine(snapshot)
    for engine in (short, progressive):
        _freeze_all(engine)
        passer = engine.state.player_for_slot(TeamSide.HOME, "cm")
        receiver = engine.state.player_for_slot(TeamSide.HOME, "rw")
        passer.location = Vector2(45.0, 34.0)
        receiver.location = Vector2(60.0, 20.0)
        for opponent in engine.state.away_players:
            opponent.location = Vector2(95.0, 62.0)
        engine.give_ball_to(passer.agent_id)
        _freeze_all(engine)
        engine.set_player_velocity(receiver.agent_id, Vector2(5.0, 0.0))

    short_passer = short.state.player_for_slot(TeamSide.HOME, "cm")
    short_receiver = short.state.player_for_slot(TeamSide.HOME, "rw")
    progressive_passer = progressive.state.player_for_slot(TeamSide.HOME, "cm")
    progressive_receiver = progressive.state.player_for_slot(TeamSide.HOME, "rw")

    short_profile = short.start_pass(
        _decision(short_passer, ActionType.SHORT_PASS, short_receiver)
    ).profile
    progressive_profile = progressive.start_pass(
        _decision(progressive_passer, ActionType.PROGRESSIVE_PASS, progressive_receiver)
    ).profile

    assert progressive_profile.intended_target.x > short_profile.intended_target.x
