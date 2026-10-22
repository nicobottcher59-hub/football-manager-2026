"""Professional scouting, career calendar reports, worldwide discovery and shortlist.

The transfer engine owns bids; scouting owns discovery, observation capacity
and estimated knowledge. Higher-quality staff progress faster. The Hub masks
confidential statistics until a report, without altering actual player ratings.
"""
from __future__ import annotations

from dataclasses import fields
from datetime import date
from math import ceil

from football_manager.domain.club_support import ProfessionalScoutAssignment, ProfessionalScoutReport
from football_manager.services.club_support import active_staff


def _targets(registry, managed_club_id: str):
    """Use the exact same eligibility as the existing professional transfer search."""
    for cid in sorted(registry.clubs):
        if cid == managed_club_id:
            continue
        club = registry.clubs[cid]
        for player in club.squad.players:
            contract = registry.contracts.get(player.id)
            if contract is not None and contract.kind == 'professional':
                yield player.id, cid, player


def _target(session, player_id: str):
    for pid, cid, player in _targets(session._world_squads, session.home_club.id):
        if pid == player_id:
            return cid, player
    return None


def _slots(staff_member) -> int:
    return 2 if staff_member.quality >= 78 else 1


def _daily_points(staff_member) -> int:
    # Quality 48: 7 points/day (~15 days); quality 85: 15 (~7 days).
    return max(5, min(17, 5 + (staff_member.quality - 35) // 5))


def _rebalance(dept, today: date) -> dict[str, object]:
    """Keep projects when contracts end; reassign automatically when possible."""
    available = sorted(active_staff(dept, 'scout', today), key=lambda m: (-m.quality, m.member_id))
    free = {m.member_id: _slots(m) for m in available}
    for assignment in sorted(dept.scouting_assignments.values(), key=lambda a: (a.started_on, a.player_id)):
        member = next((m for m in available if free[m.member_id] > 0), None)
        assignment.scout_id = member.member_id if member is not None else 'unassigned'
        if member is not None:
            free[member.member_id] -= 1
    return {m.member_id: m for m in available}


def _evaluate(session, player_id: str, cid: str, player, scout_id: str, today: date):
    attrs = player.attributes
    groups = [attrs.goalkeeping] if player.primary_position.value == 'GK' and attrs.goalkeeping else [attrs.technical]
    groups.extend([attrs.mental, attrs.physical])
    pairs = [(f.name, getattr(group, f.name)) for group in groups if group for f in fields(group)]
    strengths = tuple(n.replace('_', ' ').capitalize() for n, _ in
                      sorted(pairs, key=lambda item: (-item[1], item[0]))[:3])
    rating = round(player.overall_rating, 1)
    first_team = [entry.player.overall_rating for entry in session.home_lineup.starters]
    benchmark = sum(first_team) / len(first_team) if first_team else 65
    age = player.age_on(today)
    delta = rating - benchmark
    if delta >= 5:
        verdict = 'Strong first-team option by current overall rating. Assess the price and positional need.'
    elif delta >= -2:
        verdict = 'Competitive with the current XI. Compare role, wages and transfer cost.'
    elif age <= 22:
        verdict = 'Development prospect, not a proven immediate upgrade. Compare age and current ability.'
    else:
        verdict = 'Potential squad depth. Current level is below the XI average; review the asking price.'
    from football_manager.services.transfer_negotiation import _quote
    value = _quote(session._world_squads, player).value_gbp
    return ProfessionalScoutReport(player_id, scout_id, today, player.full_name,
                                   session._world_squads.clubs[cid].name, player.primary_position.value,
                                   rating, age, value, strengths, verdict)


def scouting_read_model(session) -> dict:
    dept = session._world_squads.club_support[session.home_club.id]
    day = session.current_date
    employees = active_staff(dept, 'scout', day)
    by_id = {m.member_id: m for m in employees}
    total = sum(_slots(m) for m in employees)
    # GET endpoints must not mutate anything, even staff allocation.
    projects = []
    for assignment in sorted(dept.scouting_assignments.values(), key=lambda a: (a.started_on, a.player_id)):
        scout = by_id.get(assignment.scout_id)
        target = _target(session, assignment.player_id)
        name = target[1].full_name if target is not None else 'Player no longer available'
        remaining = ceil((100 - assignment.progress_points) / _daily_points(scout)) if scout else None
        projects.append({'player_id': assignment.player_id, 'name': name,
                         'scout': scout.name if scout else 'Awaiting available scout',
                         'progress': assignment.progress_points,
                         'days_left': remaining})
    reports = [{'player_id': r.player_id, 'name': r.player_name, 'club': r.club_name,
                'position': r.position, 'date': r.completed_on.isoformat(),
                'scout': by_id[r.scout_id].name if r.scout_id in by_id else 'Former staff',
                'ovr': r.overall, 'age': r.age, 'value_gbp': r.value_gbp,
                'strengths': list(r.strengths), 'verdict': r.verdict}
               for r in sorted(dept.scouting_reports.values(), key=lambda r: (r.completed_on, r.player_id), reverse=True)]
    return {'scout_count': len(employees), 'capacity': total, 'occupied': len(projects),
            'free_slots': max(0, total - len(projects)), 'assignments': projects,
            'reports': reports,
            'note': 'The Scouting Hub shows public details; estimated ability and value require completed observations. Reports do not modify transfer odds.'}


def scouting_command(session, command: dict) -> dict:
    dept = session._world_squads.club_support[session.home_club.id]
    today = session.current_date
    action, player_id = command.get('action'), command.get('player_id')
    if action == 'destination':
        scout_id, destination = command.get('scout_id'), command.get('destination')
        people = {m.member_id for m in active_staff(dept, 'scout', today)}
        if scout_id not in people or not isinstance(destination, str):
            raise ValueError('Choose an active club scout and destination')
        permitted = {'all'}
        for _, _, player, _, league in _available_search_players(session):
            permitted.add('country:' + player.identity.nationality)
            permitted.add('league:' + league)
        if destination not in permitted:
            raise ValueError('Destination is not a recognised country or league')
        dept.scouting_destinations[scout_id] = destination
        return {'assigned_destination': destination, 'scout_id': scout_id}
    if not isinstance(player_id, str) or not player_id or len(player_id) > 160:
        raise ValueError('Choose a valid player')
    if action in ('shortlist_add', 'shortlist_remove', 'shortlist_priority'):
        if _target(session, player_id) is None:
            raise ValueError('This player is no longer available for scouting')
        if action == 'shortlist_remove':
            dept.scouting_shortlist.pop(player_id, None)
        else:
            priority = command.get('priority', 'monitor')
            if priority not in _PRIORITIES:
                raise ValueError('Unknown shortlist priority')
            if (player_id not in dept.scouting_shortlist
                    and len(dept.scouting_shortlist) >= 300):
                raise ValueError('Shortlist is full')
            dept.scouting_shortlist[player_id] = priority
        return {'player_id': player_id, 'shortlist_priority': dept.scouting_shortlist.get(player_id)}
    if action == 'cancel':
        if player_id not in dept.scouting_assignments:
            raise ValueError('No observation is active for this player')
        del dept.scouting_assignments[player_id]
        _rebalance(dept, today)
        return {'cancelled': player_id}
    if action != 'assign':
        raise ValueError('Unknown professional scouting operation')
    if _target(session, player_id) is None:
        raise ValueError('Only current professional players from other clubs can be scouted')
    if player_id in dept.scouting_assignments:
        raise ValueError('A scout is already following this player')
    previous = dept.scouting_reports.get(player_id)
    if previous is not None and (today - previous.completed_on).days < 30:
        raise ValueError('Existing report is recent; observations can be repeated after 30 days')
    _rebalance(dept, today)
    people = active_staff(dept, 'scout', today)
    capacity = sum(_slots(person) for person in people)
    if len(dept.scouting_assignments) >= capacity:
        raise ValueError('All scouts are occupied; hire another scout or finish/cancel a report')
    dept.scouting_assignments[player_id] = ProfessionalScoutAssignment(player_id, 'unassigned', today)
    _rebalance(dept, today)
    return {'assigned': player_id, 'free_slots': capacity - len(dept.scouting_assignments)}


def advance_professional_scouting(session, today: date) -> int:
    """One step per elapsed career day. Not called by page reads or match previews."""
    dept = session._world_squads.club_support.get(session.home_club.id)
    if dept is None or not dept.scouting_assignments:
        return 0
    personnel = _rebalance(dept, today)
    completed = 0
    for player_id, task in list(dept.scouting_assignments.items()):
        if task.scout_id == 'unassigned':
            continue
        staff = personnel.get(task.scout_id)
        if staff is None:
            continue
        target = _target(session, player_id)
        if target is None:
            # The player may have transferred to our club or left the game.
            del dept.scouting_assignments[player_id]
            continue
        task.progress_points += _daily_points(staff)
        if task.progress_points < 100:
            continue
        cid, player = target
        report = _evaluate(session, player_id, cid, player, staff.member_id, today)
        dept.scouting_reports[player_id] = report
        del dept.scouting_assignments[player_id]
        completed += 1
        from football_manager.services.manager_inbox import _notice
        _notice(session.manager_inbox, today, 'scouting', f'Professional scout report: {player.full_name}',
                f'{staff.name} finished observing {player.full_name} of {report.club_name}. Review the report in Scouting.',
                f'professional-scout:report:{player_id}:{today.isoformat()}')
    if len(dept.scouting_reports) > 350:
        old = sorted(dept.scouting_reports.values(), key=lambda r: (r.completed_on, r.player_id))
        for item in old[:len(old)-350]:
            del dept.scouting_reports[item.player_id]
    _rebalance(dept, today)
    return completed

# TS-UI-08 — Career scouting hub. The transfer engine remains authoritative for
# bids. This public read-model MUST NOT expose hidden ability or price before a
# report exists. Scout reports are deliberately APPROXIMATE, never latent PA.
_LEAGUES = {1: 'Premier League', 2: 'Championship', 3: 'League One',
            4: 'League Two', 0: 'Outside the four divisions'}
_PRIORITIES = {'top', 'future', 'monitor'}


def _available_search_players(session):
    world = session._world_squads
    for pid, cid, player in _targets(world, session.home_club.id):
        club = world.clubs[cid]
        yield pid, cid, player, club, _LEAGUES[world.identities[cid].tier]


def _search_public(pid, cid, player, club, league, today):
    return {
        'id': pid, 'name': player.full_name, 'club_id': cid, 'club': club.name,
        'league': league, 'country': club.country,
        'nationality': player.identity.nationality,
        'age': player.age_on(today), 'position': player.primary_position.value,
        'positions': [player.primary_position.value] + [p.value for p in player.secondary_positions],
        'foot': player.identity.dominant_foot.value,
        # This domain doesn't record measurements. Never synthesize them.
        'height_cm': None, 'weight_kg': None,
    }


def _estimation(source, quality, player_id, name, maximum=100):
    """Grounded but imprecise estimate, with deterministic observer noise."""
    from hashlib import sha256
    token = sha256(f'{player_id}|{name}|{quality}'.encode('utf-8')).digest()
    jitter = (token[0] % 11) - 5
    spread = max(5, 15 - quality // 13)
    centre = source + jitter
    return [max(1, min(maximum, round(centre - spread))),
            max(1, min(maximum, round(centre + spread)))]


def scouting_hub_read_model(session) -> dict:
    """Global player directory with public facts and report-gated knowledge.

    Reads do not mutate game state. All names are registered professional rivals
    from the transfer engine's existing eligibility filter. The view may be
    filtered freely by country, league, club, position or age in the browser.
    """
    world = session._world_squads
    dept = world.club_support[session.home_club.id]
    now = session.current_date
    employees = sorted(active_staff(dept, 'scout', now), key=lambda s: (-s.quality, s.name))
    active = {m.member_id: m for m in employees}
    existing = list(_available_search_players(session))
    projects = dept.scouting_assignments
    reports = dept.scouting_reports
    public = []
    for pid, cid, player, club, league in existing:
        item = _search_public(pid, cid, player, club, league, now)
        item['priority'] = dept.scouting_shortlist.get(pid)
        # Contract salary/expiry are public employment facts. They are not scouting
        # knowledge; ability, private attributes and undisclosed value remain gated.
        contract = world.contracts.get(pid)
        item['weekly_wage_gbp'] = contract.weekly_wage_gbp if contract else None
        item['contract_until'] = contract.expires_on.isoformat() if contract else None
        item['public_profile'] = None
        if player.overall_rating >= 85:
            # World-class players are publicly known. This NEVER turns into a
            # synthetic completed scout report or discloses hidden PA.
            from football_manager.services.transfer_negotiation import _quote
            attributes = []
            candidates = []
            for group in ('technical', 'mental', 'physical', 'goalkeeping'):
                bundle = getattr(player.attributes, group, None)
                if bundle is None:
                    continue
                for field_item in fields(bundle):
                    rating = getattr(bundle, field_item.name)
                    if not isinstance(rating, (int, float)):
                        continue
                    label = field_item.name.replace('_', ' ').title()
                    attributes.append({'group': group, 'name': label, 'value': rating})
                    candidates.append((rating, label))
            item['public_profile'] = {
                'overall': round(player.overall_rating, 1),
                'market_value_gbp': _quote(world, player).value_gbp,
                # Reputation does not confer knowledge of latent potential.
                # This is a broad age-sensitive projection from known OVR only.
                'potential_range': [round(player.overall_rating),
                                    min(100, round(player.overall_rating + max(3, (28-item['age'])*.55+4)))],
                'attributes': attributes,
                'strengths': [name for _, name in sorted(candidates, reverse=True)[:3]],
            }
        report = reports.get(pid)
        assignment = projects.get(pid)
        if report:
            quality = active[report.scout_id].quality if report.scout_id in active else 55
            ability = _estimation(report.overall, quality, pid, 'overall')
            # PA is private. Estimate an intentionally wide, uncertain band,
            # never the raw player.development.potential value.
            latent = player.development.potential if player.development else player.overall_rating
            potential = _estimation(max(report.overall, latent), quality, pid, 'ceiling')
            potential[0] = min(potential[0], potential[1]); potential[1] = max(potential[1], ability[1])
            uncertainty = max(.13, .31 - quality / 600)
            value = [round(report.value_gbp * (1-uncertainty), -3),
                     round(report.value_gbp * (1+uncertainty), -3)]
            # Only scout-judged ranges, not the authoritative attribute integers.
            # Reuse real recorded values, but preserve uncertainty and cap detail.
            attribute_estimates = []
            for group in ('technical', 'mental', 'physical'):
                attrs = getattr(player.attributes, group, None)
                if attrs is None:
                    continue
                for field_item in fields(attrs):
                    raw = getattr(attrs, field_item.name)
                    bounds = _estimation(raw, quality, pid, group + '.' + field_item.name, maximum=100)
                    attribute_estimates.append({'group': group, 'name': field_item.name.replace('_', ' ').title(),
                                                'range': bounds})
            item['report'] = {
                'date': report.completed_on.isoformat(),
                'scout': active[report.scout_id].name if report.scout_id in active else 'Former scout',
                'confidence': max(48, min(94, int(quality * .80 + 21))),
                'overall_range': ability, 'potential_range': potential,
                'value_range_gbp': value, 'strengths': list(report.strengths),
                'verdict': report.verdict,
                # Explicitly unavailable: no synthetic weaknesses or attributes.
                'attributes': attribute_estimates, 'weaknesses': None,
            }
        elif assignment:
            item['scouting'] = {
                'progress': assignment.progress_points,
                'scout': active[assignment.scout_id].name if assignment.scout_id in active else 'Awaiting scout',
                'days_left': ceil((100-assignment.progress_points)/_daily_points(active[assignment.scout_id]))
                if assignment.scout_id in active else None,
            }
        public.append(item)
    public.sort(key=lambda entry: (entry['club'], entry['name'], entry['id']))

    # Geographic discovery follows each staff member's retained assignment.
    # Recommendations are leads, not reports; NEVER attach hidden OVR to them.
    already=set()
    recommendations=[]
    for scout in employees:
        destination = dept.scouting_destinations.get(scout.member_id, 'all')
        eligible = []
        for pid, cid, player, club, league in existing:
            if destination.startswith('country:') and player.identity.nationality != destination[8:]:
                continue
            if destination.startswith('league:') and league != destination[7:]:
                continue
            if pid in already: continue
            age=player.age_on(now)
            if age > 29: continue
            # This ranking is only used privately to identify interesting leads.
            grade=player.overall_rating + max(0, 25-age)*.65
            from hashlib import sha256
            tie=int.from_bytes(sha256(f'{world.seed}|{pid}|{scout.member_id}|{now.year}-{now.month}'.encode()).digest()[:4], 'big')
            eligible.append((-grade, tie, pid))
        eligible.sort()
        for _,_,pid in eligible[:3]:
            already.add(pid)
            recommendations.append({'player_id':pid, 'scout_id':scout.member_id,
                                    'scout':scout.name, 'destination':destination})

    assigned_counts={m.member_id:sum(a.scout_id==m.member_id for a in projects.values()) for m in employees}
    scouts=[{'id':m.member_id,'name':m.name,'quality':m.quality,
             'capacity':_slots(m), 'occupied':assigned_counts[m.member_id],
             'destination':dept.scouting_destinations.get(m.member_id, 'all')}
            for m in employees]
    locations=sorted({p['nationality'] for p in public})
    leagues=sorted({p['league'] for p in public})
    clubs=sorted(({'id':cid, 'name':club.name, 'league':_LEAGUES[world.identities[cid].tier]}
                  for cid,club in world.clubs.items() if cid!=session.home_club.id), key=lambda x:x['name'])
    return {'schema_version':1,'club_id':session.home_club.id,'club':session.home_club.name,
            'date':now.isoformat(),'season':world.season_label,
            'scouts':scouts,'capacity':sum(s['capacity'] for s in scouts),
            'occupied':len(projects),'free_slots':max(0,sum(s['capacity'] for s in scouts)-len(projects)),
            'reports_completed':len(reports),'recommendations':recommendations,
            'shortlisted':len([p for p in public if p['priority']]),
            'players':public,'countries':locations,'leagues':leagues,'clubs':clubs}
