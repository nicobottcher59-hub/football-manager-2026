from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone

import pytest

from football_manager.domain import (
    CalendarBlock,
    CalendarConflictKind,
    CompetitionFixture,
    LeagueSchedulingPolicy,
    ScheduleSource,
    SchedulingWindow,
    ScheduledFixture,
    ScheduledFixtureStatus,
    SeasonCalendar,
    find_available_kickoff,
    generate_league_round_dates,
    merge_calendars,
    reschedule_fixture_into_window,
    schedule_fixtures_on_round_dates,
)


def _fixture(
    fixture_id: str,
    home: str,
    away: str,
    *,
    round_number: int = 1,
) -> CompetitionFixture:
    return CompetitionFixture(
        fixture_id=fixture_id,
        edition_id="league-2027",
        stage_id="league",
        home_club_id=home,
        away_club_id=away,
        round_number=round_number,
    )


def _scheduled(
    fixture_id: str,
    home: str,
    away: str,
    kickoff: datetime,
) -> ScheduledFixture:
    return ScheduledFixture(
        fixture_id=fixture_id,
        competition_id="league",
        edition_id="league-2027",
        stage_id="league",
        home_club_id=home,
        away_club_id=away,
        kickoff=kickoff,
        source=ScheduleSource.GENERATED,
    )


def test_scheduled_fixture_requires_timezone_aware_kickoff() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        _scheduled("f1", "a", "b", datetime(2027, 8, 14, 15, 0))


def test_scheduled_fixture_round_trip_preserves_reschedule_provenance() -> None:
    original = datetime(2027, 8, 14, 15, tzinfo=timezone.utc)
    moved = datetime(2027, 8, 15, 16, 30, tzinfo=timezone.utc)
    fixture = ScheduledFixture(
        fixture_id="f1",
        competition_id="league",
        edition_id="league-2027",
        stage_id="league",
        home_club_id="a",
        away_club_id="b",
        kickoff=moved,
        source=ScheduleSource.OFFICIAL,
        round_number=1,
        original_kickoff=original,
    )

    restored = ScheduledFixture.from_dict(fixture.to_dict())

    assert restored == fixture
    assert restored.is_rescheduled


def test_season_calendar_returns_club_fixtures_in_chronological_order() -> None:
    later = _scheduled(
        "later",
        "a",
        "c",
        datetime(2027, 8, 21, 15, tzinfo=timezone.utc),
    )
    earlier = _scheduled(
        "earlier",
        "b",
        "a",
        datetime(2027, 8, 14, 15, tzinfo=timezone.utc),
    )
    calendar = SeasonCalendar("2027/28", "UTC", (later, earlier))

    assert [item.fixture_id for item in calendar.fixtures_for_club("a")] == [
        "earlier",
        "later",
    ]


def test_next_fixture_ignores_played_postponed_and_other_clubs() -> None:
    played = _scheduled(
        "played",
        "a",
        "b",
        datetime(2027, 8, 14, 15, tzinfo=timezone.utc),
    )
    played = ScheduledFixture.from_dict({**played.to_dict(), "status": "played"})
    postponed = ScheduledFixture(
        fixture_id="postponed",
        competition_id="league",
        edition_id="league-2027",
        stage_id="league",
        home_club_id="a",
        away_club_id="c",
        kickoff=None,
        source=ScheduleSource.GENERATED,
        status=ScheduledFixtureStatus.POSTPONED,
    )
    other = _scheduled(
        "other",
        "d",
        "e",
        datetime(2027, 8, 15, 15, tzinfo=timezone.utc),
    )
    upcoming = _scheduled(
        "upcoming",
        "c",
        "a",
        datetime(2027, 8, 21, 15, tzinfo=timezone.utc),
    )
    calendar = SeasonCalendar("2027/28", "UTC", (played, postponed, other, upcoming))

    assert calendar.next_fixture(
        "a", after=datetime(2027, 8, 13, 12, tzinfo=timezone.utc)
    ) == upcoming


def test_postpone_then_reschedule_preserves_original_kickoff() -> None:
    kickoff = datetime(2027, 8, 14, 15, tzinfo=timezone.utc)
    moved = datetime(2027, 8, 18, 19, 45, tzinfo=timezone.utc)
    calendar = SeasonCalendar("2027/28", "UTC", (_scheduled("f1", "a", "b", kickoff),))

    postponed = calendar.postpone("f1")
    assert postponed.fixture("f1").status is ScheduledFixtureStatus.POSTPONED
    assert postponed.fixture("f1").kickoff is None
    assert postponed.fixture("f1").original_kickoff == kickoff
    assert not postponed.fixture("f1").is_rescheduled

    rescheduled = postponed.reschedule("f1", moved)
    assert rescheduled.fixture("f1").status is ScheduledFixtureStatus.SCHEDULED
    assert rescheduled.fixture("f1").kickoff == moved
    assert rescheduled.fixture("f1").original_kickoff == kickoff
    assert rescheduled.fixture("f1").is_rescheduled


