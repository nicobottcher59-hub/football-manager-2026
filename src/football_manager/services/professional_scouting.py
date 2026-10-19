"""TS-26.1: bounded first-team scouting reports, without hiding player data.

This is a work queue, not a replacement for the transfer search or youth
academy. More scouts provide more simultaneous observation slots; higher
quality scouts work faster and, at 78+, cover a second player. Reports only
summarize already-public attributes, and confer no negotiation advantage.
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
            'note': 'Attributes remain fully visible. Professional scouts add optional reports; they do not unlock stats or change transfer odds.'}


def scouting_command(session, command: dict) -> dict:
    dept = session._world_squads.club_support[session.home_club.id]
    today = session.current_date
    action, player_id = command.get('action'), command.get('player_id')
    if not isinstance(player_id, str) or not player_id or len(player_id) > 160:
        raise ValueError('Choose a valid player to scout')
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
