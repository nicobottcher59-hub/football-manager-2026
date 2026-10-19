from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache

from .enums import Position
from .validation import validate_non_negative, validate_range


# Missing positional entries are not always equivalent to "has never played anything
# remotely similar".  These transfer factors provide a conservative familiarity
# floor for closely related positions while leaving explicit database values in
# full control.  Goalkeeper remains isolated from every outfield position.
_POSITION_TRANSFER: dict[frozenset[Position], float] = {
    # Same line / mirrored variants.
    frozenset((Position.RCB, Position.CB)): 0.97,
    frozenset((Position.LCB, Position.CB)): 0.97,
    frozenset((Position.RCB, Position.LCB)): 0.92,
    frozenset((Position.RCM, Position.CM)): 0.97,
    frozenset((Position.LCM, Position.CM)): 0.97,
    frozenset((Position.RCM, Position.LCM)): 0.94,
    frozenset((Position.RW, Position.LW)): 0.90,
    frozenset((Position.RB, Position.LB)): 0.86,
    frozenset((Position.RWB, Position.LWB)): 0.86,
    # Same-side defensive neighbours. These are only familiarity floors; the
    # actual OVR difference is driven primarily by the role's attribute profile.
    frozenset((Position.RCB, Position.RB)): 0.58,
    frozenset((Position.LCB, Position.LB)): 0.58,
    frozenset((Position.CB, Position.RB)): 0.48,
    frozenset((Position.CB, Position.LB)): 0.48,
    # Full-back / wing-back relationships.
    frozenset((Position.RB, Position.RWB)): 0.90,
    frozenset((Position.LB, Position.LWB)): 0.90,
    frozenset((Position.RB, Position.LWB)): 0.72,
    frozenset((Position.LB, Position.RWB)): 0.72,
    # Wide players moving one line forward/back.
    frozenset((Position.RWB, Position.RW)): 0.72,
    frozenset((Position.LWB, Position.LW)): 0.72,
    frozenset((Position.RB, Position.RW)): 0.58,
    frozenset((Position.LB, Position.LW)): 0.58,
    # Central vertical neighbours.
    frozenset((Position.RCB, Position.DM)): 0.64,
    frozenset((Position.CB, Position.DM)): 0.68,
    frozenset((Position.LCB, Position.DM)): 0.64,
    frozenset((Position.DM, Position.RCM)): 0.80,
    frozenset((Position.DM, Position.CM)): 0.84,
    frozenset((Position.DM, Position.LCM)): 0.80,
    frozenset((Position.RCM, Position.AM)): 0.78,
    frozenset((Position.CM, Position.AM)): 0.82,
    frozenset((Position.LCM, Position.AM)): 0.78,
    frozenset((Position.AM, Position.SS)): 0.90,
    frozenset((Position.SS, Position.ST)): 0.88,
    frozenset((Position.AM, Position.ST)): 0.76,
    # Wide attackers can usually understand the opposite attacking channels
    # better than an unrelated defensive role, but are not automatically natural.
    frozenset((Position.RW, Position.AM)): 0.82,
    frozenset((Position.LW, Position.AM)): 0.82,
    frozenset((Position.RW, Position.SS)): 0.78,
    frozenset((Position.LW, Position.SS)): 0.78,
    frozenset((Position.RW, Position.ST)): 0.66,
    frozenset((Position.LW, Position.ST)): 0.66,
}


@lru_cache(maxsize=512)
def position_transfer_factor(source: Position, target: Position) -> float:
    """Return how much familiarity transfers between two positions.

    Explicit familiarity values always remain authoritative.  This function is
    used only when the target position has no explicit value in the player data.
    """

    source = source if isinstance(source, Position) else Position(source)
    target = target if isinstance(target, Position) else Position(target)
    if source is target:
        return 1.0
    if source is Position.GK or target is Position.GK:
        return 0.0
    return _POSITION_TRANSFER.get(frozenset((source, target)), 0.0)


