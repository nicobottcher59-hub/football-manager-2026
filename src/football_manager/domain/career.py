"""Phase 6.7 career-level results archive and generated next-season world.

Deliberately not a full manager save: tactical/player state still belongs to a
future complete career save model. English 2027+ calendars are GENERATED.
"""
from __future__ import annotations

from dataclasses import asdict
from datetime import date
import json
import os
from pathlib import Path
import tempfile
from typing import Any, Mapping
from dataclasses import dataclass

from football_manager.data.efl_2026_27 import tier_strength
from football_manager.data.future_seasons import generated_cups, generated_edition
from football_manager.data.staged_2026_27 import build_uefa_2026_27, build_efl_trophy_2026_27
from football_manager.domain.international_calendar import build_international_calendar
from .season_cycle import TIER_IDS, PLAYOFF_IDS, EuropeanAccessPolicy, SeasonReport, finalize_season
from .career_transition import CareerSeasonTransition
from .world_runner import WorldSeasonRunner


def next_season_world(previous: WorldSeasonRunner, report: SeasonReport,
                      names: dict[str, str]) -> WorldSeasonRunner:
    """Generate a new season with distinct fixture IDs, new participants and dates."""
    year = int(report.season_label[:4]) + 1
    season_label = f"{year}/{(year+1)%100:02d}"
    world = WorldSeasonRunner(
        season_label=season_label, seed=previous.seed + 13,
        international_calendar=build_international_calendar(year, year + 1),
    )
    tiers: dict[int, tuple[str, ...]] = {}
    for tier, cid in enumerate(TIER_IDS, 1):
        participants = report.next_tiers[cid]
        tiers[tier] = participants
        edition, schedule = generated_edition(previous.leagues[cid], participants, year,
                                             seed=world.seed + tier*31)
        strengths = {}
        for index, club in enumerate(participants):
            target = tier_strength(tier, index)
            prior = previous.strengths.get(club, target)
            # Evolved strength follows promotion/relegation without wiping
            # accumulated club identity or granting an instant elite rating.
            strengths[club] = max(24, min(92, round(target*.6 + prior*.4)))
            if club not in names:
                names[club] = f"National League Promotion {year} #{int(club.rsplit('-', 1)[-1])}"
        world.register_league(edition, schedule, strengths)
    world.configure_promotion_playoffs(TIER_IDS[1:])
    nonleague = {f"dev-nonleague-{i:03d}": max(20, 32 + ((i*7)%10)-5)
                 for i in range(1, 65)}
    for cid in nonleague:
        names.setdefault(cid, f"Non-League {int(cid[-3:]):02d}")
    english_europeans = tuple(c for group in report.europe.values() for c in group)
    for cup in generated_cups(tiers, english_europeans, year, seed=world.seed + 34):
        world.register_cup(cup, strengths=nonleague if cup.cup_id == "fa-cup" else {})
    for cid, base_strength in (("champions-league", 79), ("europa-league", 74),
                               ("conference-league", 69)):
        english = report.europe[cid]
        if len(english) > 36:
            raise ValueError("English allocation exceeds UEFA field")
        foreign = tuple(f"dev-{cid}-foreign-{i:02d}" for i in range(1, 37-len(english)))
        for index, club in enumerate(foreign):
            names.setdefault(club, f"{cid.replace('-', ' ').title()} Visitor {index+1:02d}")
        world.register_staged(
            build_uefa_2026_27(cid, (*english, *foreign), seed=world.seed + len(cid),
                               season_start_year=year),
            strengths={c: previous.strengths.get(c, base_strength + ((i*7)%17)-8)
                       for i, c in enumerate(foreign)},
        )
    trophy = build_efl_trophy_2026_27(tiers[3], tiers[4],
                                      seed=world.seed+70, season_start_year=year)
    youth = {c: previous.strengths.get(c, 46 + (i*5)%17)
             for i, c in enumerate(trophy.participants) if "-u21-" in c}
    for club in youth:
        names.setdefault(club, "Academy " + club.split("-u21-")[-1].upper() + " U21")
    world.register_staged(trophy, strengths=youth)
    from .calendar_planner import repair_generated_calendar
    repair_generated_calendar(world)
    # There must be no direct duplication of sporting fixture IDs between years.
    if set(world.fixtures) & set(previous.fixtures):
        raise RuntimeError("new season duplicated previous fixture IDs")
    return world


@dataclass(frozen=True)
class EnglishCareerTransition:
    """Default England 4-tier rules, isolated behind the career transition contract."""

    transition_id: str = "england-pyramid-v1"

    def finish(self, world: WorldSeasonRunner, *, european_policy: EuropeanAccessPolicy) -> SeasonReport:
        return finalize_season(world, european_policy=european_policy)

    def build_next(self, previous: WorldSeasonRunner, report: SeasonReport,
                   names: dict[str, str]) -> WorldSeasonRunner:
        return next_season_world(previous, report, names)


ENGLISH_CAREER_TRANSITION = EnglishCareerTransition()


def _validate_career_link(previous: WorldSeasonRunner, report: SeasonReport,
                          following: WorldSeasonRunner, *, england: bool) -> None:
    if previous.season_label != report.season_label:
        raise ValueError("career season report labels do not match")
    if previous.season_label == following.season_label:
        raise ValueError("career transition did not advance to another season")
    if set(previous.fixtures).intersection(following.fixtures):
        raise ValueError("career transition reused a fixture ID across seasons")
    if any(cid not in following.leagues
           or tuple(following.leagues[cid].participant_club_ids) != participants
           for cid, participants in report.next_tiers.items()):
        raise ValueError("next-season promotion/relegation roster mismatch")
    if england and set(report.next_tiers) != set(TIER_IDS):
        raise ValueError("English career missing a professional tier")


