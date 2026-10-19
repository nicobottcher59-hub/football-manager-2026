"""TC-E1.1: apply FIFA reflow to the first playable 2026/27 season."""
from datetime import date, datetime, timezone

import pytest

from football_manager.dev_ui.session import DevelopmentSession
from football_manager.domain.calendar import (
    CalendarBlock, ScheduleSource, ScheduledFixture, ScheduledFixtureStatus,
    SeasonCalendar, reprogram_pending_fixtures_for_blackouts,
)
from football_manager.domain.world_runner import WorldSeasonRunner
from football_manager.ui_shell.calendar import calendar_read_model


@pytest.fixture(scope="module")
def first_season() -> DevelopmentSession:
    return DevelopmentSession()


def test_first_season_has_master_and_no_games_during_fifa_breaks(first_season):
    game = first_season
    world = game._world
    assert world.season_label == "2026/27"
    assert world.international_calendar is not None
    assert not world.international_window_violations()
    assert not world.calendar.detect_conflicts(minimum_rest_hours=48)
    assert len(world.fixtures) == 2620
    assert game.current_date == date(2026, 8, 21)
    assert game._active_match.match_date == game.current_date
    assert game._active_match.fixture.fixture_id not in world.results
    assert all(item.kickoff.date() <= game.current_date for item in world.fixtures.values()
               if item.status is ScheduledFixtureStatus.PLAYED)
    assert any(item.is_rescheduled for item in world.fixtures.values()
               if item.competition_id == "dev-league-one")
    assert any(item.is_rescheduled for item in world.fixtures.values()
               if item.competition_id == "efl-trophy")


def test_premier_official_date_slots_remain_the_base_after_cup_reflow(first_season):
    from football_manager.data.premier_calendar import premier_reference_slots
    world = first_season._world
    template = premier_reference_slots(2026)
    rounds = {}
    for fixture in world.fixtures.values():
        if fixture.competition_id == "dev-premier":
            rounds.setdefault(fixture.round_number, []).append(fixture)
    assert len(rounds) == 38
    for number in range(1, 39):
        # Some fixtures get a new date after a cup or UEFA booking. Their
        # originally published slot must still be available as provenance.
        original = sorted(f.original_kickoff or f.kickoff for f in rounds[number])
        assert original == list(template[number])
    assert not any(f.kickoff.date() == date(2026, 9, 26)
                   for group in rounds.values() for f in group)
    assert any((f.kickoff.weekday() == 4) for group in rounds.values() for f in group)
    assert any((f.kickoff.weekday() == 6) for group in rounds.values() for f in group)
    # An already valid published slot must not move just to look varied.


def test_calendar_and_world_show_exactly_the_same_reprogrammed_fixture(first_season):
    game = first_season
    calendar = calendar_read_model(game)
    assert len(calendar["fifa_windows"]) == 4
    for row in calendar["matches"]:
        fixture = game._world.fixtures[row["id"]]
        assert row["date"] == fixture.kickoff.date().isoformat()
        assert row["rescheduled"] == fixture.is_rescheduled
        if fixture.is_rescheduled:
            assert row["original_date"] == fixture.original_kickoff.date().isoformat()
    assert not any(row["date"] == "2026-09-26" for row in calendar["matches"])


def test_release_only_tournaments_do_not_suspend_english_leagues(first_season):
    master = first_season._world.international_calendar
    assert master is not None
    assert any("Asian" in e.name for e in master.release_events_on(date(2027, 1, 20)))
    assert not master.stops_club_football(date(2027, 1, 20))
    assert first_season._world.international_window_violations() == ()


def test_fixture_reflow_is_atomic_and_never_moves_played_games():
    forbidden = CalendarBlock(date(2026, 9, 21), date(2026, 10, 6))
    played = ScheduledFixture(
        "already-played", "league", "edition", "league", "red", "blue",
        datetime(2026, 9, 23, 15, tzinfo=timezone.utc), ScheduleSource.GENERATED,
        status=ScheduledFixtureStatus.PLAYED,
    )
    pending = ScheduledFixture(
        "needs-moving", "league", "edition", "league", "red", "green",
        datetime(2026, 9, 26, 15, tzinfo=timezone.utc), ScheduleSource.GENERATED,
    )
    original = SeasonCalendar("2026/27", "UTC", (played, pending))
    with pytest.raises(ValueError, match="no safe date"):
        reprogram_pending_fixtures_for_blackouts(
            original, blackout_periods=(forbidden,),
            earliest_date=date(2026, 8, 15), latest_date=date(2026, 10, 6),
        )
    assert original.fixture("needs-moving").kickoff == pending.kickoff
    moved = reprogram_pending_fixtures_for_blackouts(
        original, blackout_periods=(forbidden,),
        earliest_date=date(2026, 8, 15), latest_date=date(2026, 11, 15),
    )
    assert moved.fixture("already-played") == played
    assert moved.fixture("needs-moving").original_kickoff == pending.kickoff
    assert moved.fixture("needs-moving").kickoff.date() > forbidden.end_date
    assert original.fixture("needs-moving") == pending


def test_initial_world_can_finish_with_no_window_or_rest_conflicts(first_season):
    # Use a copy so other tests continue to inspect the initial, untouched fixture slate.
    world = WorldSeasonRunner.from_dict(first_season._world.to_dict())
    progress = world.advance_until(date(2027, 6, 15))
    assert progress.stopped_for_managed_fixture_id is None
    assert len(world.fixtures) == len(world.results) == 2959
    assert not world.international_window_violations()
    assert not world.calendar.detect_conflicts(minimum_rest_hours=48)
