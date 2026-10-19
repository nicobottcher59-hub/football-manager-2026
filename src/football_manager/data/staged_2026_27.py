"""Official 2026/27 competition-round windows with GENERATED fictional draws.

The matchday calendars come from UEFA/EFL published round dates. Kickoff time and
fictitious matchups are DEV-generated; they are never an official seeded draw.
"""
from __future__ import annotations

from datetime import date
from random import Random
from typing import Sequence

from football_manager.domain.competition import CompetitionFixture
from football_manager.domain.staged_world import StagedWorldCompetition
from .future_seasons import project_window

UEFA_SOURCES = {
    "champions-league": "https://www.uefa.com/uefachampionsleague/news/02a6-20d57cfcd03e-407c22a7f465-1000--2026-27-champions-league-teams-dates-draws-format-final/",
    "europa-league": "https://www.uefa.com/uefaeuropaleague/news/02a6-20d57d095740-e1e0b3de85df-1000--2026-27-europa-league-teams-dates-draws-format-final/",
    "conference-league": "https://www.uefa.com/uefaconferenceleague/news/02a6-20d57d15f093-a90cf54c928f-1000--2026-27-conference-league-teams-dates-draws-format-final/",
}
EFL_TROPHY_SOURCE = "https://www.efl.com/news/2026/june/23/under-21-teams-and-group-stage-draw-confirmed-for-2026-27-efl-trophy/"


def _days(*values: str) -> tuple[date, ...]:
    return tuple(date.fromisoformat(s) for s in values)


UEFA_WINDOWS = {
    "champions-league": {
        "league": _days("2026-09-09", "2026-10-14", "2026-10-21", "2026-11-04", "2026-11-25", "2026-12-09", "2027-01-20", "2027-01-27"),
        "playoff": _days("2027-02-17", "2027-02-24"),
        "r16": _days("2027-03-10", "2027-03-17"),
        "qf": _days("2027-04-07", "2027-04-14"),
        "sf": _days("2027-04-28", "2027-05-05"),
        "final": _days("2027-06-05"),
    },
    "europa-league": {
        "league": _days("2026-09-17", "2026-10-15", "2026-10-22", "2026-11-05", "2026-11-26", "2026-12-10", "2027-01-21", "2027-01-28"),
        "playoff": _days("2027-02-18", "2027-02-25"),
        "r16": _days("2027-03-11", "2027-03-18"),
        "qf": _days("2027-04-08", "2027-04-15"),
        "sf": _days("2027-04-29", "2027-05-06"),
        "final": _days("2027-05-26"),
    },
    "conference-league": {
        "league": _days("2026-10-15", "2026-10-22", "2026-11-05", "2026-11-26", "2026-12-10", "2026-12-17"),
        "playoff": _days("2027-02-18", "2027-02-25"),
        "r16": _days("2027-03-11", "2027-03-18"),
        "qf": _days("2027-04-08", "2027-04-15"),
        "sf": _days("2027-04-29", "2027-05-06"),
        "final": _days("2027-06-02"),
    },
}

TROPHY_WINDOWS = {
    "r32": _days("2026-12-08"), "r16": _days("2027-01-12"),
    "qf": _days("2027-02-16"), "sf": _days("2027-03-09"),
    "final": _days("2027-04-11"),
}
TROPHY_GROUP_ANCHORS = _days("2026-09-22", "2026-10-13", "2026-11-10")


def _swiss_fixture_pairs(clubs: Sequence[str], matchdays: int, seed: int) -> tuple[tuple[tuple[str, str], ...], ...]:
    """Eight/six distinct-opponent matchdays, with four/three home games.

    A circle schedule supplies distinct opponents without rematches. Every vertex
    has even degree (8 or 6), so orient its Euler circuit to balance home/away
    *exactly*. More restrictive pot/country draws belong to a real-data importer.
    """
    if len(clubs) != 36 or matchdays not in (6, 8):
        raise ValueError("the current league-phase template requires 36 participants and 6/8 dates")
    rotated = list(clubs)
    Random(seed).shuffle(rotated)
    raw = []
    for r in range(matchdays):
        for i in range(18):
            raw.append((r, rotated[i], rotated[-1-i]))
        rotated = [rotated[0], rotated[-1], *rotated[1:-1]]
    adjacency: dict[str, list[tuple[int, str]]] = {club: [] for club in clubs}
    for index, (_r, first, second) in enumerate(raw):
        adjacency[first].append((index, second))
        adjacency[second].append((index, first))
    used = set()
    oriented: dict[int, tuple[str, str]] = {}
    for root in clubs:
        # Traverse each Eulerian component, orienting edges as they are entered.
        stack = [root]
        while stack:
            current = stack[-1]
            while adjacency[current] and adjacency[current][-1][0] in used:
                adjacency[current].pop()
            if not adjacency[current]:
                stack.pop()
                continue
            edge_index, other = adjacency[current].pop()
            if edge_index in used:
                continue
            used.add(edge_index)
            oriented[edge_index] = (current, other)
            stack.append(other)
    if len(oriented) != len(raw):
        raise RuntimeError("balanced fixture orientation failed")
    batches = [[] for _ in range(matchdays)]
    for index, (round_index, _, _) in enumerate(raw):
        batches[round_index].append(oriented[index])
    return tuple(tuple(batch) for batch in batches)


