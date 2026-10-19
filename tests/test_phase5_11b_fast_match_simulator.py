from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from statistics import fmean

import pytest

from examples.demo_match_factory import build_demo_snapshot
from football_manager.domain import MatchDecider
from football_manager.fast_simulation import (
    FastMatchDecision,
    FastMatchSimulator,
    FastSimulationConfig,
)


def _with_seed(snapshot, seed: int):
    return replace(snapshot, seed=seed, match_id=f"fast-{seed}")


def _boost_team(team, amount: float):
    starters = tuple(
        replace(
            player,
            overall_rating=min(100.0, player.overall_rating + amount),
            current_rating=min(100.0, player.current_rating + amount),
        )
        for player in team.starters
    )
    bench = tuple(
        replace(
            player,
            overall_rating=min(100.0, player.overall_rating + amount),
            current_rating=min(100.0, player.current_rating + amount),
        )
        for player in team.bench
    )
    return replace(team, starters=starters, bench=bench)


def test_fast_simulator_is_deterministic_for_same_snapshot_and_seed() -> None:
    snapshot = build_demo_snapshot(seed=51101)
    simulator = FastMatchSimulator()

    first = simulator.simulate(snapshot)
    second = simulator.simulate(snapshot)

    assert first == second


def test_different_seeds_can_change_match_outcome_or_statistics() -> None:
    snapshot = build_demo_snapshot(seed=1)
    simulator = FastMatchSimulator()
    signatures = {
        (
            result.home_goals,
            result.away_goals,
            result.statistics_home.shots,
            result.statistics_away.shots,
            result.statistics_home.possession_pct,
        )
        for result in (simulator.simulate(_with_seed(snapshot, seed)) for seed in range(1, 8))
    }
    assert len(signatures) > 1


def test_fast_result_internal_statistics_are_coherent() -> None:
    result = FastMatchSimulator().simulate(build_demo_snapshot(seed=51102))

    assert result.statistics_home.goals == result.home_goals
    assert result.statistics_away.goals == result.away_goals
    assert result.statistics_home.shots >= result.statistics_home.shots_on_target >= result.home_goals
    assert result.statistics_away.shots >= result.statistics_away.shots_on_target >= result.away_goals
    assert result.statistics_home.passes_attempted >= result.statistics_home.passes_completed
    assert result.statistics_away.passes_attempted >= result.statistics_away.passes_completed
    assert result.statistics_home.possession_pct + result.statistics_away.possession_pct == pytest.approx(100.0)
    assert len(result.goals) == result.home_goals + result.away_goals


def test_player_statistics_reconcile_with_team_totals() -> None:
    result = FastMatchSimulator().simulate(build_demo_snapshot(seed=51103))

    for club_id, team_stats in (
        (result.home_club_id, result.statistics_home),
        (result.away_club_id, result.statistics_away),
    ):
        players = [item for item in result.player_statistics if item.club_id == club_id]
        assert len(players) == 11
        assert sum(item.goals for item in players) == team_stats.goals
        assert sum(item.shots for item in players) == team_stats.shots
        assert sum(item.shots_on_target for item in players) == team_stats.shots_on_target
        assert sum(item.passes_attempted for item in players) == team_stats.passes_attempted
        assert sum(item.passes_completed for item in players) == team_stats.passes_completed
        assert sum(item.fouls for item in players) == team_stats.fouls
        assert sum(item.yellow_cards for item in players) == team_stats.yellow_cards
        assert sum(item.red_cards for item in players) == team_stats.red_cards
        assert sum(item.xg for item in players) == pytest.approx(team_stats.xg, abs=0.02)


def test_goals_have_real_scorers_and_assists_belong_to_same_team() -> None:
    snapshot = build_demo_snapshot(seed=51104)
    result = FastMatchSimulator().simulate(snapshot)
    player_club = {
        player.player_id: team.club_id
        for team in (snapshot.home_team, snapshot.away_team)
        for player in team.starters
    }

    for goal in result.goals:
        assert player_club[goal.scorer_player_id] == goal.club_id
        if goal.assist_player_id is not None:
            assert goal.assist_player_id != goal.scorer_player_id
            assert player_club[goal.assist_player_id] == goal.club_id


def test_fast_simulator_does_not_mutate_snapshot() -> None:
    snapshot = build_demo_snapshot(seed=51105)
    before = snapshot
    result = FastMatchSimulator().simulate(snapshot)

    assert snapshot == before
    assert result.match_id == snapshot.match_id


