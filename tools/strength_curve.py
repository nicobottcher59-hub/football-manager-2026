from __future__ import annotations

import argparse
import os
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
for path in (str(SRC), str(ROOT)):
    if path not in sys.path:
        sys.path.insert(0, path)

from examples.demo_match_factory import build_demo_snapshot
from football_manager.calibration import (
    STRENGTH_CURVE_SCENARIOS,
    CalibrationSample,
    build_strength_curve_snapshot,
    calibration_run_id,
    diagnose_strength_curve,
    git_metadata,
    run_calibration_match,
    strength_curve_scenario,
    summarize_strength_point,
    write_strength_reports,
)


def _run_job(job: tuple[str, int, bool]) -> CalibrationSample:
    scenario_name, seed, smoke = job
    scenario = strength_curve_scenario(scenario_name)
    base = build_demo_snapshot(seed=seed)
    snapshot = build_strength_curve_snapshot(base, scenario, seed=seed)
    return run_calibration_match(
        snapshot,
        scenario=scenario_name,
        seed=seed,
        smoke=smoke,
    )


def _parser() -> argparse.ArgumentParser:
    names = tuple(item.name for item in STRENGTH_CURVE_SCENARIOS)
    parser = argparse.ArgumentParser(
        description="Phase 5.10C paired-seed strength-curve experiment.",
    )
    parser.add_argument("--matches", type=int, default=4, help="matches per strength point (default: 4)")
    parser.add_argument(
        "--workers",
        type=int,
        default=min(4, os.cpu_count() or 1),
        help="parallel worker processes (default: min(4, CPU count))",
    )
    parser.add_argument("--seed-start", type=int, default=510_300)
    parser.add_argument(
        "--scenarios",
        nargs="+",
        choices=names,
        default=list(names),
        help="strength points to include; default is the full -20..+20 curve",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=ROOT / "reports" / "calibration",
    )
    parser.add_argument("--smoke", action="store_true", help="short periods for harness verification only")
    return parser


def _validate(args: argparse.Namespace) -> None:
    if args.matches <= 0:
        raise SystemExit("--matches must be positive")
    if args.workers <= 0:
        raise SystemExit("--workers must be positive")
    if args.seed_start < 0:
        raise SystemExit("--seed-start cannot be negative")
    if len(set(args.scenarios)) != len(args.scenarios):
        raise SystemExit("--scenarios cannot contain duplicates")
    if len(args.scenarios) < 2:
        raise SystemExit("strength curve requires at least two scenarios")


def _print(points, diagnostics, *, smoke: bool) -> None:
    print("\nPHASE 5.10C - STRENGTH CURVE")
    print("=" * 102)
    if smoke:
        print("SMOKE MODE: short periods; do not interpret outcome rates as football calibration data.")
        print("-" * 102)
    print(
        f"{'gap':>5} {'N':>4} {'PPG':>6} {'GD':>7} {'xGD':>7} {'xGshare':>8} "
        f"{'H/D/A':>18} {'upset%':>8} {'fav nonwin%':>11}"
    )
    for item in sorted(points, key=lambda row: row.strength_gap):
        hda = f"{item.home_win_pct:.0f}/{item.draw_pct:.0f}/{item.away_win_pct:.0f}"
        upset = "-" if item.underdog_win_pct is None else f"{item.underdog_win_pct:.1f}"
        nonwin = "-" if item.favorite_non_win_pct is None else f"{item.favorite_non_win_pct:.1f}"
        print(
            f"{item.strength_gap:>+5d} {item.matches:>4d} {item.home_points_per_match:>6.2f} "
            f"{item.home_goal_diff_per_match:>7.2f} {item.home_xg_diff_per_match:>7.2f} "
            f"{item.home_xg_share_pct:>7.1f}% {hda:>18} {upset:>8} {nonwin:>11}"
        )
    print("\nCurve diagnostics:")
    print(f"  Home PPG slope / +10 attributes: {diagnostics.ppg_slope_per_10_points:+.3f}")
    print(f"  Home xG diff slope / +10:       {diagnostics.xg_diff_slope_per_10_points:+.3f}")
    print(f"  PPG monotonic violations:        {diagnostics.ppg_monotonic_violations}")
    print(f"  xG monotonic violations:         {diagnostics.xg_monotonic_violations}")
    print(f"  Largest adjacent PPG jump:       {diagnostics.largest_adjacent_ppg_jump:.3f}")
    print(f"  Largest adjacent xG jump:        {diagnostics.largest_adjacent_xg_jump:.3f}")


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    _validate(args)
    scenarios = tuple(strength_curve_scenario(name) for name in args.scenarios)
    seeds = tuple(args.seed_start + index for index in range(args.matches))
    jobs = tuple((scenario.name, seed, args.smoke) for scenario in scenarios for seed in seeds)
    print(
        f"Running {len(jobs)} strength matches: {args.matches} per point, "
        f"{args.workers} worker(s), seeds {seeds[0]}..{seeds[-1]}"
    )

    if args.workers == 1:
        samples = tuple(_run_job(job) for job in jobs)
    else:
        with ProcessPoolExecutor(max_workers=args.workers) as executor:
            samples = tuple(executor.map(_run_job, jobs))
    samples = tuple(sorted(samples, key=lambda item: (item.scenario, item.seed)))
    points = tuple(
        summarize_strength_point(
            (item for item in samples if item.scenario == scenario.name),
            strength_gap=scenario.strength_gap,
        )
        for scenario in scenarios
    )
    diagnostics = diagnose_strength_curve(points)
    commit, dirty = git_metadata(ROOT)
    run_id = calibration_run_id(commit=commit)
    paths = write_strength_reports(
        args.output_dir,
        run_id=run_id,
        commit=commit,
        dirty=dirty,
        samples=samples,
        points=tuple(sorted(points, key=lambda item: item.strength_gap)),
        diagnostics=diagnostics,
    )
    _print(points, diagnostics, smoke=args.smoke)
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
