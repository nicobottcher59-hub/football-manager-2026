"""2026/27 English domestic cup *round rules/dates* for fictional clubs.

Official calendars are referenced below; fictitious draws are GENERATED.
The first five FA Cup qualifying rounds are represented by their published
windows only. The playable qualifying model begins at Q4 with 64 fictional
non-league clubs competing for the 32 first-round-proper berths.
"""
from __future__ import annotations

from datetime import date
from typing import Mapping, Sequence

from football_manager.domain.domestic_cups import DomesticCupRound, DomesticCupSeason
from football_manager.domain.knockout import KnockoutLegFormat
from football_manager.domain.match_context import MatchDecider

FA_DATES_SOURCE = "https://www.thefa.com/competitions/thefacup/round-dates"
CARABAO_DATES_SOURCE = "https://www.efl.com/competitions/key-dates/"
CARABAO_FORMAT_SOURCE = "https://www.efl.com/news/2026/august/06/carabao-cup-2026-27---key-information-/"

FA_EARLY_QUALIFYING_DATES = (
    ("extra-preliminary", date(2026, 8, 8)),
    ("preliminary", date(2026, 8, 22)),
    ("qualifying-1", date(2026, 9, 5)),
    ("qualifying-2", date(2026, 9, 19)),
    ("qualifying-3", date(2026, 10, 3)),
)


def _day(value: str) -> date:
    return date.fromisoformat(value)


def build_fa_cup_2026_27(
    league_clubs: Mapping[int, Sequence[str]], *, seed: int = 6540,
) -> DomesticCupSeason:
    if tuple(sorted(league_clubs)) != (1, 2, 3, 4):
        raise ValueError("FA Cup requires four English professional tiers")
    if tuple(len(league_clubs[t]) for t in (1, 2, 3, 4)) != (20, 24, 24, 24):
        raise ValueError("FA Cup requires 20/24/24/24 professional clubs")
    league_one_two = (*league_clubs[3], *league_clubs[4])
    premier_champ = (*league_clubs[1], *league_clubs[2])
    qualifying = tuple(f"dev-nonleague-{index:03d}" for index in range(1, 65))
    early = tuple(DomesticCupRound(round_id, label, (_day(day),), entrants) for round_id, label, day, entrants in (
        ("qualifying-4", "Fourth qualifying round", "2026-10-17", qualifying),
        ("proper-1", "First round proper", "2026-11-07", league_one_two),
        ("proper-2", "Second round proper", "2026-12-05", ()),
        ("proper-3", "Third round proper", "2027-01-09", premier_champ),
        ("proper-4", "Fourth round proper", "2027-02-13", ()),
        ("proper-5", "Fifth round proper", "2027-03-06", ()),
        ("quarterfinal", "Quarter-finals", "2027-04-03", ()),
        ("semifinal", "Semi-finals", "2027-04-24", ()),
        ("final", "Final", "2027-05-22", ()),
    ))
    return DomesticCupSeason(
        cup_id="fa-cup", name="FA Cup (fictional clubs)", season_label="2026/27",
        rounds=early, draw_seed=seed, source_url=FA_DATES_SOURCE,
        qualification_note="Q1-Q3 and earlier: published windows only; Q4 starts with 64 fictional qualifiers",
    )


def build_carabao_cup_2026_27(
    league_clubs: Mapping[int, Sequence[str]], *, european_entrant_ids: Sequence[str],
    seed: int = 6550,
) -> DomesticCupSeason:
    if tuple(sorted(league_clubs)) != (1, 2, 3, 4):
        raise ValueError("Carabao Cup requires four English professional tiers")
    if tuple(len(league_clubs[t]) for t in (1, 2, 3, 4)) != (20, 24, 24, 24):
        raise ValueError("Carabao Cup requires 20/24/24/24 professional clubs")
    premier = tuple(league_clubs[1])
    european = tuple(european_entrant_ids)
    if len(european) != 9 or len(set(european)) != 9 or not set(european).issubset(premier):
        raise ValueError("2026/27 Carabao requires nine designated Premier European entrants")
    other_premier = tuple(club for club in premier if club not in european)
    efl = (*league_clubs[2], *league_clubs[3], *league_clubs[4])
    # Four fictional EFL clubs form two preliminary ties; 68 remain in R1.
    preliminary = (league_clubs[4][0], league_clubs[4][1], league_clubs[4][2], league_clubs[4][3])
    round_one = tuple(club for club in efl if club not in preliminary)
    pen90 = MatchDecider.PENALTIES_AFTER_90
    rules = (
        DomesticCupRound("preliminary", "Preliminary round", (_day("2026-08-01"), _day("2026-08-03")), preliminary, decider=pen90),
        DomesticCupRound("round-1", "Round One", (_day("2026-08-07"), _day("2026-08-08"), _day("2026-08-09")), round_one, decider=pen90),
        DomesticCupRound("round-2", "Round Two", (_day("2026-08-25"), _day("2026-08-26")), other_premier, decider=pen90),
        DomesticCupRound("round-3", "Round Three", (_day("2026-09-08"), _day("2026-09-09"), _day("2026-09-15"), _day("2026-09-16")), european, decider=pen90),
        DomesticCupRound("round-4", "Round Four", (_day("2026-10-27"), _day("2026-10-28")), (), decider=pen90),
        DomesticCupRound("round-5", "Quarter-finals", (_day("2026-12-15"), _day("2026-12-16")), (), decider=pen90),
        DomesticCupRound("semifinal", "Semi-finals", (_day("2027-01-12"), _day("2027-02-02")), (), leg_format=KnockoutLegFormat.TWO_LEGGED),
        DomesticCupRound("final", "Final", (_day("2027-03-21"),)),
    )
    return DomesticCupSeason(
        cup_id="carabao-cup", name="Carabao Cup (fictional clubs)", season_label="2026/27",
        rounds=rules, draw_seed=seed, source_url=CARABAO_DATES_SOURCE,
        qualification_note="Fictional European-entry selection; 2026/27 format has nine European entrants",
    )
