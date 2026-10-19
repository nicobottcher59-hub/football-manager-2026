from __future__ import annotations

from dataclasses import dataclass, replace
from enum import StrEnum
from random import Random
from typing import Any, Mapping, Sequence

from .competition import CompetitionEdition, CompetitionFixture, CompetitionStageKind
from .match_context import CompetitionContextSnapshot, CupTieContextSnapshot, MatchDecider
from .score_validation import require_nonnegative_integer_score


class KnockoutDrawSource(StrEnum):
    SEEDED = "seeded"
    GENERATED = "generated"


class KnockoutLegFormat(StrEnum):
    SINGLE_LEG = "single_leg"
    TWO_LEGGED = "two_legged"

    @property
    def leg_count(self) -> int:
        return 1 if self is KnockoutLegFormat.SINGLE_LEG else 2


@dataclass(frozen=True, slots=True)
class KnockoutRoundDefinition:
    round_id: str
    name: str
    order: int
    leg_format: KnockoutLegFormat = KnockoutLegFormat.SINGLE_LEG
    deciding_match_decider: MatchDecider = MatchDecider.EXTRA_TIME_AND_PENALTIES

    def __post_init__(self) -> None:
        if not self.round_id.strip():
            raise ValueError("knockout round_id cannot be empty")
        if not self.name.strip():
            raise ValueError("knockout round name cannot be empty")
        if self.order < 1:
            raise ValueError("knockout round order must be at least 1")
        if not isinstance(self.leg_format, KnockoutLegFormat):
            object.__setattr__(self, "leg_format", KnockoutLegFormat(self.leg_format))
        if not isinstance(self.deciding_match_decider, MatchDecider):
            object.__setattr__(
                self,
                "deciding_match_decider",
                MatchDecider(self.deciding_match_decider),
            )
        if self.deciding_match_decider is MatchDecider.DRAW_ALLOWED:
            raise ValueError("a knockout round must eventually produce a winner")

    @property
    def leg_count(self) -> int:
        return self.leg_format.leg_count


@dataclass(frozen=True, slots=True)
class KnockoutTie:
    tie_id: str
    round_id: str
    club_a_id: str
    club_b_id: str
    fixtures: tuple[CompetitionFixture, ...]

    def __post_init__(self) -> None:
        for label, value in (
            ("tie_id", self.tie_id),
            ("round_id", self.round_id),
            ("club_a_id", self.club_a_id),
            ("club_b_id", self.club_b_id),
        ):
            if not value.strip():
                raise ValueError(f"{label} cannot be empty")
        if self.club_a_id == self.club_b_id:
            raise ValueError("knockout tie clubs must be different")
        if len(self.fixtures) not in {1, 2}:
            raise ValueError("knockout tie requires one or two fixtures")
        fixture_ids = [fixture.fixture_id for fixture in self.fixtures]
        if len(set(fixture_ids)) != len(fixture_ids):
            raise ValueError("knockout tie fixture IDs must be unique")

        clubs = {self.club_a_id, self.club_b_id}
        ordered = tuple(sorted(self.fixtures, key=lambda fixture: fixture.leg_number))
        if tuple(fixture.leg_number for fixture in ordered) != tuple(
            range(1, len(ordered) + 1)
        ):
            raise ValueError("knockout tie leg numbers must be contiguous from 1")
        for fixture in ordered:
            if {fixture.home_club_id, fixture.away_club_id} != clubs:
                raise ValueError("knockout tie fixture clubs do not match the tie")
        if len(ordered) == 2:
            first, second = ordered
            if not (
                first.home_club_id == second.away_club_id
                and first.away_club_id == second.home_club_id
            ):
                raise ValueError("two-legged tie must reverse home/away clubs")


