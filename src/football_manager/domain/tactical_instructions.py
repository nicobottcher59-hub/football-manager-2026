from __future__ import annotations

from dataclasses import dataclass, fields, replace
from enum import IntEnum, StrEnum

from .enums import Position


class Level(IntEnum):
    """Generic five-step tactical scale.

    The numeric values are intentionally engine-friendly while the enum names remain
    readable in code and future UI adapters.
    """

    VERY_LOW = 0
    LOW = 25
    NORMAL = 50
    HIGH = 75
    VERY_HIGH = 100


class PassLength(IntEnum):
    VERY_SHORT = 0
    SHORT = 25
    MIXED = 50
    LONG = 75
    VERY_LONG = 100


class PressingScheme(StrEnum):
    STANDARD = "standard"
    ZONAL = "zonal"
    MAN_ORIENTED = "man_oriented"
    TRAP_INSIDE = "trap_inside"
    TRAP_OUTSIDE = "trap_outside"
    CONSTANT = "constant"


class MarkingStyle(StrEnum):
    ZONAL = "zonal"
    MIXED = "mixed"
    MAN = "man"


class ForceDirection(StrEnum):
    NEUTRAL = "neutral"
    INSIDE = "inside"
    OUTSIDE = "outside"
    WEAK_FOOT = "weak_foot"


class AfterLossBehavior(StrEnum):
    COUNTERPRESS = "counterpress"
    REGROUP = "regroup"
    HOLD_SHAPE = "hold_shape"


class AfterWinBehavior(StrEnum):
    COUNTER = "counter"
    HOLD_POSSESSION = "hold_possession"
    PAUSE = "pause"
    DIRECT = "direct"
    EXPAND = "expand"


class InPossessionPosition(StrEnum):
    BASE = "base"
    WIDE = "wide"
    INSIDE = "inside"
    MIDFIELD = "midfield"
    ADVANCE = "advance"
    DROP_DEEP = "drop_deep"
    FREE = "free"


class OutOfPossessionPosition(StrEnum):
    BASE = "base"
    RETURN_TO_BASE = "return_to_base"
    STEP_UP = "step_up"
    DROP = "drop"
    FREE = "free"


class CrossType(StrEnum):
    MIXED = "mixed"
    EARLY = "early"
    BYLINE = "byline"
    LOW = "low"
    HIGH = "high"
    CUTBACK = "cutback"


class TargetKind(StrEnum):
    PLAYER = "player"
    POSITION = "position"
    ROLE = "role"


@dataclass(frozen=True, slots=True)
class TacticalTarget:
    kind: TargetKind
    target_id: str

    def __post_init__(self) -> None:
        if not self.target_id.strip():
            raise ValueError("tactical target_id cannot be empty")
        if self.kind is TargetKind.POSITION:
            Position(self.target_id)


@dataclass(frozen=True, slots=True)
class InPossessionInstructions:
    defensive_line_width: Level = Level.NORMAL
    midfield_width: Level = Level.NORMAL
    attacking_line_width: Level = Level.NORMAL
    defense_midfield_gap: Level = Level.NORMAL
    midfield_attack_gap: Level = Level.NORMAL
    tempo: Level = Level.NORMAL
    pass_speed: Level = Level.NORMAL
    pass_length: PassLength = PassLength.MIXED
    verticality: Level = Level.NORMAL
    passing_risk: Level = Level.NORMAL
    build_from_back: Level = Level.NORMAL
    support_closeness: Level = Level.NORMAL
    switch_play: Level = Level.NORMAL
    central_focus: Level = Level.NORMAL
    overlap_frequency: Level = Level.NORMAL
    patience: Level = Level.NORMAL
    crossing_frequency: Level = Level.NORMAL
    long_shot_frequency: Level = Level.NORMAL


@dataclass(frozen=True, slots=True)
class TransitionInstructions:
    after_loss: AfterLossBehavior = AfterLossBehavior.HOLD_SHAPE
    after_win: AfterWinBehavior = AfterWinBehavior.HOLD_POSSESSION
    transition_speed: Level = Level.NORMAL
    counterattack_risk: Level = Level.NORMAL
    goalkeeper_release_speed: Level = Level.NORMAL


