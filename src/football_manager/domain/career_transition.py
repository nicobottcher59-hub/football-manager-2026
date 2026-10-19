"""Stable application boundary for country-specific career season transitions.

Each territory may implement its own qualification, promotion and season builder.
This contract does not add any new country to the playable world.
"""
from __future__ import annotations

from typing import Protocol

from .season_cycle import EuropeanAccessPolicy, SeasonReport
from .world_runner import WorldSeasonRunner


class CareerSeasonTransition(Protocol):
    """Versioned strategy used by WorldCareer at a season boundary."""

    transition_id: str

    def finish(self, world: WorldSeasonRunner, *, european_policy: EuropeanAccessPolicy) -> SeasonReport:
        """Validate and report a completed world season."""
        ...

    def build_next(self, previous: WorldSeasonRunner, report: SeasonReport,
                   names: dict[str, str]) -> WorldSeasonRunner:
        """Produce the following world without mutating the previous world."""
        ...
