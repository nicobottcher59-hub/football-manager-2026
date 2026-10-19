"""Rate an in-match role/position assignment with the existing canonical ACT formula.

A substitute or a live tactical change must be evaluated exactly like an XI
starter.  In particular, rebasing the old ACT-OVR delta carries *old* role and
tactic familiarity into a different assignment.  Reconstructing a temporary
rating-only Player avoids introducing a second set of rating weights or curves.
The source snapshot remains immutable and its chemistry is preserved.
"""
from __future__ import annotations

from dataclasses import replace

from .enums import Position
from .match_snapshot import PlayerMatchSnapshot, RoleExecutionSnapshot
from .player import Player, PlayerIdentity
from .player_ratings import CurrentRatingContext
from .player_state import PlayerState
from .positional_familiarity import PositionalFamiliarity
from .roles import evaluate_role_context
from .tactical_familiarity import TacticalFamiliarity
from .tactical_instructions import PlayerInstructions


def assign_match_player(
    source: PlayerMatchSnapshot,
    *,
    slot_id: str,
    position: Position,
    role_id: str,
    role_name: str,
    tactic_id: str,
    instructions: PlayerInstructions,
) -> PlayerMatchSnapshot:
    """Return a newly rated snapshot for one assigned job; mutate no input."""
    state = source.state
    temporary = Player(
        identity=PlayerIdentity(
            player_id=source.player_id,
            first_name=source.full_name,
            last_name=source.full_name,
            birth_date=source.birth_date,
            nationality=source.nationality,
            dominant_foot=source.dominant_foot,
        ),
        attributes=source.attributes,
        # Snapshots already capture effective transfer scores for every position.
        positional_familiarity=PositionalFamiliarity(dict(source.familiarity.positions)),
        original_position=source.original_position,
        primary_position=source.original_position,
        state=PlayerState(
            fitness=state.fitness,
            fatigue=state.fatigue,
            form=state.form,
            morale=state.morale,
            confidence=state.confidence,
            match_sharpness=state.match_sharpness,
            injury=state.injury,
            suspended_matches=state.suspended_matches,
        ),
        tactical_familiarity=TacticalFamiliarity(
            tactic_values=dict(source.familiarity.tactics),
            role_values=dict(source.familiarity.roles),
        ),
    )
    rating = temporary.current_rating(
        CurrentRatingContext(
            assigned_position=position,
            role_id=role_id,
            tactic_id=tactic_id,
            chemistry=source.rating_chemistry,
        )
    )
    role_context = evaluate_role_context(temporary, position, role_id, tactic_id)
    return replace(
        source,
        overall_rating=rating.overall,
        current_rating=rating.current,
        assigned_slot_id=slot_id,
        assigned_position=position,
        role_id=role_id,
        role_name=role_name,
        effective_instructions=instructions,
        role_context=RoleExecutionSnapshot(
            position_familiarity=role_context.position_familiarity,
            role_familiarity=role_context.role_familiarity,
            tactic_familiarity=role_context.tactic_familiarity,
            role_suitability=role_context.role_suitability,
        ),
    )
