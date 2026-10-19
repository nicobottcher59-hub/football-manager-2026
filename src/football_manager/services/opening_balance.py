"""Opt-in, one-time correction of the legacy fictional Northbridge opening data.

Not a difficulty modifier, not an attribute cap and never applied on load.
Transfers, changed/developed players, physical state and other clubs are untouched.
"""
from __future__ import annotations
from dataclasses import fields, replace

BALANCE_ID = 'ts22-northbridge-opening-v1'


def _candidates(session):
    from football_manager.dev_ui.session import _build_side, _HOME_NAMES
    from football_manager.domain.tactical_presets import TacticalPreset
    if session.home_club.id != 'northbridge':
        return []
    legacy, _, _ = _build_side(club_id='northbridge', name='Northbridge FC', short_name='NBR',
                             base_offset=3, tactic_preset=TacticalPreset.BALANCED, names=_HOME_NAMES)
    canonical = {p.id: p for p in legacy.squad.players}
    return [p for p in session.home_club.squad.players
            if p.id in canonical and p.full_name == canonical[p.id].full_name
            and p.attributes == canonical[p.id].attributes]


def preview_opening_balance(session) -> dict:
    done = BALANCE_ID in session._world_squads.balance_adjustments
    candidates = [] if done else _candidates(session)
    return {'id': BALANCE_ID, 'applied': done, 'eligible': bool(candidates),
            'players': [{'id': p.id, 'name': p.full_name} for p in candidates],
            'count': len(candidates), 'attribute_reduction': 5,
            'target': 'Opening XI approximately 80-81 base OVR in its original formation/roles.',
            'description': 'Reduce unchanged legacy opening-player attributes by 5 once. No condition, fatigue, familiarity, results, transfers or other clubs change. Save the career afterwards.'}


def apply_opening_balance(session, confirmation: str) -> dict:
    if confirmation != BALANCE_ID:
        raise ValueError('explicit opening balance confirmation required')
    if BALANCE_ID in session._world_squads.balance_adjustments:
        raise ValueError('opening balance already applied')
    players = _candidates(session)
    if not players:
        raise ValueError('no unchanged legacy opening players eligible')
    for player in players:
        from football_manager.domain.player_development import current_ability, reference_overall, DevelopmentExposure
        old_ability = current_ability(player)
        changes = {}
        for group in ('technical', 'mental', 'physical', 'goalkeeping'):
            attrs = getattr(player.attributes, group)
            if attrs is not None:
                changes[group] = replace(attrs, **{f.name: max(1, getattr(attrs, f.name) - 5) for f in fields(attrs)})
        player.attributes = replace(player.attributes, **changes)
        if player.development is not None:
            # Explicit data correction, not ageing. Preserve the existing PA
            # headroom and curve; do not manufacture five extra growth points.
            new_ability = current_ability(player)
            player.development = replace(player.development,
                potential=player.development.potential - (old_ability - new_ability),
                baseline_ability=new_ability, baseline_overall=reference_overall(player),
                started_on=session.current_date, last_review=session.current_date,
                exposure=DevelopmentExposure(), history=(), annual_history=(), last_changes={})
    record = {'date': session.current_date.isoformat(), 'player_ids': [p.id for p in players], 'source': 'explicit-user-action'}
    session._world_squads.balance_adjustments[BALANCE_ID] = record
    return {'applied': True, **record, 'save_required': True}
