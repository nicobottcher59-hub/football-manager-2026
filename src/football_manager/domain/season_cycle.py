"""Phase 6.7: post-season sporting rules and persistent season history.

Only England's four professional tiers are simulated. National League is a
clearly identified external promotion boundary, not a fifth simulated league.
European access is a configurable policy; fictional foreign entrants are not
claimed to have qualified in real leagues.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any, Mapping

from .domestic_cups import DomesticCupRound, DomesticCupSeason
from .knockout import KnockoutLegFormat
from .match_context import MatchDecider

TIER_IDS = ("dev-premier", "dev-championship", "dev-league-one", "dev-league-two")
PLAYOFF_IDS = {"dev-championship": "championship-playoffs", "dev-league-one": "league-one-playoffs",
               "dev-league-two": "league-two-playoffs"}


@dataclass(frozen=True)
class EuropeanAccessPolicy:
    """Configurable English allocation, with configurable performance spot.

    Real UEFA access lists may change by season. The 2027/28 coefficients and
    special titleholder pathways are not assumed to be known in October 2026.
    """
    automatic_champions_league: int = 4
    performance_spot: bool = False
    automatic_europa_league: int = 1
    fa_cup_europa_league: bool = True
    carabao_conference_league: bool = True

    def __post_init__(self):
        if not 1 <= self.automatic_champions_league <= 6 or not 0 <= self.automatic_europa_league <= 3:
            raise ValueError("invalid European access allocation")


@dataclass(frozen=True)
class SeasonReport:
    season_label: str
    league_tables: dict[str, tuple[str, ...]]
    champions: dict[str, str]
    promoted: dict[str, tuple[str, ...]]
    relegated: dict[str, tuple[str, ...]]
    next_tiers: dict[str, tuple[str, ...]]
    europe: dict[str, tuple[str, ...]]
    external_national_league_promotions: tuple[str, ...]
    fixture_count: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "season_label": self.season_label,
            "league_tables": {k: list(v) for k, v in self.league_tables.items()},
            "champions": self.champions,
            "promoted": {k: list(v) for k, v in self.promoted.items()},
            "relegated": {k: list(v) for k, v in self.relegated.items()},
            "next_tiers": {k: list(v) for k, v in self.next_tiers.items()},
            "europe": {k: list(v) for k, v in self.europe.items()},
            "external_national_league_promotions": list(self.external_national_league_promotions),
            "fixture_count": self.fixture_count,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "SeasonReport":
        return cls(
            str(data["season_label"]),
            {str(k): tuple(v) for k, v in data["league_tables"].items()},
            dict(data["champions"]),
            {str(k): tuple(v) for k, v in data["promoted"].items()},
            {str(k): tuple(v) for k, v in data["relegated"].items()},
            {str(k): tuple(v) for k, v in data["next_tiers"].items()},
            {str(k): tuple(v) for k, v in data["europe"].items()},
            tuple(data["external_national_league_promotions"]),
            int(data["fixture_count"]),
        )


def create_efl_playoffs(league_id: str, standings: tuple[str, ...], season_start: int,
                        *, final_league_date: date | None = None) -> DomesticCupSeason:
    """Generated playoff windows; EFL has not published exact 2026/27 final dates.

    2026/27 Championship: six participants, 5v8 and 6v7 single-leg
    eliminators, 3rd/4th enter two-legged semifinals, then Wembley final.
    League One and League Two retain four-club, five-fixture playoffs.
    """
    if league_id not in PLAYOFF_IDS or len(standings) != 24 or len(set(standings)) != 24:
        raise ValueError("playoffs require a full unique EFL league table")
    end = final_league_date or date(season_start + 1, 5, 1 if league_id == "dev-championship" else 8)
    pen = MatchDecider.EXTRA_TIME_AND_PENALTIES
    if league_id == "dev-championship":
        rules = (
            DomesticCupRound("eliminator", "Playoff eliminators (5-8)", (end + timedelta(days=7),),
                             (standings[4], standings[7], standings[5], standings[6]), decider=pen),
            DomesticCupRound("semifinal", "Playoff semifinals", (end + timedelta(days=12), end + timedelta(days=19)),
                             (standings[2], standings[3]), KnockoutLegFormat.TWO_LEGGED, pen),
            DomesticCupRound("final", "Promotion playoff final", (end + timedelta(days=30),), decider=pen),
        )
    else:
        begin = 2 if league_id == "dev-league-one" else 3
        rules = (
            DomesticCupRound("semifinal", "Playoff semifinals", (end + timedelta(days=5), end + timedelta(days=12)),
                             (standings[begin+3], standings[begin],
                              standings[begin+2], standings[begin+1]), KnockoutLegFormat.TWO_LEGGED, pen),
            DomesticCupRound("final", "Promotion playoff final", (end + timedelta(days=22),), decider=pen),
        )
    return DomesticCupSeason(
        cup_id=PLAYOFF_IDS[league_id], name=f"{league_id.removeprefix('dev-').title()} Promotion Playoffs",
        season_label=f"{season_start}/{str(season_start + 1)[-2:]}", rounds=rules,
        draw_seed=season_start * 17 + len(league_id), pairing_strategy="promotion-playoffs",
        qualification_note="GENERATED DEV playoff windows, not confirmed EFL match kickoffs",
    )


def european_qualifiers(world: Any, tables: Mapping[str, tuple[str, ...]],
                        policy: EuropeanAccessPolicy = EuropeanAccessPolicy()) -> dict[str, tuple[str, ...]]:
    premier = tables[TIER_IDS[0]]
    english = set().union(*(set(tables[cid]) for cid in TIER_IDS))
    allocation: dict[str, list[str]] = {cid: [] for cid in
                                        ("champions-league", "europa-league", "conference-league")}
    assigned: set[str] = set()

    def add(club: str | None, competition: str) -> bool:
        if club not in english or club in assigned:
            return False
        allocation[competition].append(club)
        assigned.add(club)
        return True

    # UEFA winners are an independent qualification route. Their place does not
    # transfer to a league position if the winner was already qualified.
    for cid, target in (("champions-league", "champions-league"),
                        ("europa-league", "champions-league"),
                        ("conference-league", "europa-league")):
        add(world.staged[cid].champion_club_id, target)
    cl_limit = policy.automatic_champions_league + int(policy.performance_spot)
    for club in premier[:cl_limit]:
        add(club, "champions-league")

    def next_unallocated(target: str) -> None:
        for club in premier:
            if add(club, target):
                return
        raise ValueError("no English club available for European access")

    for _ in range(policy.automatic_europa_league):
        next_unallocated("europa-league")
    if policy.fa_cup_europa_league:
        if not add(world.cups["fa-cup"].champion_club_id, "europa-league"):
            next_unallocated("europa-league")
    if policy.carabao_conference_league:
        if not add(world.cups["carabao-cup"].champion_club_id, "conference-league"):
            next_unallocated("conference-league")
    return {key: tuple(clubs) for key, clubs in allocation.items()}


def finalize_season(world: Any, *, european_policy: EuropeanAccessPolicy = EuropeanAccessPolicy()) -> SeasonReport:
    """Fail closed on unfinished seasons; never invent promotion winners."""
    if set(world.results) != set(world.fixtures):
        raise ValueError("cannot finalize a season with unplayed fixtures")
    if set(world.leagues) != set(TIER_IDS):
        raise ValueError("season transition requires four English professional tiers")
    for playoff_id in PLAYOFF_IDS.values():
        if playoff_id not in world.cups or not world.cups[playoff_id].champion_club_id:
            raise ValueError(f"unfinished promotion playoffs: {playoff_id}")
    if any(not c.champion_club_id for c in world.cups.values()) or any(
            not c.champion_club_id for c in world.staged.values()):
        raise ValueError("cup or UEFA competitions are incomplete")
    tables = {cid: tuple(row.club_id for row in world.standings(cid)) for cid in TIER_IDS}
    champions = {cid: clubs[0] for cid, clubs in tables.items()}
    champions.update({cid: cup.champion_club_id for cid, cup in world.cups.items()})
    champions.update({cid: tournament.champion_club_id for cid, tournament in world.staged.items()})
    pchamp = world.cups["championship-playoffs"].champion_club_id
    pone = world.cups["league-one-playoffs"].champion_club_id
    ptwo = world.cups["league-two-playoffs"].champion_club_id
    promoted = {
        "dev-championship": (*tables["dev-championship"][:2], pchamp),
        "dev-league-one": (*tables["dev-league-one"][:2], pone),
        "dev-league-two": (*tables["dev-league-two"][:3], ptwo),
    }
    relegated = {
        "dev-premier": tables["dev-premier"][-3:],
        "dev-championship": tables["dev-championship"][-3:],
        "dev-league-one": tables["dev-league-one"][-4:],
        "dev-league-two": tables["dev-league-two"][-2:],
    }
    year = int(world.season_label[:4]) + 1
    # Explicit external boundary. No phantom National League standings are
    # fabricated, and relegated L2 clubs leave the simulated 92-club pyramid.
    incoming = (f"dev-national-promotion-{year}-01", f"dev-national-promotion-{year}-02")
    nxt = {
        "dev-premier": (*tables["dev-premier"][:-3], *promoted["dev-championship"]),
        "dev-championship": (*tuple(c for c in tables["dev-championship"] if c not in promoted["dev-championship"]
                                   and c not in relegated["dev-championship"]),
                             *relegated["dev-premier"], *promoted["dev-league-one"]),
        "dev-league-one": (*tuple(c for c in tables["dev-league-one"] if c not in promoted["dev-league-one"]
                               and c not in relegated["dev-league-one"]),
                           *relegated["dev-championship"], *promoted["dev-league-two"]),
        "dev-league-two": (*tuple(c for c in tables["dev-league-two"] if c not in promoted["dev-league-two"]
                               and c not in relegated["dev-league-two"]),
                           *relegated["dev-league-one"], *incoming),
    }
    if tuple(map(len, nxt.values())) != (20, 24, 24, 24) or len(set().union(*(set(v) for v in nxt.values()))) != 92:
        raise ValueError("season transition changed league sizes or duplicated a club")
    return SeasonReport(world.season_label, tables, champions, promoted, relegated,
                        nxt, european_qualifiers(world, tables, european_policy), incoming,
                        len(world.results))
