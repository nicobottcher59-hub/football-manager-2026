from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from .attributes import PlayerAttributes
from .enums import Foot, Position
from .formation import Formation
from .tactical_shapes import PhaseShape
from .match_context import MatchContextSnapshot
from .tactical_instructions import PlayerInstructions, TeamInstructions
from .tactical_presets import TacticalPreset
from .tactics import TacticalStyleAnalysis


@dataclass(frozen=True, slots=True)
class PlayerStateSnapshot:
    fitness: float
    fatigue: float
    form: float
    morale: float
    confidence: float
    match_sharpness: float
    injury: str | None
    suspended_matches: int

    @property
    def condition(self) -> float:
        return self.fitness


@dataclass(frozen=True, slots=True)
class PlayerFamiliaritySnapshot:
    positions: tuple[tuple[Position, float], ...]
    roles: tuple[tuple[str, float], ...]
    tactics: tuple[tuple[str, float], ...]

    def position_score(self, position: Position) -> float:
        for item_position, score in self.positions:
            if item_position == position:
                return score
        return 0.0

    def role_score(self, role_id: str) -> float:
        for item_role_id, score in self.roles:
            if item_role_id == role_id:
                return score
        return 0.0

    def tactic_score(self, tactic_id: str) -> float:
        for item_tactic_id, score in self.tactics:
            if item_tactic_id == tactic_id:
                return score
        return 0.0


@dataclass(frozen=True, slots=True)
class RoleExecutionSnapshot:
    position_familiarity: float
    role_familiarity: float
    tactic_familiarity: float
    role_suitability: float


@dataclass(frozen=True, slots=True)
class PlayerMatchSnapshot:
    player_id: str
    full_name: str
    birth_date: date
    nationality: str
    dominant_foot: Foot
    attributes: PlayerAttributes
    state: PlayerStateSnapshot
    familiarity: PlayerFamiliaritySnapshot
    overall_rating: float
    current_rating: float
    original_position: Position
    assigned_slot_id: str | None = None
    assigned_position: Position | None = None
    role_id: str | None = None
    role_name: str | None = None
    effective_instructions: PlayerInstructions | None = None
    role_context: RoleExecutionSnapshot | None = None
    # Needed to preserve the original ACT chemistry factor when reassigning a
    # player mid-match.  Historical/manual snapshots remain neutral by default.
    rating_chemistry: float = 65.0

    @property
    def is_starter(self) -> bool:
        return self.assigned_slot_id is not None


@dataclass(frozen=True, slots=True)
class TacticalSlotSnapshot:
    slot_id: str
    position: Position
    role_id: str
    role_name: str
    effective_instructions: PlayerInstructions


@dataclass(frozen=True, slots=True)
class TacticMatchSnapshot:
    tactic_id: str
    name: str
    formation: Formation
    preset_origin: TacticalPreset
    team_instructions: TeamInstructions
    slots: tuple[TacticalSlotSnapshot, ...]
    style: TacticalStyleAnalysis
    phase_shapes: tuple[PhaseShape, ...] = ()

    def slot(self, slot_id: str) -> TacticalSlotSnapshot:
        for item in self.slots:
            if item.slot_id == slot_id:
                return item
        raise KeyError(f"tactical slot {slot_id!r} does not exist")


@dataclass(frozen=True, slots=True)
class TeamMatchSnapshot:
    club_id: str
    club_name: str
    club_short_name: str
    country: str
    formation: Formation
    starters: tuple[PlayerMatchSnapshot, ...]
    bench: tuple[PlayerMatchSnapshot, ...]
    tactic: TacticMatchSnapshot

    def __post_init__(self) -> None:
        if not self.club_id.strip():
            raise ValueError("team snapshot club_id cannot be empty")
        if len(self.starters) != 11:
            raise ValueError("team snapshot must contain exactly 11 starters")
        if any(not player.is_starter for player in self.starters):
            raise ValueError("all starting snapshots must have an assigned slot")
        if any(player.is_starter for player in self.bench):
            raise ValueError("bench snapshots cannot have an assigned starting slot")

        all_ids = [player.player_id for player in self.starters + self.bench]
        if len(set(all_ids)) != len(all_ids):
            raise ValueError("team snapshot cannot contain duplicate players")

        starter_slots = [player.assigned_slot_id for player in self.starters]
        if frozenset(starter_slots) != self.formation.slot_ids:
            raise ValueError("team snapshot starters must cover every formation slot")
        if self.tactic.formation != self.formation:
            raise ValueError("team snapshot tactic formation must match lineup formation")

    def player(self, player_id: str) -> PlayerMatchSnapshot:
        for player in self.starters + self.bench:
            if player.player_id == player_id:
                return player
        raise KeyError(f"player {player_id!r} is not in the match squad snapshot")

    def player_for_slot(self, slot_id: str) -> PlayerMatchSnapshot:
        self.formation.slot(slot_id)
        for player in self.starters:
            if player.assigned_slot_id == slot_id:
                return player
        raise KeyError(f"no player assigned to slot {slot_id!r}")


@dataclass(frozen=True, slots=True)
class MatchSnapshot:
    match_id: str
    seed: int
    context: MatchContextSnapshot
    home_team: TeamMatchSnapshot
    away_team: TeamMatchSnapshot

    def __post_init__(self) -> None:
        if not self.match_id.strip():
            raise ValueError("match_id cannot be empty")
        if self.seed < 0:
            raise ValueError("match seed must be non-negative")
        if self.home_team.club_id == self.away_team.club_id:
            raise ValueError("home and away clubs must be different")
        if self.context.kits.home.club_id != self.home_team.club_id:
            raise ValueError("selected home kit belongs to a different club")
        if self.context.kits.away.club_id != self.away_team.club_id:
            raise ValueError("selected away kit belongs to a different club")
