from __future__ import annotations

from dataclasses import replace

import pytest

from football_manager.domain import (
    CompetitionContextSnapshot,
    CupTieContextSnapshot,
    MatchDecider,
)
from football_manager.simulation import (
    FlowConfig,
    MatchEndReason,
    MatchEventType,
    MatchFlowController,
    MatchPhase,
    RestartType,
    ShotBodyPart,
    ShotOutcome,
    ShotResult,
    TeamSide,
    Vector2,
)

from test_spatial_core import make_snapshot


def _flow_config(**changes) -> FlowConfig:
    base = FlowConfig(
        regulation_half_seconds=2.0,
        extra_time_half_seconds=1.0,
        decision_cooldown_seconds=0.5,
        loose_ball_collection_seconds=0.5,
        forced_loose_ball_collection_seconds=1.0,
        added_time_unit_seconds=1.0,
        regulation_added_time_cap_seconds=2.0,
        extra_time_added_time_cap_seconds=1.0,
        autonomous_actions=False,
        autonomous_tackles=False,
    )
    return replace(base, **changes)


def _with_decider(snapshot, decider: MatchDecider, *, cup_tie=None):
    competition = replace(
        snapshot.context.competition,
        match_decider=decider,
        cup_tie=cup_tie,
    )
    return replace(snapshot, context=replace(snapshot.context, competition=competition))


def test_match_decider_defaults_to_draw_allowed() -> None:
    competition = CompetitionContextSnapshot(
        competition_id="league",
        competition_name="League",
        season_label="2026",
        stage_label="Round 1",
    )

    assert competition.match_decider is MatchDecider.DRAW_ALLOWED


def test_match_decider_accepts_serialized_string_value() -> None:
    competition = CompetitionContextSnapshot(
        competition_id="cup",
        competition_name="Cup",
        season_label="2026",
        stage_label="Final",
        match_decider="extra_time_and_penalties",
    )

    assert competition.match_decider is MatchDecider.EXTRA_TIME_AND_PENALTIES


def test_start_places_kickoff_team_in_control_at_centre() -> None:
    flow = MatchFlowController(make_snapshot(seed=7001), config=_flow_config())

    flow.start()

    owner = flow.engine.state.agent(flow.engine.state.ball.owner_agent_id)
    assert flow.phase is MatchPhase.FIRST_HALF
    assert owner.side is flow.engine.state.kickoff_side
    assert flow.engine.state.ball.location == flow.engine.state.pitch.centre
    assert owner.location == flow.engine.state.pitch.centre


def test_second_half_kickoff_goes_to_opposite_initial_side() -> None:
    flow = MatchFlowController(make_snapshot(seed=7002), config=_flow_config())
    flow.start()
    first_side = flow.engine.state.kickoff_side

    while flow.phase is MatchPhase.FIRST_HALF:
        flow.step()
    assert flow.phase is MatchPhase.HALF_TIME

    flow.step()

    assert flow.phase is MatchPhase.SECOND_HALF
    assert flow.engine.state.possession.team_side is first_side.opponent


def test_league_draw_finishes_after_regulation() -> None:
    flow = MatchFlowController(make_snapshot(seed=7003), config=_flow_config())

    result = flow.run_to_completion()

    assert result.home_goals == result.away_goals == 0
    assert result.winner is None
    assert result.end_reason is MatchEndReason.DRAW
    assert flow.phase is MatchPhase.FINISHED


def test_added_time_extends_period_and_is_reported() -> None:
    flow = MatchFlowController(
        make_snapshot(seed=7004),
        config=_flow_config(regulation_added_time_cap_seconds=3.0),
    )
    flow.start()
    flow.record_stoppage(1.4)

    while flow.phase is MatchPhase.FIRST_HALF:
        flow.step()

    added = [event for event in flow.events if event.event_type is MatchEventType.ADDED_TIME]
    assert added
    assert added[0].value("seconds") == "2"
    assert flow.engine.state.clock.elapsed_seconds >= 4.0


