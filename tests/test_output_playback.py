from __future__ import annotations

from dataclasses import replace

import pytest

from football_manager.presentation import (
    CommentaryDensity,
    CommentaryFormatter,
    MatchPlaybackSession,
    MatchStatisticsTracker,
    PlaybackSpeed,
)
from football_manager.presentation.debug_viewer import PitchProjector, convex_hull
from football_manager.simulation import (
    FlowConfig,
    MatchEvent,
    MatchEventType,
    MatchPhase,
    MatchScore,
    RestartType,
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
        regulation_added_time_cap_seconds=1.0,
        extra_time_added_time_cap_seconds=1.0,
        autonomous_actions=True,
        autonomous_tackles=True,
    )
    return replace(base, **changes)


def _event(
    sequence: int,
    event_type: MatchEventType,
    *,
    side: TeamSide | None = None,
    actor: str | None = None,
    secondary: str | None = None,
    restart_type: RestartType | None = None,
    data: tuple[tuple[str, str], ...] = (),
) -> MatchEvent:
    return MatchEvent(
        sequence=sequence,
        tick=sequence,
        time_label="12'",
        phase=MatchPhase.FIRST_HALF,
        event_type=event_type,
        side=side,
        actor_agent_id=actor,
        secondary_agent_id=secondary,
        restart_type=restart_type,
        data=data,
    )


def _result_signature(session: MatchPlaybackSession):
    result = session.result
    assert result is not None
    return (
        result.home_goals,
        result.away_goals,
        result.penalties_home,
        result.penalties_away,
        result.winner,
        result.end_reason,
        tuple(
            (
                event.time_label,
                event.event_type,
                event.side,
                event.actor_agent_id,
                event.secondary_agent_id,
                event.restart_type,
                event.data,
            )
            for event in result.events
        ),
    )


def test_playback_speed_values_are_relative_multipliers() -> None:
    assert int(PlaybackSpeed.X1) == 1
    assert int(PlaybackSpeed.X2) == 2
    assert int(PlaybackSpeed.X4) == 4


def test_advance_pulse_uses_speed_only_as_tick_batch_size() -> None:
    snapshot = make_snapshot(seed=5901)
    x1 = MatchPlaybackSession(snapshot, flow_config=_flow_config(autonomous_actions=False))
    x4 = MatchPlaybackSession(snapshot, flow_config=_flow_config(autonomous_actions=False))
    x4.set_speed(PlaybackSpeed.X4)

    a = x1.advance_pulse(base_ticks=1)
    b = x4.advance_pulse(base_ticks=1)

    assert a.ticks_advanced == 1
    assert b.ticks_advanced == 4
    assert x1.flow.engine.timestep_seconds == x4.flow.engine.timestep_seconds == 0.25


def test_negative_playback_ticks_are_rejected() -> None:
    session = MatchPlaybackSession(make_snapshot(), flow_config=_flow_config())
    with pytest.raises(ValueError, match="non-negative"):
        session.advance_ticks(-1)


def test_zero_playback_ticks_do_not_mutate_match() -> None:
    session = MatchPlaybackSession(make_snapshot(), flow_config=_flow_config())
    before = session.flow.engine.state.signature()

    advance = session.advance_ticks(0)

    assert advance.ticks_advanced == 0
    assert advance.events == ()
    assert session.flow.engine.state.signature() == before


def test_x1_x2_x4_and_instant_produce_identical_match() -> None:
    snapshot = make_snapshot(seed=5920)
    config = _flow_config()
    sessions = []
    for speed in (PlaybackSpeed.X1, PlaybackSpeed.X2, PlaybackSpeed.X4):
        session = MatchPlaybackSession(snapshot, flow_config=config)
        session.set_speed(speed)
        while not session.is_finished:
            session.advance_pulse(base_ticks=1)
        sessions.append(session)

    instant = MatchPlaybackSession(snapshot, flow_config=config)
    instant.run_instant(batch_ticks=64)
    sessions.append(instant)

    signatures = [_result_signature(session) for session in sessions]
    assert signatures[1:] == [signatures[0], signatures[0], signatures[0]]


