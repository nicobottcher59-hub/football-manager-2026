from __future__ import annotations

from dataclasses import dataclass

from .metrics import CalibrationSummary


@dataclass(frozen=True, slots=True)
class MetricTarget:
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

    def distance(self, value: float) -> float:
        if value < self.low:
            return self.low - value
        if value > self.high:
            return value - self.high
        return 0.0


# Initial broad reference bands for the neutral 70-v-70 benchmark. They are
# intentionally ranges, not universal football constants. Phase 5.10B/C can
# replace or segment them by competition/era once the event model and datasets
# are hardened.
DEFAULT_NEUTRAL_TARGETS: tuple[MetricTarget, ...] = (
    MetricTarget("shots_per_match", "Total shots", 20.0, 30.0),
    MetricTarget("shots_on_target_per_match", "Shots on target", 6.0, 12.0),
    MetricTarget("goals_per_match", "Goals", 2.2, 3.2),
    MetricTarget("fouls_per_match", "Fouls", 18.0, 30.0),
    MetricTarget("yellow_cards_per_match", "Yellow cards", 2.5, 5.5),
    MetricTarget("corners_per_match", "Corners", 7.0, 13.0),
    MetricTarget("pass_completion_pct", "Pass completion", 78.0, 87.0, "%"),
    MetricTarget("home_win_pct", "Home wins", 35.0, 55.0, "%"),
    MetricTarget("draw_pct", "Draws", 18.0, 32.0, "%"),
    MetricTarget("away_win_pct", "Away wins", 22.0, 40.0, "%"),
    MetricTarget(
        "goals_minus_xg_per_match",
        "Goals - xG",
        -0.35,
        0.35,
    ),
)


@dataclass(frozen=True, slots=True)
class TargetEvaluation:
    key: str
    label: str
    value: float
    low: float
    high: float
    unit: str
    status: str
    distance: float


def evaluate_targets(
    summary: CalibrationSummary,
    targets: tuple[MetricTarget, ...] = DEFAULT_NEUTRAL_TARGETS,
) -> tuple[TargetEvaluation, ...]:
    results: list[TargetEvaluation] = []
    for target in targets:
        value = float(getattr(summary, target.key))
        results.append(
            TargetEvaluation(
                key=target.key,
                label=target.label,
                value=value,
                low=target.low,
                high=target.high,
                unit=target.unit,
                status=target.status(value),
                distance=target.distance(value),
            )
        )
    return tuple(results)