def test_added_time_display_uses_45_plus_not_raw_elapsed_minutes() -> None:
    flow = MatchFlowController(
        make_snapshot(seed=7005),
        config=_flow_config(regulation_added_time_cap_seconds=2.0),
    )
    flow.start()
    flow.record_stoppage(1.0)

    while not any(event.event_type is MatchEventType.ADDED_TIME for event in flow.events):
        flow.step()
    flow.step()

    assert flow.time_label.startswith("45+")


def test_extra_time_is_used_when_knockout_tie_requires_winner() -> None:
    snapshot = _with_decider(
        make_snapshot(seed=7006),
        MatchDecider.EXTRA_TIME_AND_PENALTIES,
    )
    flow = MatchFlowController(snapshot, config=_flow_config())

    result = flow.run_to_completion()

    assert any(event.event_type is MatchEventType.EXTRA_TIME for event in result.events)
    assert result.end_reason is MatchEndReason.PENALTIES
    assert result.winner in {TeamSide.HOME, TeamSide.AWAY}


def test_direct_penalties_skip_extra_time() -> None:
    snapshot = _with_decider(
        make_snapshot(seed=7007),
        MatchDecider.PENALTIES_AFTER_90,
    )
    flow = MatchFlowController(snapshot, config=_flow_config())

    result = flow.run_to_completion()

    assert not any(event.event_type is MatchEventType.EXTRA_TIME for event in result.events)
    assert result.end_reason is MatchEndReason.PENALTIES


def test_aggregate_lead_ends_knockout_without_extra_time() -> None:
    tie = CupTieContextSnapshot(
        round_label="Semi-final",
        leg_number=2,
        home_aggregate_goals_before_match=2,
        away_aggregate_goals_before_match=1,
    )
    snapshot = _with_decider(
        make_snapshot(seed=7008),
        MatchDecider.EXTRA_TIME_AND_PENALTIES,
        cup_tie=tie,
    )
    flow = MatchFlowController(snapshot, config=_flow_config())

    result = flow.run_to_completion()

    assert result.aggregate_home_goals == 2
    assert result.aggregate_away_goals == 1
    assert result.winner is TeamSide.HOME
    assert result.end_reason is MatchEndReason.REGULATION
    assert not any(event.event_type is MatchEventType.EXTRA_TIME for event in result.events)


def test_penalty_shootout_is_seeded_and_reproducible() -> None:
    snapshot = _with_decider(
        make_snapshot(seed=7009),
        MatchDecider.PENALTIES_AFTER_90,
    )

    first = MatchFlowController(snapshot, config=_flow_config()).run_to_completion()
    second = MatchFlowController(snapshot, config=_flow_config()).run_to_completion()

    assert (first.penalties_home, first.penalties_away, first.winner) == (
        second.penalties_home,
        second.penalties_away,
        second.winner,
    )


def test_penalty_shootout_always_produces_a_winner() -> None:
    snapshot = _with_decider(
        make_snapshot(seed=7010),
        MatchDecider.PENALTIES_AFTER_90,
    )

    result = MatchFlowController(snapshot, config=_flow_config()).run_to_completion()

    assert result.penalties_home != result.penalties_away
    assert result.winner in {TeamSide.HOME, TeamSide.AWAY}


def test_throw_in_goes_to_opponent_of_last_touch() -> None:
    flow = MatchFlowController(make_snapshot(seed=7011), config=_flow_config())
    flow.start()
    last = flow.engine.state.player_for_slot(TeamSide.HOME, "rw")
    flow.engine.set_team_possession(TeamSide.HOME)
    flow.engine.state.ball.last_touch_agent_id = last.agent_id
    flow.engine.state.ball.location = Vector2(60.0, 0.0)

    flow.step()

    restart = [event for event in flow.events if event.restart_type is RestartType.THROW_IN]
    assert restart
    assert restart[-1].side is TeamSide.AWAY
    assert flow.engine.state.possession.team_side is TeamSide.AWAY


