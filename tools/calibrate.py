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
    DEFAULT_BENCHMARK_SCENARIOS,
    CalibrationSample,
    benchmark_scenario,
    build_benchmark_snapshot,
    calibration_run_id,
    evaluate_targets,
    summarize_samples,
    write_calibration_reports,
    run_calibration_match,
    git_metadata,
)


def _run_job(job: tuple[str, int, bool]) -> CalibrationSample:
    scenario_name, seed, smoke = job
    scenario = benchmark_scenario(scenario_name)
    base = build_demo_snapshot(seed=seed)
    snapshot = build_benchmark_snapshot(base, scenario, seed=seed)
    return run_calibration_match(
        snapshot,
        scenario=scenario_name,
        seed=seed,
        smoke=smoke,
    )


def _parser() -> argparse.ArgumentParser:
    names = tuple(item.name for item in DEFAULT_BENCHMARK_SCENARIOS)
    parser = argparse.ArgumentParser(
        description="Phase 5.10B deterministic Match Engine calibration and event-integrity harness.",
    )
    parser.add_argument(
        "--matches",
        type=int,
        default=8,
        help="number of matches per scenario (default: 8)",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=min(4, os.cpu_count() or 1),
        help="parallel worker processes (default: min(4, CPU count))",
    )
    parser.add_argument(
        "--seed-start",
        type=int,
        default=510_000,
        help="first deterministic seed; the same seed set is reused across scenarios",
    )
    parser.add_argument(
        "--scenarios",
        nargs="+",
        choices=names,
        default=list(names),
        help="controlled benchmark scenarios to run",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=ROOT / "reports" / "calibration",
        help="directory for CSV/Markdown reports",
    )
    parser.add_argument(
        "--smoke",
        action="store_true",
        help="run very short periods to verify the harness only; results are not calibration data",
    )
    return parser


def _validate_args(args: argparse.Namespace) -> None:
    if args.matches <= 0:
        raise SystemExit("--matches must be positive")
    if args.workers <= 0:
        raise SystemExit("--workers must be positive")
    if args.seed_start < 0:
        raise SystemExit("--seed-start cannot be negative")
    if len(set(args.scenarios)) != len(args.scenarios):
        raise SystemExit("--scenarios cannot contain duplicates")


def _print_summary(summaries, evaluations, *, smoke: bool) -> None:
    print("\nPHASE 5.10B - CALIBRATION + EVENT INTEGRITY")
    print("=" * 104)
    if smoke:
        print("SMOKE MODE: short periods; do not interpret these figures as football calibration data.")
        print("-" * 104)
    print(
        f"{'scenario':<19} {'N':>4} {'G':>6} {'shots':>7} {'SOT':>6} {'xG':>7} "
        f"{'G-xG':>7} {'pass%':>7} {'fouls':>7} {'YC':>6} {'corners':>8} {'H/D/A':>18} {'evt!':>6} {'sec':>7}"
    )
    for item in summaries:
        hda = f"{item.home_win_pct:.0f}/{item.draw_pct:.0f}/{item.away_win_pct:.0f}"
        print(
            f"{item.scenario:<19} {item.matches:>4d} {item.goals_per_match:>6.2f} "
            f"{item.shots_per_match:>7.2f} {item.shots_on_target_per_match:>6.2f} "
            f"{item.xg_per_match:>7.2f} {item.goals_minus_xg_per_match:>7.2f} "
            f"{item.pass_completion_pct:>7.1f} {item.fouls_per_match:>7.2f} "
            f"{item.yellow_cards_per_match:>6.2f} {item.corners_per_match:>8.2f} "
            f"{hda:>18} {item.event_integrity_issues:>6d} {item.mean_elapsed_seconds:>7.2f}"
        )

    if evaluations:
        print("\nNeutral target check (broad initial bands):")
        for item in evaluations:
            print(
                f"  {item.status:>4}  {item.label:<20} "
                f"{item.value:>7.2f}{item.unit:<1}   target {item.low:.2f}-{item.high:.2f}{item.unit}"
            )


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    _validate_args(args)

    scenarios = tuple(benchmark_scenario(name) for name in args.scenarios)
    seeds = tuple(args.seed_start + index for index in range(args.matches))
    jobs = tuple((scenario.name, seed, args.smoke) for scenario in scenarios for seed in seeds)

    print(
        f"Running {len(jobs)} matches: {args.matches} per scenario, "
        f"{args.workers} worker(s), seeds {seeds[0]}..{seeds[-1]}"
    )
    if args.smoke:
        print("Smoke mode enabled: target evaluation will be skipped.")

    if args.workers == 1:
        samples = tuple(_run_job(job) for job in jobs)
    else:
        with ProcessPoolExecutor(max_workers=args.workers) as executor:
            samples = tuple(executor.map(_run_job, jobs))

    samples = tuple(sorted(samples, key=lambda item: (item.scenario, item.seed)))
    summaries = tuple(
        summarize_samples(item for item in samples if item.scenario == scenario.name)
        for scenario in scenarios
    )
    equal_summary = next((item for item in summaries if item.scenario == "equal"), None)
    evaluations = (
        evaluate_targets(equal_summary)
        if equal_summary is not None and not args.smoke
        else ()
    )

    commit, dirty = git_metadata(ROOT)
    run_id = calibration_run_id(commit=commit)
    paths = write_calibration_reports(
        args.output_dir,
        run_id=run_id,
        commit=commit,
        dirty=dirty,
        scenarios=scenarios,
        samples=samples,
        summaries=summaries,
        target_evaluations=evaluations,
    )

    _print_summary(summaries, evaluations, smoke=args.smoke)
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
