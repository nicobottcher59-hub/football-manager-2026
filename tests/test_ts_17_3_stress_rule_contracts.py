"""TS-17.3: declared stress blackouts must be enforced, not advisory."""
from datetime import date

from football_manager.domain.international_calendar import (
    InternationalDateSource, InternationalImpact, InternationalCalendar,
)
from football_manager.domain.world_runner import WorldSeasonRunner
from tools.stress_world_calendar import create_world, measure


def test_synthetic_blackouts_are_visible_to_the_actual_world_scheduler():
    world, blocks = create_world(leagues=4, seed=6060, blackouts=True)
    assert world.international_calendar is not None
    for block in blocks:
        events = [event for event in world.international_calendar.events
                  if event.start_date == block.start_date and event.end_date == block.end_date]
        assert len(events) == 1
        assert events[0].impact is InternationalImpact.CLUB_BREAK
        assert events[0].source is InternationalDateSource.OVERRIDE
    assert not world.international_window_violations()
    restored = WorldSeasonRunner.from_dict(world.to_dict())
    assert restored.international_calendar == world.international_calendar


def test_blackout_congestion_stress_reports_no_unjustified_violation():
    summary = measure(leagues=8, seed=6060, blackouts=True, staged_competitions=1,
                      cup_proxy=True, postponements=2, simulate=True)
    assert summary.status == 'pass', summary.error
    assert summary.conflicts_48h == summary.orphan_results == 0
    assert summary.final_fixtures == summary.results
    assert (summary.blackout_league_violations, summary.blackout_staged_violations,
            summary.blackout_cup_proxy_violations,
            summary.blackout_postponement_violations) == (0, 0, 0, 0)


def test_stress_combines_synthetic_and_fifa_calendar_without_relabelling_sources():
    world, blocks = create_world(leagues=4, seed=6060, blackouts=True,
                                 master_calendar=True, year=2027)
    assert world.international_calendar is not None
    events = world.international_calendar.events
    assert any(event.source is InternationalDateSource.OVERRIDE for event in events)
    assert any(event.source is InternationalDateSource.OFFICIAL for event in events)
    assert not world.international_window_violations()
    assert world.international_calendar.stops_club_football(date(2027, 9, 10))
