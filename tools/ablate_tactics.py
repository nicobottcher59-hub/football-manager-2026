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
    DEFAULT_TACTICAL_ABLATIONS,
    CalibrationSample,
    build_ablation_snapshot,
    calibration_run_id,
    git_metadata,
    run_calibration_match,
    summarize_ablation,
    tactical_ablation,
    write_ablation_reports,
)


def _run_job(job: tuple[str, str, int, bool]) -> CalibrationSample:
    ablation_name, variant, seed, smoke = job
    definition = tactical_ablation(ablation_name)
    base = build_demo_snapshot(seed=seed)
    snapshot = build_ablation_snapshot(base, definition, variant=variant, seed=seed)
    return run_calibration_match(
        snapshot,
        scenario=f"{ablation_name}:{variant}",
        seed=seed,
        smoke=smoke,
    )


def _parser() -> argparse.ArgumentParser:
    names = tuple(item.name for item in DEFAULT_TACTICAL_ABLATIONS)
    parser = argparse.ArgumentParser(
        description="Phase 5.10C paired tactical-ablation experiment.",
    )
    parser.add_argument("--matches", type=int, default=4, help="matches per control/treatment variant (default: 4)")
    parser.add_argument(
        "--workers",
        type=int,
        default=min(4, os.cpu_count() or 1),
        help="parallel worker processes (default: min(4, CPU count))",
    )
    parser.add_argument("--seed-start", type=int, default=510_500)
    parser.add_argument(
        "--ablations",
        nargs="+",
        choices=names,
        default=list(names),
        help="instructions to compare; each changes exactly one team-instruction field",
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
    if len(set(args.ablations)) != len(args.ablations):
        raise SystemExit("--ablations cannot contain duplicates")


def _print(summaries, *, smoke: bool) -> None:
    print("\nPHASE 5.10C - TACTICAL ABLATION")
    print("=" * 132)
    if smoke:
        print("SMOKE MODE: short periods; use only to verify wiring.")
        print("-" * 132)
    print(
        f"{'ablation':<20} {'N':>4} {'PPGd':>6} {'Possd':>7} {'Passd':>7} {'Pass%d':>8} "
        f"{'Shotd':>7} {'xGd':>7} {'Crossd':>7} {'Tackd':>7} {'Recovd':>7} {'Fould':>7} {'OppPass%d':>10} {'changed':>9}"
    )
    for item in summaries:
        print(
            f"{item.ablation:<20} {item.matches_per_variant:>4d} {item.home_points_delta:>+6.2f} "
            f"{item.home_possession_pp_delta:>+7.2f} {item.home_passes_attempted_delta:>+7.2f} "
            f"{item.home_pass_completion_pp_delta:>+8.2f} {item.home_shots_delta:>+7.2f} "
            f"{item.home_xg_delta:>+7.2f} {item.home_crosses_delta:>+7.2f} "
            f"{item.home_tackles_delta:>+7.2f} {item.home_recoveries_delta:>+7.2f} "
            f"{item.home_fouls_delta:>+7.2f} {item.away_pass_completion_pp_delta:>+10.2f} "
            f"{item.seeds_with_any_material_change_pct:>8.1f}%"
        )


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    _validate(args)
    definitions = tuple(tactical_ablation(name) for name in args.ablations)
    seeds = tuple(args.seed_start + index for index in range(args.matches))
    jobs = tuple(
        (definition.name, variant, seed, args.smoke)
        for definition in definitions
        for variant in ("control", "treatment")
        for seed in seeds
    )
    print(
        f"Running {len(jobs)} ablation matches: {args.matches} per variant, "
        f"{args.workers} worker(s), seeds {seeds[0]}..{seeds[-1]}"
    )

    if args.workers == 1:
        samples = tuple(_run_job(job) for job in jobs)
    else:
        with ProcessPoolExecutor(max_workers=args.workers) as executor:
            samples = tuple(executor.map(_run_job, jobs))
    samples = tuple(sorted(samples, key=lambda item: (item.scenario, item.seed)))
    summaries = tuple(
        summarize_ablation(
            (item for item in samples if item.scenario == f"{definition.name}:control"),
            (item for item in samples if item.scenario == f"{definition.name}:treatment"),
            name=definition.name,
        )
        for definition in definitions
    )

    commit, dirty = git_metadata(ROOT)
    run_id = calibration_run_id(commit=commit)
    paths = write_ablation_reports(
        args.output_dir,
        run_id=run_id,
        commit=commit,
        dirty=dirty,
        definitions=definitions,
        samples=samples,
        summaries=summaries,
    )
    _print(summaries, smoke=args.smoke)
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
