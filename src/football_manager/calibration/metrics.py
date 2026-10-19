from __future__ import annotations

from dataclasses import asdict, dataclass
from statistics import fmean
from typing import Iterable


@dataclass(frozen=True, slots=True)
class CalibrationSample:
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
    event_integrity_issues: int = 0
    unresolved_shots: int = 0
    orphan_shot_resolutions: int = 0
    score_goal_delta: int = 0
    home_tackles: int = 0
    away_tackles: int = 0
    home_successful_tackles: int = 0
    away_successful_tackles: int = 0
    home_recoveries: int = 0
    away_recoveries: int = 0
    home_dribbles: int = 0
    away_dribbles: int = 0
    home_crosses: int = 0
    away_crosses: int = 0
    home_completed_crosses: int = 0
    away_completed_crosses: int = 0

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
class CalibrationSummary:
    scenario: str
    matches: int
    mean_elapsed_seconds: float
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
    home_xg_diff_per_match: float
    event_integrity_issues: int
    matches_with_event_integrity_issues: int

    def to_row(self) -> dict[str, object]:
        return asdict(self)


def summarize_samples(samples: Iterable[CalibrationSample]) -> CalibrationSummary:
    items = tuple(samples)
    if not items:
        raise ValueError("cannot summarize an empty calibration sample set")
    scenarios = {item.scenario for item in items}
    if len(scenarios) != 1:
        raise ValueError("all calibration samples in a summary must share one scenario")

    matches = len(items)
    total_goals = sum(item.total_goals for item in items)
    total_shots = sum(item.total_shots for item in items)
    total_xg = sum(item.total_xg for item in items)
    attempted = sum(item.total_passes_attempted for item in items)
    completed = sum(item.total_passes_completed for item in items)
    home_wins = sum(item.outcome == "home" for item in items)
    draws = sum(item.outcome == "draw" for item in items)
    away_wins = matches - home_wins - draws
    home_points = home_wins * 3 + draws

    return CalibrationSummary(
        scenario=items[0].scenario,
        matches=matches,
        mean_elapsed_seconds=fmean(item.elapsed_seconds for item in items),
        goals_per_match=total_goals / matches,
        shots_per_match=total_shots / matches,
        shots_on_target_per_match=sum(item.total_shots_on_target for item in items) / matches,
        xg_per_match=total_xg / matches,
        goals_minus_xg_per_match=(total_goals - total_xg) / matches,
        goals_per_xg=(total_goals / total_xg if total_xg > 0.0 else 0.0),
        shot_conversion_pct=(total_goals / total_shots * 100.0 if total_shots > 0 else 0.0),
        pass_completion_pct=(completed / attempted * 100.0 if attempted > 0 else 0.0),
        fouls_per_match=sum(item.total_fouls for item in items) / matches,
        yellow_cards_per_match=sum(item.total_yellow_cards for item in items) / matches,
        red_cards_per_match=sum(item.total_red_cards for item in items) / matches,
        corners_per_match=sum(item.total_corners for item in items) / matches,
        home_possession_pct=fmean(item.home_possession_pct for item in items),
        home_win_pct=home_wins / matches * 100.0,
        draw_pct=draws / matches * 100.0,
        away_win_pct=away_wins / matches * 100.0,
        home_points_per_match=home_points / matches,
        home_xg_diff_per_match=sum(item.home_xg - item.away_xg for item in items) / matches,
        event_integrity_issues=sum(item.event_integrity_issues for item in items),
        matches_with_event_integrity_issues=sum(item.event_integrity_issues > 0 for item in items),
    )
