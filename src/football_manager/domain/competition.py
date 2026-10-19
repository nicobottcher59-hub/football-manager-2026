from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Iterable, Mapping

from .match_context import (
    CompetitionContextSnapshot,
    CupTieContextSnapshot,
    MatchDecider,
    StandingRowSnapshot,
)


class CompetitionScope(StrEnum):
    DOMESTIC = "domestic"
    CONTINENTAL = "continental"
    INTERNATIONAL = "international"


class CompetitionFormat(StrEnum):
    LEAGUE = "league"
    KNOCKOUT = "knockout"
    MULTI_STAGE = "multi_stage"


class CompetitionStatus(StrEnum):
    PLANNED = "planned"
    ACTIVE = "active"
    COMPLETED = "completed"


class CompetitionStageKind(StrEnum):
    ROUND_ROBIN = "round_robin"
    KNOCKOUT = "knockout"
    GROUP_STAGE = "group_stage"
    LEAGUE_PHASE = "league_phase"
    PLAYOFF = "playoff"


class QualificationKind(StrEnum):
    CONTINENTAL = "continental"
    PROMOTION = "promotion"
    RELEGATION = "relegation"
    PLAYOFF = "playoff"


class QualificationSource(StrEnum):
    STANDING_POSITION = "standing_position"
    CUP_WINNER = "cup_winner"
    CUP_RUNNER_UP = "cup_runner_up"
    TITLE_HOLDER = "title_holder"


class QualificationFallback(StrEnum):
    NONE = "none"
    NEXT_ELIGIBLE_STANDING_POSITION = "next_eligible_standing_position"