def test_playback_statistics_are_identical_across_batch_sizes() -> None:
    snapshot = make_snapshot(seed=5930)
    config = _flow_config()
    one = MatchPlaybackSession(snapshot, flow_config=config)
    four = MatchPlaybackSession(snapshot, flow_config=config)

    while not one.is_finished:
        one.advance_ticks(1)
    while not four.is_finished:
        four.advance_ticks(4)

    assert one.stats == four.stats


def test_statistics_tracker_counts_pass_attempt_and_completion() -> None:
    snapshot = make_snapshot()
    tracker = MatchStatisticsTracker(snapshot)
    home_cm = "home:home-cm"
    home_lcm = "home:home-lcm"

    tracker.consume(
        [
            _event(1, MatchEventType.PASS, actor=home_cm, secondary=home_lcm, data=(("status", "attempt"),)),
            _event(2, MatchEventType.PASS, actor=home_cm, secondary=home_lcm, data=(("outcome", "completed"),)),
        ]
    )

    stats = tracker.snapshot()
    assert stats.home.passes_attempted == 1
    assert stats.home.passes_completed == 1
    assert stats.away.passes_attempted == 0


def test_statistics_tracker_builds_possession_percentage_from_ticks() -> None:
    tracker = MatchStatisticsTracker(make_snapshot())
    tracker.observe_possession(TeamSide.HOME, 3)
    tracker.observe_possession(TeamSide.AWAY, 1)

    stats = tracker.snapshot()
    assert stats.home.possession_pct == pytest.approx(75.0)
    assert stats.away.possession_pct == pytest.approx(25.0)


def test_statistics_tracker_counts_shot_xg_and_goal_without_double_counting_shot() -> None:
    tracker = MatchStatisticsTracker(make_snapshot())
    striker = "home:home-st"
    tracker.consume(
        [
            _event(1, MatchEventType.SHOT, side=TeamSide.HOME, actor=striker, data=(("xg", "0.325"),)),
            _event(2, MatchEventType.GOAL, side=TeamSide.HOME, actor=striker, data=(("xg", "0.325"),)),
        ]
    )

    stats = tracker.snapshot(MatchScore(home=1, away=0))
    assert stats.home.shots == 1
    assert stats.home.shots_on_target == 1
    assert stats.home.xg == pytest.approx(0.325)
    assert stats.home.goals == 1


def test_in_match_penalty_counts_as_shot_but_shootout_kick_does_not() -> None:
    tracker = MatchStatisticsTracker(make_snapshot())
    tracker.consume(
        [
            _event(
                1,
                MatchEventType.PENALTY_KICK,
                side=TeamSide.HOME,
                actor="home:home-st",
                data=(("probability", "0.76"), ("shootout", "false"), ("scored", "true")),
            ),
            _event(
                2,
                MatchEventType.PENALTY_KICK,
                side=TeamSide.HOME,
                actor="home:home-st",
                data=(("probability", "0.76"), ("shootout", "true"), ("scored", "true")),
            ),
        ]
    )

    stats = tracker.snapshot()
    assert stats.home.shots == 1
    assert stats.home.shots_on_target == 1
    assert stats.home.xg == pytest.approx(0.76)


def test_statistics_tracker_counts_cards_fouls_and_corners_for_correct_side() -> None:
    tracker = MatchStatisticsTracker(make_snapshot())
    away_cm = "away:away-cm"
    tracker.consume(
        [
            _event(1, MatchEventType.FOUL, side=TeamSide.HOME, actor=away_cm),
            _event(2, MatchEventType.CARD, side=TeamSide.AWAY, actor=away_cm, data=(("card", "yellow"),)),
            _event(3, MatchEventType.RESTART, side=TeamSide.HOME, restart_type=RestartType.CORNER),
        ]
    )

    stats = tracker.snapshot()
    assert stats.away.fouls == 1
    assert stats.away.yellow_cards == 1
    assert stats.home.corners == 1


def test_commentary_always_surfaces_goal_with_time_and_xg() -> None:
    formatter = CommentaryFormatter(make_snapshot(), density=CommentaryDensity.HIGHLIGHTS)
    event = _event(
        1,
        MatchEventType.GOAL,
        side=TeamSide.HOME,
        actor="home:home-st",
        data=(("xg", "0.325"),),
    )

    text = formatter.format_event(event)

    assert text is not None
    assert "12'" in text
    assert "GOOOOO" in text
    assert "0.33" in text


