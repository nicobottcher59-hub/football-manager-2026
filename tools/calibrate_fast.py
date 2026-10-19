from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
for path in (str(SRC), str(ROOT)):
    if path not in sys.path:
        sys.path.insert(0, path)

from examples.demo_match_factory import build_demo_snapshot
from football_manager.fast_calibration import (
    FAST_ACT_GAPS,
    FAST_COACH_VS_SQUAD_SCENARIOS,
    FAST_EXECUTION_LEVELS,
    FAST_STRENGTH_GAPS,
    FAST_TACTICAL_ABLATIONS,
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
    fast_calibration_run_id,
    git_metadata,
    neutralize_fast_snapshot,
    run_fast_calibration_match,
    simulate_synthetic_league,
    summarize_coach_vs_squad,
    summarize_curve_point,
    summarize_execution_point,
    summarize_fast_samples,
    summarize_tactical_delta,
    summarize_tactical_matchup_delta,
    write_fast_calibration_reports,
)
from football_manager.fast_simulation import FastMatchSimulator


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Phase 5.11C Fast Match Simulator calibration and balance suite.",
    )
    parser.add_argument(
        "--matches",
        type=int,
        default=200,
        help="samples per baseline/curve/tactical scenario (default: 200)",
    )
    parser.add_argument("--seed-start", type=int, default=511_300)
    parser.add_argument("--league-teams", type=int, default=20)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=ROOT / "reports" / "fast_calibration",
    )
    return parser


def _validate(args: argparse.Namespace) -> None:
    if args.matches <= 0:
        raise SystemExit("--matches must be positive")
    if args.seed_start < 0:
        raise SystemExit("--seed-start cannot be negative")
    if args.league_teams < 4:
        raise SystemExit("--league-teams must be at least 4")


def _samples(base, *, scenario: str, seeds, builder=None):
    simulator = FastMatchSimulator()
    rows = []
    for seed in seeds:
        snapshot = builder(seed) if builder is not None else base
        if builder is None:
            snapshot = snapshot.__class__(
                match_id=f"{base.match_id}-{scenario}-{seed}",
                seed=seed,
                context=base.context,
                home_team=base.home_team,
                away_team=base.away_team,
            )
        rows.append(
            run_fast_calibration_match(
                snapshot,
                scenario=scenario,
                seed=seed,
                simulator=simulator,
            )
        )
    return tuple(rows)


def _print_baseline(summary, targets) -> None:
    print("\nFAST SIMULATOR - NEUTRAL 70 v 70")
    print("=" * 88)
    print(
        f"N={summary.matches} | goals={summary.goals_per_match:.2f} | shots={summary.shots_per_match:.2f} | "
        f"SOT={summary.shots_on_target_per_match:.2f} | xG={summary.xg_per_match:.2f} | "
        f"G-xG={summary.goals_minus_xg_per_match:+.2f}"
    )
    print(
        f"pass={summary.pass_completion_pct:.1f}% | fouls={summary.fouls_per_match:.2f} | "
        f"YC={summary.yellow_cards_per_match:.2f} | corners={summary.corners_per_match:.2f} | "
        f"H/D/A={summary.home_win_pct:.1f}/{summary.draw_pct:.1f}/{summary.away_win_pct:.1f}"
    )
    print(
        f"0-0={summary.scoreless_pct:.1f}% | BTTS={summary.both_teams_score_pct:.1f}% | "
        f"4+G={summary.four_plus_goals_pct:.1f}% | 3+ margin={summary.margin_three_plus_pct:.1f}% | "
        f"shot diff >=10={summary.shot_diff_10plus_pct:.1f}% | xG diff >=1={summary.xg_diff_1plus_pct:.1f}%"
    )
    print(f"throughput={summary.matches_per_second:.1f} matches/sec")
    problems = [item for item in targets if item.status != "OK"]
    if problems:
        print("target checks:")
        for item in problems:
            print(
                f"  {item.status:<4} {item.label}: {item.value:.2f}{item.unit} "
                f"(target {item.low:.2f}-{item.high:.2f}{item.unit})"
            )
    else:
        print("target checks: all neutral target bands OK")