@dataclass(slots=True)
class PositionalFamiliarity:
    values: dict[Position, float] = field(default_factory=dict)
    peak_values: dict[Position, float] = field(default_factory=dict)
    unused_minutes: dict[Position, float] = field(default_factory=dict)
    played_minutes: dict[Position, float] = field(default_factory=dict)

    def __post_init__(self) -> None:
        normalized: dict[Position, float] = {}
        for position, value in self.values.items():
            pos = position if isinstance(position, Position) else Position(position)
            normalized[pos] = validate_range(f"familiarity[{pos}]", float(value), 0.0, 100.0)
        self.values = normalized

        peaks: dict[Position, float] = {}
        for position, value in self.peak_values.items():
            pos = position if isinstance(position, Position) else Position(position)
            peaks[pos] = validate_range(f"peak_familiarity[{pos}]", float(value), 0.0, 100.0)
        for position, value in self.values.items():
            peaks[position] = max(value, peaks.get(position, value))
        self.peak_values = peaks

        inactivity: dict[Position, float] = {}
        for position, minutes in self.unused_minutes.items():
            pos = position if isinstance(position, Position) else Position(position)
            inactivity[pos] = validate_non_negative(f"unused_minutes[{pos}]", float(minutes))
        self.unused_minutes = inactivity

        minutes_played: dict[Position, float] = {}
        for position, minutes in self.played_minutes.items():
            pos = position if isinstance(position, Position) else Position(position)
            minutes_played[pos] = validate_non_negative(f"played_minutes[{pos}]", float(minutes))
        # Positions shipped explicitly in the database are treated as established
        # knowledge. Newly inferred positions must earn their secondary label by
        # accumulating real match minutes.
        for position, score in self.values.items():
            if position not in minutes_played:
                minutes_played[position] = 900.0 if score >= 70.0 else 0.0
        self.played_minutes = minutes_played

    def score(self, position: Position) -> float:
        """Return the explicit stored familiarity for a position."""

        position = position if isinstance(position, Position) else Position(position)
        return self.values.get(position, 0.0)

    def _inferred_score(self, position: Position) -> float:
        inferred = (
            source_score * position_transfer_factor(source_position, position)
            for source_position, source_score in self.values.items()
            if source_position is not position
        )
        return max(inferred, default=0.0)

    def effective_score(self, position: Position) -> float:
        """Return stored familiarity or a conservative spatial transfer floor.

        Explicit database/learned values remain the main record. Closely related
        positions can still supply a floor, which prevents a learned mirrored
        position from decaying below what the player's current spatial knowledge
        would reasonably transfer.
        """

        position = position if isinstance(position, Position) else Position(position)
        if position in self.values:
            return self.values[position]
        return self._inferred_score(position)

    def set_score(self, position: Position, value: float) -> None:
        position = position if isinstance(position, Position) else Position(position)
        value = validate_range(f"familiarity[{position}]", value, 0.0, 100.0)
        self.values[position] = value
        self.peak_values[position] = max(value, self.peak_values.get(position, value))
        self.unused_minutes.setdefault(position, 0.0)
        self.played_minutes.setdefault(position, 0.0)

    def improve(self, position: Position, amount: float) -> float:
        validate_non_negative("familiarity improvement", amount)
        position = position if isinstance(position, Position) else Position(position)
        updated = min(100.0, self.score(position) + amount)
        self.set_score(position, updated)
        return updated

    def record_minutes(
        self,
        position: Position,
        minutes: float,
        *,
        adaptability: float = 65.0,
        decay_grace_minutes: float = 900.0,
    ) -> float:
        """Learn the played position and slowly forget unused ones.

        The learning curve has diminishing returns and starts from transferable
        familiarity when a nearby position is new. Adaptability changes learning
        speed. Unused positions get a roughly ten-full-match grace window before
        slow decay begins, and historical peak familiarity creates a long-term
        memory floor so a converted player never completely forgets an old job.
        """

        position = position if isinstance(position, Position) else Position(position)
        minutes = validate_range("position minutes", float(minutes), 0.0, 120.0)
        adaptability = validate_range("adaptability", float(adaptability), 0.0, 100.0)
        decay_grace_minutes = validate_non_negative("decay grace minutes", decay_grace_minutes)
        if minutes <= 0.0:
            return self.effective_score(position)

        starting_score = self.effective_score(position)
        if position not in self.values:
            self.values[position] = starting_score
            self.peak_values[position] = starting_score

        # Faster early learning, progressively harder near natural mastery.
        per_90_gain = 0.45 + 0.75 * ((100.0 - starting_score) / 100.0)
        adaptability_factor = 0.65 + 0.70 * (adaptability / 100.0)
        gain = (minutes / 90.0) * per_90_gain * adaptability_factor
        learned = min(100.0, starting_score + gain)
        self.values[position] = learned
        self.peak_values[position] = max(learned, self.peak_values.get(position, learned))
        self.unused_minutes[position] = 0.0
        self.played_minutes[position] = self.played_minutes.get(position, 0.0) + minutes

        for other in tuple(self.values):
            if other is position:
                continue
            previous_unused = self.unused_minutes.get(other, 0.0)
            current_unused = previous_unused + minutes
            self.unused_minutes[other] = current_unused
            previous_decayable = max(0.0, previous_unused - decay_grace_minutes)
            current_decayable = max(0.0, current_unused - decay_grace_minutes)
            decayable_minutes = current_decayable - previous_decayable
            if decayable_minutes <= 0.0:
                continue

            score = self.values[other]
            peak = self.peak_values.get(other, score)
            transfer_floor = self._inferred_score(other)
            memory_floor = max(15.0, peak * 0.55, transfer_floor)
            decay_per_90 = 0.10 + 0.06 * (score / 100.0)
            decay = (decayable_minutes / 90.0) * decay_per_90
            self.values[other] = max(memory_floor, score - decay)

        return self.values[position]

    def minutes_for(self, position: Position) -> float:
        position = position if isinstance(position, Position) else Position(position)
        return self.played_minutes.get(position, 0.0)

    def best_position(self) -> Position | None:
        if not self.values:
            return None
        return max(self.values, key=self.values.get)

    def secondary_positions(
        self,
        primary: Position,
        *,
        minimum_score: float = 70.0,
        minimum_minutes: float = 450.0,
    ) -> tuple[Position, ...]:
        """Explicitly learned secondary positions, strongest first.

        A high transferable score is not enough on its own: a newly used
        position must also accumulate meaningful match minutes before the game
        presents it as an established secondary position.
        """

        primary = primary if isinstance(primary, Position) else Position(primary)
        minimum_score = validate_range("secondary familiarity threshold", minimum_score, 0.0, 100.0)
        minimum_minutes = validate_non_negative("secondary minutes threshold", minimum_minutes)
        candidates = [
            position
            for position, score in self.values.items()
            if (
                position is not primary
                and score >= minimum_score
                and self.minutes_for(position) >= minimum_minutes
            )
        ]
        return tuple(sorted(candidates, key=lambda item: self.values[item], reverse=True))
