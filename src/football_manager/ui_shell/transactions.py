"""Atomic, lightweight boundary for permanent squad and tactical UI commands.

Only the objects touched by a squad command are checkpointed. Copying the
entire DevelopmentSession would also copy thousands of unrelated fixtures and
world results for every tactical click.
"""
from __future__ import annotations

from contextlib import contextmanager
from copy import deepcopy
from typing import Iterator

from football_manager.dev_ui.session import DevelopmentSession
from .models import UIRosterAdmin, apply_squad_command


@contextmanager
def preserve_squad_edit(session: DevelopmentSession, admin: UIRosterAdmin | None) -> Iterator[None]:
    """Undo failed edits without replacing the session, players or tactic references."""
    studio = session.tactical_studio
    studio_before = deepcopy(studio)
    # TS-27 adds persistent preferences to the otherwise lightweight editor.
    set_pieces_before = dict(session.set_piece_orders)
    lineup = session.home_lineup  # Immutable MatchLineup; command replaces, not mutates.
    tactic = session.home_tactic
    tactic_before = (
        tactic.tactic_id, tactic.name, tactic.formation,
        tactic.preset_origin, tactic.team_instructions, tactic.phase_shapes,
    )
    assignments = tactic.role_assignments
    roles_before = dict(assignments)  # RoleAssignment / overrides are immutable.
    familiarity_before = [
        (player, player.tactical_familiarity,
         player.tactical_familiarity.tactic_values,
         dict(player.tactical_familiarity.tactic_values),
         player.tactical_familiarity.role_values,
         dict(player.tactical_familiarity.role_values))
        for player in session.home_club.squad.players
    ]
    if admin is not None:
        numbers = admin.numbers
        numbers_before = dict(numbers)
        statuses = admin.transfer_statuses
        statuses_before = dict(statuses)
    posture_before = dict(session._world_squads.manager_sale_posture)
    try:
        yield
    except BaseException:
        session._world_squads.manager_sale_posture.clear()
        session._world_squads.manager_sale_posture.update(posture_before)
        session.set_piece_orders.clear()
        session.set_piece_orders.update(set_pieces_before)
        for name in ("library", "plans", "rules", "revision", "sequence", "active_id"):
            setattr(studio, name, getattr(studio_before, name))
        session.tactical_studio = studio
        session.home_lineup = lineup
        (tactic.tactic_id, tactic.name, tactic.formation,
         tactic.preset_origin, tactic.team_instructions, tactic.phase_shapes) = tactic_before
        assignments.clear()
        assignments.update(roles_before)
        tactic.role_assignments = assignments
        session.home_tactic = tactic
        for player, familiarity, tactics, old_tactics, roles, old_roles in familiarity_before:
            tactics.clear()
            tactics.update(old_tactics)
            roles.clear()
            roles.update(old_roles)
            familiarity.tactic_values = tactics
            familiarity.role_values = roles
            player.tactical_familiarity = familiarity
        if admin is not None:
            numbers.clear()
            numbers.update(numbers_before)
            statuses.clear()
            statuses.update(statuses_before)
            admin.numbers = numbers
            admin.transfer_statuses = statuses
        raise


def apply_squad_command_atomically(
    session: DevelopmentSession, command: dict, admin: UIRosterAdmin,
) -> dict:
    """Commit a squad edit only after its complete UI response is constructible."""
    with preserve_squad_edit(session, admin):
        return apply_squad_command(session, command, admin)
