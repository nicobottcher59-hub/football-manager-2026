"""TS-05: deterministic calendar-heap regression tests (no timing assertions)."""
from __future__ import annotations

from datetime import date

import pytest

from football_manager.domain.calendar import ScheduledFixtureStatus
from football_manager.domain.world_runner import WorldRunProgress
from tools.stress_world_calendar import add_cup_proxy, create_world


CUTOFF = date(2027, 6, 30)


def _reference_advance(world, cutoff: date, protected: str | None = None) -> WorldRunProgress:
    """Intentionally slow pre-TS-05 reference implementation."""
    played = 0
    while True:
        ready = sorted(
            (item for item in world.fixtures.values()
             if item.status is ScheduledFixtureStatus.SCHEDULED
             and item.kickoff is not None and item.kickoff.date() <= cutoff),
            key=lambda item: (item.kickoff, item.fixture_id),
        )
        if not ready:
            return WorldRunProgress(played)
        first = ready[0]
        if protected and protected in (first.home_club_id, first.away_club_id):
            return WorldRunProgress(played, first.fixture_id)
        world.simulate_fixture(first.fixture_id)
        played += 1


def test_heap_produces_bit_identical_world_for_multiple_leagues():
    fast, _ = create_world(leagues=4, seed=5539)
    reference, _ = create_world(leagues=4, seed=5539)
    assert fast.advance_until(CUTOFF) == _reference_advance(reference, CUTOFF)
    assert fast.to_dict() == reference.to_dict()
    assert fast._advance_queue is None


def test_heap_picks_up_knockout_rounds_created_mid_progression():
    fast, _ = create_world(leagues=2, seed=6066)
    reference, _ = create_world(leagues=2, seed=6066)
    for world in (fast, reference):
        add_cup_proxy(world, seed=6066, year=2026)
    assert fast.advance_until(CUTOFF) == _reference_advance(reference, CUTOFF)
    assert fast.cups["stress-intercontinental-knockout-proxy"].champion_club_id
    assert fast.to_dict() == reference.to_dict()


def test_protected_match_stops_at_the_same_fixture_and_can_resume():
    fast, _ = create_world(leagues=2, seed=7400)
    reference, _ = create_world(leagues=2, seed=7400)
    protected = next(iter(fast.leagues.values())).participant_club_ids[0]
    actual = fast.advance_until(CUTOFF, protected_club_id=protected)
    expected = _reference_advance(reference, CUTOFF, protected=protected)
    assert actual == expected
    assert fast.to_dict() == reference.to_dict()
    assert actual.stopped_for_managed_fixture_id is not None
    for world in (fast, reference):
        world.simulate_fixture(actual.stopped_for_managed_fixture_id)
    assert fast.advance_until(CUTOFF, protected_club_id=protected) == _reference_advance(
        reference, CUTOFF, protected=protected,
    )
    assert fast.to_dict() == reference.to_dict()


def test_exception_releases_transient_queue_and_retry_is_deterministic(monkeypatch):
    world, _ = create_world(leagues=1, seed=1770)
    reference, _ = create_world(leagues=1, seed=1770)
    real_simulate = world.simulate_fixture

    def fail(_fixture_id):
        raise RuntimeError("synthetic simulation error")

    monkeypatch.setattr(world, "simulate_fixture", fail)
    with pytest.raises(RuntimeError, match="synthetic simulation error"):
        world.advance_until(CUTOFF)
    assert world._advance_queue is None
    assert world._advance_cutoff is None
    monkeypatch.setattr(world, "simulate_fixture", real_simulate)
    assert world.advance_until(CUTOFF) == _reference_advance(reference, CUTOFF)
    assert world.to_dict() == reference.to_dict()


def test_heap_tracks_fixtures_moved_into_and_out_of_cutoff():
    """Scheduling changes made mid-advance must be reflected immediately."""
    from dataclasses import replace
    from datetime import datetime, time, timezone, timedelta

    cutoff = date(2026, 8, 31)
    fast, _ = create_world(leagues=1, seed=7341)
    reference, _ = create_world(leagues=1, seed=7341)

    def attach_synthetic_reschedule(world):
        scheduled = sorted(world.fixtures.values(), key=lambda f: (f.kickoff, f.fixture_id))
        moving_out = next(item for item in scheduled if item.kickoff.date() <= cutoff
                          and item.kickoff > scheduled[0].kickoff)
        moving_in = next(item for item in scheduled if item.kickoff.date() > cutoff)
        original = world.simulate_fixture
        changes = 0

        def updated(fixture_id):
            nonlocal changes
            result = original(fixture_id)
            if changes == 0:
                world._put(world.fixtures, moving_out.fixture_id, replace(
                    world.fixtures[moving_out.fixture_id],
                    kickoff=datetime.combine(cutoff + timedelta(days=2), time(15), timezone.utc),
                ))
                world._put(world.fixtures, moving_in.fixture_id, replace(
                    world.fixtures[moving_in.fixture_id],
                    kickoff=scheduled[0].kickoff + timedelta(minutes=1),
                ))
                changes += 1
            return result

        world.simulate_fixture = updated

    attach_synthetic_reschedule(fast)
    attach_synthetic_reschedule(reference)
    assert fast.advance_until(cutoff) == _reference_advance(reference, cutoff)
    assert fast.to_dict() == reference.to_dict()
