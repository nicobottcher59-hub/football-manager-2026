"""Read-only managed-club calendar for the portable UI.

Projects the existing SeasonCalendar + WorldSeasonRunner. Never invents
fixtures, simulates matches, or mutates dates/results. The initial DEV season
has only generated fictional club pairings.
"""
from __future__ import annotations

from datetime import date

from football_manager.dev_ui.session import DevelopmentSession
from football_manager.domain.knockout import resolve_knockout_tie
from football_manager.domain.international_calendar import (
    InternationalImpact, build_international_calendar,
)


def _aggregate_for_fixture(session: DevelopmentSession, fixture_id: str, competition_key: str,
                           stage_id: str, managed_id: str) -> dict | None:
    world = session._world
    if competition_key in world.cups:
        plan = world.cups[competition_key].plan_for_fixture(fixture_id)
    elif competition_key in world.staged:
        tournament = world.staged[competition_key]
        if stage_id == tournament.primary_stage_id:
            return None
        plan = tournament.plan_for_fixture(fixture_id)
    else:
        return None
    tie = plan.tie_for_fixture(fixture_id)
    if len(tie.fixtures) != 2:
        return None
    finished = [world.result_for(leg.fixture_id) for leg in tie.fixtures]
    actual = [result.knockout_result() for result in finished if result is not None]
    if not actual:
        return None
    outcome = resolve_knockout_tie(tie, actual)
    is_a = tie.club_a_id == managed_id
    return {
        "managed_goals": outcome.aggregate_a_goals if is_a else outcome.aggregate_b_goals,
        "opponent_goals": outcome.aggregate_b_goals if is_a else outcome.aggregate_a_goals,
        "complete": outcome.complete,
        "qualified": (outcome.winner_club_id == managed_id) if outcome.complete else None,
        "decided_by_penalties": outcome.decided_by_penalties,
    }


def calendar_read_model(session: DevelopmentSession) -> dict:
    """Export the actual managed club fixtures + registered match results.

    Unresolved knockout ties are *not* represented as fixed-date TBD slots.
    Time is from the canonical calendar, with its declared UTC timezone.
    """
    managed_id = session.home_club.id
    world = session._world
    games: list[dict] = []
    competitions: dict[str, str] = {}
    for scheduled in session._season_calendar.fixtures_for_club(managed_id):
        match = session._managed_schedule.get(scheduled.fixture_id)
        if match is None or scheduled.match_date is None:
            continue
        competition_id = match.competition_key
        competitions[competition_id] = match.competition_name
        is_home = match.fixture.home_club_id == managed_id
        opponent_id = match.fixture.away_club_id if is_home else match.fixture.home_club_id
        opponent = session._world_club_names.get(opponent_id, opponent_id)
        result = world.result_for(scheduled.fixture_id)
        penalties = None
        score = None
        outcome = None
        if result is not None:
            score = {"home": result.home_goals, "away": result.away_goals}
            if result.penalties_home or result.penalties_away:
                penalties = {"home": result.penalties_home, "away": result.penalties_away}
            outcome = session.outcome_for_result(
                result.home_goals, result.away_goals, managed_home=is_home,
                penalties_home=result.penalties_home, penalties_away=result.penalties_away,
            )
        games.append({
            "id": scheduled.fixture_id,
            "date": scheduled.match_date.isoformat(),
            "kickoff": scheduled.kickoff.isoformat() if scheduled.kickoff else None,
            "competition_id": competition_id,
            "competition": match.competition_name,
            "stage": match.stage_id,
            "round": match.round_label,
            "leg": match.fixture.leg_number,
            "source": scheduled.source.value,
            "status": scheduled.status.value,
            "rescheduled": scheduled.is_rescheduled,
            "original_date": (scheduled.original_kickoff.date().isoformat()
                              if scheduled.original_kickoff else None),
            "home": is_home,
            "home_club": session.home_club.name if is_home else opponent,
            "away_club": opponent if is_home else session.home_club.name,
            "opponent": opponent,
            "opponent_id": opponent_id,
            "home_id": scheduled.home_club_id, "away_id": scheduled.away_club_id,
            "score": score,
            "penalties": penalties,
            "outcome": outcome,  # V win, E draw, D loss, from the user's club view
            "aggregate": _aggregate_for_fixture(
                session, scheduled.fixture_id, competition_id, match.stage_id, managed_id
            ),
        })
    games.sort(key=lambda row: (row["kickoff"] or row["date"], row["id"]))
    # Use the same FIFA calendar that reprogrammed the canonical world fixtures.
    # For older legacy saves without a master, still show informational windows.
    year = int(session._season_calendar.season_label[:4])
    international = world.international_calendar or build_international_calendar(year, year + 1)
    fifa_windows = [
        {"id": event.event_id, "start": event.start_date.isoformat(),
         "end": event.end_date.isoformat(), "name": event.name}
        for event in international.events
        if event.impact is InternationalImpact.CLUB_BREAK
        and event.end_date >= date(year, 8, 1)
        and event.start_date <= date(year + 1, 7, 31)
    ]
    return {
        "source": "python-development-session",
        "persistent": False,
        "club": session.home_club.name,
        "date": session.current_date.isoformat(),
        "season": session._season_calendar.season_label,
        "timezone": session._season_calendar.timezone_name,
        "competitions": [{"id": key, "name": name} for key, name in sorted(competitions.items(), key=lambda e: e[1])],
        "matches": games,
        "fifa_windows": fifa_windows,
        "limitations": {
            "fictional_pairings": True,
            "match_previews": False,
            "advance_day": True,
            "auto_sim_managed_fixtures": True,
            "stadium_details": False,
            "unresolved_future_draws_omitted": True,
        },
    }
