"""Immutable phase-specific targets, expressed in the manager's pitch view.

x: left touchline (0) -> right touchline (1).
y: opponent goal (0) -> own goal (1).
A target changes spatial occupation, NEVER a player's football position or role.
Only explicitly anchored slots override automatic role/team positioning.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import isfinite

PHASES = ('in_possession', 'out_of_possession')
PITCH_MIN = 0.04
PITCH_MAX = 0.96


@dataclass(frozen=True, slots=True)
class SlotPoint:
    slot_id: str
    x: float
    y: float

    def __post_init__(self) -> None:
        if not isinstance(self.slot_id, str) or not self.slot_id.strip():
            raise ValueError('a tactical point needs a slot ID')
        for value in (self.x, self.y):
            if type(value) not in (int, float) or not isfinite(value):
                raise ValueError('tactical coordinates must be finite numbers')
            if not PITCH_MIN <= value <= PITCH_MAX:
                raise ValueError('tactical coordinates must remain within the pitch margins')


@dataclass(frozen=True, slots=True)
class PhaseShape:
    phase: str
    points: tuple[SlotPoint, ...] = ()

    def __post_init__(self) -> None:
        if self.phase not in PHASES:
            raise ValueError('unknown tactical phase')
        if not isinstance(self.points, tuple) or any(not isinstance(p, SlotPoint) for p in self.points):
            raise ValueError('phase targets must be a tuple of SlotPoint values')
        if len({p.slot_id for p in self.points}) != len(self.points):
            raise ValueError('duplicate phase target')
        if len(self.points) > 11:
            raise ValueError('too many tactical targets')
        for point in self.points:
            point.__post_init__()

    def point(self, slot_id: str) -> SlotPoint | None:
        return next((p for p in self.points if p.slot_id == slot_id), None)


def validate_shapes(shapes: tuple[PhaseShape, ...], slot_ids: frozenset[str]) -> None:
    if not isinstance(shapes, tuple) or any(not isinstance(s, PhaseShape) for s in shapes):
        raise ValueError('phase shapes must be an immutable tuple')
    if len({s.phase for s in shapes}) != len(shapes):
        raise ValueError('duplicate tactical phase')
    for shape in shapes:
        shape.__post_init__()
        if any(p.slot_id not in slot_ids for p in shape.points):
            raise ValueError('phase target refers to an unknown formation slot')


def phase_target(shapes: tuple[PhaseShape, ...], phase: str, slot_id: str) -> SlotPoint | None:
    return next((point for shape in shapes if shape.phase == phase
                 for point in shape.points if point.slot_id == slot_id), None)
