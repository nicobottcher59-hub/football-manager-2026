from __future__ import annotations

import subprocess
import sys
from dataclasses import fields
from pathlib import Path

import pytest

from examples.demo_match_factory import build_demo_snapshot
from football_manager.calibration import (
    STRENGTH_CURVE_SCENARIOS,
    CalibrationSample,
    StrengthCurvePoint,
    build_ablation_snapshot,
    build_strength_curve_snapshot,
    diagnose_strength_curve,
    strength_curve_scenario,
    summarize_ablation,
    summarize_strength_point,
    tactical_ablation,
)


def _sample(
    *,
    scenario: str,
    seed: int,
    home_goals: int = 1,
    away_goals: int = 1,
    home_xg: float = 1.0,
    away_xg: float = 1.0,
    home_possession_pct: float = 50.0,
    home_passes_attempted: int = 100,
    away_passes_attempted: int = 100,
    home_passes_completed: int = 70,
    away_passes_completed: int = 70,
    home_shots: int = 8,
    away_shots: int = 8,
    home_crosses: int = 2,
    home_tackles: int = 4,
    home_recoveries: int = 5,
    home_fouls: int = 3,
) -> CalibrationSample:
    return CalibrationSample(
        scenario=scenario,
        seed=seed,
        elapsed_seconds=1.0,
        home_goals=home_goals,
        away_goals=away_goals,
        home_shots=home_shots,
        away_shots=away_shots,
        home_shots_on_target=3,
        away_shots_on_target=3,
        home_xg=home_xg,
        away_xg=away_xg,
        home_possession_pct=home_possession_pct,
        away_possession_pct=100.0 - home_possession_pct,
        home_passes_attempted=home_passes_attempted,
        away_passes_attempted=away_passes_attempted,
        home_passes_completed=home_passes_completed,
        away_passes_completed=away_passes_completed,
        home_fouls=home_fouls,
        away_fouls=3,
        home_yellow_cards=1,
        away_yellow_cards=1,
        home_red_cards=0,
        away_red_cards=0,
        home_corners=2,
        away_corners=2,
        home_crosses=home_crosses,
        home_tackles=home_tackles,
        home_recoveries=home_recoveries,
    )


def test_strength_curve_has_symmetric_controlled_gaps() -> None:
    assert tuple(item.strength_gap for item in STRENGTH_CURVE_SCENARIOS) == (-20, -10, -5, 0, 5, 10, 20)
    assert strength_curve_scenario("home_stronger_10_heterogeneous").strength_gap == 10


def test_heterogeneous_equal_snapshot_is_mirrored_but_not_uniform() -> None:
    base = build_demo_snapshot(seed=10)
    snapshot = build_strength_curve_snapshot(
        base,
        strength_curve_scenario("equal_heterogeneous"),
        seed=10,
    )

    home = snapshot.home_team.starters
    away = snapshot.away_team.starters
    assert home[0].attributes == away[0].attributes
    # Profiles are no longer all-70 clones.
    values = {
        getattr(player.attributes.technical, field.name)
        for player in home
        for field in fields(player.attributes.technical)
    }
    assert len(values) > 3
    assert any(value != 70 for value in values)


def test_strength_shift_preserves_profile_and_adds_exact_gap_away_from_clamps() -> None:
    base = build_demo_snapshot(seed=11)
    equal = build_strength_curve_snapshot(base, strength_curve_scenario("equal_heterogeneous"), seed=11)
    stronger = build_strength_curve_snapshot(
        base,
        strength_curve_scenario("home_stronger_10_heterogeneous"),
        seed=11,
    )

    assert stronger.home_team.starters[4].attributes.mental.decisions == (
        equal.home_team.starters[4].attributes.mental.decisions + 10
    )
    assert stronger.away_team.starters[4].attributes == equal.away_team.starters[4].attributes


