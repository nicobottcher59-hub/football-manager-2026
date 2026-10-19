"""TS-28.2: read-only career history built solely from saved, verified ledgers.

Previous editions are retained by WorldCareer. Player statistics, registration
on matchdays, transfers, honours and retirements are joined by stable IDs; a
missing historical link is labelled unknown rather than inferred.
"""
from __future__ import annotations

from football_manager.services.season_statistics import player_statistics
from football_manager.services.career_recognition import AWARD_LABELS, INDICATOR_LABELS, indicators_for
from football_manager.domain.season_statistics import SeasonPlayerStatistics


def _name(session, club_id):
    return session._world_club_names.get(club_id, club_id)


def _competition_name(world, cid):
    entry = world.leagues.get(cid) or world.cups.get(cid) or world.staged.get(cid)
    value = getattr(entry, 'name', None) or getattr(getattr(entry, 'competition', None), 'name', None)
    return (value or cid.replace('-', ' ').title()).replace(' (development)', '').replace(' (fictional clubs)', '')


def _player(session, pid):
    reg = session._world_squads
    for cid, club in reg.clubs.items():
        if club.squad.contains(pid):
            return club.squad.get(pid), cid, 'active'
    retired = reg.retired_players.get(pid)
    if retired:
        return retired.player, retired.club_id, 'retired'
    free = reg.free_agents.get(pid)
    if free:
        return free.player, None, 'free_agent'
    raise KeyError('Player is not in the career archive')


def _completed_deals(registry, *, player_id=None, club_id=None):
    rows = []
    for deal in registry.transfer_offers.values():
        if deal.status != 'completed' or deal.personal_status != 'completed':
            continue
        if player_id is not None and deal.player_id != player_id:
            continue
        if club_id is not None and club_id not in (deal.seller_id, deal.buyer_id):
            continue
        # The acceptance date is recorded; exact registration day isn't.
        accepted = deal.personal_events[-1].on_date if deal.personal_events else None
        rows.append({'id': deal.deal_id, 'player_id': deal.player_id,
                     'from_id': deal.seller_id, 'to_id': deal.buyer_id,
                     'fee_gbp': deal.terms.fixed_gbp,
                     'date': accepted.isoformat() if accepted else None,
                     'date_note': 'Player agreement date (exact registration date not stored)'})
    return sorted(rows, key=lambda row: (row['date'] or '', row['id']), reverse=True)


def _loans(registry, *, player_id=None, club_id=None):
    items = []
    for loan in registry.loans.values():
        if player_id is not None and loan.player_id != player_id:
            continue
        if club_id is not None and club_id not in (loan.parent_id, loan.borrower_id):
            continue
        items.append({'id': loan.loan_id, 'player_id': loan.player_id,
                      'from_id': loan.parent_id, 'to_id': loan.borrower_id,
                      'date': loan.started_on.isoformat(), 'ends_on': loan.ends_on.isoformat(),
                      'status': loan.status, 'kind': 'loan'})
    return sorted(items, key=lambda row: (row['date'], row['id']), reverse=True)


def _fixture_rows(session, world, club_id=None, competition_id=None, *, limit=80, offset=0):
    selected = []
    for fid, result in world.results.items():
        fixture = world.fixtures.get(fid)
        if fixture is None or fixture.kickoff is None or fixture.kickoff.date() > session.current_date:
            continue
        if club_id is not None and club_id not in (fixture.home_club_id, fixture.away_club_id):
            continue
        if competition_id is not None and fixture.competition_id != competition_id:
            continue
        selected.append((fixture.kickoff, fid, fixture, result))
    selected.sort(key=lambda item: (item[0], item[1]), reverse=True)
    items = []
    for _, fid, fixture, result in selected[offset:offset+limit]:
        items.append({'id': fid, 'date': fixture.kickoff.date().isoformat(),
                      'competition_id': fixture.competition_id,
                      'competition': _competition_name(world, fixture.competition_id),
                      'home_id': fixture.home_club_id, 'away_id': fixture.away_club_id,
                      'home': _name(session, fixture.home_club_id),
                      'away': _name(session, fixture.away_club_id),
                      'home_goals': result.home_goals, 'away_goals': result.away_goals})
    return {'matches': items, 'total': len(selected), 'offset': offset,
            'next_offset': offset+limit if len(selected) > offset+limit else None}


