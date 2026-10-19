from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from statistics import fmean
from typing import Iterable

from football_manager.domain import (
    Level,
    MatchSnapshot,
    PassLength,
    TeamInstructions,
    analyze_tactical_style,
)

from .metrics import CalibrationSample


@dataclass(frozen=True, slots=True)
class TacticalAblation:
    name: str
    section: str
    field: str
    control_value: object
    treatment_value: object
    description: str
    expected_signal: str


DEFAULT_TACTICAL_ABLATIONS: tuple[TacticalAblation, ...] = (
    TacticalAblation(
        name="tempo",
        section="in_possession",
        field="tempo",
        control_value=Level.LOW,
        treatment_value=Level.VERY_HIGH,
        description="Low tempo versus very high tempo; all other instructions remain unchanged.",
        expected_signal="home action volume / passes / shots should respond measurably",
    ),
    TacticalAblation(
        name="pressing_intensity",
        section="out_of_possession",
        field="pressing_intensity",
        control_value=Level.LOW,
        treatment_value=Level.VERY_HIGH,
        description="Low versus very high pressing intensity with identical teams and seeds.",
        expected_signal="home tackles, recoveries, fouls or opponent pass completion should move",
    ),
    TacticalAblation(
        name="build_from_back",
        section="in_possession",
        field="build_from_back",
        control_value=Level.VERY_LOW,
        treatment_value=Level.VERY_HIGH,
        description="Build-from-back disabled versus strongly preferred.",
        expected_signal="home pass volume / completion / possession should move",
    ),
    TacticalAblation(
        name="crossing_frequency",
        section="in_possession",
        field="crossing_frequency",
        control_value=Level.VERY_LOW,
        treatment_value=Level.VERY_HIGH,
        description="Rare crossing versus very frequent crossing.",
        expected_signal="home crosses should move clearly",
    ),
    TacticalAblation(
        name="pass_length",
        section="in_possession",
        field="pass_length",
        control_value=PassLength.VERY_SHORT,
        treatment_value=PassLength.VERY_LONG,
        description="Very short passing versus very long passing.",
        expected_signal="home pass completion and progression/shot profile should respond",
    ),
)


def tactical_ablation(name: str) -> TacticalAblation:
    for item in DEFAULT_TACTICAL_ABLATIONS:
        if item.name == name:
            return item
    choices = ", ".join(item.name for item in DEFAULT_TACTICAL_ABLATIONS)
    raise KeyError(f"unknown tactical ablation {name!r}; choose one of: {choices}")


def _with_instruction(
    instructions: TeamInstructions,
    *,
    section: str,
    field: str,
    value: object,
) -> TeamInstructions:
    if section not in {"in_possession", "transition", "out_of_possession", "game_management"}:
        raise ValueError(f"unsupported tactical instruction section {section!r}")
    current = getattr(instructions, section)
    updated = replace(current, **{field: value})
    return replace(instructions, **{section: updated})


def build_ablation_snapshot(
    base: MatchSnapshot,
    ablation: TacticalAblation,
    *,
    variant: str,
    seed: int,
) -> MatchSnapshot:
    if variant not in {"control", "treatment"}:
        raise ValueError("ablation variant must be 'control' or 'treatment'")
    value = ablation.control_value if variant == "control" else ablation.treatment_value
    instructions = _with_instruction(
        base.home_team.tactic.team_instructions,
        section=ablation.section,
        field=ablation.field,
        value=value,
    )
    tactic = replace(
        base.home_team.tactic,
        team_instructions=instructions,
        style=analyze_tactical_style(instructions),
    )
    home_team = replace(base.home_team, tactic=tactic)
    return replace(
        base,
        match_id=f"{base.match_id}-abl-{ablation.name}-{variant}-{seed}",
        seed=seed,
        home_team=home_team,
    )


@dataclass(frozen=True, slots=True)
class AblationSummary:
    ablation: str
    matches_per_variant: int
    home_points_delta: float
    home_possession_pp_delta: float
    home_passes_attempted_delta: float
    home_pass_completion_pp_delta: float
    home_shots_delta: float
    home_xg_delta: float
    home_crosses_delta: float
    home_tackles_delta: float
    home_recoveries_delta: float
    home_fouls_delta: float
    away_pass_completion_pp_delta: float
    seeds_with_any_material_change_pct: float

    def to_row(self) -> dict[str, object]:
        return asdict(self)


def _points(sample: CalibrationSample) -> float:
    if sample.home_goals > sample.away_goals:
        return 3.0
    if sample.home_goals == sample.away_goals:
        return 1.0
    return 0.0


def _completion(completed: int, attempted: int) -> float:
    return completed / attempted * 100.0 if attempted > 0 else 0.0


def summarize_ablation(
    control: Iterable[CalibrationSample],
    treatment: Iterable[CalibrationSample],
    *,
    name: str,
) -> AblationSummary:
    control_by_seed = {item.seed: item for item in control}
    treatment_by_seed = {item.seed: item for item in treatment}
    if not control_by_seed or set(control_by_seed) != set(treatment_by_seed):
        raise ValueError("ablation control/treatment samples must have the same non-empty seed set")

    deltas: list[dict[str, float]] = []
    materially_changed = 0
    for seed in sorted(control_by_seed):
        before = control_by_seed[seed]
        after = treatment_by_seed[seed]
        row = {
            "points": _points(after) - _points(before),
            "possession": after.home_possession_pct - before.home_possession_pct,
            "passes": float(after.home_passes_attempted - before.home_passes_attempted),
            "pass_completion": _completion(after.home_passes_completed, after.home_passes_attempted)
            - _completion(before.home_passes_completed, before.home_passes_attempted),
            "shots": float(after.home_shots - before.home_shots),
            "xg": after.home_xg - before.home_xg,
            "crosses": float(after.home_crosses - before.home_crosses),
            "tackles": float(after.home_tackles - before.home_tackles),
            "recoveries": float(after.home_recoveries - before.home_recoveries),
            "fouls": float(after.home_fouls - before.home_fouls),
            "away_pass_completion": _completion(after.away_passes_completed, after.away_passes_attempted)
            - _completion(before.away_passes_completed, before.away_passes_attempted),
        }
        deltas.append(row)
        if any(
            abs(row[key]) >= threshold
            for key, threshold in (
                ("possession", 1.0),
                ("passes", 2.0),
                ("pass_completion", 1.0),
                ("shots", 1.0),
                ("xg", 0.10),
                ("crosses", 1.0),
                ("tackles", 1.0),
                ("recoveries", 1.0),
                ("fouls", 1.0),
                ("away_pass_completion", 1.0),
            )
        ):
            materially_changed += 1

    def mean(key: str) -> float:
        return fmean(item[key] for item in deltas)

    return AblationSummary(
        ablation=name,
        matches_per_variant=len(deltas),
        home_points_delta=mean("points"),
        home_possession_pp_delta=mean("possession"),
        home_passes_attempted_delta=mean("passes"),
        home_pass_completion_pp_delta=mean("pass_completion"),
        home_shots_delta=mean("shots"),
        home_xg_delta=mean("xg"),
        home_crosses_delta=mean("crosses"),
        home_tackles_delta=mean("tackles"),
        home_recoveries_delta=mean("recoveries"),
        home_fouls_delta=mean("fouls"),
        away_pass_completion_pp_delta=mean("away_pass_completion"),
        seeds_with_any_material_change_pct=materially_changed / len(deltas) * 100.0,
    )
