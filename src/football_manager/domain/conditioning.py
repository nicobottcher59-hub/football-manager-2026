from __future__ import annotations

from dataclasses import dataclass

from .validation import validate_non_negative, validate_range


@dataclass(frozen=True, slots=True)
class ConditionState:
    """Physical readiness plus accumulated fatigue debt.

    ``condition`` is the visible/readiness scale used by selection and ACT.
    ``fatigue`` is a hidden accumulation/debt scale used to slow recovery after
    heavy match loads. Fatigue does not apply a second ACT penalty directly.
    """

    condition: float
    fatigue: float

    def __post_init__(self) -> None:
        validate_range("condition", self.condition, 0.0, 100.0)
        validate_range("fatigue", self.fatigue, 0.0, 100.0)


def _clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


def match_condition_state(
    *,
    starting_condition: float,
    starting_fatigue: float,
    stamina: float,
    minutes: int,
    workload_factor: float = 1.0,
) -> ConditionState:
    """Return post-match condition/fatigue without mutating persistent state.

    The curve is intentionally non-linear after 90 minutes. A neutral player at
    roughly average stamina should finish a normal 90 around the mid-50s and a
    120-minute match around the high-20s. Tactical/role workload and stamina move
    those outcomes substantially.
    """

    starting_condition = validate_range("starting_condition", starting_condition, 0.0, 100.0)
    starting_fatigue = validate_range("starting_fatigue", starting_fatigue, 0.0, 100.0)
    stamina = validate_range("stamina", stamina, 1.0, 100.0)
    validate_non_negative("minutes", minutes)
    if workload_factor <= 0.0:
        raise ValueError("workload_factor must be positive")

    played = min(120, int(minutes))
    if played <= 0:
        return ConditionState(round(starting_condition, 1), round(starting_fatigue, 1))

    # 90' is one full match-load unit. Extra time is deliberately more expensive
    # than a linear additional third because the player is already depleted.
    normal_fraction = min(played, 90) / 90.0
    extra_fraction = max(0, played - 90) / 30.0
    time_load = normal_fraction + extra_fraction * 0.60

    # 65 stamina is neutral. The spread is deliberately wide: low-stamina
    # players should be visibly depleted by 90 minutes while elite-stamina
    # players preserve substantially more condition under the same assignment.
    stamina_factor = _clamp(1.0 - (stamina - 65.0) * 0.009, 0.70, 1.30)
    fatigue_factor = 1.0 + starting_fatigue * 0.0015

    condition_loss = 46.0 * time_load * workload_factor * stamina_factor * fatigue_factor
    condition_after = _clamp(starting_condition - condition_loss)

    # Fatigue is the slower-recovering debt. It grows with real exertion but not
    # one-for-one with the visible condition drop.
    fatigue_gain = condition_loss * 0.85
    fatigue_after = _clamp(starting_fatigue + fatigue_gain)

    return ConditionState(round(condition_after, 1), round(fatigue_after, 1))


def recover_condition_state(
    *,
    condition: float,
    fatigue: float,
    days: int,
    natural_fitness: float,
    stamina: float = 65.0,
) -> ConditionState:
    """Recover a player's physical state across calendar days.

    Natural fitness remains the primary between-match recovery attribute, but
    stamina also matters: players who tolerate workload better recover somewhat
    better from it. Deeply depleted players regain condition faster at first,
    while accumulated fatigue still suppresses the early part of recovery.

    The intended calendar shape is deliberately demanding:
    - a normal 90-minute load is not close to fully recovered after four days;
    - a clean week normally restores that 90-minute load;
    - a 120-minute load can still leave a meaningful scar after seven days.
    """

    condition = validate_range("condition", condition, 0.0, 100.0)
    fatigue = validate_range("fatigue", fatigue, 0.0, 100.0)
    natural_fitness = validate_range("natural_fitness", natural_fitness, 1.0, 100.0)
    stamina = validate_range("stamina", stamina, 1.0, 100.0)
    validate_non_negative("days", days)

    current_condition = float(condition)
    current_fatigue = float(fatigue)
    if days <= 0:
        return ConditionState(round(current_condition, 1), round(current_fatigue, 1))

    # Natural fitness is about twice as influential as stamina between games.
    # Stamina already has the stronger role during the match itself.
    base_condition_recovery = 8.1
    base_condition_recovery += (natural_fitness - 65.0) * 0.060
    base_condition_recovery += (stamina - 65.0) * 0.030
    base_condition_recovery = _clamp(base_condition_recovery, 4.5, 12.0)

    fatigue_recovery = 11.0
    fatigue_recovery += (natural_fitness - 65.0) * 0.080
    fatigue_recovery += (stamina - 65.0) * 0.040
    fatigue_recovery = _clamp(fatigue_recovery, 6.5, 17.0)

    for _ in range(int(days)):
        # Fatigue debt slows the first days after a heavy load. Deep depletion
        # simultaneously creates a larger acute-recovery component; this lets a
        # 120-minute player make substantial progress over a full week without
        # making a four-day turnaround unrealistically easy.
        recovery_gate = 1.0 - current_fatigue * 0.0025
        recovery_gate = _clamp(recovery_gate, 0.68, 1.0)
        deep_depletion_bonus = max(0.0, 60.0 - current_condition) * 0.20
        daily_condition_recovery = (
            base_condition_recovery + deep_depletion_bonus
        ) * recovery_gate

        current_condition = _clamp(current_condition + daily_condition_recovery)
        current_fatigue = _clamp(current_fatigue - fatigue_recovery)

    return ConditionState(round(current_condition, 1), round(current_fatigue, 1))
