from __future__ import annotations

from time import perf_counter

from football_manager.domain import MatchSnapshot
from football_manager.presentation import MatchPlaybackSession
from football_manager.simulation import FlowConfig

from .audit import audit_match_events
from .metrics import CalibrationSample


def smoke_flow_config() -> FlowConfig:
    return FlowConfig(
        regulation_half_seconds=12.0,
        extra_time_half_seconds=4.0,
        decision_cooldown_seconds=0.5,
        loose_ball_collection_seconds=0.5,
        forced_loose_ball_collection_seconds=1.0,
        added_time_unit_seconds=1.0,
        regulation_added_time_cap_seconds=2.0,
        extra_time_added_time_cap_seconds=1.0,
    )


def run_calibration_match(
    snapshot: MatchSnapshot,
    *,
    scenario: str,
    seed: int,
    smoke: bool = False,
) -> CalibrationSample:
    session = MatchPlaybackSession(
        snapshot,
        flow_config=smoke_flow_config() if smoke else None,
    )
    started = perf_counter()
    session.run_instant(batch_ticks=1024)
    elapsed = perf_counter() - started

    result = session.result
    if result is None:
        raise RuntimeError("calibration match finished without a MatchResult")
    stats = session.stats
    audit = audit_match_events(
        result.events,
        home_goals=result.home_goals,
        away_goals=result.away_goals,
    )

    return CalibrationSample(
        scenario=scenario,
        seed=seed,
        elapsed_seconds=elapsed,
        home_goals=result.home_goals,
        away_goals=result.away_goals,
        home_shots=stats.home.shots,
        away_shots=stats.away.shots,
        home_shots_on_target=stats.home.shots_on_target,
        away_shots_on_target=stats.away.shots_on_target,
        home_xg=stats.home.xg,
        away_xg=stats.away.xg,
        home_possession_pct=stats.home.possession_pct,
        away_possession_pct=stats.away.possession_pct,
        home_passes_attempted=stats.home.passes_attempted,
        away_passes_attempted=stats.away.passes_attempted,
        home_passes_completed=stats.home.passes_completed,
        away_passes_completed=stats.away.passes_completed,
        home_fouls=stats.home.fouls,
        away_fouls=stats.away.fouls,
        home_yellow_cards=stats.home.yellow_cards,
        away_yellow_cards=stats.away.yellow_cards,
        home_red_cards=stats.home.red_cards,
        away_red_cards=stats.away.red_cards,
        home_corners=stats.home.corners,
        away_corners=stats.away.corners,
        event_integrity_issues=audit.integrity_issues,
        unresolved_shots=audit.unresolved_shots,
        orphan_shot_resolutions=audit.orphan_shot_resolutions,
        score_goal_delta=audit.score_goal_delta,
        home_tackles=stats.home.tackles,
        away_tackles=stats.away.tackles,
        home_successful_tackles=stats.home.successful_tackles,
        away_successful_tackles=stats.away.successful_tackles,
        home_recoveries=stats.home.recoveries,
        away_recoveries=stats.away.recoveries,
        home_dribbles=stats.home.dribbles,
        away_dribbles=stats.away.dribbles,
        home_crosses=stats.home.crosses,
        away_crosses=stats.away.crosses,
        home_completed_crosses=stats.home.completed_crosses,
        away_completed_crosses=stats.away.completed_crosses,
    )
