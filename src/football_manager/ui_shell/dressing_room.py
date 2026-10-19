"""Read-only TS-20 projection. Private personality numbers never leave Python."""
from __future__ import annotations

from datetime import timedelta

from football_manager.domain.dressing_room import TIERS, TIER_LABELS, MAX_MORALE_EFFECT
from football_manager.services.dressing_room import participation_concern


def _groups(state) -> list[list[str]]:
    """Observed strong-link components, not imposed friendship factions."""
    neighbours = {pid: set() for pid in state.members}
    for (a, b), link in state.links.items():
        if link.affinity >= 70:
            neighbours[a].add(b)
            neighbours[b].add(a)
    groups, seen = [], set()
    for pid in sorted(neighbours):
        if pid in seen:
            continue
        pending, group = [pid], []
        while pending:
            node = pending.pop()
            if node in seen:
                continue
            seen.add(node)
            group.append(node)
            pending.extend(sorted(neighbours[node] - seen, reverse=True))
        if len(group) >= 3:
            groups.append(sorted(group))
    return groups


def dressing_room_read_model(session) -> dict:
    state = session.dressing_room
    players = {p.id: p for p in session.home_club.squad.players}
    day = state.last_updated
    members = []
    for pid, member in sorted(state.members.items(), key=lambda item: (-item[1].influence, item[0])):
        # A pending external roster edit must be committed/reconciled by its
        # application service. Never mutate state while constructing a GET.
        player = players.get(pid)
        if player is None:
            continue
        recent = [a for a in member.appearances if (day-a.day).days <= 42]
        concern = participation_concern(member, player, day)
        reasons = []
        if concern >= .3:
            reasons.append('Several recent matches without much playing time while available.')
        if member.departure_disruption >= .15:
            reasons.append('Adjusting to the departure of a close, influential teammate.')
        if member.integration < 55:
            reasons.append('Still getting to know this group; settling happens automatically.')
        if member.support_player_id is not None:
            reasons.append('An established teammate is helping integration naturally.')
        if not reasons:
            reasons.append('No significant social concern. Football decisions remain the priority.')
        drift = member.influence-member.previous_influence
        # Qualitative observations, not numeric hidden-trait disclosure.
        observed = (day-member.joined_on).days >= 28
        character = 'Getting to know the group'
        if observed:
            if player.personality.professionalism >= 75:
                character = 'Consistent, professional approach'
            elif player.personality.pressure_resistance >= 75:
                character = 'Usually measured after setbacks'
            elif player.personality.ambition >= 75:
                character = 'Keen to establish a bigger role'
            else:
                character = 'Quietly finding a place in the group'
        members.append({
            'id': pid, 'name': player.full_name, 'short_name': player.identity.last_name,
            'age': player.age_on(day), 'position': player.primary_position.value,
            'tier': member.tier, 'tier_label': TIER_LABELS[member.tier],
            'trend': 'rising' if drift > .15 else 'easing' if drift < -.15 else 'steady',
            'integration': round(member.integration, 1),
            'integration_label': 'Settled' if member.integration >= 65 else 'Settling in',
            'observed_since': member.joined_on.isoformat(),
            'newcomer': (day-member.joined_on).days < 28 and member.joined_on > state.started_on,
            'young_player': player.age_on(day) <= 21,
            'support_player_id': member.support_player_id,
            'recent_appearances': sum(a.minutes > 0 for a in recent),
            'eligible_matches': sum(a.eligible for a in recent),
            'recent_minutes': sum(a.minutes for a in recent),
            'morale': round(player.state.effective_morale, 1),
            'base_morale': round(player.state.morale, 1),
            'social_morale_effect': round(player.state.dressing_room_morale, 2),
            'character_note': character, 'reasons': reasons,
        })
    links = [{
        'a': a, 'b': b, 'strength': round(link.affinity, 1),
        'label': 'Close connection' if link.affinity >= 70 else 'Good understanding' if link.affinity >= 60
                 else 'Working relationship' if link.affinity >= 45 else 'Rapport still developing',
        'shared_minutes': link.shared_minutes,
    } for (a, b), link in sorted(state.links.items()) if a in players and b in players]
    average = sum(m['social_morale_effect'] for m in members)/len(members) if members else 0.0
    return {
        'source': 'python-dressing-room', 'version': 1,
        'club_id': session.home_club.id, 'club': session.home_club.name,
        'date': session.current_date.isoformat(), 'updated_on': day.isoformat(),
        'observed_since': state.started_on.isoformat(), 'revision': state.revision,
        'last_review': state.last_review.isoformat(),
        'next_review': (state.last_review+timedelta(days=7)).isoformat(),
        'automated': True, 'decisions_required': False,
        'atmosphere': round(state.atmosphere, 1),
        'atmosphere_label': 'Positive' if state.atmosphere >= 69 else 'Stable' if state.atmosphere >= 59 else 'Settling',
        'average_morale_effect': round(average, 2), 'max_morale_effect': MAX_MORALE_EFFECT,
        'members': members, 'links': links, 'groups': _groups(state),
        'tiers': [{'id': tier, 'label': TIER_LABELS[tier], 'count': sum(m['tier']==tier for m in members)} for tier in TIERS],
        'events': [{'id': event.sequence, 'date': event.day.isoformat(), 'kind': event.kind,
                    'player_ids': list(event.player_ids), 'message': event.message}
                   for event in reversed(state.events)],
        'notes': [
            'Relationships progress with actual days and played matches, never with page visits or lineup experiments.',
            'The hierarchy is reviewed weekly. Age alone does not make a player a leader.',
            'Social effects use the existing morale channel only, bounded to +/-2 on its 0-100 scale.',
            'No meetings, compulsory decisions or manual relationship management.',
        ],
    }