@dataclass(frozen=True, slots=True)
class CompetitionRegulations:
    substitution_limit: int = 5
    extra_time_additional_substitutions: int = 1

    def __post_init__(self) -> None:
        if self.substitution_limit < 0:
            raise ValueError("substitution_limit cannot be negative")
        if self.extra_time_additional_substitutions < 0:
            raise ValueError("extra_time_additional_substitutions cannot be negative")

    def to_dict(self) -> dict[str, int]:
        return {
            "substitution_limit": self.substitution_limit,
            "extra_time_additional_substitutions": self.extra_time_additional_substitutions,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "CompetitionRegulations":
        return cls(
            substitution_limit=int(data.get("substitution_limit", 5)),
            extra_time_additional_substitutions=int(
                data.get("extra_time_additional_substitutions", 1)
            ),
        )


@dataclass(frozen=True, slots=True)
class CompetitionDefinition:
    competition_id: str
    name: str
    short_name: str
    scope: CompetitionScope
    format: CompetitionFormat
    country: str | None = None

    def __post_init__(self) -> None:
        _require_text("competition_id", self.competition_id)
        _require_text("competition name", self.name)
        _require_text("competition short_name", self.short_name)
        if not isinstance(self.scope, CompetitionScope):
            object.__setattr__(self, "scope", CompetitionScope(self.scope))
        if not isinstance(self.format, CompetitionFormat):
            object.__setattr__(self, "format", CompetitionFormat(self.format))
        if self.country is not None:
            _require_text("competition country", self.country)

    def to_dict(self) -> dict[str, Any]:
        return {
            "competition_id": self.competition_id,
            "name": self.name,
            "short_name": self.short_name,
            "scope": self.scope.value,
            "format": self.format.value,
            "country": self.country,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "CompetitionDefinition":
        return cls(
            competition_id=str(data["competition_id"]),
            name=str(data["name"]),
            short_name=str(data["short_name"]),
            scope=CompetitionScope(str(data["scope"])),
            format=CompetitionFormat(str(data["format"])),
            country=_optional_text(data.get("country")),
        )


@dataclass(frozen=True, slots=True)
class CompetitionStage:
    stage_id: str
    name: str
    kind: CompetitionStageKind
    order: int
    participant_club_ids: tuple[str, ...] = ()
    match_decider: MatchDecider = MatchDecider.DRAW_ALLOWED

    def __post_init__(self) -> None:
        _require_text("stage_id", self.stage_id)
        _require_text("stage name", self.name)
        if not isinstance(self.kind, CompetitionStageKind):
            object.__setattr__(self, "kind", CompetitionStageKind(self.kind))
        if self.order < 1:
            raise ValueError("stage order must be at least 1")
        if not isinstance(self.match_decider, MatchDecider):
            object.__setattr__(self, "match_decider", MatchDecider(self.match_decider))
        _validate_unique_ids("stage participant", self.participant_club_ids)

    def to_dict(self) -> dict[str, Any]:
        return {
            "stage_id": self.stage_id,
            "name": self.name,
            "kind": self.kind.value,
            "order": self.order,
            "participant_club_ids": list(self.participant_club_ids),
            "match_decider": self.match_decider.value,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "CompetitionStage":
        return cls(
            stage_id=str(data["stage_id"]),
            name=str(data["name"]),
            kind=CompetitionStageKind(str(data["kind"])),
            order=int(data["order"]),
            participant_club_ids=_string_tuple(data.get("participant_club_ids", ())),
            match_decider=MatchDecider(
                str(data.get("match_decider", MatchDecider.DRAW_ALLOWED.value))
            ),
        )


@dataclass(frozen=True, slots=True)
class QualificationRule:
    """A season-specific route out of a competition.

    League-position rules are intentionally data, not hardcoded behavior. This
    lets a domestic league describe European places, promotion, relegation or
    playoffs without coupling those rules to the league engine. Cup-winner and
    title-holder routes are represented by the same model so later allocation
    logic can resolve overlaps and fallback berths consistently.
    """

    rule_id: str
    label: str
    kind: QualificationKind
    source: QualificationSource
    target_competition_id: str | None = None
    target_stage_id: str | None = None
    standing_positions: tuple[int, ...] = ()
    source_competition_id: str | None = None
    fallback: QualificationFallback = QualificationFallback.NONE
    priority: int = 0

    def __post_init__(self) -> None:
        _require_text("qualification rule_id", self.rule_id)
        _require_text("qualification label", self.label)
        if not isinstance(self.kind, QualificationKind):
            object.__setattr__(self, "kind", QualificationKind(self.kind))
        if not isinstance(self.source, QualificationSource):
            object.__setattr__(self, "source", QualificationSource(self.source))
        if not isinstance(self.fallback, QualificationFallback):
            object.__setattr__(self, "fallback", QualificationFallback(self.fallback))
        if self.priority < 0:
            raise ValueError("qualification priority cannot be negative")

        if self.target_competition_id is not None:
            _require_text("qualification target_competition_id", self.target_competition_id)
        if self.target_stage_id is not None:
            _require_text("qualification target_stage_id", self.target_stage_id)
        if self.source_competition_id is not None:
            _require_text("qualification source_competition_id", self.source_competition_id)

        if self.source is QualificationSource.STANDING_POSITION:
            if not self.standing_positions:
                raise ValueError("standing-position qualification requires positions")
            if any(position < 1 for position in self.standing_positions):
                raise ValueError("qualification standing positions must be positive")
            if len(set(self.standing_positions)) != len(self.standing_positions):
                raise ValueError("qualification standing positions must be unique")
            if self.source_competition_id is not None:
                raise ValueError(
                    "standing-position qualification cannot use source_competition_id"
                )
        else:
            if self.standing_positions:
                raise ValueError(
                    "non-standing qualification cannot define standing_positions"
                )
            if self.source in {
                QualificationSource.CUP_WINNER,
                QualificationSource.CUP_RUNNER_UP,
            } and self.source_competition_id is None:
                raise ValueError(
                    "cup-derived qualification requires source_competition_id"
                )

        if self.kind in {
            QualificationKind.CONTINENTAL,
            QualificationKind.PROMOTION,
            QualificationKind.RELEGATION,
            QualificationKind.PLAYOFF,
        } and self.target_competition_id is None:
            raise ValueError("qualification rule requires target_competition_id")

    def applies_to_position(self, position: int) -> bool:
        return (
            self.source is QualificationSource.STANDING_POSITION
            and position in self.standing_positions
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "label": self.label,
            "kind": self.kind.value,
            "source": self.source.value,
            "target_competition_id": self.target_competition_id,
            "target_stage_id": self.target_stage_id,
            "standing_positions": list(self.standing_positions),
            "source_competition_id": self.source_competition_id,
            "fallback": self.fallback.value,
            "priority": self.priority,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "QualificationRule":
        return cls(
            rule_id=str(data["rule_id"]),
            label=str(data["label"]),
            kind=QualificationKind(str(data["kind"])),
            source=QualificationSource(str(data["source"])),
            target_competition_id=_optional_text(data.get("target_competition_id")),
            target_stage_id=_optional_text(data.get("target_stage_id")),
            standing_positions=tuple(
                int(position) for position in data.get("standing_positions", ())
            ),
            source_competition_id=_optional_text(data.get("source_competition_id")),
            fallback=QualificationFallback(
                str(data.get("fallback", QualificationFallback.NONE.value))
            ),
            priority=int(data.get("priority", 0)),
        )


@dataclass(frozen=True, slots=True)
class CompetitionFixture:
    """Unscheduled sporting fixture.

    Kickoff date/time deliberately does not live here. Phase 6.5 will assign
    fixtures to the unified calendar, keeping sporting structure separate from
    scheduling.
    """

    fixture_id: str
    edition_id: str
    stage_id: str
    home_club_id: str
    away_club_id: str
    round_number: int | None = None
    leg_number: int = 1

    def __post_init__(self) -> None:
        for label, value in (
            ("fixture_id", self.fixture_id),
            ("edition_id", self.edition_id),
            ("stage_id", self.stage_id),
            ("home_club_id", self.home_club_id),
            ("away_club_id", self.away_club_id),
        ):
            _require_text(label, value)
        if self.home_club_id == self.away_club_id:
            raise ValueError("fixture clubs must be different")
        if self.round_number is not None and self.round_number < 1:
            raise ValueError("fixture round_number must be at least 1")
        if self.leg_number < 1:
            raise ValueError("fixture leg_number must be at least 1")

    def to_dict(self) -> dict[str, Any]:
        return {
            "fixture_id": self.fixture_id,
            "edition_id": self.edition_id,
            "stage_id": self.stage_id,
            "home_club_id": self.home_club_id,
            "away_club_id": self.away_club_id,
            "round_number": self.round_number,
            "leg_number": self.leg_number,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "CompetitionFixture":
        round_number = data.get("round_number")
        return cls(
            fixture_id=str(data["fixture_id"]),
            edition_id=str(data["edition_id"]),
            stage_id=str(data["stage_id"]),
            home_club_id=str(data["home_club_id"]),
            away_club_id=str(data["away_club_id"]),
            round_number=None if round_number is None else int(round_number),
            leg_number=int(data.get("leg_number", 1)),
        )


@dataclass(frozen=True, slots=True)
class CompetitionEdition:
    edition_id: str
    competition: CompetitionDefinition
    season_label: str
    participant_club_ids: tuple[str, ...]
    stages: tuple[CompetitionStage, ...]
    regulations: CompetitionRegulations = field(default_factory=CompetitionRegulations)
    qualification_rules: tuple[QualificationRule, ...] = ()
    status: CompetitionStatus = CompetitionStatus.PLANNED
    fixtures: tuple[CompetitionFixture, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        _require_text("edition_id", self.edition_id)
        _require_text("season_label", self.season_label)
        if not isinstance(self.status, CompetitionStatus):
            object.__setattr__(self, "status", CompetitionStatus(self.status))
        if not isinstance(self.regulations, CompetitionRegulations):
            raise TypeError("regulations must be CompetitionRegulations")
        if len(self.participant_club_ids) < 2:
            raise ValueError("competition edition requires at least two participants")
        _validate_unique_ids("competition participant", self.participant_club_ids)
        if not self.stages:
            raise ValueError("competition edition requires at least one stage")

        stage_ids = [stage.stage_id for stage in self.stages]
        if len(set(stage_ids)) != len(stage_ids):
            raise ValueError("competition edition cannot contain duplicate stage IDs")
        stage_orders = [stage.order for stage in self.stages]
        if len(set(stage_orders)) != len(stage_orders):
            raise ValueError("competition edition cannot contain duplicate stage orders")
        if sorted(stage_orders) != list(range(1, len(self.stages) + 1)):
            raise ValueError("competition stage orders must be contiguous from 1")

        participant_set = set(self.participant_club_ids)
        for stage in self.stages:
            unknown = set(stage.participant_club_ids) - participant_set
            if unknown:
                raise ValueError(
                    f"stage {stage.stage_id} contains clubs outside edition: {sorted(unknown)}"
                )

        rule_ids = [rule.rule_id for rule in self.qualification_rules]
        if len(set(rule_ids)) != len(rule_ids):
            raise ValueError("competition edition cannot contain duplicate qualification rule IDs")
        participant_count = len(self.participant_club_ids)
        for rule in self.qualification_rules:
            if rule.source is QualificationSource.STANDING_POSITION:
                if max(rule.standing_positions) > participant_count:
                    raise ValueError(
                        "qualification standing position exceeds edition participant count"
                    )

        fixture_ids = [fixture.fixture_id for fixture in self.fixtures]
        if len(set(fixture_ids)) != len(fixture_ids):
            raise ValueError("competition edition cannot contain duplicate fixture IDs")
        valid_stage_ids = set(stage_ids)
        for fixture in self.fixtures:
            if fixture.edition_id != self.edition_id:
                raise ValueError("fixture belongs to a different competition edition")
            if fixture.stage_id not in valid_stage_ids:
                raise ValueError(f"fixture references unknown stage {fixture.stage_id}")
            if fixture.home_club_id not in participant_set or fixture.away_club_id not in participant_set:
                raise ValueError("fixture contains club outside competition edition")
            stage = self.stage(fixture.stage_id)
            if stage.participant_club_ids:
                stage_participants = set(stage.participant_club_ids)
                if (
                    fixture.home_club_id not in stage_participants
                    or fixture.away_club_id not in stage_participants
                ):
                    raise ValueError("fixture contains club outside its competition stage")

    @property
    def competition_id(self) -> str:
        return self.competition.competition_id

    def stage(self, stage_id: str) -> CompetitionStage:
        for stage in self.stages:
            if stage.stage_id == stage_id:
                return stage
        raise KeyError(f"unknown competition stage: {stage_id}")

    def has_participant(self, club_id: str) -> bool:
        return club_id in self.participant_club_ids

    def qualification_rules_for_position(self, position: int) -> tuple[QualificationRule, ...]:
        if position < 1:
            raise ValueError("standing position must be positive")
        return tuple(
            sorted(
                (
                    rule
                    for rule in self.qualification_rules
                    if rule.applies_to_position(position)
                ),
                key=lambda rule: (rule.priority, rule.rule_id),
            )
        )

    def qualification_rules_by_kind(
        self, kind: QualificationKind
    ) -> tuple[QualificationRule, ...]:
        if not isinstance(kind, QualificationKind):
            kind = QualificationKind(kind)
        return tuple(rule for rule in self.qualification_rules if rule.kind is kind)

    def fixtures_for_stage(self, stage_id: str) -> tuple[CompetitionFixture, ...]:
        self.stage(stage_id)
        return tuple(fixture for fixture in self.fixtures if fixture.stage_id == stage_id)

    def context_snapshot(
        self,
        stage_id: str,
        *,
        standings: tuple[StandingRowSnapshot, ...] = (),
        cup_tie: CupTieContextSnapshot | None = None,
    ) -> CompetitionContextSnapshot:
        stage = self.stage(stage_id)
        return CompetitionContextSnapshot(
            competition_id=self.competition_id,
            competition_name=self.competition.name,
            season_label=self.season_label,
            stage_label=stage.name,
            standings=standings,
            cup_tie=cup_tie,
            match_decider=stage.match_decider,
            substitution_limit=self.regulations.substitution_limit,
            extra_time_additional_substitutions=(
                self.regulations.extra_time_additional_substitutions
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "edition_id": self.edition_id,
            "competition": self.competition.to_dict(),
            "season_label": self.season_label,
            "participant_club_ids": list(self.participant_club_ids),
            "stages": [stage.to_dict() for stage in self.stages],
            "regulations": self.regulations.to_dict(),
            "qualification_rules": [rule.to_dict() for rule in self.qualification_rules],
            "status": self.status.value,
            "fixtures": [fixture.to_dict() for fixture in self.fixtures],
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "CompetitionEdition":
        competition_data = data["competition"]
        if not isinstance(competition_data, Mapping):
            raise TypeError("competition must be a mapping")
        return cls(
            edition_id=str(data["edition_id"]),
            competition=CompetitionDefinition.from_dict(competition_data),
            season_label=str(data["season_label"]),
            participant_club_ids=_string_tuple(data["participant_club_ids"]),
            stages=tuple(
                CompetitionStage.from_dict(_as_mapping(stage))
                for stage in data["stages"]
            ),
            regulations=CompetitionRegulations.from_dict(
                _as_mapping(data.get("regulations", {}))
            ),
            qualification_rules=tuple(
                QualificationRule.from_dict(_as_mapping(rule))
                for rule in data.get("qualification_rules", ())
            ),
            status=CompetitionStatus(str(data.get("status", CompetitionStatus.PLANNED.value))),
            fixtures=tuple(
                CompetitionFixture.from_dict(_as_mapping(fixture))
                for fixture in data.get("fixtures", ())
            ),
        )


def _require_text(label: str, value: str) -> None:
    if not value.strip():
        raise ValueError(f"{label} cannot be empty")


def _validate_unique_ids(label: str, values: Iterable[str]) -> None:
    normalized = tuple(values)
    if any(not value.strip() for value in normalized):
        raise ValueError(f"{label} IDs cannot be empty")
    if len(set(normalized)) != len(normalized):
        raise ValueError(f"{label} IDs must be unique")


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value)
    _require_text("optional text", text)
    return text


def _string_tuple(values: Iterable[Any]) -> tuple[str, ...]:
    return tuple(str(value) for value in values)


def _as_mapping(value: Any) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise TypeError("serialized competition item must be a mapping")
    return value
