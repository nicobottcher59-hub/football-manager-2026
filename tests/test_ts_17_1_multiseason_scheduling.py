"""TS-17.1: career-long scheduling and atomic displacement regressions."""
from datetime import date, datetime, timedelta, timezone

import pytest

from football_manager.dev_ui.session import DevelopmentSession
from football_manager.domain.calendar import ScheduleSource, ScheduledFixture
from football_manager.domain.world_runner import WorldSeasonRunner


def test_league_replacement_can_find_a_gap_after_seven_weeks(monkeypatch):
    world = WorldSeasonRunner(season_label="2027/28")
    anchor = datetime(2027, 9, 8, 19, 45, tzinfo=timezone.utc)
    league = ScheduledFixture(
        "league-r05", "test-league", "test-edition", "league",
        "A", "B", anchor - timedelta(days=1), ScheduleSource.GENERATED,
    )

    def fake_conflicts(kickoff, home, away):
        return [league] if kickoff.date() >= anchor.date() + timedelta(days=50) else [
            league, ScheduledFixture(
                "busy", "protected", "protected-edition", "league", "A", "C",
                kickoff, ScheduleSource.OFFICIAL,
            ),
        ]

    monkeypatch.setattr(world, "_matching_conflicts", fake_conflicts)
    moved = world._find_league_replacement(league, anchor)
    assert moved.date() == anchor.date() + timedelta(days=50)
    assert moved.year == 2027


def test_multiple_planned_displacements_reserve_each_others_times():
    world = WorldSeasonRunner(season_label="2027/28")
    anchor = datetime(2027, 9, 8, 19, 45, tzinfo=timezone.utc)
    first = ScheduledFixture(
        "a", "test", "test-edition", "league", "A", "B",
        anchor, ScheduleSource.GENERATED,
    )
    second = ScheduledFixture(
        "b", "test", "test-edition", "league", "B", "C",
        anchor + timedelta(hours=1), ScheduleSource.GENERATED,
    )
    world.fixtures.update(a=first, b=second)
    plan = world._plan_league_displacements([first, second], anchor)
    assert plan is not None
    assert len(plan) == 2
    assert abs((plan[0][1] - plan[1][1]).total_seconds()) >= 48 * 3600
    assert plan[0][1].date() != plan[1][1].date()


def test_real_career_second_season_finishes_and_scheduled_games_are_valid():
    session = DevelopmentSession()
    session.simulate_remaining_season()
    session.begin_next_season()
    managed = session.simulate_remaining_season()
    assert managed >= 1
    world = session._world
    assert world.season_label == "2027/28"
    assert session.season_finished
    assert len(world.fixtures) == len(world.results)
    world.validate_integrity()
    displaced = world.fixtures["dev-league-two-2027-28-league-r05-m055"]
    assert displaced.original_kickoff is not None
    assert displaced.kickoff > displaced.original_kickoff


def test_six_complete_seasons_keep_knockout_legs_in_order():
    # The sixth career year formerly put Europa League leg 2 before leg 1,
    # causing a KeyError when the world tried to simulate the deciding leg.
    session = DevelopmentSession()
    for number in range(6):
        if number:
            session.begin_next_season()
        assert session.simulate_remaining_season() > 0
        world = session._world
        assert session.season_finished
        assert set(world.results) == set(world.fixtures)
        world.validate_integrity()
        for staged in world.staged.values():
            for plan in staged.knockout_plans:
                for tie in plan.ties:
                    times = [world.fixtures[f.fixture_id].kickoff for f in
                             sorted(tie.fixtures, key=lambda x: x.leg_number)]
                    assert times == sorted(times)


def test_uefa_search_reaches_second_window_if_first_needs_impossible_league_move(monkeypatch):
    from football_manager.data.staged_2026_27 import build_uefa_2026_27

    entrants = tuple(f"synthetic-{i:02d}" for i in range(36))
    competition = build_uefa_2026_27('champions-league', entrants, seed=991)
    fixture = competition.primary_fixtures[0]
    day = competition.primary_dates[0]
    world = WorldSeasonRunner()
    world.leagues['fake-league'] = object()
    blocked = ScheduledFixture(
        'fake-blocked', 'fake-league', 'fake-edition', 'league',
        fixture.home_club_id, 'other',
        datetime.combine(day, datetime.min.time(), timezone.utc), ScheduleSource.GENERATED,
    )
    monkeypatch.setattr(world, '_matching_conflicts',
                        lambda kickoff, home, away: [blocked]
                        if abs((kickoff.date() - day).days) <= 8 else [])

    def no_replacement(*args, **kwargs):
        raise ValueError('no valid league move')

    monkeypatch.setattr(world, '_find_league_replacement', no_replacement)
    world._schedule_staged_fixture(competition, fixture, day)
    assert abs((world.fixtures[fixture.fixture_id].kickoff.date() - day).days) > 8


def test_cup_search_reaches_second_window_if_first_needs_impossible_league_move(monkeypatch):
    from types import SimpleNamespace

    world = WorldSeasonRunner()
    world.leagues['fake-league'] = object()
    day = date(2026, 9, 9)
    blocked = ScheduledFixture(
        'fake-blocked', 'fake-league', 'fake-edition', 'league', 'A', 'other',
        datetime(2026, 9, 9, 15, tzinfo=timezone.utc), ScheduleSource.GENERATED,
    )
    monkeypatch.setattr(world, '_matching_conflicts',
                        lambda kickoff, home, away: [blocked]
                        if abs((kickoff.date() - day).days) <= 10 else [])

    def no_replacement(*args, **kwargs):
        raise ValueError('no valid league move')

    monkeypatch.setattr(world, '_find_league_replacement', no_replacement)
    world._insert_cup_match(
        fixture_id='new-cup-game',
        cup=SimpleNamespace(cup_id='carabao-cup', edition_id='carabao-cup-2026-27'),
        rule_id='round-3', home='A', away='B', leg_number=1, round_number=3,
        candidates=(day,),
    )
    assert (world.fixtures['new-cup-game'].kickoff.date() - day).days >= 11
