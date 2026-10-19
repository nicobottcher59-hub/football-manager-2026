from __future__ import annotations

from dataclasses import replace
from statistics import fmean

import pytest

from examples.demo_match_factory import build_demo_snapshot
from football_manager.domain import MatchDecider, Position
from football_manager.fast_calibration.scenarios import neutralize_fast_snapshot
from football_manager.fast_simulation import FastMatchDecision, FastMatchSimulator


def _with_seed(snapshot, seed: int):
    return replace(snapshot, seed=seed, match_id=f"phase-5-11d-{seed}")


def _with_decider(snapshot, decider: MatchDecider, *, extra_subs: int = 1):
    competition = replace(
        snapshot.context.competition,
        match_decider=decider,
        extra_time_additional_substitutions=extra_subs,
    )
    return replace(snapshot, context=replace(snapshot.context, competition=competition))


def _familiar_bench(team):
    role_ids = tuple(sorted({slot.role_id for slot in team.tactic.slots}))
    bench = []
    for player in team.bench:
        familiarity = replace(
            player.familiarity,
            roles=tuple((role_id, 65.0) for role_id in role_ids),
            tactics=((team.tactic.tactic_id, 65.0),),
        )
        bench.append(replace(player, familiarity=familiarity))
    return replace(team, bench=tuple(bench))


def _base_knockout(*, seed: int = 1):
    base = neutralize_fast_snapshot(build_demo_snapshot(seed=seed), rating=70, seed=seed)
    return replace(
        base,
        home_team=_familiar_bench(base.home_team),
        away_team=_familiar_bench(base.away_team),
    )


def _find_seed(snapshot, decision: FastMatchDecision, *, limit: int = 500) -> int:
    simulator = FastMatchSimulator()
    for seed in range(1, limit + 1):
        if simulator.simulate(_with_seed(snapshot, seed)).decision is decision:
            return seed
    raise AssertionError(f"could not find {decision} in {limit} seeds")


def test_knockout_simulation_is_seed_reproducible_including_shootout_events() -> None:
    base = _with_decider(_base_knockout(), MatchDecider.EXTRA_TIME_AND_PENALTIES)
    seed = _find_seed(base, FastMatchDecision.PENALTIES)
    simulator = FastMatchSimulator()

    first = simulator.simulate(_with_seed(base, seed))
    second = simulator.simulate(_with_seed(base, seed))

    assert first == second
    assert first.penalty_kicks


def test_direct_penalties_preserve_the_same_90_minute_match_and_skip_extra_time() -> None:
    base = _base_knockout()
    league = _with_decider(base, MatchDecider.DRAW_ALLOWED)
    simulator = FastMatchSimulator()
    draw_seed = _find_seed(league, FastMatchDecision.DRAW)

    ninety = simulator.simulate(_with_seed(league, draw_seed))
    direct = simulator.simulate(
        _with_seed(_with_decider(base, MatchDecider.PENALTIES_AFTER_90), draw_seed)
    )

    assert direct.decision is FastMatchDecision.PENALTIES
    assert direct.regulation_home_goals == ninety.home_goals
    assert direct.regulation_away_goals == ninety.away_goals
    assert direct.extra_time_home_goals == direct.extra_time_away_goals == 0
    assert direct.statistics_home == ninety.statistics_home
    assert direct.statistics_away == ninety.statistics_away
    assert direct.substitutions == ()
    assert all(player.minutes == 90 for player in direct.player_statistics)
    assert direct.penalty_kicks[-1].score_after_home == direct.penalties_home
    assert direct.penalty_kicks[-1].score_after_away == direct.penalties_away