def _print_curve(title, points, diagnostics, *, execution: bool = False) -> None:
    print(f"\n{title}")
    print("=" * 88)
    label = "score" if execution else "gap"
    print(f"{label:>7} {'N':>5} {'PPG':>6} {'GD':>7} {'xGD':>7} {'xGshare':>8} {'H/D/A':>16} {'upset':>8}")
    for point in points:
        hda = f"{point.home_win_pct:.0f}/{point.draw_pct:.0f}/{point.away_win_pct:.0f}"
        upset = "-" if point.underdog_win_pct is None else f"{point.underdog_win_pct:.1f}%"
        value = f"{point.value:.0f}" if execution else f"{point.value:+.0f}"
        print(
            f"{value:>7} {point.matches:>5} {point.home_points_per_match:>6.2f} "
            f"{point.home_goal_diff_per_match:>+7.2f} {point.home_xg_diff_per_match:>+7.2f} "
            f"{point.home_xg_share_pct:>7.1f}% {hda:>16} {upset:>8}"
        )
    print(
        f"slope PPG/+10={diagnostics.ppg_slope_per_10:+.3f} | "
        f"xGD/+10={diagnostics.xg_diff_slope_per_10:+.3f} | "
        f"monotonic violations PPG/xGD={diagnostics.ppg_monotonic_violations}/{diagnostics.xg_monotonic_violations}"
    )


def _print_tactics(items) -> None:
    print("\nTACTICAL ABLATIONS - ONE CHANGE AT A TIME")
    print("=" * 108)
    print(
        f"{'change':<22} {'PPGd':>7} {'Possd':>8} {'Pass%d':>8} {'Shotd':>8} "
        f"{'xGd':>8} {'Fould':>8} {'Cornd':>8} {'OppPass%d':>10}"
    )
    for item in items:
        print(
            f"{item.name:<22} {item.home_points_delta:>+7.2f} {item.home_possession_pp_delta:>+8.2f} "
            f"{item.home_pass_completion_pp_delta:>+8.2f} {item.home_shots_delta:>+8.2f} "
            f"{item.home_xg_delta:>+8.2f} {item.home_fouls_delta:>+8.2f} "
            f"{item.home_corners_delta:>+8.2f} {item.away_pass_completion_pp_delta:>+10.2f}"
        )


def _print_tactical_matchups(items) -> None:
    print("\nTACTICAL MATCHUPS - SAME QUALITY, DIFFERENT OPPONENT FIT")
    print("=" * 120)
    print(
        f"{'matchup':<22} {'PPGd':>7} {'xGd':>8} {'OppxGd':>9} {'xGDd':>8} "
        f"{'ShotDd':>8} {'Possd':>8} {'Pass%d':>8} {'OppPass%d':>10}"
    )
    for item in items:
        print(
            f"{item.name:<22} {item.home_points_delta:>+7.2f} {item.home_xg_delta:>+8.2f} "
            f"{item.away_xg_delta:>+9.2f} {item.xg_diff_delta:>+8.2f} {item.shot_diff_delta:>+8.2f} "
            f"{item.home_possession_pp_delta:>+8.2f} {item.home_pass_completion_pp_delta:>+8.2f} "
            f"{item.away_pass_completion_pp_delta:>+10.2f}"
        )



def _print_coach_vs_squad(items) -> None:
    print("\nCOACH VS SQUAD QUALITY - WEAKER TEAM POV")
    print("=" * 104)
    print(
        f"{'scenario':<20} {'PPG':>6} {'W/D/L':>17} {'GD':>8} {'xGD':>8} "
        f"{'ShotD':>8} {'xGshare':>9}"
    )
    for item in items:
        wdl = f"{item.weaker_win_pct:.1f}/{item.draw_pct:.1f}/{item.stronger_win_pct:.1f}"
        print(
            f"{item.scenario:<20} {item.weaker_points_per_match:>6.2f} {wdl:>17} "
            f"{item.weaker_goal_diff_per_match:>+8.2f} {item.weaker_xg_diff_per_match:>+8.2f} "
            f"{item.weaker_shot_diff_per_match:>+8.2f} {item.weaker_xg_share_pct:>8.1f}%"
        )
    by_name = {item.scenario: item for item in items}
    baseline = by_name["quality_baseline"]
    better = by_name["better_coach"]
    wrong = by_name["wrong_plan"]
    print(
        "coach lift vs quality baseline: "
        f"PPG {better.weaker_points_per_match - baseline.weaker_points_per_match:+.2f} | "
        f"xGD {better.weaker_xg_diff_per_match - baseline.weaker_xg_diff_per_match:+.2f}"
    )
    print(
        "correct-plan lift vs equally well-executed wrong plan: "
        f"PPG {better.weaker_points_per_match - wrong.weaker_points_per_match:+.2f} | "
        f"xGD {better.weaker_xg_diff_per_match - wrong.weaker_xg_diff_per_match:+.2f}"
    )


