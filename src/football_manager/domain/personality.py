"""Stable, private player characteristics (TS-20).

Game design values, not scouting facts or a second ability rating. They never
consume match RNG. The only public view is qualitative; no UI API serializes
this dataclass. Injury susceptibility is reserved for the future medical model.
"""
from __future__ import annotations

from dataclasses import dataclass, fields
from hashlib import sha256


@dataclass(frozen=True, slots=True)
class Personality:
    professionalism: int = 60
    ambition: int = 60
    loyalty: int = 60
    pressure_resistance: int = 60
    injury_susceptibility: int = 50
    leadership: int = 60

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        for item in fields(self):
            value = getattr(self, item.name)
            if type(value) is not int or not 1 <= value <= 100:
                raise ValueError(f'{item.name} must be an integer between 1 and 100')


def personality_for(player_id: str) -> Personality:
    """Reproducible legacy/new-player default, independent of Python hash seed."""
    if not isinstance(player_id, str) or not player_id.strip():
        raise ValueError('a stable player ID is required')
    digest = sha256(('fm-player-personality-v1:' + player_id).encode('utf-8')).digest()
    values = [20 + round((digest[2*i] + digest[2*i+1]) / 510 * 75) for i in range(6)]
    return Personality(*values)