def test_extra_time_uses_extra_substitution_allowance_and_reconciles_minutes() -> None:
    base = _with_decider(_base_knockout(), MatchDecider.EXTRA_TIME_AND_PENALTIES, extra_subs=1)
    seed = _find_seed(base, FastMatchDecision.PENALTIES)
    result = FastMatchSimulator().simulate(_with_seed(base, seed))

    assert len(result.substitutions) == 2
    assert all(item.extra_time and item.minute == 91 for item in result.substitutions)
    stats = {item.player_id: item for item in result.player_statistics}
    for substitution in result.substitutions:
        assert stats[substitution.player_out_id].minutes == 90
        assert stats[substitution.player_in_id].minutes == 30
    for club_id in (result.home_club_id, result.away_club_id):
        assert sum(item.minutes for item in result.player_statistics if item.club_id == club_id) == 11 * 120


def test_extra_time_goal_events_and_score_split_are_explicit() -> None:
    base = _with_decider(_base_knockout(), MatchDecider.EXTRA_TIME_AND_PENALTIES)
    seed = _find_seed(base, FastMatchDecision.EXTRA_TIME)
    result = FastMatchSimulator().simulate(_with_seed(base, seed))

    assert result.extra_time_home_goals + result.extra_time_away_goals > 0
    assert result.home_goals == result.regulation_home_goals + result.extra_time_home_goals
    assert result.away_goals == result.regulation_away_goals + result.extra_time_away_goals
    assert sum(goal.extra_time for goal in result.goals) == result.extra_time_home_goals + result.extra_time_away_goals
    assert all(91 <= goal.minute <= 120 for goal in result.goals if goal.extra_time)
    assert result.penalty_kicks == ()


def test_extra_time_has_lower_pace_than_an_extra_third_of_a_full_match() -> None:
    base = _base_knockout()
    league = _with_decider(base, MatchDecider.DRAW_ALLOWED)
    knockout = _with_decider(base, MatchDecider.EXTRA_TIME_AND_PENALTIES)
    simulator = FastMatchSimulator()
    extra_shots: list[int] = []
    extra_goals: list[int] = []

    for seed in range(1, 601):
        ninety = simulator.simulate(_with_seed(league, seed))
        if ninety.decision is not FastMatchDecision.DRAW:
            continue
        extended = simulator.simulate(_with_seed(knockout, seed))
        extra_shots.append(
            extended.statistics_home.shots
            + extended.statistics_away.shots
            - ninety.statistics_home.shots
            - ninety.statistics_away.shots
        )
        extra_goals.append(extended.extra_time_home_goals + extended.extra_time_away_goals)

    assert len(extra_shots) >= 100
    assert 2.5 <= fmean(extra_shots) <= 6.5
    assert 0.30 <= fmean(extra_goals) <= 0.90


def test_shootout_conversion_and_home_away_balance_remain_plausible() -> None:
    base = _with_decider(_base_knockout(), MatchDecider.PENALTIES_AFTER_90)
    simulator = FastMatchSimulator()
    shootouts = []
    for seed in range(1, 1001):
        result = simulator.simulate(_with_seed(base, seed))
        if result.decision is FastMatchDecision.PENALTIES:
            shootouts.append(result)

    kicks = [kick for result in shootouts for kick in result.penalty_kicks]
    conversion = sum(kick.scored for kick in kicks) / len(kicks)
    home_win_rate = sum(result.penalties_home > result.penalties_away for result in shootouts) / len(shootouts)

    assert len(shootouts) >= 150
    assert 0.68 <= conversion <= 0.84
    assert 8.0 <= fmean(len(result.penalty_kicks) for result in shootouts) <= 14.0
    assert 0.35 <= home_win_rate <= 0.65


