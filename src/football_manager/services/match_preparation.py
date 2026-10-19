"""TS-27: optional opponent preview and persistent, validated set-piece orders.

Orders are club preferences, not a second tactic. An absent/unavailable starter
is automatically replaced by the best eligible player on the pitch.
"""
from __future__ import annotations

from football_manager.domain.enums import Position

ROLES = ('captain', 'penalties', 'free_kicks', 'corners_left', 'corners_right')
MAX_ORDER = 3


def role_score(player, role: str) -> float:
    a = player.attributes
    if role == 'penalties':
        return .60 * a.technical.penalties + .25 * a.mental.composure + .15 * a.technical.finishing
    if role == 'free_kicks':
        return .68 * a.technical.set_pieces + .18 * a.technical.technique + .14 * a.mental.composure
    if role.startswith('corners_'):
        return .55 * a.technical.crossing + .35 * a.technical.set_pieces + .10 * a.technical.passing
    if role == 'captain':
        return (.40 * a.mental.teamwork + .30 * a.mental.decisions
                + .20 * a.mental.composure + .10 * a.mental.concentration)
    raise ValueError('unknown set-piece role')


def validate_orders(session) -> None:
    orders = getattr(session, 'set_piece_orders', None)
    if not isinstance(orders, dict) or set(orders) != set(ROLES):
        raise ValueError('invalid set-piece preferences')
    # Stale IDs may remain after a legitimate transfer: ignore on matchday.
    # New preferences are always limited to the current roster by assign_order.
    for role, values in orders.items():
        if (not isinstance(values, tuple) or len(values) != MAX_ORDER
                or any(type(x) is not str or len(x) > 128 for x in values)
                or len([x for x in values if x]) != len({x for x in values if x})):
            raise ValueError(f'invalid set-piece order for {role}')


def empty_orders() -> dict[str, tuple[str, ...]]:
    return {role: ('',) * MAX_ORDER for role in ROLES}


def assign_order(session, command: dict) -> None:
    role = command.get('role')
    rank = command.get('rank', 0)
    player_id = command.get('player_id')
    if role not in ROLES or type(rank) is not int or not 0 <= rank < MAX_ORDER:
        raise ValueError('invalid set-piece assignment')
    if type(player_id) is not str or (player_id and not session.home_club.squad.contains(player_id)):
        raise ValueError('unknown set-piece player')
    values = list(session.set_piece_orders[role])
    values[rank] = player_id
    if player_id:
        # A player cannot hold two positions in the SAME priority list.
        for i in range(MAX_ORDER):
            if i != rank and values[i] == player_id:
                values[i] = ''
    session.set_piece_orders[role] = tuple(values)
    validate_orders(session)


def effective_order(orders: dict, role: str, players: tuple) -> tuple:
    """Only current on-field players; never choose a bench/injured player."""
    if not players:
        return ()
    # Any starter can be named explicitly, including a goalkeeper captain or
    # an unusual goalkeeper penalty taker. Defaults still favour outfielders.
    preferred_ids = orders.get(role, ())
    by_id = {p.player_id: p for p in players}
    preferred = [by_id[id_] for id_ in preferred_ids if id_ in by_id]
    seen = {p.player_id for p in preferred}
    outfield = [p for p in players if p.assigned_position is not Position.GK and p.player_id not in seen]
    keepers = [p for p in players if p.assigned_position is Position.GK and p.player_id not in seen]
    key = lambda p: (-role_score(p, role), p.player_id)
    return (*preferred, *sorted(outfield, key=key), *sorted(keepers, key=key))


def _row_order(players: tuple, role: str, preferences: dict) -> dict:
    ordered = effective_order(preferences, role, players)
    chosen = ordered[0] if ordered else None
    return {
        'role': role,
        'orders': list(preferences[role]),
        'effective_id': chosen.player_id if chosen else None,
        'effective_name': chosen.full_name if chosen else None,
        'fallback': bool(chosen and chosen.player_id not in preferences[role]),
    }


def set_piece_view(session) -> dict:
    lineup = session.home_lineup
    # No extra team-quality calculation. Purely for player selection in the read model.
    class Candidate:
        def __init__(self, player, position):
            self.player_id = player.id
            self.full_name = player.full_name
            self.assigned_position = position
            self.attributes = player.attributes
    on_field = tuple(Candidate(e.player, lineup.formation.slot(e.slot_id).position) for e in lineup.starters)
    return {
        'supported': True,
        'roles': [_row_order(on_field, role, session.set_piece_orders) for role in ROLES],
        'players': ([{'id': p.id, 'name': p.full_name} for p in session.home_club.squad.players]
                    + [{'id': pid, 'name': 'Unavailable - former player'}
                       for pid in sorted({pid for values in session.set_piece_orders.values() for pid in values if pid}
                                         - {p.id for p in session.home_club.squad.players})]),
        'note': 'Orders persist. If the preferred player is absent, an eligible starter takes over automatically.',
    }


def opponent_report(session) -> dict:
    """Read actual opponent lineups, tactics and *recorded* results, never a fabricated weakness."""
    if session._active_match is None or session.match_played:
        return {'available': False, 'message': 'No upcoming managed fixture to analyse.'}
    club, lineup, tactic = session.away_club, session.away_lineup, session.away_tactic
    style = tactic.analyze_style()
    on_field = [e.player for e in lineup.starters]
    key_players = sorted(on_field, key=lambda p: (-p.overall_rating, p.id))[:3]
    metrics = {
        'pressing': round(style.pressing),
        'directness': round(style.directness),
        'possession': round(style.possession),
        'defensive_depth': round(style.defensive_depth),
    }
    tendencies = []
    if style.pressing >= 66:
        tendencies.append('Often applies high pressure; direct passes can bypass some pressing situations.')
    if style.possession >= 65:
        tendencies.append('Looks to control possession and build attacks patiently.')
    if style.directness >= 67:
        tendencies.append('Frequently moves the ball forward quickly and directly.')
    if style.defensive_depth < 42:
        tendencies.append('Usually sits deeper, leaving fewer spaces close to its goal.')
    if not tendencies:
        tendencies.append('No extreme tactical tendency stands out in its current setup.')
    world = session._world
    recent = []
    for fixture_id, record in world.results.items():
        fixture = world.fixtures.get(fixture_id)
        if not fixture or club.id not in (fixture.home_club_id, fixture.away_club_id):
            continue
        if fixture.match_date is None or fixture.match_date > session.current_date:
            continue
        recent.append((fixture.match_date, fixture_id, {
            'date': fixture.match_date.isoformat(),
            'opponent': session._world_club_names.get(
                fixture.away_club_id if fixture.home_club_id == club.id else fixture.home_club_id,
                fixture.away_club_id if fixture.home_club_id == club.id else fixture.home_club_id,
            ),
            'goals_for': record.home_goals if fixture.home_club_id == club.id else record.away_goals,
            'goals_against': record.away_goals if fixture.home_club_id == club.id else record.home_goals,
        }))
    recent.sort(key=lambda item: (item[0], item[1]), reverse=True)
    return {
        'available': True, 'opponent': club.name, 'formation': tactic.formation.name,
        'style': style.label, 'metrics': metrics, 'tendencies': tendencies,
        'key_players': [{'name': p.full_name, 'position': p.primary_position.value,
                         'ovr': round(p.overall_rating, 1)} for p in key_players],
        'recent': [row for _, _, row in recent[:5]],
        'disclaimer': 'Projected lineup from current squad selection; tactical tendencies are estimates, not a guaranteed counter.'
    }
