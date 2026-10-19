"""TS-09 regression: saved world calendars must respect temporal invariants."""
from __future__ import annotations

from dataclasses import replace
from datetime import date, datetime, timedelta, timezone

import pytest

from football_manager.data.staged_2026_27 import build_uefa_2026_27
from football_manager.domain.calendar import ScheduleSource, ScheduledFixtureStatus
from football_manager.domain.domestic_cups import DomesticCupRound, DomesticCupSeason
from football_manager.domain.world_runner import WorldSeasonRunner
from tools.stress_world_calendar import create_world


def _fixtures_for_club(world, club_id):
    return sorted((f for f in world.fixtures.values()
                   if club_id in (f.home_club_id, f.away_club_id)),
                  key=lambda f: (f.kickoff or datetime.max.replace(tzinfo=timezone.utc), f.fixture_id))


def _overlapping_world():
    world, _ = create_world(leagues=1, seed=9090)
    fixture = next(iter(world.fixtures.values()))
    other = next(f for f in _fixtures_for_club(world, fixture.home_club_id)
                 if f.fixture_id != fixture.fixture_id)
    world.fixtures[other.fixture_id] = replace(other, kickoff=fixture.kickoff)
    return world


def test_save_rejects_same_club_double_booking_before_replacing_existing_file(tmp_path):
    world, _ = create_world(leagues=1, seed=9090)
    target = tmp_path / 'world.json'
    world.save_json(target)
    original = target.read_bytes()
    first = next(iter(world.fixtures.values()))
    other = next(f for f in _fixtures_for_club(world, first.home_club_id)
                 if f.fixture_id != first.fixture_id)
    world.fixtures[other.fixture_id] = replace(other, kickoff=first.kickoff)
    with pytest.raises(ValueError, match='calendar conflict|double.book|overlap'):
        world.save_json(target)
    assert target.read_bytes() == original


def test_loading_rejects_double_booking_even_if_fixture_ids_and_owners_are_valid():
    world = _overlapping_world()
    with pytest.raises(ValueError, match='calendar conflict|double.book|overlap'):
        WorldSeasonRunner.from_dict(world.to_dict())


def test_minimum_rest_applies_across_competitions_and_different_dates():
    world, _ = create_world(leagues=1, seed=9091)
    first = next(iter(world.fixtures.values()))
    other = next(f for f in _fixtures_for_club(world, first.home_club_id)
                 if f.fixture_id != first.fixture_id)
    # Two kickoffs on distinct dates, 35 hours apart: not a same-day collision.
    world.fixtures[other.fixture_id] = replace(other, kickoff=first.kickoff + timedelta(hours=35))
    with pytest.raises(ValueError, match='insufficient_rest|calendar conflict'):
        world.validate_integrity()


def test_played_match_also_blocks_conflicting_pending_fixture():
    world, _ = create_world(leagues=1, seed=9092)
    first = next(iter(world.fixtures.values()))
    world.record_result(first.fixture_id, 1, 0)
    other = next(f for f in _fixtures_for_club(world, first.home_club_id)
                 if f.fixture_id != first.fixture_id)
    world.fixtures[other.fixture_id] = replace(other, kickoff=first.kickoff)
    with pytest.raises(ValueError, match='calendar conflict|overlap'):
        world.validate_integrity()


def test_inactive_fixture_does_not_reserve_its_original_slot():
    world, _ = create_world(leagues=1, seed=9093)
    first = next(iter(world.fixtures.values()))
    # Use the reverse fixture between the same two clubs.  Any other opponent
    # would already have a round-one fixture on this date.
    other = next(f for f in _fixtures_for_club(world, first.home_club_id)
                 if f.fixture_id != first.fixture_id
                 and {f.home_club_id, f.away_club_id}
                    == {first.home_club_id, first.away_club_id})
    # Postponement retains provenance, but no current kickoff.
    world.fixtures[first.fixture_id] = replace(
        first, kickoff=None, original_kickoff=first.kickoff,
        status=ScheduledFixtureStatus.POSTPONED,
    )
    world.fixtures[other.fixture_id] = replace(other, kickoff=first.kickoff)
    world.validate_integrity()
    assert WorldSeasonRunner.from_dict(world.to_dict()).to_dict() == world.to_dict()


def test_generated_fixture_in_fifa_club_break_is_rejected_on_load_and_save(tmp_path):
    world, _ = create_world(leagues=1, seed=9094, year=2027, master_calendar=True)
    first = next(iter(world.fixtures.values()))
    # Middle of the 2027 combined September/October FIFA club break.
    forbidden = datetime(2027, 9, 26, 15, tzinfo=timezone.utc)
    world.fixtures[first.fixture_id] = replace(first, kickoff=forbidden)
    with pytest.raises(ValueError, match='international.*break|FIFA'):
        world.save_json(tmp_path / 'invalid.json')
    with pytest.raises(ValueError, match='international.*break|FIFA'):
        WorldSeasonRunner.from_dict(world.to_dict())