def _award_view(session, award):
    try:
        player = _player(session, award.player_id)[0]
        name = player.full_name
    except KeyError:
        name = 'Player unavailable'
    return {'season': award.season, 'category': award.category,
            'label': AWARD_LABELS.get(award.category, award.category),
            'competition_id': award.competition_id,
            'competition': ('Simulated World' if award.competition_id == 'world'
                            else _competition_name(session._world, award.competition_id)),
            'player_id': award.player_id, 'player': name, 'club_id': award.club_id,
            'club': _name(session, award.club_id) if award.club_id else None}


def _all_awards(session):
    registry = session._world_squads
    return [_award_view(session, award)
            for season in sorted(registry.individual_awards, reverse=True)
            for award in registry.individual_awards[season]]


def _player_progression(registry, player, status, on_date):
    from football_manager.services.career_recognition import indicators_for
    points = [{'season': point.season, 'date': point.on_date.isoformat(),
               'overall': point.overall, 'indicators': dict(zip(INDICATOR_LABELS, point.indicators)), 'is_current': False}
              for point in registry.rating_history.get(player.id, ())]
    # The current point is an observation, not a fictitious historic checkpoint.
    if status != 'retired' and (not points or points[-1]['date'] < on_date.isoformat()):
        points.append({'season': registry.season_label, 'date': on_date.isoformat(),
                       'overall': round(player.overall_rating, 2),
                       'indicators': dict(indicators_for(player)), 'is_current': True})
    return points


def _records(session, *, club_id=None, competition_id=None):
    registry = session._world_squads
    aggregate = {}
    for season, competitions in registry.statistics.seasons.items():
        for cid, players in competitions.items():
            if competition_id and cid != competition_id:
                continue
            for pid, stat in players.items():
                if club_id is not None:
                    # The season ledger doesn't split a multi-club year into
                    # per-club rows. Such totals must not be assigned wholesale.
                    if registry.player_season_clubs.get(season, {}).get(pid) != (club_id,):
                        continue
                aggregate[pid] = aggregate.get(pid, SeasonPlayerStatistics()).plus(stat)
    categories = (('goals','goals'), ('assists','assists'), ('appearances','appearances'))
    result = {}
    for label, attr in categories:
        ordered = sorted(((pid, getattr(stat, attr)) for pid, stat in aggregate.items()
                          if getattr(stat, attr)), key=lambda item:(-item[1],item[0]))[:5]
        rows = []
        for pid, val in ordered:
            try: name = _player(session, pid)[0].full_name
            except KeyError: continue
            rows.append({'player_id':pid, 'player':name,'value':val})
        result[label] = rows
    return result


def _club_institution(session, club_id):
    reg = session._world_squads
    club = reg.clubs.get(club_id)
    if club is None:
        return {'registered': False, 'note': 'This visitor has no persistent club profile.'}
    ident = reg.identities.get(club_id)
    department = reg.club_support.get(club_id)
    finances = reg.club_finances.get(club_id)
    env = reg.development_environments.get(club_id)
    league = next((cid for cid, e in session._world.leagues.items()
                   if club_id in e.participant_club_ids), None)
    player_rows = sorted(club.squad.players, key=lambda p:(-p.overall_rating, p.id))[:7]
    staff = []
    if department:
        for role in ('coach','fitness','medic','scout'):
            members = [x for x in department.members.values()
                       if x.role == role and x.contract_until >= session.current_date]
            staff.append({'role':role, 'count':len(members), 'capacity':department.capacity[role],
                          'average_quality':round(sum(x.quality for x in members)/len(members),1) if members else None})
    return {'registered':True, 'country':club.country,
            'city':getattr(club,'city',None), 'stadium':getattr(club,'stadium',None),
            'stadium_capacity':getattr(club,'capacity',None),
            'founded':getattr(club,'founded',None),
            'current_tier':ident.tier if ident else None,
            'initial_tier':ident.initial_tier if ident else None,
            'playing_style':ident.style_key if ident else None,
            'league_id':league,
            'league':_competition_name(session._world,league) if league else None,
            'team_strength':session._world.strengths.get(club_id),
            'finance':({'cash_gbp':finances.cash_gbp,
                        'transfer_budget_gbp':finances.transfer_budget_gbp,
                        'wage_budget_weekly_gbp':finances.wage_budget_weekly_gbp}
                       if finances else None),
            'training_environment':({'quality':env.training_quality, 'coaching':env.coaching_quality,
                                     'source':env.source} if env else None),
            'facilities':({'source':department.capacity_source,
                           'staffing_slots':staff} if department else None),
            'top_players':[{'id':p.id,'name':p.full_name,'position':p.primary_position.value,
                            'overall':round(p.overall_rating,1)} for p in player_rows],
            'note': ('This data pack has no verified stadium, city or foundation dates for most fictional clubs. '
                     'Staffing capacities are provisional; facility construction is planned for TS-29. '
                     'Team strength is a simulator rating, not a historical reputation score.')}


