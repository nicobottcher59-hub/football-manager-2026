"""Cross-competition smoke regression for the initial disposable career.

This deliberately compares two independent sessions instead of pinning a
particular score or kickoff day: football balancing and fixture policies may
change, but identical starting state and seeds must remain reproducible.
"""
from __future__ import annotations

from football_manager.dev_ui import DevelopmentSession
from football_manager.domain.calendar import ScheduledFixtureStatus


def _two_match_signature() -> tuple:
    session = DevelopmentSession()
    matches = []
    for index in range(2):
        scheduled = session._active_match
        assert scheduled is not None
        fixture_id = scheduled.fixture.fixture_id
        assert session._world.result_for(fixture_id) is None
        result = session.quick_simulate()
        saved = session._world.result_for(fixture_id)
        assert saved is not None
        assert saved.resolver == "managed"
        assert (saved.home_goals, saved.away_goals) == (
            result.home_goals, result.away_goals
        )
        assert session._world.fixtures[fixture_id].status is ScheduledFixtureStatus.PLAYED
        matches.append(
            (
                fixture_id,
                scheduled.competition_key,
                scheduled.match_date,
                result.home_goals,
                result.away_goals,
                result.goals,
                result.cards,
                result.statistics_home,
                result.statistics_away,
            )
        )
        if index == 0:
            assert session.can_continue
            session.continue_to_next_match()
            assert session.current_date > scheduled.match_date
    # The world ledger also includes matches played by AI-controlled clubs.
    world_results = tuple(
        sorted(
            (fixture_id, item.home_goals, item.away_goals, item.resolver)
            for fixture_id, item in session._world.results.items()
        )
    )
    return tuple(matches), world_results


def test_replaying_two_managed_matches_and_background_world_is_deterministic() -> None:
    assert _two_match_signature() == _two_match_signature()
