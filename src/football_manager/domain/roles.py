from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .enums import Position
from .player import Player
from .tactical_instructions import (
    InPossessionPosition,
    Level,
    OutOfPossessionPosition,
    PlayerInstructions,
)


@dataclass(frozen=True, slots=True)
class RoleDefinition:
    role_id: str
    name: str
    compatible_positions: frozenset[Position]
    default_instructions: PlayerInstructions
    attribute_weights: tuple[tuple[str, float], ...]

    def __post_init__(self) -> None:
        if not self.role_id.strip():
            raise ValueError("role_id cannot be empty")
        if not self.name.strip():
            raise ValueError("role name cannot be empty")
        if not self.compatible_positions:
            raise ValueError("a role must support at least one position")
        if not self.attribute_weights:
            raise ValueError("a role must define attribute weights")
        if any(weight <= 0 for _, weight in self.attribute_weights):
            raise ValueError("role attribute weights must be positive")

    def supports(self, position: Position) -> bool:
        return position in self.compatible_positions


def _weights(*items: tuple[str, float]) -> tuple[tuple[str, float], ...]:
    return items


def _positions(*positions: Position) -> frozenset[Position]:
    return frozenset(positions)


def _build_role_catalog() -> dict[str, RoleDefinition]:
    roles = [
        # Goalkeepers
        RoleDefinition(
            "goalkeeper",
            "Goalkeeper",
            _positions(Position.GK),
            PlayerInstructions(
                forward_runs=Level.VERY_LOW,
                pressing_intensity=Level.VERY_LOW,
                defensive_tracking=Level.VERY_HIGH,
            ),
            _weights(
                ("goalkeeping.handling", 2.0),
                ("goalkeeping.reflexes", 2.0),
                ("goalkeeping.goalkeeper_positioning", 2.0),
                ("mental.concentration", 1.0),
            ),
        ),
        RoleDefinition(
            "shot_stopper",
            "Shot Stopper",
            _positions(Position.GK),
            PlayerInstructions(
                forward_runs=Level.VERY_LOW,
                pressing_intensity=Level.VERY_LOW,
                defensive_tracking=Level.VERY_HIGH,
                passing_risk=Level.VERY_LOW,
            ),
            _weights(
                ("goalkeeping.reflexes", 2.5),
                ("goalkeeping.one_on_ones", 2.0),
                ("goalkeeping.handling", 1.5),
                ("mental.anticipation", 1.0),
            ),
        ),
        RoleDefinition(
            "sweeper_keeper",
            "Sweeper Keeper",
            _positions(Position.GK),
            PlayerInstructions(
                forward_runs=Level.HIGH,
                pressing_intensity=Level.HIGH,
                passing_risk=Level.NORMAL,
                in_possession_position=InPossessionPosition.ADVANCE,
                out_of_possession_position=OutOfPossessionPosition.STEP_UP,
            ),
            _weights(
                ("goalkeeping.one_on_ones", 1.5),
                ("goalkeeping.kicking", 1.5),
                ("physical.acceleration", 1.0),
                ("mental.anticipation", 1.5),
                ("mental.decisions", 1.5),
            ),
        ),
        RoleDefinition(
            "distributor_keeper",
            "Distributor Keeper",
            _positions(Position.GK),
            PlayerInstructions(
                passing_risk=Level.HIGH,
                in_possession_position=InPossessionPosition.ADVANCE,
            ),
            _weights(
                ("goalkeeping.kicking", 2.0),
                ("goalkeeping.throwing", 1.5),
                ("technical.passing", 1.5),
                ("mental.vision", 1.0),
                ("mental.decisions", 1.5),
            ),
        ),
        RoleDefinition(
            "aggressive_keeper",
            "Aggressive Keeper",
            _positions(Position.GK),
            PlayerInstructions(
                forward_runs=Level.VERY_HIGH,
                pressing_intensity=Level.VERY_HIGH,
                in_possession_position=InPossessionPosition.ADVANCE,
                out_of_possession_position=OutOfPossessionPosition.STEP_UP,
            ),
            _weights(
                ("goalkeeping.one_on_ones", 2.0),
                ("goalkeeping.aerial_reach", 1.0),
                ("physical.acceleration", 1.5),
                ("mental.anticipation", 1.5),
                ("mental.bravery", 1.0),
            ),
        ),
        # Centre-backs
        RoleDefinition(
            "central_defender",
            "Central Defender",
            _positions(Position.CB, Position.RCB, Position.LCB),
            PlayerInstructions(
                forward_runs=Level.VERY_LOW,
                dribbling_frequency=Level.VERY_LOW,
                passing_risk=Level.LOW,
                defensive_tracking=Level.VERY_HIGH,
            ),
            _weights(
                ("technical.marking", 1.5),
                ("technical.tackling", 1.5),
                ("mental.positioning", 1.5),
                ("mental.concentration", 1.0),
                ("physical.strength", 1.0),
                ("physical.jumping_reach", 1.0),
            ),
        ),
        RoleDefinition(
            "stopper",
            "Stopper",
            _positions(Position.CB, Position.RCB, Position.LCB),
            PlayerInstructions(
                forward_runs=Level.LOW,
                pressing_intensity=Level.VERY_HIGH,
                defensive_tracking=Level.VERY_HIGH,
                out_of_possession_position=OutOfPossessionPosition.STEP_UP,
            ),
            _weights(
                ("technical.tackling", 1.5),
                ("mental.aggression", 1.5),
                ("mental.bravery", 1.0),
                ("mental.anticipation", 1.0),
                ("physical.strength", 1.5),
            ),
        ),
        RoleDefinition(
            "covering_defender",
            "Covering Defender",
            _positions(Position.CB, Position.RCB, Position.LCB),
            PlayerInstructions(
                forward_runs=Level.VERY_LOW,
                pressing_intensity=Level.LOW,
                defensive_tracking=Level.VERY_HIGH,
                out_of_possession_position=OutOfPossessionPosition.DROP,
            ),
            _weights(
                ("mental.anticipation", 1.5),
                ("mental.positioning", 1.5),
                ("physical.pace", 1.5),
                ("physical.acceleration", 1.0),
                ("technical.marking", 1.0),
            ),
        ),
        RoleDefinition(
            "ball_playing_defender",
            "Ball Playing Defender",
            _positions(Position.CB, Position.RCB, Position.LCB),
            PlayerInstructions(
                forward_runs=Level.LOW,
                passing_risk=Level.HIGH,
                dribbling_frequency=Level.LOW,
                defensive_tracking=Level.HIGH,
            ),
            _weights(
                ("technical.passing", 1.5),
                ("technical.first_touch", 1.0),
                ("mental.vision", 1.0),
                ("mental.decisions", 1.5),
                ("technical.marking", 1.0),
                ("technical.tackling", 1.0),
            ),
        ),
        RoleDefinition(
            "wide_center_back",
            "Wide Centre-Back",
            _positions(Position.CB, Position.RCB, Position.LCB),
            PlayerInstructions(
                forward_runs=Level.HIGH,
                dribbling_frequency=Level.NORMAL,
                passing_risk=Level.NORMAL,
                in_possession_position=InPossessionPosition.WIDE,
                defensive_tracking=Level.HIGH,
            ),
            _weights(
                ("physical.pace", 1.0),
                ("physical.stamina", 1.0),
                ("technical.passing", 1.0),
                ("technical.tackling", 1.0),
                ("mental.decisions", 1.0),
                ("mental.positioning", 1.0),
            ),
        ),
        # Full-backs
        RoleDefinition(
            "defensive_fullback",
            "Defensive Full-Back",
            _positions(Position.RB, Position.LB),
            PlayerInstructions(
                forward_runs=Level.VERY_LOW,
                crossing_frequency=Level.LOW,
                dribbling_frequency=Level.LOW,
                defensive_tracking=Level.VERY_HIGH,
            ),
            _weights(
                ("technical.tackling", 1.6),
                ("technical.marking", 1.5),
                ("mental.positioning", 1.5),
                ("mental.decisions", 0.8),
                ("technical.passing", 0.8),
                ("physical.pace", 0.9),
                ("physical.stamina", 1.0),
            ),
        ),
        RoleDefinition(
            "balanced_fullback",
            "Balanced Full-Back",
            _positions(Position.RB, Position.LB),
            PlayerInstructions(
                forward_runs=Level.NORMAL,
                crossing_frequency=Level.NORMAL,
                dribbling_frequency=Level.NORMAL,
                defensive_tracking=Level.HIGH,
            ),
            _weights(
                ("technical.tackling", 1.0),
                ("technical.crossing", 1.0),
                ("technical.passing", 1.0),
                ("physical.pace", 1.0),
                ("physical.stamina", 1.0),
                ("mental.decisions", 1.0),
            ),
        ),
        RoleDefinition(
            "wingback",
            "Wing-Back",
            _positions(Position.RB, Position.LB, Position.RWB, Position.LWB),
            PlayerInstructions(
                forward_runs=Level.HIGH,
                crossing_frequency=Level.HIGH,
                dribbling_frequency=Level.NORMAL,
                attack_space=Level.HIGH,
                defensive_tracking=Level.HIGH,
                in_possession_position=InPossessionPosition.WIDE,
            ),
            _weights(
                ("physical.stamina", 1.5),
                ("physical.pace", 1.5),
                ("technical.crossing", 1.5),
                ("technical.dribbling", 1.0),
                ("mental.work_rate", 1.0),
            ),
        ),
        RoleDefinition(
            "inverted_fullback",
            "Inverted Full-Back",
            _positions(Position.RB, Position.LB),
            PlayerInstructions(
                forward_runs=Level.LOW,
                passing_risk=Level.NORMAL,
                defensive_tracking=Level.VERY_HIGH,
                in_possession_position=InPossessionPosition.MIDFIELD,
            ),
            _weights(
                ("technical.passing", 1.5),
                ("technical.first_touch", 1.0),
                ("mental.decisions", 1.5),
                ("mental.tactical_intelligence", 1.5),
                ("technical.tackling", 1.0),
            ),
        ),
        RoleDefinition(
            "inverted_wingback",
            "Inverted Wing-Back",
            _positions(Position.RB, Position.LB, Position.RWB, Position.LWB),
            PlayerInstructions(
                forward_runs=Level.HIGH,
                dribbling_frequency=Level.NORMAL,
                passing_risk=Level.HIGH,
                attack_space=Level.HIGH,
                in_possession_position=InPossessionPosition.MIDFIELD,
            ),
            _weights(
                ("technical.passing", 1.5),
                ("technical.dribbling", 1.0),
                ("technical.first_touch", 1.0),
                ("mental.vision", 1.0),
                ("mental.tactical_intelligence", 1.5),
                ("physical.stamina", 1.0),
            ),
        ),
        # Wing-backs specific alternatives
        RoleDefinition(
            "defensive_wingback",
            "Defensive Wing-Back",
            _positions(Position.RWB, Position.LWB),
            PlayerInstructions(
                forward_runs=Level.LOW,
                crossing_frequency=Level.NORMAL,
                defensive_tracking=Level.VERY_HIGH,
                in_possession_position=InPossessionPosition.WIDE,
            ),
            _weights(
                ("technical.tackling", 1.5),
                ("technical.marking", 1.0),
                ("physical.pace", 1.0),
                ("physical.stamina", 1.5),
                ("mental.work_rate", 1.0),
            ),
        ),
        RoleDefinition(
            "attacking_wingback",
            "Attacking Wing-Back",
            _positions(Position.RWB, Position.LWB),
            PlayerInstructions(
                forward_runs=Level.VERY_HIGH,
                crossing_frequency=Level.VERY_HIGH,
                dribbling_frequency=Level.HIGH,
                attack_space=Level.VERY_HIGH,
                in_possession_position=InPossessionPosition.WIDE,
            ),
            _weights(
                ("physical.pace", 1.5),
                ("physical.stamina", 1.5),
                ("technical.crossing", 1.5),
                ("technical.dribbling", 1.5),
                ("mental.off_the_ball", 1.0),
            ),
        ),
        RoleDefinition(
            "wide_playmaker_wingback",
            "Wide Playmaker Wing-Back",
            _positions(Position.RWB, Position.LWB),
            PlayerInstructions(
                forward_runs=Level.NORMAL,
                passing_risk=Level.HIGH,
                roaming=Level.HIGH,
                in_possession_position=InPossessionPosition.INSIDE,
            ),
            _weights(
                ("technical.passing", 1.5),
                ("technical.technique", 1.5),
                ("mental.vision", 1.5),
                ("mental.decisions", 1.0),
                ("physical.stamina", 1.0),
            ),
        ),
        # Defensive midfielders
        RoleDefinition(
            "anchor",
            "Anchor",
            _positions(Position.DM),
            PlayerInstructions(
                forward_runs=Level.VERY_LOW,
                passing_risk=Level.LOW,
                defensive_tracking=Level.VERY_HIGH,
                roaming=Level.VERY_LOW,
            ),
            _weights(
                ("mental.positioning", 1.5),
                ("mental.anticipation", 1.0),
                ("technical.tackling", 1.5),
                ("technical.marking", 1.0),
                ("mental.concentration", 1.0),
            ),
        ),
        RoleDefinition(
            "holding_midfielder",
            "Holding Midfielder",
            _positions(Position.DM),
            PlayerInstructions(
                forward_runs=Level.LOW,
                passing_risk=Level.NORMAL,
                defensive_tracking=Level.HIGH,
            ),
            _weights(
                ("technical.passing", 1.0),
                ("technical.tackling", 1.0),
                ("mental.positioning", 1.0),
                ("mental.decisions", 1.0),
                ("mental.teamwork", 1.0),
            ),
        ),
        RoleDefinition(
            "deep_lying_playmaker",
            "Deep-Lying Playmaker",
            _positions(Position.DM),
            PlayerInstructions(
                forward_runs=Level.LOW,
                passing_risk=Level.HIGH,
                roaming=Level.LOW,
                defensive_tracking=Level.NORMAL,
            ),
            _weights(
                ("technical.passing", 2.0),
                ("technical.first_touch", 1.0),
                ("mental.vision", 1.5),
                ("mental.decisions", 1.5),
                ("mental.composure", 1.0),
            ),
        ),
        RoleDefinition(
            "ball_winning_midfielder",
            "Ball-Winning Midfielder",
            _positions(Position.DM, Position.CM, Position.RCM, Position.LCM),
            PlayerInstructions(
                forward_runs=Level.NORMAL,
                pressing_intensity=Level.VERY_HIGH,
                defensive_tracking=Level.VERY_HIGH,
                passing_risk=Level.LOW,
            ),
            _weights(
                ("technical.tackling", 1.5),
                ("mental.aggression", 1.5),
                ("mental.work_rate", 1.5),
                ("physical.stamina", 1.5),
                ("mental.anticipation", 1.0),
            ),
        ),
        RoleDefinition(
            "half_back",
            "Half-Back",
            _positions(Position.DM),
            PlayerInstructions(
                forward_runs=Level.VERY_LOW,
                passing_risk=Level.NORMAL,
                defensive_tracking=Level.VERY_HIGH,
                in_possession_position=InPossessionPosition.DROP_DEEP,
            ),
            _weights(
                ("technical.passing", 1.0),
                ("technical.tackling", 1.0),
                ("mental.positioning", 1.5),
                ("mental.tactical_intelligence", 1.5),
                ("mental.decisions", 1.0),
            ),
        ),
        # Central midfielders
        RoleDefinition(
            "central_midfielder",
            "Central Midfielder",
            _positions(Position.CM, Position.RCM, Position.LCM),
            PlayerInstructions(),
            _weights(
                ("technical.passing", 1.0),
                ("technical.first_touch", 1.0),
                ("mental.decisions", 1.0),
                ("mental.teamwork", 1.0),
                ("physical.stamina", 1.0),
            ),
        ),
        RoleDefinition(
            "box_to_box",
            "Box-to-Box Midfielder",
            _positions(Position.CM, Position.RCM, Position.LCM),
            PlayerInstructions(
                forward_runs=Level.HIGH,
                attack_space=Level.HIGH,
                pressing_intensity=Level.HIGH,
                defensive_tracking=Level.VERY_HIGH,
            ),
            _weights(
                ("physical.stamina", 2.0),
                ("mental.work_rate", 1.5),
                ("technical.passing", 1.0),
                ("technical.tackling", 1.0),
                ("mental.off_the_ball", 1.0),
            ),
        ),
        RoleDefinition(
            "central_playmaker",
            "Central Playmaker",
            _positions(Position.CM, Position.RCM, Position.LCM),
            PlayerInstructions(
                passing_risk=Level.HIGH,
                roaming=Level.NORMAL,
                pressing_intensity=Level.LOW,
            ),
            _weights(
                ("technical.passing", 1.5),
                ("technical.technique", 1.0),
                ("mental.vision", 1.5),
                ("mental.creativity", 1.5),
                ("mental.decisions", 1.0),
            ),
        ),
        RoleDefinition(
            "mezzala",
            "Mezzala",
            _positions(Position.CM, Position.RCM, Position.LCM),
            PlayerInstructions(
                forward_runs=Level.HIGH,
                dribbling_frequency=Level.HIGH,
                attack_space=Level.HIGH,
                roaming=Level.HIGH,
                in_possession_position=InPossessionPosition.WIDE,
            ),
            _weights(
                ("technical.dribbling", 1.5),
                ("technical.passing", 1.0),
                ("mental.off_the_ball", 1.5),
                ("mental.creativity", 1.0),
                ("physical.agility", 1.0),
            ),
        ),
        # Attacking midfielders
        RoleDefinition(
            "attacking_midfielder",
            "Attacking Midfielder",
            _positions(Position.AM),
            PlayerInstructions(
                forward_runs=Level.HIGH,
                attack_space=Level.HIGH,
                passing_risk=Level.NORMAL,
            ),
            _weights(
                ("technical.first_touch", 1.0),
                ("technical.passing", 1.0),
                ("mental.off_the_ball", 1.0),
                ("mental.decisions", 1.0),
                ("mental.creativity", 1.0),
            ),
        ),
        RoleDefinition(
            "advanced_playmaker",
            "Advanced Playmaker",
            _positions(Position.AM),
            PlayerInstructions(
                passing_risk=Level.VERY_HIGH,
                roaming=Level.HIGH,
                forward_runs=Level.NORMAL,
            ),
            _weights(
                ("technical.passing", 1.5),
                ("technical.technique", 1.0),
                ("mental.vision", 2.0),
                ("mental.creativity", 1.5),
                ("mental.decisions", 1.0),
            ),
        ),
        RoleDefinition(
            "shadow_striker",
            "Shadow Striker",
            _positions(Position.AM, Position.SS),
            PlayerInstructions(
                forward_runs=Level.VERY_HIGH,
                attack_space=Level.VERY_HIGH,
                shooting_frequency=Level.HIGH,
                pressing_intensity=Level.HIGH,
                in_possession_position=InPossessionPosition.ADVANCE,
            ),
            _weights(
                ("technical.finishing", 1.5),
                ("mental.off_the_ball", 1.5),
                ("mental.anticipation", 1.0),
                ("physical.acceleration", 1.0),
                ("mental.composure", 1.0),
            ),
        ),
        RoleDefinition(
            "roaming_playmaker",
            "Roaming Playmaker",
            _positions(Position.AM),
            PlayerInstructions(
                passing_risk=Level.HIGH,
                roaming=Level.VERY_HIGH,
                dribbling_frequency=Level.HIGH,
                defensive_tracking=Level.NORMAL,
                in_possession_position=InPossessionPosition.FREE,
            ),
            _weights(
                ("technical.passing", 1.5),
                ("technical.dribbling", 1.0),
                ("mental.vision", 1.5),
                ("mental.creativity", 1.5),
                ("physical.stamina", 1.0),
            ),
        ),
        RoleDefinition(
            "enganche",
            "Enganche",
            _positions(Position.AM),
            PlayerInstructions(
                forward_runs=Level.LOW,
                passing_risk=Level.VERY_HIGH,
                roaming=Level.LOW,
                pressing_intensity=Level.VERY_LOW,
                defensive_tracking=Level.VERY_LOW,
            ),
            _weights(
                ("technical.passing", 1.5),
                ("technical.technique", 1.5),
                ("technical.first_touch", 1.0),
                ("mental.vision", 2.0),
                ("mental.creativity", 1.5),
            ),
        ),
        # Wide attackers
        RoleDefinition(
            "winger",
            "Winger",
            _positions(Position.RW, Position.LW),
            PlayerInstructions(
                forward_runs=Level.HIGH,
                dribbling_frequency=Level.HIGH,
                crossing_frequency=Level.HIGH,
                attack_space=Level.HIGH,
                in_possession_position=InPossessionPosition.WIDE,
            ),
            _weights(
                ("physical.pace", 1.5),
                ("physical.acceleration", 1.0),
                ("technical.dribbling", 1.5),
                ("technical.crossing", 1.5),
                ("mental.off_the_ball", 1.0),
            ),
        ),
        RoleDefinition(
            "inverted_winger",
            "Inverted Winger",
            _positions(Position.RW, Position.LW),
            PlayerInstructions(
                forward_runs=Level.HIGH,
                dribbling_frequency=Level.HIGH,
                crossing_frequency=Level.NORMAL,
                shooting_frequency=Level.NORMAL,
                attack_space=Level.HIGH,
                in_possession_position=InPossessionPosition.INSIDE,
            ),
            _weights(
                ("technical.dribbling", 1.5),
                ("technical.technique", 1.0),
                ("technical.passing", 1.0),
                ("mental.off_the_ball", 1.0),
                ("physical.acceleration", 1.0),
            ),
        ),
        RoleDefinition(
            "inside_forward",
            "Inside Forward",
            _positions(Position.RW, Position.LW),
            PlayerInstructions(
                forward_runs=Level.VERY_HIGH,
                dribbling_frequency=Level.HIGH,
                crossing_frequency=Level.LOW,
                shooting_frequency=Level.HIGH,
                attack_space=Level.VERY_HIGH,
                in_possession_position=InPossessionPosition.INSIDE,
            ),
            _weights(
                ("technical.finishing", 1.5),
                ("technical.dribbling", 1.5),
                ("mental.off_the_ball", 1.5),
                ("physical.acceleration", 1.0),
                ("mental.composure", 1.0),
            ),
        ),
        RoleDefinition(
            "wide_playmaker",
            "Wide Playmaker",
            _positions(Position.RW, Position.LW),
            PlayerInstructions(
                forward_runs=Level.NORMAL,
                dribbling_frequency=Level.NORMAL,
                crossing_frequency=Level.LOW,
                passing_risk=Level.VERY_HIGH,
                roaming=Level.HIGH,
                in_possession_position=InPossessionPosition.INSIDE,
            ),
            _weights(
                ("technical.passing", 1.5),
                ("technical.technique", 1.0),
                ("mental.vision", 1.5),
                ("mental.creativity", 1.5),
                ("technical.first_touch", 1.0),
            ),
        ),
        RoleDefinition(
            "defensive_winger",
            "Defensive Winger",
            _positions(Position.RW, Position.LW),
            PlayerInstructions(
                forward_runs=Level.NORMAL,
                dribbling_frequency=Level.NORMAL,
                crossing_frequency=Level.NORMAL,
                pressing_intensity=Level.VERY_HIGH,
                defensive_tracking=Level.VERY_HIGH,
                in_possession_position=InPossessionPosition.WIDE,
            ),
            _weights(
                ("mental.work_rate", 1.5),
                ("physical.stamina", 1.5),
                ("technical.tackling", 1.0),
                ("physical.pace", 1.0),
                ("technical.crossing", 1.0),
            ),
        ),
        # Second strikers
        RoleDefinition(
            "second_striker",
            "Second Striker",
            _positions(Position.SS),
            PlayerInstructions(
                forward_runs=Level.HIGH,
                attack_space=Level.HIGH,
                shooting_frequency=Level.HIGH,
                passing_risk=Level.NORMAL,
            ),
            _weights(
                ("technical.finishing", 1.5),
                ("technical.first_touch", 1.0),
                ("mental.off_the_ball", 1.5),
                ("mental.composure", 1.0),
                ("mental.vision", 1.0),
            ),
        ),
        RoleDefinition(
            "trequartista",
            "Trequartista",
            _positions(Position.SS),
            PlayerInstructions(
                forward_runs=Level.NORMAL,
                dribbling_frequency=Level.HIGH,
                passing_risk=Level.VERY_HIGH,
                roaming=Level.VERY_HIGH,
                pressing_intensity=Level.VERY_LOW,
                defensive_tracking=Level.VERY_LOW,
                in_possession_position=InPossessionPosition.FREE,
            ),
            _weights(
                ("technical.technique", 1.5),
                ("technical.dribbling", 1.0),
                ("mental.vision", 1.5),
                ("mental.creativity", 1.5),
                ("technical.first_touch", 1.0),
            ),
        ),
        RoleDefinition(
            "pressing_second_striker",
            "Pressing Second Striker",
            _positions(Position.SS),
            PlayerInstructions(
                forward_runs=Level.HIGH,
                attack_space=Level.HIGH,
                pressing_intensity=Level.VERY_HIGH,
                defensive_tracking=Level.HIGH,
            ),
            _weights(
                ("mental.work_rate", 1.5),
                ("physical.stamina", 1.5),
                ("physical.acceleration", 1.0),
                ("mental.off_the_ball", 1.0),
                ("technical.finishing", 1.0),
            ),
        ),
        RoleDefinition(
            "roaming_forward",
            "Roaming Forward",
            _positions(Position.SS),
            PlayerInstructions(
                forward_runs=Level.HIGH,
                dribbling_frequency=Level.HIGH,
                attack_space=Level.HIGH,
                roaming=Level.VERY_HIGH,
                in_possession_position=InPossessionPosition.FREE,
            ),
            _weights(
                ("technical.dribbling", 1.0),
                ("technical.first_touch", 1.0),
                ("mental.off_the_ball", 1.5),
                ("mental.vision", 1.0),
                ("physical.agility", 1.0),
            ),
        ),
        # Strikers
        RoleDefinition(
            "advanced_forward",
            "Advanced Forward",
            _positions(Position.ST),
            PlayerInstructions(
                forward_runs=Level.VERY_HIGH,
                dribbling_frequency=Level.HIGH,
                attack_space=Level.VERY_HIGH,
                pressing_intensity=Level.HIGH,
                shooting_frequency=Level.HIGH,
                in_possession_position=InPossessionPosition.ADVANCE,
            ),
            _weights(
                ("technical.finishing", 1.5),
                ("mental.off_the_ball", 1.5),
                ("physical.acceleration", 1.5),
                ("physical.pace", 1.0),
                ("mental.composure", 1.0),
            ),
        ),
        RoleDefinition(
            "pressing_forward",
            "Pressing Forward",
            _positions(Position.ST),
            PlayerInstructions(
                forward_runs=Level.HIGH,
                attack_space=Level.HIGH,
                pressing_intensity=Level.VERY_HIGH,
                defensive_tracking=Level.HIGH,
                shooting_frequency=Level.NORMAL,
            ),
            _weights(
                ("mental.work_rate", 1.5),
                ("physical.stamina", 1.5),
                ("physical.acceleration", 1.0),
                ("mental.off_the_ball", 1.0),
                ("technical.finishing", 1.0),
            ),
        ),
        RoleDefinition(
            "target_forward",
            "Target Forward",
            _positions(Position.ST),
            PlayerInstructions(
                forward_runs=Level.LOW,
                dribbling_frequency=Level.VERY_LOW,
                hold_up_play=Level.VERY_HIGH,
                attack_space=Level.LOW,
                passing_risk=Level.LOW,
            ),
            _weights(
                ("physical.strength", 2.0),
                ("physical.jumping_reach", 1.5),
                ("technical.heading", 1.5),
                ("technical.first_touch", 1.0),
                ("mental.bravery", 1.0),
            ),
        ),
        RoleDefinition(
            "deep_lying_forward",
            "Deep-Lying Forward",
            _positions(Position.ST),
            PlayerInstructions(
                forward_runs=Level.LOW,
                hold_up_play=Level.HIGH,
                passing_risk=Level.HIGH,
                roaming=Level.NORMAL,
                in_possession_position=InPossessionPosition.DROP_DEEP,
            ),
            _weights(
                ("technical.first_touch", 1.5),
                ("technical.passing", 1.0),
                ("mental.vision", 1.0),
                ("physical.strength", 1.0),
                ("mental.decisions", 1.0),
            ),
        ),
        RoleDefinition(
            "false_nine",
            "False Nine",
            _positions(Position.ST),
            PlayerInstructions(
                forward_runs=Level.LOW,
                dribbling_frequency=Level.HIGH,
                passing_risk=Level.HIGH,
                roaming=Level.HIGH,
                pressing_intensity=Level.NORMAL,
                in_possession_position=InPossessionPosition.DROP_DEEP,
            ),
            _weights(
                ("technical.first_touch", 1.5),
                ("technical.passing", 1.5),
                ("technical.dribbling", 1.0),
                ("mental.vision", 1.5),
                ("mental.creativity", 1.0),
            ),
        ),
    ]

    catalog = {role.role_id: role for role in roles}
    if len(catalog) != len(roles):
        raise RuntimeError("duplicate role IDs in role catalog")
    return catalog


