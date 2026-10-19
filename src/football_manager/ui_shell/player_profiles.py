"""Read-only, reusable player presentation. Attribute charts are not new ratings."""
from __future__ import annotations
from dataclasses import asdict
from statistics import mean
from football_manager.domain.enums import Position
from football_manager.domain.roles import roles_for_position, get_role
from football_manager.domain.player_ratings import CurrentRatingContext

# Explicit presentation groups. They do not modify role weights or OVR/ACT.
OUTFIELD_AXES = (
    ('Pace', ('physical.pace', 'physical.acceleration')),
    ('Finishing', ('technical.finishing', 'technical.shot_power', 'technical.long_shots', 'mental.composure')),
    ('Creation', ('technical.passing', 'technical.crossing', 'mental.vision', 'mental.creativity')),
    ('Ball control', ('technical.first_touch', 'technical.technique', 'technical.dribbling', 'physical.agility')),
    ('Defending', ('technical.tackling', 'technical.marking', 'mental.positioning', 'mental.anticipation')),
    ('Physical', ('physical.strength', 'physical.stamina', 'physical.balance', 'physical.jumping_reach')),
)
KEEPER_AXES = (
    ('Reflexes', ('goalkeeping.reflexes', 'goalkeeping.one_on_ones')),
    ('Handling', ('goalkeeping.handling', 'mental.concentration')),
    ('Aerial', ('goalkeeping.aerial_reach', 'goalkeeping.command_of_area')),
    ('Distribution', ('goalkeeping.kicking', 'goalkeeping.throwing', 'technical.passing')),
    ('Positioning', ('goalkeeping.goalkeeper_positioning', 'mental.anticipation', 'mental.decisions')),
    ('Athleticism', ('physical.agility', 'physical.acceleration', 'physical.jumping_reach')),
)


def _value(player, path):
    group, field = path.split('.')
    attrs = getattr(player.attributes, group, None)
    return getattr(attrs, field, None) if attrs is not None else None


def profile_graphics(player, position: Position, role_id: str | None = None) -> dict:
    role_options = roles_for_position(position)
    role = get_role(role_id) if role_id else role_options[0]
    if not role.supports(position):
        raise ValueError('role is incompatible with selected position')
    axes = KEEPER_AXES if position is Position.GK else OUTFIELD_AXES
    general = []
    for label, paths in axes:
        values = [_value(player, path) for path in paths]
        general.append({'label': label, 'value': round(mean(values), 1) if all(v is not None for v in values) else None,
                        'attributes': list(paths)})
    # Six (or fewer) highest-weight role attributes, directly from the engine.
    selected = sorted(role.attribute_weights, key=lambda item: (-item[1], item[0]))[:6]
    return {'scale': [0, 100], 'general': general,
            'role': {'id': role.role_id, 'name': role.name,
                     'axes': [{'label': path.split('.')[1].replace('_', ' ').title(),
                               'value': _value(player, path), 'weight': weight, 'attribute': path}
                              for path, weight in selected]},
            'role_options': [{'id': r.role_id, 'name': r.name} for r in role_options],
            'note': 'General axes: arithmetic means. Role axes: highest-weight attributes of the selected engine role, not a potential estimate or a new rating.',
            'evolution': {'available': False, 'message': 'Attribute development history is not implemented yet. Changes in current GRL from fatigue are not development.'}}


def player_profile_read_model(session, club_id, player_id, *, position=None, role_id=None):
    registry = session._world_squads
    club = registry.clubs.get(club_id)
    archived = registry.retired_players.get(player_id)
    if club is not None and club.squad.contains(player_id):
        player = club.squad.get(player_id)
    elif archived is not None and archived.club_id == club_id:
        player = archived.player
    else:
        raise KeyError('Player is not in this persistent squad or its retirement archive')
    assigned = Position(position) if position else player.primary_position
    from football_manager.services.player_development import development_read_model
    graphics = profile_graphics(player, assigned, role_id)
    graphics['evolution'] = development_read_model(player, session.current_date)
    from football_manager.services.market_valuation import player_market_view
    market = (player_market_view(registry, player, session.current_date)
              if club is not None and club.squad.contains(player_id) else None)
    return {'club_id': club_id, 'player_id': player_id, 'graphics': graphics, 'valuation': market}