def test_mark_played_updates_only_requested_fixture() -> None:
    first = _scheduled(
        "f1", "a", "b", datetime(2027, 8, 14, 15, tzinfo=timezone.utc)
    )
    second = _scheduled(
        "f2", "c", "d", datetime(2027, 8, 14, 15, tzinfo=timezone.utc)
    )
    calendar = SeasonCalendar("2027/28", "UTC", (first, second)).mark_played("f1")

    assert calendar.fixture("f1").status is ScheduledFixtureStatus.PLAYED
    assert calendar.fixture("f2").status is ScheduledFixtureStatus.SCHEDULED


def test_calendar_blocks_invalid_status_transitions() -> None:
    kickoff = datetime(2027, 8, 14, 15, tzinfo=timezone.utc)
    scheduled = SeasonCalendar("2027/28", "UTC", (_scheduled("f1", "a", "b", kickoff),))
    played = scheduled.mark_played("f1")
    postponed = scheduled.postpone("f1")
    cancelled = scheduled.cancel("f1")

    with pytest.raises(ValueError, match="only a scheduled fixture"):
        played.postpone("f1")
    with pytest.raises(ValueError, match="only a scheduled fixture"):
        played.mark_played("f1")
    with pytest.raises(ValueError, match="only a scheduled fixture"):
        postponed.mark_played("f1")
    with pytest.raises(ValueError, match="scheduled or postponed"):
        played.reschedule("f1", kickoff)
    with pytest.raises(ValueError, match="scheduled or postponed"):
        cancelled.reschedule("f1", kickoff)
    assert cancelled.fixture("f1").status is ScheduledFixtureStatus.CANCELLED
    assert cancelled.next_fixture("a", after=kickoff - timedelta(days=1)) is None
    cancelled_postponement = postponed.cancel("f1")
    assert cancelled_postponement.fixture("f1").kickoff is None
    assert cancelled_postponement.fixture("f1").original_kickoff == kickoff
    assert SeasonCalendar.from_dict(cancelled_postponement.to_dict()) == cancelled_postponement


def test_detect_conflicts_finds_same_club_same_kickoff() -> None:
    kickoff = datetime(2027, 8, 14, 15, tzinfo=timezone.utc)
    calendar = SeasonCalendar(
        "2027/28",
        "UTC",
        (
            _scheduled("f1", "a", "b", kickoff),
            _scheduled("f2", "c", "a", kickoff),
        ),
    )

    conflicts = calendar.detect_conflicts()

    assert len(conflicts) == 1
    assert conflicts[0].kind is CalendarConflictKind.SAME_CLUB_OVERLAP
    assert conflicts[0].club_id == "a"


def test_same_day_double_booking_is_detected_with_different_kickoffs() -> None:
    calendar = SeasonCalendar(
        "2027/28",
        "UTC",
        (
            _scheduled("league", "a", "b", datetime(2027, 8, 14, 12, tzinfo=timezone.utc)),
            _scheduled("cup", "c", "a", datetime(2027, 8, 14, 20, tzinfo=timezone.utc)),
        ),
    )
    conflicts = calendar.detect_conflicts(minimum_rest_hours=0)
    assert len(conflicts) == 1
    assert conflicts[0].kind is CalendarConflictKind.SAME_CLUB_OVERLAP
    assert conflicts[0].gap_hours == 8


def test_detect_conflicts_can_enforce_minimum_rest_window() -> None:
    first = datetime(2027, 8, 14, 15, tzinfo=timezone.utc)
    second = datetime(2027, 8, 16, 12, tzinfo=timezone.utc)
    calendar = SeasonCalendar(
        "2027/28",
        "UTC",
        (
            _scheduled("f1", "a", "b", first),
            _scheduled("f2", "c", "a", second),
        ),
    )

    conflicts = calendar.detect_conflicts(minimum_rest_hours=48)

    assert len(conflicts) == 1
    assert conflicts[0].kind is CalendarConflictKind.INSUFFICIENT_REST
    assert conflicts[0].gap_hours == pytest.approx(45.0)