def test_penalty_order_prioritizes_the_best_available_specialist() -> None:
    base = _base_knockout()
    home_players = []
    star_id = None
    for player in base.home_team.starters:
        penalties = 40
        confidence = 65.0
        if player.assigned_position is Position.ST:
            penalties = 100
            confidence = 100.0
            star_id = player.player_id
        attrs = replace(
            player.attributes,
            technical=replace(player.attributes.technical, penalties=penalties),
        )
        home_players.append(
            replace(player, attributes=attrs, state=replace(player.state, confidence=confidence))
        )
    base = replace(base, home_team=replace(base.home_team, starters=tuple(home_players)))
    direct = _with_decider(base, MatchDecider.PENALTIES_AFTER_90)
    seed = _find_seed(direct, FastMatchDecision.PENALTIES)
    result = FastMatchSimulator().simulate(_with_seed(direct, seed))

    first_home_kick = next(kick for kick in result.penalty_kicks if kick.club_id == result.home_club_id)
    assert first_home_kick.taker_player_id == star_id


def test_penalty_quality_and_confidence_move_shootout_odds_without_guaranteeing_win() -> None:
    base = _base_knockout()

    def tune(team, penalties: int, confidence: float):
        starters = []
        for player in team.starters:
            attrs = replace(
                player.attributes,
                technical=replace(player.attributes.technical, penalties=penalties),
            )
            starters.append(
                replace(player, attributes=attrs, state=replace(player.state, confidence=confidence))
            )
        return replace(team, starters=tuple(starters))

    tuned = replace(
        base,
        home_team=tune(base.home_team, 95, 90.0),
        away_team=tune(base.away_team, 45, 40.0),
    )
    tuned = _with_decider(tuned, MatchDecider.PENALTIES_AFTER_90)
    simulator = FastMatchSimulator()
    shootouts = []
    for seed in range(1, 1201):
        result = simulator.simulate(_with_seed(tuned, seed))
        if result.decision is FastMatchDecision.PENALTIES:
            shootouts.append(result)

    home_wins = sum(result.penalties_home > result.penalties_away for result in shootouts)
    assert len(shootouts) >= 150
    assert home_wins / len(shootouts) > 0.62
    assert home_wins < len(shootouts)


def test_shootout_pressure_rises_toward_decisive_and_sudden_death_kicks() -> None:
    base = _with_decider(_base_knockout(), MatchDecider.PENALTIES_AFTER_90)
    simulator = FastMatchSimulator()
    sudden_result = None
    for seed in range(1, 1000):
        result = simulator.simulate(_with_seed(base, seed))
        if result.decision is FastMatchDecision.PENALTIES and any(kick.sudden_death for kick in result.penalty_kicks):
            sudden_result = result
            break

    assert sudden_result is not None
    first_round_pressure = max(kick.pressure for kick in sudden_result.penalty_kicks if kick.round_number == 1)
    sudden_pressure = min(kick.pressure for kick in sudden_result.penalty_kicks if kick.sudden_death)
    assert first_round_pressure <= 0.20
    assert sudden_pressure >= 0.72
    assert sudden_pressure > first_round_pressure


def test_extra_time_lowers_condition_but_fresh_substitutes_keep_more_energy() -> None:
    base = _base_knockout()
    league = _with_decider(base, MatchDecider.DRAW_ALLOWED)
    knockout = _with_decider(base, MatchDecider.EXTRA_TIME_AND_PENALTIES)
    simulator = FastMatchSimulator()
    seed = _find_seed(league, FastMatchDecision.DRAW)

    ninety = simulator.simulate(_with_seed(league, seed))
    extended = simulator.simulate(_with_seed(knockout, seed))
    assert extended.substitutions

    ninety_stats = {item.player_id: item for item in ninety.player_statistics}
    extended_stats = {item.player_id: item for item in extended.player_statistics}
    substituted_out = {item.player_out_id for item in extended.substitutions}
    substituted_in = {item.player_in_id for item in extended.substitutions}

    long_running = [
        player_id
        for player_id in ninety_stats
        if player_id not in substituted_out and player_id in extended_stats
    ]
    assert fmean(extended_stats[player_id].condition_after for player_id in long_running) < fmean(
        ninety_stats[player_id].condition_after for player_id in long_running
    )
    assert fmean(extended_stats[player_id].condition_after for player_id in substituted_in) > fmean(
        extended_stats[player_id].condition_after for player_id in long_running
    )
