"""Apply generated-fixture repairs at the complete-career load boundary.

Loading never writes the source SQLite. Played fixtures and today's open match
are protected. Graph/entity validation must happen BEFORE this migration.
"""
from __future__ import annotations

from football_manager.domain.calendar_planner import repair_generated_calendar


def stabilize_session_calendar(session) -> dict:
    report = repair_generated_calendar(session._world, after_date=session.current_date)
    if not report['moved']:
        return report
    previous = session._active_match
    previous_id = previous.fixture.fixture_id if previous is not None else None
    session._sync_world_view()
    if session.match_played or (previous is not None and previous.match_date <= session.current_date):
        # Keep the post-match summary or the currently open pre-match identity.
        session._active_match = session._managed_schedule.get(previous_id)
    else:
        session._active_match = session._next_unplayed_managed_match()
        if (session._active_match is not None
                and session._active_match.fixture.fixture_id != previous_id):
            # Reordering a future fixture can change the previewed opponent.
            # Preview setup must not recover/train anyone merely by loading.
            from football_manager.services.managed_match_transaction import capture_player_state, restore_player_state
            registry = session._world_squads
            fixture = session._active_match.fixture
            opponent = fixture.away_club_id if fixture.home_club_id == session.home_club.id else fixture.home_club_id
            clubs = (registry.clubs[opponent],) if opponent in registry.clubs else ()
            saved = capture_player_state(clubs)
            recovery = dict(registry.last_recovery)
            try:
                session._prepare_development_opponent()
            finally:
                restore_player_state(saved)
                registry.last_recovery.clear()
                registry.last_recovery.update(recovery)
    if session._active_match is not None and session._active_match.competition_key == 'league':
        session._current_league_fixture = session._active_match.fixture
    return report
