from __future__ import annotations

from dataclasses import dataclass, field

from .player import Player


@dataclass(slots=True)
class Squad:
    """Mutable first-team squad keyed by stable player IDs."""

    _players: dict[str, Player] = field(default_factory=dict, repr=False)

    def __post_init__(self) -> None:
        original = list(self._players.values())
        self._players = {}
        for player in original:
            self.add(player)

    @classmethod
    def from_players(cls, players: list[Player] | tuple[Player, ...]) -> Squad:
        squad = cls()
        for player in players:
            squad.add(player)
        return squad

    def add(self, player: Player) -> None:
        if player.id in self._players:
            raise ValueError(f"player {player.id!r} is already in the squad")
        self._players[player.id] = player

    def remove(self, player_id: str) -> Player:
        try:
            player = self._players.pop(player_id)
            # A club's social context does not follow a player to another club.
            player.state.dressing_room_morale = 0.0
            return player
        except KeyError as exc:
            raise KeyError(f"player {player_id!r} is not in the squad") from exc

    def get(self, player_id: str) -> Player:
        try:
            return self._players[player_id]
        except KeyError as exc:
            raise KeyError(f"player {player_id!r} is not in the squad") from exc

    def contains(self, player_id: str) -> bool:
        return player_id in self._players

    @property
    def players(self) -> tuple[Player, ...]:
        return tuple(self._players.values())

    def __len__(self) -> int:
        return len(self._players)
