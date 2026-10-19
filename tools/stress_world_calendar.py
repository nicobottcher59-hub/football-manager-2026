"""Diagnostic-only synthetic multi-country calendar and world-runner stress harness.

This does not create real countries, FIFA international duty, or a Club World Cup.
It exercises the actual WorldSeasonRunner, existing round-robin generator,
league-date policy, and optionally the existing UEFA-style staged competitions.
No production modules are modified. Run from repository root:

    python tools/stress_world_calendar.py --quick
    python tools/stress_world_calendar.py --full --output reports/world_scalability.json
"""
from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from datetime import date, time, timedelta
from dataclasses import replace
import json
from pathlib import Path
import random
try:
    import resource  # Available on Linux/macOS, not on Windows.
except ImportError:
    resource = None
import sys
from time import perf_counter

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from football_manager.data.staged_2026_27 import build_uefa_2026_27
from football_manager.domain.calendar import (
    CalendarBlock,
    ScheduledFixtureStatus,
    SchedulingWindow,
    reschedule_fixture_into_window,
    LeagueSchedulingPolicy,
    ScheduleSource,
    SeasonCalendar,
    generate_league_round_dates, reprogram_round_dates_for_blackouts,
    schedule_fixtures_on_round_dates,
)
from football_manager.domain.competition import (
    CompetitionDefinition,
    CompetitionEdition,
    CompetitionFormat,
    CompetitionScope,
    CompetitionStage,
    CompetitionStageKind,
)
from football_manager.domain.domestic_cups import DomesticCupRound, DomesticCupSeason
from football_manager.domain.league import generate_double_round_robin
from football_manager.domain.world_runner import WorldSeasonRunner
from football_manager.domain.international_calendar import (
    InternationalCalendar, InternationalEvent, InternationalDateSource,
    InternationalImpact, build_international_calendar,
)


@dataclass
class ScenarioMetrics:
    leagues: int
    countries: int
    clubs: int
    seed: int
    blackouts: bool
    master_calendar: bool
    staged_competitions: int
    simulate: bool
    season_year: int = 2026
    cup_proxy: bool = False
    postponements_requested: int = 0
    postponements_succeeded: int = 0
    build_seconds: float = 0.0
    staged_seconds: float = 0.0
    run_seconds: float | None = None
    total_seconds: float = 0.0
    initial_fixtures: int = 0
    final_fixtures: int = 0
    results: int = 0
    duplicate_ids: int = 0
    orphan_results: int = 0
    unplayed: int | None = None
    conflicts_48h: int = 0
    blackout_league_violations: int = 0
    blackout_staged_violations: int = 0
    blackout_cup_proxy_violations: int = 0
    blackout_postponement_violations: int = 0
    rescheduled: int = 0
    world_json_bytes: int | None = None
    json_serialize_seconds: float | None = None
    json_roundtrip_seconds: float | None = None
    rss_mb: float = 0.0
    status: str = "not_started"
    error: str | None = None


def _blackouts(year: int) -> tuple[CalendarBlock, ...]:
    # Deliberately synthetic test windows, NOT the official FIFA calendar.
    return (
        CalendarBlock(date(year, 9, 7), date(year, 9, 15), "synthetic-september"),
        CalendarBlock(date(year, 11, 9), date(year, 11, 17), "synthetic-november"),
        CalendarBlock(date(year + 1, 3, 15), date(year + 1, 3, 23), "synthetic-march"),
    )


