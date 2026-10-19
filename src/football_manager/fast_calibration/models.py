from __future__ import annotations

from dataclasses import asdict, dataclass
from statistics import fmean
from typing import Iterable


@dataclass(frozen=True, slots=True)
class FastCalibrationSample:
    scenario: str
    seed: int
    elapsed_seconds: float
    home_goals: int
    away_goals: int
    home_shots: int
    away_shots: int
    home_shots_on_target: int
    away_shots_on_target: int
    home_xg: float
    away_xg: float
    home_possession_pct: float
    away_possession_pct: float
    home_passes_attempted: int
    away_passes_attempted: int
    home_passes_completed: int
    away_passes_completed: int
    home_fouls: int
    away_fouls: int
    home_yellow_cards: int
    away_yellow_cards: int
    home_red_cards: int
    away_red_cards: int
    home_corners: int
    away_corners: int

    @property
    def total_goals(self) -> int:
        return self.home_goals + self.away_goals

    @property
    def total_shots(self) -> int:
        return self.home_shots + self.away_shots

    @property
    def total_shots_on_target(self) -> int:
        return self.home_shots_on_target + self.away_shots_on_target

    @property
    def total_xg(self) -> float:
        return self.home_xg + self.away_xg

    @property
    def total_fouls(self) -> int:
        return self.home_fouls + self.away_fouls

    @property
    def total_yellow_cards(self) -> int:
        return self.home_yellow_cards + self.away_yellow_cards

    @property
    def total_red_cards(self) -> int:
        return self.home_red_cards + self.away_red_cards

    @property
    def total_corners(self) -> int:
        return self.home_corners + self.away_corners

    @property
    def total_passes_attempted(self) -> int:
        return self.home_passes_attempted + self.away_passes_attempted

    @property
    def total_passes_completed(self) -> int:
        return self.home_passes_completed + self.away_passes_completed

    @property
    def pass_completion_pct(self) -> float:
        if self.total_passes_attempted <= 0:
            return 0.0
        return self.total_passes_completed / self.total_passes_attempted * 100.0

    @property
    def outcome(self) -> str:
        if self.home_goals > self.away_goals:
            return "home"
        if self.home_goals < self.away_goals:
            return "away"
        return "draw"

    @property
    def home_points(self) -> int:
        if self.outcome == "home":
            return 3
        if self.outcome == "draw":
            return 1
        return 0

    def to_row(self) -> dict[str, object]:
        row = asdict(self)
        row.update(
            total_goals=self.total_goals,
            total_shots=self.total_shots,
            total_shots_on_target=self.total_shots_on_target,
            total_xg=round(self.total_xg, 6),
            total_fouls=self.total_fouls,
            total_yellow_cards=self.total_yellow_cards,
            total_red_cards=self.total_red_cards,
            total_corners=self.total_corners,
            pass_completion_pct=round(self.pass_completion_pct, 6),
            outcome=self.outcome,
        )
        return row


@dataclass(frozen=True, slots=True)
class FastCalibrationSummary:
    scenario: str
    matches: int
    matches_per_second: float
    goals_per_match: float
    shots_per_match: float
    shots_on_target_per_match: float
    xg_per_match: float
    goals_minus_xg_per_match: float
    goals_per_xg: float
    shot_conversion_pct: float
    pass_completion_pct: float
    fouls_per_match: float
    yellow_cards_per_match: float
    red_cards_per_match: float
    corners_per_match: float
    home_possession_pct: float
    home_win_pct: float
    draw_pct: float
    away_win_pct: float
    home_points_per_match: float
    home_goal_diff_per_match: float
    home_xg_diff_per_match: float
    home_xg_share_pct: float
    scoreless_pct: float
    both_teams_score_pct: float
    four_plus_goals_pct: float
    margin_three_plus_pct: float
    shot_diff_10plus_pct: float
    xg_diff_1plus_pct: float
    possession_60plus_pct: float

    def to_row(self) -> dict[str, object]:
        return asdict(self)


