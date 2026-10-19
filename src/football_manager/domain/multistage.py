from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Iterable, Mapping, Sequence

from .competition import CompetitionEdition, CompetitionFormat, CompetitionStageKind
from .league import LeagueStandingRow


class StageRouteKind(StrEnum):
    """How a club leaves one stage of a multi-stage competition."""

    ADVANCE = "advance"
    PLAYOFF = "playoff"
    ELIMINATED = "eliminated"


@dataclass(frozen=True, slots=True)
class StandingRouteRule:
    """Route league/standing positions into a later competition stage.

    The rule is deliberately season data.  A Champions-like edition can route
    a leading block directly to a knockout round, a middle block to a playoff,
    and leave the remainder eliminated without teaching the engine any UEFA-
    specific numbers.
    """

    rule_id: str
    label: str
    source_stage_id: str
    positions: tuple[int, ...]
    route: StageRouteKind
    target_stage_id: str | None = None
    priority: int = 0

    def __post_init__(self) -> None:
        for label, value in (
            ("rule_id", self.rule_id),
            ("label", self.label),
            ("source_stage_id", self.source_stage_id),
        ):
            if not value.strip():
                raise ValueError(f"{label} cannot be empty")
        if not isinstance(self.route, StageRouteKind):
            object.__setattr__(self, "route", StageRouteKind(self.route))
        if not self.positions:
            raise ValueError("standing route requires at least one position")
        if any(position < 1 for position in self.positions):
            raise ValueError("standing route positions must be positive")
        if len(set(self.positions)) != len(self.positions):
            raise ValueError("standing route positions must be unique")
        if self.priority < 0:
            raise ValueError("standing route priority cannot be negative")
        if self.route is StageRouteKind.ELIMINATED:
            if self.target_stage_id is not None:
                raise ValueError("eliminated route cannot target another stage")
        else:
            if self.target_stage_id is None or not self.target_stage_id.strip():
                raise ValueError("advancing standing route requires target_stage_id")

    def to_dict(self) -> dict[str, object]:
        return {
            "rule_id": self.rule_id,
            "label": self.label,
            "source_stage_id": self.source_stage_id,
            "positions": list(self.positions),
            "route": self.route.value,
            "target_stage_id": self.target_stage_id,
            "priority": self.priority,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, object]) -> "StandingRouteRule":
        raw_positions = data.get("positions", ())
        if not isinstance(raw_positions, Iterable):
            raise TypeError("positions must be iterable")
        return cls(
            rule_id=str(data["rule_id"]),
            label=str(data["label"]),
            source_stage_id=str(data["source_stage_id"]),
            positions=tuple(int(position) for position in raw_positions),
            route=StageRouteKind(str(data["route"])),
            target_stage_id=(
                None
                if data.get("target_stage_id") is None
                else str(data["target_stage_id"])
            ),
            priority=int(data.get("priority", 0)),
        )


@dataclass(frozen=True, slots=True)
class StageRouteAssignment:
    source_stage_id: str
    position: int
    club_id: str
    route: StageRouteKind
    target_stage_id: str | None
    rule_id: str
    label: str


@dataclass(frozen=True, slots=True)
class StandingStageTransition:
    source_stage_id: str
    assignments: tuple[StageRouteAssignment, ...]

    def for_target(self, stage_id: str) -> tuple[str, ...]:
        """Return clubs routed to ``stage_id`` in source-standing order."""

        return tuple(
            item.club_id
            for item in sorted(self.assignments, key=lambda item: item.position)
            if item.target_stage_id == stage_id
        )

    @property
    def eliminated_club_ids(self) -> tuple[str, ...]:
        return tuple(
            item.club_id
            for item in sorted(self.assignments, key=lambda item: item.position)
            if item.route is StageRouteKind.ELIMINATED
        )

    def assignment_for_club(self, club_id: str) -> StageRouteAssignment:
        for item in self.assignments:
            if item.club_id == club_id:
                return item
        raise KeyError(f"club {club_id!r} is not part of the stage transition")


