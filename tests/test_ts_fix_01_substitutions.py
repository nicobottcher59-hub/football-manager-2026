"""TS-FIX-01: causal substitutions, legal windows, minutes and delegation."""
from dataclasses import replace
from collections import Counter, defaultdict

import pytest
from examples.demo_match_factory import build_demo_snapshot
from football_manager.domain import MatchDecider, Position
from football_manager.domain.tactical_studio import PlanRule
from football_manager.fast_simulation import FastMatchSimulator, FastCardType
from football_manager.fast_simulation.ai_coaching import coach_for_match
from football_manager.fast_simulation.plans import FastTacticalChange


def coaches(snapshot):
    return {t.club_id: coach_for_match(snapshot.seed, t.club_id, t.tactic.preset_origin.value,
                                      snapshot.match_id) for t in (snapshot.home_team, snapshot.away_team)}


def check_accounting(snapshot, result, duration=90):
    entrants = {s.player_in_id: s.minute - 1 for s in result.substitutions}
    exits = {s.player_out_id: s.minute - 1 for s in result.substitutions}
    reds = {c.player_id: c.minute for c in result.cards if c.card is FastCardType.RED}
    stats = {p.player_id: p for p in result.player_statistics}
    role_minutes = Counter()
    for segment in result.role_segments:
        role_minutes[segment.player_id] += segment.minutes
    for player_id, stat in stats.items():
        expected = min(exits.get(player_id, duration), reds.get(player_id, duration)) - entrants.get(player_id, 0)
        assert stat.minutes == expected
        assert role_minutes[player_id] == expected
        assert 0 <= stat.condition_after <= 100 and 0 <= stat.fatigue_after <= 100
    for event in result.goals:
        for pid in (event.scorer_player_id, event.assist_player_id):
            if pid:
                assert entrants.get(pid, 0) < event.minute <= min(exits.get(pid, duration), reds.get(pid, duration))
    for event in result.cards:
        assert entrants.get(event.player_id, 0) < event.minute <= min(exits.get(event.player_id, duration), reds.get(event.player_id, duration))
    for club_id, total in ((result.home_club_id, result.statistics_home), (result.away_club_id, result.statistics_away)):
        members = [p for p in result.player_statistics if p.club_id == club_id]
        lost = sum(duration - c.minute for c in result.cards if c.club_id == club_id and c.card is FastCardType.RED)
        assert sum(p.minutes for p in members) == 11 * duration - lost
        for name in ('shots', 'shots_on_target', 'fouls', 'passes_attempted', 'passes_completed', 'yellow_cards', 'red_cards'):
            assert getattr(total, name) == sum(getattr(p, name) for p in members)
    for side in (snapshot.home_team, snapshot.away_team):
        subs = [s for s in result.substitutions if s.club_id == side.club_id]
        assert len({s.player_in_id for s in subs}) == len(subs)
        assert all(s.player_in_id in {p.player_id for p in side.bench} for s in subs)
        for sub in subs:
            assert sub.player_out_id not in reds or reds[sub.player_out_id] >= sub.minute
        rules = snapshot.context.competition
        assert len(subs) <= rules.substitution_limit + (rules.extra_time_additional_substitutions if duration == 120 else 0)
        normal_windows = {s.minute for s in subs if s.minute <= 90 and s.minute != 46}
        all_windows = {s.minute for s in subs if s.minute not in (46, 91, 106)}
        assert len(normal_windows) <= rules.substitution_window_limit
        assert len(all_windows) <= rules.substitution_window_limit + (rules.extra_time_additional_windows if duration == 120 else 0)


def test_both_delegated_teams_substitute_deterministically_without_mutating_snapshot():
    snapshot = build_demo_snapshot(seed=1)
    original = repr(snapshot)
    engine = FastMatchSimulator()
    first = engine.simulate(snapshot, ai_coaches=coaches(snapshot))
    assert first == engine.simulate(snapshot, ai_coaches=coaches(snapshot))
    assert {s.club_id for s in first.substitutions} == {snapshot.home_team.club_id, snapshot.away_team.club_id}
    assert repr(snapshot) == original
    check_accounting(snapshot, first)


@pytest.mark.parametrize('seed', range(1, 25))
def test_chronology_minutes_red_cards_and_accounting(seed):
    snapshot = build_demo_snapshot(seed=seed)
    result = FastMatchSimulator().simulate(snapshot, ai_coaches=coaches(snapshot))
    check_accounting(snapshot, result)


