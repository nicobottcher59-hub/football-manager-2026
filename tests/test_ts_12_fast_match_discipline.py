"""TS-12: chronological red-card consequences in the seeded fast simulator."""
from __future__ import annotations

from collections import defaultdict

from examples.demo_match_factory import build_demo_snapshot
from football_manager.fast_simulation import FastCardType, FastMatchSimulator


def _player(result, club_id: str, player_id: str):
    return next(p for p in result.player_statistics if p.club_id == club_id and p.player_id == player_id)


def test_second_yellow_dismisses_player_and_limits_played_minutes() -> None:
    result = FastMatchSimulator().simulate(build_demo_snapshot(seed=4))
    yellows = [card for card in result.cards if card.club_id == 'away' and card.player_id == 'away-lb' and card.card is FastCardType.YELLOW]
    assert len(yellows) == 2
    red = [card for card in result.cards if card.club_id == 'away' and card.player_id == 'away-lb' and card.card is FastCardType.RED]
    assert len(red) == 1
    assert red[0].minute == yellows[1].minute
    assert _player(result, 'away', 'away-lb').minutes == red[0].minute
    assert _player(result, 'away', 'away-lb').red_cards == 1


def test_direct_red_ends_participation_and_blocks_later_cards_or_goals() -> None:
    result = FastMatchSimulator().simulate(build_demo_snapshot(seed=11))
    reds = [card for card in result.cards if card.card is FastCardType.RED]
    assert reds
    for card in reds:
        assert _player(result, card.club_id, card.player_id).minutes == card.minute
        assert not any(
            other.club_id == card.club_id and other.player_id == card.player_id and other.minute > card.minute
            for other in result.cards
        )
        assert not any(
            goal.club_id == card.club_id
            and (goal.scorer_player_id == card.player_id or goal.assist_player_id == card.player_id)
            and goal.minute > card.minute
            for goal in result.goals
        )


def test_no_player_can_receive_cards_after_dismissal_and_statistics_reconcile() -> None:
    simulator = FastMatchSimulator()
    for seed in range(1, 180):
        result = simulator.simulate(build_demo_snapshot(seed=seed))
        by_player = defaultdict(list)
        for card in result.cards:
            by_player[(card.club_id, card.player_id)].append(card)
        for (club_id, player_id), cards in by_player.items():
            cards.sort(key=lambda card: card.minute)
            reds = [card for card in cards if card.card is FastCardType.RED]
            yellows = [card for card in cards if card.card is FastCardType.YELLOW]
            assert len(reds) <= 1
            assert len(yellows) <= 2
            if reds:
                assert cards[-1].minute == reds[0].minute
                assert _player(result, club_id, player_id).minutes == reds[0].minute
                if len(yellows) == 2:
                    assert yellows[1].minute == reds[0].minute
            elif len(yellows) == 2:
                raise AssertionError(f'missing second-yellow dismissal in seed {seed}')
        for club_id, team in ((result.home_club_id, result.statistics_home), (result.away_club_id, result.statistics_away)):
            players = [p for p in result.player_statistics if p.club_id == club_id]
            assert team.yellow_cards == sum(p.yellow_cards for p in players)
            assert team.red_cards == sum(p.red_cards for p in players)
            assert team.shots == sum(p.shots for p in players)
            assert team.passes_attempted == sum(p.passes_attempted for p in players)
            assert team.fouls == sum(p.fouls for p in players)


def test_no_dismissal_match_preserves_ts19_reference_result() -> None:
    result = FastMatchSimulator().simulate(build_demo_snapshot(seed=1))
    assert not any(card.card is FastCardType.RED for card in result.cards)
    # TS-19 enables previously unconsumed instructions and phase geometry.
    # The old TS-12 golden (1-6, 7/24 shots) is no longer an unaffected match.
    # Keep a strict versioned reference rather than tuning effects to that score.
    assert (result.home_goals, result.away_goals) == (1, 5)
    assert (result.statistics_home.shots, result.statistics_away.shots) == (7, 22)
    assert FastMatchSimulator().simulate(build_demo_snapshot(seed=1)) == result


