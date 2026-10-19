"""In-place rollback for mutable footballer state during a managed match.

Application-level transaction helper. Does not import the development UI and
preserves references held by lineups and other parts of the application.
"""
from __future__ import annotations

from contextlib import contextmanager
from copy import deepcopy
from dataclasses import fields
from typing import Iterable, Iterator

from football_manager.domain.club import Club


def _restore_fields(original: object, snapshot: object) -> None:
    for field in fields(snapshot):
        setattr(original, field.name, deepcopy(getattr(snapshot, field.name)))


def capture_player_state(clubs: Iterable[Club]) -> list[tuple]:
    """Capture mutable football state while retaining the canonical references."""
    saved = []
    seen: set[int] = set()
    for club in clubs:
        for player in club.squad.players:
            if id(player) in seen:
                continue
            seen.add(id(player))
            saved.append((
                player, player.state, deepcopy(player.state),
                player.positional_familiarity, deepcopy(player.positional_familiarity),
                player.tactical_familiarity, deepcopy(player.tactical_familiarity),
                player.primary_position,
            ))
    return saved


def restore_player_state(saved: list[tuple]) -> None:
    for player, state, state_copy, positional, positional_copy, tactical, tactical_copy, primary in saved:
        _restore_fields(state, state_copy)
        _restore_fields(positional, positional_copy)
        _restore_fields(tactical, tactical_copy)
        player.state = state
        player.positional_familiarity = positional
        player.tactical_familiarity = tactical
        player.primary_position = primary


@contextmanager
def preserve_player_state(clubs: Iterable[Club]) -> Iterator[None]:
    """Rollback footballers in place if a managed match commit fails."""
    saved = capture_player_state(clubs)
    try:
        yield
    except BaseException:
        restore_player_state(saved)
        raise
