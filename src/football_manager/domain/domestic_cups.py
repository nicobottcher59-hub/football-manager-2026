"""Domestic knockout cup season specification and staged entry/progression.

Sporting draws are GENERATED for fictional clubs.  The published 2026/27
round dates are data, not claims that fictional pairings are official draws.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import date
from typing import Any, Mapping, Sequence

from .knockout import (
    KnockoutDrawSource, KnockoutLegFormat, KnockoutMatchResult,
    KnockoutRoundDefinition, KnockoutRoundPlan, generate_knockout_round,
    resolve_knockout_round, seed_knockout_round,
)
from .match_context import MatchDecider


@dataclass(frozen=True, slots=True)
class DomesticCupRound:
    round_id: str
    label: str
    dates: tuple[date, ...]
    entrants: tuple[str, ...] = ()
    leg_format: KnockoutLegFormat = KnockoutLegFormat.SINGLE_LEG
    decider: MatchDecider = MatchDecider.EXTRA_TIME_AND_PENALTIES

    def __post_init__(self) -> None:
        if not self.round_id or not self.label or not self.dates:
            raise ValueError("cup round requires ID, name and dates")
        if len(self.dates) not in (1, 2, 3, 4):
            raise ValueError("cup round requires 1..4 window dates")
        if len(set(self.entrants)) != len(self.entrants):
            raise ValueError("round entrants must be unique")
        if self.leg_format is KnockoutLegFormat.TWO_LEGGED and len(self.dates) < 2:
            raise ValueError("two-legged round requires distinct leg dates")
        if self.decider is MatchDecider.DRAW_ALLOWED:
            raise ValueError("cup round must decide a winner")

    def to_dict(self) -> dict[str, Any]:
        return {
            "round_id": self.round_id, "label": self.label,
            "dates": [day.isoformat() for day in self.dates],
            "entrants": list(self.entrants),
            "leg_format": self.leg_format.value, "decider": self.decider.value,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "DomesticCupRound":
        return cls(
            round_id=str(value["round_id"]), label=str(value["label"]),
            dates=tuple(date.fromisoformat(str(day)) for day in value["dates"]),
            entrants=tuple(str(x) for x in value["entrants"]),
            leg_format=KnockoutLegFormat(value["leg_format"]),
            decider=MatchDecider(value["decider"]),
        )


@dataclass(slots=True)
class DomesticCupSeason:
    cup_id: str
    name: str
    season_label: str
    rounds: tuple[DomesticCupRound, ...]
    draw_seed: int = 6600
    source_url: str = ""
    qualification_note: str = ""
    pairing_strategy: str = "generated"
    plans: list[KnockoutRoundPlan] = field(default_factory=list)
    champion_club_id: str | None = None

    def __post_init__(self) -> None:
        if not self.cup_id or not self.name or not self.season_label:
            raise ValueError("cup season needs identifiers and name")
        if self.pairing_strategy not in ("generated", "promotion-playoffs"):
            raise ValueError("unknown cup pairing strategy")
        if not self.rounds or len({rule.round_id for rule in self.rounds}) != len(self.rounds):
            raise ValueError("cup rounds must be nonempty with unique IDs")
        if any(max(a.dates) >= min(b.dates) for a, b in zip(self.rounds, self.rounds[1:])):
            raise ValueError("cup rounds must be in chronological order")
        all_entrants = [club for rule in self.rounds for club in rule.entrants]
        if len(set(all_entrants)) != len(all_entrants):
            raise ValueError("cup club may enter only once")

    @property
    def edition_id(self) -> str:
        return f"{self.cup_id}-{self.season_label.replace('/', '-')}"

    @property
    def current_round(self) -> DomesticCupRound:
        return self.rounds[len(self.plans) - 1] if self.plans else self.rounds[0]

    @property
    def current_plan(self) -> KnockoutRoundPlan | None:
        return self.plans[-1] if self.plans else None

    def start(self) -> KnockoutRoundPlan:
        if self.plans:
            return self.plans[0]
        self._append_plan(self.rounds[0].entrants, 0)
        return self.plans[0]

    def _append_plan(self, participants: Sequence[str], index: int) -> KnockoutRoundPlan:
        rule = self.rounds[index]
        if len(participants) % 2 or len(participants) < 2:
            raise ValueError(f"{self.cup_id}/{rule.round_id}: invalid participant count")
        definition = KnockoutRoundDefinition(
            round_id=rule.round_id, name=rule.label, order=index + 1,
            leg_format=rule.leg_format,
            deciding_match_decider=rule.decider,
        )
        if self.pairing_strategy == "promotion-playoffs":
            # EFL seeding, not an unrestricted random draw. Higher seeds host
            # the second semifinal leg. Championship eliminates 5v8/6v7 first.
            if self.cup_id == "championship-playoffs" and index == 1:
                # 2026/27 EFL: third faces the *lowest-ranked remaining*
                # eliminator winner, fourth faces the other one. Eliminator
                # winners arrive in bracket order, not necessarily seed order.
                eliminator_seed = {
                    club: rank for club, rank in zip(self.rounds[0].entrants, (5, 8, 6, 7))
                }
                winner_a, winner_b, third, fourth = participants
                if winner_a not in eliminator_seed or winner_b not in eliminator_seed:
                    raise ValueError("Championship eliminator winner is not a seeded qualifier")
                low, high = sorted((winner_a, winner_b),
                                   key=lambda club: eliminator_seed[club], reverse=True)
                # Club B hosts leg two, so third/fourth get the higher-seed
                # second-leg home advantage.
                pairings = ((low, third), (high, fourth))
            else:
                pairings = tuple((participants[i], participants[i+1])
                                 for i in range(0, len(participants), 2))
            plan = replace(seed_knockout_round(
                edition_id=self.edition_id, stage_id=rule.round_id,
                definition=definition, pairings=pairings,
            ), source=KnockoutDrawSource.GENERATED)
        else:
            plan = generate_knockout_round(
                edition_id=self.edition_id, stage_id=rule.round_id,
                definition=definition, participant_club_ids=tuple(participants),
                seed=self.draw_seed + 1009 * index,
            )
        self.plans.append(plan)
        return plan

    def after_results(self, results: Mapping[str, KnockoutMatchResult]) -> KnockoutRoundPlan | None:
        """Advance only when every tie in the current round has a winner."""
        if not self.plans or self.champion_club_id:
            return None
        current = self.plans[-1]
        completed = resolve_knockout_round(
            current, tuple(results[f.fixture_id] for f in current.fixtures if f.fixture_id in results),
        )
        if not completed.complete:
            return None
        if len(self.plans) == len(self.rounds):
            if len(completed.winner_club_ids) != 1:
                raise ValueError("final round must have exactly one winner")
            self.champion_club_id = completed.winner_club_ids[0]
            return None
        index = len(self.plans)
        participants = (*completed.winner_club_ids, *self.rounds[index].entrants)
        return self._append_plan(participants, index)

    def rule_for_fixture(self, fixture_id: str) -> DomesticCupRound:
        for index, plan in enumerate(self.plans):
            if any(f.fixture_id == fixture_id for f in plan.fixtures):
                return self.rounds[index]
        raise KeyError(f"unknown cup fixture: {fixture_id}")

    def plan_for_fixture(self, fixture_id: str) -> KnockoutRoundPlan:
        for plan in self.plans:
            if any(f.fixture_id == fixture_id for f in plan.fixtures):
                return plan
        raise KeyError(f"unknown cup fixture: {fixture_id}")

    def to_dict(self) -> dict[str, Any]:
        return {
            "cup_id": self.cup_id, "name": self.name, "season_label": self.season_label,
            "rounds": [rule.to_dict() for rule in self.rounds],
            "draw_seed": self.draw_seed, "source_url": self.source_url,
            "qualification_note": self.qualification_note,
            "pairing_strategy": self.pairing_strategy,
            "plans": [
                {
                    "round_id": plan.definition.round_id,
                    "pairings": [[tie.club_a_id, tie.club_b_id] for tie in plan.ties],
                    "source": plan.source.value,
                }
                for plan in self.plans
            ],
            "champion_club_id": self.champion_club_id,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "DomesticCupSeason":
        season = cls(
            cup_id=str(value["cup_id"]), name=str(value["name"]),
            season_label=str(value["season_label"]),
            rounds=tuple(DomesticCupRound.from_dict(r) for r in value["rounds"]),
            draw_seed=int(value["draw_seed"]), source_url=str(value.get("source_url", "")),
            qualification_note=str(value.get("qualification_note", "")),
            pairing_strategy=str(value.get("pairing_strategy", "generated")),
        )
        for index, item in enumerate(value["plans"]):
            if index >= len(season.rounds) or item["round_id"] != season.rounds[index].round_id:
                raise ValueError("invalid persisted cup round sequence")
            rule = season.rounds[index]
            definition = KnockoutRoundDefinition(
                rule.round_id, rule.label, index + 1, rule.leg_format, rule.decider,
            )
            plan = seed_knockout_round(
                edition_id=season.edition_id, stage_id=rule.round_id,
                definition=definition,
                pairings=tuple(tuple(pair) for pair in item["pairings"]),
            )
            season.plans.append(replace(plan, source=KnockoutDrawSource(item["source"])))
        season.champion_club_id = value.get("champion_club_id")
        return season