def summarize_fast_samples(samples: Iterable[FastCalibrationSample]) -> FastCalibrationSummary:
    items = tuple(samples)
    if not items:
        raise ValueError("cannot summarize an empty fast-calibration sample set")
    scenarios = {item.scenario for item in items}
    if len(scenarios) != 1:
        raise ValueError("all samples in one summary must share the same scenario")

    matches = len(items)
    elapsed = sum(item.elapsed_seconds for item in items)
    total_goals = sum(item.total_goals for item in items)
    total_shots = sum(item.total_shots for item in items)
    total_xg = sum(item.total_xg for item in items)
    attempted = sum(item.total_passes_attempted for item in items)
    completed = sum(item.total_passes_completed for item in items)
    home_wins = sum(item.outcome == "home" for item in items)
    draws = sum(item.outcome == "draw" for item in items)
    away_wins = matches - home_wins - draws
    home_xg = sum(item.home_xg for item in items)
    away_xg = sum(item.away_xg for item in items)
    xg_total = home_xg + away_xg

    return FastCalibrationSummary(
        scenario=items[0].scenario,
        matches=matches,
        matches_per_second=(matches / elapsed if elapsed > 0.0 else float("inf")),
        goals_per_match=total_goals / matches,
        shots_per_match=total_shots / matches,
        shots_on_target_per_match=sum(item.total_shots_on_target for item in items) / matches,
        xg_per_match=total_xg / matches,
        goals_minus_xg_per_match=(total_goals - total_xg) / matches,
        goals_per_xg=(total_goals / total_xg if total_xg > 0.0 else 0.0),
        shot_conversion_pct=(total_goals / total_shots * 100.0 if total_shots else 0.0),
        pass_completion_pct=(completed / attempted * 100.0 if attempted else 0.0),
        fouls_per_match=sum(item.total_fouls for item in items) / matches,
        yellow_cards_per_match=sum(item.total_yellow_cards for item in items) / matches,
        red_cards_per_match=sum(item.total_red_cards for item in items) / matches,
        corners_per_match=sum(item.total_corners for item in items) / matches,
        home_possession_pct=fmean(item.home_possession_pct for item in items),
        home_win_pct=home_wins / matches * 100.0,
        draw_pct=draws / matches * 100.0,
        away_win_pct=away_wins / matches * 100.0,
        home_points_per_match=sum(item.home_points for item in items) / matches,
        home_goal_diff_per_match=sum(item.home_goals - item.away_goals for item in items) / matches,
        home_xg_diff_per_match=sum(item.home_xg - item.away_xg for item in items) / matches,
        home_xg_share_pct=(home_xg / xg_total * 100.0 if xg_total > 0.0 else 50.0),
        scoreless_pct=sum(item.total_goals == 0 for item in items) / matches * 100.0,
        both_teams_score_pct=sum(item.home_goals > 0 and item.away_goals > 0 for item in items) / matches * 100.0,
        four_plus_goals_pct=sum(item.total_goals >= 4 for item in items) / matches * 100.0,
        margin_three_plus_pct=sum(abs(item.home_goals - item.away_goals) >= 3 for item in items) / matches * 100.0,
        shot_diff_10plus_pct=sum(abs(item.home_shots - item.away_shots) >= 10 for item in items) / matches * 100.0,
        xg_diff_1plus_pct=sum(abs(item.home_xg - item.away_xg) >= 1.0 for item in items) / matches * 100.0,
        possession_60plus_pct=sum(max(item.home_possession_pct, item.away_possession_pct) >= 60.0 for item in items) / matches * 100.0,
    )


@dataclass(frozen=True, slots=True)
class FastMetricTarget:
    key: str
    label: str
    low: float
    high: float
    unit: str = ""

    def status(self, value: float) -> str:
        if value < self.low:
            return "LOW"
        if value > self.high:
            return "HIGH"
        return "OK"


@dataclass(frozen=True, slots=True)
class FastTargetEvaluation:
    key: str
    label: str
    value: float
    low: float
    high: float
    unit: str
    status: str


DEFAULT_FAST_NEUTRAL_TARGETS: tuple[FastMetricTarget, ...] = (
    FastMetricTarget("goals_per_match", "Goals", 2.45, 3.00),
    FastMetricTarget("shots_per_match", "Total shots", 22.0, 28.0),
    FastMetricTarget("shots_on_target_per_match", "Shots on target", 7.5, 10.0),
    FastMetricTarget("xg_per_match", "xG", 2.45, 3.00),
    FastMetricTarget("goals_minus_xg_per_match", "Goals - xG", -0.20, 0.20),
    FastMetricTarget("pass_completion_pct", "Pass completion", 80.0, 86.0, "%"),
    FastMetricTarget("fouls_per_match", "Fouls", 20.0, 27.0),
    FastMetricTarget("yellow_cards_per_match", "Yellow cards", 3.2, 4.5),
    FastMetricTarget("corners_per_match", "Corners", 8.0, 11.5),
    FastMetricTarget("home_win_pct", "Home wins", 36.0, 46.0, "%"),
    FastMetricTarget("draw_pct", "Draws", 19.0, 29.0, "%"),
    FastMetricTarget("away_win_pct", "Away wins", 29.0, 40.0, "%"),
)