def test_commentary_highlights_hide_routine_completed_pass() -> None:
    formatter = CommentaryFormatter(make_snapshot(), density=CommentaryDensity.HIGHLIGHTS)
    formatter.format_event(
        _event(
            1,
            MatchEventType.PASS,
            actor="home:home-cm",
            secondary="home:home-lcm",
            data=(("status", "attempt"), ("action", "short_pass")),
        )
    )
    resolved = _event(
        2,
        MatchEventType.PASS,
        actor="home:home-cm",
        secondary="home:home-lcm",
        data=(("outcome", "completed"),),
    )

    assert formatter.format_event(resolved) is None


def test_commentary_detailed_surfaces_sampled_routine_passes() -> None:
    formatter = CommentaryFormatter(make_snapshot(), density=CommentaryDensity.DETAILED)
    formatter.format_event(
        _event(
            3,
            MatchEventType.PASS,
            actor="home:home-cm",
            secondary="home:home-lcm",
            data=(("status", "attempt"), ("action", "short_pass")),
        )
    )
    resolved = _event(
        4,
        MatchEventType.PASS,
        actor="home:home-cm",
        secondary="home:home-lcm",
        data=(("outcome", "completed"),),
    )

    text = formatter.format_event(resolved)
    assert text is not None
    assert "HOME CM" in text
    assert "HOME LCM" in text


def test_commentary_highlights_surface_sampled_interceptions() -> None:
    formatter = CommentaryFormatter(make_snapshot(), density=CommentaryDensity.HIGHLIGHTS)
    formatter.format_event(
        _event(
            1,
            MatchEventType.PASS,
            actor="home:home-cm",
            secondary="home:home-st",
            data=(("status", "attempt"), ("action", "progressive_pass")),
        )
    )
    text = formatter.format_event(
        _event(
            8,
            MatchEventType.PASS,
            actor="home:home-cm",
            secondary="away:away-cm",
            data=(("outcome", "intercepted"),),
        )
    )

    assert text is not None
    assert "intercepta" in text


def test_commentary_can_switch_density_without_touching_simulation() -> None:
    formatter = CommentaryFormatter(make_snapshot(), density=CommentaryDensity.NORMAL)
    formatter.set_density(CommentaryDensity.DETAILED)
    assert formatter.density is CommentaryDensity.DETAILED


def test_pitch_projector_maps_pitch_corners_and_centre() -> None:
    projector = PitchProjector(1100, 740, margin_px=50)

    assert projector.to_canvas(100, 64, Vector2(0, 0)) == pytest.approx((50, 50))
    assert projector.to_canvas(100, 64, Vector2(100, 64)) == pytest.approx((1050, 690))
    assert projector.to_canvas(100, 64, Vector2(50, 32)) == pytest.approx((550, 370))


def test_convex_hull_wraps_team_shape_and_discards_inner_points() -> None:
    points = [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0), (5.0, 5.0)]
    hull = convex_hull(points)

    assert len(hull) == 4
    assert (5.0, 5.0) not in hull


def test_flow_shot_event_exposes_xg_for_presentation(monkeypatch) -> None:
    session = MatchPlaybackSession(
        make_snapshot(seed=5999),
        flow_config=_flow_config(autonomous_actions=False),
    )
    flow = session.flow
    flow.start()
    shooter = flow.engine.state.player_for_slot(TeamSide.HOME, "st")
    flow.engine.give_ball_to(shooter.agent_id)

    from football_manager.simulation import ActionType, PlayerDecision

    decision = PlayerDecision(
        agent_id=shooter.agent_id,
        action_type=ActionType.SHOOT,
        target_agent_id=None,
        utility=80.0,
        considered_options=(),
    )
    flow._execute_decision(decision)

    shot = [event for event in flow.events if event.event_type is MatchEventType.SHOT][-1]
    assert shot.side is TeamSide.HOME
    assert float(shot.value("xg")) > 0.0
    assert shot.value("body_part") == "foot"
