from __future__ import annotations

from dataclasses import dataclass


DEFAULT_TIMESTEP_SECONDS = 0.25


@dataclass(slots=True)
class MatchClock:
    """Fixed-timestep match clock.

    The clock stores an integer tick count and derives elapsed time from it. This
    avoids accumulated floating-point drift and keeps playback chunking separate
    from simulation precision.
    """

    tick_seconds: float = DEFAULT_TIMESTEP_SECONDS
    tick_count: int = 0

    def __post_init__(self) -> None:
        if self.tick_seconds <= 0:
            raise ValueError("tick_seconds must be positive")
        if self.tick_count < 0:
            raise ValueError("tick_count must be non-negative")

    @property
    def elapsed_seconds(self) -> float:
        return self.tick_count * self.tick_seconds

    @property
    def minute(self) -> int:
        return int(self.elapsed_seconds // 60)

    @property
    def second(self) -> int:
        return int(self.elapsed_seconds % 60)

    @property
    def display(self) -> str:
        return f"{self.minute:02d}:{self.second:02d}"

    def advance(self, ticks: int = 1) -> None:
        if ticks < 0:
            raise ValueError("ticks must be non-negative")
        self.tick_count += ticks