def resolve_standing_stage_transition(
    standings: Sequence[LeagueStandingRow],
    rules: Sequence[StandingRouteRule],
    *,
    source_stage_id: str | None = None,
    eliminate_unmatched: bool = True,
) -> StandingStageTransition:
    """Resolve a completed standings table into stage destinations.

    Rules may cover only the meaningful qualifying bands.  Any unmatched club
    is eliminated by default, which keeps real competition data concise while
    still preventing a club from silently qualifying through two routes.
    """

    if not standings:
        raise ValueError("standing transition requires at least one standing row")
    positions = [row.position for row in standings]
    if len(set(positions)) != len(positions):
        raise ValueError("standing positions must be unique")
    if sorted(positions) != list(range(1, len(standings) + 1)):
        raise ValueError("standing positions must be contiguous from 1")

    inferred_source = source_stage_id
    if inferred_source is None:
        stage_ids = {rule.source_stage_id for rule in rules}
        if len(stage_ids) != 1:
            raise ValueError("source_stage_id is ambiguous; supply it explicitly")
        inferred_source = next(iter(stage_ids))
    if not inferred_source.strip():
        raise ValueError("source_stage_id cannot be empty")

    applicable = [rule for rule in rules if rule.source_stage_id == inferred_source]
    rule_by_position: dict[int, StandingRouteRule] = {}
    for rule in sorted(applicable, key=lambda item: (item.priority, item.rule_id)):
        for position in rule.positions:
            if position > len(standings):
                raise ValueError("standing route position exceeds table size")
            if position in rule_by_position:
                raise ValueError(f"standing position {position} has overlapping routes")
            rule_by_position[position] = rule

    assignments: list[StageRouteAssignment] = []
    for row in sorted(standings, key=lambda item: item.position):
        rule = rule_by_position.get(row.position)
        if rule is None:
            if not eliminate_unmatched:
                raise ValueError(f"standing position {row.position} has no route")
            assignments.append(
                StageRouteAssignment(
                    source_stage_id=inferred_source,
                    position=row.position,
                    club_id=row.club_id,
                    route=StageRouteKind.ELIMINATED,
                    target_stage_id=None,
                    rule_id="implicit-elimination",
                    label="Eliminated",
                )
            )
            continue
        assignments.append(
            StageRouteAssignment(
                source_stage_id=inferred_source,
                position=row.position,
                club_id=row.club_id,
                route=rule.route,
                target_stage_id=rule.target_stage_id,
                rule_id=rule.rule_id,
                label=rule.label,
            )
        )

    return StandingStageTransition(
        source_stage_id=inferred_source,
        assignments=tuple(assignments),
    )


def merge_stage_participants(*groups: Iterable[str]) -> tuple[str, ...]:
    """Merge direct qualifiers and winners while preserving deterministic order."""

    merged: list[str] = []
    seen: set[str] = set()
    for group in groups:
        for club_id in group:
            if not str(club_id).strip():
                raise ValueError("stage participant club ID cannot be empty")
            if club_id in seen:
                raise ValueError(f"duplicate stage participant: {club_id}")
            seen.add(club_id)
            merged.append(club_id)
    if len(merged) < 2:
        raise ValueError("competition stage requires at least two participants")
    return tuple(merged)


def next_stage_id(edition: CompetitionEdition, stage_id: str) -> str | None:
    current = edition.stage(stage_id)
    later = sorted(
        (stage for stage in edition.stages if stage.order > current.order),
        key=lambda stage: stage.order,
    )
    return later[0].stage_id if later else None


def validate_multi_stage_edition(
    edition: CompetitionEdition,
    routes: Sequence[StandingRouteRule] = (),
) -> None:
    if edition.competition.format is not CompetitionFormat.MULTI_STAGE:
        raise ValueError("competition edition is not multi-stage")
    if len(edition.stages) < 2:
        raise ValueError("multi-stage competition requires at least two stages")

    stage_ids = {stage.stage_id for stage in edition.stages}
    for rule in routes:
        if rule.source_stage_id not in stage_ids:
            raise ValueError(f"route references unknown source stage {rule.source_stage_id}")
        if rule.target_stage_id is not None and rule.target_stage_id not in stage_ids:
            raise ValueError(f"route references unknown target stage {rule.target_stage_id}")
        source = edition.stage(rule.source_stage_id)
        if source.kind not in {
            CompetitionStageKind.ROUND_ROBIN,
            CompetitionStageKind.GROUP_STAGE,
            CompetitionStageKind.LEAGUE_PHASE,
        }:
            raise ValueError("standing route source must be a standings-based stage")
        if rule.target_stage_id is not None:
            target = edition.stage(rule.target_stage_id)
            if target.order <= source.order:
                raise ValueError("standing route must target a later stage")
