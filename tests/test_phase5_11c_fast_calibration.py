from __future__ import annotations

from pathlib import Path

import pytest

from examples.demo_match_factory import build_demo_snapshot
from football_manager.fast_calibration import (
    FAST_ACT_GAPS,
    FAST_COACH_VS_SQUAD_SCENARIOS,
    FAST_STRENGTH_GAPS,
    FAST_TACTICAL_MATCHUPS,
    build_act_snapshot,
    build_coach_vs_squad_snapshot,
    build_execution_snapshot,
    build_mixed_snapshot,
    build_strength_snapshot,
    build_tactical_snapshot,
    build_tactical_matchup_snapshot,
    diagnose_curve,
    evaluate_fast_targets,
    neutralize_fast_snapshot,
    run_fast_calibration_match,
    simulate_synthetic_league,
    summarize_coach_vs_squad,
    summarize_curve_point,
    summarize_execution_point,
    summarize_fast_samples,
    summarize_tactical_delta,
    summarize_tactical_matchup_delta,
    tactical_ablation,
    with_seed,
)
from football_manager.fast_simulation import FastMatchSimulator


def _base():
    return neutralize_fast_snapshot(build_demo_snapshot(seed=1), rating=70, seed=1)


def _sample(base, seeds, *, scenario="test", builder=None):
    simulator = FastMatchSimulator()
    rows = []
    for seed in seeds:
        snapshot = builder(seed) if builder is not None else with_seed(base, seed)
        rows.append(
            run_fast_calibration_match(
                snapshot,
                scenario=scenario,
                seed=seed,
                simulator=simulator,
            )
        )
    return tuple(rows)


def test_neutral_fast_benchmark_removes_demo_fixture_artifacts() -> None:
    base = _base()
    home, away = FastMatchSimulator().profiles(base)

    for profile in (home, away):
        assert profile.overall == 70.0
        assert profile.current == 70.0
        assert profile.attack == pytest.approx(70.0)
        assert profile.control == pytest.approx(70.0)
        assert profile.defense == pytest.approx(70.0)
        assert profile.goalkeeping == 70.0
        assert profile.tactical_execution == 65.0
        assert profile.possession_style == 50.0
        assert profile.pressing == 50.0


def test_neutral_fast_batch_sits_inside_broad_reference_bands() -> None:
    base = _base()
    rows = _sample(base, range(90_000, 90_400), scenario="neutral")
    summary = summarize_fast_samples(rows)
    evaluations = evaluate_fast_targets(summary)

    assert all(item.status == "OK" for item in evaluations)
    assert abs(summary.goals_minus_xg_per_match) <= 0.20
    assert summary.matches_per_second > 0.0


def test_neutral_volatility_is_present_without_constant_extremes() -> None:
    base = _base()
    summary = summarize_fast_samples(_sample(base, range(91_000, 91_300), scenario="neutral"))

    assert 4.0 <= summary.scoreless_pct <= 15.0
    assert 40.0 <= summary.both_teams_score_pct <= 65.0
    assert 18.0 <= summary.four_plus_goals_pct <= 40.0
    assert 8.0 <= summary.margin_three_plus_pct <= 25.0
    assert 10.0 <= summary.shot_diff_10plus_pct <= 35.0
    assert 18.0 <= summary.xg_diff_1plus_pct <= 45.0


def test_strength_curve_is_monotonic_but_keeps_upsets_alive() -> None:
    base = _base()
    seeds = range(92_000, 92_120)
    points = []
    for gap in FAST_STRENGTH_GAPS:
        rows = _sample(
            base,
            seeds,
            scenario=f"strength:{gap}",
            builder=lambda seed, gap=gap: build_strength_snapshot(base, gap, seed=seed),
        )
        points.append(summarize_curve_point(rows, value=float(gap)))

    diagnostics = diagnose_curve(points)
    by_gap = {int(point.value): point for point in points}
    assert diagnostics.ppg_slope_per_10 > 0.25
    assert diagnostics.xg_diff_slope_per_10 > 0.30
    assert diagnostics.ppg_monotonic_violations <= 1
    assert diagnostics.xg_monotonic_violations <= 1
    assert by_gap[20].home_win_pct > by_gap[0].home_win_pct > by_gap[-20].home_win_pct
    assert by_gap[20].underdog_win_pct is not None and by_gap[20].underdog_win_pct > 0.0
    assert by_gap[-20].underdog_win_pct is not None and by_gap[-20].underdog_win_pct > 0.0