def test_early_expulsion_reduces_team_opportunities_and_advantages_opponent() -> None:
    from football_manager.fast_simulation.engine import _TeamRuntime
    from football_manager.fast_simulation.profiles import build_fast_team_profile
    from football_manager.fast_simulation.randomness import FastMatchRandom

    snapshot = build_demo_snapshot(seed=10)
    simulator = FastMatchSimulator()
    controlled_shots = disadvantaged_shots = 0
    other_base_shots = other_advantage_shots = 0
    for seed in range(150):
        def runtimes():
            return (
                _TeamRuntime(snapshot.home_team, build_fast_team_profile(snapshot.home_team)),
                _TeamRuntime(snapshot.away_team, build_fast_team_profile(snapshot.away_team)),
            )

        home, away = runtimes()
        sim_kwargs = dict(minutes=90, minute_start=1, minute_end=90, home_advantage=True)
        simulator._simulate_shot_windows(home, away, random=FastMatchRandom(seed).fork('home'), **sim_kwargs)
        simulator._simulate_shot_windows(
            away, home, minutes=90, minute_start=1, minute_end=90,
            home_advantage=False, random=FastMatchRandom(seed).fork('away'),
        )
        controlled_shots += len(home.shots)
        other_base_shots += len(away.shots)

        home, away = runtimes()
        dismissed_player = next(p for p in home.team.starters if p.assigned_position.value == 'ST')
        home.dismissed_at[dismissed_player.player_id] = 10
        simulator._simulate_shot_windows(home, away, random=FastMatchRandom(seed).fork('home'), **sim_kwargs)
        simulator._simulate_shot_windows(
            away, home, minutes=90, minute_start=1, minute_end=90,
            home_advantage=False, random=FastMatchRandom(seed).fork('away'),
        )
        disadvantaged_shots += len(home.shots)
        other_advantage_shots += len(away.shots)
        assert not any(shot.player_id == dismissed_player.player_id and shot.minute > 10 for shot in home.shots)
        assert not any(shot.assist_player_id == dismissed_player.player_id and shot.minute > 10 for shot in home.shots)

    assert disadvantaged_shots < controlled_shots * 0.9
    assert other_advantage_shots > other_base_shots * 1.03


def test_penalty_shootout_eligibility_excludes_dismissed_players_and_keeper() -> None:
    from football_manager.fast_simulation.engine import _TeamRuntime
    from football_manager.fast_simulation.profiles import build_fast_team_profile

    snapshot = build_demo_snapshot(seed=1)
    runtime = _TeamRuntime(snapshot.home_team, build_fast_team_profile(snapshot.home_team))
    goalkeeper = next(player for player in snapshot.home_team.starters if player.assigned_position.value == 'GK')
    striker = next(player for player in snapshot.home_team.starters if player.assigned_position.value == 'ST')
    runtime.dismissed_at[goalkeeper.player_id] = 90
    runtime.dismissed_at[striker.player_id] = 35

    simulator = FastMatchSimulator()
    takers = simulator._penalty_takers(runtime, 91)
    assert striker.player_id not in {p.player_id for p in takers}
    assert goalkeeper.player_id not in {p.player_id for p in takers}
    assert len(takers) == 9
    assert simulator._active_goalkeeper(runtime, 91).player_id != goalkeeper.player_id


def test_booked_players_have_at_least_one_recorded_foul() -> None:
    simulator = FastMatchSimulator()
    for seed in range(1, 90):
        result = simulator.simulate(build_demo_snapshot(seed=seed))
        for stat in result.player_statistics:
            if stat.yellow_cards or stat.red_cards:
                # Second yellow and its red are one foul, not two.
                minimum = max(stat.yellow_cards, stat.red_cards)
                assert stat.fouls >= minimum, (seed, stat.player_id)


def test_keeper_expulsion_reduces_defending_effectiveness() -> None:
    from football_manager.fast_simulation.engine import _TeamRuntime
    from football_manager.fast_simulation.profiles import build_fast_team_profile
    from football_manager.fast_simulation.randomness import FastMatchRandom

    snapshot = build_demo_snapshot(seed=12)
    simulator = FastMatchSimulator()
    keeper = next(p for p in snapshot.home_team.starters if p.assigned_position.value == 'GK')
    outfielder = next(p for p in snapshot.home_team.starters if p.assigned_position.value == 'ST')
    conceded_after_keeper_red = conceded_after_outfield_red = 0
    for seed in range(250):
        def away_goals_with_dismissal(player_id: str) -> int:
            home = _TeamRuntime(snapshot.home_team, build_fast_team_profile(snapshot.home_team))
            away = _TeamRuntime(snapshot.away_team, build_fast_team_profile(snapshot.away_team))
            home.dismissed_at[player_id] = 10
            simulator._simulate_shot_windows(
                away, home, minutes=90, minute_start=1, minute_end=90,
                home_advantage=False, random=FastMatchRandom(seed).fork('away'),
            )
            return sum(shot.goal for shot in away.shots)

        conceded_after_keeper_red += away_goals_with_dismissal(keeper.player_id)
        conceded_after_outfield_red += away_goals_with_dismissal(outfielder.player_id)

    assert conceded_after_keeper_red > conceded_after_outfield_red * 1.08
