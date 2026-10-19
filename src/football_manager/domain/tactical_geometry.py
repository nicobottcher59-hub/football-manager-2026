"""Deterministic tactical geometry used by the editor and fast-engine expansion.

This is estimated occupation, NOT event-derived heatmap data or win probability.
The automatic positions mirror the portable board; explicit phase targets take
precedence. Keeping the same axes at the boundary avoids away-team mirroring bugs.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import exp, hypot
from statistics import mean
from .enums import Position
from .tactical_catalogue import formation_board_layouts
from .tactical_shapes import PHASES, phase_target

_BASE = {
    'GK': (50, 90), 'RB': (83, 75), 'RCB': (61, 75), 'CB': (50, 75),
    'LCB': (39, 75), 'LB': (17, 75), 'RWB': (85, 65), 'LWB': (15, 65),
    'DM': (50, 59), 'RCM': (64, 49), 'CM': (50, 49), 'LCM': (36, 49),
    'AM': (50, 34), 'RW': (84, 26), 'LW': (16, 26), 'SS': (50, 24), 'ST': (50, 14),
}


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def base_formation_id(formation_id: str) -> str:
    return formation_id.removeprefix('custom:')


def base_points(formation) -> dict[str, tuple[float, float]]:
    layout = formation_board_layouts().get(base_formation_id(formation.formation_id), {})
    result = {}
    for slot in formation.slots:
        if slot.slot_id in layout:
            result[slot.slot_id] = layout[slot.slot_id]
            continue
        x, y = _BASE.get(slot.position.value, (50, 50))
        if slot.slot_id in ('rdm', 'ram', 'rst'):
            x = 61 if slot.position in (Position.ST, Position.AM) else 63
        if slot.slot_id in ('ldm', 'lam', 'lst'):
            x = 39 if slot.position in (Position.ST, Position.AM) else 37
        result[slot.slot_id] = (x / 100, y / 100)
    return result


def player_instructions(tactic, slot_id: str):
    if hasattr(tactic, 'effective_player_instructions'):
        return tactic.effective_player_instructions(slot_id)
    try:
        return tactic.slot(slot_id).effective_instructions
    except KeyError:
        # Legacy/manual incomplete snapshots remain neutral, not fatal.
        from .tactical_instructions import PlayerInstructions
        return PlayerInstructions()


def phase_points(tactic, phase: str, *, use_overrides: bool = True) -> dict[str, tuple[float, float]]:
    if phase not in PHASES:
        raise ValueError('unknown tactical phase')
    on = phase == 'in_possession'
    group = getattr(tactic.team_instructions, phase)
    trans = tactic.team_instructions.transition
    # Management instructions depend on the live score, never on a pre-match diagram.
    base = base_points(tactic.formation)
    result = {}
    for slot in tactic.formation.slots:
        x, y = (v * 100 for v in base[slot.slot_id])
        line = 'defensive' if y >= 67 else 'midfield' if y >= 40 else 'attacking'
        if slot.position is not Position.GK:
            width = float(getattr(group, f'{line}_line_width' if line != 'midfield' else 'midfield_width'))
            factor = .58 + width / 100 * .86
            if not on:
                factor *= 1.15 - float(group.horizontal_compactness) / 260
                factor *= 1.11 - float(group.protect_centre) / 420
            x = 50 + (x - 50) * factor
            dg, ag = float(group.defense_midfield_gap), float(group.midfield_attack_gap)
            if line == 'midfield':
                y += (dg - 50) * -.12
            if line == 'attacking':
                y += (ag - 50) * -.11 + (dg - 50) * -.055
            if on:
                forward = (float(group.verticality) - 50) * .042 + (float(group.tempo) - 50) * .024
                y -= forward * (1 if line == 'attacking' else .65 if line == 'midfield' else .16)
                y += (float(group.patience) - 50) * .018
                y += (float(group.support_closeness) - 50) * (.035 if line == 'midfield' else -.01)
                x += (x - 50) * (float(group.switch_play) - 50) / 950
                if line == 'defensive':
                    y += (float(group.build_from_back) - 50) * .039
                if line == 'attacking':
                    x += (x - 50) * (float(group.crossing_frequency) - 50) / 1150
                if slot.position in (Position.RB, Position.LB, Position.RWB, Position.LWB):
                    x += (x - 50) * (float(group.overlap_frequency) - 50) / 450
                if line == 'midfield':
                    y -= (float(group.long_shot_frequency) - 50) * .033
                    y -= (float(group.pass_speed) - 50) * .018
                if line == 'attacking':
                    y -= (float(group.passing_risk) - 50) * .018
                    y += (float(group.central_focus) - 50) * .018
                y -= (float(group.pass_length) / 25 - 2) * .8
            else:
                block = (float(group.block_height) - 50) * .2
                height = (float(group.defensive_line_height) - 50) * .15
                press = (float(group.pressing_intensity) - 50) * .09
                y -= block * .45 + height if line == 'defensive' else block if line == 'midfield' else block + press
                y += (50 - float(group.vertical_compactness)) * (y - 50) / 430
                if line == 'defensive' and group.offside_trap:
                    y -= 3
                if line == 'midfield':
                    y -= (float(group.defensive_aggression) - 50) * .05
                if line == 'defensive':
                    y += (float(group.protect_box) - 50) * .03
                if group.marking_style.value == 'man':
                    x += 1.2 if x >= 50 else -1.2
                scheme = group.pressing_scheme.value
                if scheme == 'constant':
                    y -= 1.8
                if scheme == 'trap_inside':
                    x += (50 - x) * .06
                if scheme == 'trap_outside':
                    x += (x - 50) * .06
                if group.force_direction.value == 'inside':
                    x += (50 - x) * .055
                if group.force_direction.value == 'outside':
                    x += (x - 50) * .055
                if line == 'attacking':
                    y -= (float(group.cross_tolerance) - 50) * .018
            if on:
                if trans.after_win.value in ('counter', 'direct'):
                    y -= 3 if line == 'attacking' else 1
                if trans.after_win.value == 'expand':
                    x += (x - 50) * .05
                y -= (float(trans.transition_speed) - 50) * .015
                if line == 'attacking':
                    y -= (float(trans.counterattack_risk) - 50) * .023
            else:
                if trans.after_loss.value == 'counterpress':
                    y -= 4 if line == 'attacking' else 1
                if trans.after_loss.value == 'regroup':
                    y += 2 if line == 'attacking' else 3
            x, y = clamp(x, 7, 93), clamp(y, 8, 84)
        elif on:
            y -= (float(trans.goalkeeper_release_speed) - 50) * .025
        ins = player_instructions(tactic, slot.slot_id)
        pos = (ins.in_possession_position if on else ins.out_of_possession_position).value
        if pos == 'wide':
            x += 3 if x >= 50 else -3
        if pos == 'inside':
            x += (50 - x) * .25
        if pos == 'midfield':
            y += (50 - y) * .22
        if pos in ('advance', 'step_up'):
            y -= 5
        if pos in ('drop_deep', 'drop'):
            y += 5
        if pos == 'return_to_base' and not on:
            x = 50 + (x - 50) * .94
        x, y = clamp(x, 5, 95) / 100, clamp(y, 5, 95) / 100
        point = phase_target(tactic.phase_shapes, phase, slot.slot_id) if use_overrides else None
        result[slot.slot_id] = (point.x, point.y) if point else (x, y)
    return result


def occupation(points, x: float, y: float) -> float:
    """Bounded geometric coverage. points excludes the goalkeeper."""
    intensity = sum(exp(-.5 * (((x - px) / .16) ** 2 + ((y - py) / .13) ** 2))
                    for px, py in points)
    return 1.0 - exp(-intensity)


def rest_cover(points, x: float) -> float:
    """Cover remaining behind the ball for a generic loss in the attacking half."""
    intensity = sum(exp(-.5 * (((x - px) / .18) ** 2 + ((.72 - py) / .18) ** 2))
                    * clamp((py - .34) / .26, 0, 1) for px, py in points)
    return 1 - exp(-intensity)


@dataclass(frozen=True, slots=True)
class ShapeSummary:
    left_cover: float = .65
    centre_cover: float = .80
    right_cover: float = .65
    attacking_support: float = .50
    connection: float = .65
    defensive_width: float = .65
    attacking_width: float = .65
    block_left_cover: float = .65
    block_centre_cover: float = .80
    block_right_cover: float = .65
    screen_control: float = .65
    keeper_exposure: float = 0.0
    keeper_support: float = 0.0


def shape_summary(tactic) -> ShapeSummary:
    on, off = phase_points(tactic, PHASES[0]), phase_points(tactic, PHASES[1])
    ids = [s.slot_id for s in tactic.formation.slots if s.position is not Position.GK]
    points = [on[k] for k in ids]
    off_points = [off[k] for k in ids]
    defense = [off[k] for k in ids if off[k][1] >= .50]
    attack = [on[k] for k in ids if on[k][1] <= .50]
    nearest = [min(hypot(x - xx, y - yy) for j, (xx, yy) in enumerate(points) if i != j)
               for i, (x, y) in enumerate(points)]
    keeper_id = next(s.slot_id for s in tactic.formation.slots if s.position is Position.GK)
    keeper_on = phase_target(tactic.phase_shapes, 'in_possession', keeper_id)
    keeper_off = phase_target(tactic.phase_shapes, 'out_of_possession', keeper_id)
    def exposure(point):
        return 0.0 if point is None else clamp(max(0, .82 - point.y) / .5 + abs(point.x - .5), 0, 1)
    return ShapeSummary(
        left_cover=rest_cover(points, .16), centre_cover=rest_cover(points, .50),
        right_cover=rest_cover(points, .84),
        attacking_support=mean(occupation(points, x, .26) for x in (.24, .50, .76)),
        connection=clamp(1 - mean(nearest) / .4, 0, 1),
        defensive_width=max((p[0] for p in defense), default=.5) - min((p[0] for p in defense), default=.5),
        attacking_width=max((p[0] for p in attack), default=.5) - min((p[0] for p in attack), default=.5),
        block_left_cover=occupation(off_points, .16, .80),
        block_centre_cover=occupation(off_points, .50, .80),
        block_right_cover=occupation(off_points, .84, .80),
        screen_control=mean(occupation(off_points, x, .55) for x in (.24, .50, .76)),
        keeper_exposure=max(exposure(keeper_off), .45 * exposure(keeper_on)),
        keeper_support=0 if keeper_on is None else clamp((.9 - keeper_on.y) / .4, 0, 1),
    )
