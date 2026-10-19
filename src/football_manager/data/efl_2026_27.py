"""2026/27 EFL date-slot templates and fictional development divisions.

The EFL published real 2026/27 club fixtures. The development world intentionally
DOES NOT map its imaginary clubs to real ones: only the 46-round kickoff-slot
calendar is imported. Pairings remain GENERATED, never labelled OFFICIAL.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from importlib.resources import files
from random import Random
from typing import Mapping

from football_manager.domain import (
    CompetitionDefinition,
    CompetitionEdition,
    CompetitionFormat,
    CompetitionScope,
    CompetitionStage,
    CompetitionStageKind,
    CompetitionStatus,
    RoundRobinFixturePlan,
    ScheduleSource,
    ScheduledFixture,
    SeasonCalendar,
)

EFL_RELEASE_URL = "https://www.efl.com/news/2026/june/25/the-2026-27-efl-fixtures-are-here/"
EFL_SOURCE_ROOT = "https://fixturedownload.com/results/"


@dataclass(frozen=True, slots=True)
class EflDivisionSpec:
    key: str
    name: str
    short_name: str
    tier: int
    slot_filename: str
    slot_page: str
    strength_base: int
    first_date: date
    last_date: date


_EFL_DIVISIONS = (
    EflDivisionSpec("championship", "Championship", "ECH", 2,
                    "championship_2026_27.slots", "championship-2026", 65,
                    date(2026, 8, 14), date(2027, 5, 1)),
    EflDivisionSpec("league-one", "League One", "EL1", 3,
                    "league_one_2026_27.slots", "efl-league-one-2026", 50,
                    date(2026, 8, 15), date(2027, 5, 8)),
    EflDivisionSpec("league-two", "League Two", "EL2", 4,
                    "league_two_2026_27.slots", "efl-league-two-2026", 35,
                    date(2026, 8, 15), date(2027, 5, 8)),
)
SPECS_BY_KEY = {spec.key: spec for spec in _EFL_DIVISIONS}


@dataclass(frozen=True, slots=True)
class DevelopmentEflDivision:
    """Fictional club identities + genuine matchweek kickoff slots, separate provenance."""

    spec: EflDivisionSpec
    club_names: Mapping[str, str]
    strengths: Mapping[str, int]
    edition: CompetitionEdition
    calendar: SeasonCalendar
    slot_source_url: str
    fixture_source: ScheduleSource = ScheduleSource.GENERATED


# Town names here are invented. No 2026/27 EFL club identities are imported.
_TOWN_SEEDS = (
    "Alderwick", "Blackmere", "Crestfield", "Dunhaven", "Eastbrook", "Fernwick",
    "Glenford", "Hawthorne", "Ironmere", "Juniper Bay", "Kestrelton", "Longford",
    "Marshbury", "Northvale", "Oakminster", "Pinebridge", "Queensford", "Redmarsh",
    "Silverford", "Thornwick", "Upperdale", "Valebridge", "Westmead", "Yewford",
)
_ENDINGS = ("Athletic", "Town", "United", "City", "Rovers", "Albion", "FC", "Wanderers")


def tier_strength(tier: int, club_index: int) -> int:
    """Sandbox-only relative team quality, always separated across tiers.

    These ratings are NOT real player/team ratings and never modify the FastSim
    calibration. All clubs within a division retain meaningful variation.
    """
    bases = {1: 80, 2: 65, 3: 50, 4: 35}
    if tier not in bases or club_index < 0:
        raise ValueError("tier must be 1..4 and club_index >= 0")
    return bases[tier] + Random(tier * 100_003 + club_index * 47).randint(-4, 4)


def load_efl_2026_27_slots(key: str) -> tuple[tuple[datetime, ...], ...]:
    """46 × 12 UTC kickoffs per division; reject any incomplete/invalid template."""
    if key not in SPECS_BY_KEY:
        raise ValueError(f"unknown EFL division: {key}")
    spec = SPECS_BY_KEY[key]
    source = files("football_manager.data").joinpath(
        "official", "england", "efl_slots", spec.slot_filename
    )
    lines = source.read_text(encoding="utf-8").splitlines()
    by_round: dict[int, tuple[datetime, ...]] = {}
    for raw_line in lines:
        line = raw_line.split("#", 1)[0].strip()
        if not line:
            continue
        fields = line.split()
        number = int(fields[0])
        if number in by_round:
            raise ValueError(f"EFL template repeats round {number}")
        slots: list[datetime] = []
        for token in fields[1:]:
            compact, _, multiplicity = token.partition("x")
            count = int(multiplicity) if multiplicity else 1
            if not 1 <= count <= 12:
                raise ValueError(f"bad EFL slot multiplicity: {token}")
            if len(compact) != 9 or compact[4] != "-":
                raise ValueError(f"bad EFL date-time slot: {token}")
            month = int(compact[:2])
            day = int(compact[2:4])
            hour = int(compact[5:7])
            minute = int(compact[7:9])
            year = 2026 if month >= 8 else 2027
            kickoff = datetime(year, month, day, hour, minute, tzinfo=timezone.utc)
            if not (date(2026, 8, 1) <= kickoff.date() <= date(2027, 5, 31)):
                raise ValueError("EFL slot is outside the season")
            slots.extend((kickoff,) * count)
        if len(slots) != 12:
            raise ValueError(f"EFL round {number} needs 12 kickoff slots, got {len(slots)}")
        by_round[number] = tuple(sorted(slots))
    if set(by_round) != set(range(1, 47)):
        raise ValueError("EFL slot template must cover rounds 1..46")
    all_slots = tuple(kickoff for round_slots in by_round.values() for kickoff in round_slots)
    if min(x.date() for x in all_slots) != spec.first_date:
        raise ValueError(f"incorrect opening date for {key}")
    if max(x.date() for x in all_slots) != spec.last_date:
        raise ValueError(f"incorrect final date for {key}")
    return tuple(by_round[number] for number in range(1, 47))


def build_development_efl_2026_27(key: str, *, seed: int = 6510) -> DevelopmentEflDivision:
    """Generate fictional round-robin pairings on published EFL 2026/27 kickoff slots.

    We never claim those GENERATED pairings are real EFL fixtures. The official
    date/time *distribution* is the only imported data. It can be inspected,
    played out by a future competition runner, and later replaced by real teams.
    """
    slots = load_efl_2026_27_slots(key)
    spec = SPECS_BY_KEY[key]
    club_names = {
        f"dev-{key}-{index+1:02d}": (
            f"{_TOWN_SEEDS[(index + (spec.tier - 2) * 8) % len(_TOWN_SEEDS)]} "
            f"{_ENDINGS[(index + spec.tier * 3) % len(_ENDINGS)]}"
        )
        for index in range(24)
    }
    strengths = {
        club_id: tier_strength(spec.tier, index)
        for index, club_id in enumerate(club_names)
    }
    participant_ids = tuple(club_names)
    edition_id = f"dev-{key}-2026-27"
    plan = RoundRobinFixturePlan.generated(
        edition_id=edition_id, stage_id="league", participant_club_ids=participant_ids,
        seed=seed + spec.tier,
    )
    edition = CompetitionEdition(
        edition_id=edition_id,
        competition=CompetitionDefinition(
            competition_id=f"dev-{key}", name=f"{spec.name} (development)",
            short_name=spec.short_name, scope=CompetitionScope.DOMESTIC,
            format=CompetitionFormat.LEAGUE, country="England",
        ),
        season_label="2026/27",
        participant_club_ids=participant_ids,
        stages=(CompetitionStage(
            stage_id="league", name="League", kind=CompetitionStageKind.ROUND_ROBIN,
            order=1, participant_club_ids=participant_ids,
        ),),
        status=CompetitionStatus.ACTIVE,
        fixtures=plan.fixtures,
    )
    by_round = {
        number: tuple(f for f in edition.fixtures if f.round_number == number)
        for number in range(1, 47)
    }
    # A fixture postponed in the published season can occupy a date also used by
    # another matchweek. Shuffle the fictional pair-to-slot mapping until no
    # imaginary club is double-booked, without changing ANY published date slot.
    for attempt in range(256):
        rng = Random(seed + spec.tier * 1000 + attempt)
        scheduled = []
        for number in range(1, 47):
            matches = list(by_round[number])
            rng.shuffle(matches)
            for fixture, kickoff in zip(matches, slots[number - 1], strict=True):
                scheduled.append(ScheduledFixture(
                    fixture_id=fixture.fixture_id,
                    competition_id=edition.competition.competition_id,
                    edition_id=edition_id,
                    stage_id="league",
                    home_club_id=fixture.home_club_id,
                    away_club_id=fixture.away_club_id,
                    kickoff=kickoff,
                    source=ScheduleSource.GENERATED,
                    round_number=number,
                ))
        calendar = SeasonCalendar("2026/27", "UTC", tuple(scheduled))
        if not calendar.detect_conflicts(minimum_rest_hours=24):
            break
    else:
        raise ValueError(f"could not assign conflict-free fictional dates for {key}")
    return DevelopmentEflDivision(
        spec=spec, club_names=club_names, strengths=strengths,
        edition=edition, calendar=calendar,
        slot_source_url=EFL_SOURCE_ROOT + spec.slot_page,
    )


def build_all_development_efl_2026_27() -> dict[str, DevelopmentEflDivision]:
    return {spec.key: build_development_efl_2026_27(spec.key) for spec in _EFL_DIVISIONS}