def evaluate_fast_targets(
    summary: FastCalibrationSummary,
    targets: tuple[FastMetricTarget, ...] = DEFAULT_FAST_NEUTRAL_TARGETS,
) -> tuple[FastTargetEvaluation, ...]:
    return tuple(
        FastTargetEvaluation(
            key=target.key,
            label=target.label,
            value=float(getattr(summary, target.key)),
            low=target.low,
            high=target.high,
            unit=target.unit,
            status=target.status(float(getattr(summary, target.key))),
        )
        for target in targets
    )


@dataclass(frozen=True, slots=True)
class FastCurvePoint:
    value: float
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


@dataclass(frozen=True, slots=True)
class FastCurveDiagnostics:
    ppg_slope_per_10: float
    xg_diff_slope_per_10: float
    ppg_monotonic_violations: int
    xg_monotonic_violations: int
    largest_adjacent_ppg_jump: float
    largest_adjacent_xg_jump: float


def summarize_curve_point(
    samples: Iterable[FastCalibrationSample],
    *,
    value: float,
    favorite_gap: float | None = None,
) -> FastCurvePoint:
    summary = summarize_fast_samples(samples)
    underdog_win: float | None
    favorite_non_win: float | None
    resolved_gap = value if favorite_gap is None else favorite_gap
    if resolved_gap > 0:
        underdog_win = summary.away_win_pct
        favorite_non_win = 100.0 - summary.home_win_pct
    elif resolved_gap < 0:
        underdog_win = summary.home_win_pct
        favorite_non_win = 100.0 - summary.away_win_pct
    else:
        underdog_win = None
        favorite_non_win = None
    return FastCurvePoint(
        value=value,
        matches=summary.matches,
        home_points_per_match=summary.home_points_per_match,
        home_goal_diff_per_match=summary.home_goal_diff_per_match,
        home_xg_diff_per_match=summary.home_xg_diff_per_match,
        home_xg_share_pct=summary.home_xg_share_pct,
        home_win_pct=summary.home_win_pct,
        draw_pct=summary.draw_pct,
        away_win_pct=summary.away_win_pct,
        underdog_win_pct=underdog_win,
        favorite_non_win_pct=favorite_non_win,
    )


def _linear_slope(xs: list[float], ys: list[float]) -> float:
    x_mean = fmean(xs)
    y_mean = fmean(ys)
    denominator = sum((x - x_mean) ** 2 for x in xs)
    if denominator <= 0.0:
        return 0.0
    return sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, ys, strict=True)) / denominator


def diagnose_curve(points: Iterable[FastCurvePoint]) -> FastCurveDiagnostics:
    items = tuple(sorted(points, key=lambda item: item.value))
    if len(items) < 2:
        raise ValueError("curve diagnostics require at least two points")
    ppg = [item.home_points_per_match for item in items]
    xgd = [item.home_xg_diff_per_match for item in items]
    xs = [item.value for item in items]
    return FastCurveDiagnostics(
        ppg_slope_per_10=_linear_slope(xs, ppg) * 10.0,
        xg_diff_slope_per_10=_linear_slope(xs, xgd) * 10.0,
        ppg_monotonic_violations=sum(right < left for left, right in zip(ppg, ppg[1:])),
        xg_monotonic_violations=sum(right < left for left, right in zip(xgd, xgd[1:])),
        largest_adjacent_ppg_jump=max(abs(right - left) for left, right in zip(ppg, ppg[1:])),
        largest_adjacent_xg_jump=max(abs(right - left) for left, right in zip(xgd, xgd[1:])),
    )


@dataclass(frozen=True, slots=True)
class FastExecutionPoint:
    score: float
    matches: int
    home_points_per_match: float
    home_possession_pct: float
    home_pass_completion_pct: float
    home_shots_per_match: float
    home_xg_per_match: float
    home_fouls_per_match: float
    home_corners_per_match: float
    away_pass_completion_pct: float


def summarize_execution_point(
    samples: Iterable[FastCalibrationSample],
    *,
    score: float,
) -> FastExecutionPoint:
    items = tuple(samples)
    summary = summarize_fast_samples(items)
    home_attempted = sum(item.home_passes_attempted for item in items)
    home_completed = sum(item.home_passes_completed for item in items)
    away_attempted = sum(item.away_passes_attempted for item in items)
    away_completed = sum(item.away_passes_completed for item in items)
    return FastExecutionPoint(
        score=score,
        matches=summary.matches,
        home_points_per_match=summary.home_points_per_match,
        home_possession_pct=summary.home_possession_pct,
        home_pass_completion_pct=(home_completed / home_attempted * 100.0 if home_attempted else 0.0),
        home_shots_per_match=sum(item.home_shots for item in items) / summary.matches,
        home_xg_per_match=sum(item.home_xg for item in items) / summary.matches,
        home_fouls_per_match=sum(item.home_fouls for item in items) / summary.matches,
        home_corners_per_match=sum(item.home_corners for item in items) / summary.matches,
        away_pass_completion_pct=(away_completed / away_attempted * 100.0 if away_attempted else 0.0),
    )