class WorldCareer:
    """World history orchestrator independent of national transition logic.

    The default transition is the existing four-tier England implementation.
    New transitions must be explicitly registered for archive loading, avoiding
    silent interpretation of a foreign world as England.
    """
    SCHEMA_VERSION = 1

    def __init__(self, opening_world: WorldSeasonRunner, club_names: Mapping[str, str],
                 *, european_policy: EuropeanAccessPolicy | None = None,
                 transition: CareerSeasonTransition | None = None) -> None:
        self.worlds = [opening_world]
        self.reports: list[SeasonReport] = []
        self.club_names = dict(club_names)
        self.european_policy = european_policy or EuropeanAccessPolicy()
        self.transition = transition or ENGLISH_CAREER_TRANSITION
        if not isinstance(self.transition.transition_id, str) or not self.transition.transition_id.strip():
            raise ValueError("career transition requires a stable nonempty identifier")
        if (self.transition.transition_id == ENGLISH_CAREER_TRANSITION.transition_id
                and self.transition != ENGLISH_CAREER_TRANSITION):
            raise ValueError("cannot override the built-in England transition")

    @property
    def current(self) -> WorldSeasonRunner:
        return self.worlds[-1]

    def begin_next_season(self) -> SeasonReport:
        report = self.transition.finish(self.current, european_policy=self.european_policy)
        # Season builders may discover external clubs. Do not retain new names
        # if generation fails; committing a season is one career-level change.
        updated_names = dict(self.club_names)
        next_world = self.transition.build_next(self.current, report, updated_names)
        _validate_career_link(
            self.current, report, next_world,
            england=self.transition.transition_id == ENGLISH_CAREER_TRANSITION.transition_id,
        )
        self.reports.append(report)
        self.worlds.append(next_world)
        self.club_names = updated_names
        return report

    def to_dict(self) -> dict[str, Any]:
        return {"schema_version": self.SCHEMA_VERSION,
                "transition_id": self.transition.transition_id,
                "worlds": [world.to_dict() for world in self.worlds],
                "reports": [report.to_dict() for report in self.reports],
                "club_names": self.club_names, "european_policy": asdict(self.european_policy)}

    @classmethod
    def from_dict(cls, data: Mapping[str, Any], *,
                  transitions: Mapping[str, CareerSeasonTransition] | None = None) -> "WorldCareer":
        if data.get("schema_version") != cls.SCHEMA_VERSION:
            raise ValueError("unsupported career results archive version")
        selected = str(data.get("transition_id", ENGLISH_CAREER_TRANSITION.transition_id))
        available: dict[str, CareerSeasonTransition] = {
            ENGLISH_CAREER_TRANSITION.transition_id: ENGLISH_CAREER_TRANSITION,
        }
        for key, value in (transitions or {}).items():
            if key != value.transition_id or key in available:
                raise ValueError("career transition registration ID mismatch or reserved ID")
            available[key] = value
        if selected not in available:
            raise ValueError(f"unknown career transition: {selected}")
        worlds = [WorldSeasonRunner.from_dict(w) for w in data["worlds"]]
        reports = [SeasonReport.from_dict(r) for r in data["reports"]]
        if not worlds or len(worlds) != len(reports) + 1:
            raise ValueError("career results timeline is incomplete")
        for i, report in enumerate(reports):
            _validate_career_link(
                worlds[i], report, worlds[i + 1],
                england=selected == ENGLISH_CAREER_TRANSITION.transition_id,
            )
            if set(worlds[i].results) != set(worlds[i].fixtures):
                raise ValueError("archived world has unfinished fixtures")
        if len({w.season_label for w in worlds}) != len(worlds):
            raise ValueError("duplicate season in career archive")
        career = cls(worlds[0], data["club_names"],
                     european_policy=EuropeanAccessPolicy(**data.get("european_policy", {})),
                     transition=available[selected])
        career.worlds = worlds
        career.reports = reports
        return career

    def validate_integrity(self) -> None:
        """Validate the entire career before writing a results-only archive.

        All worlds must meet the same integrity rules as standalone world
        saves; validating only on load could create an unreadable archive.
        """
        if not self.worlds or len(self.worlds) != len(self.reports) + 1:
            raise ValueError("career results timeline is incomplete")
        if len({world.season_label for world in self.worlds}) != len(self.worlds):
            raise ValueError("duplicate season in career archive")
        for world in self.worlds:
            world.validate_integrity()
        for index, report in enumerate(self.reports):
            _validate_career_link(
                self.worlds[index], report, self.worlds[index + 1],
                england=self.transition.transition_id == ENGLISH_CAREER_TRANSITION.transition_id,
            )
            if set(self.worlds[index].results) != set(self.worlds[index].fixtures):
                raise ValueError("archived world has unfinished fixtures")

    def save_json(self, destination: str | Path) -> None:
        """Atomic, integrity-checked archive; excludes squad/player state."""
        self.validate_integrity()
        path = Path(destination)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp_name = None
        try:
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", prefix=path.name+".",
                                             suffix=".tmp", dir=path.parent, delete=False) as f:
                json.dump(self.to_dict(), f, sort_keys=True, indent=2, allow_nan=False)
                temp_name = f.name
            os.replace(temp_name, path)
        finally:
            if temp_name and os.path.exists(temp_name):
                os.unlink(temp_name)

    @classmethod
    def load_json(cls, source: str | Path, *,
                  transitions: Mapping[str, CareerSeasonTransition] | None = None) -> "WorldCareer":
        with Path(source).open("r", encoding="utf-8") as f:
            return cls.from_dict(json.load(f), transitions=transitions)
