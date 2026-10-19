"""Read-only calendar integrity checks at world save/load boundaries.

Fixture placement is handled by the schedulers.  This module validates the
finished ledger without shifting published kickoffs, changing results, or
requiring an O(number-of-fixtures) scan after every simulated match.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Mapping, Sequence

from .calendar import (
    ScheduleSource,
    ScheduledFixture,
    ScheduledFixtureStatus,
    SeasonCalendar,
)
from .domestic_cups import DomesticCupSeason
from .international_calendar import InternationalCalendar
from .staged_world import StagedWorldCompetition


# Mirrors the minimum separation currently used by the world scheduler.  A
# future ruleset could make this edition-specific; do not silently relax it.
MINIMUM_KICKOFF_REST_HOURS = 48.0
_ACTIVE = frozenset((ScheduledFixtureStatus.SCHEDULED, ScheduledFixtureStatus.PLAYED))


def _bounds(
    fixtures: Sequence,
    by_id: Mapping[str, ScheduledFixture],
) -> tuple[datetime | None, datetime | None]:
    """Earliest and latest active kickoff in a sporting round/phase."""
    kickoffs = [by_id[item.fixture_id].kickoff for item in fixtures
                if by_id[item.fixture_id].status in _ACTIVE
                and by_id[item.fixture_id].kickoff is not None]
    return (min(kickoffs), max(kickoffs)) if kickoffs else (None, None)


def _check_round_sequence(
    competition_id: str,
    rounds: Sequence[Sequence],
    by_id: Mapping[str, ScheduledFixture],
) -> None:
    previous_end: datetime | None = None
    for sporting_fixtures in rounds:
        start, end = _bounds(sporting_fixtures, by_id)
        if start is not None and previous_end is not None:
            if start < previous_end + timedelta(hours=MINIMUM_KICKOFF_REST_HOURS):
                raise ValueError(
                    f"calendar round chronology error in {competition_id}: "
                    "a round precedes the completed scheduling window of its predecessor"
                )
        if end is not None:
            previous_end = end


def _check_tie_legs(
    competition_id: str,
    plans: Sequence,
    by_id: Mapping[str, ScheduledFixture],
) -> None:
    for plan in plans:
        for tie in plan.ties:
            previous: datetime | None = None
            for sporting in sorted(tie.fixtures, key=lambda item: item.leg_number):
                scheduled = by_id[sporting.fixture_id]
                if scheduled.kickoff is None or scheduled.status not in _ACTIVE:
                    continue
                if previous is not None and scheduled.kickoff <= previous:
                    raise ValueError(f"calendar tie-leg chronology error in {competition_id}")
                previous = scheduled.kickoff


def validate_calendar_invariants(
    calendar: SeasonCalendar,
    *,
    international_calendar: InternationalCalendar | None,
    cups: Mapping[str, DomesticCupSeason],
    staged: Mapping[str, StagedWorldCompetition],
) -> None:
    """Reject incompatible kickoffs while preserving official-source exceptions.

    An official imported fixture remains authoritative if its date overlaps a
    club-break window, but is still subject to same-club/rest checks. Generated
    fixtures must never be inserted into mandatory club-break windows. Player
    release-only events do not stop club matches.
    """
    for fixture in calendar.fixtures:
        if fixture.status is ScheduledFixtureStatus.POSTPONED and fixture.kickoff is not None:
            raise ValueError(
                f"postponed fixture {fixture.fixture_id} must not retain an active kickoff"
            )

    conflicts = calendar.detect_conflicts(minimum_rest_hours=MINIMUM_KICKOFF_REST_HOURS)
    if conflicts:
        first = conflicts[0]
        raise ValueError(
            f"calendar conflict ({first.kind.value}) for club {first.club_id}: "
            f"{first.first_fixture_id} vs {first.second_fixture_id} "
            f"({first.gap_hours:.1f} hours between kickoffs)"
        )

    if international_calendar is not None:
        for fixture in calendar.fixtures:
            if (fixture.status in _ACTIVE and fixture.source is ScheduleSource.GENERATED
                    and fixture.kickoff is not None
                    and international_calendar.stops_club_football(fixture.kickoff.date())):
                raise ValueError(
                    f"generated fixture {fixture.fixture_id} violates international club break"
                )

    by_id = {fixture.fixture_id: fixture for fixture in calendar.fixtures}
    for cup in cups.values():
        _check_round_sequence(cup.cup_id, [plan.fixtures for plan in cup.plans], by_id)
        _check_tie_legs(cup.cup_id, cup.plans, by_id)
    for competition in staged.values():
        rounds = [competition.primary_fixtures]
        rounds.extend(plan.fixtures for plan in competition.knockout_plans)
        _check_round_sequence(competition.competition_id, rounds, by_id)
        _check_tie_legs(competition.competition_id, competition.knockout_plans, by_id)