def test_schedule_fixtures_on_round_dates_preserves_sporting_fixture_identity() -> None:
    fixtures = (
        _fixture("r1-a", "a", "b", round_number=1),
        _fixture("r2-a", "b", "a", round_number=2),
    )
    dates = {
        1: datetime(2027, 8, 14, 15, tzinfo=timezone.utc),
        2: datetime(2027, 8, 21, 15, tzinfo=timezone.utc),
    }

    scheduled = schedule_fixtures_on_round_dates(
        fixtures,
        dates,
        competition_id="league",
    )

    assert [item.fixture_id for item in scheduled] == ["r1-a", "r2-a"]
    assert scheduled[0].kickoff == dates[1]
    assert scheduled[0].source is ScheduleSource.GENERATED


def test_round_date_generation_uses_new_season_rules_and_skips_blackout() -> None:
    policy = LeagueSchedulingPolicy(
        season_start=date(2027, 8, 13),
        season_end=date(2027, 9, 30),
        preferred_weekday=5,
        kickoff_local_time=time(15, 0),
        blackout_periods=(
            CalendarBlock(date(2027, 8, 21), date(2027, 8, 22), "International break"),
        ),
    )

    dates = generate_league_round_dates(3, policy)

    assert dates[1].date() == date(2027, 8, 14)
    assert dates[2].date() == date(2027, 9, 4)
    assert dates[3].date() == date(2027, 9, 25)


def test_future_38_round_season_spans_full_window_and_can_use_midweeks() -> None:
    policy = LeagueSchedulingPolicy(
        season_start=date(2027, 8, 14),
        season_end=date(2028, 5, 28),
        blackout_periods=(
            CalendarBlock(date(2027, 9, 4), date(2027, 9, 14), "International"),
            CalendarBlock(date(2027, 10, 2), date(2027, 10, 12), "International"),
            CalendarBlock(date(2027, 11, 13), date(2027, 11, 23), "International"),
            CalendarBlock(date(2028, 3, 18), date(2028, 3, 28), "International"),
            CalendarBlock(date(2028, 4, 1), date(2028, 4, 7), "Cup"),
        ),
    )
    result = generate_league_round_dates(38, policy)
    values = tuple(result.values())

    assert len(values) == 38
    assert values[0].date() == date(2027, 8, 14)
    assert values[-1].date() == date(2028, 5, 27)
    assert sum(item.weekday() in (1, 2) for item in values) > 0
    assert all((later - earlier).days >= 3 for earlier, later in zip(values, values[1:]))
    assert all(
        not any(block.contains(item.date()) for block in policy.blackout_periods)
        for item in values
    )


def test_future_season_policy_rejects_duplicate_or_out_of_range_midweek_days() -> None:
    with pytest.raises(ValueError, match="midweek weekdays must be unique"):
        LeagueSchedulingPolicy(date(2027, 8, 1), date(2028, 5, 1), midweek_weekdays=(1, 1))
    with pytest.raises(ValueError, match="midweek weekdays must be in range"):
        LeagueSchedulingPolicy(date(2027, 8, 1), date(2028, 5, 1), midweek_weekdays=(7,))


def test_round_date_generation_refuses_impossible_window() -> None:
    policy = LeagueSchedulingPolicy(
        season_start=date(2027, 8, 1),
        season_end=date(2027, 8, 8),
    )
    with pytest.raises(ValueError, match="cannot fit"):
        generate_league_round_dates(3, policy)


def test_merge_calendars_combines_competitions_and_rejects_duplicate_fixture_ids() -> None:
    first = SeasonCalendar(
        "2027/28",
        "UTC",
        (
            _scheduled(
                "league-f1",
                "a",
                "b",
                datetime(2027, 8, 14, 15, tzinfo=timezone.utc),
            ),
        ),
    )
    cup_fixture = ScheduledFixture(
        fixture_id="cup-f1",
        competition_id="cup",
        edition_id="cup-2027",
        stage_id="r1",
        home_club_id="a",
        away_club_id="c",
        kickoff=datetime(2027, 8, 18, 19, 45, tzinfo=timezone.utc),
        source=ScheduleSource.GENERATED,
    )
    second = SeasonCalendar("2027/28", "UTC", (cup_fixture,))

    merged = merge_calendars(first, second)
    assert {item.competition_id for item in merged.fixtures_for_club("a")} == {
        "league",
        "cup",
    }

    with pytest.raises(ValueError, match="duplicate fixture IDs"):
        merge_calendars(first, first)