def player_career_read_model(session, player_id):
    registry = session._world_squads
    player, current_club, status = _player(session, player_id)
    seasons = sorted(set(registry.history) | set(registry.statistics.seasons) |
                     set(registry.player_season_clubs) | {registry.season_label}, reverse=True)
    rows = []
    for season in seasons:
        played = registry.player_season_clubs.get(season, {}).get(player_id, ())
        seen = registry.history.get(season, {}).get(player_id)
        if season == registry.season_label:
            seen = registry.usage.get(player_id)
        detail = registry.statistics.seasons.get(season, {})
        if not played and seen is None and not any(player_id in players for players in detail.values()):
            if season != registry.season_label or status == 'retired':
                continue
        summary = player_statistics(registry, player_id, season=season)
        rows.append({'season': season, 'club_ids': list(played),
                     'clubs': [{'id': cid, 'name': _name(session, cid)} for cid in played],
                     'statistics': summary, 'coverage': summary['coverage']})
    deals = _completed_deals(registry, player_id=player_id)
    for row in deals:
        row['player_name'] = player.full_name
        row['from'] = _name(session, row['from_id'])
        row['to'] = _name(session, row['to_id'])
    loans = _loans(registry, player_id=player_id)
    for row in loans:
        row['from'] = _name(session, row['from_id'])
        row['to'] = _name(session, row['to_id'])
    honours = [{'season': season, 'competition_id': competition,
                'competition': _competition_name(session._world, competition),
                'club_id': club, 'club': _name(session, club)}
               for season, competition, club in registry.player_honours.get(player_id, ())]
    return {'source': 'verified-career-ledgers', 'type': 'player', 'id': player_id,
            'progression': _player_progression(registry, player, status, session.current_date),
            'awards': [x for x in _all_awards(session) if x['player_id'] == player_id],
            'name': player.full_name, 'status': status,
            'retired_on': (player.aging.retired_on.isoformat() if player.aging and player.aging.retired_on else None),
            'current_club_id': current_club, 'current_club': _name(session, current_club) if current_club else None,
            'birth_date': player.identity.birth_date.isoformat(),
            'nationality': player.identity.nationality,
            'position': player.primary_position.value,
            'seasons': rows, 'transfers': deals, 'loans': loans, 'honours': honours,
            'note': ('Club IDs in season statistics reflect recorded match participation starting TS-28.2. '
                     'Earlier seasons may have verified statistics without club attribution. '
                     'Honours are captured from the confirmed champion roster at season-end; '
                     'older untracked seasons are not backfilled.')}


def _reports(session):
    return list(session._career.reports)


def _club_seasons(session, club_id):
    rows = []
    for report in reversed(_reports(session)):
        league = next(((cid, table.index(club_id)+1)
                       for cid, table in report.league_tables.items() if club_id in table), None)
        titles = [{'id': cid, 'name': _competition_name(session._world, cid)}
                  for cid, champ in report.champions.items() if champ == club_id]
        if league or titles:
            rows.append({'season': report.season_label,
                         'league_id': league[0] if league else None,
                         'league': _competition_name(session._world, league[0]) if league else None,
                         'position': league[1] if league else None,
                         'promoted': [cid for cid, clubs in report.promoted.items() if club_id in clubs],
                         'relegated': [cid for cid, clubs in report.relegated.items() if club_id in clubs],
                         'titles': titles, 'complete': True})
    now = session._world
    league = next((cid for cid, edition in now.leagues.items() if club_id in edition.participant_club_ids), None)
    position = None
    if league:
        position = next((r.position for r in now.standings(league) if r.club_id == club_id), None)
    return ([{'season': now.season_label, 'league_id': league,
              'league': _competition_name(now, league) if league else None,
              'position': position, 'promoted': [], 'relegated': [],
              'titles': [], 'complete': False}] + rows)


