"""TS-28.3: lightweight immutable snapshots and actual season award certificates.

Never backfill an ability curve or an award from a player's current rating.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from math import isfinite


@dataclass(frozen=True, slots=True)
class RatingSnapshot:
    season: str
    on_date: date
    overall: float
    # Small, labelled selection of measurements; not a copy of the full player.
    indicators: tuple[float, ...]

    def validate(self) -> None:
        if (not self.season or type(self.on_date) is not date or not isfinite(self.overall)
                or not 1 <= self.overall <= 100 or not isinstance(self.indicators, tuple) or len(self.indicators) != 10
                or any(not isfinite(v) or not 0 <= v <= 100
                       for v in self.indicators)):
            raise ValueError('invalid historical rating snapshot')


@dataclass(frozen=True, slots=True)
class IndividualAward:
    season: str
    competition_id: str  # `world` is the simulated universe's annual award.
    category: str
    player_id: str
    club_id: str | None  # Unknown for multiple registered clubs in one season.

    def validate(self) -> None:
        if (not self.season or not self.competition_id or not self.category or not self.player_id
                or (self.club_id is not None and not self.club_id)):
            raise ValueError('invalid career award')
