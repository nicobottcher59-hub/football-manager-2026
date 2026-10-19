"""Persistent, deterministic competition runner for leagues and knockout cups.

This is the world-level result ledger. Managed-club results can be supplied by
FastMatchSimulator; unobserved fixtures use a cheap strength-sensitive DEV
resolver. Never simulate a protected club automatically.
"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, replace
from functools import wraps
from heapq import heappop, heappush, heapify
from datetime import date, datetime, time, timedelta, timezone
import json
import os
from pathlib import Path
from random import Random
import tempfile
from typing import Any, Iterator, Mapping

from .calendar import ScheduleSource, ScheduledFixture, ScheduledFixtureStatus, SeasonCalendar
from .score_validation import require_nonnegative_integer_score
from .competition import CompetitionEdition
from .domestic_cups import DomesticCupSeason
from .knockout import KnockoutMatchResult, resolve_knockout_round, resolve_knockout_tie
from .league import LeagueResult, build_league_table
from .staged_world import StagedWorldCompetition
from .international_calendar import InternationalCalendar
from .calendar_invariants import validate_calendar_invariants


@dataclass(frozen=True, slots=True)
class WorldMatchResult:
    fixture_id: str
    home_goals: int
    away_goals: int
    penalties_home: int = 0
    penalties_away: int = 0
    resolver: str = "background"

    def __post_init__(self) -> None:
        if not self.fixture_id:
            raise ValueError("fixture_id cannot be empty")
        for field in ("home_goals", "away_goals", "penalties_home", "penalties_away"):
            require_nonnegative_integer_score(getattr(self, field), field)
        if self.resolver not in ("background", "managed", "imported", "administrative"):
            raise ValueError("unknown result resolver")
        if self.penalties_home or self.penalties_away:
            if self.penalties_home == self.penalties_away:
                raise ValueError("a shootout cannot end level")

    def knockout_result(self) -> KnockoutMatchResult:
        return KnockoutMatchResult(
            self.fixture_id, self.home_goals, self.away_goals,
            self.penalties_home, self.penalties_away,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "fixture_id": self.fixture_id, "home_goals": self.home_goals,
            "away_goals": self.away_goals, "penalties_home": self.penalties_home,
            "penalties_away": self.penalties_away, "resolver": self.resolver,
        }

    @classmethod
    def from_dict(cls, item: Mapping[str, Any]) -> "WorldMatchResult":
        return cls(
            str(item["fixture_id"]), item["home_goals"],
            item["away_goals"], item.get("penalties_home", 0),
            item.get("penalties_away", 0), str(item.get("resolver", "imported")),
        )


@dataclass(frozen=True, slots=True)
class WorldRunProgress:
    matches_played: int
    stopped_for_managed_fixture_id: str | None = None


_MISSING = object()


class _WorldChangeJournal:
    """Undo only touched dictionary entries and mutable tournament progress.

    Copying every fixture for every result would make multi-league simulation
    quadratic. Journal entries are kept only until the current operation ends.
    """

    def __init__(self) -> None:
        self.entries: list[tuple[dict, str, object]] = []
        self.fixture_index = None
        self.undo_callbacks: dict[object, Any] = {}
        self.cup_states: dict[int, tuple[DomesticCupSeason, tuple, str | None]] = {}
        self.staged_states: dict[int, tuple[StagedWorldCompetition, tuple, tuple[str, ...], str | None]] = {}

    def set(self, mapping: dict, key: str, value: object) -> None:
        self.entries.append((mapping, key, mapping.get(key, _MISSING)))
        mapping[key] = value

    def remember_cup(self, cup: DomesticCupSeason) -> None:
        self.cup_states.setdefault(id(cup), (cup, tuple(cup.plans), cup.champion_club_id))

    def remember_staged(self, competition: StagedWorldCompetition) -> None:
        self.staged_states.setdefault(id(competition), (
            competition, tuple(competition.knockout_plans),
            competition.direct_qualifiers, competition.champion_club_id,
        ))

    def rollback(self) -> None:
        for undo in reversed(tuple(self.undo_callbacks.values())):
            undo()
        for mapping, key, previous in reversed(self.entries):
            if previous is _MISSING:
                mapping.pop(key, None)
            else:
                mapping[key] = previous
        for cup, plans, champion in self.cup_states.values():
            cup.plans[:] = plans  # Keep references held by the UI or calling code.
            cup.champion_club_id = champion
        for competition, plans, qualifiers, champion in self.staged_states.values():
            competition.knockout_plans[:] = plans
            competition.direct_qualifiers = qualifiers
            competition.champion_club_id = champion


def _atomic_world_operation(method):
    """Commit a world mutation in full, or restore its entry state on failure."""
    @wraps(method)
    def wrapped(self, *args, **kwargs):
        with self._atomic():
            return method(self, *args, **kwargs)
    return wrapped


class WorldSeasonRunner:
    """Canonical background world results with a round-aware cup graph.

    A save contains calendar, fixture status, scores, league edition definitions,
    and exact cup draw history. It does not yet persist player states or lineups.
    """

    SCHEMA_VERSION = 3

    def __init__(self, *, season_label: str = "2026/27", seed: int = 6600,
                 international_calendar: InternationalCalendar | None = None) -> None:
        self.season_label = season_label
        self.seed = seed
        # Opt-in for generated worlds. Preserve published/legacy DEV schedules.
        self.international_calendar = international_calendar
        # Complete manager saves preserve this shared registry. Results-only JSON
        # intentionally retains its historical, competition-only contract.
        self.football_world = None
        self.strengths: dict[str, int] = {}
        self.fixtures: dict[str, ScheduledFixture] = {}
        self.results: dict[str, WorldMatchResult] = {}
        self.leagues: dict[str, CompetitionEdition] = {}
        self.cups: dict[str, DomesticCupSeason] = {}
        self._cup_fixture_ids: dict[str, str] = {}
        self.staged: dict[str, StagedWorldCompetition] = {}
        self._staged_fixture_ids: dict[str, str] = {}
        self.promotion_playoff_leagues: dict[str, str] = {}
        self._active_journal: _WorldChangeJournal | None = None
        # Transient due-fixture heap, active only inside advance_until().
        # It is not persisted and never changes the sporting ordering policy.
        self._advance_queue: list[tuple[datetime, str, int, ScheduledFixture]] | None = None
        self._advance_cutoff: date | None = None
        self._advance_sequence = 0

    @contextmanager
    def _atomic(self) -> Iterator[None]:
        # Playoff creation can register a cup inside record_result. A nested
        # command shares its parent's journal so failure unwinds both actions.
        if self._active_journal is not None:
            yield
            return
        journal = _WorldChangeJournal()
        self._active_journal = journal
        try:
            yield
        except BaseException:
            journal.rollback()
            raise
        finally:
            self._active_journal = None

    @contextmanager
    def transaction(self) -> Iterator[None]:
        """Compose several world mutations into one application-level unit of work.

        Callers may perform additional work before committing. Nested world
        commands share an undo journal and roll back on any exception.
        The runner remains single-threaded; this is not a distributed lock.
        """
        with self._atomic():
            yield

    def _put(self, mapping: dict, key: str, value: object) -> None:
        if (mapping is self.fixtures and self._active_journal is not None
                and self._active_journal.fixture_index is not None):
            self._active_journal.fixture_index.put(mapping.get(key), value)
        if self._active_journal is None:
            mapping[key] = value
        else:
            self._active_journal.set(mapping, key, value)
        # A simulated cup match may schedule a new knockout round or move a
        # league match. Queue those revisions without scanning the world again.
        # Stale heap entries are skipped by object identity when popped.
        if (mapping is self.fixtures and self._advance_queue is not None
                and isinstance(value, ScheduledFixture)
                and value.status is ScheduledFixtureStatus.SCHEDULED
                and value.kickoff is not None and self._advance_cutoff is not None
                and value.kickoff.date() <= self._advance_cutoff):
            self._advance_sequence += 1
            heappush(self._advance_queue, (
                value.kickoff, key, self._advance_sequence, value,
            ))

    def _remember_cup(self, cup: DomesticCupSeason) -> None:
        if self._active_journal is not None:
            self._active_journal.remember_cup(cup)

    def _remember_staged(self, competition: StagedWorldCompetition) -> None:
        if self._active_journal is not None:
            self._active_journal.remember_staged(competition)

    @property
    def calendar(self) -> SeasonCalendar:
        return SeasonCalendar(self.season_label, "UTC", tuple(self.fixtures.values()))

    def _is_club_break(self, day: date) -> bool:
        return (self.international_calendar is not None
                and self.international_calendar.stops_club_football(day))

    def international_window_violations(self) -> tuple[str, ...]:
        """Fixture IDs inside a mandatory club pause (including imported fixtures)."""
        return tuple(sorted(
            f.fixture_id for f in self.fixtures.values()
            if (f.status in (ScheduledFixtureStatus.SCHEDULED, ScheduledFixtureStatus.PLAYED)
                and f.kickoff is not None and self._is_club_break(f.kickoff.date()))
        ))

    @_atomic_world_operation
    def configure_promotion_playoffs(self, league_ids: tuple[str, ...]) -> None:
        """Generate EFL playoff fixtures only after final league standings exist.

        This opt-in keeps the low-level Runner usable for isolated league tests.
        """
        from .season_cycle import PLAYOFF_IDS
        for league_id in league_ids:
            if league_id not in PLAYOFF_IDS or league_id not in self.leagues:
                raise ValueError(f"unknown EFL playoff league {league_id}")
            self._put(self.promotion_playoff_leagues, league_id, PLAYOFF_IDS[league_id])

    @_atomic_world_operation
    def register_league(
        self, edition: CompetitionEdition, calendar: SeasonCalendar,
        strengths: Mapping[str, int],
    ) -> None:
        competition_id = edition.competition.competition_id
        if competition_id in self.leagues or competition_id in self.cups or competition_id in self.staged:
            raise ValueError("competition already registered")
        fixture_ids = {fixture.fixture_id for fixture in edition.fixtures}
        if {item.fixture_id for item in calendar.fixtures} != fixture_ids:
            raise ValueError("league calendar must cover every sporting fixture once")
        if not set(edition.participant_club_ids).issubset(strengths):
            raise ValueError("missing league strength inputs")
        for item in calendar.fixtures:
            sporting = next(f for f in edition.fixtures if f.fixture_id == item.fixture_id)
            if (item.home_club_id, item.away_club_id, item.competition_id) != (
                sporting.home_club_id, sporting.away_club_id, competition_id
            ):
                raise ValueError("league sporting fixture/calendar mismatch")
            if item.fixture_id in self.fixtures:
                raise ValueError("duplicate world fixture ID")
            if (item.source is ScheduleSource.GENERATED and item.kickoff is not None
                    and self._is_club_break(item.kickoff.date())):
                raise ValueError("generated league fixture violates international club break")
        self._put(self.leagues, competition_id, edition)
        for club_id, strength in strengths.items():
            self._put(self.strengths, club_id, strength)
        for fixture in calendar.fixtures:
            self._put(self.fixtures, fixture.fixture_id, fixture)

    @_atomic_world_operation
    def register_cup(self, cup: DomesticCupSeason, *, strengths: Mapping[str, int]) -> None:
        if cup.cup_id in self.cups or cup.cup_id in self.leagues or cup.cup_id in self.staged:
            raise ValueError("competition already registered")
        entrants = {club for rule in cup.rounds for club in rule.entrants}
        if not entrants.issubset(set(strengths) | set(self.strengths)):
            raise ValueError("missing cup entrant strengths")
        self._remember_cup(cup)
        for club_id, strength in strengths.items():
            self._put(self.strengths, club_id, strength)
        self._put(self.cups, cup.cup_id, cup)
        self._schedule_cup_plan(cup, cup.start())

    @_atomic_world_operation
    def register_staged(
        self, competition: StagedWorldCompetition, *, strengths: Mapping[str, int],
    ) -> None:
        """Attach UEFA/EFL Trophy phase + later generated knockout to one world ledger."""
        cid = competition.competition_id
        if cid in self.leagues or cid in self.cups or cid in self.staged:
            raise ValueError("competition already registered")
        if not set(competition.participants).issubset(set(strengths) | set(self.strengths)):
            raise ValueError("missing staged-competition participant strengths")
        self._put(self.staged, cid, competition)
        for club_id, strength in strengths.items():
            self._put(self.strengths, club_id, strength)
        for fixture, day in zip(competition.primary_fixtures, competition.primary_dates):
            self._schedule_staged_fixture(competition, fixture, day)

    @staticmethod
    def _staged_allowed_weekdays(competition: StagedWorldCompetition, fixture) -> tuple[int, ...]:
        """Allowed days for generated matches, derived from competition and stage.

        Fixture dates are projections for fictional draws; do not treat a free
        Monday or Saturday as a valid UEFA league-phase replacement.
        """
        cid = competition.competition_id
        if cid == "champions-league":
            return (5,) if fixture.stage_id == "final" else (1, 2)
        if cid == "europa-league":
            if fixture.stage_id == "final":
                return (2,)
            return (2, 3) if fixture.stage_id == competition.primary_stage_id and fixture.round_number == 1 else (3,)
        if cid == "conference-league":
            return (2,) if fixture.stage_id == "final" else (3,)
        if cid == "efl-trophy":
            return (6,) if fixture.stage_id == "final" else (1, 2)
        return tuple(range(7))

    @staticmethod
    def _next_round_earliest(previous: list[ScheduledFixture]) -> datetime | None:
        """Never schedule a successor before its preceding matches have finished.

        This is a lower bound, not a fixed rescheduling date. It preserves the
        existing >=48-hour recovery policy without falsely guaranteeing that
        additional travel/competition requirements have been modeled.
        """
        kickoffs = [f.kickoff for f in previous if f.kickoff is not None]
        return max(kickoffs) + timedelta(hours=48) if kickoffs else None

    def _schedule_staged_fixture(
        self, competition: StagedWorldCompetition, fixture, window: date,
        *, not_before: datetime | None = None,
    ) -> None:
        if fixture.fixture_id in self.fixtures:
            raise ValueError("duplicate staged fixture ID")
        # Round window comes from an official tournament schedule; exact fictional
        # kickoff may shift to prevent a collision with the club's domestic matches.
        selected = None
        had_candidates = False
        allowed_weekdays = self._staged_allowed_weekdays(competition, fixture)
        # Prefer the original cup/UEFA scheduling proximity. Only expand the
        # search when a FIFA break rules out the ordinary nearby slots.
        for offsets in (
            (0, 1, -1, 2, -2, 3, 4, 5, 6, 7, 8),
            (*range(9, 29), *range(-3, -10, -1)),
        ):
            ranked = []
            for offset in offsets:
                day = window + timedelta(days=offset)
                if (day < date(int(self.season_label[:4]), 8, 1)
                        or day > date(int(self.season_label[:4]) + 1, 6, 15)
                        or day.weekday() not in allowed_weekdays
                        or self._is_club_break(day)):
                    continue
                kickoff = datetime.combine(day, time(19, 45), tzinfo=timezone.utc)
                if not_before is not None and kickoff < not_before:
                    continue
                conflicts = self._matching_conflicts(kickoff, fixture.home_club_id, fixture.away_club_id)
                if any(x.competition_id not in self.leagues
                       or x.source is ScheduleSource.OFFICIAL
                       or x.status is ScheduledFixtureStatus.PLAYED for x in conflicts):
                    continue
                ranked.append((len(conflicts), abs(offset), kickoff, conflicts))
            had_candidates |= bool(ranked)
            for _count, _distance, proposed, clashes in sorted(ranked, key=lambda r: (r[0], r[1], r[2])):
                plan = self._plan_league_displacements(clashes, proposed)
                if plan is not None:
                    selected = (proposed, plan)
                    break
            if selected is not None:
                break
        if selected is None:
            if not had_candidates:
                raise ValueError(f"no free staged fixture window for {fixture.fixture_id}")
            raise ValueError(f"no feasible staged/league calendar for {fixture.fixture_id}")
        kickoff, moves = selected
        self._put(self.fixtures, fixture.fixture_id, ScheduledFixture(
            fixture.fixture_id, competition.competition_id, competition.edition_id,
            fixture.stage_id, fixture.home_club_id, fixture.away_club_id,
            kickoff, ScheduleSource.GENERATED,
            round_number=fixture.round_number, leg_number=fixture.leg_number,
            original_kickoff=(
                datetime.combine(window, time(19, 45), tzinfo=timezone.utc)
                if kickoff.date() != window else None
            ),
        ))
        self._put(self._staged_fixture_ids, fixture.fixture_id, competition.competition_id)
        for clash, moved in moves:
            self._put(self.fixtures, clash.fixture_id, replace(
                clash, kickoff=moved,
                original_kickoff=clash.original_kickoff or clash.kickoff,
            ))

    def _schedule_staged_plan(self, competition: StagedWorldCompetition, plan) -> None:
        window = competition.knockout_windows[plan.definition.round_id]
        if len(competition.knockout_plans) == 1:
            preceding = [self.fixtures[f.fixture_id] for f in competition.primary_fixtures]
        else:
            preceding = [self.fixtures[f.fixture_id]
                         for f in competition.knockout_plans[-2].fixtures]
        not_before = self._next_round_earliest(preceding)
        for tie in plan.ties:
            previous_leg: datetime | None = None
            for fixture in sorted(tie.fixtures, key=lambda item: item.leg_number):
                scheduled_day = window[fixture.leg_number - 1]
                leg_bound = (previous_leg + timedelta(hours=48)
                             if previous_leg is not None else None)
                earliest = max(filter(None, (not_before, leg_bound)), default=None)
                self._schedule_staged_fixture(
                    competition, fixture, scheduled_day, not_before=earliest,
                )
                previous_leg = self.fixtures[fixture.fixture_id].kickoff

    def _schedule_cup_plan(self, cup: DomesticCupSeason, plan) -> None:
        rule = cup.rounds[len(cup.plans) - 1]
        not_before = (self._next_round_earliest([
            self.fixtures[f.fixture_id] for f in cup.plans[-2].fixtures
        ]) if len(cup.plans) > 1 else None)
        for tie_index, tie in enumerate(plan.ties):
            previous_leg: datetime | None = None
            for fixture in sorted(tie.fixtures, key=lambda item: item.leg_number):
                if fixture.fixture_id in self.fixtures:
                    raise ValueError("duplicate cup fixture ID")
                if rule.leg_format.leg_count == 2:
                    candidates = (rule.dates[fixture.leg_number - 1],)
                else:
                    candidates = (rule.dates[tie_index % len(rule.dates)], *rule.dates)
                leg_bound = (previous_leg + timedelta(hours=48)
                             if previous_leg is not None else None)
                earliest = max(filter(None, (not_before, leg_bound)), default=None)
                self._insert_cup_match(
                    fixture_id=fixture.fixture_id, cup=cup, rule_id=rule.round_id,
                    home=fixture.home_club_id, away=fixture.away_club_id,
                    leg_number=fixture.leg_number, round_number=plan.definition.order,
                    candidates=candidates, not_before=earliest,
                )
                previous_leg = self.fixtures[fixture.fixture_id].kickoff
                self._put(self._cup_fixture_ids, fixture.fixture_id, cup.cup_id)

    def _fixture_index(self):
        from .calendar_planner import FixtureIndex
        journal = self._active_journal
        if journal is None:
            return FixtureIndex(self.fixtures.values())
        if journal.fixture_index is None:
            journal.fixture_index = FixtureIndex(self.fixtures.values())
        return journal.fixture_index

    def _matching_conflicts(self, kickoff: datetime, home: str, away: str) -> list[ScheduledFixture]:
        return self._fixture_index().conflicts(kickoff, home, away, hours=48)

    def _find_league_replacement(
        self, item: ScheduledFixture, anchor: datetime,
        *, planned: tuple[tuple[ScheduledFixture, datetime], ...] = (),
    ) -> datetime:
        from .calendar_planner import find_league_replacement
        return find_league_replacement(self, item, anchor, planned=planned)

    def _repair_after_new_round(self, plan) -> None:
        from .calendar_planner import repair_generated_calendar
        clubs = frozenset(cid for f in plan.fixtures for cid in (f.home_club_id, f.away_club_id))
        last_played = max((f.match_date for f in self.fixtures.values()
                           if f.status is ScheduledFixtureStatus.PLAYED and f.match_date is not None), default=None)
        repair_generated_calendar(self, after_date=last_played, clubs=clubs)

    def _plan_league_displacements(
        self, conflicts: list[ScheduledFixture], kickoff: datetime,
    ) -> tuple[tuple[ScheduledFixture, datetime], ...] | None:
        """Check that ALL conflicting league fixtures can move before committing.

        Plan against earlier reservations, then change the world only after
        the whole plan succeeds. Avoids picking a plausible cup slot that is
        impossible to accommodate once the affected league is congested.
        """
        planned: list[tuple[ScheduledFixture, datetime]] = []
        for item in sorted(conflicts, key=lambda fixture: fixture.fixture_id):
            try:
                moved = (self._find_league_replacement(item, kickoff, planned=tuple(planned))
                         if planned else self._find_league_replacement(item, kickoff))
            except ValueError:
                return None
            planned.append((item, moved))
        return tuple(planned)

    def _insert_cup_match(
        self, *, fixture_id: str, cup: DomesticCupSeason, rule_id: str,
        home: str, away: str, leg_number: int, round_number: int,
        candidates: tuple[date, ...],
        not_before: datetime | None = None,
    ) -> None:
        unique_dates = list(dict.fromkeys(candidates))
        # A published FA Cup Saturday may be played Sunday (TV selection).
        # A Cup tie has priority over fictional league slots on the chosen day.
        expanded = [*unique_dates]
        if cup.cup_id == "fa-cup" and rule_id != "final":
            expanded.extend(day + timedelta(days=1) for day in unique_dates)
        # If both UEFA and English cup dates collide for a fictional club, we
        # must use a neighbouring DEV kickoff rather than skipping either cup.
        # Published windows remain recorded as provenance, not claimed as exact
        # fixture kickoffs for these GENERATED pairings.
        expanded.extend(day + timedelta(days=offset) for day in unique_dates
                        for offset in (2, -1, 3, 4, -2, 5, 6, 7, 8, 9, 10))
        kickoff_hour = 15 if cup.cup_id == "fa-cup" else 19
        kickoff_minute = 0 if cup.cup_id == "fa-cup" else 45
        selected = None
        had_candidates = False
        for candidates_to_try in (
            dict.fromkeys(expanded),
            dict.fromkeys(day + timedelta(days=offset) for day in unique_dates
                          for offset in range(11, 29)),
        ):
            ranked: list[tuple[int, int, datetime, list[ScheduledFixture]]] = []
            for day in candidates_to_try:
                if (day < date(int(self.season_label[:4]), 8, 1)
                        or day > date(int(self.season_label[:4]) + 1, 6, 15)
                        or self._is_club_break(day)):
                    continue
                kickoff = datetime.combine(day, time(kickoff_hour, kickoff_minute), tzinfo=timezone.utc)
                if not_before is not None and kickoff < not_before:
                    continue
                conflicts = self._matching_conflicts(kickoff, home, away)
                if any(item.competition_id not in self.leagues
                       or item.source is ScheduleSource.OFFICIAL
                       or item.status is ScheduledFixtureStatus.PLAYED for item in conflicts):
                    continue
                # A free *published* date must not lose to a free earlier
                # fallback simply because the fallback is chronologically first.
                displacement = abs((day - unique_dates[0]).days)
                ranked.append((len(conflicts), displacement, kickoff, conflicts))
            had_candidates |= bool(ranked)
            # The first search window may have apparent dates whose league
            # displacement is impossible. Only stop if we found a feasible
            # candidate; otherwise search the expanded window too.
            for _count, _distance, proposed, clashes in sorted(ranked, key=lambda row: (row[0], row[1], row[2])):
                plan = self._plan_league_displacements(clashes, proposed)
                if plan is not None:
                    selected = (proposed, plan)
                    break
            if selected is not None:
                break
        if selected is None:
            if not had_candidates:
                raise ValueError(f"no available cup window for {fixture_id}")
            raise ValueError(f"no feasible cup/league calendar for {fixture_id}")
        kickoff, moves = selected
        # Cup fixture is inserted first, so a rescheduled league match cannot
        # accidentally pick the same date again.
        self._put(self.fixtures, fixture_id, ScheduledFixture(
            fixture_id, cup.cup_id, cup.edition_id, rule_id,
            home, away, kickoff, ScheduleSource.GENERATED,
            round_number=round_number, leg_number=leg_number,
            original_kickoff=(
                datetime.combine(unique_dates[0], time(kickoff_hour, kickoff_minute), tzinfo=timezone.utc)
                if kickoff.date() != unique_dates[0] else None
            ),
        ))
        for item, moved in moves:
            self._put(self.fixtures, item.fixture_id, replace(
                item, kickoff=moved,
                original_kickoff=item.original_kickoff or item.kickoff,
            ))

    @_atomic_world_operation
    def reschedule_league_fixture(self, fixture_id: str, window) -> ScheduledFixture:
        """Safely reschedule one league fixture with all global FIFA club breaks."""
        from .calendar import reschedule_fixture_into_window
        item = self.fixtures[fixture_id]
        if item.competition_id not in self.leagues:
            raise ValueError("only league fixtures can be directly rescheduled")
        blocks = (self.international_calendar.league_blackouts(
            window.start_date, window.end_date) if self.international_calendar else ())
        revised = reschedule_fixture_into_window(
            self.calendar, fixture_id, window=window, kickoff_local_time=time(19, 45),
            blackout_periods=blocks,
        )
        updated = revised.fixture(fixture_id)
        self._put(self.fixtures, fixture_id, updated)
        return updated

    def result_for(self, fixture_id: str) -> WorldMatchResult | None:
        return self.results.get(fixture_id)

    def league_results(self, competition_id: str) -> tuple[LeagueResult, ...]:
        edition = self.leagues[competition_id]
        ids = {fixture.fixture_id for fixture in edition.fixtures}
        return tuple(
            LeagueResult(record.fixture_id, record.home_goals, record.away_goals)
            for record in self.results.values() if record.fixture_id in ids
        )

    def standings(self, competition_id: str, group_id: str | None = None):
        if competition_id in self.staged:
            return self.staged[competition_id].standings(self.results, group_id)
        if group_id is not None:
            raise ValueError("regular league does not contain groups")
        edition = self.leagues[competition_id]
        return build_league_table(
            participant_club_ids=edition.participant_club_ids,
            fixtures=edition.fixtures,
            results=self.league_results(competition_id),
        )

    def _validate_result_semantics(self, record: WorldMatchResult,
                                   results: Mapping[str, WorldMatchResult]) -> None:
        """Use the same sporting rules for live results and persisted archives."""
        fixture_id = record.fixture_id
        item = self.fixtures[fixture_id]
        home_goals, away_goals = record.home_goals, record.away_goals
        penalties_home, penalties_away = record.penalties_home, record.penalties_away
        cup_id = self._cup_fixture_ids.get(fixture_id)
        staged_id = self._staged_fixture_ids.get(fixture_id)
        staged = self.staged[staged_id] if staged_id else None
        if cup_id is None and staged is None and (penalties_home or penalties_away):
            raise ValueError("league fixtures cannot have penalties")
        if staged is not None and item.stage_id == staged.primary_stage_id:
            is_draw = home_goals == away_goals
            used = bool(penalties_home or penalties_away)
            if staged.kind == "uefa" and used:
                raise ValueError("UEFA league phase never has shootouts")
            if staged.kind == "efl-trophy" and used != is_draw:
                raise ValueError("EFL Trophy drawn group matches require a shootout")
        if cup_id is not None or (staged is not None and item.stage_id != staged.primary_stage_id):
            cup = self.cups[cup_id] if cup_id else staged
            plan = cup.plan_for_fixture(fixture_id)
            tie = plan.tie_for_fixture(fixture_id)
            is_decider = item.leg_number == plan.definition.leg_count
            earlier = [
                results[f.fixture_id].knockout_result()
                for f in tie.fixtures if f.leg_number < item.leg_number
            ]
            interim = resolve_knockout_tie(tie, (*earlier, record.knockout_result()))
            penalties_used = bool(record.penalties_home or record.penalties_away)
            if penalties_used and (not is_decider or interim.aggregate_a_goals != interim.aggregate_b_goals):
                raise ValueError("penalties are valid only for an aggregate-tied deciding leg")
            if is_decider and not interim.complete:
                raise ValueError("a knockout deciding leg must produce a winner")

    @_atomic_world_operation
    def record_result(
        self, fixture_id: str, home_goals: int, away_goals: int,
        *, penalties_home: int = 0, penalties_away: int = 0,
        resolver: str = "managed",
    ) -> WorldMatchResult:
        item = self.fixtures.get(fixture_id)
        if item is None:
            raise KeyError(f"unknown world fixture: {fixture_id}")
        if item.status is not ScheduledFixtureStatus.SCHEDULED or fixture_id in self.results:
            raise ValueError("fixture already played or no longer scheduled")
        record = WorldMatchResult(
            fixture_id, home_goals, away_goals, penalties_home, penalties_away, resolver,
        )
        self._validate_result_semantics(record, self.results)
        cup_id = self._cup_fixture_ids.get(fixture_id)
        staged_id = self._staged_fixture_ids.get(fixture_id)
        staged = self.staged[staged_id] if staged_id else None
        self._put(self.results, fixture_id, record)
        self._put(self.fixtures, fixture_id, replace(item, status=ScheduledFixtureStatus.PLAYED))
        if staged is not None:
            self._remember_staged(staged)
            next_plan = staged.after_result(self.results)
            if next_plan is not None:
                self._schedule_staged_plan(staged, next_plan)
                self._repair_after_new_round(next_plan)
        if cup_id is not None:
            cup = self.cups[cup_id]
            cup_results = {
                fid: r.knockout_result()
                for fid, r in self.results.items() if fid in self._cup_fixture_ids
                and self._cup_fixture_ids[fid] == cup_id
            }
            self._remember_cup(cup)
            new_plan = cup.after_results(cup_results)
            if new_plan is not None:
                self._schedule_cup_plan(cup, new_plan)
                self._repair_after_new_round(new_plan)
        if item.competition_id in self.promotion_playoff_leagues:
            league = self.leagues[item.competition_id]
            playoff_id = self.promotion_playoff_leagues[item.competition_id]
            if playoff_id not in self.cups and all(f.fixture_id in self.results for f in league.fixtures):
                from .season_cycle import create_efl_playoffs
                rows = tuple(row.club_id for row in self.standings(item.competition_id))
                # Use the final fixture window, not the first fixture simulated.
                last_day = max(self.fixtures[f.fixture_id].kickoff.date() for f in league.fixtures)
                self.register_cup(create_efl_playoffs(
                    item.competition_id, rows, int(self.season_label[:4]), final_league_date=last_day,
                ), strengths={})
        return record

    @staticmethod
    def _poisson(rng: Random, expected: float) -> int:
        import math
        product = 1.0
        threshold = math.exp(-max(0.18, min(3.7, expected)))
        count = 0
        while product > threshold:
            product *= rng.random()
            count += 1
        return min(9, count - 1)

    def simulate_fixture(self, fixture_id: str) -> WorldMatchResult:
        fixture = self.fixtures[fixture_id]
        if (self.football_world is not None and
                (fixture.home_club_id in self.football_world.clubs or
                 fixture.away_club_id in self.football_world.clubs)):
            from football_manager.services.world_matches import simulate_registered_fixture
            return simulate_registered_fixture(self, fixture_id)
        if fixture_id in self.results:
            raise ValueError("cannot simulate a fixture twice")
        rng = Random(f"world-runner:{self.seed}:{fixture_id}")
        home_strength = self.strengths[fixture.home_club_id]
        away_strength = self.strengths[fixture.away_club_id]
        difference = home_strength - away_strength
        home_goals = self._poisson(rng, 1.48 + difference * 0.023)
        away_goals = self._poisson(rng, 1.18 - difference * 0.023)
        penalties_home = penalties_away = 0
        cup_id = self._cup_fixture_ids.get(fixture_id)
        staged_id = self._staged_fixture_ids.get(fixture_id)
        staged = self.staged[staged_id] if staged_id else None
        if staged is not None and fixture.stage_id == staged.primary_stage_id and staged.kind == "efl-trophy":
            if home_goals == away_goals:
                penalties_home, penalties_away = (5, 4) if rng.random() < .5 else (4, 5)
        if cup_id is not None or (staged is not None and fixture.stage_id != staged.primary_stage_id):
            cup = self.cups[cup_id] if cup_id else staged
            plan = cup.plan_for_fixture(fixture_id)
            tie = plan.tie_for_fixture(fixture_id)
            if fixture.leg_number == plan.definition.leg_count:
                prior = [
                    self.results[f.fixture_id].knockout_result()
                    for f in tie.fixtures if f.leg_number < fixture.leg_number
                ]
                candidate = KnockoutMatchResult(fixture_id, home_goals, away_goals)
                interim = resolve_knockout_tie(tie, (*prior, candidate))
                if not interim.complete:
                    if rng.random() < 0.5:
                        penalties_home, penalties_away = 5, 4
                    else:
                        penalties_home, penalties_away = 4, 5
        return self.record_result(
            fixture_id, home_goals, away_goals,
            penalties_home=penalties_home, penalties_away=penalties_away,
            resolver="background",
        )

    def advance_until(
        self, last_date: date, *, protected_club_id: str | None = None,
    ) -> WorldRunProgress:
        """Advance fixtures in canonical kickoff/ID order using a transient heap.

        Unlike sorting the entire remaining calendar once per match, this builds
        the due queue once and adds only fixtures created/rescheduled while
        advancing. Replaced fixtures leave stale entries that are ignored.
        """
        if self._advance_queue is not None:
            raise RuntimeError("recursive advance_until is not supported")
        queue = [
            (item.kickoff, item.fixture_id, sequence, item)
            for sequence, item in enumerate(self.fixtures.values())
            if item.status is ScheduledFixtureStatus.SCHEDULED
            and item.kickoff is not None and item.kickoff.date() <= last_date
        ]
        heapify(queue)
        self._advance_queue = queue
        self._advance_cutoff = last_date
        self._advance_sequence = len(queue)
        played = 0
        try:
            while queue:
                _, fixture_id, _, item = heappop(queue)
                if self.fixtures.get(fixture_id) is not item:
                    continue  # Fixture was played or reprogrammed since insertion.
                from football_manager.services.player_development import advance_world_development
                advance_world_development(self, item.match_date)
                if protected_club_id and protected_club_id in (
                    item.home_club_id, item.away_club_id
                ):
                    return WorldRunProgress(played, fixture_id)
                self.simulate_fixture(fixture_id)
                played += 1
            from football_manager.services.player_development import advance_world_development
            advance_world_development(self, last_date)
            return WorldRunProgress(played)
        finally:
            # Do not retain a seasonal heap in saves or when a command fails.
            self._advance_queue = None
            self._advance_cutoff = None
            self._advance_sequence = 0

    def validate_integrity(self) -> None:
        """Reject orphaned fixtures, invalid scores and forged winners.

        Run at I/O boundaries, not per simulated match: it must scale to
        thousands of fixtures without slowing the match engine.
        """
        ownership: dict[str, str] = {}
        ids = set(self.leagues) | set(self.cups) | set(self.staged)
        if len(ids) != len(self.leagues) + len(self.cups) + len(self.staged):
            raise ValueError("duplicate world competition identifier")

        def owned(fid: str, cid: str) -> None:
            if fid in ownership:
                raise ValueError(f"fixture {fid} owned by multiple competitions")
            ownership[fid] = cid

        for cid, edition in self.leagues.items():
            for f in edition.fixtures:
                owned(f.fixture_id, cid)
        for cid, cup in self.cups.items():
            for plan in cup.plans:
                for f in plan.fixtures:
                    owned(f.fixture_id, cid)
        for cid, staged in self.staged.items():
            for f in staged.primary_fixtures:
                owned(f.fixture_id, cid)
            for plan in staged.knockout_plans:
                for f in plan.fixtures:
                    owned(f.fixture_id, cid)

        if set(ownership) != set(self.fixtures):
            raise ValueError("world fixture ledger differs from competition fixtures")
        for fid, fixture in self.fixtures.items():
            if fixture.fixture_id != fid or ownership[fid] != fixture.competition_id:
                raise ValueError(f"fixture ownership mismatch: {fid}")
            if fixture.home_club_id not in self.strengths or fixture.away_club_id not in self.strengths:
                raise ValueError(f"fixture missing club strengths: {fid}")
        if {fid for fid, f in self.fixtures.items()
                if f.status is ScheduledFixtureStatus.PLAYED} != set(self.results):
            raise ValueError("played fixture and result ledger mismatch")
        for fid, result in self.results.items():
            if result.fixture_id != fid:
                raise ValueError(f"result fixture ID mismatch: {fid}")
            self._validate_result_semantics(result, self.results)

        # TS-09: persist only temporally consistent worlds.  Validate once at
        # save/load boundaries rather than once per result during simulation.
        validate_calendar_invariants(
            self.calendar,
            international_calendar=self.international_calendar,
            cups=self.cups,
            staged=self.staged,
        )

        for cup in self.cups.values():
            for index, plan in enumerate(cup.plans):
                available = tuple(self.results[f.fixture_id].knockout_result()
                                  for f in plan.fixtures if f.fixture_id in self.results)
                outcome = resolve_knockout_round(plan, available)
                if index < len(cup.plans) - 1 and not outcome.complete:
                    raise ValueError(f"cup {cup.cup_id} advanced with unfinished round")
                if index == len(cup.plans) - 1:
                    expected = (outcome.winner_club_ids[0]
                                if outcome.complete and len(cup.plans) == len(cup.rounds) else None)
                    if expected != cup.champion_club_id:
                        raise ValueError(f"cup {cup.cup_id} champion does not match final")

        for competition in self.staged.values():
            if competition.knockout_plans and any(
                    f.fixture_id not in self.results for f in competition.primary_fixtures):
                raise ValueError(f"{competition.competition_id} advanced with unfinished first phase")
            for index, plan in enumerate(competition.knockout_plans):
                available = tuple(self.results[f.fixture_id].knockout_result()
                                  for f in plan.fixtures if f.fixture_id in self.results)
                outcome = resolve_knockout_round(plan, available)
                if index < len(competition.knockout_plans) - 1 and not outcome.complete:
                    raise ValueError(f"{competition.competition_id} advanced with unfinished knockout round")
                if index == len(competition.knockout_plans) - 1:
                    expected = (outcome.winner_club_ids[0]
                                if outcome.complete and plan.definition.round_id == "final" else None)
                    if expected != competition.champion_club_id:
                        raise ValueError(f"{competition.competition_id} champion does not match final")

    def save_json(self, destination: str | Path) -> None:
        """Atomic file replacement so interrupted saves do not corrupt progress."""
        self.validate_integrity()
        path = Path(destination)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(self.to_dict(), indent=2, sort_keys=True)
        temp_name = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8", prefix=path.name + ".",
                suffix=".tmp", dir=path.parent, delete=False,
            ) as temp:
                temp.write(payload)
                temp_name = temp.name
            os.replace(temp_name, path)
        finally:
            if temp_name and os.path.exists(temp_name):
                os.unlink(temp_name)

    @classmethod
    def load_json(cls, source: str | Path) -> "WorldSeasonRunner":
        with Path(source).open("r", encoding="utf-8") as handle:
            return cls.from_dict(json.load(handle))

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.SCHEMA_VERSION,
            "season_label": self.season_label, "seed": self.seed,
            "international_calendar": (self.international_calendar.to_dict()
                                       if self.international_calendar else None),
            "calendar": self.calendar.to_dict(),
            "results": [r.to_dict() for r in sorted(self.results.values(), key=lambda x: x.fixture_id)],
            "strengths": dict(self.strengths),
            "leagues": {name: edition.to_dict() for name, edition in self.leagues.items()},
            "cups": {name: cup.to_dict() for name, cup in self.cups.items()},
            "staged": {name: comp.to_dict() for name, comp in self.staged.items()},
            "promotion_playoff_leagues": dict(self.promotion_playoff_leagues),
        }

    @classmethod
    def from_dict(cls, item: Mapping[str, Any]) -> "WorldSeasonRunner":
        if item.get("schema_version") not in (1, 2, cls.SCHEMA_VERSION):
            raise ValueError("unsupported world save schema version")
        raw_international = item.get("international_calendar")
        runner = cls(
            season_label=str(item["season_label"]), seed=int(item["seed"]),
            international_calendar=(InternationalCalendar.from_dict(raw_international)
                                    if raw_international is not None else None),
        )
        runner.strengths = {str(k): int(v) for k, v in item["strengths"].items()}
        runner.promotion_playoff_leagues = {
            str(k): str(v) for k, v in item.get("promotion_playoff_leagues", {}).items()
        }
        from .season_cycle import PLAYOFF_IDS
        if any(PLAYOFF_IDS.get(key) != value for key, value in runner.promotion_playoff_leagues.items()):
            raise ValueError("invalid persisted promotion playoff configuration")
        runner.leagues = {
            str(k): CompetitionEdition.from_dict(value)
            for k, value in item["leagues"].items()
        }
        runner.cups = {
            str(k): DomesticCupSeason.from_dict(value)
            for k, value in item["cups"].items()
        }
        runner.staged = {
            str(k): StagedWorldCompetition.from_dict(value)
            for k, value in item.get("staged", {}).items()
        }
        for staged_id, competition in runner.staged.items():
            if staged_id != competition.competition_id:
                raise ValueError("staged competition ID mismatch in save")
            for fixture in (*competition.primary_fixtures,
                            *(f for plan in competition.knockout_plans for f in plan.fixtures)):
                if fixture.fixture_id in runner._staged_fixture_ids:
                    raise ValueError("duplicate staged fixture in save")
                runner._staged_fixture_ids[fixture.fixture_id] = staged_id
        if any(league_id not in runner.leagues for league_id in runner.promotion_playoff_leagues):
            raise ValueError("playoff league missing from saved world")
        for cup_id, cup in runner.cups.items():
            if cup_id != cup.cup_id:
                raise ValueError("cup ID mismatch in save")
            for plan in cup.plans:
                for fixture in plan.fixtures:
                    if fixture.fixture_id in runner._cup_fixture_ids:
                        raise ValueError("duplicate persisted cup fixture")
                    runner._cup_fixture_ids[fixture.fixture_id] = cup_id
        calendar = SeasonCalendar.from_dict(item["calendar"])
        if calendar.season_label != runner.season_label:
            raise ValueError("save calendar season mismatch")
        runner.fixtures = {fixture.fixture_id: fixture for fixture in calendar.fixtures}
        expected = {
            fixture.fixture_id for edition in runner.leagues.values() for fixture in edition.fixtures
        } | set(runner._cup_fixture_ids) | set(runner._staged_fixture_ids)
        if set(runner.fixtures) != expected:
            raise ValueError("save calendar does not match registered competitions")
        # IDs alone do not guarantee an unmodified sporting schedule. Reject
        # saves in which a fixture was retargeted to other clubs/stages while
        # keeping the same stable ID, otherwise results could corrupt tables.
        for edition in runner.leagues.values():
            for sporting in edition.fixtures:
                scheduled = runner.fixtures[sporting.fixture_id]
                if (scheduled.competition_id, scheduled.edition_id, scheduled.stage_id,
                    scheduled.home_club_id, scheduled.away_club_id,
                    scheduled.leg_number, scheduled.round_number) != (
                    edition.competition_id, sporting.edition_id, sporting.stage_id,
                    sporting.home_club_id, sporting.away_club_id,
                    sporting.leg_number, sporting.round_number
                ):
                    raise ValueError("saved league fixture does not match sporting fixture")
        for cup in runner.cups.values():
            for plan in cup.plans:
                for sporting in plan.fixtures:
                    scheduled = runner.fixtures[sporting.fixture_id]
                    if (scheduled.competition_id, scheduled.edition_id,
                        scheduled.stage_id, scheduled.home_club_id,
                        scheduled.away_club_id, scheduled.leg_number,
                        scheduled.round_number) != (
                        cup.cup_id, cup.edition_id, sporting.stage_id,
                        sporting.home_club_id, sporting.away_club_id,
                        sporting.leg_number, plan.definition.order
                    ):
                        raise ValueError("saved cup fixture does not match sporting fixture")
        for competition in runner.staged.values():
            for sporting in (*competition.primary_fixtures,
                             *(f for plan in competition.knockout_plans for f in plan.fixtures)):
                scheduled = runner.fixtures[sporting.fixture_id]
                if (scheduled.competition_id, scheduled.edition_id,
                    scheduled.stage_id, scheduled.home_club_id, scheduled.away_club_id,
                    scheduled.leg_number, scheduled.round_number) != (
                    competition.competition_id, competition.edition_id,
                    sporting.stage_id, sporting.home_club_id, sporting.away_club_id,
                    sporting.leg_number, sporting.round_number
                ):
                    raise ValueError("saved staged fixture does not match sporting fixture")
        for value in item["results"]:
            record = WorldMatchResult.from_dict(value)
            if record.fixture_id in runner.results or record.fixture_id not in runner.fixtures:
                raise ValueError("save result duplicate or unknown fixture")
            if runner.fixtures[record.fixture_id].status is not ScheduledFixtureStatus.PLAYED:
                raise ValueError("save result must reference PLAYED fixture")
            runner.results[record.fixture_id] = record
        if {fid for fid, fixture in runner.fixtures.items() if fixture.status is ScheduledFixtureStatus.PLAYED} != set(runner.results):
            raise ValueError("save PLAYED fixtures and results do not match")
        if not set(runner.strengths).issuperset(
            club for fixture in runner.fixtures.values()
            for club in (fixture.home_club_id, fixture.away_club_id)
        ):
            raise ValueError("save is missing club strength data")
        # Result archives created in Phase 6.6 had no playoff configuration.
        # Migrate the four-tier DEV world when loading such an archive. If the
        # EFL leagues already finished, create their unplayed playoff brackets
        # immediately instead of leaving the career unable to start 2027/28.
        if item.get("schema_version") in (1, 2):
            from .season_cycle import PLAYOFF_IDS, create_efl_playoffs
            if all(league_id in runner.leagues for league_id in PLAYOFF_IDS):
                runner.configure_promotion_playoffs(tuple(PLAYOFF_IDS))
                for league_id, playoff_id in PLAYOFF_IDS.items():
                    league = runner.leagues[league_id]
                    if playoff_id not in runner.cups and all(
                            f.fixture_id in runner.results for f in league.fixtures):
                        standings = tuple(r.club_id for r in runner.standings(league_id))
                        last_day = max(runner.fixtures[f.fixture_id].kickoff.date()
                                       for f in league.fixtures)
                        runner.register_cup(create_efl_playoffs(
                            league_id, standings, int(runner.season_label[:4]),
                            final_league_date=last_day,
                        ), strengths={})
        runner.validate_integrity()
        return runner