def create_world(*, leagues: int, seed: int, blackouts: bool = False,
                 year: int = 2026, master_calendar: bool = False) -> tuple[WorldSeasonRunner, tuple[CalendarBlock, ...]]:
    if not 1 <= leagues <= 64 or not 2026 <= year <= 2035:
        raise ValueError("leagues must be 1..64 and year in 2026..2035")
    label = f"{year}/{(year + 1) % 100:02d}"
    master = build_international_calendar(year, year + 1) if master_calendar else None
    blocks = _blackouts(year) if blackouts else ()
    # Synthetic blackout windows are real constraints of THIS experiment,
    # not fabricated official FIFA dates. Attach them to the experimental
    # world so the cup/UEFA planner and postponements must respect them too.
    synthetic = tuple(
        InternationalEvent(
            event_id=f"test-blackout-{year}-{index}", name=block.label,
            start_date=block.start_date, end_date=block.end_date,
            impact=InternationalImpact.CLUB_BREAK,
            source=InternationalDateSource.OVERRIDE,
        ) for index, block in enumerate(blocks)
    )
    events = (*(master.events if master else ()), *synthetic)
    calendar = (InternationalCalendar(tuple(sorted(events, key=lambda e: (e.start_date, e.event_id))))
                if events else None)
    world = WorldSeasonRunner(season_label=label, seed=seed, international_calendar=calendar)
    if master is not None:
        blocks += master.league_blackouts(date(year, 8, 1), date(year + 1, 6, 30))
    available_clubs: list[str] = []
    for index in range(leagues):
        country_index = index // 4
        division = index % 4 + 1
        league_id = f"stress-country{country_index:02}-div{division}"
        edition_id = f"{league_id}-{year}-{(year + 1) % 100:02d}"
        clubs = tuple(f"{league_id}-club{i:02}" for i in range(1, 21))
        available_clubs.extend(clubs)
        fixtures = generate_double_round_robin(
            edition_id=edition_id, stage_id="league", participant_club_ids=clubs,
            seed=seed + 31 * index,
        )
        edition = CompetitionEdition(
            edition_id=edition_id,
            competition=CompetitionDefinition(
                competition_id=league_id, name=f"Synthetic League {index + 1}",
                short_name=f"S{index + 1}", scope=CompetitionScope.DOMESTIC,
                format=CompetitionFormat.LEAGUE, country=f"Synthetic Country {country_index + 1}",
            ),
            season_label=label, participant_club_ids=clubs,
            stages=(CompetitionStage(
                stage_id="league", name="League", kind=CompetitionStageKind.ROUND_ROBIN,
                order=1, participant_club_ids=clubs,
            ),),
            fixtures=fixtures,
        )
        start = date(year, 8, 1) + timedelta(days=7 * (country_index % 3))
        # Country-dependent windows / match weekdays exercise distinct schedules.
        end = date(year + 1, 5, 31) - timedelta(days=7 * (country_index % 2))
        weekday = (5, 6, 5, 6)[country_index % 4]
        policy = LeagueSchedulingPolicy(
            season_start=start, season_end=end, preferred_weekday=weekday,
            kickoff_local_time=time(15, 0), minimum_round_gap_days=3,
            # Preserve TC-E0 synthetic exclusions; FIFA windows are overlaid
            # AFTER the normal league calendar has already been generated.
            blackout_periods=_blackouts(year) if blackouts else (),
            midweek_weekdays=(1, 2),
        )
        natural = generate_league_round_dates(38, policy)
        dates = (reprogram_round_dates_for_blackouts(natural, replace(policy, blackout_periods=blocks))
                 if master is not None else natural)
        scheduled = schedule_fixtures_on_round_dates(
            fixtures, dates, competition_id=league_id, source=ScheduleSource.GENERATED,
        )
        if master is not None:
            scheduled = tuple(replace(item, original_kickoff=(natural[item.round_number]
                                  if natural[item.round_number] != item.kickoff else None))
                              for item in scheduled)
        world.register_league(
            edition,
            SeasonCalendar(label, "UTC", scheduled),
            {club: 55 + (i % 25) for i, club in enumerate(clubs)},
        )

    return world, blocks



def add_staged(world: WorldSeasonRunner, *, seed: int, count: int, year: int) -> None:
    if count not in range(4):
        raise ValueError("staged competition count must be 0..3")
    clubs = [c for edition in world.leagues.values() for c in edition.participant_club_ids]
    need = 36 * count
    if len(clubs) < need:
        raise ValueError(f"requires at least {need} distinct clubs")
    # Spread entrants across countries and divisions. Deliberately NOT a
    # real UEFA qualification/allocation algorithm.
    sampled = clubs[::20] + clubs[1::20] + clubs[2::20]
    if len(sampled) < need:
        sampled = clubs.copy()
        random.Random(seed).shuffle(sampled)
    for index, cid in enumerate(("champions-league", "europa-league", "conference-league")[:count]):
        world.register_staged(
            build_uefa_2026_27(cid, tuple(sampled[index * 36:(index + 1) * 36]),
                               seed=seed + index + 1000, season_start_year=year),
            strengths={},
        )


def add_cup_proxy(world: WorldSeasonRunner, *, seed: int, year: int) -> None:
    """Knockout congestion proxy: NOT a FIFA Club World Cup implementation."""
    clubs = [c for edition in world.leagues.values() for c in edition.participant_club_ids]
    if len(clubs) < 32:
        raise ValueError("cup proxy requires at least 32 different clubs")
    # Overlap some UEFA participants to force calendar contention.
    staged_clubs = [c for comp in world.staged.values() for c in comp.participants]
    pool = list(dict.fromkeys([*staged_clubs, *clubs]))
    dates = (
        date(year, 10, 14), date(year, 11, 4),
        date(year + 1, 1, 20), date(year + 1, 3, 10),
        date(year + 1, 5, 5),
    )
    cup = DomesticCupSeason(
        cup_id="stress-intercontinental-knockout-proxy",
        name="Synthetic intercontinental knockout proxy",
        season_label=world.season_label, draw_seed=seed + 930,
        rounds=tuple(
            DomesticCupRound(
                round_id=f"round-{i+1}", label=f"Synthetic round {i+1}",
                dates=(day,), entrants=tuple(pool[:32]) if i == 0 else (),
            )
            for i, day in enumerate(dates)
        ),
    )
    world.register_cup(cup, strengths={})