def test_act_curve_changes_results_less_aggressively_than_full_quality() -> None:
    base = _base()
    seeds = range(93_000, 93_120)
    act_points = []
    for gap in FAST_ACT_GAPS:
        rows = _sample(
            base,
            seeds,
            scenario=f"act:{gap}",
            builder=lambda seed, gap=gap: build_act_snapshot(base, gap, seed=seed),
        )
        act_points.append(summarize_curve_point(rows, value=float(gap)))

    diagnostics = diagnose_curve(act_points)
    by_gap = {int(point.value): point for point in act_points}
    assert diagnostics.ppg_slope_per_10 > 0.12
    assert diagnostics.ppg_slope_per_10 < 0.45
    assert diagnostics.ppg_monotonic_violations <= 1
    assert by_gap[20].home_points_per_match > by_gap[0].home_points_per_match
    assert by_gap[-20].home_points_per_match < by_gap[0].home_points_per_match
    assert by_gap[20].away_win_pct > 0.0


def test_tactical_execution_scales_expression_of_the_same_plan() -> None:
    base = _base()
    seeds = range(94_000, 94_160)
    low_rows = _sample(
        base,
        seeds,
        scenario="execution:20",
        builder=lambda seed: build_execution_snapshot(base, 20, seed=seed),
    )
    high_rows = _sample(
        base,
        seeds,
        scenario="execution:100",
        builder=lambda seed: build_execution_snapshot(base, 100, seed=seed),
    )
    low = summarize_execution_point(low_rows, score=20)
    high = summarize_execution_point(high_rows, score=100)

    assert high.home_points_per_match > low.home_points_per_match + 0.30
    assert high.home_possession_pct > low.home_possession_pct + 3.0
    assert high.home_pass_completion_pct > low.home_pass_completion_pct + 1.5
    assert high.home_shots_per_match > low.home_shots_per_match + 1.0
    assert high.home_xg_per_match > low.home_xg_per_match + 0.20


def test_tactical_ablations_move_the_process_they_are_supposed_to_control() -> None:
    base = _base()
    seeds = range(95_000, 95_140)

    def delta(name: str):
        definition = tactical_ablation(name)
        control = _sample(
            base,
            seeds,
            scenario=f"{name}:control",
            builder=lambda seed: build_tactical_snapshot(base, definition, treatment=False, seed=seed),
        )
        treatment = _sample(
            base,
            seeds,
            scenario=f"{name}:treatment",
            builder=lambda seed: build_tactical_snapshot(base, definition, treatment=True, seed=seed),
        )
        return summarize_tactical_delta(control, treatment, name=name)

    possession = delta("possession")
    directness = delta("directness")
    pressing = delta("pressing")
    crossing = delta("crossing_frequency")

    assert possession.home_possession_pp_delta > 0.8
    assert possession.home_pass_completion_pp_delta > 1.0
    assert directness.home_pass_completion_pp_delta < -1.0
    assert pressing.home_fouls_delta > 0.3
    assert pressing.away_pass_completion_pp_delta < -1.0
    assert crossing.home_corners_delta > 0.2



def test_tactical_matchups_create_real_counters_without_changing_player_quality() -> None:
    base = _base()
    seeds = range(94_500, 94_700)
    results = {}
    for definition in FAST_TACTICAL_MATCHUPS:
        difficult = _sample(
            base,
            seeds,
            scenario=f"matchup:{definition.name}:difficult",
            builder=lambda seed, definition=definition: build_tactical_matchup_snapshot(
                base, definition, favorable=False, seed=seed
            ),
        )
        favorable = _sample(
            base,
            seeds,
            scenario=f"matchup:{definition.name}:favorable",
            builder=lambda seed, definition=definition: build_tactical_matchup_snapshot(
                base, definition, favorable=True, seed=seed
            ),
        )
        results[definition.name] = summarize_tactical_matchup_delta(
            difficult, favorable, name=definition.name
        )

    assert results["direct_vs_line"].home_points_delta > 0.15
    assert results["direct_vs_line"].xg_diff_delta > 0.20
    assert results["possession_vs_press"].home_points_delta > 0.25
    assert results["possession_vs_press"].home_pass_completion_pp_delta > 2.0
    assert results["press_vs_build"].home_points_delta > 0.25
    assert results["press_vs_build"].xg_diff_delta > 0.40
    assert results["wide_vs_compact"].shot_diff_delta > 0.80


