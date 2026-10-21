"""TS-15: versioned JSON object graph for the disposable manager session.

Unlike pickle this decoder cannot name arbitrary Python classes or execute
user-provided callables. The whitelist is limited to known game-state modules.
References are explicit: club players shared by squads/lineups stay identical.
This is a snapshot codec, not a general-purpose object serializer.
"""
from __future__ import annotations

from dataclasses import fields, is_dataclass
import base64
import json
import zlib
from datetime import date, datetime
from enum import Enum
from importlib import import_module
from math import isfinite
import re
from typing import Any

from football_manager.dev_ui.session import DevelopmentSession
from football_manager.domain.world_runner import WorldSeasonRunner

from .models import SaveIntegrityError, UnsupportedSaveVersionError

GRAPH_VERSION = 24
# TS-24.13: a fully populated 92-club career already needs ~286k live
# graph nodes after its first season (TS-24.12 rejected that save). Keep
# the integrity limit finite but accommodate normal longitudinal growth.
# The graph schema/version and all archive decompression guards are unchanged.
MAX_NODES = 1_000_000
MAX_ARCHIVED_WORLD_BYTES = 64 * 1024 * 1024

# Only installed, audited game model packages may appear in a save. Never
# import arbitrary modules or resolve dotted attribute expressions from JSON.
_ALLOWED_MODULES = frozenset({
    'football_manager.dev_ui.session',
    'football_manager.fast_simulation.engine',
    'football_manager.fast_simulation.models',
    'football_manager.domain.attributes',
    'football_manager.domain.calendar',
    'football_manager.domain.career',
    'football_manager.domain.career_transition',
    'football_manager.domain.club',
    'football_manager.domain.football_world',
    'football_manager.domain.youth_academy',
    'football_manager.domain.market_valuation',
    'football_manager.domain.club_economy',
    'football_manager.domain.transfer_negotiation',
    'football_manager.domain.transfer_personal',
    'football_manager.domain.loan_market',
    'football_manager.domain.season_statistics',
    'football_manager.domain.competition',
    'football_manager.domain.domestic_cups',
    'football_manager.domain.enums',
    'football_manager.domain.formation',
    'football_manager.domain.international_calendar',
    'football_manager.domain.knockout',
    'football_manager.domain.league',
    'football_manager.domain.lineup',
    'football_manager.domain.match_context',
    'football_manager.domain.multistage',
    'football_manager.domain.player',
    'football_manager.domain.personality',
    'football_manager.domain.player_development',
    'football_manager.domain.player_aging',
    'football_manager.domain.dressing_room',
    'football_manager.domain.manager_inbox',
    'football_manager.domain.club_support',
    'football_manager.domain.career_recognition',
    'football_manager.domain.player_state',
    'football_manager.domain.positional_familiarity',
    'football_manager.domain.season_cycle',
    'football_manager.domain.squad',
    'football_manager.domain.staged_world',
    'football_manager.domain.tactical_familiarity',
    'football_manager.domain.tactical_instructions',
    'football_manager.domain.tactical_presets',
    'football_manager.domain.tactics',
    'football_manager.domain.tactical_shapes',
    'football_manager.domain.tactical_studio',
    'football_manager.domain.world_runner',
    'football_manager.data.efl_2026_27',
    'football_manager.data.official_schedule',
})
_CLASS_IDENTIFIER = re.compile(r'^[A-Za-z][A-Za-z0-9_]*$')


def _class_name(value: object) -> str:
    cls = value if isinstance(value, type) else type(value)
    if cls.__module__ not in _ALLOWED_MODULES or not _CLASS_IDENTIFIER.fullmatch(cls.__name__):
        raise SaveIntegrityError(f'unsupported career-state class: {cls.__module__}.{cls.__name__}')
    return f'{cls.__module__}:{cls.__name__}'


def _trusted_type(name: object) -> type:
    if not isinstance(name, str) or name.count(':') != 1:
        raise SaveIntegrityError('invalid saved state type')
    module, class_name = name.split(':')
    if module not in _ALLOWED_MODULES or not _CLASS_IDENTIFIER.fullmatch(class_name):
        raise SaveIntegrityError('saved state type is not permitted')
    candidate = getattr(import_module(module), class_name, None)
    if not isinstance(candidate, type) or candidate.__module__ != module:
        raise SaveIntegrityError('unknown saved state type')
    return candidate