@dataclass(frozen=True, slots=True)
class KnockoutRoundPlan:
    definition: KnockoutRoundDefinition
    ties: tuple[KnockoutTie, ...]
    source: KnockoutDrawSource = KnockoutDrawSource.GENERATED

    def __post_init__(self) -> None:
        if not isinstance(self.source, KnockoutDrawSource):
            object.__setattr__(self, "source", KnockoutDrawSource(self.source))
        if not self.ties:
            raise ValueError("knockout round requires at least one tie")
        tie_ids = [tie.tie_id for tie in self.ties]
        if len(set(tie_ids)) != len(tie_ids):
            raise ValueError("knockout round tie IDs must be unique")
        fixture_ids = [fixture.fixture_id for fixture in self.fixtures]
        if len(set(fixture_ids)) != len(fixture_ids):
            raise ValueError("knockout round fixture IDs must be unique")
        seen_clubs: set[str] = set()
        for tie in self.ties:
            if tie.round_id != self.definition.round_id:
                raise ValueError("tie belongs to a different knockout round")
            if len(tie.fixtures) != self.definition.leg_count:
                raise ValueError("tie leg count does not match round definition")
            for club_id in (tie.club_a_id, tie.club_b_id):
                if club_id in seen_clubs:
                    raise ValueError("club appears in more than one tie in the round")
                seen_clubs.add(club_id)

    @property
    def fixtures(self) -> tuple[CompetitionFixture, ...]:
        return tuple(fixture for tie in self.ties for fixture in tie.fixtures)

    @property
    def participant_club_ids(self) -> tuple[str, ...]:
        return tuple(club_id for tie in self.ties for club_id in (tie.club_a_id, tie.club_b_id))

    def tie(self, tie_id: str) -> KnockoutTie:
        for tie in self.ties:
            if tie.tie_id == tie_id:
                return tie
        raise KeyError(f"unknown knockout tie: {tie_id}")

    def tie_for_fixture(self, fixture_id: str) -> KnockoutTie:
        for tie in self.ties:
            if any(fixture.fixture_id == fixture_id for fixture in tie.fixtures):
                return tie
        raise KeyError(f"unknown knockout fixture: {fixture_id}")


@dataclass(frozen=True, slots=True)
class KnockoutMatchResult:
    fixture_id: str
    home_goals: int
    away_goals: int
    penalties_home: int = 0
    penalties_away: int = 0

    def __post_init__(self) -> None:
        if not self.fixture_id.strip():
            raise ValueError("fixture_id cannot be empty")
        for field in ("home_goals", "away_goals", "penalties_home", "penalties_away"):
            require_nonnegative_integer_score(getattr(self, field), field)
        penalties_used = self.penalties_home > 0 or self.penalties_away > 0
        if penalties_used and self.penalties_home == self.penalties_away:
            raise ValueError("penalty shootout must produce a winner")

    @property
    def decided_by_penalties(self) -> bool:
        return self.penalties_home > 0 or self.penalties_away > 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "fixture_id": self.fixture_id,
            "home_goals": self.home_goals,
            "away_goals": self.away_goals,
            "penalties_home": self.penalties_home,
            "penalties_away": self.penalties_away,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "KnockoutMatchResult":
        return cls(
            fixture_id=str(data["fixture_id"]),
            home_goals=data["home_goals"],
            away_goals=data["away_goals"],
            penalties_home=data.get("penalties_home", 0),
            penalties_away=data.get("penalties_away", 0),
        )


@dataclass(frozen=True, slots=True)
class KnockoutTieOutcome:
    tie_id: str
    club_a_id: str
    club_b_id: str
    aggregate_a_goals: int
    aggregate_b_goals: int
    winner_club_id: str | None
    loser_club_id: str | None
    decided_by_penalties: bool
    complete: bool


@dataclass(frozen=True, slots=True)
class KnockoutRoundOutcome:
    round_id: str
    ties: tuple[KnockoutTieOutcome, ...]

    @property
    def complete(self) -> bool:
        return all(tie.complete for tie in self.ties)

    @property
    def winner_club_ids(self) -> tuple[str, ...]:
        if not self.complete:
            raise ValueError("knockout round is not complete")
        return tuple(tie.winner_club_id for tie in self.ties if tie.winner_club_id is not None)


@dataclass(frozen=True, slots=True)
class KnockoutBracketRound:
    definition: KnockoutRoundDefinition
    plan: KnockoutRoundPlan
    outcome: KnockoutRoundOutcome | None = None


def generate_knockout_round(
    *,
    edition_id: str,
    stage_id: str,
    definition: KnockoutRoundDefinition,
    participant_club_ids: Sequence[str],
    seed: int | None = None,
) -> KnockoutRoundPlan:
    participants = list(participant_club_ids)
    _validate_participants(participants)
    if len(participants) % 2 != 0:
        raise ValueError("knockout round requires an even number of participants")
    if seed is not None:
        Random(seed).shuffle(participants)
    pairings = tuple(
        (participants[index], participants[index + 1])
        for index in range(0, len(participants), 2)
    )
    return _build_knockout_plan(
        edition_id=edition_id,
        stage_id=stage_id,
        definition=definition,
        pairings=pairings,
        source=KnockoutDrawSource.GENERATED,
    )