@pytest.mark.parametrize('limit,windows', [(0, 0), (0, 3), (1, 1), (3, 1), (3, 3), (5, 0), (5, 1), (5, 3)])
def test_competition_allowances_not_hardcoded(limit, windows):
    base = build_demo_snapshot(seed=7)
    rules = replace(base.context.competition, substitution_limit=limit, substitution_window_limit=windows)
    snapshot = replace(base, context=replace(base.context, competition=rules))
    result = FastMatchSimulator().simulate(snapshot, ai_coaches=coaches(snapshot))
    check_accounting(snapshot, result)
    if limit == 0:
        assert not result.substitutions


def test_manual_side_is_not_substituted_by_opponent_coach():
    snapshot = build_demo_snapshot(seed=4)
    ai = coaches(snapshot)
    del ai[snapshot.home_team.club_id]
    result = FastMatchSimulator().simulate(snapshot, ai_coaches=ai)
    assert result.substitutions
    assert all(s.club_id == snapshot.away_team.club_id for s in result.substitutions)
    check_accounting(snapshot, result)


@pytest.mark.parametrize('unavailable', ['injured', 'suspended', 'no_familiarity', 'empty'])
def test_unavailable_or_unsuitable_bench_does_not_force_changes(unavailable):
    snapshot = build_demo_snapshot(seed=1)
    def restrict(team):
        bench = []
        for p in team.bench:
            if unavailable == 'injured':
                p = replace(p, state=replace(p.state, injury='test injury'))
            elif unavailable == 'suspended':
                p = replace(p, state=replace(p.state, suspended_matches=1))
            elif unavailable == 'no_familiarity':
                p = replace(p, familiarity=replace(p.familiarity, positions=()))
            bench.append(p)
        return replace(team, bench=() if unavailable == 'empty' else tuple(bench))
    snapshot = replace(snapshot, home_team=restrict(snapshot.home_team), away_team=restrict(snapshot.away_team))
    result = FastMatchSimulator().simulate(snapshot, ai_coaches=coaches(snapshot))
    assert not result.substitutions
    check_accounting(snapshot, result)


def test_plans_after_substitutions_keep_replacements_roles_and_no_reentry():
    snapshot = build_demo_snapshot(seed=10)
    plan = FastTacticalChange(PlanRule('B', 77), 'Second-half plan', snapshot.home_team)
    result = FastMatchSimulator().simulate(snapshot, tactical_plans=(plan,), ai_coaches=coaches(snapshot))
    assert any(s.minute < 77 for s in result.substitutions)
    assert result.tactical_events[0].applied and result.tactical_events[0].minute == 77
    check_accounting(snapshot, result)


def test_extra_time_carries_remaining_allowance_and_penalties_use_final_players():
    engine = FastMatchSimulator()
    found = 0
    for seed in range(1, 100):
        base = build_demo_snapshot(seed=seed)
        rules = replace(base.context.competition, match_decider=MatchDecider.EXTRA_TIME_AND_PENALTIES,
                        substitution_limit=3, extra_time_additional_substitutions=1)
        snapshot = replace(base, context=replace(base.context, competition=rules))
        result = engine.simulate(snapshot, ai_coaches=coaches(snapshot))
        if result.decision.value not in ('extra_time', 'penalties'):
            continue
        check_accounting(snapshot, result, 120)
        removed = {s.player_out_id for s in result.substitutions}
        removed.update(c.player_id for c in result.cards if c.card is FastCardType.RED)
        assert all(k.taker_player_id not in removed for k in result.penalty_kicks)
        found += 1
        if found == 5:
            break
    assert found == 5


def test_substitutions_change_future_team_profiles_and_physical_load():
    snapshot = build_demo_snapshot(seed=1)
    # Unlike the uniform demo XI, this bench has measurably different skills.
    # Equal players can legitimately produce identical rounded team totals.
    bench = tuple(replace(p, attributes=replace(p.attributes, technical=replace(
        p.attributes.technical, passing=95, finishing=95, first_touch=95)))
        for p in snapshot.home_team.bench)
    snapshot = replace(snapshot, home_team=replace(snapshot.home_team, bench=bench))
    result = FastMatchSimulator().simulate(snapshot, ai_coaches=coaches(snapshot))
    stats = {p.player_id: p for p in result.player_statistics}
    for sub in result.substitutions:
        assert stats[sub.player_in_id].minutes < 90
        assert stats[sub.player_out_id].minutes < 90
    assert any(stats[s.player_in_id].condition_after > stats[s.player_out_id].condition_after
               for s in result.substitutions)
    # Avoid golden scores: assert a change in the actual evolving match, not
    # simply that the commentary contains replacement events.
    no_sub = replace(snapshot, context=replace(snapshot.context, competition=replace(
        snapshot.context.competition, substitution_limit=0)))
    other = FastMatchSimulator().simulate(no_sub, ai_coaches=coaches(no_sub))
    assert (result.statistics_home, result.statistics_away) != (other.statistics_home, other.statistics_away)
