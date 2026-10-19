from __future__ import annotations

import subprocess
import sys
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

import pytest

from examples.demo_match_factory import build_demo_snapshot
from football_manager.calibration import (
    BenchmarkScenario,
    CalibrationSample,
    MetricTarget,
    benchmark_scenario,
    build_benchmark_snapshot,
    calibration_run_id,
    evaluate_targets,
    shift_player_attributes,
    summarize_samples,
    write_calibration_reports,
)


def _sample(
    *,
    seed: int,
    home_goals: int,
    away_goals: int,
    home_xg: float,
    away_xg: float,
    scenario: str = "equal",
) -> CalibrationSample:
    return CalibrationSample(
        scenario=scenario,
        seed=seed,
        elapsed_seconds=2.0,
        home_goals=home_goals,
        away_goals=away_goals,
        home_shots=10,
        away_shots=8,
        home_shots_on_target=4,
        away_shots_on_target=3,
        home_xg=home_xg,
        away_xg=away_xg,
        home_possession_pct=55.0,
        away_possession_pct=45.0,
        home_passes_attempted=100,
        away_passes_attempted=100,
        home_passes_completed=80,
        away_passes_completed=70,
        home_fouls=7,
        away_fouls=8,
        home_yellow_cards=1,
        away_yellow_cards=2,
        home_red_cards=0,
        away_red_cards=0,
        home_corners=5,
        away_corners=4,
    )


def test_benchmark_scenarios_are_named_and_lookup_is_strict() -> None:
    assert benchmark_scenario("equal").strength_gap == 0
    assert benchmark_scenario("home_weaker_10").strength_gap == -10
    assert benchmark_scenario("home_stronger_10").strength_gap == 10
    with pytest.raises(KeyError):
        benchmark_scenario("unknown")


def test_attribute_shift_is_clamped_and_does_not_mutate_source() -> None:
    snapshot = build_demo_snapshot(seed=1)
    source = snapshot.home_team.starters[0].attributes
    raised = shift_player_attributes(source, 40)
    lowered = shift_player_attributes(source, -80)

    assert source.technical.passing == 70
    assert raised.technical.passing == 100
    assert raised.mental.decisions == 100
    assert lowered.physical.pace == 1


def test_benchmark_snapshot_changes_only_controlled_strength_and_seed() -> None:
    base = build_demo_snapshot(seed=10)
    scenario = BenchmarkScenario("test", home_attribute_delta=5, away_attribute_delta=-5)
    benchmark = build_benchmark_snapshot(base, scenario, seed=123)

    assert benchmark.seed == 123
    assert benchmark.match_id.endswith("-cal-test-123")
    assert benchmark.home_team.starters[0].attributes.technical.passing == 75
    assert benchmark.away_team.starters[0].attributes.technical.passing == 65
    assert base.home_team.starters[0].attributes.technical.passing == 70
    assert base.away_team.starters[0].attributes.technical.passing == 70


def test_summary_aggregates_distribution_and_outcomes() -> None:
    summary = summarize_samples(
        (
            _sample(seed=1, home_goals=2, away_goals=1, home_xg=1.8, away_xg=1.0),
            _sample(seed=2, home_goals=1, away_goals=1, home_xg=1.2, away_xg=1.1),
            _sample(seed=3, home_goals=0, away_goals=1, home_xg=0.8, away_xg=1.2),
        )
    )

    assert summary.matches == 3
    assert summary.goals_per_match == pytest.approx(2.0)
    assert summary.shots_per_match == pytest.approx(18.0)
    assert summary.pass_completion_pct == pytest.approx(75.0)
    assert summary.home_win_pct == pytest.approx(100 / 3)
    assert summary.draw_pct == pytest.approx(100 / 3)
    assert summary.away_win_pct == pytest.approx(100 / 3)
    assert summary.home_points_per_match == pytest.approx(4 / 3)
    assert summary.goals_minus_xg_per_match == pytest.approx((6.0 - 7.1) / 3)


def test_summary_rejects_empty_or_mixed_scenarios() -> None:
    with pytest.raises(ValueError):
        summarize_samples(())
    with pytest.raises(ValueError):
        summarize_samples(
            (
                _sample(seed=1, home_goals=1, away_goals=0, home_xg=1.0, away_xg=0.5),
                _sample(
                    seed=2,
                    home_goals=1,
                    away_goals=0,
                    home_xg=1.0,
                    away_xg=0.5,
                    scenario="home_stronger_10",
                ),
            )
        )


def test_target_evaluation_reports_low_ok_and_high() -> None:
    summary = summarize_samples(
        (_sample(seed=1, home_goals=2, away_goals=1, home_xg=1.5, away_xg=1.5),)
    )
    targets = (
        MetricTarget("shots_per_match", "Shots", 20.0, 30.0),
        MetricTarget("goals_per_match", "Goals", 2.0, 4.0),
        MetricTarget("pass_completion_pct", "Pass", 60.0, 70.0),
    )
    statuses = tuple(item.status for item in evaluate_targets(summary, targets))
    assert statuses == ("LOW", "OK", "HIGH")


def test_report_files_are_versioned_and_contain_scenario_summary(tmp_path: Path) -> None:
    samples = (
        _sample(seed=1, home_goals=2, away_goals=1, home_xg=1.6, away_xg=0.9),
    )
    summaries = (summarize_samples(samples),)
    scenarios = (benchmark_scenario("equal"),)
    evaluations = evaluate_targets(summaries[0])
    run_id = calibration_run_id(
        commit="abc123",
        now=datetime(2026, 10, 6, 12, 0, tzinfo=timezone.utc),
    )

    paths = write_calibration_reports(
        tmp_path,
        run_id=run_id,
        commit="abc123",
        dirty=True,
        scenarios=scenarios,
        samples=samples,
        summaries=summaries,
        target_evaluations=evaluations,
    )

    assert all(path.exists() for path in paths)
    assert run_id == "20261006T120000Z_abc123"
    markdown = paths[-1].read_text(encoding="utf-8")
    assert "Match Engine calibration report" in markdown
    assert "equal" in markdown
    assert "Goals - xG" in markdown


def test_calibrate_cli_smoke_run_writes_reports(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[1]
    process = subprocess.run(
        [
            sys.executable,
            str(root / "tools" / "calibrate.py"),
            "--matches",
            "1",
            "--workers",
            "1",
            "--scenarios",
            "equal",
            "--smoke",
            "--output-dir",
            str(tmp_path),
        ],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )

    assert "SMOKE MODE" in process.stdout
    assert len(list(tmp_path.glob("*.md"))) == 1
    assert len(list(tmp_path.glob("*_matches.csv"))) == 1
    assert len(list(tmp_path.glob("*_summary.csv"))) == 1
