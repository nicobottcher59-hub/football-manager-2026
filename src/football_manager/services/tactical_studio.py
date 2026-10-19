"""Validated tactical editor commands. The HTTP transaction owns rollback."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from math import isfinite

from football_manager.domain.enums import Position
from football_manager.domain.formation import FormationSlot
from football_manager.domain.roles import default_role_for_position, get_role
from football_manager.domain.tactics import RoleAssignment
from football_manager.domain.tactical_shapes import PHASES, PhaseShape, SlotPoint
from football_manager.domain.tactical_studio import (
    MAX_TACTICS, PLAN_KEYS, PLAN_CONDITIONS, PlanRule, SavedTactic, tactic_name,
)
from football_manager.domain.tactical_presets import TacticalPreset
from football_manager.domain.tactical_geometry import base_formation_id, phase_points
from football_manager.domain.tactical_position_zones import position_options, position_zone_read_model

STUDIO_ACTIONS = frozenset({
    'studio_point', 'studio_place', 'studio_shape', 'studio_position', 'studio_save',
    'studio_load', 'studio_rename', 'studio_duplicate', 'studio_delete',
    'studio_plan', 'studio_activate_plan', 'studio_rules',
})


def same_tactic(left, right) -> bool:
    return (left.formation == right.formation
            and left.team_instructions == right.team_instructions
            and left.role_assignments == right.role_assignments
            and left.phase_shapes == right.phase_shapes)


def _entry(state, entry_id):
    if not isinstance(entry_id, str) or entry_id not in state.library:
        raise ValueError('saved tactic does not exist')
    return state.library[entry_id]


def _name(state, raw, except_id=None):
    name = tactic_name(raw)
    if any(e.name.casefold() == name.casefold() and key != except_id for key, e in state.library.items()):
        raise ValueError('a tactic with that name already exists')
    return name


def _next_id(state):
    if len(state.library) >= MAX_TACTICS:
        raise ValueError(f'the library supports at most {MAX_TACTICS} tactics')
    while True:
        state.sequence += 1
        key = f'tactic-{state.sequence:05d}'
        if key not in state.library:
            return key


def load_template(session, template, *, entry_id=None):
    from football_manager.dev_ui.session import _reassign_lineup_to_formation
    tactic = deepcopy(template)
    tactic.__post_init__()
    # Reuse the current eleven, never save or resurrect a player's selection.
    lineup = session.home_lineup
    if lineup.formation != tactic.formation:
        lineup = _reassign_lineup_to_formation(lineup, tactic.formation)
    tactic.tactic_id = session.home_tactic.tactic_id
    session.home_lineup, session.home_tactic = lineup, tactic
    session.tactical_studio.active_id = entry_id
    session._sync_effective_tactic_familiarity(home=True)


def _coordinate(value):
    if type(value) not in (int, float) or not isfinite(value):
        raise ValueError('coordinates must be finite numeric percentages')
    return round(float(value) / 100, 6)


def _point(raw):
    if not isinstance(raw, dict) or set(raw) != {'slot_id', 'x', 'y'}:
        raise ValueError('a target needs exactly slot_id, x and y')
    return SlotPoint(raw['slot_id'], _coordinate(raw['x']), _coordinate(raw['y']))


def _with_position(session, slot_id, position):
    """Build a validated candidate without changing player identities or OVR rules."""
    tactic = session.home_tactic
    slot = tactic.formation.slot(slot_id)
    if (slot.position is Position.GK) != (position is Position.GK):
        raise ValueError('the goalkeeper slot cannot be converted to/from an outfield slot')
    if slot.position == position:
        return replace(tactic), session.home_lineup
    original = tactic.formation
    formation = replace(original, formation_id='custom:' + base_formation_id(original.formation_id),
                        name='Custom ' + original.name.removeprefix('Custom '),
                        slots=tuple(FormationSlot(s.slot_id, position) if s.slot_id == slot_id else s
                                    for s in original.slots))
    roles = dict(tactic.role_assignments)
    if not get_role(roles[slot_id].role_id).supports(position):
        roles[slot_id] = RoleAssignment(default_role_for_position(position).role_id)
    candidate = replace(tactic, formation=formation, role_assignments=roles,
                        preset_origin=TacticalPreset.CUSTOM)
    return candidate, replace(session.home_lineup, formation=formation)


def apply_studio_command(session, command):
    state = session.tactical_studio
    action = command['action']
    if action not in STUDIO_ACTIONS:
        raise ValueError('unsupported studio command')
    expected = command.get('expected_revision')
    if expected is not None and (type(expected) is not int or expected != state.revision):
        raise ValueError('tactics changed in another view; refresh before editing')
    tactic = session.home_tactic
    if action == 'studio_point':
        slot_id, phase = command.get('slot_id'), command.get('phase')
        if not isinstance(slot_id, str) or phase not in PHASES:
            raise ValueError('invalid slot or phase')
        slot = tactic.formation.slot(slot_id)
        if slot.position is Position.GK and command.get('reset') is not True:
            raise ValueError('the goalkeeper is fixed in the tactical editor')
        if command.get('reset') is True:
            tactic.set_phase_point(phase, slot_id, None, None)
        else:
            point = _point({'slot_id': slot_id, 'x': command.get('x'), 'y': command.get('y')})
            tactic.set_phase_point(phase, slot_id, point.x, point.y)
        tactic.preset_origin = TacticalPreset.CUSTOM
    elif action == 'studio_shape':
        raw = command.get('points')
        if not isinstance(raw, list) or len(raw) > 11:
            raise ValueError('phase shape needs up to eleven explicit targets')
        points = tuple(_point(p) for p in raw)
        goalkeeper_slots = {slot.slot_id for slot in tactic.formation.slots if slot.position is Position.GK}
        if any(p.slot_id in goalkeeper_slots for p in points):
            raise ValueError('the goalkeeper is fixed in the tactical editor')
        tactic.replace_phase_shape(command.get('phase'), points)
        tactic.preset_origin = TacticalPreset.CUSTOM
    elif action == 'studio_place':
        # A drop is a draft until the user chooses a position. Validate position
        # and geometry together, before replacing either lineup or tactic.
        slot_id, phase = command.get('slot_id'), command.get('phase')
        if not isinstance(slot_id, str) or phase not in PHASES:
            raise ValueError('invalid slot or phase')
        point = _point({'slot_id': slot_id, 'x': command.get('x'), 'y': command.get('y')})
        slot = tactic.formation.slot(slot_id)
        if slot.position is Position.GK:
            raise ValueError('the goalkeeper is fixed in the tactical editor')
        position = Position(command.get('position'))
        if position not in position_options(point.x, point.y, goalkeeper=slot.position is Position.GK):
            raise ValueError('choose a football position compatible with the dropped area')
        candidate, lineup = _with_position(session, slot_id, position)
        candidate.set_phase_point(phase, slot_id, point.x, point.y)
        candidate.preset_origin = TacticalPreset.CUSTOM
        if slot.position != position:
            # Position/role is global. Preserve the existing opposite-phase
            # location so this edit does not unexpectedly move the other shape.
            other = next(p for p in PHASES if p != phase)
            before = phase_points(tactic, other)[slot_id]
            if phase_points(candidate, other)[slot_id] != before:
                candidate.set_phase_point(other, slot_id, *before)
        session.home_tactic, session.home_lineup = candidate, lineup
        if slot.position != position:
            session._sync_effective_tactic_familiarity(home=True)
    elif action == 'studio_position':
        slot_id = command.get('slot_id')
        position = Position(command.get('position'))
        slot = tactic.formation.slot(slot_id)
        # Phase-aware UI changes are restricted to the marker's current zone.
        # No-phase calls remain the original explicit assignment API, used by
        # legacy automation; saved templates are never reinterpreted on load.
        phase = command.get('phase')
        if phase is not None:
            point = phase_points(tactic, phase)[slot_id]
            if position not in position_options(*point, goalkeeper=slot.position is Position.GK):
                raise ValueError('choose a football position compatible with this phase location')
        if slot.position != position:
            candidate, lineup = _with_position(session, slot_id, position)
            if phase is not None:
                # Retain both visible locations when selecting an actual role
                # family. Coordinates and role are different editing concepts.
                for current_phase in PHASES:
                    before = phase_points(tactic, current_phase)[slot_id]
                    if phase_points(candidate, current_phase)[slot_id] != before:
                        candidate.set_phase_point(current_phase, slot_id, *before)
            session.home_tactic, session.home_lineup = candidate, lineup
            session._sync_effective_tactic_familiarity(home=True)
    elif action == 'studio_save':
        entry_id = command.get('entry_id')
        if entry_id is not None:
            _entry(state, entry_id)
        name = _name(state, command.get('name'), entry_id)
        entry_id = entry_id or _next_id(state)
        saved = deepcopy(tactic)
        saved.name = name
        state.library[entry_id] = SavedTactic(entry_id, name, saved)
        state.active_id = entry_id
    elif action == 'studio_load':
        entry = _entry(state, command.get('entry_id'))
        load_template(session, entry.tactic, entry_id=entry.entry_id)
    elif action == 'studio_rename':
        entry = _entry(state, command.get('entry_id'))
        name = _name(state, command.get('name'), entry.entry_id)
        copied = deepcopy(entry.tactic)
        copied.name = name
        state.library[entry.entry_id] = SavedTactic(entry.entry_id, name, copied)
    elif action == 'studio_duplicate':
        entry = _entry(state, command.get('entry_id'))
        name = _name(state, command.get('name'))
        new_id = _next_id(state)
        copied = deepcopy(entry.tactic)
        copied.name = name
        state.library[new_id] = SavedTactic(new_id, name, copied)
    elif action == 'studio_delete':
        entry = _entry(state, command.get('entry_id'))
        del state.library[entry.entry_id]
        for key, value in state.plans.items():
            if value == entry.entry_id:
                state.plans[key] = None
        state.rules = tuple(r for r in state.rules if state.plans[r.plan] is not None)
        if state.active_id == entry.entry_id:
            state.active_id = None
    elif action == 'studio_plan':
        key, entry_id = command.get('plan'), command.get('entry_id')
        if key not in PLAN_KEYS:
            raise ValueError('plan must be A, B or C')
        if entry_id is not None:
            _entry(state, entry_id)
        state.plans[key] = entry_id
        if entry_id is None:
            state.rules = tuple(r for r in state.rules if r.plan != key)
    elif action == 'studio_activate_plan':
        key = command.get('plan')
        if key not in PLAN_KEYS:
            raise ValueError('plan must be A, B or C')
        entry = _entry(state, state.plans[key])
        load_template(session, entry.tactic, entry_id=entry.entry_id)
    elif action == 'studio_rules':
        raw = command.get('rules')
        if not isinstance(raw, list) or len(raw) > 6:
            raise ValueError('use at most six in-match plan rules')
        rules = []
        for item in raw:
            if not isinstance(item, dict) or set(item) != {'plan', 'minute', 'condition'}:
                raise ValueError('a plan rule needs plan, minute and condition')
            rules.append(PlanRule(item['plan'], item['minute'], item['condition']))
        # Validate before changing live state, including plan references.
        candidate = replace(state, rules=tuple(sorted(rules, key=lambda r: r.minute)))
        candidate.validate()
        state.rules = candidate.rules
    state.validate()


def studio_read_model(session):
    state, tactic = session.tactical_studio, session.home_tactic
    active = state.library.get(state.active_id)
    return {
        'version': 1, 'revision': state.revision, 'active_id': state.active_id,
        'dirty': active is None or not same_tactic(tactic, active.tactic),
        'anchors': {shape.phase: {p.slot_id: {'x': round(p.x * 100, 4), 'y': round(p.y * 100, 4)}
                                  for p in shape.points} for shape in tactic.phase_shapes},
        'shapes': {phase: {key: {'x': round(x * 100, 4), 'y': round(y * 100, 4)}
                           for key, (x, y) in phase_points(tactic, phase).items()} for phase in PHASES},
        'library': [{'id': e.entry_id, 'name': e.name, 'formation': e.tactic.formation.name,
                     'custom_points': sum(len(s.points) for s in e.tactic.phase_shapes)}
                    for e in sorted(state.library.values(), key=lambda e: (e.name.casefold(), e.entry_id))],
        'plans': dict(state.plans),
        'rules': [{'plan': r.plan, 'minute': r.minute, 'condition': r.condition} for r in state.rules],
        'positions': [p.value for p in Position],
        'position_zones': position_zone_read_model(),
        'opponent': {
            'name': session.away_club.name,
            'formation': session.away_tactic.formation.name,
            'shapes': {phase: [{'slot_id': key, 'x': round(x * 100, 4), 'y': round(y * 100, 4),
                               'position': session.away_tactic.formation.slot(key).position.value}
                              for key, (x, y) in phase_points(session.away_tactic, phase).items()]
                       for phase in PHASES},
        },
        'persistence': 'Saved with the complete career save; legacy results-only JSON does not include tactics.',
        'plan_execution': 'Rules are checked once, immediately before the chosen minute, against the actual score.',
    }


def prepared_match_plans(session):
    """Snapshot each saved plan using an isolated roster, with canonical ACT.

    Only the selected team is copied, not a whole world simulation. Plans carry
    tactical assignments, never replacement players or changes to the bench.
    """
    from copy import copy
    from football_manager.services.match_snapshot_builder import build_team_match_snapshot
    from football_manager.fast_simulation.plans import FastTacticalChange
    state = session.tactical_studio
    state.validate()
    prepared = {}
    for rule in state.rules:
        entry_id = state.plans[rule.plan]
        if entry_id not in prepared:
            temporary = copy(session)
            temporary.home_club, temporary.home_lineup, temporary.home_tactic = deepcopy(
                (session.home_club, session.home_lineup, session.home_tactic))
            temporary.tactical_studio = deepcopy(state)
            # _sync_effective_tactic_familiarity reads these dictionaries, and
            # future extensions must not be able to mutate the live baselines.
            temporary._home_base_tactic_familiarity = dict(session._home_base_tactic_familiarity)
            load_template(temporary, state.library[entry_id].tactic, entry_id=entry_id)
            prepared[entry_id] = build_team_match_snapshot(
                club=temporary.home_club, lineup=temporary.home_lineup,
                tactic=temporary.home_tactic, chemistry_by_player=session._home_chemistry)
    return tuple(FastTacticalChange(rule, state.library[state.plans[rule.plan]].name,
                                  prepared[state.plans[rule.plan]]) for rule in state.rules)
