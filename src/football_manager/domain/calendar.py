from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date, datetime, time, timedelta, timezone
from enum import StrEnum
from typing import Any, Iterable, Mapping, Sequence

from .competition import CompetitionFixture


class ScheduleSource(StrEnum):
    OFFICIAL = "official"
    GENERATED = "generated"


class ScheduledFixtureStatus(StrEnum):
    SCHEDULED = "scheduled"
    PLAYED = "played"
    POSTPONED = "postponed"
    CANCELLED = "cancelled"


class CalendarConflictKind(StrEnum):
    SAME_CLUB_OVERLAP = "same_club_overlap"
    INSUFFICIENT_REST = "insufficient_rest"


@dataclass(frozen=True, slots=True)
class ScheduledFixture:
    """Calendar assignment for one sporting fixture.

    ``CompetitionFixture`` remains the sporting truth (participants/stage/round).
    This object only adds chronology and scheduling provenance so a fixture can be
    moved without changing the competition structure.
    """

    fixture_id: str
    competition_id: str
    edition_id: str
    stage_id: str
    home_club_id: str
    away_club_id: str
    kickoff: datetime | None
    source: ScheduleSource
    status: ScheduledFixtureStatus = ScheduledFixtureStatus.SCHEDULED
    round_number: int | None = None
    leg_number: int = 1
    original_kickoff: datetime | None = None

    def __post_init__(self) -> None:
        for label, value in (
            ("fixture_id", self.fixture_id),
            ("competition_id", self.competition_id),
            ("edition_id", self.edition_id),
            ("stage_id", self.stage_id),
            ("home_club_id", self.home_club_id),
            ("away_club_id", self.away_club_id),
        ):
            if not str(value).strip():
                raise ValueError(f"{label} cannot be empty")
        if self.home_club_id == self.away_club_id:
            raise ValueError("scheduled fixture clubs must be different")
        if not isinstance(self.source, ScheduleSource):
            object.__setattr__(self, "source", ScheduleSource(self.source))
        if not isinstance(self.status, ScheduledFixtureStatus):
            object.__setattr__(self, "status", ScheduledFixtureStatus(self.status))
        if self.round_number is not None and self.round_number < 1:
            raise ValueError("round_number must be at least 1")
        if self.leg_number < 1:
            raise ValueError("leg_number must be at least 1")
        _validate_datetime(self.kickoff, "kickoff")
        _validate_datetime(self.original_kickoff, "original_kickoff")
        if self.status in {
            ScheduledFixtureStatus.SCHEDULED,
            ScheduledFixtureStatus.PLAYED,
        } and self.kickoff is None:
            raise ValueError(f"{self.status.value} fixture requires kickoff")
        if (
            self.original_kickoff is not None
            and self.kickoff is None
            and self.status not in {
                ScheduledFixtureStatus.POSTPONED,
                ScheduledFixtureStatus.CANCELLED,
            }
        ):
            raise ValueError("active or played fixture requires a current kickoff")

    @property
    def is_rescheduled(self) -> bool:
        return (
            self.kickoff is not None
            and self.original_kickoff is not None
            and self.original_kickoff != self.kickoff
        )

    @property
    def match_date(self) -> date | None:
        return None if self.kickoff is None else self.kickoff.date()

    def to_dict(self) -> dict[str, Any]:
        return {
            "fixture_id": self.fixture_id,
            "competition_id": self.competition_id,
            "edition_id": self.edition_id,
            "stage_id": self.stage_id,
            "home_club_id": self.home_club_id,
            "away_club_id": self.away_club_id,
            "kickoff": _datetime_to_text(self.kickoff),
            "source": self.source.value,
            "status": self.status.value,
            "round_number": self.round_number,
            "leg_number": self.leg_number,
            "original_kickoff": _datetime_to_text(self.original_kickoff),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "ScheduledFixture":
        round_number = data.get("round_number")
        return cls(
            fixture_id=str(data["fixture_id"]),
            competition_id=str(data["competition_id"]),
            edition_id=str(data["edition_id"]),
            stage_id=str(data["stage_id"]),
            home_club_id=str(data["home_club_id"]),
            away_club_id=str(data["away_club_id"]),
            kickoff=_datetime_from_text(data.get("kickoff")),
            source=ScheduleSource(str(data["source"])),
            status=ScheduledFixtureStatus(
                str(data.get("status", ScheduledFixtureStatus.SCHEDULED.value))
            ),
            round_number=None if round_number is None else int(round_number),
            leg_number=int(data.get("leg_number", 1)),
            original_kickoff=_datetime_from_text(data.get("original_kickoff")),
        )


@dataclass(frozen=True, slots=True)
class CalendarConflict:
    kind: CalendarConflictKind
    club_id: str
    first_fixture_id: str
    second_fixture_id: str
    gap_hours: float


@dataclass(frozen=True, slots=True)
class CalendarBlock:
    """Date range on which generated competition matches may not be assigned."""

    start_date: date
    end_date: date
    label: str = "Blocked"

    def __post_init__(self) -> None:
        if self.end_date < self.start_date:
            raise ValueError("calendar block end_date cannot precede start_date")
        if not self.label.strip():
            raise ValueError("calendar block label cannot be empty")

    def contains(self, candidate: date) -> bool:
        return self.start_date <= candidate <= self.end_date


@dataclass(frozen=True, slots=True)
class SchedulingWindow:
    """Allowed date window for a competition round or rescheduled match."""

    window_id: str
    start_date: date
    end_date: date
    allowed_weekdays: tuple[int, ...] = tuple(range(7))
    label: str = "Scheduling window"

    def __post_init__(self) -> None:
        if not self.window_id.strip():
            raise ValueError("window_id cannot be empty")
        if not self.label.strip():
            raise ValueError("scheduling window label cannot be empty")
        if self.end_date < self.start_date:
            raise ValueError("scheduling window end_date cannot precede start_date")
        if not self.allowed_weekdays:
            raise ValueError("scheduling window requires at least one allowed weekday")
        if any(day not in range(7) for day in self.allowed_weekdays):
            raise ValueError("allowed weekdays must be in range 0..6")
        if len(set(self.allowed_weekdays)) != len(self.allowed_weekdays):
            raise ValueError("allowed weekdays must be unique")

    def allows(self, candidate: date) -> bool:
        return (
            self.start_date <= candidate <= self.end_date
            and candidate.weekday() in self.allowed_weekdays
        )


@dataclass(frozen=True, slots=True)
class LeagueSchedulingPolicy:
    """Season rules used to generate future league dates.

    The policy is deliberately season data.  It does not clone the previous
    season or add 365 days to existing fixtures.  A future edition supplies a
    new start/end window, preferred match day, optional midweek days and
    blackout periods, then the scheduler allocates sporting rounds across
    that window. The midweek days make congested, international-break-aware
    seasons possible without importing old season dates.
    """

    season_start: date
    season_end: date
    preferred_weekday: int = 5  # Saturday
    kickoff_local_time: time = time(15, 0)
    minimum_round_gap_days: int = 3
    blackout_periods: tuple[CalendarBlock, ...] = ()
    midweek_weekdays: tuple[int, ...] = (1, 2)  # Tuesday / Wednesday

    def __post_init__(self) -> None:
        if self.season_end <= self.season_start:
            raise ValueError("season_end must be after season_start")
        if self.preferred_weekday not in range(7):
            raise ValueError("preferred_weekday must be in range 0..6")
        if self.minimum_round_gap_days < 1:
            raise ValueError("minimum_round_gap_days must be positive")
        if len(set(self.midweek_weekdays)) != len(self.midweek_weekdays):
            raise ValueError("midweek weekdays must be unique")
        if any(day not in range(7) for day in self.midweek_weekdays):
            raise ValueError("midweek weekdays must be in range 0..6")
        if self.preferred_weekday in self.midweek_weekdays:
            raise ValueError("preferred weekday cannot also be a midweek weekday")


@dataclass(frozen=True, slots=True)
class SeasonCalendar:
    season_label: str
    timezone_name: str
    fixtures: tuple[ScheduledFixture, ...] = ()

    def __post_init__(self) -> None:
        if not self.season_label.strip():
            raise ValueError("season_label cannot be empty")
        if not self.timezone_name.strip():
            raise ValueError("timezone_name cannot be empty")
        fixture_ids = [fixture.fixture_id for fixture in self.fixtures]
        if len(fixture_ids) != len(set(fixture_ids)):
            raise ValueError("season calendar cannot contain duplicate fixture IDs")

    def fixture(self, fixture_id: str) -> ScheduledFixture:
        for fixture in self.fixtures:
            if fixture.fixture_id == fixture_id:
                return fixture
        raise KeyError(f"unknown scheduled fixture: {fixture_id}")

    def fixtures_for_club(self, club_id: str) -> tuple[ScheduledFixture, ...]:
        relevant = (
            fixture
            for fixture in self.fixtures
            if club_id in (fixture.home_club_id, fixture.away_club_id)
        )
        return tuple(sorted(relevant, key=_scheduled_sort_key))

    def fixtures_for_competition(self, competition_id: str) -> tuple[ScheduledFixture, ...]:
        return tuple(
            sorted(
                (fixture for fixture in self.fixtures if fixture.competition_id == competition_id),
                key=_scheduled_sort_key,
            )
        )

    def fixtures_on(self, match_date: date) -> tuple[ScheduledFixture, ...]:
        return tuple(
            fixture
            for fixture in sorted(self.fixtures, key=_scheduled_sort_key)
            if fixture.match_date == match_date
        )

    def next_fixture(
        self,
        club_id: str,
        *,
        after: datetime,
    ) -> ScheduledFixture | None:
        _validate_datetime(after, "after")
        candidates = (
            fixture
            for fixture in self.fixtures_for_club(club_id)
            if fixture.kickoff is not None
            and fixture.kickoff > after
            and fixture.status is ScheduledFixtureStatus.SCHEDULED
        )
        return next(iter(candidates), None)

    def mark_played(self, fixture_id: str) -> "SeasonCalendar":
        if self.fixture(fixture_id).status is not ScheduledFixtureStatus.SCHEDULED:
            raise ValueError("only a scheduled fixture can be marked played")
        return self._replace_fixture(
            fixture_id,
            lambda fixture: replace(fixture, status=ScheduledFixtureStatus.PLAYED),
        )

    def postpone(self, fixture_id: str) -> "SeasonCalendar":
        if self.fixture(fixture_id).status is not ScheduledFixtureStatus.SCHEDULED:
            raise ValueError("only a scheduled fixture can be postponed")
        return self._replace_fixture(
            fixture_id,
            lambda fixture: replace(
                fixture,
                kickoff=None,
                original_kickoff=fixture.original_kickoff or fixture.kickoff,
                status=ScheduledFixtureStatus.POSTPONED,
            ),
        )

    def cancel(self, fixture_id: str) -> "SeasonCalendar":
        if self.fixture(fixture_id).status not in {
            ScheduledFixtureStatus.SCHEDULED,
            ScheduledFixtureStatus.POSTPONED,
        }:
            raise ValueError("only a scheduled or postponed fixture can be cancelled")
        return self._replace_fixture(
            fixture_id,
            lambda fixture: replace(fixture, status=ScheduledFixtureStatus.CANCELLED),
        )

    def reschedule(self, fixture_id: str, new_kickoff: datetime) -> "SeasonCalendar":
        _validate_datetime(new_kickoff, "new_kickoff")
        if self.fixture(fixture_id).status not in {
            ScheduledFixtureStatus.SCHEDULED,
            ScheduledFixtureStatus.POSTPONED,
        }:
            raise ValueError("only a scheduled or postponed fixture can be rescheduled")

        def update(fixture: ScheduledFixture) -> ScheduledFixture:
            original = fixture.original_kickoff or fixture.kickoff
            if original is None:
                raise ValueError("cannot reschedule fixture without an original kickoff")
            return replace(
                fixture,
                kickoff=new_kickoff,
                original_kickoff=original,
                status=ScheduledFixtureStatus.SCHEDULED,
            )

        return self._replace_fixture(fixture_id, update)

    def detect_conflicts(self, *, minimum_rest_hours: float = 0.0) -> tuple[CalendarConflict, ...]:
        if minimum_rest_hours < 0:
            raise ValueError("minimum_rest_hours cannot be negative")
        by_club: dict[str, list[ScheduledFixture]] = {}
        for fixture in self.fixtures:
            if fixture.kickoff is None or fixture.status in {
                ScheduledFixtureStatus.POSTPONED,
                ScheduledFixtureStatus.CANCELLED,
            }:
                continue
            by_club.setdefault(fixture.home_club_id, []).append(fixture)
            by_club.setdefault(fixture.away_club_id, []).append(fixture)

        conflicts: list[CalendarConflict] = []
        for club_id, club_fixtures in by_club.items():
            ordered = sorted(club_fixtures, key=_scheduled_sort_key)
            for first, second in zip(ordered, ordered[1:]):
                assert first.kickoff is not None and second.kickoff is not None
                gap_hours = (second.kickoff - first.kickoff).total_seconds() / 3600.0
                # A club cannot play two different fixtures on one local match
                # date, even if kickoffs are separated by a few hours.
                if first.match_date == second.match_date:
                    conflicts.append(
                        CalendarConflict(
                            CalendarConflictKind.SAME_CLUB_OVERLAP,
                            club_id,
                            first.fixture_id,
                            second.fixture_id,
                            gap_hours,
                        )
                    )
                elif gap_hours < minimum_rest_hours:
                    conflicts.append(
                        CalendarConflict(
                            CalendarConflictKind.INSUFFICIENT_REST,
                            club_id,
                            first.fixture_id,
                            second.fixture_id,
                            gap_hours,
                        )
                    )
        return tuple(conflicts)

    def to_dict(self) -> dict[str, Any]:
        return {
            "season_label": self.season_label,
            "timezone_name": self.timezone_name,
            "fixtures": [fixture.to_dict() for fixture in self.fixtures],
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "SeasonCalendar":
        raw = data.get("fixtures", ())
        if not isinstance(raw, Iterable):
            raise TypeError("fixtures must be iterable")
        return cls(
            season_label=str(data["season_label"]),
            timezone_name=str(data["timezone_name"]),
            fixtures=tuple(ScheduledFixture.from_dict(item) for item in raw),
        )

    def _replace_fixture(self, fixture_id: str, updater) -> "SeasonCalendar":
        changed = False
        fixtures: list[ScheduledFixture] = []
        for fixture in self.fixtures:
            if fixture.fixture_id == fixture_id:
                fixtures.append(updater(fixture))
                changed = True
            else:
                fixtures.append(fixture)
        if not changed:
            raise KeyError(f"unknown scheduled fixture: {fixture_id}")
        return replace(self, fixtures=tuple(fixtures))


def schedule_fixtures_on_round_dates(
    fixtures: Sequence[CompetitionFixture],
    round_dates: Mapping[int, datetime],
    *,
    competition_id: str,
    source: ScheduleSource = ScheduleSource.GENERATED,
) -> tuple[ScheduledFixture, ...]:
    scheduled: list[ScheduledFixture] = []
    for fixture in fixtures:
        if fixture.round_number is None:
            raise ValueError("round-date scheduling requires fixture round_number")
        if fixture.round_number not in round_dates:
            raise ValueError(f"missing calendar date for round {fixture.round_number}")
        kickoff = round_dates[fixture.round_number]
        _validate_datetime(kickoff, "round kickoff")
        scheduled.append(
            ScheduledFixture(
                fixture_id=fixture.fixture_id,
                competition_id=competition_id,
                edition_id=fixture.edition_id,
                stage_id=fixture.stage_id,
                home_club_id=fixture.home_club_id,
                away_club_id=fixture.away_club_id,
                kickoff=kickoff,
                source=source,
                round_number=fixture.round_number,
                leg_number=fixture.leg_number,
            )
        )
    return tuple(scheduled)


def generate_league_round_dates(
    round_count: int,
    policy: LeagueSchedulingPolicy,
    *,
    tzinfo=timezone.utc,
) -> dict[int, datetime]:
    """Allocate league dates across this season's window, including midweeks.

    Choose round dates by minimizing deviation from an even season-long
    distribution, with a preference for the main match weekday. The dynamic
    program respects blackout periods and minimum between-round rest, and
    uses midweek fixtures only when they improve the resulting calendar.
    Neither the previous edition nor any previous kickoff is consulted.
    """

    if round_count < 1:
        raise ValueError("round_count must be positive")
    allowed_days = {policy.preferred_weekday, *policy.midweek_weekdays}
    dates: list[date] = []
    current = policy.season_start
    while current <= policy.season_end:
        if current.weekday() in allowed_days and not any(
            block.contains(current) for block in policy.blackout_periods
        ):
            dates.append(current)
        current += timedelta(days=1)

    if not dates:
        raise ValueError("season window cannot fit all competition rounds")

    # previous_compatible[i] is the last candidate with enough between-round
    # rest before candidate i. The DP then needs O(round_count * candidate_days).
    previous_compatible: list[int] = []
    previous = -1
    for i, candidate in enumerate(dates):
        while (
            previous + 1 < i
            and (candidate - dates[previous + 1]).days >= policy.minimum_round_gap_days
        ):
            previous += 1
        previous_compatible.append(previous)

    impossible = float("inf")
    count = len(dates)
    best: list[list[float]] = [[0.0] * count] + [
        [impossible] * count for _ in range(round_count)
    ]
    chosen: list[list[bool]] = [[False] * count for _ in range(round_count + 1)]
    first_day = dates[0]
    last_day = dates[-1]
    span = (last_day - first_day).days
    for round_number in range(1, round_count + 1):
        target_day = (
            0.0 if round_count == 1 else span * (round_number - 1) / (round_count - 1)
        )
        for i, candidate in enumerate(dates):
            skipped = best[round_number][i - 1] if i else impossible
            prior_index = previous_compatible[i]
            prior_cost = (
                0.0 if round_number == 1 else
                best[round_number - 1][prior_index] if prior_index >= 0 else impossible
            )
            delta_days = (candidate - first_day).days - target_day
            midweek_penalty = 25.0 if candidate.weekday() != policy.preferred_weekday else 0.0
            used = prior_cost + delta_days * delta_days + midweek_penalty
            if used < skipped:
                best[round_number][i] = used
                chosen[round_number][i] = True
            else:
                best[round_number][i] = skipped

    if best[round_count][-1] == impossible:
        raise ValueError("season window cannot fit all competition rounds")

    chosen_dates: list[date] = []
    index = count - 1
    for round_number in range(round_count, 0, -1):
        while not chosen[round_number][index]:
            index -= 1
        chosen_dates.append(dates[index])
        index = previous_compatible[index]
    chosen_dates.reverse()
    return {
        number: datetime.combine(day, policy.kickoff_local_time, tzinfo=tzinfo)
        for number, day in enumerate(chosen_dates, start=1)
    }



def reprogram_round_dates_for_blackouts(
    original: Mapping[int, datetime], policy: LeagueSchedulingPolicy,
) -> dict[int, datetime]:
    """Second scheduling pass: move already generated rounds out of club breaks.

    The initial fixture generator decides all pairings and natural matchweeks
    without knowing FIFA dates. This pass preserves their identity/order and
    original date wherever possible. It reallocates the *whole round* (not
    individual matches) so all clubs keep 48+ hours between league matchweeks.
    A changed fixture must retain its original_kickoff when materialized.

    There is no stadium/calendar-of-national-teams model yet. Cross-competition
    collisions are handled later when the world registers cup/staged matches.
    """
    if not original:
        return {}
    numbers = sorted(original)
    if numbers != list(range(1, len(numbers) + 1)):
        raise ValueError("league matchweeks must be numbered consecutively from 1")
    ordered = [original[number] for number in numbers]
    if any(kickoff.tzinfo is None or kickoff.utcoffset() is None for kickoff in ordered):
        raise ValueError("round kickoff must be timezone-aware")
    if any(ordered[i] >= ordered[i + 1] for i in range(len(ordered) - 1)):
        raise ValueError("round kickoff dates must be strictly chronological")
    if not policy.blackout_periods or all(
        not any(block.contains(kickoff.date()) for block in policy.blackout_periods)
        for kickoff in ordered
    ):
        return dict(original)

    allowed = {policy.preferred_weekday, *policy.midweek_weekdays}
    candidates: list[date] = []
    day = policy.season_start
    while day <= policy.season_end:
        if day.weekday() in allowed and not any(
            block.contains(day) for block in policy.blackout_periods
        ):
            candidates.append(day)
        day += timedelta(days=1)
    if not candidates:
        raise ValueError("season window cannot fit all competition rounds")

    previous_compatible: list[int] = []
    previous = -1
    for index, candidate in enumerate(candidates):
        while previous + 1 < index and (
            candidate - candidates[previous + 1]
        ).days >= policy.minimum_round_gap_days:
            previous += 1
        previous_compatible.append(previous)

    count = len(candidates)
    impossible = float("inf")
    costs = [[0.] * count] + [[impossible] * count for _ in numbers]
    selected = [[False] * count for _ in range(len(numbers) + 1)]
    for r, original_kickoff in enumerate(ordered, start=1):
        for i, candidate in enumerate(candidates):
            skip_cost = costs[r][i - 1] if i else impossible
            previous_idx = previous_compatible[i]
            take_prior = (0. if r == 1 else
                          costs[r - 1][previous_idx] if previous_idx >= 0 else impossible)
            deviation = abs((candidate - original_kickoff.date()).days)
            # Strongly prefer the published/generated natural dates, but use
            # realistic midweek replacements when a FIFA pause forces moves.
            change_cost = (0. if deviation == 0 else 45. + deviation ** 2)
            midweek_cost = 8. if candidate.weekday() != policy.preferred_weekday else 0.
            take_cost = take_prior + change_cost + midweek_cost
            if take_cost < skip_cost:
                costs[r][i] = take_cost
                selected[r][i] = True
            else:
                costs[r][i] = skip_cost
    if costs[len(numbers)][-1] == impossible:
        raise ValueError("season window cannot fit all competition rounds around international breaks")

    chosen: list[date] = []
    idx = count - 1
    for r in range(len(numbers), 0, -1):
        while idx >= 0 and not selected[r][idx]:
            idx -= 1
        if idx < 0:
            raise AssertionError("blackout schedule could not be reconstructed")
        chosen.append(candidates[idx])
        idx = previous_compatible[idx]
    chosen.reverse()
    return {
        number: datetime.combine(day, ordered[number - 1].timetz())
        for number, day in enumerate(chosen, start=1)
    }



def reprogram_pending_fixtures_for_blackouts(
    calendar: SeasonCalendar,
    *,
    blackout_periods: Sequence[CalendarBlock],
    earliest_date: date,
    latest_date: date,
    minimum_rest_hours: float = 48.0,
) -> SeasonCalendar:
    """Move only unplayed fixtures inside FIFA breaks, keeping their opponents.

    Unlike the round-level planner, this handles EFL's published *per-match*
    kickoff slots (including independently postponed games). The initial
    season is drawn on its normal slots first, then this pass schedules only
    the affected fixtures. Played matches are immutable. It is transactional:
    an impossible window leaves the caller's calendar unchanged.
    """
    if minimum_rest_hours < 0:
        raise ValueError("minimum_rest_hours cannot be negative")
    if latest_date < earliest_date:
        raise ValueError("invalid fixture reflow date range")
    blocks = tuple(blackout_periods)
    def blocked(day: date) -> bool:
        return any(block.contains(day) for block in blocks)

    impacted = sorted(
        (item for item in calendar.fixtures
         if item.status is ScheduledFixtureStatus.SCHEDULED
         and item.kickoff is not None
         and item.kickoff.date() > earliest_date
         and blocked(item.kickoff.date())),
        key=_scheduled_sort_key,
    )
    if not impacted:
        return calendar

    movable = {item.fixture_id for item in impacted}
    occupancy: dict[str, list[datetime]] = {}
    for item in calendar.fixtures:
        if (item.fixture_id in movable or item.kickoff is None
                or item.status in (ScheduledFixtureStatus.POSTPONED, ScheduledFixtureStatus.CANCELLED)):
            continue
        occupancy.setdefault(item.home_club_id, []).append(item.kickoff)
        occupancy.setdefault(item.away_club_id, []).append(item.kickoff)

    chosen: dict[str, ScheduledFixture] = {}
    for item in impacted:
        assert item.kickoff is not None
        original = item.kickoff
        # Postpone, never bring an EFL game forward in front of an earlier
        # matchweek or an already completed match.
        cursor = original.date() + timedelta(days=1)
        while cursor <= latest_date:
            if not blocked(cursor):
                candidate = datetime.combine(cursor, original.timetz())
                if all(
                    existing.date() != cursor
                    and abs((existing - candidate).total_seconds()) >= minimum_rest_hours * 3600
                    for club in (item.home_club_id, item.away_club_id)
                    for existing in occupancy.get(club, ())
                ):
                    chosen[item.fixture_id] = replace(
                        item, kickoff=candidate,
                        original_kickoff=item.original_kickoff or original,
                    )
                    occupancy.setdefault(item.home_club_id, []).append(candidate)
                    occupancy.setdefault(item.away_club_id, []).append(candidate)
                    break
            cursor += timedelta(days=1)
        else:
            raise ValueError(f"no safe date for FIFA-affected fixture {item.fixture_id}")

    return SeasonCalendar(
        calendar.season_label, calendar.timezone_name,
        tuple(chosen.get(f.fixture_id, f) for f in calendar.fixtures),
    )

def find_available_kickoff(
    calendar: SeasonCalendar,
    *,
    club_ids: Sequence[str],
    window: SchedulingWindow,
    kickoff_local_time: time,
    tzinfo=timezone.utc,
    minimum_rest_hours: float = 48.0,
    blackout_periods: Sequence[CalendarBlock] = (),
) -> datetime:
    """Find the first slot in ``window`` compatible with the clubs' schedule."""

    if len(club_ids) < 2 or len(set(club_ids)) != len(club_ids):
        raise ValueError("club_ids must contain at least two unique clubs")
    if minimum_rest_hours < 0:
        raise ValueError("minimum_rest_hours cannot be negative")

    existing = [
        fixture
        for fixture in calendar.fixtures
        if fixture.kickoff is not None
        and fixture.status not in {
            ScheduledFixtureStatus.POSTPONED,
            ScheduledFixtureStatus.CANCELLED,
        }
        and any(club_id in (fixture.home_club_id, fixture.away_club_id) for club_id in club_ids)
    ]
    candidate_date = window.start_date
    while candidate_date <= window.end_date:
        if window.allows(candidate_date) and not any(
            block.contains(candidate_date) for block in blackout_periods
        ):
            candidate = datetime.combine(candidate_date, kickoff_local_time, tzinfo=tzinfo)
            valid = True
            for fixture in existing:
                assert fixture.kickoff is not None
                gap_hours = abs((candidate - fixture.kickoff).total_seconds()) / 3600.0
                if (
                    candidate.date() == fixture.kickoff.date()
                    or gap_hours < minimum_rest_hours
                ):
                    valid = False
                    break
            if valid:
                return candidate
        candidate_date += timedelta(days=1)
    raise ValueError(f"no available kickoff inside scheduling window {window.window_id}")


def reschedule_fixture_into_window(
    calendar: SeasonCalendar,
    fixture_id: str,
    *,
    window: SchedulingWindow,
    kickoff_local_time: time,
    tzinfo=timezone.utc,
    minimum_rest_hours: float = 48.0,
    blackout_periods: Sequence[CalendarBlock] = (),
) -> SeasonCalendar:
    fixture = calendar.fixture(fixture_id)
    comparison_calendar = SeasonCalendar(
        season_label=calendar.season_label,
        timezone_name=calendar.timezone_name,
        fixtures=tuple(item for item in calendar.fixtures if item.fixture_id != fixture_id),
    )
    kickoff = find_available_kickoff(
        comparison_calendar,
        club_ids=(fixture.home_club_id, fixture.away_club_id),
        window=window,
        kickoff_local_time=kickoff_local_time,
        tzinfo=tzinfo,
        minimum_rest_hours=minimum_rest_hours,
        blackout_periods=blackout_periods,
    )
    return calendar.reschedule(fixture_id, kickoff)


def merge_calendars(*calendars: SeasonCalendar) -> SeasonCalendar:
    if not calendars:
        raise ValueError("at least one season calendar is required")
    season_labels = {calendar.season_label for calendar in calendars}
    timezone_names = {calendar.timezone_name for calendar in calendars}
    if len(season_labels) != 1:
        raise ValueError("cannot merge calendars from different seasons")
    if len(timezone_names) != 1:
        raise ValueError("cannot merge calendars with different timezone names")
    fixtures: list[ScheduledFixture] = []
    for calendar in calendars:
        fixtures.extend(calendar.fixtures)
    return SeasonCalendar(
        season_label=calendars[0].season_label,
        timezone_name=calendars[0].timezone_name,
        fixtures=tuple(fixtures),
    )


def _scheduled_sort_key(fixture: ScheduledFixture) -> tuple[datetime, str]:
    far_future = datetime.max.replace(tzinfo=timezone.utc)
    kickoff = fixture.kickoff
    if kickoff is None:
        normalized = far_future
    else:
        normalized = kickoff.astimezone(timezone.utc)
    return normalized, fixture.fixture_id


def _validate_datetime(value: datetime | None, label: str) -> None:
    if value is None:
        return
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{label} must be timezone-aware")


def _datetime_to_text(value: datetime | None) -> str | None:
    return None if value is None else value.isoformat()


def _datetime_from_text(value: object) -> datetime | None:
    if value is None:
        return None
    return datetime.fromisoformat(str(value))
