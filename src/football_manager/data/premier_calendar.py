"""Premier League date-slot template for fictional DEV leagues.

The source is the stored 380-kickoff *official* 2026/27 schedule.  Only
kickoff slots are reused: imaginary clubs and future opponents are never
labelled official.  Future years project the same week/weekday/time pattern,
then the international blackout overlay may move only affected fixtures.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta, timezone

from football_manager.data.official_schedule import load_premier_league_2026_27
from football_manager.domain.calendar import (
    ScheduleSource, ScheduledFixture, SeasonCalendar,
    reprogram_pending_fixtures_for_blackouts,
)
from football_manager.domain.competition import CompetitionEdition
from football_manager.domain.international_calendar import (
    InternationalCalendar, build_international_calendar,
)


def _last_sunday(year: int, month: int) -> date:
    first_next = date(year + (month == 12), month % 12 + 1, 1)
    last = first_next - timedelta(days=1)
    return last - timedelta(days=(last.weekday() + 1) % 7)


def _uk_kickoff_timezone(day: date) -> timezone:
    """UK matchday offset without external tzdata (Windows Python safe).

    Football kickoffs use daytime/evening hours; DST clocks change in the
    early hours of the last Sundays of March and October.
    """
    summer = _last_sunday(day.year, 3) <= day < _last_sunday(day.year, 10)
    return timezone(timedelta(hours=1 if summer else 0))


def _project_date(source: date, year: int) -> date:
    """Preserve reference weekday near the same day/month, not +365 days."""
    target_year = year if source.month >= 8 else year + 1
    anchor = date(target_year, source.month, source.day)
    return min(
        (anchor + timedelta(days=shift) for shift in range(-3, 4)
         if (anchor + timedelta(days=shift)).weekday() == source.weekday()),
        key=lambda day: abs((day - anchor).days),
    )


def premier_reference_slots(year: int) -> dict[int, tuple[datetime, ...]]:
    """38 sets of ten UTC kickoff slots, projected from 2026/27 for later years.

    The baseline is not a promise of future broadcaster selections.  Kickoff
    distribution changes only when the scheduler moves a fixture for real
    clashes (including FIFA pauses and later cup/UEFA rounds).
    """
    if year < 2026:
        raise ValueError("Premier template cannot be projected before 2026")
    slots: dict[int, list[datetime]] = defaultdict(list)
    for fixture in load_premier_league_2026_27().calendar.fixtures:
        assert fixture.kickoff is not None and fixture.round_number is not None
        local = fixture.kickoff  # published ISO 8601 kickoff has its UK UTC offset
        if year == 2026:
            planned = fixture.kickoff.astimezone(timezone.utc)
        else:
            projected = _project_date(local.date(), year)
            planned = datetime.combine(
                projected, local.time(), tzinfo=_uk_kickoff_timezone(projected),
            ).astimezone(timezone.utc)
        slots[fixture.round_number].append(planned)
    if sorted(slots) != list(range(1, 39)) or any(len(group) != 10 for group in slots.values()):
        raise ValueError("Premier reference must contain 38 matchweeks with 10 slots each")
    return {number: tuple(sorted(group)) for number, group in slots.items()}


def build_premier_calendar(
    edition: CompetitionEdition, year: int,
    *, international_calendar: InternationalCalendar | None = None,
) -> SeasonCalendar:
    """Assign the real date pattern to fictional pairings, then overlay FIFA.

    Changes after cup/UEFA advancement are handled by WorldSeasonRunner using
    these fixture IDs.  Neither the competition draw nor a result is replaced.
    """
    template = premier_reference_slots(year)
    by_round: dict[int, list] = defaultdict(list)
    for fixture in edition.fixtures:
        if fixture.round_number not in template:
            raise ValueError("invalid Premier round")
        by_round[fixture.round_number].append(fixture)
    if len(edition.fixtures) != 380 or len(by_round) != 38:
        raise ValueError("Premier date template requires 380 sporting fixtures")
    scheduled: list[ScheduledFixture] = []
    for number in sorted(by_round):
        group = sorted(by_round[number], key=lambda item: item.fixture_id)
        if len(group) != 10:
            raise ValueError(f"Premier round {number} requires ten fixtures")
        for match, kickoff in zip(group, template[number]):
            scheduled.append(ScheduledFixture(
                fixture_id=match.fixture_id,
                competition_id=edition.competition_id,
                edition_id=match.edition_id,
                stage_id=match.stage_id,
                home_club_id=match.home_club_id,
                away_club_id=match.away_club_id,
                kickoff=kickoff,
                source=ScheduleSource.GENERATED,
                round_number=number,
                leg_number=match.leg_number,
            ))
    season = f"{year}/{(year + 1) % 100:02d}"
    baseline = SeasonCalendar(season, "UTC", tuple(scheduled))
    master = international_calendar or build_international_calendar(year, year + 1)
    adjusted = reprogram_pending_fixtures_for_blackouts(
        baseline,
        blackout_periods=master.league_blackouts(date(year, 8, 1), date(year + 1, 6, 15)),
        earliest_date=date(year, 8, 1),
        latest_date=date(year + 1, 6, 15),
    )
    conflicts = adjusted.detect_conflicts(minimum_rest_hours=48)
    if conflicts:
        raise ValueError(f"Premier kickoff template produces {len(conflicts)} rest conflicts")
    return adjusted
