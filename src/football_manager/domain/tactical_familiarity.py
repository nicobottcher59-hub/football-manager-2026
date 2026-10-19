from __future__ import annotations

from dataclasses import dataclass, field

from .validation import validate_non_negative, validate_range


@dataclass(slots=True)
class TacticalFamiliarity:
    """Player familiarity with tactics and roles.

    These values describe learned comfort. They never rewrite player attributes.
    Learning rules based on minutes, training, age and role similarity will be added
    in a later phase.
    """

    tactic_values: dict[str, float] = field(default_factory=dict)
    role_values: dict[str, float] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.tactic_values = self._normalize(self.tactic_values, "tactic")
        self.role_values = self._normalize(self.role_values, "role")

    @staticmethod
    def _normalize(values: dict[str, float], kind: str) -> dict[str, float]:
        normalized: dict[str, float] = {}
        for key, value in values.items():
            if not key.strip():
                raise ValueError(f"{kind} familiarity key cannot be empty")
            normalized[key] = validate_range(
                f"{kind}_familiarity[{key}]",
                float(value),
                0.0,
                100.0,
            )
        return normalized

    def tactic_score(self, tactic_id: str) -> float:
        return self.tactic_values.get(tactic_id, 0.0)

    def role_score(self, role_id: str) -> float:
        return self.role_values.get(role_id, 0.0)

    def set_tactic_score(self, tactic_id: str, value: float) -> None:
        if not tactic_id.strip():
            raise ValueError("tactic_id cannot be empty")
        self.tactic_values[tactic_id] = validate_range(
            f"tactic_familiarity[{tactic_id}]",
            value,
            0.0,
            100.0,
        )

    def set_role_score(self, role_id: str, value: float) -> None:
        if not role_id.strip():
            raise ValueError("role_id cannot be empty")
        self.role_values[role_id] = validate_range(
            f"role_familiarity[{role_id}]",
            value,
            0.0,
            100.0,
        )

    def improve_tactic(self, tactic_id: str, amount: float) -> float:
        validate_non_negative("tactic familiarity improvement", amount)
        updated = min(100.0, self.tactic_score(tactic_id) + amount)
        self.set_tactic_score(tactic_id, updated)
        return updated

    def improve_role(self, role_id: str, amount: float) -> float:
        validate_non_negative("role familiarity improvement", amount)
        updated = min(100.0, self.role_score(role_id) + amount)
        self.set_role_score(role_id, updated)
        return updated
