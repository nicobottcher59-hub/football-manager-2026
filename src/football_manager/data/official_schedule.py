from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from datetime import date, datetime
from importlib.resources import files
from typing import Any

from football_manager.domain import (
    CompetitionDefinition,
    CompetitionEdition,
    CompetitionFixture,
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


@dataclass(frozen=True, slots=True)
class OfficialScheduleMetadata:
    competition_id: str
    edition_id: str
    season_label: str
    competition_name: str
    short_name: str
    country: str
    stage_id: str
    timezone: str
    source_url: str
    source_title: str
    published_date: date
    snapshot_date: date
    dataset_basis: str


@dataclass(frozen=True, slots=True)
class OfficialCompetitionSchedule:
    metadata: OfficialScheduleMetadata
    club_names: dict[str, str]
    edition: CompetitionEdition
    calendar: SeasonCalendar


_DATA_ROOT = files("football_manager.data").joinpath("official", "england")


def load_premier_league_2026_27() -> OfficialCompetitionSchedule:
    """Load the official published Premier League 2026/27 fixture schedule.

    The dataset stores sporting fixtures and scheduled kickoffs separately in
    the returned edition/calendar pair.  It intentionally does not import real
    results: a new game starting in 2026/27 should simulate its own season.
    """

    metadata = _load_metadata("premier_league_2026_27.meta.json")
    rows = _load_rows("premier_league_2026_27.csv")

    club_names: dict[str, str] = {}
    fixtures: list[CompetitionFixture] = []
    scheduled: list[ScheduledFixture] = []
    week_counters: dict[int, int] = {}

    for row in rows:
        matchweek = int(row["matchweek"])
        week_counters[matchweek] = week_counters.get(matchweek, 0) + 1
        match_number = week_counters[matchweek]
        home_club_id = row["home_club_id"].strip()
        away_club_id = row["away_club_id"].strip()
        home_name = row["home_name"].strip()
        away_name = row["away_name"].strip()
        kickoff = datetime.fromisoformat(row["kickoff"].strip())

        _register_club_name(club_names, home_club_id, home_name)
        _register_club_name(club_names, away_club_id, away_name)

        fixture_id = (
            f"{metadata.edition_id}-{metadata.stage_id}-"
            f"r{matchweek:02d}-m{match_number:02d}"
        )
        fixture = CompetitionFixture(
            fixture_id=fixture_id,
            edition_id=metadata.edition_id,
            stage_id=metadata.stage_id,
            home_club_id=home_club_id,
            away_club_id=away_club_id,
            round_number=matchweek,
        )
        fixtures.append(fixture)
        scheduled.append(
            ScheduledFixture(
                fixture_id=fixture_id,
                competition_id=metadata.competition_id,
                edition_id=metadata.edition_id,
                stage_id=metadata.stage_id,
                home_club_id=home_club_id,
                away_club_id=away_club_id,
                kickoff=kickoff,
                source=ScheduleSource.OFFICIAL,
                round_number=matchweek,
            )
        )

    participant_club_ids = tuple(sorted(club_names))
    stage = CompetitionStage(
        stage_id=metadata.stage_id,
        name="League",
        kind=CompetitionStageKind.ROUND_ROBIN,
        order=1,
        participant_club_ids=participant_club_ids,
    )
    competition = CompetitionDefinition(
        competition_id=metadata.competition_id,
        name=metadata.competition_name,
        short_name=metadata.short_name,
        scope=CompetitionScope.DOMESTIC,
        format=CompetitionFormat.LEAGUE,
        country=metadata.country,
    )
    edition = CompetitionEdition(
        edition_id=metadata.edition_id,
        competition=competition,
        season_label=metadata.season_label,
        participant_club_ids=participant_club_ids,
        stages=(stage,),
        status=CompetitionStatus.PLANNED,
        fixtures=tuple(fixtures),
    )

    # Reuse the Phase 6.2 structural validator: the imported official plan must
    # genuinely be a complete 20-club double round-robin before it can load.
    RoundRobinFixturePlan.seeded(
        fixtures=edition.fixtures,
        participant_club_ids=edition.participant_club_ids,
    )

    calendar = SeasonCalendar(
        season_label=metadata.season_label,
        timezone_name=metadata.timezone,
        fixtures=tuple(scheduled),
    )
    _validate_official_premier_schedule(edition, calendar)
    return OfficialCompetitionSchedule(metadata, club_names, edition, calendar)


def _load_metadata(filename: str) -> OfficialScheduleMetadata:
    raw = json.loads(_DATA_ROOT.joinpath(filename).read_text(encoding="utf-8"))
    return OfficialScheduleMetadata(
        competition_id=str(raw["competition_id"]),
        edition_id=str(raw["edition_id"]),
        season_label=str(raw["season_label"]),
        competition_name=str(raw["competition_name"]),
        short_name=str(raw["short_name"]),
        country=str(raw["country"]),
        stage_id=str(raw["stage_id"]),
        timezone=str(raw["timezone"]),
        source_url=str(raw["source_url"]),
        source_title=str(raw["source_title"]),
        published_date=date.fromisoformat(str(raw["published_date"])),
        snapshot_date=date.fromisoformat(str(raw["snapshot_date"])),
        dataset_basis=str(raw["dataset_basis"]),
    )


def _load_rows(filename: str) -> list[dict[str, str]]:
    with _DATA_ROOT.joinpath(filename).open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    required = {
        "matchweek",
        "kickoff",
        "home_club_id",
        "home_name",
        "away_club_id",
        "away_name",
    }
    if not rows:
        raise ValueError("official fixture dataset cannot be empty")
    if not required.issubset(rows[0]):
        missing = sorted(required - set(rows[0]))
        raise ValueError(f"official fixture dataset is missing columns: {missing}")
    return rows


def _register_club_name(names: dict[str, str], club_id: str, club_name: str) -> None:
    if not club_id or not club_name:
        raise ValueError("official fixture club ID/name cannot be empty")
    existing = names.get(club_id)
    if existing is not None and existing != club_name:
        raise ValueError(f"club ID {club_id!r} has inconsistent official names")
    names[club_id] = club_name


def _validate_official_premier_schedule(
    edition: CompetitionEdition,
    calendar: SeasonCalendar,
) -> None:
    if len(edition.participant_club_ids) != 20:
        raise ValueError("Premier League 2026/27 dataset must contain 20 clubs")
    if len(edition.fixtures) != 380 or len(calendar.fixtures) != 380:
        raise ValueError("Premier League 2026/27 dataset must contain 380 fixtures")
    rounds = {fixture.round_number for fixture in edition.fixtures}
    if rounds != set(range(1, 39)):
        raise ValueError("Premier League 2026/27 dataset must contain matchweeks 1..38")
    for round_number in range(1, 39):
        round_fixtures = [
            fixture for fixture in edition.fixtures if fixture.round_number == round_number
        ]
        if len(round_fixtures) != 10:
            raise ValueError(f"matchweek {round_number} must contain 10 fixtures")
        clubs = {
            club_id
            for fixture in round_fixtures
            for club_id in (fixture.home_club_id, fixture.away_club_id)
        }
        if len(clubs) != 20:
            raise ValueError(f"matchweek {round_number} must use every club exactly once")
    if any(item.source is not ScheduleSource.OFFICIAL for item in calendar.fixtures):
        raise ValueError("official Premier League calendar has non-official fixture provenance")
    # The published release begins on 21 August 2026 and ends on 30 May 2027.
    dates = [item.match_date for item in calendar.fixtures]
    if min(dates) != date(2026, 8, 21) or max(dates) != date(2027, 5, 30):
        raise ValueError("official Premier League calendar has unexpected season bounds")
