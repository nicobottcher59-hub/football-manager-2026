"""Negotiation-safe identity and knowledge. Never expose hidden ratings/quotes.

Own players and already-public 85+ players use their general OVR (not current
match-adjusted rating). Reports expose their recorded snapshot, not a fresh
private evaluation. Unobserved values are JSON null, rendered as ?? by the UI.
"""
from __future__ import annotations


def player_knowledge(session, club_id, player) -> dict:
    registry = session._world_squads
    manager = session.home_club.id
    support = registry.club_support.get(manager)
    report = support.scouting_reports.get(player.id) if support else None
    source = 'unknown'
    overall = value = observed = None
    if club_id == manager or player.overall_rating >= 85:
        from football_manager.services.transfer_negotiation import _quote
        source = 'own_club' if club_id == manager else 'public'
        overall = round(player.overall_rating, 1)
        value = _quote(registry, player).value_gbp
    elif report is not None:
        source, overall, value = 'scout_report', report.overall, report.value_gbp
        observed = report.completed_on.isoformat()
    club = registry.clubs[club_id]
    contract = registry.contracts.get(player.id)
    tier = registry.identities[club_id].tier
    return {'id': player.id, 'name': player.full_name, 'club_id': club_id, 'club': club.name,
        'age': player.age_on(session.current_date), 'position': player.primary_position.value,
        'positions': [player.primary_position.value, *(p.value for p in player.secondary_positions)],
        'nationality': player.identity.nationality, 'country': club.country,
        'league': {1:'Premier League',2:'Championship',3:'League One',4:'League Two',0:'Other divisions'}[tier],
        'ovr': overall, 'value_gbp': value, 'knowledge_source': source, 'observed_on': observed,
        'contract_until': contract.expires_on.isoformat() if contract else None}
