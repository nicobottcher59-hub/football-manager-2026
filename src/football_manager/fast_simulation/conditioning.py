from __future__ import annotations

from football_manager.domain import ConditionState, PlayerMatchSnapshot, Position, match_condition_state

from .profiles import FastTeamProfile


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _attr(player: PlayerMatchSnapshot, path: str) -> float:
    current: object = player.attributes
    for part in path.split("."):
        current = getattr(current, part)
        if current is None:
            return 50.0
    return float(current)


def player_workload_factor(player: PlayerMatchSnapshot, profile: FastTeamProfile) -> float:
    """Estimate how physically expensive this player's current assignment is."""

    position = player.assigned_position
    base = {
        Position.GK: 0.35,
        Position.RB: 1.03,
        Position.RCB: 0.88,
        Position.CB: 0.88,
        Position.LCB: 0.88,
        Position.LB: 1.03,
        Position.RWB: 1.12,
        Position.LWB: 1.12,
        Position.DM: 0.98,
        Position.RCM: 1.05,
        Position.CM: 1.05,
        Position.LCM: 1.05,
        Position.AM: 1.02,
        Position.RW: 1.05,
        Position.LW: 1.05,
        Position.SS: 1.00,
        Position.ST: 0.95,
    }.get(position, 1.0)

    # Fast tempo is a global physical tax.
    base *= 1.0 + ((profile.tempo - 50.0) / 50.0) * 0.10

    # Pressing is deliberately role-sensitive. The first line and midfield carry
    # far more of a high press than the centre-backs.
    pressing_weight = {
        Position.GK: 0.00,
        Position.RB: 0.06,
        Position.RCB: 0.05,
        Position.CB: 0.05,
        Position.LCB: 0.05,
        Position.LB: 0.06,
        Position.RWB: 0.10,
        Position.LWB: 0.10,
        Position.DM: 0.10,
        Position.RCM: 0.13,
        Position.CM: 0.13,
        Position.LCM: 0.13,
        Position.AM: 0.15,
        Position.RW: 0.17,
        Position.LW: 0.17,
        Position.SS: 0.17,
        Position.ST: 0.18,
    }.get(position, 0.10)
    base *= 1.0 + ((profile.pressing - 50.0) / 50.0) * pressing_weight

    defensive_positions = {
        Position.RB,
        Position.RCB,
        Position.CB,
        Position.LCB,
        Position.LB,
        Position.RWB,
        Position.LWB,
        Position.DM,
    }
    if position in defensive_positions:
        # Sitting deep shifts sustained work toward the defensive unit. A very
        # high line has a smaller sprint/recovery cost of its own.
        if profile.defensive_depth < 50.0:
            base *= 1.0 + ((50.0 - profile.defensive_depth) / 50.0) * 0.12
        elif profile.defensive_depth > 70.0:
            base *= 1.0 + ((profile.defensive_depth - 70.0) / 30.0) * 0.05

    sprint_positions = {
        Position.RB,
        Position.LB,
        Position.RWB,
        Position.LWB,
        Position.AM,
        Position.RW,
        Position.LW,
        Position.SS,
        Position.ST,
    }
    if position in sprint_positions:
        base *= 1.0 + ((profile.directness - 50.0) / 50.0) * 0.05

    instructions = player.effective_instructions
    if instructions is not None:
        individual_load = 0.0
        individual_load += (float(instructions.pressing_intensity) - 50.0) / 50.0 * 0.055
        individual_load += (float(instructions.defensive_tracking) - 50.0) / 50.0 * 0.035
        individual_load += (float(instructions.forward_runs) - 50.0) / 50.0 * 0.035
        individual_load += (float(instructions.roaming) - 50.0) / 50.0 * 0.025
        base *= 1.0 + individual_load

    # High work-rate players choose to spend a little more energy. Stamina is
    # handled separately as their resistance to that workload.
    work_rate = _attr(player, "mental.work_rate")
    base *= 1.0 + ((work_rate - 65.0) / 35.0) * 0.035
    return _clamp(base, 0.30, 1.45)


def physical_state_after(
    player: PlayerMatchSnapshot,
    profile: FastTeamProfile,
    minutes: int,
) -> ConditionState:
    return match_condition_state(
        starting_condition=player.state.condition,
        starting_fatigue=player.state.fatigue,
        stamina=_attr(player, "physical.stamina"),
        minutes=minutes,
        workload_factor=player_workload_factor(player, profile),
    )