def test_official_fixture_is_not_silently_rewritten_by_fifa_policy():
    world, _ = create_world(leagues=1, seed=9095, year=2027, master_calendar=True)
    fixture = next(iter(world.fixtures.values()))
    official = replace(fixture, source=ScheduleSource.OFFICIAL,
                       kickoff=datetime(2027, 9, 27, 15, tzinfo=timezone.utc))
    world.fixtures[fixture.fixture_id] = official
    world.validate_integrity()
    restored = WorldSeasonRunner.from_dict(world.to_dict())
    assert restored.fixtures[fixture.fixture_id] == official


def test_cup_final_cannot_be_dated_before_completed_semifinals():
    world = WorldSeasonRunner()
    cup = DomesticCupSeason(
        'calendar-order-cup', 'Cup', '2026/27', draw_seed=99,
        rounds=(
            DomesticCupRound('semi', 'Semifinal', (date(2026, 9, 10),), entrants=('a', 'b', 'c', 'd')),
            DomesticCupRound('final', 'Final', (date(2026, 9, 17),)),
        ),
    )
    world.register_cup(cup, strengths={x: 70 for x in 'abcd'})
    for fixture in cup.plans[0].fixtures:
        world.record_result(fixture.fixture_id, 1, 0)
    final = cup.plans[1].fixtures[0]
    earlier = datetime(2026, 9, 3, 15, tzinfo=timezone.utc)
    world.fixtures[final.fixture_id] = replace(world.fixtures[final.fixture_id], kickoff=earlier)
    assert not world.calendar.detect_conflicts(minimum_rest_hours=48), 'chrono test should isolate order from rest'
    with pytest.raises(ValueError, match='chronolog|round order'):
        world.validate_integrity()


def test_unchanged_generated_world_roundtrip_with_fifa_and_uefa():
    world, _ = create_world(leagues=4, seed=9096, year=2027, master_calendar=True)
    clubs = [club for league in world.leagues.values() for club in league.participant_club_ids]
    competition = build_uefa_2026_27('champions-league', clubs[:36], season_start_year=2027)
    world.register_staged(competition, strengths={})
    world.validate_integrity()
    assert WorldSeasonRunner.from_dict(world.to_dict()).to_dict() == world.to_dict()


def test_cancelled_fixture_does_not_create_false_international_violation():
    world, _ = create_world(leagues=1, seed=9097, year=2027, master_calendar=True)
    first = next(iter(world.fixtures.values()))
    # A cancelled game retains its old kickoff as audit metadata, not as a match.
    world.fixtures[first.fixture_id] = replace(
        first, kickoff=datetime(2027, 9, 26, 15, tzinfo=timezone.utc),
        status=ScheduledFixtureStatus.CANCELLED,
    )
    assert first.fixture_id not in world.international_window_violations()
    world.validate_integrity()


def test_second_leg_cannot_be_played_before_first_leg_without_calendar_overlap():
    from football_manager.domain.knockout import KnockoutLegFormat
    cup = DomesticCupSeason(
        'two-legs', 'Two Leg Cup', '2026/27', draw_seed=98,
        rounds=(DomesticCupRound(
            'semi', 'Semifinal', (date(2026, 9, 10), date(2026, 9, 17)),
            entrants=('a', 'b', 'c', 'd'), leg_format=KnockoutLegFormat.TWO_LEGGED,
        ), DomesticCupRound('final', 'Final', (date(2026, 9, 24),))),
    )
    world = WorldSeasonRunner()
    world.register_cup(cup, strengths={x: 70 for x in 'abcd'})
    second_leg = next(f for f in cup.plans[0].fixtures if f.leg_number == 2)
    world.fixtures[second_leg.fixture_id] = replace(
        world.fixtures[second_leg.fixture_id],
        kickoff=datetime(2026, 9, 1, 19, 45, tzinfo=timezone.utc),
    )
    assert not world.calendar.detect_conflicts(minimum_rest_hours=48)
    with pytest.raises(ValueError, match='tie-leg chronology'):
        world.validate_integrity()


def test_postponed_fixture_with_kickoff_is_not_accepted_as_inactive():
    world, _ = create_world(leagues=1, seed=9098)
    first = next(iter(world.fixtures.values()))
    world.fixtures[first.fixture_id] = replace(
        first, status=ScheduledFixtureStatus.POSTPONED,
        original_kickoff=first.kickoff,
    )
    with pytest.raises(ValueError, match='postponed fixture.*active kickoff'):
        world.validate_integrity()


def test_staged_knockout_round_cannot_precede_its_primary_phase():
    clubs = tuple(f'europe-{i:02d}' for i in range(36))
    stage = build_uefa_2026_27('champions-league', clubs)
    world = WorldSeasonRunner()
    world.register_staged(stage, strengths={club: 70 for club in clubs})
    for fixture in stage.primary_fixtures:
        world.record_result(fixture.fixture_id, 1, 0)
    assert stage.knockout_plans
    playoff = stage.knockout_plans[0].fixtures[0]
    world.fixtures[playoff.fixture_id] = replace(
        world.fixtures[playoff.fixture_id],
        kickoff=datetime(2026, 8, 5, 19, 45, tzinfo=timezone.utc),
    )
    assert not world.calendar.detect_conflicts(minimum_rest_hours=48)
    with pytest.raises(ValueError, match='calendar round chronology'):
        world.validate_integrity()
