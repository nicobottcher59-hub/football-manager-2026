from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from .ablation import AblationSummary, TacticalAblation
from .metrics import CalibrationSample
from .reporting import write_csv_report
from .strength import StrengthCurveDiagnostics, StrengthCurvePoint


def _fmt(value: float | None, digits: int = 2) -> str:
    if value is None:
        return "-"
    return f"{value:.{digits}f}"


def write_strength_reports(
    output_dir: str | Path,
    *,
    run_id: str,
    commit: str,
    dirty: bool,
    samples: tuple[CalibrationSample, ...],
    points: tuple[StrengthCurvePoint, ...],
    diagnostics: StrengthCurveDiagnostics,
) -> tuple[Path, Path, Path, Path]:
    directory = Path(output_dir)
    matches = write_csv_report(directory / f"{run_id}_strength_matches.csv", (item.to_row() for item in samples))
    curve = write_csv_report(directory / f"{run_id}_strength_curve.csv", (item.to_row() for item in points))
    diag = write_csv_report(directory / f"{run_id}_strength_diagnostics.csv", (diagnostics.to_row(),))
    markdown = directory / f"{run_id}_strength.md"
    markdown.parent.mkdir(parents=True, exist_ok=True)

    lines = [
        "# Phase 5.10C strength-curve report",
        "",
        f"- Commit: `{commit}`",
        f"- Working tree dirty: `{str(dirty).lower()}`",
        f"- Generated (UTC): `{datetime.now(timezone.utc).isoformat(timespec='seconds')}`",
        "- Squads: mirrored heterogeneous profiles; only the controlled team-strength delta changes.",
        "",
        "| Gap | N | Home PPG | GD | xG diff | Home xG share | H/D/A % | Underdog win | Favorite non-win |",
        "|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for item in points:
        lines.append(
            f"| {item.strength_gap:+d} | {item.matches} | {_fmt(item.home_points_per_match)} | "
            f"{_fmt(item.home_goal_diff_per_match)} | {_fmt(item.home_xg_diff_per_match)} | "
            f"{_fmt(item.home_xg_share_pct, 1)}% | "
            f"{_fmt(item.home_win_pct, 1)}/{_fmt(item.draw_pct, 1)}/{_fmt(item.away_win_pct, 1)} | "
            f"{_fmt(item.underdog_win_pct, 1)}% | {_fmt(item.favorite_non_win_pct, 1)}% |"
        )

    lines.extend(
        [
            "",
            "## Diagnostics",
            "",
            f"- Home PPG slope per +10 attribute points: `{diagnostics.ppg_slope_per_10_points:.3f}`",
            f"- Home xG-difference slope per +10 attribute points: `{diagnostics.xg_diff_slope_per_10_points:.3f}`",
            f"- PPG monotonicity violations: `{diagnostics.ppg_monotonic_violations}`",
            f"- xG monotonicity violations: `{diagnostics.xg_monotonic_violations}`",
            f"- Largest adjacent PPG jump: `{diagnostics.largest_adjacent_ppg_jump:.3f}`",
            f"- Largest adjacent xG-diff jump: `{diagnostics.largest_adjacent_xg_jump:.3f}`",
            "",
            "> Small samples are noisy. Use this report to detect gross hypersensitivity and regressions; "
            "final strength tuning belongs to Phase 5.10D.",
            "",
        ]
    )
    markdown.write_text("\n".join(lines), encoding="utf-8")
    return matches, curve, diag, markdown


def write_ablation_reports(
    output_dir: str | Path,
    *,
    run_id: str,
    commit: str,
    dirty: bool,
    definitions: tuple[TacticalAblation, ...],
    samples: tuple[CalibrationSample, ...],
    summaries: tuple[AblationSummary, ...],
) -> tuple[Path, Path, Path]:
    directory = Path(output_dir)
    matches = write_csv_report(directory / f"{run_id}_ablation_matches.csv", (item.to_row() for item in samples))
    summary = write_csv_report(directory / f"{run_id}_ablation_summary.csv", (item.to_row() for item in summaries))
    markdown = directory / f"{run_id}_ablation.md"
    markdown.parent.mkdir(parents=True, exist_ok=True)
    by_name = {item.name: item for item in definitions}

    lines = [
        "# Phase 5.10C tactical-ablation report",
        "",
        f"- Commit: `{commit}`",
        f"- Working tree dirty: `{str(dirty).lower()}`",
        f"- Generated (UTC): `{datetime.now(timezone.utc).isoformat(timespec='seconds')}`",
        "- Every control/treatment pair uses identical teams and the same seed.",
        "",
        "| Ablation | N/variant | PPG Δ | Poss pp Δ | Passes Δ | Pass% pp Δ | Shots Δ | xG Δ | Crosses Δ | Tackles Δ | Recov Δ | Fouls Δ | Opp pass% pp Δ | Changed seeds |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for item in summaries:
        lines.append(
            f"| {item.ablation} | {item.matches_per_variant} | {_fmt(item.home_points_delta)} | "
            f"{_fmt(item.home_possession_pp_delta)} | {_fmt(item.home_passes_attempted_delta)} | "
            f"{_fmt(item.home_pass_completion_pp_delta)} | {_fmt(item.home_shots_delta)} | "
            f"{_fmt(item.home_xg_delta)} | {_fmt(item.home_crosses_delta)} | "
            f"{_fmt(item.home_tackles_delta)} | {_fmt(item.home_recoveries_delta)} | "
            f"{_fmt(item.home_fouls_delta)} | {_fmt(item.away_pass_completion_pp_delta)} | "
            f"{_fmt(item.seeds_with_any_material_change_pct, 1)}% |"
        )

    lines.extend(["", "## Definitions", ""])
    for item in summaries:
        definition = by_name[item.ablation]
        lines.append(
            f"- `{definition.name}` — `{definition.section}.{definition.field}`: "
            f"`{definition.control_value}` -> `{definition.treatment_value}`. "
            f"Expected signal: {definition.expected_signal}."
        )
    lines.extend(
        [
            "",
            "> An ablation that repeatedly produces no measurable change is a candidate for wiring review, "
            "not immediate coefficient inflation. Phase 5.10C measures whether the instruction reaches the engine.",
            "",
        ]
    )
    markdown.write_text("\n".join(lines), encoding="utf-8")
    return matches, summary, markdown
