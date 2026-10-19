"""TC-E1 international *planning* calendar; no national-team match simulation.

FIFA 2026-2030 dates and selected tournament dates are source-backed anchors.
Subsequent dates are explicitly GENERATED game-calendar projections, not fixtures
or official future announcements. World scheduling uses only CLUB_BREAK events;
RELEASE_ONLY events instead reserve time for explicit future player call-ups.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date, timedelta
from enum import StrEnum
from typing import Any, Mapping, Sequence

from .calendar import CalendarBlock


class InternationalImpact(StrEnum):
    CLUB_BREAK = "club_break"
    RELEASE_ONLY = "release_only"


class InternationalDateSource(StrEnum):
    OFFICIAL = "official"
    PROJECTED = "projected"
    OVERRIDE = "override"


@dataclass(frozen=True, slots=True)
class InternationalEvent:
    event_id: str
    name: str
    start_date: date
    end_date: date
    impact: InternationalImpact
    source: InternationalDateSource
    confederation: str | None = None
    release_start: date | None = None
    release_end: date | None = None

    def __post_init__(self) -> None:
        if not self.event_id.strip() or not self.name.strip():
            raise ValueError("international event requires ID and name")
        if self.end_date < self.start_date:
            raise ValueError("international event end cannot precede start")
        if self.release_start is not None and self.release_start > self.start_date:
            raise ValueError("release cannot begin after event start")
        if self.release_end is not None and self.release_end < self.end_date:
            raise ValueError("release cannot end before event end")

    @property
    def duty_start(self) -> date:
        return self.release_start or self.start_date

    @property
    def duty_end(self) -> date:
        return self.release_end or self.end_date

    def is_club_break(self, day: date) -> bool:
        return self.impact is InternationalImpact.CLUB_BREAK and self.start_date <= day <= self.end_date

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id, "name": self.name,
            "start_date": self.start_date.isoformat(), "end_date": self.end_date.isoformat(),
            "impact": self.impact.value, "source": self.source.value,
            "confederation": self.confederation,
            "release_start": self.release_start.isoformat() if self.release_start else None,
            "release_end": self.release_end.isoformat() if self.release_end else None,
        }

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "InternationalEvent":
        return cls(
            event_id=str(raw["event_id"]), name=str(raw["name"]),
            start_date=date.fromisoformat(str(raw["start_date"])),
            end_date=date.fromisoformat(str(raw["end_date"])),
            impact=InternationalImpact(str(raw["impact"])),
            source=InternationalDateSource(str(raw["source"])),
            confederation=None if raw.get("confederation") is None else str(raw["confederation"]),
            release_start=(date.fromisoformat(str(raw["release_start"]))
                           if raw.get("release_start") else None),
            release_end=(date.fromisoformat(str(raw["release_end"]))
                         if raw.get("release_end") else None),
        )


@dataclass(frozen=True, slots=True)
class InternationalCalendar:
    events: tuple[InternationalEvent, ...]

    def __post_init__(self) -> None:
        ids = [e.event_id for e in self.events]
        if len(set(ids)) != len(ids):
            raise ValueError("duplicate international event ID")
        if self.events != tuple(sorted(self.events, key=lambda e: (e.start_date, e.event_id))):
            raise ValueError("international events must be sorted chronologically")

    def event(self, event_id: str) -> InternationalEvent:
        for event in self.events:
            if event.event_id == event_id:
                return event
        raise KeyError(f"unknown international event: {event_id}")

    def events_on(self, day: date) -> tuple[InternationalEvent, ...]:
        return tuple(e for e in self.events if e.start_date <= day <= e.end_date)

    def release_events_on(self, day: date) -> tuple[InternationalEvent, ...]:
        return tuple(e for e in self.events if e.duty_start <= day <= e.duty_end)

    def stops_club_football(self, day: date) -> bool:
        return any(e.is_club_break(day) for e in self.events)

    def league_blackouts(self, start: date, end: date) -> tuple[CalendarBlock, ...]:
        """Return ONLY full FIFA windows intersecting the given scheduling season."""
        if end < start:
            raise ValueError("invalid date range")
        return tuple(
            CalendarBlock(max(start, e.start_date), min(end, e.end_date), e.name)
            for e in self.events
            if e.impact is InternationalImpact.CLUB_BREAK
            and e.start_date <= end and e.end_date >= start
        )

    def to_dict(self) -> dict[str, Any]:
        return {"events": [event.to_dict() for event in self.events]}

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "InternationalCalendar":
        return cls(tuple(InternationalEvent.from_dict(e) for e in data["events"]))


@dataclass(frozen=True, slots=True)
class InternationalCallUp:
    """An explicit real/simulated national-team selection, NOT auto-generated.

    ``last_unavailable_day`` may precede the event end when a national team
    is eliminated. Club availability is based on these dates, not on ethnicity
    or guessed nationality. No call-ups exist until another system supplies them.
    """
    player_id: str
    national_team_id: str
    event_id: str
    first_unavailable_day: date
    last_unavailable_day: date

    def __post_init__(self) -> None:
        if not all((self.player_id.strip(), self.national_team_id.strip(), self.event_id.strip())):
            raise ValueError("call-up requires player, national team and event IDs")
        if self.last_unavailable_day < self.first_unavailable_day:
            raise ValueError("call-up last day cannot precede first day")


@dataclass(frozen=True, slots=True)
class InternationalDutyRegistry:
    calendar: InternationalCalendar
    callups: tuple[InternationalCallUp, ...] = ()

    def __post_init__(self) -> None:
        by_player: dict[str, list[InternationalCallUp]] = {}
        for duty in self.callups:
            event = self.calendar.event(duty.event_id)
            if not (event.duty_start <= duty.first_unavailable_day <= duty.last_unavailable_day <= event.duty_end):
                raise ValueError("call-up dates must fit event release period")
            for previous in by_player.setdefault(duty.player_id, []):
                if (previous.first_unavailable_day <= duty.last_unavailable_day
                        and duty.first_unavailable_day <= previous.last_unavailable_day):
                    raise ValueError("player cannot have overlapping international call-ups")
            by_player[duty.player_id].append(duty)

    def unavailable(self, player_id: str, day: date) -> bool:
        return any(
            duty.player_id == player_id
            and duty.first_unavailable_day <= day <= duty.last_unavailable_day
            for duty in self.callups
        )

    def active(self, day: date) -> tuple[InternationalCallUp, ...]:
        return tuple(d for d in self.callups if d.first_unavailable_day <= day <= d.last_unavailable_day)


# Exact men's FIFA match windows published for 2026-2030. These are *date
# reservations*, not national-team fixtures. Beyond 2030 the same calendar
# weeks are projected and may be overridden without changing the scheduler.
# Source: https://inside.fifa.com/tournament-organisation/international-match-calendars
_FIFA_OFFICIAL: dict[int, dict[str, tuple[tuple[int, int], tuple[int, int]]]] = {
    2026: {"march": ((3, 23), (3, 31)), "june": ((6, 1), (6, 9)),
           "sep-oct": ((9, 21), (10, 6)), "november": ((11, 9), (11, 17))},
    2027: {"march": ((3, 22), (3, 30)), "june": ((6, 7), (6, 15)),
           "sep-oct": ((9, 20), (10, 5)), "november": ((11, 8), (11, 16))},
    2028: {"march": ((3, 20), (3, 28)), "june": ((5, 29), (6, 6)),
           "sep-oct": ((9, 18), (10, 3)), "november": ((11, 13), (11, 21))},
    2029: {"march": ((3, 19), (3, 27)), "june": ((6, 4), (6, 12)),
           "sep-oct": ((9, 24), (10, 9)), "november": ((11, 12), (11, 20))},
    2030: {"march": ((3, 18), (3, 26)), "june": ((6, 3), (6, 11)),
           "sep-oct": ((9, 23), (10, 8)), "november": ((11, 11), (11, 19))},
}


def _week_monday(year: int, month: int, day: int) -> date:
    anchor = date(year, month, day)
    return anchor - timedelta(days=anchor.weekday())


def _projected_window(year: int, label: str) -> tuple[date, date]:
    # Stable reference calendar weeks after the official 2026-2030 horizon.
    anchor = {"march": (3, 23), "june": (6, 4),
              "sep-oct": (9, 24), "november": (11, 12)}[label]
    start = _week_monday(year, *anchor)
    return start, start + timedelta(days=15 if label == "sep-oct" else 8)


def _projected_tournament(year: int, month: int, day: int, duration_days: int,
                          *, reference_year: int) -> tuple[date, date]:
    """Keep the same week of the year as the reference edition."""
    start = _week_monday(year, month, day) + timedelta(days=date(reference_year, month, day).weekday())
    # Tournament fixtures can occupy any days within these reserved weeks.
    return start, start + timedelta(days=duration_days - 1)


def build_international_calendar(
    first_year: int, last_year: int,
    *, overrides: Mapping[str, tuple[date, date]] | None = None,
) -> InternationalCalendar:
    """Generate FIFA breaks and tournament release windows inclusively by YEAR.

    2026-2030 FIFA match-window dates, 2026 World Cup, 2027 Asian Cup / AFCON
    and 2028 EURO have announced dates. Copa America 2028, AFCON 2028+,
    2030+ World Cups and all 2031+ FIFA windows are projected game templates.
    No tournament freezes an entire club league merely by taking place.
    """
    if not 2026 <= first_year <= last_year <= 2100:
        raise ValueError("international calendar years must be 2026..2100")
    events: list[InternationalEvent] = []
    fifa_names = {"march": "FIFA March window", "june": "FIFA June window",
                  "sep-oct": "FIFA September-October window", "november": "FIFA November window"}
    for year in range(first_year, last_year + 1):
        for label, name in fifa_names.items():
            dates = _FIFA_OFFICIAL.get(year)
            if dates is not None:
                (sm, sd), (em, ed) = dates[label]
                start, end = date(year, sm, sd), date(year, em, ed)
                source = InternationalDateSource.OFFICIAL
            else:
                start, end = _projected_window(year, label)
                source = InternationalDateSource.PROJECTED
            events.append(InternationalEvent(
                f"fifa-{label}-{year}", name, start, end,
                InternationalImpact.CLUB_BREAK, source,
            ))
        if (year - 2026) % 4 == 0:
            if year == 2026:
                start, end = date(2026, 6, 11), date(2026, 7, 19)
                release = date(2026, 5, 25)
                source = InternationalDateSource.OFFICIAL
            else:
                start, end = _projected_tournament(year, 6, 11, 39, reference_year=2026)
                release = start - timedelta(days=17)
                source = InternationalDateSource.PROJECTED
            events.append(InternationalEvent(
                f"world-cup-{year}", "FIFA World Cup", start, end,
                InternationalImpact.RELEASE_ONLY, source,
                release_start=release,
            ))
        if (year - 2028) % 4 == 0 and year >= 2028:
            if year == 2028:
                start, end = date(2028, 6, 9), date(2028, 7, 9)
                euro_source = InternationalDateSource.OFFICIAL
            else:
                start, end = _projected_tournament(year, 6, 9, 31, reference_year=2028)
                euro_source = InternationalDateSource.PROJECTED
            events.append(InternationalEvent(
                f"euro-{year}", "UEFA European Championship", start, end,
                InternationalImpact.RELEASE_ONLY, euro_source, confederation="UEFA",
            ))
            copa_start, copa_end = _projected_tournament(year, 6, 20, 25, reference_year=2024)
            events.append(InternationalEvent(
                f"copa-america-{year}", "CONMEBOL Copa America", copa_start, copa_end,
                InternationalImpact.RELEASE_ONLY, InternationalDateSource.PROJECTED,
                confederation="CONMEBOL",
            ))
        if (year - 2027) % 4 == 0 and year >= 2027:
            start, end = ((date(2027, 1, 7), date(2027, 2, 5)) if year == 2027
                          else _projected_tournament(year, 1, 7, 30, reference_year=2027))
            events.append(InternationalEvent(
                f"asian-cup-{year}", "AFC Asian Cup", start, end,
                InternationalImpact.RELEASE_ONLY,
                InternationalDateSource.OFFICIAL if year == 2027 else InternationalDateSource.PROJECTED,
                confederation="AFC",
            ))
        if year == 2027 or (year >= 2028 and (year - 2028) % 4 == 0):
            start, end = ((date(2027, 6, 19), date(2027, 7, 17)) if year == 2027
                          else _projected_tournament(year, 6, 19, 29, reference_year=2027))
            events.append(InternationalEvent(
                f"afcon-{year}", "CAF Africa Cup of Nations", start, end,
                InternationalImpact.RELEASE_ONLY,
                InternationalDateSource.OFFICIAL if year == 2027 else InternationalDateSource.PROJECTED,
                confederation="CAF",
            ))

    requested = dict(overrides or {})
    valid = {event.event_id for event in events}
    if set(requested) - valid:
        raise ValueError(f"unknown override event IDs: {sorted(set(requested) - valid)}")
    if requested:
        updated = []
        for event in events:
            if event.event_id in requested:
                new_start, new_end = requested[event.event_id]
                if new_end < new_start:
                    raise ValueError("override end cannot precede start")
                # For overriden event dates, update any pre-tournament release
                # lead by the same delta, preserving its duration and meaning.
                release_start = (event.release_start + (new_start - event.start_date)
                                 if event.release_start else None)
                release_end = (event.release_end + (new_end - event.end_date)
                               if event.release_end else None)
                event = replace(event, start_date=new_start, end_date=new_end,
                                release_start=release_start, release_end=release_end,
                                source=InternationalDateSource.OVERRIDE)
            updated.append(event)
        events = updated
    return InternationalCalendar(tuple(sorted(events, key=lambda e: (e.start_date, e.event_id))))