ROLE_CATALOG: dict[str, RoleDefinition] = _build_role_catalog()


DEFAULT_ROLE_BY_POSITION: dict[Position, str] = {
    Position.GK: "goalkeeper",
    Position.RB: "balanced_fullback",
    Position.RCB: "central_defender",
    Position.CB: "central_defender",
    Position.LCB: "central_defender",
    Position.LB: "balanced_fullback",
    Position.RWB: "wingback",
    Position.LWB: "wingback",
    Position.DM: "holding_midfielder",
    Position.RCM: "central_midfielder",
    Position.CM: "central_midfielder",
    Position.LCM: "central_midfielder",
    Position.AM: "attacking_midfielder",
    Position.RW: "winger",
    Position.LW: "winger",
    Position.SS: "second_striker",
    Position.ST: "advanced_forward",
}


def get_role(role_id: str) -> RoleDefinition:
    try:
        return ROLE_CATALOG[role_id]
    except KeyError as exc:
        raise KeyError(f"unknown role {role_id!r}") from exc


def roles_for_position(position: Position) -> tuple[RoleDefinition, ...]:
    return tuple(role for role in ROLE_CATALOG.values() if role.supports(position))


def default_role_for_position(position: Position) -> RoleDefinition:
    return get_role(DEFAULT_ROLE_BY_POSITION[position])