@dataclass(frozen=True, slots=True)
class FastTacticalDelta:
    name: str
    matches_per_variant: int
    home_points_delta: float
    home_possession_pp_delta: float
    home_pass_completion_pp_delta: float
    home_shots_delta: float
    home_xg_delta: float
    home_fouls_delta: float
    home_corners_delta: float
    away_pass_completion_pp_delta: float


def summarize_tactical_delta(
    control: Iterable[FastCalibrationSample],
    treatment: Iterable[FastCalibrationSample],
    *,
    name: str,
) -> FastTacticalDelta:
    c_items = tuple(control)
    t_items = tuple(treatment)
    c = summarize_fast_samples(c_items)
    t = summarize_fast_samples(t_items)
    if c.matches != t.matches:
        raise ValueError("paired tactical summaries require equal sample sizes")

    def home_pass_pct(items: Iterable[FastCalibrationSample]) -> float:
        rows = tuple(items)
        attempted = sum(item.home_passes_attempted for item in rows)
        completed = sum(item.home_passes_completed for item in rows)
        return completed / attempted * 100.0 if attempted else 0.0

    c_home_pass = home_pass_pct(c_items)
    t_home_pass = home_pass_pct(t_items)
    c_away_pass = (
        sum(item.away_passes_completed for item in c_items)
        / sum(item.away_passes_attempted for item in c_items)
        * 100.0
    )
    t_away_pass = (
        sum(item.away_passes_completed for item in t_items)
        / sum(item.away_passes_attempted for item in t_items)
        * 100.0
    )
    return FastTacticalDelta(
        name=name,
        matches_per_variant=c.matches,
        home_points_delta=t.home_points_per_match - c.home_points_per_match,
        home_possession_pp_delta=t.home_possession_pct - c.home_possession_pct,
        home_pass_completion_pp_delta=t_home_pass - c_home_pass,
        home_shots_delta=(sum(item.home_shots for item in t_items) - sum(item.home_shots for item in c_items)) / c.matches,
        home_xg_delta=(sum(item.home_xg for item in t_items) - sum(item.home_xg for item in c_items)) / c.matches,
        home_fouls_delta=(sum(item.home_fouls for item in t_items) - sum(item.home_fouls for item in c_items)) / c.matches,
        home_corners_delta=(sum(item.home_corners for item in t_items) - sum(item.home_corners for item in c_items)) / c.matches,
        away_pass_completion_pp_delta=t_away_pass - c_away_pass,
    )


@dataclass(frozen=True, slots=True)
class FastTacticalMatchupDelta:
    name: str
    matches_per_variant: int
    home_points_delta: float
    home_xg_delta: float
    away_xg_delta: float
    xg_diff_delta: float
    shot_diff_delta: float
    home_possession_pp_delta: float
    home_pass_completion_pp_delta: float
    away_pass_completion_pp_delta: float


def summarize_tactical_matchup_delta(
    difficult: Iterable[FastCalibrationSample],
    favorable: Iterable[FastCalibrationSample],
    *,
    name: str,
) -> FastTacticalMatchupDelta:
    d_items = tuple(difficult)
    f_items = tuple(favorable)
    d = summarize_fast_samples(d_items)
    f = summarize_fast_samples(f_items)
    if d.matches != f.matches:
        raise ValueError("paired tactical matchup summaries require equal sample sizes")

    def pass_pct(items: tuple[FastCalibrationSample, ...], *, home: bool) -> float:
        if home:
            attempted = sum(item.home_passes_attempted for item in items)
            completed = sum(item.home_passes_completed for item in items)
        else:
            attempted = sum(item.away_passes_attempted for item in items)
            completed = sum(item.away_passes_completed for item in items)
        return completed / attempted * 100.0 if attempted else 0.0

    d_home_xg = sum(item.home_xg for item in d_items) / d.matches
    f_home_xg = sum(item.home_xg for item in f_items) / f.matches
    d_away_xg = sum(item.away_xg for item in d_items) / d.matches
    f_away_xg = sum(item.away_xg for item in f_items) / f.matches
    d_shot_diff = sum(item.home_shots - item.away_shots for item in d_items) / d.matches
    f_shot_diff = sum(item.home_shots - item.away_shots for item in f_items) / f.matches
    return FastTacticalMatchupDelta(
        name=name,
        matches_per_variant=d.matches,
        home_points_delta=f.home_points_per_match - d.home_points_per_match,
        home_xg_delta=f_home_xg - d_home_xg,
        away_xg_delta=f_away_xg - d_away_xg,
        xg_diff_delta=(f_home_xg - f_away_xg) - (d_home_xg - d_away_xg),
        shot_diff_delta=f_shot_diff - d_shot_diff,
        home_possession_pp_delta=f.home_possession_pct - d.home_possession_pct,
        home_pass_completion_pp_delta=pass_pct(f_items, home=True) - pass_pct(d_items, home=True),
        away_pass_completion_pp_delta=pass_pct(f_items, home=False) - pass_pct(d_items, home=False),
    )


