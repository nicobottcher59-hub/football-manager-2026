"""Season-scoped mixed league/group/knockout cups for the world runner.

Published *round windows* are separate from GENERATED fictional draws and clubs.
This model reuses LeagueResult/build_league_table and the existing knockout engine.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import date
from random import Random
from typing import Any, Mapping, Sequence

from .competition import CompetitionFixture
from .knockout import (
    KnockoutDrawSource, KnockoutLegFormat, KnockoutMatchResult, KnockoutRoundDefinition,
    KnockoutRoundPlan, generate_knockout_round, resolve_knockout_round,
    seed_knockout_round,
)
from .league import LeagueResult, LeagueStandingRow, build_league_table
from .match_context import MatchDecider


@dataclass(slots=True)
class StagedWorldCompetition:
    competition_id: str
    name: str
    season_label: str
    kind: str  # 'uefa' or 'efl-trophy'
    participants: tuple[str, ...]
    primary_fixtures: tuple[CompetitionFixture, ...]
    primary_dates: tuple[date, ...]
    knockout_windows: dict[str, tuple[date, ...]]
    seed: int
    groups: dict[str, tuple[str, ...]] = field(default_factory=dict)
    source_url: str = ""
    knockout_plans: list[KnockoutRoundPlan] = field(default_factory=list)
    champion_club_id: str | None = None
    direct_qualifiers: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.kind not in ("uefa", "efl-trophy"):
            raise ValueError("invalid staged format")
        expected = 36 if self.kind == "uefa" else 64
        if len(self.participants) != expected or len(set(self.participants)) != expected:
            raise ValueError("staged competition requires its exact unique participant count")
        if self.kind == "uefa" and self.groups:
            raise ValueError("UEFA league phase does not use groups")
        if self.kind == "efl-trophy":
            if len(self.groups) != 16 or any(len(v) != 4 for v in self.groups.values()):
                raise ValueError("EFL Trophy needs 16 groups of four")
            if sorted(c for group in self.groups.values() for c in group) != sorted(self.participants):
                raise ValueError("EFL Trophy group entrants do not match participants")
        if len({f.fixture_id for f in self.primary_fixtures}) != len(self.primary_fixtures):
            raise ValueError("duplicate league-phase fixture")
        if len(self.primary_fixtures) != len(self.primary_dates):
            raise ValueError("primary dates must cover every primary fixture")
        for f in self.primary_fixtures:
            if f.home_club_id == f.away_club_id or not {f.home_club_id, f.away_club_id}.issubset(self.participants):
                raise ValueError("invalid staged fixture participants")

    @property
    def edition_id(self) -> str:
        return f"{self.competition_id}-{self.season_label.replace('/', '-')}"

    @property
    def primary_stage_id(self) -> str:
        return "league-phase" if self.kind == "uefa" else "group-stage"

    @property
    def rounds(self) -> tuple[str, ...]:
        if self.kind == "uefa":
            return ("playoff", "r16", "qf", "sf", "final")
        return ("r32", "r16", "qf", "sf", "final")

    def plan_for_fixture(self, fixture_id: str) -> KnockoutRoundPlan:
        for plan in self.knockout_plans:
            if any(f.fixture_id == fixture_id for f in plan.fixtures):
                return plan
        raise KeyError(f"unknown staged knockout fixture {fixture_id}")

    def _primary_results(self, results: Mapping[str, Any]) -> tuple[LeagueResult, ...]:
        return tuple(
            LeagueResult(f.fixture_id, results[f.fixture_id].home_goals, results[f.fixture_id].away_goals)
            for f in self.primary_fixtures if f.fixture_id in results
        )

    def standings(self, results: Mapping[str, Any], group_id: str | None = None) -> tuple[LeagueStandingRow, ...]:
        if group_id is not None:
            if group_id not in self.groups:
                raise KeyError(group_id)
            members = self.groups[group_id]
            fixtures = tuple(f for f in self.primary_fixtures if f.home_club_id in members)
        else:
            members = self.participants
            fixtures = self.primary_fixtures
        if self.kind == "efl-trophy":
            return trophy_group_table(members, fixtures, results)
        return build_league_table(
            participant_club_ids=members, fixtures=fixtures,
            results=self._primary_results(results),
        )

    def _append_plan(self, stage: str, pairings: Sequence[tuple[str, str]]) -> KnockoutRoundPlan:
        index = self.rounds.index(stage)
        final = stage == "final"
        definition = KnockoutRoundDefinition(
            stage, stage.upper().replace("R", "Round of ") if stage.startswith("r") else stage.title(),
            index + 1,
            KnockoutLegFormat.TWO_LEGGED if self.kind == "uefa" and not final else KnockoutLegFormat.SINGLE_LEG,
            MatchDecider.EXTRA_TIME_AND_PENALTIES if self.kind == "uefa" or final else MatchDecider.PENALTIES_AFTER_90,
        )
        # The pairs reflect known sporting progression from earlier results, not an official real-world draw.
        plan = seed_knockout_round(
            edition_id=self.edition_id, stage_id=stage, definition=definition, pairings=pairings,
        )
        plan = replace(plan, source=KnockoutDrawSource.GENERATED)
        self.knockout_plans.append(plan)
        return plan

    @staticmethod
    def _pairs(clubs: Sequence[str], seed: int) -> list[tuple[str, str]]:
        shuffled = list(clubs)
        Random(seed).shuffle(shuffled)
        if len(shuffled) % 2:
            raise ValueError("knockout stage requires even number of clubs")
        return [(shuffled[i], shuffled[i + 1]) for i in range(0, len(shuffled), 2)]

    def after_result(self, results: Mapping[str, Any]) -> KnockoutRoundPlan | None:
        """Return a new drawn round once its predecessor becomes fully decided."""
        if self.champion_club_id:
            return None
        if not self.knockout_plans:
            if any(f.fixture_id not in results for f in self.primary_fixtures):
                return None
            if self.kind == "uefa":
                standing = self.standings(results)
                self.direct_qualifiers = tuple(row.club_id for row in standing[:8])
                middle = [row.club_id for row in standing[8:24]]
                # A seeded 9-24 playoff skeleton. UEFA's protected bracket lanes and
                # country restrictions can be supplied by a future draw importer.
                pairs = [(middle[i], middle[-1-i]) for i in range(8)]
                return self._append_plan("playoff", pairs)
            top = {key: self.standings(results, key)[:2] for key in self.groups}
            pairs = []
            for section in ("north", "south"):
                keys = [f"{section}-{i}" for i in range(1, 9)]
                for i, key in enumerate(keys):
                    pairs.append((top[key][0].club_id, top[keys[(i + 1) % 8]][1].club_id))
            return self._append_plan("r32", pairs)
        current = self.knockout_plans[-1]
        outcome = resolve_knockout_round(
            current,
            tuple(results[f.fixture_id].knockout_result() for f in current.fixtures if f.fixture_id in results),
        )
        if not outcome.complete:
            return None
        if current.definition.round_id == "final":
            self.champion_club_id = outcome.winner_club_ids[0]
            return None
        winners = outcome.winner_club_ids
        next_id = self.rounds[len(self.knockout_plans)]
        if self.kind == "uefa" and current.definition.round_id == "playoff":
            # Put each playoff survivor alongside a directly qualified club.
            pairings = list(zip(self.direct_qualifiers, winners))
        elif self.kind == "efl-trophy" and current.definition.round_id in ("r32", "r16"):
            # Regionalised until the QF. Winners are still in north/south tie order.
            half = len(winners) // 2
            pairings = self._pairs(winners[:half], self.seed + len(self.knockout_plans))
            pairings += self._pairs(winners[half:], self.seed + 50 + len(self.knockout_plans))
        else:
            pairings = self._pairs(winners, self.seed + 100 * len(self.knockout_plans))
        return self._append_plan(next_id, pairings)

    def to_dict(self) -> dict[str, Any]:
        return {
            "competition_id": self.competition_id, "name": self.name,
            "season_label": self.season_label, "kind": self.kind,
            "participants": list(self.participants),
            "primary_fixtures": [f.to_dict() for f in self.primary_fixtures],
            "primary_dates": [d.isoformat() for d in self.primary_dates],
            "knockout_windows": {k: [d.isoformat() for d in v] for k, v in self.knockout_windows.items()},
            "seed": self.seed, "groups": {k: list(v) for k, v in self.groups.items()},
            "source_url": self.source_url, "direct_qualifiers": list(self.direct_qualifiers),
            "champion_club_id": self.champion_club_id,
            "knockout_plans": [
                {"stage": p.definition.round_id, "pairings": [[t.club_a_id, t.club_b_id] for t in p.ties]}
                for p in self.knockout_plans
            ],
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "StagedWorldCompetition":
        instance = cls(
            competition_id=str(data["competition_id"]), name=str(data["name"]),
            season_label=str(data["season_label"]), kind=str(data["kind"]),
            participants=tuple(str(c) for c in data["participants"]),
            primary_fixtures=tuple(CompetitionFixture.from_dict(f) for f in data["primary_fixtures"]),
            primary_dates=tuple(date.fromisoformat(v) for v in data["primary_dates"]),
            knockout_windows={k: tuple(date.fromisoformat(v) for v in vals) for k, vals in data["knockout_windows"].items()},
            seed=int(data["seed"]), groups={k: tuple(v) for k, v in data.get("groups", {}).items()},
            source_url=str(data.get("source_url", "")),
        )
        plans = list(data.get("knockout_plans", ()))
        if len(plans) > len(instance.rounds):
            raise ValueError("too many persisted knockout stages")
        for i, item in enumerate(plans):
            if item["stage"] != instance.rounds[i]:
                raise ValueError("persisted staged rounds out of sequence")
            instance._append_plan(item["stage"], tuple(tuple(p) for p in item["pairings"]))
        instance.direct_qualifiers = tuple(data.get("direct_qualifiers", ()))
        instance.champion_club_id = data.get("champion_club_id")
        if instance.champion_club_id and (not plans or plans[-1]["stage"] != "final"):
            raise ValueError("staged champion requires a final")
        return instance


def trophy_group_table(
    members: Sequence[str], fixtures: Sequence[CompetitionFixture], results: Mapping[str, Any],
) -> tuple[LeagueStandingRow, ...]:
    """EFL Trophy 3/2/1/0 group points; shootout winner gets an extra point."""
    stats = {c: {"played": 0, "won": 0, "drawn": 0, "lost": 0, "goals_for": 0,
                 "goals_against": 0, "points": 0} for c in members}
    for fixture in fixtures:
        if fixture.fixture_id not in results:
            continue
        result = results[fixture.fixture_id]
        home, away = stats[fixture.home_club_id], stats[fixture.away_club_id]
        home["played"] += 1
        away["played"] += 1
        home["goals_for"] += result.home_goals
        away["goals_for"] += result.away_goals
        home["goals_against"] += result.away_goals
        away["goals_against"] += result.home_goals
        if result.home_goals > result.away_goals:
            home["won"] += 1; away["lost"] += 1; home["points"] += 3
        elif result.home_goals < result.away_goals:
            away["won"] += 1; home["lost"] += 1; away["points"] += 3
        else:
            if result.penalties_home == result.penalties_away:
                raise ValueError("drawn EFL Trophy group result must contain a decided shootout")
            home["drawn"] += 1; away["drawn"] += 1
            home["points"] += 1 + (result.penalties_home > result.penalties_away)
            away["points"] += 1 + (result.penalties_away > result.penalties_home)
    sorted_clubs = sorted(
        members, key=lambda c: (-stats[c]["points"],
                                -(stats[c]["goals_for"] - stats[c]["goals_against"]),
                                -stats[c]["goals_for"], c),
    )
    return tuple(LeagueStandingRow(i, c, **stats[c]) for i, c in enumerate(sorted_clubs, 1))
