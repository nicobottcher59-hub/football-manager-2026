from __future__ import annotations

from dataclasses import asdict, dataclass
from statistics import fmean
from typing import Iterable

from .metrics import CalibrationSample


@dataclass(frozen=True, slots=True)
class StrengthCurvePoint:
    scenario: str
    strength_gap: int
    matches: int
    home_points_per_match: float
    home_goal_diff_per_match: float
    home_xg_diff_per_match: float
    home_xg_share_pct: float
    home_win_pct: float
    draw_pct: float
    away_win_pct: float
    underdog_win_pct: float | None
    favorite_non_win_pct: float | None

    def to_row(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class StrengthCurveDiagnostics:
    points: int
    ppg_slope_per_10_points: float
    xg_diff_slope_per_10_points: float
    ppg_monotonic_violations: int
    xg_monotonic_violations: int
    largest_adjacent_ppg_jump: float
    largest_adjacent_xg_jump: float

    def to_row(self) -> dict[str, object]:
        return asdict(self)


def summarize_strength_point(
    samples: Iterable[CalibrationSample],
    *,
    strength_gap: int,
) -> StrengthCurvePoint:
    items = tuple(samples)
    if not items:
        raise ValueError("cannot summarize an empty strength sample set")
    scenarios = {item.scenario for item in items}
    if len(scenarios) != 1:
        raise ValueError("strength samples must share one scenario")

    matches = len(items)
    home_wins = sum(item.home_goals > item.away_goals for item in items)
    draws = sum(item.home_goals == item.away_goals for item in items)
    away_wins = matches - home_wins - draws
    home_xg = sum(item.home_xg for item in items)
    away_xg = sum(item.away_xg for item in items)
    total_xg = home_xg + away_xg

    if strength_gap > 0:
        underdog_wins = away_wins
        favorite_non_wins = away_wins + draws
    elif strength_gap < 0:
        underdog_wins = home_wins
        favorite_non_wins = home_wins + draws
    else:
        underdog_wins = None
        favorite_non_wins = None

    return StrengthCurvePoint(
        scenario=items[0].scenario,
        strength_gap=strength_gap,
        matches=matches,
        home_points_per_match=(home_wins * 3 + draws) / matches,
        home_goal_diff_per_match=fmean(item.home_goals - item.away_goals for item in items),
        home_xg_diff_per_match=fmean(item.home_xg - item.away_xg for item in items),
        home_xg_share_pct=(home_xg / total_xg * 100.0 if total_xg > 0.0 else 50.0),
        home_win_pct=home_wins / matches * 100.0,
        draw_pct=draws / matches * 100.0,
        away_win_pct=away_wins / matches * 100.0,
        underdog_win_pct=(underdog_wins / matches * 100.0 if underdog_wins is not None else None),
        favorite_non_win_pct=(
            favorite_non_wins / matches * 100.0 if favorite_non_wins is not None else None
        ),
    )


def _linear_slope(points: tuple[StrengthCurvePoint, ...], attr: str) -> float:
    xs = tuple(float(item.strength_gap) for item in points)
    ys = tuple(float(getattr(item, attr)) for item in points)
    x_mean = fmean(xs)
    y_mean = fmean(ys)
    denom = sum((x - x_mean) ** 2 for x in xs)
    if denom <= 0.0:
        return 0.0
    slope_per_point = sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, ys, strict=True)) / denom
    return slope_per_point * 10.0


def diagnose_strength_curve(
    points: Iterable[StrengthCurvePoint],
) -> StrengthCurveDiagnostics:
    ordered = tuple(sorted(points, key=lambda item: item.strength_gap))
    if len(ordered) < 2:
        raise ValueError("strength curve diagnostics require at least two points")

    ppg_violations = 0
    xg_violations = 0
    ppg_jumps: list[float] = []
    xg_jumps: list[float] = []
    for left, right in zip(ordered, ordered[1:]):
        ppg_delta = right.home_points_per_match - left.home_points_per_match
        xg_delta = right.home_xg_diff_per_match - left.home_xg_diff_per_match
        if ppg_delta < 0.0:
            ppg_violations += 1
        if xg_delta < 0.0:
            xg_violations += 1
        ppg_jumps.append(abs(ppg_delta))
        xg_jumps.append(abs(xg_delta))

    return StrengthCurveDiagnostics(
        points=len(ordered),
        ppg_slope_per_10_points=_linear_slope(ordered, "home_points_per_match"),
        xg_diff_slope_per_10_points=_linear_slope(ordered, "home_xg_diff_per_match"),
        ppg_monotonic_violations=ppg_violations,
        xg_monotonic_violations=xg_violations,
        largest_adjacent_ppg_jump=max(ppg_jumps, default=0.0),
        largest_adjacent_xg_jump=max(xg_jumps, default=0.0),
    )