def seed_knockout_round(
    *,
    edition_id: str,
    stage_id: str,
    definition: KnockoutRoundDefinition,
    pairings: Sequence[tuple[str, str]],
) -> KnockoutRoundPlan:
    """Build a round from externally supplied pairings.

    This is the cup equivalent of a seeded first-season league fixture list:
    real-world draws can be imported exactly, while later in-game draws can use
    ``generate_knockout_round``. Dates still belong to the future calendar layer.
    """

    normalized = tuple((str(home), str(away)) for home, away in pairings)
    participants = tuple(club_id for pairing in normalized for club_id in pairing)
    _validate_participants(participants)
    if not normalized:
        raise ValueError("seeded knockout round requires at least one pairing")
    return _build_knockout_plan(
        edition_id=edition_id,
        stage_id=stage_id,
        definition=definition,
        pairings=normalized,
        source=KnockoutDrawSource.SEEDED,
    )


def _build_knockout_plan(
    *,
    edition_id: str,
    stage_id: str,
    definition: KnockoutRoundDefinition,
    pairings: Sequence[tuple[str, str]],
    source: KnockoutDrawSource,
) -> KnockoutRoundPlan:
    ties: list[KnockoutTie] = []
    for tie_number, (club_a, club_b) in enumerate(pairings, start=1):
        if not club_a.strip() or not club_b.strip():
            raise ValueError("knockout pairing club IDs cannot be empty")
        if club_a == club_b:
            raise ValueError("knockout pairing clubs must be different")
        tie_id = f"{edition_id}-{definition.round_id}-t{tie_number:02d}"
        fixtures: list[CompetitionFixture] = [
            CompetitionFixture(
                fixture_id=f"{tie_id}-l1",
                edition_id=edition_id,
                stage_id=stage_id,
                home_club_id=club_a,
                away_club_id=club_b,
                round_number=definition.order,
                leg_number=1,
            )
        ]
        if definition.leg_format is KnockoutLegFormat.TWO_LEGGED:
            fixtures.append(
                CompetitionFixture(
                    fixture_id=f"{tie_id}-l2",
                    edition_id=edition_id,
                    stage_id=stage_id,
                    home_club_id=club_b,
                    away_club_id=club_a,
                    round_number=definition.order,
                    leg_number=2,
                )
            )
        ties.append(
            KnockoutTie(
                tie_id=tie_id,
                round_id=definition.round_id,
                club_a_id=club_a,
                club_b_id=club_b,
                fixtures=tuple(fixtures),
            )
        )
    return KnockoutRoundPlan(
        definition=definition, ties=tuple(ties), source=source
    )


def resolve_knockout_tie(
    tie: KnockoutTie,
    results: Sequence[KnockoutMatchResult],
) -> KnockoutTieOutcome:
    result_by_fixture = _results_by_fixture(results)
    relevant = [result_by_fixture.get(fixture.fixture_id) for fixture in tie.fixtures]
    complete = all(result is not None for result in relevant)

    aggregate = {tie.club_a_id: 0, tie.club_b_id: 0}
    for fixture, result in zip(tie.fixtures, relevant):
        if result is None:
            continue
        aggregate[fixture.home_club_id] += result.home_goals
        aggregate[fixture.away_club_id] += result.away_goals

    winner: str | None = None
    loser: str | None = None
    decided_by_penalties = False
    if complete:
        a_goals = aggregate[tie.club_a_id]
        b_goals = aggregate[tie.club_b_id]
        if a_goals > b_goals:
            winner, loser = tie.club_a_id, tie.club_b_id
        elif b_goals > a_goals:
            winner, loser = tie.club_b_id, tie.club_a_id
        else:
            decisive_fixture = max(tie.fixtures, key=lambda fixture: fixture.leg_number)
            decisive_result = result_by_fixture[decisive_fixture.fixture_id]
            if decisive_result.penalties_home > decisive_result.penalties_away:
                winner, loser = decisive_fixture.home_club_id, decisive_fixture.away_club_id
                decided_by_penalties = True
            elif decisive_result.penalties_away > decisive_result.penalties_home:
                winner, loser = decisive_fixture.away_club_id, decisive_fixture.home_club_id
                decided_by_penalties = True
            else:
                complete = False

    return KnockoutTieOutcome(
        tie_id=tie.tie_id,
        club_a_id=tie.club_a_id,
        club_b_id=tie.club_b_id,
        aggregate_a_goals=aggregate[tie.club_a_id],
        aggregate_b_goals=aggregate[tie.club_b_id],
        winner_club_id=winner,
        loser_club_id=loser,
        decided_by_penalties=decided_by_penalties,
        complete=complete,
    )


