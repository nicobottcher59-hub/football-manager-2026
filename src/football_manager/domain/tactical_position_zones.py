"""TS-19 editor placement ranges, not new football/simulation coefficients.

Coordinates face the opponent's goal at y=0. Overlapping bands deliberately
permit neighbouring positions on boundaries; side restrictions distinguish
left/right assignments. Existing saved tactics and automatic phase movements
are not rewritten. The keeper remains the keeper in either phase. LM/RM are UI names for
the existing LW/RW football positions in the middle third of each flank.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import isfinite

from .enums import Position
from .tactical_shapes import PITCH_MIN, PITCH_MAX


@dataclass(frozen=True, slots=True)
class PositionZone:
    position: Position
    label: str
    x_min: float
    x_max: float
    y_min: float
    y_max: float
    display_position: str | None = None

    def contains(self, x: float, y: float) -> bool:
        # Browser percentages are serialized to four decimals (six normalized).
        epsilon = 1e-7
        return (self.x_min - epsilon <= x <= self.x_max + epsilon
                and self.y_min - epsilon <= y <= self.y_max + epsilon)


POSITION_ZONES = (
    PositionZone(Position.ST, 'Striker', .28, .72, .04, .31),
    PositionZone(Position.SS, 'Second striker', .23, .77, .16, .39),
    PositionZone(Position.AM, 'Attacking midfielder', .22, .78, .25, .49),
    PositionZone(Position.LW, 'Left winger', .04, .36, .04, .36),
    PositionZone(Position.RW, 'Right winger', .64, .96, .04, .36),
    # UI-only aliases: still commit LW/RW so the role, familiarity and save
    # formats keep using the positions that the simulation already supports.
    PositionZone(Position.LW, 'Left midfielder', .04, .36, .36, .60, 'LM'),
    PositionZone(Position.RW, 'Right midfielder', .64, .96, .36, .60, 'RM'),
    PositionZone(Position.LCM, 'Left central midfielder', .15, .52, .38, .66),
    PositionZone(Position.CM, 'Central midfielder', .30, .70, .38, .66),
    PositionZone(Position.RCM, 'Right central midfielder', .48, .85, .38, .66),
    PositionZone(Position.DM, 'Defensive midfielder', .20, .80, .55, .79),
    PositionZone(Position.LWB, 'Left wing-back', .04, .32, .48, .78),
    PositionZone(Position.RWB, 'Right wing-back', .68, .96, .48, .78),
    PositionZone(Position.LB, 'Left-back', .04, .30, .70, .96),
    PositionZone(Position.RB, 'Right-back', .70, .96, .70, .96),
    PositionZone(Position.LCB, 'Left centre-back', .15, .52, .71, .96),
    PositionZone(Position.CB, 'Centre-back', .27, .73, .71, .96),
    PositionZone(Position.RCB, 'Right centre-back', .48, .85, .71, .96),
)


def position_options(x: float, y: float, *, goalkeeper: bool = False) -> tuple[Position, ...]:
    """Offer only positions in the dropped area; never silently choose one."""
    for value in (x, y):
        if (type(value) not in (int, float) or not isfinite(value)
                or not PITCH_MIN <= value <= PITCH_MAX):
            raise ValueError('placement must be inside the pitch margins')
    if goalkeeper:
        return (Position.GK,)
    return tuple(dict.fromkeys(zone.position for zone in POSITION_ZONES if zone.contains(x, y)))


def position_zone_read_model() -> list[dict]:
    """The browser uses this exact configuration, not a second hardcoded map."""
    return [dict(position=z.position.value, display_position=z.display_position or z.position.value,
                 label=z.label, x_min=z.x_min, x_max=z.x_max, y_min=z.y_min, y_max=z.y_max)
            for z in POSITION_ZONES]
