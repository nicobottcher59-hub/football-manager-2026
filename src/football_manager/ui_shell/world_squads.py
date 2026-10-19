"""Read-only professional-club squads inside the existing competition explorer."""
from __future__ import annotations

from dataclasses import fields
from enum import Enum

from football_manager.domain.player_ratings import CurrentRatingContext
from football_manager.domain.roles import roles_for_position
from football_manager.domain.tactical_catalogue import formation_board_layouts, formation_slot_label
from football_manager.domain.football_world import PlayerSeasonUsage
from football_manager.domain.enums import Position
from football_manager.domain.season_cycle import TIER_IDS
from football_manager.services.world_squads import coverage_report, select_lineup


def world_squads_index(session) -> dict:
    registry = session._world_squads
    leagues = []
    for tier, cid in enumerate(TIER_IDS, 1):
        edition = session._world.leagues[cid]
        clubs = []
        for club_id in sorted(edition.participant_club_ids, key=lambda x: registry.clubs[x].name):
            club, identity = registry.clubs[club_id], registry.identities[club_id]
            tactic = session.home_tactic if club_id == session.home_club.id else identity.primary
            clubs.append({'id': club_id, 'name': club.name, 'count': len(club.squad),
                          'formation': tactic.formation.name, 'style': tactic.analyze_style().label})
        leagues.append({'id': cid, 'name': edition.competition.name.replace(' (development)', ''),
                        'tier': tier, 'clubs': clubs})
    return {'schema_version': 1, 'source': 'persistent-english-world',
            'season': registry.season_label, 'date': session.current_date.isoformat(),
            'player_count': sum(len(registry.clubs[cid].squad) for l in leagues for cid in [c['id'] for c in l['clubs']]),
            'club_count': sum(len(l['clubs']) for l in leagues),
            'retained_external_clubs': sum(i.tier == 0 for i in registry.identities.values()), 'leagues': leagues}


def _slot_label(tactic, slot) -> str:
    label = formation_slot_label(tactic.formation.formation_id, slot.slot_id, slot.position.value)
    coords = formation_board_layouts().get(tactic.formation.formation_id, {})
    y = coords.get(slot.slot_id, (.5, .3))[1]
    if y >= .4 and slot.position in (Position.RW, Position.LW):
        label = 'RM' if slot.position is Position.RW else 'LM'
    return label


def _instructions(tactic) -> list[dict]:
    groups = []
    for group_field in fields(tactic.team_instructions):
        group = getattr(tactic.team_instructions, group_field.name)
        rows = []
        for f in fields(group):
            value = getattr(group, f.name)
            if isinstance(value, Enum):
                value = value.name.replace('_', ' ').title()
            elif isinstance(value, bool):
                value = 'Yes' if value else 'No'
            rows.append({'name': f.name.replace('_', ' ').title(), 'value': str(value)})
        groups.append({'name': group_field.name.replace('_', ' ').title(), 'rows': rows})
    return groups


def _tactic(tactic) -> dict:
    style = tactic.analyze_style()
    return {'id': tactic.tactic_id, 'name': tactic.name, 'formation': tactic.formation.name,
            'preset': tactic.preset_origin.value, 'style': style.label,
            'metrics': {k: round(getattr(style, k), 1) for k in
                        ('possession', 'pressing', 'directness', 'defensive_depth', 'tempo', 'width', 'risk')},
            'slots': [{'id': s.slot_id, 'position': _slot_label(tactic, s),
                       'role': tactic.role_for_slot(s.slot_id).name,
                       'role_id': tactic.role_for_slot(s.slot_id).role_id}
                      for s in tactic.formation.slots],
            'instructions': _instructions(tactic)}


def club_squad_read_model(session, club_id: str) -> dict:
    registry = session._world_squads
    if club_id not in registry.clubs:
        raise KeyError(club_id)
    club, identity = registry.clubs[club_id], registry.identities[club_id]
    managed = club_id == session.home_club.id
    tactic = session.home_tactic if managed else identity.primary
    warning = None
    try:
        lineup = session.home_lineup if managed else select_lineup(club, tactic, current=False)
        starters = {e.player.id: e for e in lineup.starters}
    except ValueError:
        starters = {}
        warning = 'Not enough available players to select a complete XI.'
    from football_manager.services.market_valuation import player_market_view
    from football_manager.services.club_economy import contract_view
    rows = []
    for player in club.squad.players:
        entry = starters.get(player.id)
        if entry:
            slot = tactic.formation.slot(entry.slot_id)
            position, label, role = slot.position, _slot_label(tactic, slot), tactic.role_for_slot(entry.slot_id)
        else:
            position = player.primary_position
            role = max(roles_for_position(position),
                       key=lambda r: (player.tactical_familiarity.role_score(r.role_id),
                                      player.overall_rating_for(position, r.role_id)))
            label = position.value
            # The label is about this player's intended job, not a new engine position.
            compatible = [s for s in tactic.formation.slots if s.position is position]
            if compatible:
                label = _slot_label(tactic, compatible[0])
        rating = player.current_rating(CurrentRatingContext(
            assigned_position=position, role_id=role.role_id, tactic_id=tactic.tactic_id))
        usage = registry.usage.get(player.id, PlayerSeasonUsage())
        rows.append({'id': player.id, 'name': player.full_name, 'age': player.age_on(session.current_date),
                     'position': label, 'natural_position': player.primary_position.value,
                     'secondary_positions': [p.value for p in player.secondary_positions],
                     'role': role.name, 'role_id': role.role_id, 'starter': bool(entry),
                     'ovr': rating.overall, 'act': rating.current,
                     'available': player.state.is_available, 'condition': player.state.condition,
                     'condition_as_of': (session.current_date if managed else registry.last_recovery[club_id]).isoformat(),
                     'appearances': usage.appearances, 'minutes': usage.minutes,
                     'goals': usage.goals, 'assists': usage.assists,
                     **player_market_view(registry, player, session.current_date),
                     'contract_details': contract_view(registry,player.id,session.current_date),
                     'attributes': {g: {f.name: getattr(getattr(player.attributes, g), f.name)
                                        for f in fields(getattr(player.attributes, g))}
                                    for g in ('technical', 'mental', 'physical', 'goalkeeping')
                                    if getattr(player.attributes, g) is not None}})
    rows.sort(key=lambda r: (not r['starter'], r['natural_position'] != 'GK', r['position'], r['name']))
    primary_ovr = [r['ovr'] for r in rows if r['starter']]
    from football_manager.services.ai_squad_planning import squad_plan
    planning = squad_plan(club,tactic)
    return {'schema_version': 1, 'source': identity.source,
            'squad_planning': {k:planning[k] for k in ('formation','target_size','squad_size','starters_covered','backups_covered','third_keeper_covered','vacancies','natural_position_counts')},
            'club_id': club_id, 'name': club.name, 'managed': managed,
            'tier': identity.tier, 'season': registry.season_label,
            'date': session.current_date.isoformat(), 'count': len(rows),
            'tracked_from': registry.tracked_from.isoformat() if registry.tracked_from else None,
            'initial_size': 22, 'players': rows,
            'primary': _tactic(tactic), 'alternative': _tactic(identity.alternative),
            'mean_xi_ovr': round(sum(primary_ovr) / len(primary_ovr), 1) if primary_ovr else None,
            'coverage': coverage_report(club, tactic), 'warning': warning,
            'development_enabled': False}
