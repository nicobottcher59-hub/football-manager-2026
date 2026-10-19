from __future__ import annotations

from dataclasses import dataclass

from .validation import validate_non_negative, validate_range


@dataclass(slots=True)
class PlayerState:
    fitness: float = 100.0
    fatigue: float = 0.0
    form: float = 65.0
    morale: float = 65.0
    confidence: float = 65.0
    match_sharpness: float = 65.0
    injury: str | None = None
    suspended_matches: int = 0
    # Club-scoped context, never folded into stored base morale. Replaced by
    # TS-20 progression; the established morale -> ACT formula stays intact.
    dressing_room_morale: float = 0.0

    def __post_init__(self) -> None:
        self._validate()

    def _validate(self) -> None:
        for name in ("fitness", "fatigue", "form", "morale", "confidence", "match_sharpness"):
            validate_range(name, getattr(self, name), 0.0, 100.0)
        validate_non_negative("suspended_matches", self.suspended_matches)
        from .dressing_room import finite_range, MAX_MORALE_EFFECT
        finite_range('dressing_room_morale', self.dressing_room_morale, -MAX_MORALE_EFFECT, MAX_MORALE_EFFECT)

    @property
    def effective_morale(self) -> float:
        return max(0.0, min(100.0, self.morale + self.dressing_room_morale))

    @property
    def condition(self) -> float:
        """Current physical readiness on a 0-100 scale.

        ``fitness`` remains the stored field for backward compatibility with the
        existing project. New rating code uses the clearer ``condition`` name:
        100 means fully ready, and lower values progressively restrict output.
        """

        return self.fitness

    @property
    def is_available(self) -> bool:
        return self.injury is None and self.suspended_matches == 0 and self.fitness > 0

    def apply_fatigue(self, amount: float) -> None:
        validate_non_negative("fatigue amount", amount)
        self.fatigue = min(100.0, self.fatigue + amount)
        self.fitness = max(0.0, self.fitness - amount * 0.55)

    def recover(self, amount: float) -> None:
        validate_non_negative("recovery amount", amount)
        self.fatigue = max(0.0, self.fatigue - amount)
        self.fitness = min(100.0, self.fitness + amount * 0.7)

    def adjust_confidence(self, delta: float) -> float:
        self.confidence = max(0.0, min(100.0, self.confidence + delta))
        return self.confidence

    def adjust_form(self, delta: float) -> float:
        self.form = max(0.0, min(100.0, self.form + delta))
        return self.form

    def adjust_morale(self, delta: float) -> float:
        self.morale = max(0.0, min(100.0, self.morale + delta))
        return self.morale