def test_season_calendar_round_trip() -> None:
    calendar = SeasonCalendar(
        "2027/28",
        "UTC",
        (
            _scheduled(
                "f1",
                "a",
                "b",
                datetime(2027, 8, 14, 15, tzinfo=timezone.utc),
            ),
        ),
    )

    assert SeasonCalendar.from_dict(calendar.to_dict()) == calendar


def test_development_session_uses_season_calendar_as_chronology_source() -> None:
    from football_manager.dev_ui import DevelopmentSession

    session = DevelopmentSession()
    scheduled = session._season_calendar.fixtures_for_club(session.home_club.id)

    assert len(scheduled) >= 38
    assert session._active_match is not None
    assert scheduled[0].fixture_id == session._active_match.fixture.fixture_id
    assert all(item.source is ScheduleSource.GENERATED for item in scheduled)


def test_development_quick_sim_marks_calendar_fixture_played_before_continue() -> None:
    from football_manager.dev_ui import DevelopmentSession

    session = DevelopmentSession()
    active_id = session._active_match.fixture.fixture_id

    session.quick_simulate()

    assert session._season_calendar.fixture(active_id).status is ScheduledFixtureStatus.PLAYED
    next_item = session._next_unplayed_managed_match()
    assert next_item is not None
    assert next_item.fixture.fixture_id != active_id


def test_development_official_calendar_inspector_exposes_all_380_real_fixtures() -> None:
    from football_manager.dev_ui import DevelopmentSession

    session = DevelopmentSession()

    assert len(session.official_calendar_rows) == 380
    assert session.official_calendar_rows[0].home == "Arsenal"
    assert session.official_calendar_rows[0].away == "Coventry City"
    assert session.official_calendar_rows[0].kickoff == "20:00 BST"
    assert session.official_calendar_rows[0].source == "OFFICIAL"
    assert "380 fixtures" in session.official_calendar_summary


def test_development_competition_inspector_lists_official_premier_dataset_separately() -> None:
    from football_manager.dev_ui import DevelopmentSession

    session = DevelopmentSession()
    names = {name for name, _format, _status in session.competition_rows}

    assert "Premier League" in names
    assert "Premier League 2026/27 official data" in names


def test_find_available_kickoff_skips_slots_that_violate_rest_window() -> None:
    existing = _scheduled(
        "existing",
        "a",
        "x",
        datetime(2027, 1, 5, 20, tzinfo=timezone.utc),
    )
    calendar = SeasonCalendar("2026/27", "UTC", (existing,))
    window = SchedulingWindow(
        "cup-r4",
        date(2027, 1, 6),
        date(2027, 1, 9),
        allowed_weekdays=(2, 3, 4, 5),
        label="Cup round 4",
    )

    kickoff = find_available_kickoff(
        calendar,
        club_ids=("a", "b"),
        window=window,
        kickoff_local_time=time(20, 0),
        minimum_rest_hours=48,
    )

    assert kickoff == datetime(2027, 1, 7, 20, tzinfo=timezone.utc)


def test_available_kickoff_never_assigns_two_games_to_same_club_same_day() -> None:
    existing = _scheduled("league", "a", "b", datetime(2027, 1, 6, 15, tzinfo=timezone.utc))
    calendar = SeasonCalendar("2026/27", "UTC", (existing,))
    window = SchedulingWindow("cup", date(2027, 1, 6), date(2027, 1, 7))

    kickoff = find_available_kickoff(
        calendar,
        club_ids=("a", "c"),
        window=window,
        kickoff_local_time=time(20),
        minimum_rest_hours=0,
    )
    assert kickoff.date() == date(2027, 1, 7)


def test_reschedule_fixture_into_window_moves_match_and_keeps_original_date() -> None:
    original = datetime(2027, 1, 6, 20, tzinfo=timezone.utc)
    fixture = _scheduled("cup", "a", "b", original)
    blocker = _scheduled(
        "league",
        "a",
        "c",
        datetime(2027, 1, 5, 20, tzinfo=timezone.utc),
    )
    calendar = SeasonCalendar("2026/27", "UTC", (fixture, blocker))
    window = SchedulingWindow(
        "cup-window",
        date(2027, 1, 6),
        date(2027, 1, 10),
        allowed_weekdays=(2, 3, 4, 5, 6),
    )

    updated = reschedule_fixture_into_window(
        calendar,
        "cup",
        window=window,
        kickoff_local_time=time(20, 0),
        minimum_rest_hours=48,
    )

    moved = updated.fixture("cup")
    assert moved.kickoff == datetime(2027, 1, 7, 20, tzinfo=timezone.utc)
    assert moved.original_kickoff == original
    assert moved.is_rescheduled
