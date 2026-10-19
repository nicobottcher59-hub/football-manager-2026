from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from .attributes import PlayerAttributes
from .enums import Foot, Position
from .player_state import PlayerState
from .personality import Personality, personality_for
from .positional_familiarity import PositionalFamiliarity
from .tactical_familiarity import TacticalFamiliarity
from .player_development import PlayerDevelopment
from .player_aging import PlayerAging


@dataclass(frozen=True, slots=True)
class PlayerIdentity:
    player_id: str
    first_name: str
    last_name: str
    birth_date: date
    nationality: str
    dominant_foot: Foot

    def __post_init__(self) -> None:
        if type(self.birth_date) is not date:
            raise ValueError("birth_date must be a calendar date")
        if not self.player_id.strip():
            raise ValueError("player_id cannot be empty")
        if not self.first_name.strip():
            raise ValueError("first_name cannot be empty")
        if not self.last_name.strip():
            raise ValueError("last_name cannot be empty")
        if not self.nationality.strip():
            raise ValueError("nationality cannot be empty")


@dataclass(slots=True)
class Player:
    identity: PlayerIdentity
    attributes: PlayerAttributes
    positional_familiarity: PositionalFamiliarity
    original_position: Position
    primary_position: Position
    state: PlayerState = field(default_factory=PlayerState)
    tactical_familiarity: TacticalFamiliarity = field(default_factory=TacticalFamiliarity)

    personality: Personality | None = field(default=None, repr=False)
    development: PlayerDevelopment | None = field(default=None, repr=False)

    aging: PlayerAging | None = field(default=None, repr=False)

    def __post_init__(self) -> None:
        if self.personality is None:
            self.personality = personality_for(self.id)
        elif not isinstance(self.personality, Personality):
            raise ValueError('invalid player personality')
        self.personality.validate()
        if self.development is not None:
            self.development.validate(self)
        if self.aging is not None:
            self.aging.validate(self)

    @property
    def id(self) -> str:
        return self.identity.player_id

    @property
    def full_name(self) -> str:
        return f"{self.identity.first_name} {self.identity.last_name}"

    def age_on(self, on_date: date) -> int:
        if on_date < self.identity.birth_date:
            raise ValueError("on_date cannot be before the player's birth date")
        years = on_date.year - self.identity.birth_date.year
        birthday_passed = (on_date.month, on_date.day) >= (
            self.identity.birth_date.month,
            self.identity.birth_date.day,
        )
        return years if birthday_passed else years - 1

    def familiarity_for(self, position: Position) -> float:
        return self.positional_familiarity.effective_score(position)

    @property
    def overall_rating(self) -> float:
        """OVR for the player's current primary position and its default role."""
        from .player_ratings import calculate_overall

        return calculate_overall(self)

    def overall_rating_for(self, position: Position, role_id: str | None = None) -> float:
        """Contextual OVR for a specific tactical job."""
        from .player_ratings import calculate_overall

        return calculate_overall(self, position, role_id)

    def overall_breakdown_for(self, position: Position, role_id: str | None = None):
        from .player_ratings import calculate_overall_breakdown

        return calculate_overall_breakdown(self, position, role_id)

    def current_rating(self, context=None):
        from .player_ratings import calculate_current_rating

        return calculate_current_rating(self, context)

    @property
    def secondary_positions(self) -> tuple[Position, ...]:
        return self.positional_familiarity.secondary_positions(self.primary_position)

    def record_position_minutes(self, position: Position, minutes: float) -> float:
        """Persist positional learning/decay from real match minutes."""

        score = self.positional_familiarity.record_minutes(
            position,
            minutes,
            adaptability=float(self.attributes.mental.adaptability),
        )
        self.recalculate_primary_position()
        return score

    def recalculate_primary_position(
        self,
        minimum_margin: float = 5.0,
        minimum_score: float = 82.0,
        minimum_minutes: float = 1350.0,
    ) -> Position:
        """Promote a learned position only after clear, sustained superiority.

        Familiarity accumulation itself provides the inertia: a short emergency
        spell cannot immediately rewrite the player's identity. Once another
        explicit learned position is both highly familiar and clearly ahead, it
        becomes primary automatically and the previous primary can remain as a
        secondary while its familiarity slowly decays.
        """
        best = self.positional_familiarity.best_position()
        if best is None:
            return self.primary_position

        current_score = self.positional_familiarity.score(self.primary_position)
        best_score = self.positional_familiarity.score(best)
        if (
            best != self.primary_position
            and best_score >= minimum_score
            and self.positional_familiarity.minutes_for(best) >= minimum_minutes
            and best_score >= current_score + minimum_margin
        ):
            self.primary_position = best
        return self.primary_position
