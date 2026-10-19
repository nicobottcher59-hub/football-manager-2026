"""Smoke and known-limit tests for the diagnostic-only calendar stress harness."""
from __future__ import annotations

from dataclasses import replace
from datetime import date

import pytest

from football_manager.data.staged_2026_27 import build_uefa_2026_27
from football_manager.domain.season_cycle import finalize_season
from tools.stress_world_calendar import create_world, measure


def test_synthetic_four_league_season_finishes_without_collisions() -> None:
    actual = measure(leagues=4, seed=6060, simulate=True)
    assert actual.status == "pass"
    assert actual.final_fixtures == actual.results == 1520
    assert actual.conflicts_48h == 0
    assert actual.unplayed == 0
    assert actual.json_roundtrip_seconds is not None


def test_synthetic_blackouts_are_enforced_for_leagues_and_staged_uefa() -> None:
    actual = measure(leagues=4, seed=6060, blackouts=True,
                     staged_competitions=1, simulate=False)
    assert actual.status == "pass"
    assert actual.blackout_league_violations == 0
    assert actual.blackout_staged_violations == 0
    assert actual.results == 0
    assert actual.unplayed is None  # not simulated, not a completed season


def test_synthetic_congested_world_with_postponements_finishes() -> None:
    actual = measure(leagues=8, seed=6060, blackouts=True, staged_competitions=1,
                     cup_proxy=True, postponements=2, simulate=True)
    assert actual.status == "pass"
    assert actual.postponements_succeeded == 2
    assert actual.final_fixtures == actual.results
    assert actual.conflicts_48h == 0
    assert actual.orphan_results == 0
    assert actual.blackout_staged_violations == 0
    assert actual.blackout_cup_proxy_violations == 0
    assert actual.blackout_postponement_violations == 0
    assert actual.blackout_league_violations == 0


def test_staged_registration_rolls_back_when_window_cannot_be_scheduled() -> None:
    """Invalid windows must never partially register a tournament."""
    world, _ = create_world(leagues=4, seed=6060)
    clubs = [c for edition in world.leagues.values() for c in edition.participant_club_ids]
    stage = build_uefa_2026_27("champions-league", clubs[:36], seed=6060)
    stage = replace(stage, primary_dates=(date(2027, 7, 10), *stage.primary_dates[1:]))
    fixtures_before = set(world.fixtures)
    with pytest.raises(ValueError, match="no free staged fixture window"):
        world.register_staged(stage, strengths={})
    assert "champions-league" not in world.staged
    assert set(world.fixtures) == fixtures_before


def test_multicountry_world_is_not_supported_by_current_career_transition() -> None:
    """A finished synthetic world cannot use England-only WorldCareer finalization."""
    world, _ = create_world(leagues=8, seed=6060)
    world.advance_until(date(2027, 6, 30))
    assert len(world.results) == len(world.fixtures) == 3040
    with pytest.raises(ValueError, match="four English professional tiers"):
        finalize_season(world)
