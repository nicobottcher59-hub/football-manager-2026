from __future__ import annotations

import csv
from dataclasses import fields
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from .benchmarks import BenchmarkScenario
from .metrics import CalibrationSample, CalibrationSummary
from .targets import TargetEvaluation


def calibration_run_id(*, commit: str = "unknown", now: datetime | None = None) -> str:
    moment = now or datetime.now(timezone.utc)
    stamp = moment.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    safe_commit = "".join(ch for ch in commit if ch.isalnum() or ch in "-_.") or "unknown"
    return f"{stamp}_{safe_commit}"


def write_csv_report(
    path: str | Path,
    rows: Iterable[dict[str, object]],
) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    items = list(rows)
    if not items:
        raise ValueError("cannot write an empty CSV report")
    fieldnames = list(items[0])
    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(items)
    return output


def _fmt(value: float, digits: int = 2) -> str:
    return f"{value:.{digits}f}"


def write_markdown_report(
    path: str | Path,
    *,
    commit: str,
    dirty: bool,
    scenarios: tuple[BenchmarkScenario, ...],
    summaries: tuple[CalibrationSummary, ...],
    target_evaluations: tuple[TargetEvaluation, ...] = (),
) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    scenario_by_name = {scenario.name: scenario for scenario in scenarios}

    lines = [
        "# Match Engine calibration report",
        "",
        f"- Commit: `{commit}`",
        f"- Working tree dirty: `{str(dirty).lower()}`",
        f"- Generated (UTC): `{datetime.now(timezone.utc).isoformat(timespec='seconds')}`",
        "",
        "## Scenario summary",
        "",
        "| Scenario | N | Goals | Shots | SOT | xG | G-xG | Pass % | Fouls | Yellows | Corners | H/D/A % | Home PPG | Home xG diff | Event issues | sec/match |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for summary in summaries:
        lines.append(
            "| "
            + " | ".join(
                (
                    summary.scenario,
                    str(summary.matches),
                    _fmt(summary.goals_per_match),
                    _fmt(summary.shots_per_match),
                    _fmt(summary.shots_on_target_per_match),
                    _fmt(summary.xg_per_match),
                    _fmt(summary.goals_minus_xg_per_match),
                    _fmt(summary.pass_completion_pct, 1),
                    _fmt(summary.fouls_per_match),
                    _fmt(summary.yellow_cards_per_match),
                    _fmt(summary.corners_per_match),
                    f"{_fmt(summary.home_win_pct, 1)}/{_fmt(summary.draw_pct, 1)}/{_fmt(summary.away_win_pct, 1)}",
                    _fmt(summary.home_points_per_match),
                    _fmt(summary.home_xg_diff_per_match),
                    str(summary.event_integrity_issues),
                    _fmt(summary.mean_elapsed_seconds),
                )
            )
            + " |"
        )

    if target_evaluations:
        equal = next((item for item in summaries if item.scenario == "equal"), None)
        lines.extend(
            [
                "",
                "## Neutral benchmark target check",
                "",
                "> These are broad initial reference bands, not universal constants. With small N, outcome-rate rows are especially noisy.",
                "",
                "| Metric | Value | Target | Status |",
                "|---|---:|---:|:---:|",
            ]
        )
        for item in target_evaluations:
            unit = item.unit
            lines.append(
                f"| {item.label} | {_fmt(item.value)}{unit} | "
                f"{_fmt(item.low)}-{_fmt(item.high)}{unit} | **{item.status}** |"
            )
        if equal is not None:
            lines.extend(
                [
                    "",
                    f"Long-run consistency check: goals/xG ratio = `{equal.goals_per_xg:.3f}`; "
                    f"goals minus xG per match = `{equal.goals_minus_xg_per_match:.3f}`.",
                ]
            )

    lines.extend(["", "## Event integrity", ""])
    for summary in summaries:
        status = "OK" if summary.event_integrity_issues == 0 else "ISSUES"
        lines.append(
            f"- `{summary.scenario}`: **{status}** — "
            f"{summary.event_integrity_issues} issue(s) across {summary.matches} match(es); "
            f"{summary.matches_with_event_integrity_issues} affected match(es)."
        )

    lines.extend(["", "## Controlled scenarios", ""])
    for scenario in scenarios:
        lines.append(
            f"- `{scenario.name}`: home delta {scenario.home_attribute_delta:+d}, "
            f"away delta {scenario.away_attribute_delta:+d}. {scenario.description}"
        )

    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "This report measures distributions; it does not change Match Engine parameters. "
            "Any anomaly should be reproduced with fixed seeds and inspected in the Phase 5.9 viewer before tuning the engine.",
            "",
        ]
    )
    output.write_text("\n".join(lines), encoding="utf-8")
    return output


def write_calibration_reports(
    output_dir: str | Path,
    *,
    run_id: str,
    commit: str,
    dirty: bool,
    scenarios: tuple[BenchmarkScenario, ...],
    samples: tuple[CalibrationSample, ...],
    summaries: tuple[CalibrationSummary, ...],
    target_evaluations: tuple[TargetEvaluation, ...] = (),
) -> tuple[Path, Path, Path]:
    directory = Path(output_dir)
    match_csv = write_csv_report(
        directory / f"{run_id}_matches.csv",
        (sample.to_row() for sample in samples),
    )
    summary_csv = write_csv_report(
        directory / f"{run_id}_summary.csv",
        (summary.to_row() for summary in summaries),
    )
    markdown = write_markdown_report(
        directory / f"{run_id}.md",
        commit=commit,
        dirty=dirty,
        scenarios=scenarios,
        summaries=summaries,
        target_evaluations=target_evaluations,
    )
    return match_csv, summary_csv, markdown