def test_attacker_last_touch_over_goal_line_becomes_goal_kick() -> None:
    flow = MatchFlowController(make_snapshot(seed=7012), config=_flow_config())
    flow.start()
    attacker = flow.engine.state.player_for_slot(TeamSide.HOME, "st")
    flow.engine.set_team_possession(TeamSide.HOME)
    flow.engine.state.ball.last_touch_agent_id = attacker.agent_id
    flow.engine.state.ball.location = Vector2(flow.engine.state.pitch.length_m, 30.0)

    flow.step()

    restart = [event for event in flow.events if event.restart_type is RestartType.GOAL_KICK]
    assert restart
    assert restart[-1].side is TeamSide.AWAY


def test_defender_last_touch_over_goal_line_becomes_corner() -> None:
    flow = MatchFlowController(make_snapshot(seed=7013), config=_flow_config())
    flow.start()
    defender = flow.engine.state.player_for_slot(TeamSide.AWAY, "rcb")
    flow.engine.set_team_possession(TeamSide.AWAY)
    flow.engine.state.ball.last_touch_agent_id = defender.agent_id
    flow.engine.state.ball.location = Vector2(flow.engine.state.pitch.length_m, 60.0)

    flow.step()

    restart = [event for event in flow.events if event.restart_type is RestartType.CORNER]
    assert restart
    assert restart[-1].side is TeamSide.HOME


def test_register_foul_awards_free_kick_to_fouled_team() -> None:
    flow = MatchFlowController(make_snapshot(seed=7014), config=_flow_config())
    flow.start()
    offender = flow.engine.state.player_for_slot(TeamSide.AWAY, "cm")
    victim = flow.engine.state.player_for_slot(TeamSide.HOME, "cm")

    flow.register_foul(offender.agent_id, victim.agent_id)

    assert flow.events[-2].event_type is MatchEventType.FOUL
    assert flow.events[-1].restart_type is RestartType.FREE_KICK
    assert flow.engine.state.possession.team_side is TeamSide.HOME


def test_register_foul_rejects_same_team_players() -> None:
    flow = MatchFlowController(make_snapshot(seed=7015), config=_flow_config())
    flow.start()
    first = flow.engine.state.player_for_slot(TeamSide.HOME, "cm")
    second = flow.engine.state.player_for_slot(TeamSide.HOME, "rcm")

    with pytest.raises(ValueError):
        flow.register_foul(first.agent_id, second.agent_id)


def test_goal_kick_is_controlled_by_goalkeeper() -> None:
    flow = MatchFlowController(make_snapshot(seed=7016), config=_flow_config())
    flow.start()

    controller_id = flow.award_restart(RestartType.GOAL_KICK, TeamSide.HOME)

    controller = flow.engine.state.agent(controller_id)
    assert controller.assigned_position.value == "GK"
    assert flow.engine.state.ball.owner_agent_id == controller.agent_id


def test_corner_places_ball_on_attacking_goal_line_corner() -> None:
    flow = MatchFlowController(make_snapshot(seed=7017), config=_flow_config())
    flow.start()

    flow.award_restart(
        RestartType.CORNER,
        TeamSide.HOME,
        location=Vector2(105.0, 60.0),
    )

    assert flow.engine.state.ball.location == Vector2(105.0, 68.0)


def test_loose_ball_is_recovered_after_bounded_delay() -> None:
    flow = MatchFlowController(make_snapshot(seed=7018), config=_flow_config())
    flow.start()
    flow.engine.set_team_possession(TeamSide.HOME)
    flow.engine.state.ball.location = Vector2(52.5, 34.0)

    for _ in range(5):
        flow.step()

    assert flow.engine.state.ball.owner_agent_id is not None
    assert any(event.event_type is MatchEventType.RECOVERY for event in flow.events)


