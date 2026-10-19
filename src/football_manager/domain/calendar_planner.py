"""TS-21.1.1: generated-club scheduling policy, independent of team strength.

72 hours is a game scheduling preference, NOT a claim about federation rules.
The existing 48-hour hard invariant is retained for protected dates/congestion.
Only generated, unplayed league fixtures can be repaired. Sporting identities,
results, knockout chronology and imported official fixtures are never rewritten.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import replace
from datetime import date, datetime, time, timedelta, timezone
from typing import Iterable

from .calendar import ScheduleSource, ScheduledFixture, ScheduledFixtureStatus

TARGET_REST_HOURS = 72
HARD_REST_HOURS = 48
_ACTIVE = (ScheduledFixtureStatus.SCHEDULED, ScheduledFixtureStatus.PLAYED)


class FixtureIndex:
    """Call/transaction-local index: queries visit only the two clubs involved.

    No persistent cache, no references to previous seasons. The world journal
    updates this index with each fixture replacement and discards it on commit
    or rollback. Read-only standalone audits build their own independent index.
    """

    def __init__(self, fixtures: Iterable[ScheduledFixture]):
        self.by_club: dict[str, dict[str, ScheduledFixture]] = defaultdict(dict)
        for fixture in fixtures:
            self.put(None, fixture)

    def put(self, old: ScheduledFixture | None, new: ScheduledFixture) -> None:
        if old is not None:
            for club_id in (old.home_club_id, old.away_club_id):
                self.by_club[club_id].pop(old.fixture_id, None)
        if new.kickoff is not None and new.status in _ACTIVE:
            for club_id in (new.home_club_id, new.away_club_id):
                self.by_club[club_id][new.fixture_id] = new

    def conflicts(self, kickoff: datetime, home: str, away: str, *, hours: float = TARGET_REST_HOURS,
                  ignore: frozenset[str] = frozenset()) -> list[ScheduledFixture]:
        relevant = dict(self.by_club.get(home, {}))
        relevant.update(self.by_club.get(away, {}))
        seconds = hours * 3600
        return [f for fid, f in relevant.items() if fid not in ignore and (
            f.kickoff.date() == kickoff.date()
            or abs((f.kickoff - kickoff).total_seconds()) < seconds)]


def _season_bounds(world) -> tuple[date, date]:
    year = int(world.season_label[:4])
    return date(year, 8, 1), date(year + 1, 6, 12)


def _kickoffs(day: date) -> tuple[datetime, ...]:
    # Existing game timestamps are UTC. An evening option avoids treating
    # Saturday 15:00 as 72h after Wednesday 19:45 (it is only 67h15).
    times = (time(16, 30), time(19, 45)) if day.weekday() == 6 else (
        (time(15), time(19, 45)) if day.weekday() == 5 else (time(19, 45),))
    return tuple(datetime.combine(day, clock, tzinfo=timezone.utc) for clock in times)


def _preference(candidate: datetime, anchor: datetime, *, prefer_sunday: bool = False) -> tuple:
    """Prefer a nearby weekend, not an arbitrary free Friday weeks later."""
    delta = abs((candidate.date() - anchor.date()).days)
    # Same football weekend first. Do not defer a month just to get Sunday.
    nearby_weekend = candidate.weekday() in (5, 6) and delta <= 4
    return (0 if nearby_weekend else 1,
            (0 if candidate.weekday() == 6 else 1) if nearby_weekend and prefer_sunday else 0, delta,
            0 if candidate.weekday() in (5, 6) else 1,
            0 if candidate >= anchor else 1, candidate)


def find_league_replacement(world, item: ScheduledFixture, anchor: datetime, *, planned=()) -> datetime:
    """Reserve all displaced games; try 72h for both clubs before 48h fallback."""
    if item.source is ScheduleSource.OFFICIAL or item.status is ScheduledFixtureStatus.PLAYED:
        raise ValueError(f'cannot displace protected league fixture {item.fixture_id}')
    start, end = _season_bounds(world)
    start = max(start, anchor.date() + timedelta(days=2))
    ignored = frozenset([item.fixture_id, *(f.fixture_id for f, _ in planned)])
    clubs = {item.home_club_id, item.away_club_id}
    candidates = [kickoff for n in range(max(0, (end - start).days + 1))
                  for day in (start + timedelta(days=n),)
                  if not world._is_club_break(day) for kickoff in _kickoffs(day)]
    candidates.sort(key=lambda dt: _preference(dt, anchor, prefer_sunday=anchor.weekday() in (2, 3)))
    index = world._fixture_index()
    for hours in (TARGET_REST_HOURS, HARD_REST_HOURS):
        for candidate in candidates:
            if (candidate - anchor).total_seconds() < hours * 3600:
                continue
            # Keep the historical conflict seam: callers/tests can substitute
            # constraints, while the indexed 72-hour query adds the preference.
            conflicts = world._matching_conflicts(candidate, item.home_club_id, item.away_club_id)
            if any(f.fixture_id not in ignored for f in conflicts):
                continue
            if hours > HARD_REST_HOURS and index.conflicts(candidate, item.home_club_id,
                    item.away_club_id, hours=hours, ignore=ignored):
                continue
            if any(clubs & {f.home_club_id, f.away_club_id} and (
                    dt.date() == candidate.date()
                    or abs((dt - candidate).total_seconds()) < hours * 3600) for f, dt in planned):
                continue
            return candidate
    raise ValueError(f'unable to reprogram league fixture {item.fixture_id}')


def repair_generated_calendar(world, *, after_date: date | None = None,
                              clubs: frozenset[str] | None = None) -> dict:
    """Improve pending league dates without cascading arbitrary postponements.

    Fixed cup/European windows take precedence. Search locally (+/-7 days,
    then up to 21 days later); only accept a move with >=72h on BOTH sides for
    BOTH clubs. Every move strictly removes at least one short-rest pair, so
    re-running the repair is idempotent, not a repeated fixture shuffle.
    after_date protects today's open match and every previous calendar day.
    """
    start, end = _season_bounds(world)
    if after_date is not None:
        start = max(start, after_date + timedelta(days=1))
    moves = []
    with world.transaction():
        index = world._fixture_index()
        eligible = sorted((f for f in world.fixtures.values()
            if f.competition_id in world.leagues and f.source is ScheduleSource.GENERATED
            and f.status is ScheduledFixtureStatus.SCHEDULED and f.match_date is not None
            and start <= f.match_date <= end
            and (clubs is None or clubs & {f.home_club_id, f.away_club_id})),
            key=lambda f: (f.kickoff, f.fixture_id))
        # Moving one fixture can free a date for another already-congested one.
        # A move adds no new short-rest pair; thus at most 2*N useful passes.
        for _ in range(len(eligible) * 2 + 1):
            changed = False
            for initial in eligible:
                item = world.fixtures[initial.fixture_id]
                ignore = frozenset((item.fixture_id,))
                clashes = index.conflicts(item.kickoff, item.home_club_id, item.away_club_id, ignore=ignore)
                if not clashes:
                    continue
                prefer_sunday = any(f.competition_id not in world.leagues
                    and f.kickoff.weekday() in (2, 3) and f.kickoff < item.kickoff
                    and (item.match_date - f.match_date).days <= 4 for f in clashes)
                candidate = None
                for offsets in (range(-7, 8), range(8, 22)):
                    dates = [dt for offset in offsets
                             for day in (item.match_date + timedelta(days=offset),)
                             if start <= day <= end and not world._is_club_break(day)
                             for dt in _kickoffs(day)]
                    for dt in sorted(dates, key=lambda t: _preference(t, item.kickoff, prefer_sunday=prefer_sunday)):
                        if not index.conflicts(dt, item.home_club_id, item.away_club_id, ignore=ignore):
                            candidate = dt
                            break
                    if candidate is not None:
                        break
                if candidate is None:
                    continue  # Explicit congested/protected exception; never force a broken date.
                updated = replace(item, kickoff=candidate, original_kickoff=item.original_kickoff or item.kickoff)
                world._put(world.fixtures, item.fixture_id, updated)
                moves.append({'fixture_id': item.fixture_id, 'from': item.kickoff.isoformat(),
                              'to': candidate.isoformat(), 'reason': 'cross_competition_rest'})
                changed = True
            if not changed:
                break
        else:
            raise RuntimeError('calendar repair did not converge')
    return {'moved': moves, 'target_rest_hours': TARGET_REST_HOURS,
            'hard_rest_hours': HARD_REST_HOURS}


def calendar_rest_audit(world, *, after_date: date | None = None) -> dict:
    """Read-only exception report; includes both clubs, not only the manager."""
    index = FixtureIndex(world.fixtures.values())
    short = []
    for club_id, by_id in sorted(index.by_club.items()):
        fixtures = sorted(by_id.values(), key=lambda f: (f.kickoff, f.fixture_id))
        for left, right in zip(fixtures, fixtures[1:]):
            if after_date is not None and right.match_date <= after_date:
                continue
            gap = (right.kickoff - left.kickoff).total_seconds() / 3600
            if gap < TARGET_REST_HOURS:
                short.append({'club_id': club_id, 'first': left.fixture_id, 'second': right.fixture_id,
                              'gap_hours': round(gap, 2), 'hard_violation': gap < HARD_REST_HOURS})
    return {'target_rest_hours': TARGET_REST_HOURS, 'short_rest_pairs': short,
            'hard_violations': sum(p['hard_violation'] for p in short),
            'international_violations': list(world.international_window_violations())}
