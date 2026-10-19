from __future__ import annotations

from dataclasses import dataclass
from math import hypot


@dataclass(frozen=True, slots=True)
class Vector2:
    """Small immutable 2D vector used by the spatial match engine."""

    x: float
    y: float

    @classmethod
    def zero(cls) -> "Vector2":
        return cls(0.0, 0.0)

    def __add__(self, other: "Vector2") -> "Vector2":
        return Vector2(self.x + other.x, self.y + other.y)

    def __sub__(self, other: "Vector2") -> "Vector2":
        return Vector2(self.x - other.x, self.y - other.y)

    def scale(self, factor: float) -> "Vector2":
        return Vector2(self.x * factor, self.y * factor)

    @property
    def magnitude(self) -> float:
        return hypot(self.x, self.y)

    def normalized(self) -> "Vector2":
        magnitude = self.magnitude
        if magnitude == 0.0:
            return Vector2.zero()
        return Vector2(self.x / magnitude, self.y / magnitude)

    def distance_to(self, other: "Vector2") -> float:
        return hypot(self.x - other.x, self.y - other.y)
