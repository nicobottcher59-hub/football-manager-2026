"""UI-3.4: authoritative DEV day-by-day progression over the existing Python world.

The UI-3.5 match screen is implemented separately in ui_shell.match; full
career save/load remains future work. FastMatchSimulator resolves managed auto-sim matches,
while WorldSeasonRunner resolves other clubs. Commands are committed by the HTTP
runtime only if the entire operation succeeds (see server.py).
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Callable

from football_manager.services import recover_player_between_matches

from football_manager.dev_ui.session import DevelopmentSession


MAX_SKIP_DAYS = 370
MAX_MANAGED_MATCHES_PER_SKIP = 180


def season_cutoff(session: DevelopmentSession) -> date:
    return date(int(session._world.season_label[:4]) + 1, 6, 30)


def pending_managed_match(session: DevelopmentSession):
    return session._next_unplayed_managed_match()


def pending_transfer_decisions(session) -> list[dict]:
    """Unanswered club offers or signed club terms awaiting player consent."""
    cid, today = session.home_club.id, session.current_date
    pending = []
    for deal in session._world_squads.transfer_offers.values():
        if cid not in (deal.seller_id, deal.buyer_id) or deal.expires_on < today:
            continue
        if not (deal.status == 'manager_turn' and deal.proposed_by != cid or deal.status == 'agreed'):
            continue
        contract = session._world_squads.contracts.get(deal.player_id)
        player = None
        if contract and contract.club_id in session._world_squads.clubs:
            player = session._world_squads.clubs[contract.club_id].squad._players.get(deal.player_id)
        pending.append({'deal_id':deal.deal_id, 'player_id':deal.player_id,
            'player':player.full_name if player else deal.player_id,
            'kind':'incoming_offer' if deal.seller_id == cid else 'negotiation_response',
            'status':deal.status, 'expires_on':deal.expires_on.isoformat()})
    return sorted(pending, key=lambda row:(row['expires_on'],row['deal_id']))


def progression_read_model(session: DevelopmentSession) -> dict:
    upcoming = pending_managed_match(session)
    today_match = (upcoming is not None and upcoming.match_date <= session.current_date)
    if session.current_date >= season_cutoff(session):
        button = "Season finished" if session.season_finished else "Season status"
    else:
        button = "Go to Match" if today_match else "Continue"
    return {
        "source": "python-world-runner", "persistent": False,
        "date": session.current_date.isoformat(), "season": session._world.season_label,
        "season_cutoff": season_cutoff(session).isoformat(),
        "managed_club": session.home_club.name,
        "action": "go_to_match" if today_match else "advance_day",
        "button_label": button,
        "match_day": today_match,
        "pending_match": ({
            "id": upcoming.fixture.fixture_id, "date": upcoming.match_date.isoformat(),
            "opponent": session._world_club_names.get(
                upcoming.fixture.away_club_id if upcoming.fixture.home_club_id == session.home_club.id
                else upcoming.fixture.home_club_id, "Unknown opponent"),
            "competition": upcoming.competition_name,
            "home": upcoming.fixture.home_club_id == session.home_club.id,
        } if upcoming else None),
        "season_complete": session.season_finished,
        "intervention_events_supported": False,
        "pending_transfer_decisions": pending_transfer_decisions(session),
        "resume_target": getattr(session, '_calendar_resume_target', None),
        "auto_sim_includes_managed_matches": True,
        "match_screen_supported": True,
        "saving_supported": False,
    }


def _bind_next_match(session: DevelopmentSession) -> None:
    """Keep managed snapshot/opposition in sync with newly scheduled fixtures."""
    next_match = pending_managed_match(session)
    previous_id = session._active_match.fixture.fixture_id if session._active_match else None
    next_id = next_match.fixture.fixture_id if next_match else None
    session._active_match = next_match
    if next_id != previous_id and next_match is not None:
        session._prepare_development_opponent()
    elif next_match is not None:
        # TS-24.5: AI transfers can change the opponent's registered squad
        # while the next managed fixture remains the same. A cached preview
        # lineup must never reference players sold to another club. Do not
        # rebuild merely because of fatigue/injury; ordinary match-day
        # preparation already handles availability.
        opponent = getattr(session, 'away_club', None)
        lineup = getattr(session, 'away_lineup', None)
        if opponent is not None and lineup is not None:
            canonical = session._world_squads.clubs.get(opponent.id)
            if canonical is not None and any(
                not canonical.squad.contains(player.id)
                or canonical.squad.get(player.id) is not player
                for player in lineup.selected_players
            ):
                session._prepare_development_opponent()
    if next_id != previous_id:
        session.last_result = None
        session.match_played = False


def _settle_scheduled_registrations(session: DevelopmentSession) -> None:
    """Finish only agreements signed by a manager or agent before the window."""
    from dataclasses import replace
    from football_manager.services.transfer_windows import window_open
    from football_manager.services.transfer_personal import _finish
    registry=session._world_squads
    today=session.current_date
    for key, deal in tuple(sorted(registry.transfer_offers.items())):
        if deal.status!='pending_window' or not window_open(today,registry.clubs[deal.buyer_id].country):
            continue
        # Existing transfer and contract safety checks are reused at execution.
        # If conditions materially changed, do not fabricate a completed deal.
        try:
            _finish(session,deal,deal.personal_terms)
            # Link activated loan options to the completed permanent purchase.
            # Completion is never recorded before the transfer actually settles.
            for loan_id, loan in tuple(registry.loans.items()):
                if loan.option_pending_deal_id==deal.deal_id:
                    registry.loans[loan_id]=replace(loan,status='purchased',completed_on=today)
        except ValueError as exc:
            registry.transfer_offers[key]=replace(deal,status='failed',
                reason=f'Scheduled transfer could not complete: {str(exc)[:165]}')


def _move_day(session: DevelopmentSession) -> int:
    new_day = session.current_date + timedelta(days=1)
    if new_day > season_cutoff(session):
        raise ValueError("Current season has ended. Next season transition is not enabled here yet.")
    # Progress the background world, stopping before any Northbridge fixture.
    result = session._world.advance_until(new_day, protected_club_id=session.home_club.id)
    if result.matches_played:
        session._sync_world_view()
    # Contract expirations and loan returns can change squad registration on
    # the monthly boundary even when there was no background fixture.
    from football_manager.services.player_aging import repair_managed_unavailable
    repair_managed_unavailable(session)
    _bind_next_match(session)
    if result.stopped_for_managed_fixture_id:
        upcoming = pending_managed_match(session)
        if upcoming is None or upcoming.match_date != new_day:
            raise RuntimeError("A managed fixture is overdue or was not projected into the calendar")
    # Recovery happens once for every actual elapsed day, not once per click.
    from football_manager.services.club_support import recover_managed_players
    recover_managed_players(session, days=1, start_date=session.current_date)
    session.current_date = new_day
    # Registration of already-signed agreements is a dated market event, not
    # an unanswered decision. No automatic acceptance of incoming proposals.
    _settle_scheduled_registrations(session)
    from football_manager.services.professional_scouting import advance_professional_scouting
    advance_professional_scouting(session, new_day)
    # Re-select/recover the canonical rival when the fixture becomes playable;
    # a previously previewed opponent may have played in the meantime.
    if session._active_match is not None and session._active_match.match_date <= new_day:
        session._prepare_development_opponent()
    session.update_dressing_room()
    from football_manager.services.manager_inbox import synchronize_manager_inbox
    synchronize_manager_inbox(session)
    session.match_played = False
    return result.matches_played


def advance_day(session: DevelopmentSession) -> dict:
    if session.current_date >= season_cutoff(session):
        raise ValueError("Reached the end of this season")
    pending = pending_managed_match(session)
    if pending is not None and pending.match_date <= session.current_date:
        raise ValueError("Go to Match: the club has a pending match today. Open the match tab or use Calendar auto-sim.")
    previous = session.current_date
    processed = _move_day(session)
    return {"mode": "daily", "from_date": previous.isoformat(),
            "to_date": session.current_date.isoformat(), "managed_matches": 0,
            "background_matches": processed, "auto_results": [],
            "stopped_for_decision": False, "state": progression_read_model(session)}


def _finish_day(session: DevelopmentSession, auto_results: list[dict]) -> int:
    """Process all fixtures through current_date, including managed FastSim."""
    background_count = 0
    for _ in range(MAX_MANAGED_MATCHES_PER_SKIP):
        progress = session._world.advance_until(session.current_date, protected_club_id=session.home_club.id)
        background_count += progress.matches_played
        if progress.matches_played:
            session._sync_world_view()
        _bind_next_match(session)
        if not progress.stopped_for_managed_fixture_id:
            return background_count
        upcoming = pending_managed_match(session)
        if (upcoming is None or upcoming.fixture.fixture_id != progress.stopped_for_managed_fixture_id
                or upcoming.match_date != session.current_date):
            raise RuntimeError("Managed fixture could not be activated on its scheduled date")
        # Use the actual managed squad/position/condition/tactics, never cheap
        # WorldRunner results for Northbridge. quick_simulate registers scores.
        if session.match_played:
            session.match_played = False
        session._prepare_development_opponent()
        from football_manager.services.player_aging import repair_managed_unavailable
        repair_managed_unavailable(session)
        result = session.quick_simulate()
        auto_results.append({
            "id": upcoming.fixture.fixture_id,
            "date": session.current_date.isoformat(),
            "competition": upcoming.competition_name,
            "home_goals": result.home_goals,
            "away_goals": result.away_goals,
            "penalties_home": result.penalties_home,
            "penalties_away": result.penalties_away,
        })
        session.match_played = False
    raise RuntimeError("Exceeded the managed-match safety limit during progression")


def simulate_until(
    session: DevelopmentSession, target: date,
    *, on_day: Callable[[date, list[dict]], None] | None = None,
) -> dict:
    if not isinstance(target, date) or isinstance(target, datetime):
        raise ValueError("target must be a calendar date")
    start = session.current_date
    if target < start:
        raise ValueError("Cannot simulate into the past")
    if target > season_cutoff(session):
        raise ValueError("Target is outside the current season; transition separately")
    if (target - start).days > MAX_SKIP_DAYS:
        raise ValueError("Requested simulation interval is too long")
    auto_results: list[dict] = []
    background = 0
    # Explicit request to simulate through today resolves a same-day match too.
    # Continue, unlike this action, always stops on a managed match day.
    _settle_scheduled_registrations(session)
    before = set(session._world.results) if on_day is not None else None
    def publish_day():
        nonlocal before
        if on_day is None:
            return
        # A single day may include dozens of background fixtures and one
        # or more managed matches. Every emitted result exists in the world
        # ledger; none is a demo score or a fabricated fixture.
        ids = session._world.results.keys() - before
        fixtures = session._world.fixtures
        ordered = sorted(ids, key=lambda fid: (
            fixtures[fid].kickoff.isoformat() if fixtures[fid].kickoff else "", fid,
        ))
        day_results = []
        for fid in ordered:
            fixture = fixtures[fid]
            score = session._world.results[fid]
            own = session.home_club.id in (fixture.home_club_id, fixture.away_club_id)
            home_name = session._world_club_names.get(fixture.home_club_id, fixture.home_club_id)
            away_name = session._world_club_names.get(fixture.away_club_id, fixture.away_club_id)
            from football_manager.ui_shell.career_history import _competition_name
            day_results.append({
                'type': 'result', 'id': fid, 'date': (fixture.match_date or session.current_date).isoformat(),
                'competition_id': fixture.competition_id,
                'competition': _competition_name(session._world, fixture.competition_id),
                'home_club': home_name, 'away_club': away_name,
                'home_id': fixture.home_club_id, 'away_id': fixture.away_club_id,
                'home_goals': score.home_goals, 'away_goals': score.away_goals,
                'penalties_home': score.penalties_home,
                'penalties_away': score.penalties_away,
                'managed': own, 'resolver': score.resolver,
            })
        on_day(session.current_date, day_results)
        before = set(session._world.results)

    while True:
        # TS-FIX-04: Calendar is deliberately unattended delegation. Offers
        # may expire while fast-forwarding; never auto-consent or auto-sell.
        background += _finish_day(session, auto_results)
        from football_manager.services.manager_inbox import synchronize_manager_inbox
        synchronize_manager_inbox(session)
        publish_day()
        if session.current_date == target:
            break
        background += _move_day(session)
    decisions = pending_transfer_decisions(session)
    session._calendar_resume_target = None
    return {
        "mode": "calendar_auto_sim", "from_date": start.isoformat(),
        "to_date": session.current_date.isoformat(),
        "managed_matches": len(auto_results),
        "background_matches": background,
        "auto_results": auto_results,
        "stopped_for_decision": False,
        "decisions": decisions,
        "requested_target": target.isoformat(),
        "state": progression_read_model(session),
    }
