"""GENERATED 2027+ season templates; never claimed to be official fixture data.

Round-robin opponents are regenerated after transfers between divisions. Window
policies use next season's weekdays/months and do not copy old fixture pairings
or use a fixed +365-day shift.
"""
from __future__ import annotations

from dataclasses import replace
from datetime import date, datetime, time, timedelta, timezone
from typing import Sequence, Mapping

from football_manager.domain.calendar import (
    ScheduledFixture, SeasonCalendar, ScheduleSource, LeagueSchedulingPolicy,
    generate_league_round_dates, reprogram_round_dates_for_blackouts,
)
from football_manager.domain.international_calendar import build_international_calendar
from football_manager.domain.competition import CompetitionEdition
from football_manager.domain.domestic_cups import DomesticCupSeason
from football_manager.domain.league import RoundRobinFixturePlan
from .english_cups_2026_27 import build_fa_cup_2026_27, build_carabao_cup_2026_27
from .premier_calendar import build_premier_calendar


def weekend_start(year: int) -> date:
    first = date(year, 8, 14)
    return first + timedelta(days=(5-first.weekday()) % 7)


def normal_round_dates(year: int, round_count: int) -> tuple[date, ...]:
    """Natural football fixture, generated BEFORE applying international breaks."""
    if round_count not in (38, 46):
        raise ValueError("supported English division must play 38 or 46 rounds")
    start = weekend_start(year)
    weekends = [start + timedelta(days=7*i) for i in range(38)]
    if round_count == 38:
        return tuple(weekends)
    midweek_after = (3, 7, 11, 15, 19, 23, 27, 31)
    return tuple(sorted((*weekends, *(weekends[i]+timedelta(days=3) for i in midweek_after))))


def round_dates(year: int, round_count: int) -> tuple[date, ...]:
    """Natural English matchweeks with a separate FIFA reprogramming pass."""
    normal = normal_round_dates(year, round_count)
    first, last = normal[0], date(year + 1, 5, 31)
    master = build_international_calendar(year, year + 1)
    policy = LeagueSchedulingPolicy(
        season_start=first, season_end=last,
        preferred_weekday=5, kickoff_local_time=time(15),
        minimum_round_gap_days=3,
        blackout_periods=master.league_blackouts(first, last),
        midweek_weekdays=(1, 2),
    )
    original = {i: datetime.combine(day, time(15), tzinfo=timezone.utc)
                for i, day in enumerate(normal, start=1)}
    revised = reprogram_round_dates_for_blackouts(original, policy)
    return tuple(revised[i].date() for i in range(1, round_count + 1))


def generated_edition(previous: CompetitionEdition, participants: Sequence[str], year: int,
                      *, seed: int = 6700) -> tuple[CompetitionEdition, SeasonCalendar]:
    participants = tuple(participants)
    if len(participants) != len(previous.participant_club_ids) or len(set(participants)) != len(participants):
        raise ValueError("invalid promoted/relegated club roster")
    season_label = f"{year}/{(year+1) % 100:02d}"
    edition_id = f"{previous.competition_id}-{year}-{(year+1) % 100:02d}"
    plan = RoundRobinFixturePlan.generated(
        edition_id=edition_id, stage_id="league", participant_club_ids=participants, seed=seed+year,
    )
    edition = replace(
        previous, edition_id=edition_id, season_label=season_label,
        participant_club_ids=participants,
        stages=tuple(replace(stage, participant_club_ids=participants) for stage in previous.stages),
        fixtures=plan.fixtures,
    )
    round_count = 2 * (len(participants) - 1)
    if previous.competition_id == "dev-premier" and round_count == 38:
        # Reference the 2026/27 published Premier kickoff *slots* for fictional
        # future pairings, rather than uniformly assigning Saturdays.
        return edition, build_premier_calendar(edition, year)
    normal = normal_round_dates(year, round_count)
    windows = round_dates(year, round_count)
    calendar = SeasonCalendar(season_label, "UTC", tuple(
        ScheduledFixture(
            fixture.fixture_id, edition.competition_id, edition.edition_id, "league",
            fixture.home_club_id, fixture.away_club_id,
            datetime.combine(windows[fixture.round_number-1], time(15), tzinfo=timezone.utc),
            ScheduleSource.GENERATED, round_number=fixture.round_number,
            original_kickoff=(
                datetime.combine(normal[fixture.round_number-1], time(15), tzinfo=timezone.utc)
                if windows[fixture.round_number-1] != normal[fixture.round_number-1] else None
            ),
        ) for fixture in edition.fixtures
    ))
    return edition, calendar


def project_window(source: date, next_year: int) -> date:
    """Project a reference competition round by month and weekday policy.

    Final weekday alignment is GENERATED; no assertion of official future dates.
    """
    new_year = next_year if source.month >= 8 else next_year + 1
    anchor = date(new_year, source.month, min(source.day, 28) if source.month == 2 else source.day)
    return min((anchor + timedelta(days=offset) for offset in (-3,-2,-1,0,1,2,3)
                if (anchor+timedelta(days=offset)).weekday() == source.weekday()),
               key=lambda day: abs((day-anchor).days))


def generated_cups(tiers: Mapping[int, Sequence[str]], european_clubs: Sequence[str], year: int,
                   *, seed: int = 6720) -> tuple[DomesticCupSeason, DomesticCupSeason]:
    if year <= 2026:
        raise ValueError("2026/27 should use published windows from the original builders")
    premier = tuple(tiers[1])
    european = [c for c in european_clubs if c in premier]
    european += [c for c in premier if c not in european]
    carabao_entrants = tuple(european[:9])
    templates = (build_fa_cup_2026_27(tiers, seed=seed),
                 build_carabao_cup_2026_27(tiers, european_entrant_ids=carabao_entrants, seed=seed+1))
    season_label = f"{year}/{(year+1) % 100:02d}"
    return tuple(replace(
        template, season_label=season_label,
        rounds=tuple(replace(r, dates=tuple(project_window(day, year) for day in r.dates))
                     for r in template.rounds),
        plans=[], champion_club_id=None, source_url="",
        qualification_note="GENERATED DEV future windows; not official dates or confirmed cup entrants",
    ) for template in templates)