def test_goal_result_updates_score_and_gives_kickoff_to_conceding_team() -> None:
    flow = MatchFlowController(make_snapshot(seed=7019), config=_flow_config())
    flow.start()
    shooter = flow.engine.state.player_for_slot(TeamSide.HOME, "st")
    goalkeeper = flow.engine.state.player_for_slot(TeamSide.AWAY, "gk")
    flow.engine.shooting.last_result = ShotResult(
        outcome=ShotOutcome.GOAL,
        shooter_agent_id=shooter.agent_id,
        goalkeeper_agent_id=goalkeeper.agent_id,
        body_part=ShotBodyPart.FOOT,
        chance_origin="open_play",
        started_tick=0,
        resolved_tick=flow.engine.state.clock.tick_count,
        xg=0.4,
        on_target=True,
        execution_quality=80.0,
        target_error_m=0.1,
    )

    flow._handle_resolved_actions()

    assert flow.score.home == 1
    assert flow.score.away == 0
    assert flow.engine.state.possession.team_side is TeamSide.AWAY
    assert any(event.event_type is MatchEventType.GOAL for event in flow.events)


def test_off_target_shot_awards_goal_kick() -> None:
    flow = MatchFlowController(make_snapshot(seed=7020), config=_flow_config())
    flow.start()
    shooter = flow.engine.state.player_for_slot(TeamSide.HOME, "st")
    goalkeeper = flow.engine.state.player_for_slot(TeamSide.AWAY, "gk")
    flow.engine.shooting.last_result = ShotResult(
        outcome=ShotOutcome.OFF_TARGET,
        shooter_agent_id=shooter.agent_id,
        goalkeeper_agent_id=goalkeeper.agent_id,
        body_part=ShotBodyPart.FOOT,
        chance_origin="open_play",
        started_tick=0,
        resolved_tick=flow.engine.state.clock.tick_count,
        xg=0.1,
        on_target=False,
        execution_quality=40.0,
        target_error_m=2.0,
    )

    flow._handle_resolved_actions()

    assert flow.events[-1].restart_type is RestartType.GOAL_KICK
    assert flow.events[-1].side is TeamSide.AWAY


def test_autonomous_short_match_finishes_without_manual_actions() -> None:
    config = _flow_config(
        regulation_half_seconds=3.0,
        autonomous_actions=True,
        autonomous_tackles=True,
    )
    flow = MatchFlowController(make_snapshot(seed=7021), config=config)

    result = flow.run_to_completion()

    assert result.match_id == flow.snapshot.match_id
    assert flow.is_finished
    assert len(result.events) > 4


def test_same_snapshot_seed_and_config_produce_same_full_flow_signature() -> None:
    snapshot = make_snapshot(seed=7022)
    config = _flow_config(regulation_half_seconds=3.0, autonomous_actions=True)

    first = MatchFlowController(snapshot, config=config).run_to_completion()
    second = MatchFlowController(snapshot, config=config).run_to_completion()

    first_signature = tuple(
        (event.time_label, event.event_type, event.side, event.actor_agent_id, event.data)
        for event in first.events
    )
    second_signature = tuple(
        (event.time_label, event.event_type, event.side, event.actor_agent_id, event.data)
        for event in second.events
    )
    assert (first.home_goals, first.away_goals, first_signature) == (
        second.home_goals,
        second.away_goals,
        second_signature,
    )


def test_event_stream_is_sequence_numbered_and_structured() -> None:
    flow = MatchFlowController(make_snapshot(seed=7023), config=_flow_config())
    result = flow.run_to_completion()

    assert result.events
    assert [event.sequence for event in result.events] == list(range(1, len(result.events) + 1))
    assert all(event.time_label for event in result.events)


def test_record_stoppage_rejects_negative_seconds() -> None:
    flow = MatchFlowController(make_snapshot(seed=7024), config=_flow_config())
    flow.start()

    with pytest.raises(ValueError):
        flow.record_stoppage(-1.0)
