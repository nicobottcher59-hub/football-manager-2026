from __future__ import annotations

from time import perf_counter

from football_manager.domain import MatchSnapshot
from football_manager.fast_simulation import FastMatchSimulator

from .models import FastCalibrationSample


def run_fast_calibration_match(
    snapshot: MatchSnapshot,
    *,
    scenario: str,
    seed: int,
    simulator: FastMatchSimulator | None = None,
) -> FastCalibrationSample:
    engine = simulator or FastMatchSimulator()
    started = perf_counter()
    result = engine.simulate(snapshot)
    elapsed = perf_counter() - started
    h = result.statistics_home
    a = result.statistics_away
    return FastCalibrationSample(
        scenario=scenario,
        seed=seed,
        elapsed_seconds=elapsed,
        home_goals=result.home_goals,
        away_goals=result.away_goals,
        home_shots=h.shots,
        away_shots=a.shots,
        home_shots_on_target=h.shots_on_target,
        away_shots_on_target=a.shots_on_target,
        home_xg=h.xg,
        away_xg=a.xg,
        home_possession_pct=h.possession_pct,
        away_possession_pct=a.possession_pct,
        home_passes_attempted=h.passes_attempted,
        away_passes_attempted=a.passes_attempted,
        home_passes_completed=h.passes_completed,
        away_passes_completed=a.passes_completed,
        home_fouls=h.fouls,
        away_fouls=a.fouls,
        home_yellow_cards=h.yellow_cards,
        away_yellow_cards=a.yellow_cards,
        home_red_cards=h.red_cards,
        away_red_cards=a.red_cards,
        home_corners=h.corners,
        away_corners=a.corners,
    )
