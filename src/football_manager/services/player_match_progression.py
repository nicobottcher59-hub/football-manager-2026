"""Commit already-modelled player state and tactical learning from played minutes.

These updates only change the short/medium-term context consumed by ACT. The
player's technical/mental/physical attributes and OVR formula remain untouched.
They use the existing match rating and minutes; the rates are conservative
integration parameters, not a new rating/balance formula.
"""
from __future__ import annotations

from math import sqrt

from football_manager.domain.player import Player


def _clamp(value: float, minimum: float = 0.0, maximum: float = 100.0) -> float:
    return max(minimum, min(maximum, value))


def apply_player_match_progression(
    player: Player,
    *,
    minutes: int,
    match_rating: float,
    role_id: str | None = None,
    tactic_id: str | None = None,
    role_minutes: dict[str, int] | None = None,
) -> float:
    """Update existing form/confidence/sharpness and familiarities.

    Returns the learned tactic-score increment so that the session can preserve
    it in the *baseline* used by its existing plan-similarity adjustment.
    Substitutes have no documented per-minute role assignment, so they learn
    team tactics and short-term state, not an invented substitute role.
    Poor performances can yield no role/tactic progress at all.
    """
    if not 0 <= minutes <= 120:
        raise ValueError('played minutes must be between 0 and 120')
    if not 1.0 <= match_rating <= 10.0:
        raise ValueError('match rating must be between 1 and 10')
    if role_minutes is not None:
        if (not isinstance(role_minutes, dict)
                or any(not isinstance(key, str) or type(value) is not int or value < 0
                       for key, value in role_minutes.items())
                or sum(role_minutes.values()) != minutes):
            raise ValueError('role minutes must partition actual played minutes')
    if minutes == 0:
        return 0.0

    participation = min(1.25, minutes / 90.0)
    state = player.state
    # Recent performance moves toward the level implied by an actual match
    # rating, instead of accumulating an unconditional positive bonus.
    form_target = _clamp(65.0 + 12.0 * (match_rating - 6.5))
    confidence_target = _clamp(65.0 + 10.0 * (match_rating - 6.5))
    # Keep the existing target curves, but limit the effect of one appearance.
    # Even an exceptionally poor game cannot suddenly collapse a player's
    # confidence/form. A sustained run still changes the underlying state.
    def gradual_step(current: float, target: float, rate: float, limit: float) -> float:
        step = (target - current) * rate
        return max(-limit, min(limit, step)) * participation

    state.adjust_form(gradual_step(state.form, form_target, 0.09, 2.0))
    state.adjust_confidence(gradual_step(state.confidence, confidence_target, 0.07, 1.25))
    state.match_sharpness = _clamp(
        state.match_sharpness + (100.0 - state.match_sharpness) * 0.018 * participation
    )

    # Learning is not guaranteed by playing. It depends on actual performance,
    # the player's adaptability/tactical intelligence and current confidence.
    performance = _clamp((match_rating - 5.6) / 2.4, 0.0, 1.25)
    if performance <= 0.0:
        return 0.0
    mental = player.attributes.mental
    aptitude = (float(mental.adaptability) + float(mental.tactical_intelligence)) / 200.0
    rate = 1.6 * participation * performance * aptitude * state.confidence / 100.0

    def familiarity_gain(current: float) -> float:
        return rate * sqrt(max(0.0, (100.0 - current) / 100.0))

    if role_minutes is not None:
        # Apply form/confidence once; split the existing learning budget across
        # the roles actually played instead of rewarding every role for 90 min.
        for actual_role, played in role_minutes.items():
            current = player.tactical_familiarity.role_score(actual_role)
            player.tactical_familiarity.improve_role(actual_role, familiarity_gain(current) * played / minutes)
    elif role_id is not None:
        current = player.tactical_familiarity.role_score(role_id)
        player.tactical_familiarity.improve_role(role_id, familiarity_gain(current))
    if tactic_id is None:
        return 0.0
    previous = player.tactical_familiarity.tactic_score(tactic_id)
    updated = player.tactical_familiarity.improve_tactic(tactic_id, familiarity_gain(previous))
    return updated - previous
