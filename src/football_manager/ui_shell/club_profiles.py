"""One read-only Squad surface for any registered club. Never generate on GET."""
from __future__ import annotations
from dataclasses import asdict
from football_manager.services.season_statistics import player_statistics, statistics_options
from .world_squads import club_squad_read_model


def club_profile_read_model(session, club_id, *, season=None, competition=None):
    registry = session._world_squads
    world = session._world
    if club_id not in registry.clubs:
        if club_id not in session._world_club_names:
            raise KeyError('Unknown club')
        return {'club_id': club_id, 'club': session._world_club_names[club_id], 'readonly': True,
                'available': False, 'message': 'This club has no persistent squad in the current data pack.',
                'roster': [], 'date': session.current_date.isoformat()}
    original = club_squad_read_model(session, club_id)
    club = registry.clubs[club_id]
    roster = []
    for row in original['players']:
        p = club.squad.get(row['id'])
        fam = p.positional_familiarity
        positions = {p.primary_position, *p.secondary_positions, *fam.values}
        roster.append({**row, 'primary_position': p.primary_position.value,
                       'short_name': p.identity.last_name, 'base_ovr': round(p.overall_rating, 1),
                       'nationality': p.identity.nationality, 'foot': p.identity.dominant_foot.value,
                       'birth_date': p.identity.birth_date.isoformat(),
                       'condition': round(p.state.condition, 1), 'fatigue': round(p.state.fatigue, 1),
                       'morale': round(p.state.effective_morale, 1), 'form': p.state.form,
                       'sharpness': p.state.match_sharpness, 'injury': p.state.injury,
                       'suspension': p.state.suspended_matches, 'number': None,
                       'contract': (row['contract_details']['weekly_wage']+'/w · '+row['contract_details']['expires_on']
                                    if row.get('contract_details') else None), 'happiness': None,
                       'transfer_status': 'normal',
                       'familiarities': [{'position': pos.value, 'effective': round(fam.effective_score(pos), 1),
                                          'stored': fam.values.get(pos), 'peak': fam.peak_values.get(pos),
                                          'minutes': fam.minutes_for(pos), 'is_primary': pos == p.primary_position,
                                          'is_secondary': pos in p.secondary_positions}
                                         for pos in sorted(positions, key=lambda v: (v != p.primary_position, v.value))],
                       'season_stats': player_statistics(registry, p.id, season=season, competition=competition)})
    league = None
    for cid, edition in world.leagues.items():
        if club_id in edition.participant_club_ids:
            standings = world.standings(cid)
            row = next((r for r in standings if r.club_id == club_id), None)
            league = {'id': cid, 'name': edition.competition.name.replace(' (development)', ''),
                      'position': row.position if row else None, 'points': row.points if row else None}
            break
    # Results are canonical scores. A club profile does not simulate or recover.
    recent = []
    for fid, result in world.results.items():
        fixture = world.fixtures[fid]
        if club_id not in (fixture.home_club_id, fixture.away_club_id):
            continue
        recent.append({'id': fid, 'date': fixture.match_date.isoformat() if fixture.match_date else None,
                       'competition_id': fixture.competition_id,
                       'home_id': fixture.home_club_id, 'away_id': fixture.away_club_id,
                       'home': session._world_club_names.get(fixture.home_club_id, fixture.home_club_id),
                       'away': session._world_club_names.get(fixture.away_club_id, fixture.away_club_id),
                       'home_goals': result.home_goals, 'away_goals': result.away_goals})
    recent.sort(key=lambda r: (r['date'] or '', r['id']), reverse=True)
    return {'available': True, 'readonly': True, 'club_id': club_id, 'club': club.name,
            'date': session.current_date.isoformat(), 'persistent': True, 'roster': roster,
            'stats_selection': {'season': season or registry.season_label, 'competition': competition or 'all'},
            'statistics': statistics_options(registry, world),
            'information': {'country': club.country, 'city': getattr(club, 'city', None),
                            'stadium': getattr(club, 'stadium', None), 'capacity': getattr(club, 'capacity', None),
                            'league': league, 'recent_results': recent[:5],
                            'condition_as_of': (session.current_date if club_id == session.home_club.id else registry.last_recovery[club_id]).isoformat()},
            'primary': original['primary'], 'alternative': original['alternative'],
            'warning': original['warning'],
            'retired_players': [{'id': e.player.id, 'name': e.player.full_name, 'retired_on': e.retired_on.isoformat()}
                                for e in registry.retired_players.values() if e.club_id == club_id]}