def club_career_read_model(session, club_id, *, season=None, offset=0):
    if club_id not in session._world_club_names:
        raise KeyError('Unknown club')
    registry = session._world_squads
    rows = _club_seasons(session, club_id)
    selected = season or session._world.season_label
    if selected not in {s['season'] for s in rows}:
        raise KeyError('Club has no recorded season')
    worlds = {w.season_label: w for w in session._career.worlds}
    matches = _fixture_rows(session, worlds[selected], club_id=club_id, offset=offset) if selected in worlds else {'matches': [], 'total': 0, 'offset': offset, 'next_offset': None}
    titles = [{'season': s['season'], **t} for s in rows for t in s['titles']]
    retired = [{'id': r.player.id, 'name': r.player.full_name,
                'retired_on': r.retired_on.isoformat()} for r in registry.retired_players.values() if r.club_id == club_id]
    transfers = _completed_deals(registry, club_id=club_id)
    for row in transfers:
        row['from'] = _name(session, row['from_id'])
        row['to'] = _name(session, row['to_id'])
        try:
            row['player_name'] = _player(session, row['player_id'])[0].full_name
        except KeyError:
            row['player_name'] = 'Player (profile unavailable)'
    return {'source': 'verified-career-ledgers', 'type': 'club', 'id': club_id,
            'institution': _club_institution(session,club_id),
            'records': _records(session,club_id=club_id),
            'awards': [x for x in _all_awards(session) if x['club_id'] == club_id],
            'name': _name(session, club_id), 'season': selected, 'seasons': rows,
            'trophies': titles, 'transfers': transfers[:80], 'retired_players': retired[:80],
            'fixtures': matches,
            'has_active_squad': club_id in registry.clubs,
            'note': 'Finished league positions and trophies come from season reports. All displayed matches are completed fixtures; missing historical statistics are not estimated.'}


def competition_career_read_model(session, competition_id, *, season=None, offset=0):
    worlds = {w.season_label: w for w in session._career.worlds}
    reports = {report.season_label: report for report in _reports(session)}
    available = [label for label, world in worlds.items()
                 if competition_id in world.leagues or competition_id in world.cups or competition_id in world.staged]
    if not available:
        raise KeyError('Unknown competition')
    available.sort(reverse=True)
    chosen = season or (session._world.season_label if session._world.season_label in available else available[0])
    if chosen not in available:
        raise KeyError('Unknown competition season')
    world = worlds[chosen]
    report = reports.get(chosen)
    champion = report.champions.get(competition_id) if report else None
    if not champion:
        item = world.cups.get(competition_id) or world.staged.get(competition_id)
        champion = getattr(item, 'champion_club_id', None) if item else None
    rows = []
    if competition_id in world.leagues:
        if report and competition_id in report.league_tables:
            final = report.league_tables[competition_id]
            rows = [{'position': index, 'club_id': cid, 'club': _name(session, cid)}
                    for index, cid in enumerate(final, 1)]
        else:
            rows = [{'position': r.position, 'club_id': r.club_id, 'club': _name(session, r.club_id),
                     'points': r.points, 'played': r.played, 'gd': r.goal_difference}
                    for r in world.standings(competition_id)]
    champions = [{'season': label, 'club_id': reports[label].champions[competition_id],
                  'club': _name(session, reports[label].champions[competition_id])}
                 for label in available if label in reports and competition_id in reports[label].champions]
    return {'source': 'verified-career-ledgers', 'type': 'competition', 'id': competition_id,
            'records': _records(session,competition_id=competition_id),
            'awards': [x for x in _all_awards(session)
                       if x['competition_id'] == competition_id and x['season'] == chosen],
            'name': _competition_name(world, competition_id), 'season': chosen,
            'available_seasons': available, 'season_complete': chosen in reports,
            'champion_id': champion, 'champion': _name(session, champion) if champion else None,
            'champions': champions, 'table': rows,
            'fixtures': _fixture_rows(session, world, competition_id=competition_id, offset=offset),
            'note': 'Completed seasons and winners are read from the archived world and season report. Historical tables list confirmed final positions; no points are invented if missing.'}
