from __future__ import annotations

import csv
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from .models import (
    FastCalibrationSummary,
    FastCoachVsSquadSummary,
    FastCurveDiagnostics,
    FastCurvePoint,
    FastExecutionPoint,
    FastLeagueStanding,
    FastLeagueSummary,
    FastTargetEvaluation,
    FastTacticalDelta,
    FastTacticalMatchupDelta,
)


def fast_calibration_run_id(*, commit: str) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    safe_commit = (commit or "unknown").replace("/", "-")[:12]
    return f"{stamp}_{safe_commit}_fast"


def _write_csv(path: Path, rows: Iterable[dict[str, object]]) -> None:
    items = tuple(rows)
    if not items:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(items[0].keys()))
        writer.writeheader()
        writer.writerows(items)


def write_fast_calibration_reports(
    output_dir: str | Path,
    *,
    run_id: str,
    commit: str,
    dirty: bool,
    baseline: FastCalibrationSummary,
    mixed: FastCalibrationSummary,
    targets: tuple[FastTargetEvaluation, ...],
    strength_points: tuple[FastCurvePoint, ...],
    strength_diagnostics: FastCurveDiagnostics,
    act_points: tuple[FastCurvePoint, ...],
    act_diagnostics: FastCurveDiagnostics,
    execution_points: tuple[FastExecutionPoint, ...],
    tactical: tuple[FastTacticalDelta, ...],
    tactical_matchups: tuple[FastTacticalMatchupDelta, ...],
    coach_vs_squad: tuple[FastCoachVsSquadSummary, ...],
    league_standings: tuple[FastLeagueStanding, ...],
    league_summary: FastLeagueSummary,
) -> tuple[Path, ...]:
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    baseline_csv = root / f"{run_id}_baseline.csv"
    mixed_csv = root / f"{run_id}_mixed.csv"
    strength_csv = root / f"{run_id}_strength.csv"
    act_csv = root / f"{run_id}_act.csv"
    execution_csv = root / f"{run_id}_execution.csv"
    tactical_csv = root / f"{run_id}_tactics.csv"
    matchup_csv = root / f"{run_id}_tactical_matchups.csv"
    coach_csv = root / f"{run_id}_coach_vs_squad.csv"
    league_csv = root / f"{run_id}_league.csv"
    markdown = root / f"{run_id}.md"

    _write_csv(baseline_csv, [baseline.to_row()])
    _write_csv(mixed_csv, [mixed.to_row()])
    _write_csv(strength_csv, [asdict(item) for item in strength_points])
    _write_csv(act_csv, [asdict(item) for item in act_points])
    _write_csv(execution_csv, [asdict(item) for item in execution_points])
    _write_csv(tactical_csv, [asdict(item) for item in tactical])
    _write_csv(matchup_csv, [asdict(item) for item in tactical_matchups])
    _write_csv(coach_csv, [asdict(item) for item in coach_vs_squad])
    _write_csv(league_csv, [item.to_row() for item in league_standings])

    lines = [
        "# Fast Match Simulator Calibration",
        "",
        f"- Commit: `{commit}`",
        f"- Dirty working tree: `{dirty}`",
        f"- Neutral samples: `{baseline.matches}`",
        f"- Measured throughput: `{baseline.matches_per_second:.1f} matches/sec`",
        "",
        "## Neutral baseline",
        "",
        "| Metric | Value | Target | Status |",
        "| --- | ---: | ---: | :---: |",
    ]
    for item in targets:
        unit = item.unit
        lines.append(
            f"| {item.label} | {item.value:.2f}{unit} | {item.low:.2f}-{item.high:.2f}{unit} | {item.status} |"
        )
    lines += [
        "",
        "### Volatility",
        "",
        f"- 0-0 matches: {baseline.scoreless_pct:.1f}%",
        f"- Both teams score: {baseline.both_teams_score_pct:.1f}%",
        f"- 4+ total goals: {baseline.four_plus_goals_pct:.1f}%",
        f"- 3+ goal margin: {baseline.margin_three_plus_pct:.1f}%",
        f"- 10+ shot differential: {baseline.shot_diff_10plus_pct:.1f}%",
        f"- 1.0+ xG differential: {baseline.xg_diff_1plus_pct:.1f}%",
        f"- Either team reaches 60% possession: {baseline.possession_60plus_pct:.1f}%",
        "",
        "## Mixed realistic batch",
        "",
        f"- Goals: {mixed.goals_per_match:.2f}",
        f"- Shots / SOT: {mixed.shots_per_match:.2f} / {mixed.shots_on_target_per_match:.2f}",
        f"- xG: {mixed.xg_per_match:.2f}",
        f"- H/D/A: {mixed.home_win_pct:.1f}/{mixed.draw_pct:.1f}/{mixed.away_win_pct:.1f}",
        f"- 3+ goal margin: {mixed.margin_three_plus_pct:.1f}%",
        f"- 10+ shot differential: {mixed.shot_diff_10plus_pct:.1f}%",
        f"- 1.0+ xG differential: {mixed.xg_diff_1plus_pct:.1f}%",
        "",
        "## Strength curve",
        "",
        "| Gap | PPG | GD | xGD | xG share | H/D/A | Upset | Fav non-win |",
        "| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for point in strength_points:
        upset = "-" if point.underdog_win_pct is None else f"{point.underdog_win_pct:.1f}%"
        nonwin = "-" if point.favorite_non_win_pct is None else f"{point.favorite_non_win_pct:.1f}%"
        lines.append(
            f"| {point.value:+.0f} | {point.home_points_per_match:.2f} | {point.home_goal_diff_per_match:+.2f} | "
            f"{point.home_xg_diff_per_match:+.2f} | {point.home_xg_share_pct:.1f}% | "
            f"{point.home_win_pct:.0f}/{point.draw_pct:.0f}/{point.away_win_pct:.0f} | {upset} | {nonwin} |"
        )
    lines += [
        "",
        f"Strength PPG slope / +10: {strength_diagnostics.ppg_slope_per_10:+.3f}",
        f"Strength xGD slope / +10: {strength_diagnostics.xg_diff_slope_per_10:+.3f}",
        f"Strength PPG monotonic violations: {strength_diagnostics.ppg_monotonic_violations}",
        f"Strength xGD monotonic violations: {strength_diagnostics.xg_monotonic_violations}",
        "",
        "## ACT sensitivity",
        "",
        "| ACT delta | PPG | GD | xGD | H/D/A |",
        "| ---: | ---: | ---: | ---: | ---: |",
    ]
    for point in act_points:
        lines.append(
            f"| {point.value:+.0f} | {point.home_points_per_match:.2f} | {point.home_goal_diff_per_match:+.2f} | "
            f"{point.home_xg_diff_per_match:+.2f} | {point.home_win_pct:.0f}/{point.draw_pct:.0f}/{point.away_win_pct:.0f} |"
        )
    lines += [
        "",
        f"ACT PPG slope / +10: {act_diagnostics.ppg_slope_per_10:+.3f}",
        f"ACT monotonic violations: {act_diagnostics.ppg_monotonic_violations}",
        "",
        "## Tactical execution / familiarity",
        "",
        "This experiment uses the same non-neutral tactical plan at every point; only its execution/familiarity score changes.",
        "",
        "| Execution | PPG | Poss | Pass% | Shots | xG | Fouls | Corners | Opp pass% |",
        "| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for point in execution_points:
        lines.append(
            f"| {point.score:.0f} | {point.home_points_per_match:.2f} | {point.home_possession_pct:.1f}% | "
            f"{point.home_pass_completion_pct:.1f}% | {point.home_shots_per_match:.2f} | "
            f"{point.home_xg_per_match:.2f} | {point.home_fouls_per_match:.2f} | "
            f"{point.home_corners_per_match:.2f} | {point.away_pass_completion_pct:.1f}% |"
        )
    lines += [
        "",
        "## Tactical ablations",
        "",
        "| Change | PPG d | Poss d | Pass% d | Shots d | xG d | Fouls d | Corners d | Opp pass% d |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for item in tactical:
        lines.append(
            f"| {item.name} | {item.home_points_delta:+.2f} | {item.home_possession_pp_delta:+.2f} | "
            f"{item.home_pass_completion_pp_delta:+.2f} | {item.home_shots_delta:+.2f} | {item.home_xg_delta:+.2f} | "
            f"{item.home_fouls_delta:+.2f} | {item.home_corners_delta:+.2f} | {item.away_pass_completion_pp_delta:+.2f} |"
        )
    lines += [
        "",
        "## Tactical matchup interactions",
        "",
        "Each row compares the same home plan in a difficult matchup versus a favorable matchup, with equal player quality and paired seeds.",
        "",
        "| Matchup | PPG d | xG d | Opp xG d | xGD d | Shot diff d | Poss d | Pass% d | Opp pass% d |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for item in tactical_matchups:
        lines.append(
            f"| {item.name} | {item.home_points_delta:+.2f} | {item.home_xg_delta:+.2f} | "
            f"{item.away_xg_delta:+.2f} | {item.xg_diff_delta:+.2f} | {item.shot_diff_delta:+.2f} | "
            f"{item.home_possession_pp_delta:+.2f} | {item.home_pass_completion_pp_delta:+.2f} | "
            f"{item.away_pass_completion_pp_delta:+.2f} |"
        )
    lines += [
        "",
        "## Coach vs squad quality",
        "",
        "The stronger squad is fixed at +10 structural quality. The weaker squad is evaluated over paired home/away seeds; only its tactical plan and execution change.",
        "",
        "| Scenario | Weak PPG | Weak W/D/L | Weak GD | Weak xGD | Weak shot diff | Weak xG share |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for item in coach_vs_squad:
        lines.append(
            f"| {item.scenario} | {item.weaker_points_per_match:.2f} | "
            f"{item.weaker_win_pct:.1f}/{item.draw_pct:.1f}/{item.stronger_win_pct:.1f} | "
            f"{item.weaker_goal_diff_per_match:+.2f} | {item.weaker_xg_diff_per_match:+.2f} | "
            f"{item.weaker_shot_diff_per_match:+.2f} | {item.weaker_xg_share_pct:.1f}% |"
        )
    lines += [
        "",
        "## Synthetic 20-team league",
        "",
        f"- Matches: {league_summary.matches}",
        f"- Throughput: {league_summary.matches_per_second:.1f} matches/sec",
        f"- Strongest team rank: {league_summary.strongest_team_rank}",
        f"- Weakest team rank: {league_summary.weakest_team_rank}",
        f"- Top-half mean quality delta: {league_summary.top_half_mean_quality:+.2f}",
        f"- Bottom-half mean quality delta: {league_summary.bottom_half_mean_quality:+.2f}",
        f"- Quality/points correlation: {league_summary.rank_quality_correlation:+.3f}",
        "",
        "Full standings are in the companion CSV.",
    ]
    markdown.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return (markdown, baseline_csv, mixed_csv, strength_csv, act_csv, execution_csv, tactical_csv, matchup_csv, coach_csv, league_csv)
