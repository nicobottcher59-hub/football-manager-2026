"""Per-career tactical library and match plans; no player roster is saved here."""
from __future__ import annotations

from dataclasses import dataclass, field
from .tactics import Tactic
from .tactical_shapes import validate_shapes

PLAN_KEYS = ('A', 'B', 'C')
PLAN_CONDITIONS = ('always', 'leading', 'level', 'trailing')
MAX_TACTICS = 64
MAX_RULES = 6


def tactic_name(value: object) -> str:
    if not isinstance(value, str):
        raise ValueError('tactic name must be text')
    name = value.strip()
    if not 1 <= len(name) <= 60 or any(ord(c) < 32 for c in name):
        raise ValueError('tactic name must contain 1 to 60 printable characters')
    return name


@dataclass(frozen=True, slots=True)
class SavedTactic:
    entry_id: str
    name: str
    tactic: Tactic

    def __post_init__(self) -> None:
        if not isinstance(self.entry_id, str) or not self.entry_id.startswith('tactic-'):
            raise ValueError('invalid library tactic ID')
        if tactic_name(self.name) != self.name or not isinstance(self.tactic, Tactic):
            raise ValueError('invalid saved tactic')
        self.tactic.__post_init__()


@dataclass(frozen=True, slots=True)
class PlanRule:
    plan: str
    minute: int
    condition: str = 'always'

    def __post_init__(self) -> None:
        if self.plan not in PLAN_KEYS or self.condition not in PLAN_CONDITIONS:
            raise ValueError('invalid tactical plan condition')
        if type(self.minute) is not int or not 1 <= self.minute <= 119:
            raise ValueError('plan minute must be an integer from 1 to 119')

    def matches(self, own_goals: int, opponent_goals: int) -> bool:
        return (self.condition == 'always'
                or self.condition == 'leading' and own_goals > opponent_goals
                or self.condition == 'level' and own_goals == opponent_goals
                or self.condition == 'trailing' and own_goals < opponent_goals)


@dataclass(slots=True)
class TacticalStudioState:
    library: dict[str, SavedTactic] = field(default_factory=dict)
    plans: dict[str, str | None] = field(default_factory=lambda: dict.fromkeys(PLAN_KEYS))
    rules: tuple[PlanRule, ...] = ()
    revision: int = 0
    sequence: int = 0
    active_id: str | None = None

    def validate(self) -> None:
        if type(self.revision) is not int or self.revision < 0 or type(self.sequence) is not int or self.sequence < 0:
            raise ValueError('invalid tactical library revision')
        if not isinstance(self.library, dict) or len(self.library) > MAX_TACTICS:
            raise ValueError('invalid tactical library size')
        names = set()
        for key, entry in self.library.items():
            if not isinstance(entry, SavedTactic) or key != entry.entry_id:
                raise ValueError('invalid tactical library entry')
            entry.__post_init__()
            if entry.name.casefold() in names:
                raise ValueError('duplicate tactical library name')
            names.add(entry.name.casefold())
        if not isinstance(self.plans, dict) or set(self.plans) != set(PLAN_KEYS):
            raise ValueError('tactical plans must contain A, B and C')
        if any(value is not None and value not in self.library for value in self.plans.values()):
            raise ValueError('plan points to a missing saved tactic')
        if self.active_id is not None and self.active_id not in self.library:
            raise ValueError('active library tactic is missing')
        if not isinstance(self.rules, tuple) or len(self.rules) > MAX_RULES:
            raise ValueError('too many tactical plan rules')
        minutes = set()
        for rule in self.rules:
            if not isinstance(rule, PlanRule):
                raise ValueError('invalid tactical plan rule')
            rule.__post_init__()
            if not self.plans[rule.plan]:
                raise ValueError('scheduled plan needs a saved tactic')
            if rule.minute in minutes:
                raise ValueError('use only one plan change at each minute')
            minutes.add(rule.minute)