def capture_manager_graph(session: DevelopmentSession) -> dict:
    """Capture all DEV session attributes with object identity preserved."""
    if not isinstance(session, DevelopmentSession):
        raise TypeError('DevelopmentSession required')
    if session._world._active_journal is not None or session._world._advance_queue is not None:
        raise ValueError('cannot save a world during an active transaction/simulation')

    nodes: list[dict] = []
    memo: dict[int, int] = {}

    def encode(value: Any):
        if value is None or type(value) in (str, int, bool):
            return value
        if type(value) is float:
            if not isfinite(value):
                raise SaveIntegrityError('non-finite value in manager state')
            return value
        oid = id(value)
        if oid in memo:
            return {'$ref': memo[oid]}
        if len(nodes) >= MAX_NODES:
            raise SaveIntegrityError('save object graph is too large')
        index = len(nodes)
        memo[oid] = index
        nodes.append({})
        # Full fixture ledgers for FINISHED seasons are immutable history in
        # the career. Encoding them as separate compressed snapshots avoids
        # counting tens of thousands of historical fixtures as live graph
        # nodes every year. The CURRENT world is still encoded normally so
        # shared references (session, career, lineups) remain canonical.
        if isinstance(value, WorldSeasonRunner) and value is not session._world:
            if value._active_journal is not None or value._advance_queue is not None:
                raise SaveIntegrityError('cannot archive world during a simulation')
            raw = json.dumps(value.to_dict(), separators=(',', ':'),
                             ensure_ascii=False).encode('utf-8')
            if len(raw) > MAX_ARCHIVED_WORLD_BYTES:
                raise SaveIntegrityError('historic season archive is too large')
            node = {'type': 'archived_world',
                    'data': base64.b64encode(zlib.compress(raw, level=6)).decode('ascii')}
        elif isinstance(value, Enum):
            node = {'type': 'enum', 'class': _class_name(value), 'value': value.name}
        elif isinstance(value, datetime):
            node = {'type': 'datetime', 'value': value.isoformat()}
        elif isinstance(value, date):
            node = {'type': 'date', 'value': value.isoformat()}
        elif isinstance(value, dict):
            node = {'type': 'dict', 'items': [[encode(k), encode(v)] for k, v in value.items()]}
        elif isinstance(value, list):
            node = {'type': 'list', 'items': [encode(x) for x in value]}
        elif isinstance(value, tuple):
            node = {'type': 'tuple', 'items': [encode(x) for x in value]}
        elif isinstance(value, (set, frozenset)):
            node = {'type': 'frozenset' if isinstance(value, frozenset) else 'set',
                    'items': [encode(x) for x in sorted(value, key=repr)]}
        elif is_dataclass(value):
            node = {'type': 'object', 'class': _class_name(value),
                    'fields': {f.name: encode(getattr(value, f.name)) for f in fields(value)}}
        elif hasattr(value, '__dict__'):
            node = {'type': 'object', 'class': _class_name(value),
                    'fields': {k: encode(v) for k, v in vars(value).items()}}
        else:
            raise SaveIntegrityError(f'unsupported manager state: {type(value).__name__}')
        nodes[index] = node
        return {'$ref': index}

    return {'version': GRAPH_VERSION, 'root': encode(session.__dict__), 'nodes': nodes}