def test_no_single_tactical_instruction_receives_a_hidden_universal_win_bonus() -> None:
    base = _base()
    seeds = range(95_500, 95_680)

    # High pressing is favorable against possession build-up...
    press_definition = next(item for item in FAST_TACTICAL_MATCHUPS if item.name == "press_vs_build")
    difficult = _sample(
        base,
        seeds,
        scenario="press-vs-direct",
        builder=lambda seed: build_tactical_matchup_snapshot(
            base, press_definition, favorable=False, seed=seed
        ),
    )
    favorable = _sample(
        base,
        seeds,
        scenario="press-vs-possession",
        builder=lambda seed: build_tactical_matchup_snapshot(
            base, press_definition, favorable=True, seed=seed
        ),
    )
    press_delta = summarize_tactical_matchup_delta(difficult, favorable, name="press_context")

    # ...so the same pressing plan cannot be modeled as a flat team-strength bonus.
    assert press_delta.home_points_delta > 0.25
    assert press_delta.xg_diff_delta > 0.35

def test_mixed_batch_combines_quality_act_tactics_and_execution_without_breaking_totals() -> None:
    base = _base()
    seeds = range(96_000, 96_240)
    neutral = summarize_fast_samples(_sample(base, seeds, scenario="neutral"))
    mixed = summarize_fast_samples(
        _sample(
            base,
            seeds,
            scenario="mixed",
            builder=lambda seed: build_mixed_snapshot(base, seed=seed),
        )
    )

    assert 2.2 <= mixed.goals_per_match <= 3.4
    assert 21.0 <= mixed.shots_per_match <= 30.0
    assert abs(mixed.goals_minus_xg_per_match) <= 0.35
    assert mixed.xg_diff_1plus_pct >= neutral.xg_diff_1plus_pct
    assert mixed.home_win_pct > 0.0 and mixed.away_win_pct > 0.0 and mixed.draw_pct > 0.0


def test_synthetic_20_team_league_has_quality_signal_without_predetermined_table() -> None:
    standings, summary = simulate_synthetic_league(
        _base(),
        teams=20,
        seed_start=97_000,
    )

    assert len(standings) == 20
    assert summary.matches == 380
    assert summary.rank_quality_correlation > 0.60
    assert summary.top_half_mean_quality > summary.bottom_half_mean_quality
    assert summary.strongest_team_rank <= 6
    assert any(row.quality_delta < 0 for row in standings[:10])
    assert any(row.quality_delta > 0 for row in standings[10:])



def test_better_coach_can_compensate_for_a_plus_ten_quality_gap_without_flat_bonus() -> None:
    base = _base()
    simulator = FastMatchSimulator()
    summaries = {}

    for scenario in FAST_COACH_VS_SQUAD_SCENARIOS:
        rows = []
        for index in range(160):
            for leg, weaker_home in enumerate((False, True)):
                seed = 98_000 + index * 2 + leg
                snapshot = build_coach_vs_squad_snapshot(
                    base,
                    scenario,
                    seed=seed,
                    weaker_home=weaker_home,
                )
                sample = run_fast_calibration_match(
                    snapshot,
                    scenario=f"coach:{scenario}",
                    seed=seed,
                    simulator=simulator,
                )
                rows.append((sample, weaker_home))
        summaries[scenario] = summarize_coach_vs_squad(rows, scenario=scenario)

    baseline = summaries["quality_baseline"]
    better = summaries["better_coach"]
    wrong = summaries["wrong_plan"]

    # +10 quality must make the weaker side a clear underdog before coaching.
    assert baseline.weaker_points_per_match < 1.05
    assert baseline.weaker_xg_diff_per_match < -0.45

    # A strong counter-plan with high execution can erase most/all of that gap.
    assert better.weaker_points_per_match > baseline.weaker_points_per_match + 0.35
    assert better.weaker_xg_diff_per_match > baseline.weaker_xg_diff_per_match + 0.55
    assert better.weaker_win_pct >= 30.0
    assert better.weaker_xg_share_pct >= 48.0

    # High execution alone is not a hidden bonus: the wrong plan remains poor.
    assert better.weaker_points_per_match > wrong.weaker_points_per_match + 0.35
    assert better.weaker_xg_diff_per_match > wrong.weaker_xg_diff_per_match + 0.55
    assert wrong.weaker_points_per_match < 1.05


def test_fast_calibration_code_has_no_dependency_on_legacy_spatial_engine() -> None:
    package = Path("src/football_manager/fast_calibration")
    source = "\n".join(path.read_text(encoding="utf-8") for path in package.glob("*.py"))

    assert "football_manager.simulation" not in source
    assert "SpatialMatchEngine" not in source
    assert "MatchFlowController" not in source