def resolve_knockout_round(
    plan: KnockoutRoundPlan,
    results: Sequence[KnockoutMatchResult],
) -> KnockoutRoundOutcome:
    fixture_ids = {fixture.fixture_id for fixture in plan.fixtures}
    result_ids = [result.fixture_id for result in results]
    if len(set(result_ids)) != len(result_ids):
        raise ValueError("knockout fixture cannot have more than one final result")
    unknown = set(result_ids) - fixture_ids
    if unknown:
        raise ValueError(f"result references unknown knockout fixture: {sorted(unknown)}")
    return KnockoutRoundOutcome(
        round_id=plan.definition.round_id,
        ties=tuple(resolve_knockout_tie(tie, results) for tie in plan.ties),
    )


def advance_knockout_round(
    outcome: KnockoutRoundOutcome,
    *,
    edition_id: str,
    stage_id: str,
    next_definition: KnockoutRoundDefinition,
    seed: int | None = None,
) -> KnockoutRoundPlan:
    if not outcome.complete:
        raise ValueError("cannot advance an incomplete knockout round")
    winners = outcome.winner_club_ids
    if len(winners) < 2:
        raise ValueError("competition is complete; there is no next knockout round")
    return generate_knockout_round(
        edition_id=edition_id,
        stage_id=stage_id,
        definition=next_definition,
        participant_club_ids=winners,
        seed=seed,
    )


def knockout_context_for_fixture(
    *,
    edition: CompetitionEdition,
    stage_id: str,
    plan: KnockoutRoundPlan,
    fixture_id: str,
    results: Sequence[KnockoutMatchResult] = (),
) -> CompetitionContextSnapshot:
    stage = edition.stage(stage_id)
    if stage.kind is not CompetitionStageKind.KNOCKOUT:
        raise ValueError("knockout context requires a KNOCKOUT competition stage")
    tie = plan.tie_for_fixture(fixture_id)
    fixture = next(item for item in tie.fixtures if item.fixture_id == fixture_id)
    result_by_fixture = _results_by_fixture(results)

    prior_home = 0
    prior_away = 0
    for previous in tie.fixtures:
        if previous.leg_number >= fixture.leg_number:
            continue
        result = result_by_fixture.get(previous.fixture_id)
        if result is None:
            raise ValueError("prior knockout leg result is required before a later leg")
        for club_id, goals in (
            (previous.home_club_id, result.home_goals),
            (previous.away_club_id, result.away_goals),
        ):
            if club_id == fixture.home_club_id:
                prior_home += goals
            elif club_id == fixture.away_club_id:
                prior_away += goals

    base = edition.context_snapshot(
        stage_id,
        cup_tie=CupTieContextSnapshot(
            round_label=plan.definition.name,
            leg_number=fixture.leg_number,
            home_aggregate_goals_before_match=prior_home,
            away_aggregate_goals_before_match=prior_away,
        ),
    )
    is_deciding_leg = fixture.leg_number == plan.definition.leg_count
    decider = (
        plan.definition.deciding_match_decider
        if is_deciding_leg
        else MatchDecider.DRAW_ALLOWED
    )
    return replace(base, match_decider=decider)


def validate_knockout_edition(edition: CompetitionEdition, stage_id: str) -> None:
    stage = edition.stage(stage_id)
    if stage.kind is not CompetitionStageKind.KNOCKOUT:
        raise ValueError("knockout stage must be KNOCKOUT")


def _results_by_fixture(
    results: Sequence[KnockoutMatchResult],
) -> dict[str, KnockoutMatchResult]:
    mapped: dict[str, KnockoutMatchResult] = {}
    for result in results:
        if result.fixture_id in mapped:
            raise ValueError("knockout fixture cannot have more than one final result")
        mapped[result.fixture_id] = result
    return mapped


def _validate_participants(participant_club_ids: Sequence[str]) -> None:
    participants = tuple(participant_club_ids)
    if len(participants) < 2:
        raise ValueError("knockout round requires at least two participants")
    if any(not club_id.strip() for club_id in participants):
        raise ValueError("knockout participant IDs cannot be empty")
    if len(set(participants)) != len(participants):
        raise ValueError("knockout participant IDs must be unique")