@dataclass(frozen=True, slots=True)
class OutOfPossessionInstructions:
    # Shape without the ball is intentionally independent from in-possession shape.
    # This allows, for example, a wide build-up shape that collapses into a narrow
    # defensive block after possession is lost.
    defensive_line_width: Level = Level.NORMAL
    midfield_width: Level = Level.NORMAL
    attacking_line_width: Level = Level.NORMAL
    defense_midfield_gap: Level = Level.NORMAL
    midfield_attack_gap: Level = Level.NORMAL
    block_height: Level = Level.NORMAL
    defensive_line_height: Level = Level.NORMAL
    horizontal_compactness: Level = Level.NORMAL
    vertical_compactness: Level = Level.NORMAL
    pressing_intensity: Level = Level.NORMAL
    pressing_scheme: PressingScheme = PressingScheme.STANDARD
    force_direction: ForceDirection = ForceDirection.NEUTRAL
    marking_style: MarkingStyle = MarkingStyle.ZONAL
    offside_trap: bool = False
    defensive_aggression: Level = Level.NORMAL
    protect_box: Level = Level.NORMAL
    protect_centre: Level = Level.NORMAL
    cross_tolerance: Level = Level.NORMAL


@dataclass(frozen=True, slots=True)
class GameManagementInstructions:
    time_wasting: Level = Level.VERY_LOW
    risk_when_leading: Level = Level.NORMAL
    urgency_when_trailing: Level = Level.HIGH


@dataclass(frozen=True, slots=True)
class TeamInstructions:
    in_possession: InPossessionInstructions = InPossessionInstructions()
    transition: TransitionInstructions = TransitionInstructions()
    out_of_possession: OutOfPossessionInstructions = OutOfPossessionInstructions()
    game_management: GameManagementInstructions = GameManagementInstructions()


@dataclass(frozen=True, slots=True)
class PlayerInstructions:
    forward_runs: Level = Level.NORMAL
    dribbling_frequency: Level = Level.NORMAL
    crossing_frequency: Level = Level.NORMAL
    shooting_frequency: Level = Level.NORMAL
    passing_risk: Level = Level.NORMAL
    hold_up_play: Level = Level.NORMAL
    attack_space: Level = Level.NORMAL
    pressing_intensity: Level = Level.NORMAL
    defensive_tracking: Level = Level.NORMAL
    roaming: Level = Level.NORMAL
    in_possession_position: InPossessionPosition = InPossessionPosition.BASE
    out_of_possession_position: OutOfPossessionPosition = OutOfPossessionPosition.RETURN_TO_BASE
    cross_type: CrossType = CrossType.MIXED
    marking: TacticalTarget | None = None
    pressing_target: TacticalTarget | None = None


@dataclass(frozen=True, slots=True)
class PlayerInstructionOverrides:
    forward_runs: Level | None = None
    dribbling_frequency: Level | None = None
    crossing_frequency: Level | None = None
    shooting_frequency: Level | None = None
    passing_risk: Level | None = None
    hold_up_play: Level | None = None
    attack_space: Level | None = None
    pressing_intensity: Level | None = None
    defensive_tracking: Level | None = None
    roaming: Level | None = None
    in_possession_position: InPossessionPosition | None = None
    out_of_possession_position: OutOfPossessionPosition | None = None
    cross_type: CrossType | None = None
    marking: TacticalTarget | None = None
    pressing_target: TacticalTarget | None = None

    def values_to_apply(self) -> dict[str, object]:
        values: dict[str, object] = {}
        for item in fields(self):
            value = getattr(self, item.name)
            if value is not None:
                values[item.name] = value
        return values


def apply_player_overrides(
    base: PlayerInstructions,
    overrides: PlayerInstructionOverrides,
) -> PlayerInstructions:
    """Return effective instructions without mutating the role preset."""

    values = overrides.values_to_apply()
    if not values:
        return base
    return replace(base, **values)
