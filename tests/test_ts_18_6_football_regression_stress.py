"""TS-18.6: cross-match invariants for the existing fast engine; no gameplay changes."""
from collections import Counter

import pytest

from examples.demo_match_factory import build_demo_snapshot
from football_manager.fast_simulation import FastMatchSimulator


@pytest.mark.parametrize('seed', range(18600, 18720))
def test_fast_match_event_and_player_integrity_across_seeds(seed):
    snapshot = build_demo_snapshot(seed=seed)
    result = FastMatchSimulator().simulate(snapshot)
    roster = {
        snapshot.home_team.club_id: {p.player_id for p in snapshot.home_team.starters + snapshot.home_team.bench},
        snapshot.away_team.club_id: {p.player_id for p in snapshot.away_team.starters + snapshot.away_team.bench},
    }
    participant_stats = {(s.club_id, s.player_id): s for s in result.player_statistics}
    assert len(participant_stats) == len(result.player_statistics)
    assert all(player_id in roster[club_id] for club_id, player_id in participant_stats)
    assert sum(g.club_id == result.home_club_id for g in result.goals) == result.home_goals
    assert sum(g.club_id == result.away_club_id for g in result.goals) == result.away_goals
    for goal in result.goals:
        assert (goal.club_id, goal.scorer_player_id) in participant_stats
        if goal.assist_player_id is not None:
            assert (goal.club_id, goal.assist_player_id) in participant_stats
            assert goal.assist_player_id != goal.scorer_player_id
    for card in result.cards:
        assert (card.club_id, card.player_id) in participant_stats
    for sub in result.substitutions:
        assert sub.player_in_id != sub.player_out_id
        assert (sub.club_id, sub.player_in_id) in participant_stats
        assert (sub.club_id, sub.player_out_id) in participant_stats
    goal_counts = Counter((g.club_id, g.scorer_player_id) for g in result.goals)
    assist_counts = Counter((g.club_id, g.assist_player_id) for g in result.goals if g.assist_player_id)
    for key, stat in participant_stats.items():
        assert stat.goals == goal_counts[key]
        assert stat.assists == assist_counts[key]
        assert 0 <= stat.minutes <= 120
        assert 0 <= stat.condition_after <= 100
        assert 0 <= stat.fatigue_after <= 100
    assert result.statistics_home.shots_on_target >= result.home_goals
    assert result.statistics_away.shots_on_target >= result.away_goals


def test_repeatability_stress_at_multiple_seeds():
    simulator = FastMatchSimulator()
    for seed in (18601, 18615, 18638, 18671, 18719):
        snapshot = build_demo_snapshot(seed=seed)
        assert simulator.simulate(snapshot) == simulator.simulate(snapshot)
