from __future__ import annotations

from dataclasses import dataclass

from .enums import Position
from .formation import Formation
from .player import Player


@dataclass(frozen=True, slots=True)
class LineupEntry:
    slot_id: str
    player: Player

    def __post_init__(self) -> None:
        if not self.slot_id.strip():
            raise ValueError("slot_id cannot be empty")


@dataclass(frozen=True, slots=True)
class MatchLineup:
    """A club's submitted pre-match starting XI and bench.

    The object is immutable. In-match substitutions will later live in match state
    rather than mutating the submitted lineup.
    """

    club_id: str
    formation: Formation
    starters: tuple[LineupEntry, ...]
    bench: tuple[Player, ...] = ()

    def __post_init__(self) -> None:
        if not self.club_id.strip():
            raise ValueError("club_id cannot be empty")
        if len(self.starters) != 11:
            raise ValueError("a starting lineup must contain exactly 11 players")

        submitted_slots = [entry.slot_id for entry in self.starters]
        if len(set(submitted_slots)) != len(submitted_slots):
            raise ValueError("each formation slot can only be assigned once")

        expected_slots = self.formation.slot_ids
        actual_slots = frozenset(submitted_slots)
        missing = expected_slots - actual_slots
        unknown = actual_slots - expected_slots
        if missing or unknown:
            details: list[str] = []
            if missing:
                details.append(f"missing slots: {sorted(missing)}")
            if unknown:
                details.append(f"unknown slots: {sorted(unknown)}")
            raise ValueError("lineup does not match formation (" + "; ".join(details) + ")")

        all_players = [entry.player for entry in self.starters] + list(self.bench)
        player_ids = [player.id for player in all_players]
        if len(set(player_ids)) != len(player_ids):
            raise ValueError("a player cannot appear more than once in the match squad")

        unavailable = [player.id for player in all_players if not player.state.is_available]
        if unavailable:
            raise ValueError(f"unavailable players cannot be selected: {sorted(unavailable)}")

    @property
    def starting_players(self) -> tuple[Player, ...]:
        return tuple(entry.player for entry in self.starters)

    @property
    def selected_players(self) -> tuple[Player, ...]:
        return self.starting_players + self.bench

    def player_for_slot(self, slot_id: str) -> Player:
        self.formation.slot(slot_id)
        for entry in self.starters:
            if entry.slot_id == slot_id:
                return entry.player
        raise KeyError(f"no player assigned to slot {slot_id!r}")

    def assigned_position(self, player_id: str) -> Position:
        for entry in self.starters:
            if entry.player.id == player_id:
                return self.formation.slot(entry.slot_id).position
        raise KeyError(f"player {player_id!r} is not in the starting XI")