def restore_manager_graph(data: dict, *, migrate_world: bool = True) -> DevelopmentSession:
    """Load a snapshot using only known Python game classes, never pickle."""
    if not isinstance(data, dict):
        raise SaveIntegrityError('manager graph must be a JSON object')
    if type(data.get('version')) is not int or data['version'] not in (*range(1, GRAPH_VERSION+1),):
        raise UnsupportedSaveVersionError('unsupported manager graph version')
    nodes = data.get('nodes')
    if not isinstance(nodes, list) or len(nodes) > MAX_NODES:
        raise SaveIntegrityError('invalid manager graph node count')
    constructed: dict[int, Any] = {}
    resolving: set[int] = set()

    def decode(value):
        if value is None or type(value) in (str, bool, int):
            return value
        if type(value) is float and isfinite(value):
            return value
        if not isinstance(value, dict) or set(value) != {'$ref'} or type(value['$ref']) is not int:
            raise SaveIntegrityError('invalid manager graph reference')
        idx = value['$ref']
        if idx < 0 or idx >= len(nodes):
            raise SaveIntegrityError('dangling manager graph reference')
        if idx in constructed:
            return constructed[idx]
        if idx in resolving:
            # This can only happen for an unsupported tuple/enum cycle. Dicts,
            # lists and objects register their placeholders before decoding.
            raise SaveIntegrityError('unsupported immutable reference cycle')
        resolving.add(idx)
        try:
            node = nodes[idx]
            if not isinstance(node, dict):
                raise SaveIntegrityError('invalid manager graph node')
            kind = node.get('type')
            if kind == 'archived_world':
                if data['version'] not in range(2, GRAPH_VERSION+1) or not isinstance(node.get('data'), str):
                    raise SaveIntegrityError('invalid archived season state')
                try:
                    packed = base64.b64decode(node['data'], validate=True)
                    if len(packed) > MAX_ARCHIVED_WORLD_BYTES:
                        raise SaveIntegrityError('oversized compressed season archive')
                    decompressor = zlib.decompressobj()
                    raw = decompressor.decompress(packed, MAX_ARCHIVED_WORLD_BYTES + 1)
                    if (len(raw) > MAX_ARCHIVED_WORLD_BYTES or not decompressor.eof
                            or decompressor.unused_data or decompressor.unconsumed_tail):
                        raise SaveIntegrityError('invalid archived season payload')
                    item = WorldSeasonRunner.from_dict(json.loads(raw.decode('utf-8')))
                except (ValueError, TypeError, UnicodeError, zlib.error) as exc:
                    if isinstance(exc, SaveIntegrityError):
                        raise
                    raise SaveIntegrityError('corrupt archived season payload') from exc
                constructed[idx] = item
            elif kind == 'dict':
                item = {}
                constructed[idx] = item
                for pair in node['items']:
                    if not isinstance(pair, list) or len(pair) != 2:
                        raise SaveIntegrityError('invalid dictionary entry')
                    key, val = decode(pair[0]), decode(pair[1])
                    if key in item:
                        raise SaveIntegrityError('duplicate key in saved dictionary')
                    item[key] = val
            elif kind == 'list':
                item = []
                constructed[idx] = item
                item.extend(decode(x) for x in node['items'])
            elif kind in ('tuple', 'set', 'frozenset'):
                values = [decode(x) for x in node['items']]
                item = tuple(values) if kind == 'tuple' else (set(values) if kind == 'set' else frozenset(values))
                constructed[idx] = item
            elif kind == 'date':
                item = date.fromisoformat(node['value'])
                constructed[idx] = item
            elif kind == 'datetime':
                item = datetime.fromisoformat(node['value'])
                constructed[idx] = item
            elif kind == 'enum':
                cls = _trusted_type(node.get('class'))
                if not issubclass(cls, Enum):
                    raise SaveIntegrityError('saved enum class is invalid')
                item = cls[node['value']]
                constructed[idx] = item
            elif kind == 'object':
                cls = _trusted_type(node.get('class'))
                if issubclass(cls, Enum) or cls is DevelopmentSession:
                    raise SaveIntegrityError('invalid saved state object')
                values = node.get('fields')
                if not isinstance(values, dict):
                    raise SaveIntegrityError('invalid saved object fields')
                if is_dataclass(cls):
                    allowed = {f.name for f in fields(cls)}
                    # TS-19 migrations are explicit and class/field-specific.
                    # Never silently supply defaults for arbitrary damaged saves.
                    legacy_defaults = {
                        'football_manager.domain.tactics:Tactic': {'phase_shapes': ()},
                        'football_manager.fast_simulation.models:FastMatchResult': {
                            'tactical_events': (), 'role_segments': (),
                        },
                    }
                    missing = allowed - set(values)
                    defaults = dict(legacy_defaults.get(node.get('class'), {})) if data['version'] < 3 else {}
                    if data['version'] < 4:
                        defaults.update({
                            'football_manager.domain.player:Player': {'personality': None},
                            'football_manager.domain.player_state:PlayerState': {'dressing_room_morale': 0.0},
                        }.get(node.get('class'), {}))
                    if data['version'] < 6 and node.get('class') == 'football_manager.domain.football_world:FootballWorld':
                        from football_manager.domain.season_statistics import SeasonStatisticsLedger
                        defaults.update(statistics=SeasonStatisticsLedger(), balance_adjustments={})
                    if data['version'] < 7:
                        if node.get('class') == 'football_manager.domain.player:Player':
                            defaults.update(development=None)
                        if node.get('class') == 'football_manager.domain.football_world:FootballWorld':
                            defaults.update(development_next_review=None, development_environments={})
                    if data['version'] < 8:
                        if node.get('class') == 'football_manager.domain.player:Player':
                            defaults.update(aging=None)
                        if node.get('class') == 'football_manager.domain.football_world:FootballWorld':
                            defaults.update(retired_players={}, medical_followups={})
                    if data['version'] < 10 and node.get('class') == 'football_manager.domain.football_world:FootballWorld':
                        defaults.update(youth=None)
                    if data['version'] < 11:
                        if node.get('class') == 'football_manager.domain.youth_academy:YouthSystem':
                            defaults.update(recruitment_funds=500_000,recruitment_spent=0,
                                last_scout_payroll=None,lost_prospects={})
                        if node.get('class') == 'football_manager.domain.youth_academy:YouthScout':
                            defaults.update(name='',hired_on=None,contract_until=None,
                                signing_fee=0,monthly_wage=0)
                    if data['version'] < 12 and node.get('class') == 'football_manager.domain.football_world:FootballWorld':
                        defaults.update(market_review_on=None, market_values={})
                    if data['version'] < 13 and node.get('class') == 'football_manager.domain.football_world:FootballWorld':
                        defaults.update(finance_review_on=None,finance_started_on=None,contracts={},club_finances={})
                    if data['version'] < 14 and node.get('class') == 'football_manager.domain.football_world:FootballWorld':
                        defaults.update(transfer_last_review_on=None,transfer_next_id=1,transfer_offers={})
                    if data['version'] < 15 and node.get('class') == 'football_manager.domain.transfer_negotiation:TransferNegotiation':
                        defaults.update(personal_status='not_started',personal_terms=None,
                            personal_events=(),personal_refusals=0,sell_on_paid_gbp=0,
                            bonus_baseline=(0,0,0),bonus_paid=(),buyer_tier_at_signing=0)
                    if data['version'] < 16 and node.get('class') == 'football_manager.domain.football_world:FootballWorld':
                        defaults.update(loan_next_id=1,loans={},free_agents={})
                    if data['version'] < 18 and node.get('class') == 'football_manager.domain.football_world:FootballWorld':
                        defaults.update(club_support={})
                    if data['version'] < 21 and node.get('class') == 'football_manager.domain.football_world:FootballWorld':
                        defaults.update(player_season_clubs={}, player_honours={})
                    if data['version'] < 22 and node.get('class') == 'football_manager.domain.football_world:FootballWorld':
                        defaults.update(rating_history={}, individual_awards={})
                    if data['version'] < 19 and node.get('class') == 'football_manager.domain.club_support:ClubSupport':
                        defaults.update(scouting_assignments={}, scouting_reports={})
                    if node.get('class') == 'football_manager.domain.club_support:TrainingPolicy':
                        if data['version'] < 24:
                            # TS-UI-03.03 intentionally retires group-by-XI and
                            # physical protection fields. Old settings must NOT
                            # influence current workouts or survive new saves.
                            for retired in ('starters', 'bench', 'rest', 'protection',
                                            'low_condition', 'medium_condition'):
                                values.pop(retired, None)
                            missing = allowed - set(values)
                        if data['version'] < 23:
                            defaults.update(performance_max=50, performance_focus=60,
                                energy_max=50, energy_focus=60, individual_intensities={})
                    if set(values) - allowed or missing - set(defaults):
                        raise SaveIntegrityError('saved dataclass fields do not match this version')
                elif cls.__name__ not in {'WorldSeasonRunner', 'WorldCareer', 'SeasonCalendar', 'EnglishCareerTransition', 'FastMatchSimulator'}:
                    raise SaveIntegrityError('saved mutable object class is not permitted')
                item = object.__new__(cls)
                constructed[idx] = item
                for name, val in values.items():
                    if not isinstance(name, str) or not name.isidentifier():
                        raise SaveIntegrityError('invalid saved object field')
                    object.__setattr__(item, name, decode(val))
                if is_dataclass(cls):
                    for name in missing:
                        object.__setattr__(item, name, defaults[name])
                    if data['version'] < 4 and node.get('class') == 'football_manager.domain.player:Player' and item.personality is None:
                        from football_manager.domain.personality import personality_for
                        item.personality = personality_for(item.id)
            else:
                raise SaveIntegrityError('invalid manager graph node kind')
            return constructed[idx]
        except (KeyError, TypeError, ValueError, IndexError, AttributeError) as exc:
            if isinstance(exc, SaveIntegrityError):
                raise
            raise SaveIntegrityError('invalid manager graph contents') from exc
        finally:
            resolving.discard(idx)

    root = decode(data.get('root'))
    if not isinstance(root, dict):
        raise SaveIntegrityError('manager graph root must be a dictionary')
    session = object.__new__(DevelopmentSession)
    session.__dict__.update(root)
    if data['version'] < 3 and 'tactical_studio' not in root:
        from football_manager.domain.tactical_studio import TacticalStudioState
        session.tactical_studio = TacticalStudioState()
    if data['version'] < 4 and 'dressing_room' not in root:
        from football_manager.services.dressing_room import create_dressing_room
        session.dressing_room = create_dressing_room(session.home_club.id, session.home_club.squad.players, session.current_date)
    if data['version'] < 5:
        for world in session._career.worlds:
            world.football_world = None
        if migrate_world:
            from football_manager.services.world_squads import install_football_world
            install_football_world(session, migration=True)
    if data['version'] < 6 and hasattr(session, '_world_squads'):
        from football_manager.services.season_statistics import migrate_statistics
        migrate_statistics(session)
    if data['version'] < 7 and hasattr(session, '_world_squads'):
        from football_manager.services.player_development import initialize_world_development
        initialize_world_development(session._world_squads, session.current_date)
    if data['version'] < 8 and hasattr(session, '_world_squads'):
        from football_manager.services.player_aging import initialize_world_aging
        initialize_world_aging(session._world_squads, session.current_date)
    if data['version'] < 9 and hasattr(session, '_world_squads'):
        # Only upgrade the explicitly provisional neutral environments. This
        # never re-rolls a player, backdates growth or changes a current skill.
        from football_manager.services.world_training import initialize_club_training
        initialize_club_training(session._world_squads, upgrade_neutral=True)
    if data['version'] < 10 and hasattr(session, '_world_squads'):
        from football_manager.services.youth_academy import initialize_youth
        initialize_youth(session._world_squads, session.current_date, session.home_club.id)
    if data['version'] < 11 and hasattr(session,'_world_squads') and session._world_squads.youth:
        youth=session._world_squads.youth
        if youth.last_scout_payroll is None:
            youth.last_scout_payroll=session.current_date.replace(day=1)
    if data['version'] < 12 and hasattr(session, '_world_squads'):
        from football_manager.services.market_valuation import initialize_market
        initialize_market(session._world_squads, session.current_date)
    if data['version'] < 13 and hasattr(session, '_world_squads'):
        from football_manager.services.club_economy import initialize_finances
        initialize_finances(session._world_squads, session.current_date)
    if data['version'] < 14 and hasattr(session, '_world_squads'):
        from football_manager.services.transfer_negotiation import initialize_transfer_market
        initialize_transfer_market(session._world_squads, session.current_date)
    if data['version'] < 17 and 'manager_inbox' not in root:
        from football_manager.services.manager_inbox import create_manager_inbox
        session.manager_inbox = create_manager_inbox(session)
    if data['version'] < 18 and hasattr(session, '_world_squads'):
        from football_manager.services.club_support import initialize_club_support
        initialize_club_support(session._world_squads, session.current_date)
    if data['version'] < 19 and hasattr(session, '_world_squads'):
        from football_manager.services.club_support import upgrade_club_support_scouts
        upgrade_club_support_scouts(session._world_squads, session.current_date)
    if data['version'] < 20 and 'set_piece_orders' not in root:
        from football_manager.services.match_preparation import empty_orders
        session.set_piece_orders = empty_orders()
    if data['version'] < 22 and hasattr(session, '_world_squads'):
        from football_manager.services.career_recognition import record_rating_snapshots
        record_rating_snapshots(session._world_squads, session.current_date)
    return session