def _attribute_value(player: Player, path: str) -> float:
    group_name, attribute_name = path.split(".", maxsplit=1)
    group = getattr(player.attributes, group_name)
    if group is None:
        return 1.0
    return float(getattr(group, attribute_name))


def role_suitability(player: Player, role: RoleDefinition | str) -> float:
    """Return the attribute-fit component used by contextual OVR.

    The score is deliberately independent from positional familiarity, side/foot
    fit and current form. Contextual OVR starts from this role-specific attribute
    profile, then applies those separate assignment factors.
    """

    definition = get_role(role) if isinstance(role, str) else role
    weighted_total = 0.0
    total_weight = 0.0
    for path, weight in definition.attribute_weights:
        weighted_total += _attribute_value(player, path) * weight
        total_weight += weight
    return weighted_total / total_weight


def role_similarity(first: RoleDefinition | str, second: RoleDefinition | str) -> float:
    """Behavioral similarity used later as a basis for learning transfer."""

    a = get_role(first) if isinstance(first, str) else first
    b = get_role(second) if isinstance(second, str) else second

    numeric_fields = (
        "forward_runs",
        "dribbling_frequency",
        "crossing_frequency",
        "shooting_frequency",
        "passing_risk",
        "hold_up_play",
        "attack_space",
        "pressing_intensity",
        "defensive_tracking",
        "roaming",
    )
    penalties: list[float] = []
    for field_name in numeric_fields:
        first_value = int(getattr(a.default_instructions, field_name))
        second_value = int(getattr(b.default_instructions, field_name))
        penalties.append(abs(first_value - second_value) / 100.0)

    categorical_pairs: Iterable[tuple[object, object]] = (
        (
            a.default_instructions.in_possession_position,
            b.default_instructions.in_possession_position,
        ),
        (
            a.default_instructions.out_of_possession_position,
            b.default_instructions.out_of_possession_position,
        ),
    )
    penalties.extend(0.0 if first_value == second_value else 0.5 for first_value, second_value in categorical_pairs)

    mean_penalty = sum(penalties) / len(penalties)
    return max(0.0, min(100.0, 100.0 * (1.0 - mean_penalty)))


@dataclass(frozen=True, slots=True)
class RoleExecutionContext:
    position_familiarity: float
    role_familiarity: float
    tactic_familiarity: float
    role_suitability: float


def evaluate_role_context(
    player: Player,
    position: Position,
    role: RoleDefinition | str,
    tactic_id: str,
) -> RoleExecutionContext:
    definition = get_role(role) if isinstance(role, str) else role
    return RoleExecutionContext(
        position_familiarity=player.familiarity_for(position),
        role_familiarity=player.tactical_familiarity.role_score(definition.role_id),
        tactic_familiarity=player.tactical_familiarity.tactic_score(tactic_id),
        role_suitability=role_suitability(player, definition),
    )
