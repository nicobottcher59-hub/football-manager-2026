from __future__ import annotations

from football_manager.domain.conditioning import ConditionState, recover_condition_state
from football_manager.domain.player import Player


def set_post_match_condition(player: Player, *, condition: float, fatigue: float) -> ConditionState:
    """Persist a simulator's post-match physical state onto the world player."""

    state = ConditionState(condition=condition, fatigue=fatigue)
    player.state.fitness = state.condition
    player.state.fatigue = state.fatigue
    return state


def recover_player_between_matches(player: Player, *, days: int) -> ConditionState:
    """Advance recovery for a player across calendar days and persist the result."""

    physical = player.attributes.physical
    recovered = recover_condition_state(
        condition=player.state.condition,
        fatigue=player.state.fatigue,
        days=days,
        natural_fitness=float(physical.natural_fitness),
        stamina=float(physical.stamina),
    )
    player.state.fitness = recovered.condition
    player.state.fatigue = recovered.fatigue
    return recovered
