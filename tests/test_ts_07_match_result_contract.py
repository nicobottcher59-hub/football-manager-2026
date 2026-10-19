"""TS-07: fast/background/future 2D results share one checked score contract."""
from __future__ import annotations

from datetime import date
from types import SimpleNamespace

import pytest

from football_manager.dev_ui import DevelopmentSession
from football_manager.services.match_result_contract import (
    FixtureMatchOutcome, from_match_score, from_world_result, record_managed_match,
)
from tools.stress_world_calendar import create_world


def test_real_managed_match_matches_world_outcome_without_moving_score():
    session = DevelopmentSession()
    fixture = session._active_match.fixture
    result = session.quick_simulate()
    projected = from_match_score(fixture, result)
    recorded = session._world.results[fixture.fixture_id]
    assert projected.to_world_result() == recorded
    assert projected == from_world_result(fixture, recorded)
    assert projected.home_club_id == fixture.home_club_id
    assert projected.away_club_id == fixture.away_club_id
    # The DEV FastMatchSimulator's match_id is an independent simulation ID.
    assert result.match_id != fixture.fixture_id


def test_mismatched_home_away_is_rejected_before_world_mutation():
    world, _ = create_world(leagues=1, seed=6077)
    fixture = next(iter(world.fixtures.values()))
    mismatched = SimpleNamespace(
        home_club_id=fixture.away_club_id, away_club_id=fixture.home_club_id,
        home_goals=2, away_goals=1, penalties_home=0, penalties_away=0,
    )
    before = len(world.results)
    with pytest.raises(ValueError, match="participants do not match"):
        record_managed_match(world, fixture, mismatched)
    assert len(world.results) == before
    assert world.fixtures[fixture.fixture_id] is fixture


def test_valid_generic_source_can_be_recorded_without_fast_engine():
    world, _ = create_world(leagues=1, seed=6077)
    fixture = next(iter(world.fixtures.values()))
    generic_2d_like_result = SimpleNamespace(
        home_club_id=fixture.home_club_id, away_club_id=fixture.away_club_id,
        home_goals=1, away_goals=2, penalties_home=0, penalties_away=0,
    )
    recorded = record_managed_match(world, fixture, generic_2d_like_result)
    assert recorded.resolver == "managed"
    assert world.result_for(fixture.fixture_id) == recorded
    assert from_world_result(fixture, recorded) == from_match_score(fixture, generic_2d_like_result)


def test_corrupt_score_or_wrong_world_fixture_id_is_rejected():
    world, _ = create_world(leagues=1, seed=6077)
    fixture = next(iter(world.fixtures.values()))
    invalid = SimpleNamespace(
        home_club_id=fixture.home_club_id, away_club_id=fixture.away_club_id,
        home_goals=-1, away_goals=1, penalties_home=0, penalties_away=0,
    )
    with pytest.raises(ValueError, match="negative"):
        from_match_score(fixture, invalid)
    with pytest.raises(ValueError, match="different clubs"):
        FixtureMatchOutcome("f", "a", "a", 1, 0, 0, 0, "managed")
    world_result = world.simulate_fixture(fixture.fixture_id)
    another = next(f for f in world.fixtures.values() if f.fixture_id != fixture.fixture_id)
    with pytest.raises(ValueError, match="does not belong"):
        from_world_result(another, world_result)


def test_background_resolver_projects_to_same_contract():
    world, _ = create_world(leagues=1, seed=5110)
    progress = world.advance_until(date(2026, 8, 31))
    assert progress.matches_played > 0
    for fid, result in world.results.items():
        projection = from_world_result(world.fixtures[fid], result)
        assert projection.to_world_result() == result
        assert projection.resolver == "background"


def test_managed_away_fixture_preserves_score_orientation():
    session = DevelopmentSession()
    for _ in range(8):
        fixture = session._active_match.fixture
        if fixture.home_club_id != session.home_club.id:
            result = session.quick_simulate()
            saved = session._world.results[fixture.fixture_id]
            assert saved.home_goals == result.home_goals
            assert saved.away_goals == result.away_goals
            assert from_world_result(fixture, saved) == from_match_score(fixture, result)
            return
        session.quick_simulate()
        session.continue_to_next_match()
    pytest.fail("no away fixture found in first eight managed matches")
