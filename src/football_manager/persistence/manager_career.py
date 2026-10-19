"""TS-15: opt-in, recoverable single-player manager career save slots.

The whole development session and its shared object references are saved in
one versioned SQLite transaction. No user-controlled class loading, pickle,
UI redesign, automated overwrites or changes to the legacy JSON format.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any, Mapping

from football_manager.dev_ui.session import DevelopmentSession
from football_manager.domain.lineup import MatchLineup
from football_manager.domain.tactics import Tactic
from football_manager.fast_simulation.models import FastMatchResult
from football_manager.ui_shell.models import UIRosterAdmin

from .career_adapter import world_career_document
from .models import (
    EntityKey, EntityLink, SaveDocument, SaveIntegrityError, SaveSection,
    UnsupportedSaveVersionError,
)
from .session_codec import capture_manager_graph, restore_manager_graph
from .sqlite_repository import SQLiteSaveRepository

MANAGER_STATE_VERSION = 19
_UI_STATE_VERSION = 1

# Explicit contract for the current disposable session. When a later version
# adds new persistent state, this must be revised and migrated intentionally.
_REQUIRED_FIELDS = frozenset({
    '_simulator', '_next_seed', '_seed', 'current_date',
    'home_club', 'home_lineup', 'home_tactic', 'tactical_studio', 'dressing_room', 'manager_inbox',
    'away_club', 'away_lineup', 'away_tactic',
    '_world_squads',
    '_league_club_names', '_league_fixture_plan', '_league_edition',
    '_league_results', '_current_league_fixture',
    '_cup_club_names', '_cup_edition', '_cup_round_definitions', '_cup_results', '_cup_rounds',
    '_continental_club_names', '_continental_edition', '_continental_routes',
    '_continental_round_definitions', '_continental_league_results',
    '_continental_knockout_results', '_continental_rounds', '_continental_transition',
    '_continental_direct_semifinalists', '_managed_schedule', '_season_calendar',
    '_active_match', '_official_premier_schedule', '_efl_divisions', '_efl_results',
    '_efl_current_round', '_world', '_world_club_names', '_career', 'dev_favorable_mode',
    '_home_reference_formation', '_home_reference_style', '_home_base_tactic_familiarity',
    '_away_reference_formation', '_away_reference_style', '_away_base_tactic_familiarity',
    '_home_chemistry', '_away_chemistry', '_last_played_match_metadata',
    'last_result', 'match_played',
})


@dataclass(frozen=True)
class LoadedManagerCareer:
    metadata: Any
    session: DevelopmentSession
    admin: UIRosterAdmin
    last_match_summary: dict | None


def validate_manager_session(session: DevelopmentSession) -> None:
    """Validate identity, calendar, timelines and selection before save/load."""
    if not isinstance(session, DevelopmentSession) or set(vars(session)) != _REQUIRED_FIELDS:
        raise SaveIntegrityError('manager career has incompatible state fields')
    if not isinstance(session.current_date, date) or type(session._seed) is not int or type(session._next_seed) is not int:
        raise SaveIntegrityError('invalid manager clock or simulation seed')
    if session._next_seed < 0 or session._seed < 0:
        raise SaveIntegrityError('invalid manager simulation seed')
    if not isinstance(session.dev_favorable_mode, bool) or not isinstance(session.match_played, bool):
        raise SaveIntegrityError('invalid manager mode or match flag')
    if session.last_result is not None:
        if not isinstance(session.last_result, FastMatchResult):
            raise SaveIntegrityError('invalid last simulated match result')
        try:
            session.last_result.__post_init__()
        except (TypeError, ValueError) as exc:
            raise SaveIntegrityError('saved last match result is inconsistent') from exc
    if session._career.current is not session._world:
        raise SaveIntegrityError('active world and career timeline are disconnected')
    if session._world._active_journal is not None or session._world._advance_queue is not None:
        raise SaveIntegrityError('cannot save while world simulation is active')
    try:
        from football_manager.domain.tactical_studio import TacticalStudioState
        from football_manager.domain.tactical_shapes import validate_shapes
        if not isinstance(session.tactical_studio, TacticalStudioState):
            raise SaveIntegrityError('invalid tactical studio state')
        session.tactical_studio.validate()
        from football_manager.domain.dressing_room import DressingRoomState
        from football_manager.domain.personality import Personality
        if not isinstance(session.dressing_room, DressingRoomState) or session.dressing_room.club_id != session.home_club.id:
            raise SaveIntegrityError('invalid dressing room state')
        session.dressing_room.validate({p.id for p in session.home_club.squad.players}, session.current_date)
        from football_manager.domain.manager_inbox import ManagerInbox
        if not isinstance(session.manager_inbox, ManagerInbox):
            raise SaveIntegrityError('manager inbox state missing')
        session.manager_inbox.validate(session.current_date, session.home_club.id)
        from football_manager.domain.football_world import FootballWorld
        from football_manager.services.world_squads import english_participants
        if (not isinstance(session._world_squads, FootballWorld)
                or session._world.football_world is not session._world_squads):
            raise SaveIntegrityError('disconnected persistent football world')
        session._world_squads.validate(english_participants(session._world))
        if session._world_squads.development_next_review is None:
            raise SaveIntegrityError('missing global development clock')
        for club in session._world_squads.clubs.values():
            for player in club.squad.players:
                if player.development.last_review > session.current_date or player.aging.last_review > session.current_date:
                    raise SaveIntegrityError('player development is ahead of the career date')
        if session._world_squads.season_label != session._world.season_label:
            raise SaveIntegrityError('football world is on a different season')
        if not set(session._world_squads.processed_fixtures).issubset(session._world.results):
            raise SaveIntegrityError('participation without a committed world result')
        for club in (session.home_club, session.away_club):
            if club.id in session._world_squads.clubs and session._world_squads.clubs[club.id] is not club:
                raise SaveIntegrityError('session club is not the canonical world club')
        session._career.validate_integrity()
        session._world.validate_integrity()
        for club, lineup, tactic in (
            (session.home_club, session.home_lineup, session.home_tactic),
            (session.away_club, session.away_lineup, session.away_tactic),
        ):
            if not isinstance(lineup, MatchLineup) or not isinstance(tactic, Tactic):
                raise SaveIntegrityError('invalid lineup or tactic')
            if lineup.club_id != club.id or lineup.formation != tactic.formation:
                raise SaveIntegrityError('lineup/formation does not match registered club')
            tactic._validate_role_assignments()
            validate_shapes(tactic.phase_shapes, tactic.formation.slot_ids)
            registered = {player.id: player for player in club.squad.players}
            for player in registered.values():
                if not isinstance(player.personality, Personality):
                    raise SaveIntegrityError('invalid saved personality')
                player.personality.validate()
                player.state._validate()
            if len(registered) != len(club.squad.players):
                raise SaveIntegrityError('duplicate player ID within a club')
            # Lineups may temporarily contain injured players after a match;
            # identity must remain canonical even in that recoverable state.
            for player in lineup.selected_players:
                if registered.get(player.id) is not player:
                    raise SaveIntegrityError('lineup does not reference canonical squad player')
        if session.home_club.id == session.away_club.id:
            raise SaveIntegrityError('manager and opponent have identical club IDs')
        if not isinstance(session._managed_schedule, dict):
            raise SaveIntegrityError('invalid managed fixture schedule')
        for fixture_id, match in session._managed_schedule.items():
            canonical = session._world.fixtures.get(fixture_id)
            if canonical is None or canonical.home_club_id != match.fixture.home_club_id or canonical.away_club_id != match.fixture.away_club_id:
                raise SaveIntegrityError('managed fixture identity does not match current world')
            if canonical.kickoff is not None and canonical.kickoff.date() != match.match_date:
                raise SaveIntegrityError('managed match date differs from the world calendar')
        if session._active_match is not None and session._active_match.fixture.fixture_id not in session._managed_schedule:
            raise SaveIntegrityError('active match missing from managed fixture schedule')
    except (ValueError, KeyError, AttributeError, TypeError, IndexError) as exc:
        if isinstance(exc, SaveIntegrityError):
            raise
        raise SaveIntegrityError('manager state failed domain validation') from exc


def _validate_admin(admin: UIRosterAdmin, session: DevelopmentSession) -> None:
    if not isinstance(admin, UIRosterAdmin) or not isinstance(admin.numbers, dict) or not isinstance(admin.transfer_statuses, dict):
        raise SaveIntegrityError('invalid manager squad metadata')
    from football_manager.ui_shell.models import TRANSFER_STATUSES
    active_ids = {p.id for p in session.home_club.squad.players}
    identifiers = active_ids | {pid for pid, entry in session._world_squads.retired_players.items()
                               if entry.club_id == session.home_club.id}
    for player_id, number in admin.numbers.items():
        if player_id not in identifiers or type(number) is not int or not 1 <= number <= 99:
            raise SaveIntegrityError('invalid saved shirt number')
    active_numbers = [n for pid, n in admin.numbers.items() if pid in active_ids]
    if len(set(active_numbers)) != len(active_numbers):
        raise SaveIntegrityError('duplicate saved shirt number')
    for player_id, status in admin.transfer_statuses.items():
        if player_id not in identifiers or status not in TRANSFER_STATUSES:
            raise SaveIntegrityError('invalid saved transfer flag')


def _manager_index(session: DevelopmentSession, *, include_world: bool = True):
    results = world_career_document(session._career)
    entities = set(results.entities)
    links = set(results.links)
    clubs = ({**session._world_squads.clubs, session.home_club.id: session.home_club,
              session.away_club.id: session.away_club}.values() if include_world
             else (session.home_club, session.away_club))
    for club in clubs:
        club_key = EntityKey('club', club.id)
        entities.add(club_key)
        for player in club.squad.players:
            player_key = EntityKey('player', player.id, club.id)
            entities.add(player_key)
            links.add(EntityLink(player_key, 'registered_with', club_key))
    if include_world:
        for entry in session._world_squads.retired_players.values():
            club_key = EntityKey('club', entry.club_id)
            player_key = EntityKey('player', entry.player.id, entry.club_id)
            entities.update((club_key, player_key))
            links.add(EntityLink(player_key, 'retired_from', club_key))
    return (tuple(sorted(entities, key=lambda e: (e.kind, e.scope, e.entity_id))),
            tuple(sorted(links, key=lambda e: (
                e.source.kind, e.source.scope, e.source.entity_id, e.relation,
                e.target.kind, e.target.scope, e.target.entity_id))))


def manager_career_document(session: DevelopmentSession, *,
                            admin: UIRosterAdmin | None = None,
                            last_match_summary: dict | None = None) -> SaveDocument:
    """One complete coherent snapshot; never persist pending UI-only edits."""
    validate_manager_session(session)
    admin = admin if admin is not None else UIRosterAdmin()
    _validate_admin(admin, session)
    if last_match_summary is not None and not isinstance(last_match_summary, dict):
        raise SaveIntegrityError('invalid saved match summary')
    entities, links = _manager_index(session)
    return SaveDocument(
        kind='manager_career',
        sections=(
            SaveSection('manager_state', MANAGER_STATE_VERSION, capture_manager_graph(session)),
            SaveSection('ui_metadata', _UI_STATE_VERSION, {
                'numbers': dict(admin.numbers),
                'transfer_statuses': dict(admin.transfer_statuses),
                'last_match_summary': last_match_summary,
            }),
        ),
        entities=entities, links=links,
    )


def save_manager_career(repository: SQLiteSaveRepository, *, slot_id: str,
                        display_name: str, session: DevelopmentSession,
                        expected_revision: int, admin: UIRosterAdmin | None = None,
                        last_match_summary: dict | None = None):
    """Save state atomically; optimistic revision protects other copies."""
    return repository.save(slot_id, display_name,
                           manager_career_document(session, admin=admin,
                                                   last_match_summary=last_match_summary),
                           expected_revision=expected_revision)


def load_manager_career(repository: SQLiteSaveRepository, slot_id: str) -> LoadedManagerCareer:
    """Reconstruct and fully validate a *new* session before it may be published."""
    stored = repository.load(slot_id)
    document = stored.document
    sections = {section.name: section for section in document.sections}
    if document.kind != 'manager_career' or set(sections) != {'manager_state', 'ui_metadata'}:
        raise SaveIntegrityError('slot is not a complete manager career')
    if sections['manager_state'].version not in (*range(1,MANAGER_STATE_VERSION+1),) or sections['ui_metadata'].version != _UI_STATE_VERSION:
        raise UnsupportedSaveVersionError('unsupported manager career section version')
    try:
        payload = sections['manager_state'].payload
        if payload.get('version') != sections['manager_state'].version:
            raise SaveIntegrityError('manager section and graph version disagree')
        legacy = payload['version'] < 5
        session = restore_manager_graph(payload, migrate_world=False)
        # Validate the ORIGINAL index before adding supplementary players. A
        # version-4 save cannot contain the newly generated registry's entities.
        entities, links = _manager_index(session, include_world=not legacy)
        if set(document.entities) != set(entities) or set(document.links) != set(links):
            raise SaveIntegrityError('manager career entity index does not match state')
        if legacy:
            from football_manager.services.world_squads import install_football_world
            install_football_world(session, migration=True)
        validate_manager_session(session)
        from football_manager.services.calendar_stabilization import stabilize_session_calendar
        stabilized = stabilize_session_calendar(session)
        if stabilized['moved']:
            validate_manager_session(session)
        ui = sections['ui_metadata'].payload
        if set(ui) != {'numbers', 'transfer_statuses', 'last_match_summary'}:
            raise SaveIntegrityError('invalid manager UI metadata fields')
        admin = UIRosterAdmin(numbers=ui['numbers'], transfer_statuses=ui['transfer_statuses'])
        _validate_admin(admin, session)
        summary = ui['last_match_summary']
        if summary is not None and not isinstance(summary, dict):
            raise SaveIntegrityError('invalid saved match summary')
    except (AttributeError, ValueError, TypeError, KeyError, IndexError) as exc:
        if isinstance(exc, SaveIntegrityError):
            raise
        raise SaveIntegrityError('could not reconstruct saved manager career') from exc
    return LoadedManagerCareer(stored.metadata, session, admin, summary)
