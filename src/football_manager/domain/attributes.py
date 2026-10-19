from __future__ import annotations

from dataclasses import dataclass, fields

from .validation import validate_range


ATTRIBUTE_MIN = 1
ATTRIBUTE_MAX = 100


class _ValidatedAttributeGroup:
    def __post_init__(self) -> None:
        for field in fields(self):
            value = getattr(self, field.name)
            validate_range(field.name, value, ATTRIBUTE_MIN, ATTRIBUTE_MAX)

    def average(self) -> float:
        values = [getattr(self, field.name) for field in fields(self)]
        return sum(values) / len(values)


@dataclass(frozen=True, slots=True)
class TechnicalAttributes(_ValidatedAttributeGroup):
    passing: int
    technique: int
    finishing: int
    first_touch: int
    dribbling: int
    crossing: int
    tackling: int
    heading: int
    long_shots: int
    shot_power: int
    marking: int
    set_pieces: int
    penalties: int


@dataclass(frozen=True, slots=True)
class MentalAttributes(_ValidatedAttributeGroup):
    vision: int
    decisions: int
    anticipation: int
    concentration: int
    composure: int
    positioning: int
    off_the_ball: int
    teamwork: int
    work_rate: int
    aggression: int
    bravery: int
    creativity: int
    tactical_intelligence: int
    adaptability: int = 65


@dataclass(frozen=True, slots=True)
class PhysicalAttributes(_ValidatedAttributeGroup):
    pace: int
    acceleration: int
    strength: int
    stamina: int
    agility: int
    balance: int
    jumping_reach: int
    natural_fitness: int


@dataclass(frozen=True, slots=True)
class GoalkeepingAttributes(_ValidatedAttributeGroup):
    reflexes: int
    handling: int
    one_on_ones: int
    aerial_reach: int
    command_of_area: int
    kicking: int
    throwing: int
    goalkeeper_positioning: int


@dataclass(frozen=True, slots=True)
class PlayerAttributes:
    technical: TechnicalAttributes
    mental: MentalAttributes
    physical: PhysicalAttributes
    goalkeeping: GoalkeepingAttributes | None = None

    def outfield_average(self) -> float:
        """Diagnostic arithmetic mean of all outfield attributes.

        This remains useful for debugging, but it is not the derived OVR. OVR uses
        position-appropriate weighting and specific football actions still use the
        attributes relevant to that action.
        """
        values: list[int] = []
        for group in (self.technical, self.mental, self.physical):
            values.extend(getattr(group, field.name) for field in fields(group))
        return sum(values) / len(values)

    def goalkeeping_average(self) -> float | None:
        if self.goalkeeping is None:
            return None
        return self.goalkeeping.average()

    def average(self) -> float:
        """Backward-compatible alias for the outfield diagnostic average."""
        return self.outfield_average()
