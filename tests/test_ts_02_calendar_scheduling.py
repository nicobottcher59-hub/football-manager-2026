"""TS-02: published-date preference, round causality and protected fixtures."""
from dataclasses import replace
from datetime import date, datetime, time, timedelta, timezone

import pytest

from football_manager.data.staged_2026_27 import build_uefa_2026_27
from football_manager.domain.calendar import ScheduleSource, ScheduledFixture
from football_manager.domain.domestic_cups import DomesticCupRound, DomesticCupSeason
from football_manager.domain.world_runner import WorldSeasonRunner


def _cup(*, second: date = date(2026, 9, 17)) -> DomesticCupSeason:
    return DomesticCupSeason(
        "schedule-test-cup", "Schedule test cup", "2026/27", draw_seed=102,
        rounds=(
            DomesticCupRound("semi", "Semifinal", (date(2026, 9, 10),), entrants=("a", "b", "c", "d")),
            DomesticCupRound("final", "Final", (second,)),
        ),
    )


def _world_with_cup() -> tuple[WorldSeasonRunner, DomesticCupSeason]:
    world = WorldSeasonRunner()
    cup = _cup()
    world.register_cup(cup, strengths={club: 75 for club in ("a", "b", "c", "d")})
    return world, cup


def test_cup_prefers_published_anchor_to_equally_conflict_free_earlier_day():
    world, cup = _world_with_cup()
    for fixture in cup.plans[0].fixtures:
        assert world.fixtures[fixture.fixture_id].kickoff.date() == date(2026, 9, 10)
        assert world.fixtures[fixture.fixture_id].original_kickoff is None


def test_new_round_waits_until_late_previous_round_fixture_plus_rest():
    world, cup = _world_with_cup()
    first, last = [f.fixture_id for f in cup.plans[0].fixtures]
    delayed = replace(world.fixtures[last], kickoff=datetime(2026, 9, 20, 15, tzinfo=timezone.utc))
    world.fixtures[last] = delayed
    world.record_result(first, 2, 0)
    world.record_result(last, 1, 0)
    final = world.fixtures[cup.plans[-1].fixtures[0].fixture_id]
    assert final.kickoff >= delayed.kickoff + timedelta(hours=48)
    assert final.kickoff.date() > date(2026, 9, 20)
    assert final.original_kickoff.date() == date(2026, 9, 17)
    assert not world.calendar.detect_conflicts(minimum_rest_hours=48)


def test_new_round_rejects_impossible_postseason_and_rolls_back():
    world, cup = _world_with_cup()
    first, last = [f.fixture_id for f in cup.plans[0].fixtures]
    world.fixtures[last] = replace(world.fixtures[last], kickoff=datetime(2027, 6, 15, 15, tzinfo=timezone.utc))
    world.record_result(first, 1, 0)
    before = world.to_dict()
    with pytest.raises(ValueError, match="no available cup window"):
        world.record_result(last, 1, 0)
    assert world.to_dict() == before
    assert len(cup.plans) == 1


def test_generated_cup_does_not_move_official_league_slot():
    world = WorldSeasonRunner()
    world.leagues["l"] = object()  # Only ownership is consulted by scheduling.
    league = ScheduledFixture(
        "official", "l", "l-2026-27", "league", "a", "outsider",
        datetime(2026, 9, 10, 15, tzinfo=timezone.utc), ScheduleSource.OFFICIAL,
    )
    world.fixtures[league.fixture_id] = league
    cup = _cup()
    world.register_cup(cup, strengths={club: 75 for club in ("a", "b", "c", "d")})
    assert world.fixtures[league.fixture_id] == league
    involved = [world.fixtures[f.fixture_id] for f in cup.plans[0].fixtures
                if "a" in (f.home_club_id, f.away_club_id)]
    assert involved and involved[0].kickoff.date() != league.kickoff.date()


def test_uefa_replacements_only_use_competition_matchdays():
    clubs = tuple(f"club-{n:02}" for n in range(36))
    stage = build_uefa_2026_27("champions-league", clubs)
    world = WorldSeasonRunner()
    opening = stage.primary_fixtures[0]
    window = stage.primary_dates[0]
    # A played or protected cup fixture prevents using the official Wednesday.
    blocker = ScheduledFixture(
        "blocker", "other-cup", "other-cup-2026-27", "cup",
        opening.home_club_id, "guest", datetime.combine(window, time(19, 45), tzinfo=timezone.utc),
        ScheduleSource.GENERATED,
    )
    world.fixtures[blocker.fixture_id] = blocker
    world.register_staged(stage, strengths={club: 70 for club in clubs})
    assigned = world.fixtures[opening.fixture_id]
    assert assigned.kickoff.weekday() in (1, 2)
    assert assigned.kickoff.date() != window


def test_uefa_next_phase_not_backdated_before_delayed_group_fixture():
    clubs = tuple(f"club-{n:02}" for n in range(36))
    stage = build_uefa_2026_27("champions-league", clubs)
    world = WorldSeasonRunner()
    world.register_staged(stage, strengths={club: 70 for club in clubs})
    last = stage.primary_fixtures[-1].fixture_id
    delayed = datetime(2027, 2, 19, 19, 45, tzinfo=timezone.utc)
    world.fixtures[last] = replace(world.fixtures[last], kickoff=delayed)
    for fixture in stage.primary_fixtures:
        world.record_result(fixture.fixture_id, 1, 0)
    assert len(stage.knockout_plans) == 1
    first_plan = stage.knockout_plans[0]
    for fixture in first_plan.fixtures:
        scheduled = world.fixtures[fixture.fixture_id]
        assert scheduled.kickoff >= delayed + timedelta(hours=48)
        assert scheduled.kickoff.weekday() in (1, 2)
    assert not world.calendar.detect_conflicts(minimum_rest_hours=48)
