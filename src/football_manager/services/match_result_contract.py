"""Stable adapter from simulation results to world fixture results.

A future 2D engine can provide the same score/participant fields as the fast
engine. Background results already use WorldMatchResult and may be projected
through `read_world_outcome` without inventing detailed player statistics.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from football_manager.domain.world_runner import WorldMatchResult, WorldSeasonRunner


class FixtureIdentity(Protocol):
    fixture_id: str
    home_club_id: str
    away_club_id: str


class MatchScoreSource(Protocol):
    home_club_id: str
    away_club_id: str
    home_goals: int
    away_goals: int
    penalties_home: int
    penalties_away: int


@dataclass(frozen=True, slots=True)
class FixtureMatchOutcome:
    """Engine-independent, identity-checked projection of a played fixture."""

    fixture_id: str
    home_club_id: str
    away_club_id: str
    home_goals: int
    away_goals: int
    penalties_home: int
    penalties_away: int
    resolver: str

    def __post_init__(self) -> None:
        if not self.fixture_id or not self.home_club_id or not self.away_club_id:
            raise ValueError("fixture outcome requires IDs for fixture and clubs")
        if self.home_club_id == self.away_club_id:
            raise ValueError("fixture outcome requires different clubs")
        self.to_world_result()

    def to_world_result(self) -> WorldMatchResult:
        return WorldMatchResult(
            self.fixture_id, self.home_goals, self.away_goals,
            self.penalties_home, self.penalties_away, self.resolver,
        )


def from_match_score(fixture: FixtureIdentity, score: MatchScoreSource, *,
                     resolver: str = "managed") -> FixtureMatchOutcome:
    """Reject home/away mismatches before any world or player state is written."""
    if (score.home_club_id, score.away_club_id) != (
        fixture.home_club_id, fixture.away_club_id,
    ):
        raise ValueError(f"match participants do not match fixture {fixture.fixture_id}")
    outcome = FixtureMatchOutcome(
        fixture.fixture_id, fixture.home_club_id, fixture.away_club_id,
        score.home_goals, score.away_goals,
        score.penalties_home, score.penalties_away, resolver,
    )
    return outcome


def from_world_result(fixture: FixtureIdentity, result: WorldMatchResult) -> FixtureMatchOutcome:
    """Read a background/imported result with the same fixture ID contract."""
    if fixture.fixture_id != result.fixture_id:
        raise ValueError("world result does not belong to requested fixture")
    return FixtureMatchOutcome(
        fixture.fixture_id, fixture.home_club_id, fixture.away_club_id,
        result.home_goals, result.away_goals,
        result.penalties_home, result.penalties_away, result.resolver,
    )


def record_managed_match(world: WorldSeasonRunner, fixture: FixtureIdentity,
                         result: MatchScoreSource) -> WorldMatchResult:
    """Validate against the world's fixture ledger before committing the score.

    Checking only the caller-supplied fixture is insufficient: a stale or
    forged fixture can have a genuine ID but reversed home/away participants.
    Never accept a score in that orientation, even if the score matches the
    forged fixture perfectly.
    """
    canonical = world.fixtures.get(fixture.fixture_id)
    if canonical is None:
        raise KeyError(f"unknown world fixture: {fixture.fixture_id}")
    if (fixture.home_club_id, fixture.away_club_id) != (
        canonical.home_club_id, canonical.away_club_id
    ):
        raise ValueError(f"fixture {fixture.fixture_id} participants differ from canonical world")
    outcome = from_match_score(canonical, result, resolver="managed")
    return world.record_result(
        outcome.fixture_id, outcome.home_goals, outcome.away_goals,
        penalties_home=outcome.penalties_home, penalties_away=outcome.penalties_away,
        resolver=outcome.resolver,
    )