@dataclass(frozen=True, slots=True)
class FastLeagueStanding:
    team_id: str
    quality_delta: int
    played: int
    won: int
    drawn: int
    lost: int
    goals_for: int
    goals_against: int
    points: int

    @property
    def goal_difference(self) -> int:
        return self.goals_for - self.goals_against

    @property
    def points_per_match(self) -> float:
        return self.points / self.played if self.played else 0.0

    def to_row(self) -> dict[str, object]:
        row = asdict(self)
        row["goal_difference"] = self.goal_difference
        row["points_per_match"] = round(self.points_per_match, 6)
        return row


@dataclass(frozen=True, slots=True)
class FastLeagueSummary:
    teams: int
    matches: int
    elapsed_seconds: float
    matches_per_second: float
    strongest_team_rank: int
    weakest_team_rank: int
    top_half_mean_quality: float
    bottom_half_mean_quality: float
    rank_quality_correlation: float


@dataclass(frozen=True, slots=True)
class FastCoachVsSquadSummary:
    scenario: str
    paired_seeds: int
    matches: int
    weaker_points_per_match: float
    weaker_win_pct: float
    draw_pct: float
    stronger_win_pct: float
    weaker_goal_diff_per_match: float
    weaker_xg_diff_per_match: float
    weaker_shot_diff_per_match: float
    weaker_xg_share_pct: float


def summarize_coach_vs_squad(
    samples: Iterable[tuple[FastCalibrationSample, bool]],
    *,
    scenario: str,
) -> FastCoachVsSquadSummary:
    """Summarize paired fixtures from the weaker team's point of view.

    The bool in each tuple is True when the weaker team was the home team.
    """

    items = tuple(samples)
    if not items:
        raise ValueError("cannot summarize an empty coach-vs-squad sample set")

    weak_wins = draws = strong_wins = 0
    weak_points = 0
    weak_goal_diff = 0.0
    weak_xg_diff = 0.0
    weak_shot_diff = 0.0
    weak_xg = 0.0
    strong_xg = 0.0

    for sample, weaker_home in items:
        if weaker_home:
            weak_goals, strong_goals = sample.home_goals, sample.away_goals
            weak_match_xg, strong_match_xg = sample.home_xg, sample.away_xg
            weak_shots, strong_shots = sample.home_shots, sample.away_shots
        else:
            weak_goals, strong_goals = sample.away_goals, sample.home_goals
            weak_match_xg, strong_match_xg = sample.away_xg, sample.home_xg
            weak_shots, strong_shots = sample.away_shots, sample.home_shots

        if weak_goals > strong_goals:
            weak_wins += 1
            weak_points += 3
        elif weak_goals == strong_goals:
            draws += 1
            weak_points += 1
        else:
            strong_wins += 1

        weak_goal_diff += weak_goals - strong_goals
        weak_xg_diff += weak_match_xg - strong_match_xg
        weak_shot_diff += weak_shots - strong_shots
        weak_xg += weak_match_xg
        strong_xg += strong_match_xg

    matches = len(items)
    paired_seeds = matches // 2
    total_xg = weak_xg + strong_xg
    return FastCoachVsSquadSummary(
        scenario=scenario,
        paired_seeds=paired_seeds,
        matches=matches,
        weaker_points_per_match=weak_points / matches,
        weaker_win_pct=weak_wins / matches * 100.0,
        draw_pct=draws / matches * 100.0,
        stronger_win_pct=strong_wins / matches * 100.0,
        weaker_goal_diff_per_match=weak_goal_diff / matches,
        weaker_xg_diff_per_match=weak_xg_diff / matches,
        weaker_shot_diff_per_match=weak_shot_diff / matches,
        weaker_xg_share_pct=(weak_xg / total_xg * 100.0 if total_xg > 0.0 else 50.0),
    )
