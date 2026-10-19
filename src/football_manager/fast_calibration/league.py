from __future__ import annotations

from dataclasses import dataclass, replace
from math import sqrt
from time import perf_counter

from football_manager.domain import MatchSnapshot
from football_manager.fast_simulation import FastMatchSimulator

from .models import FastLeagueStanding, FastLeagueSummary
from .scenarios import shift_team_quality, with_seed


@dataclass(slots=True)
class _StandingAccumulator:
    quality_delta: int
    played: int = 0
    won: int = 0
    drawn: int = 0
    lost: int = 0
    goals_for: int = 0
    goals_against: int = 0
    points: int = 0


def _pearson(xs: list[float], ys: list[float]) -> float:
    if len(xs) != len(ys) or len(xs) < 2:
        return 0.0
    mx = sum(xs) / len(xs)
    my = sum(ys) / len(ys)
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys, strict=True))
    dx = sqrt(sum((x - mx) ** 2 for x in xs))
    dy = sqrt(sum((y - my) ** 2 for y in ys))
    return num / (dx * dy) if dx > 0.0 and dy > 0.0 else 0.0


def simulate_synthetic_league(
    base: MatchSnapshot,
    *,
    teams: int = 20,
    seed_start: int = 511_000,
    simulator: FastMatchSimulator | None = None,
) -> tuple[tuple[FastLeagueStanding, ...], FastLeagueSummary]:
    if teams < 4:
        raise ValueError("synthetic league requires at least four teams")
    engine = simulator or FastMatchSimulator()
    midpoint = (teams - 1) / 2.0
    deltas = [int(round((index - midpoint) * 20.0 / max(1.0, teams - 1))) for index in range(teams)]
    accum = {
        f"T{index + 1:02d}": _StandingAccumulator(quality_delta=delta)
        for index, delta in enumerate(deltas)
    }
    seed = seed_start
    started = perf_counter()
    matches = 0

    for home_index in range(teams):
        for away_index in range(teams):
            if home_index == away_index:
                continue
            home_id = f"T{home_index + 1:02d}"
            away_id = f"T{away_index + 1:02d}"
            snapshot = replace(
                with_seed(base, seed, label=f"league-{home_id}-{away_id}"),
                home_team=shift_team_quality(base.home_team, accum[home_id].quality_delta),
                away_team=shift_team_quality(base.away_team, accum[away_id].quality_delta),
            )
            result = engine.simulate(snapshot)
            h = accum[home_id]
            a = accum[away_id]
            h.played += 1
            a.played += 1
            h.goals_for += result.home_goals
            h.goals_against += result.away_goals
            a.goals_for += result.away_goals
            a.goals_against += result.home_goals
            if result.home_goals > result.away_goals:
                h.won += 1
                a.lost += 1
                h.points += 3
            elif result.home_goals < result.away_goals:
                a.won += 1
                h.lost += 1
                a.points += 3
            else:
                h.drawn += 1
                a.drawn += 1
                h.points += 1
                a.points += 1
            seed += 1
            matches += 1

    elapsed = perf_counter() - started
    standings = tuple(
        sorted(
            (
                FastLeagueStanding(
                    team_id=team_id,
                    quality_delta=item.quality_delta,
                    played=item.played,
                    won=item.won,
                    drawn=item.drawn,
                    lost=item.lost,
                    goals_for=item.goals_for,
                    goals_against=item.goals_against,
                    points=item.points,
                )
                for team_id, item in accum.items()
            ),
            key=lambda row: (row.points, row.goal_difference, row.goals_for),
            reverse=True,
        )
    )
    rank_by_team = {row.team_id: index + 1 for index, row in enumerate(standings)}
    strongest = max(standings, key=lambda row: row.quality_delta)
    weakest = min(standings, key=lambda row: row.quality_delta)
    half = teams // 2
    top_half = standings[:half]
    bottom_half = standings[-half:]
    quality = [float(row.quality_delta) for row in standings]
    points = [float(row.points) for row in standings]
    summary = FastLeagueSummary(
        teams=teams,
        matches=matches,
        elapsed_seconds=elapsed,
        matches_per_second=(matches / elapsed if elapsed > 0.0 else float("inf")),
        strongest_team_rank=rank_by_team[strongest.team_id],
        weakest_team_rank=rank_by_team[weakest.team_id],
        top_half_mean_quality=sum(row.quality_delta for row in top_half) / len(top_half),
        bottom_half_mean_quality=sum(row.quality_delta for row in bottom_half) / len(bottom_half),
        rank_quality_correlation=_pearson(quality, points),
    )
    return standings, summary