def test_strength_summary_reports_underdog_wins_by_gap_direction() -> None:
    samples = (
        _sample(scenario="plus10", seed=1, home_goals=2, away_goals=0, home_xg=1.5, away_xg=0.5),
        _sample(scenario="plus10", seed=2, home_goals=0, away_goals=1, home_xg=1.1, away_xg=0.7),
        _sample(scenario="plus10", seed=3, home_goals=1, away_goals=1, home_xg=1.0, away_xg=0.8),
    )
    point = summarize_strength_point(samples, strength_gap=10)

    assert point.home_points_per_match == pytest.approx(4 / 3)
    assert point.underdog_win_pct == pytest.approx(100 / 3)
    assert point.favorite_non_win_pct == pytest.approx(200 / 3)


def test_strength_diagnostics_detect_monotonicity_violations() -> None:
    points = (
        StrengthCurvePoint("m5", -5, 4, 1.0, -0.2, -0.1, 48, 25, 25, 50, 25, 75),
        StrengthCurvePoint("eq", 0, 4, 1.5, 0.0, 0.0, 50, 50, 0, 50, None, None),
        StrengthCurvePoint("p5", 5, 4, 1.3, 0.2, 0.3, 55, 50, 25, 25, 25, 50),
    )
    diagnostics = diagnose_strength_curve(points)
    assert diagnostics.ppg_monotonic_violations == 1
    assert diagnostics.xg_monotonic_violations == 0
    assert diagnostics.xg_diff_slope_per_10_points > 0


def test_ablation_snapshot_changes_only_requested_team_instruction() -> None:
    base = build_demo_snapshot(seed=12)
    definition = tactical_ablation("pressing_intensity")
    control = build_ablation_snapshot(base, definition, variant="control", seed=12)
    treatment = build_ablation_snapshot(base, definition, variant="treatment", seed=12)

    assert control.home_team.tactic.team_instructions.out_of_possession.pressing_intensity != (
        treatment.home_team.tactic.team_instructions.out_of_possession.pressing_intensity
    )
    assert control.away_team == treatment.away_team
    assert control.home_team.tactic.team_instructions.in_possession == (
        treatment.home_team.tactic.team_instructions.in_possession
    )
    assert control.home_team.tactic.style.pressing < treatment.home_team.tactic.style.pressing


def test_ablation_summary_uses_paired_seed_deltas() -> None:
    control = (
        _sample(scenario="tempo:control", seed=1, home_passes_attempted=90, home_shots=6, home_xg=0.8),
        _sample(scenario="tempo:control", seed=2, home_passes_attempted=100, home_shots=7, home_xg=0.9),
    )
    treatment = (
        _sample(scenario="tempo:treatment", seed=1, home_passes_attempted=100, home_shots=8, home_xg=1.0),
        _sample(scenario="tempo:treatment", seed=2, home_passes_attempted=110, home_shots=8, home_xg=1.1),
    )
    summary = summarize_ablation(control, treatment, name="tempo")

    assert summary.home_passes_attempted_delta == pytest.approx(10.0)
    assert summary.home_shots_delta == pytest.approx(1.5)
    assert summary.home_xg_delta == pytest.approx(0.2)
    assert summary.seeds_with_any_material_change_pct == 100.0


def test_strength_curve_cli_smoke_writes_reports(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[1]
    process = subprocess.run(
        [
            sys.executable,
            str(root / "tools" / "strength_curve.py"),
            "--matches", "1",
            "--workers", "1",
            "--scenarios", "home_weaker_5_heterogeneous", "home_stronger_5_heterogeneous",
            "--smoke",
            "--output-dir", str(tmp_path),
        ],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )
    assert "STRENGTH CURVE" in process.stdout
    assert len(list(tmp_path.glob("*_strength.md"))) == 1
    assert len(list(tmp_path.glob("*_strength_curve.csv"))) == 1


def test_tactical_ablation_cli_smoke_writes_reports(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[1]
    process = subprocess.run(
        [
            sys.executable,
            str(root / "tools" / "ablate_tactics.py"),
            "--matches", "1",
            "--workers", "1",
            "--ablations", "tempo",
            "--smoke",
            "--output-dir", str(tmp_path),
        ],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )
    assert "TACTICAL ABLATION" in process.stdout
    assert len(list(tmp_path.glob("*_ablation.md"))) == 1
    assert len(list(tmp_path.glob("*_ablation_summary.csv"))) == 1