def _print_league(standings, summary) -> None:
    print("\nSYNTHETIC LEAGUE")
    print("=" * 88)
    print(
        f"teams={summary.teams} | matches={summary.matches} | "
        f"throughput={summary.matches_per_second:.1f}/sec | quality-points r={summary.rank_quality_correlation:+.3f}"
    )
    print(
        f"strongest rank={summary.strongest_team_rank} | weakest rank={summary.weakest_team_rank} | "
        f"top-half quality={summary.top_half_mean_quality:+.1f} | bottom-half={summary.bottom_half_mean_quality:+.1f}"
    )
    print("top 5:")
    for rank, row in enumerate(standings[:5], start=1):
        print(
            f"  {rank:>2}. {row.team_id} q={row.quality_delta:+d} pts={row.points:>3} "
            f"GD={row.goal_difference:+d} W/D/L={row.won}/{row.drawn}/{row.lost}"
        )


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    _validate(args)
    base = neutralize_fast_snapshot(build_demo_snapshot(seed=args.seed_start), rating=70, seed=args.seed_start)
    seeds = tuple(args.seed_start + index for index in range(args.matches))

    baseline_samples = _samples(base, scenario="neutral", seeds=seeds)
    baseline = summarize_fast_samples(baseline_samples)
    targets = evaluate_fast_targets(baseline)
    _print_baseline(baseline, targets)

    mixed_samples = _samples(
        base,
        scenario="mixed",
        seeds=seeds,
        builder=lambda seed: build_mixed_snapshot(base, seed=seed),
    )
    mixed = summarize_fast_samples(mixed_samples)
    print("\nMIXED REALISTIC BATCH")
    print("=" * 88)
    print(
        f"N={mixed.matches} | goals={mixed.goals_per_match:.2f} | shots={mixed.shots_per_match:.2f} | "
        f"SOT={mixed.shots_on_target_per_match:.2f} | xG={mixed.xg_per_match:.2f} | "
        f"H/D/A={mixed.home_win_pct:.1f}/{mixed.draw_pct:.1f}/{mixed.away_win_pct:.1f}"
    )
    print(
        f"3+ margin={mixed.margin_three_plus_pct:.1f}% | shot diff >=10={mixed.shot_diff_10plus_pct:.1f}% | "
        f"xG diff >=1={mixed.xg_diff_1plus_pct:.1f}% | throughput={mixed.matches_per_second:.1f}/sec"
    )

    strength_points = []
    for gap in FAST_STRENGTH_GAPS:
        rows = _samples(
            base,
            scenario=f"strength:{gap:+d}",
            seeds=seeds,
            builder=lambda seed, gap=gap: build_strength_snapshot(base, gap, seed=seed),
        )
        strength_points.append(summarize_curve_point(rows, value=float(gap)))
    strength_points = tuple(strength_points)
    strength_diagnostics = diagnose_curve(strength_points)
    _print_curve("STRENGTH CURVE", strength_points, strength_diagnostics)

    act_points = []
    for gap in FAST_ACT_GAPS:
        rows = _samples(
            base,
            scenario=f"act:{gap:+d}",
            seeds=seeds,
            builder=lambda seed, gap=gap: build_act_snapshot(base, gap, seed=seed),
        )
        act_points.append(summarize_curve_point(rows, value=float(gap)))
    act_points = tuple(act_points)
    act_diagnostics = diagnose_curve(act_points)
    _print_curve("ACT / CURRENT-PERFORMANCE CURVE", act_points, act_diagnostics)

    execution_points = []
    for score in FAST_EXECUTION_LEVELS:
        rows = _samples(
            base,
            scenario=f"execution:{score}",
            seeds=seeds,
            builder=lambda seed, score=score: build_execution_snapshot(base, score, seed=seed),
        )
        execution_points.append(summarize_execution_point(rows, score=float(score)))
    execution_points = tuple(execution_points)
    print("\nTACTICAL EXECUTION / FAMILIARITY")
    print("=" * 108)
    print(
        f"{'score':>7} {'PPG':>6} {'Poss':>7} {'Pass%':>7} {'Shots':>7} "
        f"{'xG':>7} {'Fouls':>7} {'Corners':>8} {'OppPass%':>9}"
    )
    for point in execution_points:
        print(
            f"{point.score:>7.0f} {point.home_points_per_match:>6.2f} {point.home_possession_pct:>6.1f}% "
            f"{point.home_pass_completion_pct:>6.1f}% {point.home_shots_per_match:>7.2f} "
            f"{point.home_xg_per_match:>7.2f} {point.home_fouls_per_match:>7.2f} "
            f"{point.home_corners_per_match:>8.2f} {point.away_pass_completion_pct:>8.1f}%"
        )

    tactical_summaries = []
    for definition in FAST_TACTICAL_ABLATIONS:
        control = _samples(
            base,
            scenario=f"tactic:{definition.name}:control",
            seeds=seeds,
            builder=lambda seed, definition=definition: build_tactical_snapshot(
                base, definition, treatment=False, seed=seed
            ),
        )
        treatment = _samples(
            base,
            scenario=f"tactic:{definition.name}:treatment",
            seeds=seeds,
            builder=lambda seed, definition=definition: build_tactical_snapshot(
                base, definition, treatment=True, seed=seed
            ),
        )
        tactical_summaries.append(
            summarize_tactical_delta(control, treatment, name=definition.name)
        )
    tactical_summaries = tuple(tactical_summaries)
    _print_tactics(tactical_summaries)

    tactical_matchups = []
    for definition in FAST_TACTICAL_MATCHUPS:
        difficult = _samples(
            base,
            scenario=f"matchup:{definition.name}:difficult",
            seeds=seeds,
            builder=lambda seed, definition=definition: build_tactical_matchup_snapshot(
                base, definition, favorable=False, seed=seed
            ),
        )
        favorable = _samples(
            base,
            scenario=f"matchup:{definition.name}:favorable",
            seeds=seeds,
            builder=lambda seed, definition=definition: build_tactical_matchup_snapshot(
                base, definition, favorable=True, seed=seed
            ),
        )
        tactical_matchups.append(
            summarize_tactical_matchup_delta(difficult, favorable, name=definition.name)
        )
    tactical_matchups = tuple(tactical_matchups)
    _print_tactical_matchups(tactical_matchups)

    coach_vs_squad = []
    simulator = FastMatchSimulator()
    for scenario in FAST_COACH_VS_SQUAD_SCENARIOS:
        paired_rows = []
        for index, seed in enumerate(seeds):
            # Two legs per paired seed remove home-advantage noise while the
            # same derived seeds are reused across every scenario.
            for leg, weaker_home in enumerate((False, True)):
                derived_seed = args.seed_start + 200_000 + index * 2 + leg
                snapshot = build_coach_vs_squad_snapshot(
                    base,
                    scenario,
                    seed=derived_seed,
                    weaker_home=weaker_home,
                )
                row = run_fast_calibration_match(
                    snapshot,
                    scenario=f"coach:{scenario}",
                    seed=derived_seed,
                    simulator=simulator,
                )
                paired_rows.append((row, weaker_home))
        coach_vs_squad.append(
            summarize_coach_vs_squad(paired_rows, scenario=scenario)
        )
    coach_vs_squad = tuple(coach_vs_squad)
    _print_coach_vs_squad(coach_vs_squad)

    standings, league_summary = simulate_synthetic_league(
        base,
        teams=args.league_teams,
        seed_start=args.seed_start + 100_000,
    )
    _print_league(standings, league_summary)

    commit, dirty = git_metadata(ROOT)
    run_id = fast_calibration_run_id(commit=commit)
    paths = write_fast_calibration_reports(
        args.output_dir,
        run_id=run_id,
        commit=commit,
        dirty=dirty,
        baseline=baseline,
        mixed=mixed,
        targets=targets,
        strength_points=strength_points,
        strength_diagnostics=strength_diagnostics,
        act_points=act_points,
        act_diagnostics=act_diagnostics,
        execution_points=execution_points,
        tactical=tactical_summaries,
        tactical_matchups=tactical_matchups,
        coach_vs_squad=coach_vs_squad,
        league_standings=standings,
        league_summary=league_summary,
    )
    print("\nReports:")
    for path in paths:
        try:
            shown = path.relative_to(ROOT)
        except ValueError:
            shown = path
        print(f"  {shown}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