def build_uefa_2026_27(
    competition_id: str, participants: Sequence[str], *, seed: int = 6600,
    season_start_year: int = 2026,
) -> StagedWorldCompetition:
    if competition_id not in UEFA_WINDOWS:
        raise ValueError(f"unsupported UEFA competition {competition_id}")
    if len(participants) != 36 or len(set(participants)) != 36:
        raise ValueError("UEFA competition must have 36 unique teams")
    dates = UEFA_WINDOWS[competition_id]
    if season_start_year != 2026:
        dates = {key: tuple(project_window(day, season_start_year) for day in windows)
                 for key, windows in dates.items()}
    batches = _swiss_fixture_pairs(participants, len(dates["league"]), seed)
    edition_id = f"{competition_id}-{season_start_year}-{(season_start_year+1)%100:02d}"
    fixtures, fixture_dates = [], []
    for r, batch in enumerate(batches, 1):
        for i, (home, away) in enumerate(batch, 1):
            fixtures.append(CompetitionFixture(
                f"{edition_id}-md{r:02d}-m{i:02d}", edition_id, "league-phase",
                home, away, round_number=r,
            ))
            fixture_dates.append(dates["league"][r-1])
    return StagedWorldCompetition(
        competition_id=competition_id,
        name={"champions-league": "UEFA Champions League", "europa-league": "UEFA Europa League",
              "conference-league": "UEFA Conference League"}[competition_id],
        season_label=f"{season_start_year}/{(season_start_year+1)%100:02d}", kind="uefa", participants=tuple(participants),
        primary_fixtures=tuple(fixtures), primary_dates=tuple(fixture_dates),
        knockout_windows={k: v for k, v in dates.items() if k != "league"},
        seed=seed, source_url=UEFA_SOURCES[competition_id] if season_start_year == 2026 else "",
    )


def build_efl_trophy_2026_27(
    league_one: Sequence[str], league_two: Sequence[str], *, seed: int = 6670,
    season_start_year: int = 2026,
) -> StagedWorldCompetition:
    if len(league_one) != 24 or len(league_two) != 24 or len(set((*league_one, *league_two))) != 48:
        raise ValueError("EFL Trophy requires 24 unique League One and 24 League Two clubs")
    trophy_dates = (TROPHY_GROUP_ANCHORS if season_start_year == 2026 else
                    tuple(project_window(day, season_start_year) for day in TROPHY_GROUP_ANCHORS))
    knockout_dates = (TROPHY_WINDOWS if season_start_year == 2026 else
                      {key: tuple(project_window(day, season_start_year) for day in window)
                       for key, window in TROPHY_WINDOWS.items()})
    edition_id = f"efl-trophy-{season_start_year}-{(season_start_year+1)%100:02d}"
    # Fictional north/south grouping: real geography is not modeled yet.
    # Each region has 24 senior clubs + eight U21 invitees.
    seniors = list((*league_one, *league_two))
    rng = Random(seed)
    rng.shuffle(seniors)
    groups: dict[str, tuple[str, ...]] = {}
    fixtures, dates = [], []
    for section, start in (("north", 0), ("south", 24)):
        for index in range(8):
            members = tuple(seniors[start + index * 3:start + index * 3 + 3])
            invited = f"dev-trophy-u21-{section}-{index + 1:02d}"
            group_id = f"{section}-{index + 1}"
            groups[group_id] = (*members, invited)
            # Three deterministic group matchdays; invited U21 is always away.
            pairings = (
                ((members[0], invited), (members[1], members[2])),
                ((members[1], invited), (members[2], members[0])),
                ((members[2], invited), (members[0], members[1])),
            )
            for r, matchups in enumerate(pairings, 1):
                for i, (home, away) in enumerate(matchups, 1):
                    fixtures.append(CompetitionFixture(
                        f"{edition_id}-{group_id}-md{r}-m{i}", edition_id,
                        "group-stage", home, away, round_number=r,
                    ))
                    dates.append(trophy_dates[r-1])
    return StagedWorldCompetition(
        competition_id="efl-trophy", name="EFL Trophy", season_label=f"{season_start_year}/{(season_start_year+1)%100:02d}",
        kind="efl-trophy", participants=tuple(c for g in groups.values() for c in g),
        primary_fixtures=tuple(fixtures), primary_dates=tuple(dates),
        knockout_windows=dict(knockout_dates), seed=seed, groups=groups,
        source_url=EFL_TROPHY_SOURCE if season_start_year == 2026 else "",
    )