def inject_postponements(world: WorldSeasonRunner, *, count: int, year: int,
                        blocks: tuple[CalendarBlock, ...]) -> tuple[int, int]:
    """Exercise domain reschedule policy while leaving production code untouched."""
    if count < 0 or count > 20:
        raise ValueError("postponements must be between 0 and 20")
    scheduled = sorted(
        (f for f in world.fixtures.values()
         if f.competition_id in world.leagues and f.kickoff is not None
         and date(year, 10, 1) <= f.kickoff.date() <= date(year, 12, 15)),
        key=lambda f: (f.kickoff, f.fixture_id),
    )
    # Spread postponements across fixtures rather than congesting one team.
    chosen = scheduled[::max(1, len(scheduled) // max(1, count))][:count]
    succeeded = 0
    within_block = 0
    for item in chosen:
        original = item.kickoff
        assert original is not None
        world.fixtures[item.fixture_id] = replace(
            item, kickoff=None, status=ScheduledFixtureStatus.POSTPONED,
            original_kickoff=original,
        )
        calendar = world.calendar
        window = SchedulingWindow(
            window_id=f"synthetic-postpone-{item.fixture_id}",
            start_date=original.date() + timedelta(days=5),
            end_date=original.date() + timedelta(days=40),
        )
        # Use the same world-level blackout contract as cup/UEFA scheduling.
        if world.international_calendar is not None:
            updated = world.reschedule_league_fixture(item.fixture_id, window)
        else:
            revised = reschedule_fixture_into_window(
                calendar, item.fixture_id, window=window,
                kickoff_local_time=time(19, 45), minimum_rest_hours=48,
            )
            updated = revised.fixture(item.fixture_id)
            world.fixtures[item.fixture_id] = updated
        succeeded += 1
        if any(block.contains(updated.kickoff.date()) for block in blocks):
            within_block += 1
    return succeeded, within_block

def measure(*, leagues: int, seed: int = 6060, blackouts: bool = False,
            staged_competitions: int = 0, simulate: bool = True,
            cup_proxy: bool = False, postponements: int = 0, year: int = 2026,
            master_calendar: bool = False) -> ScenarioMetrics:
    measurement = ScenarioMetrics(
        leagues=leagues, countries=(leagues + 3) // 4, clubs=leagues * 20,
        seed=seed, blackouts=blackouts, master_calendar=master_calendar,
        staged_competitions=staged_competitions, simulate=simulate, season_year=year, cup_proxy=cup_proxy,
        postponements_requested=postponements,
    )
    overall = perf_counter()
    try:
        build = perf_counter()
        world, blocks = create_world(leagues=leagues, seed=seed, blackouts=blackouts,
                                    year=year, master_calendar=master_calendar)
        measurement.build_seconds = perf_counter() - build
        staged = perf_counter()
        add_staged(world, seed=seed, count=staged_competitions, year=year)
        if cup_proxy:
            add_cup_proxy(world, seed=seed, year=year)
        if postponements:
            succeeded, violates_block = inject_postponements(
                world, count=postponements, year=year, blocks=blocks,
            )
            measurement.postponements_succeeded = succeeded
            measurement.blackout_postponement_violations = violates_block
        measurement.staged_seconds = perf_counter() - staged
        measurement.initial_fixtures = len(world.fixtures)
        if simulate:
            run = perf_counter()
            world.advance_until(date(year + 1, 6, 30))
            measurement.run_seconds = perf_counter() - run
        measurement.final_fixtures = len(world.fixtures)
        measurement.results = len(world.results)
        measurement.duplicate_ids = len(world.fixtures) - len(set(world.fixtures))
        measurement.orphan_results = len(set(world.results) - set(world.fixtures))
        measurement.unplayed = len(set(world.fixtures) - set(world.results)) if simulate else None
        measurement.conflicts_48h = len(world.calendar.detect_conflicts(minimum_rest_hours=48))
        measurement.rescheduled = sum(bool(f.original_kickoff) for f in world.fixtures.values())
        if blocks:
            measurement.blackout_league_violations = sum(
                any(block.contains(f.kickoff.date()) for block in blocks)
                for f in world.fixtures.values()
                if f.competition_id in world.leagues and f.kickoff is not None
            )
            measurement.blackout_staged_violations = sum(
                any(block.contains(f.kickoff.date()) for block in blocks)
                for f in world.fixtures.values()
                if f.competition_id in world.staged and f.kickoff is not None
            )
            measurement.blackout_cup_proxy_violations = sum(
                any(block.contains(f.kickoff.date()) for block in blocks)
                for f in world.fixtures.values()
                if f.competition_id in world.cups and f.kickoff is not None
            )
        # This is the WorldSeasonRunner ledger only, never a complete SaveGame.
        serial_start = perf_counter()
        payload = json.dumps(world.to_dict(), indent=2, sort_keys=True)
        measurement.world_json_bytes = len(payload.encode("utf-8"))
        measurement.json_serialize_seconds = perf_counter() - serial_start
        if simulate:
            serial_start = perf_counter()
            restored = WorldSeasonRunner.from_dict(json.loads(payload))
            if set(restored.fixtures) != set(world.fixtures) or set(restored.results) != set(world.results):
                raise AssertionError("world JSON roundtrip lost fixtures or results")
            measurement.json_roundtrip_seconds = perf_counter() - serial_start
        structural_ok = (measurement.conflicts_48h == 0 and
                         (measurement.unplayed in (None, 0)) and
                         measurement.orphan_results == 0 and
                         measurement.duplicate_ids == 0 and
                         measurement.postponements_succeeded == postponements)
        if not structural_ok:
            measurement.status = "invariant_failure"
        elif sum((measurement.blackout_league_violations,
                  measurement.blackout_staged_violations,
                  measurement.blackout_cup_proxy_violations,
                  measurement.blackout_postponement_violations)):
            measurement.status = "window_invariant_failure"
        else:
            measurement.status = "pass"
    except Exception as exc:
        measurement.status = "error"
        measurement.error = f"{type(exc).__name__}: {exc}"
    measurement.total_seconds = perf_counter() - overall
    if resource is not None and sys.platform.startswith("linux"):
        # Cumulative peak across this process, not scenario-specific RAM usage.
        measurement.rss_mb = round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 2)
    return measurement


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--quick", action="store_true", help="short diagnostic subset")
    mode.add_argument("--full", action="store_true", help="4/8/16/24 league stress matrix")
    mode.add_argument("--single", action="store_true", help="one configurable scenario")
    parser.add_argument("--seed", type=int, default=6060)
    parser.add_argument("--year", type=int, default=2026)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--leagues", type=int, default=24, help="--single: synthetic 20-club leagues")
    parser.add_argument("--staged", type=int, default=3, help="--single: UEFA-style tournaments (0..3)")
    parser.add_argument("--blackouts", action="store_true", help="--single: synthetic international windows")
    parser.add_argument("--master-calendar", action="store_true",
                        help="--single: TC-E1 recurring international calendar (not national-team fixtures)")
    parser.add_argument("--cup-proxy", action="store_true", help="--single: generic intercontinental knockout proxy")
    parser.add_argument("--postponements", type=int, default=0, help="--single: forced league reprogramming")
    parser.add_argument("--no-sim", action="store_true", help="--single: only build the schedule")
    args = parser.parse_args()
    scenarios = (
        [(args.leagues, args.staged, args.blackouts, not args.no_sim,
          args.cup_proxy, args.postponements)] if args.single else
        [(4, 0, False, True, False, 0),
         (8, 0, True, False, False, 0),
         (4, 1, True, False, False, 0)]
        if args.quick else
        [(n, 0, False, True, False, 0) for n in (4, 8, 16, 24)] +
        [(24, 3, True, False, True, 4), (8, 1, True, True, True, 2)]
    )
    output = []
    for leagues, staged, blackouts, simulate, cup_proxy, postponements in scenarios:
        print(f"START leagues={leagues} staged={staged} blackout={blackouts} "
              f"simulate={simulate} cup_proxy={cup_proxy} postponements={postponements}", flush=True)
        result = measure(leagues=leagues, seed=args.seed, blackouts=blackouts,
                         staged_competitions=staged, simulate=simulate,
                         cup_proxy=cup_proxy, postponements=postponements,
                         year=args.year, master_calendar=args.master_calendar)
        output.append(asdict(result))
        print(json.dumps(output[-1], sort_keys=True), flush=True)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps({"metadata": {
            "purpose": "synthetic stress, not real FIFA or Club World Cup fixtures",
            "seed": args.seed,
            "season_start_year": args.year,
            "resource_peak_rss_is_process_cumulative": True,
            "platform": sys.platform,
            "python": sys.version.split()[0],
            "description": "20 clubs per league; 4 divisions per synthetic country",
        }, "scenarios": output}, indent=2) + "\n", encoding="utf-8")
        print(f"Saved: {args.output}", flush=True)
    return int(any(row["status"] != "pass" for row in output))


if __name__ == "__main__":
    raise SystemExit(main())