def test_fast_simulation_package_has_no_dependency_on_spatial_simulation() -> None:
    package = Path("src/football_manager/fast_simulation")
    source = "\n".join(path.read_text(encoding="utf-8") for path in package.glob("*.py"))

    assert "from football_manager.simulation" not in source
    assert "import football_manager.simulation" not in source
    assert "SpatialMatchEngine" not in source
    assert "MatchFlowController" not in source


def test_equal_team_batch_has_broadly_football_like_mvp_distributions() -> None:
    base = build_demo_snapshot(seed=1)
    simulator = FastMatchSimulator()
    results = [simulator.simulate(_with_seed(base, seed)) for seed in range(200, 500)]

    total_goals = fmean(result.total_goals for result in results)
    total_shots = fmean(result.statistics_home.shots + result.statistics_away.shots for result in results)
    total_sot = fmean(
        result.statistics_home.shots_on_target + result.statistics_away.shots_on_target
        for result in results
    )
    total_xg = fmean(
        result.statistics_home.xg + result.statistics_away.xg
        for result in results
    )
    total_fouls = fmean(result.statistics_home.fouls + result.statistics_away.fouls for result in results)
    total_yellows = fmean(
        result.statistics_home.yellow_cards + result.statistics_away.yellow_cards
        for result in results
    )
    total_corners = fmean(result.statistics_home.corners + result.statistics_away.corners for result in results)
    pass_pct = fmean(
        (result.statistics_home.pass_completion_pct + result.statistics_away.pass_completion_pct) / 2.0
        for result in results
    )

    # Wide MVP guardrails only. Phase 5.11C owns real calibration.
    assert 1.8 <= total_goals <= 3.8
    assert 19.0 <= total_shots <= 31.0
    assert 6.0 <= total_sot <= 12.0
    assert abs(total_goals - total_xg) <= 0.6
    assert 17.0 <= total_fouls <= 31.0
    assert 2.0 <= total_yellows <= 5.5
    assert 6.0 <= total_corners <= 14.0
    assert 76.0 <= pass_pct <= 89.0


def test_stronger_team_is_favored_but_upsets_and_non_wins_survive() -> None:
    base = build_demo_snapshot(seed=1)
    stronger = replace(base, home_team=_boost_team(base.home_team, 12.0))
    simulator = FastMatchSimulator()

    results = [simulator.simulate(_with_seed(stronger, seed)) for seed in range(600, 1000)]
    home_wins = sum(result.home_goals > result.away_goals for result in results)
    away_wins = sum(result.away_goals > result.home_goals for result in results)
    draws = len(results) - home_wins - away_wins

    assert home_wins > away_wins
    assert home_wins / len(results) > 0.45
    assert away_wins > 0
    assert draws > 0
    assert home_wins < len(results)


def test_more_possession_oriented_tactic_moves_possession_without_fixing_result() -> None:
    base = build_demo_snapshot(seed=1)
    style = base.home_team.tactic.style
    control_tactic = replace(
        base.home_team.tactic,
        style=replace(style, possession=100.0, directness=15.0, tempo=40.0),
    )
    direct_tactic = replace(
        base.home_team.tactic,
        style=replace(style, possession=15.0, directness=100.0, tempo=75.0),
    )
    control = replace(base, home_team=replace(base.home_team, tactic=control_tactic))
    direct = replace(base, home_team=replace(base.home_team, tactic=direct_tactic))
    simulator = FastMatchSimulator()

    control_possession = fmean(
        simulator.simulate(_with_seed(control, seed)).statistics_home.possession_pct
        for seed in range(1000, 1100)
    )
    direct_possession = fmean(
        simulator.simulate(_with_seed(direct, seed)).statistics_home.possession_pct
        for seed in range(1000, 1100)
    )

    assert control_possession > direct_possession + 2.0


def test_penalty_decider_resolves_a_regulation_draw_without_2d_engine() -> None:
    base = build_demo_snapshot(seed=1)
    competition = replace(base.context.competition, match_decider=MatchDecider.PENALTIES_AFTER_90)
    base = replace(base, context=replace(base.context, competition=competition))
    simulator = FastMatchSimulator()

    draw_seed = None
    for seed in range(1, 200):
        result = simulator.simulate(_with_seed(base, seed))
        if result.decision is FastMatchDecision.PENALTIES:
            draw_seed = seed
            break

    assert draw_seed is not None
    resolved = simulator.simulate(_with_seed(base, draw_seed))
    assert resolved.home_goals == resolved.away_goals
    assert resolved.penalties_home != resolved.penalties_away
    assert resolved.winner_club_id in {resolved.home_club_id, resolved.away_club_id}
