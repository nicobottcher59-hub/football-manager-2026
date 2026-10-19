"""TS-19 tactical consumers for the compact (non-spatial) match engine.

All adjustments are bounded, seeded action probabilities or opportunity shares.
They do not edit attributes, OVR or ACT. A high setting is a tradeoff, not a
universal upgrade. Geometry is estimated occupation, not a measured heatmap.
"""
from __future__ import annotations

from dataclasses import dataclass
from statistics import mean

from football_manager.domain.enums import Position
from football_manager.domain.tactical_instructions import (
    PlayerInstructions, TargetKind, CrossType,
)
from football_manager.domain.tactical_geometry import (
    ShapeSummary, shape_summary, phase_points, clamp,
)


def centered(value) -> float:
    return (float(value) - 50.0) / 50.0


def instructions(player) -> PlayerInstructions:
    return player.effective_instructions or PlayerInstructions()


def attribute(player, path: str) -> float:
    value = player.attributes
    for part in path.split('.'):
        value = getattr(value, part)
        if value is None:
            return 50.0
    return float(value)


@dataclass(frozen=True, slots=True)
class TacticalFeatures:
    enabled: bool = False
    defense_midfield_gap: float = 0.0
    midfield_attack_gap: float = 0.0
    switch_play: float = 0.0
    central_focus: float = 0.0
    overlap: float = 0.0
    long_shots: float = 0.0
    keeper_release: float = 0.0
    defensive_width: float = 0.0
    midfield_width: float = 0.0
    forward_width: float = 0.0
    force_direction: str = 'neutral'
    marking_style: str = 'zonal'
    dribble: float = 0.0
    player_crosses: float = 0.0
    shooting: float = 0.0
    pass_risk: float = 0.0
    hold_up: float = 0.0
    attack_space: float = 0.0
    free_attack: float = 0.0
    free_defense: float = 0.0
    wide_runners: float = 0.0
    technical_escape: float = 65.0
    defensive_marking: float = 65.0
    mobility: float = 65.0
    shape: ShapeSummary = ShapeSummary()


def build_tactical_features(team) -> TacticalFeatures:
    ip, op = team.tactic.team_instructions.in_possession, team.tactic.team_instructions.out_of_possession
    tr = team.tactic.team_instructions.transition
    players = [p for p in team.starters if p.assigned_position is not Position.GK]
    def avg(field):
        return mean(centered(getattr(instructions(p), field)) for p in players) if players else 0.0
    defenders = [p for p in players if p.assigned_position in
                 (Position.RB, Position.LB, Position.RCB, Position.LCB, Position.CB, Position.DM, Position.RWB, Position.LWB)]
    return TacticalFeatures(
        enabled=True, defense_midfield_gap=centered(ip.defense_midfield_gap),
        midfield_attack_gap=centered(ip.midfield_attack_gap), switch_play=centered(ip.switch_play),
        central_focus=centered(ip.central_focus), overlap=centered(ip.overlap_frequency),
        long_shots=centered(ip.long_shot_frequency),
        keeper_release=centered(tr.goalkeeper_release_speed) if tr.after_win.value in ('counter', 'direct', 'expand') else 0.0,
        defensive_width=centered(op.defensive_line_width), midfield_width=centered(op.midfield_width),
        forward_width=centered(op.attacking_line_width), force_direction=op.force_direction.value,
        marking_style=op.marking_style.value,
        dribble=avg('dribbling_frequency'), player_crosses=avg('crossing_frequency'),
        shooting=avg('shooting_frequency'), pass_risk=avg('passing_risk'),
        hold_up=avg('hold_up_play'), attack_space=avg('attack_space'),
        free_attack=sum(instructions(p).in_possession_position.value == 'free' for p in players) / max(1, len(players)),
        free_defense=sum(instructions(p).out_of_possession_position.value == 'free' for p in players) / max(1, len(players)),
        wide_runners=sum(p.assigned_position in (Position.RB, Position.LB, Position.RWB, Position.LWB) for p in players) / 2,
        technical_escape=mean((attribute(p, 'technical.dribbling') + attribute(p, 'mental.decisions')) / 2 for p in players) if players else 65,
        defensive_marking=mean((attribute(p, 'technical.marking') + attribute(p, 'mental.positioning')) / 2 for p in defenders) if defenders else 40,
        mobility=mean((attribute(p, 'physical.acceleration') + attribute(p, 'mental.off_the_ball')) / 2 for p in players) if players else 65,
        shape=shape_summary(team.tactic),
    )


def possession_edge(a: TacticalFeatures, d: TacticalFeatures) -> float:
    if not a.enabled:
        return 0.0
    spacing_cost = abs(a.defense_midfield_gap) * .35 + abs(a.midfield_attack_gap) * .25
    edge = .75 * a.hold_up - .55 * a.dribble - .55 * a.pass_risk - .4 * a.keeper_release
    edge -= spacing_cost
    edge += (a.shape.connection - .40) * 2.0 + .25 * a.shape.keeper_support
    if d.enabled:
        edge -= .7 * (d.shape.screen_control - .65)
        edge += a.switch_play * max(0, -d.midfield_width) * .6
        edge -= a.central_focus * max(0, -d.midfield_width) * .4
        if d.marking_style in ('man', 'mixed'):
            strength = 1 if d.marking_style == 'man' else .5
            edge -= strength * (d.defensive_marking - a.mobility) / 50
            edge += strength * a.free_attack * .5
    return clamp(edge, -2.0, 2.0)


def defensive_route_cover(a: TacticalFeatures, d: TacticalFeatures) -> float:
    """Meet the requested attacking channel against the actual defensive block.

    Rest defence is assessed separately from the in-possession shape. This
    contribution uses out-of-possession targets, so moving defensive markers
    cannot be merely cosmetic. A narrower block helps centrally at a cost on
    the flanks; no extra OVR/ACT or familiarity penalty is introduced.
    """
    central_share = clamp(.5 + .3 * a.central_focus, .2, .8)
    flank_cover = (d.shape.block_left_cover + d.shape.block_right_cover) / 2
    return central_share * d.shape.block_centre_cover + (1 - central_share) * flank_cover


def shot_edge(a: TacticalFeatures, d: TacticalFeatures, directness: float = 50) -> float:
    if not a.enabled:
        return 0.0
    edge = .65 * a.long_shots + .45 * a.shooting + .25 * a.dribble
    edge += .35 * a.attack_space + .30 * a.overlap * min(1, a.wide_runners)
    edge += .20 * a.keeper_release * max(0, centered(directness))
    edge += (a.shape.attacking_support - .70) * 2.0
    if d.enabled:
        outside_gap = 1 - (d.shape.left_cover + d.shape.right_cover) / 2
        edge += .85 * (.70 - defensive_route_cover(a, d))
        edge += .35 * d.shape.keeper_exposure - .45 * (d.shape.screen_control - .60)
        edge += .8 * a.switch_play * outside_gap
        edge += a.central_focus * (.45 * d.midfield_width + .45 * d.defensive_width)
        edge += (d.shape.centre_cover - (d.shape.left_cover + d.shape.right_cover) / 2) * (1 - a.central_focus) * .4
        edge += max(0, centered(directness)) * outside_gap * 1.2
        # Overlaps consume rest defence; the opponent may exploit the space.
        edge += max(0, d.overlap) * min(1, d.wide_runners) * max(0, centered(directness)) * .45
        edge += .2 * abs(d.forward_width - d.midfield_width) + .4 * d.free_defense
        if d.force_direction == 'inside':
            edge += .35 * (1 - d.shape.centre_cover) - .25 * max(0, -a.central_focus)
        elif d.force_direction == 'outside':
            edge += .35 * outside_gap - .25 * max(0, a.central_focus)
        elif d.force_direction == 'weak_foot':
            edge -= clamp((d.defensive_marking - a.technical_escape + 35) / 100, 0, .6) * .35
        if d.marking_style in ('man', 'mixed'):
            strength = 1 if d.marking_style == 'man' else .5
            edge += strength * ((a.mobility - d.defensive_marking) / 70 + .35 * a.free_attack)
    return clamp(edge, -1.7, 1.7)


def quality_edge(a: TacticalFeatures, d: TacticalFeatures) -> float:
    if not a.enabled:
        return 0.0
    edge = -.006 * a.long_shots - .004 * a.shooting
    edge += .006 * a.attack_space - .003 * a.hold_up + .003 * a.free_attack
    edge += .006 * a.dribble * (a.technical_escape - 60) / 40
    edge -= .003 * abs(a.defense_midfield_gap - a.midfield_attack_gap)
    if d.enabled:
        edge += .005 * a.switch_play * max(0, -d.defensive_width)
        edge += .005 * a.central_focus * d.defensive_width
        edge += .006 * (1 - min(d.shape.left_cover, d.shape.right_cover))
        edge += .004 * d.free_defense
        edge += .008 * (.70 - defensive_route_cover(a, d)) + .028 * d.shape.keeper_exposure
    return clamp(edge, -.018, .018)


def pass_completion_edge(a: TacticalFeatures, d: TacticalFeatures) -> float:
    if not a.enabled:
        return 0.0
    value = -.012 * a.pass_risk - .006 * a.switch_play - .007 * a.dribble
    value += .007 * a.hold_up - .004 * a.keeper_release
    value -= .004 * abs(a.defense_midfield_gap) + .004 * abs(a.midfield_attack_gap)
    if d.enabled:
        value -= .004 * abs(d.forward_width - d.midfield_width)
        value += .004 * a.central_focus * d.midfield_width
    return clamp(value, -.035, .035)


def target_matches(target, player) -> bool:
    if target is None:
        return False
    if target.kind is TargetKind.PLAYER:
        return player.player_id == target.target_id
    if target.kind is TargetKind.POSITION:
        return player.assigned_position is not None and player.assigned_position.value == target.target_id
    if target.kind is TargetKind.ROLE:
        return player.role_id == target.target_id
    return False


def targeted_pressure(player, defenders) -> float:
    """Targets only affect present opponents; never select a missing player."""
    pressure = 0.0
    for marker in defenders:
        ins = instructions(marker)
        if target_matches(ins.marking, player):
            skill = (attribute(marker, 'technical.marking') + attribute(marker, 'mental.positioning')) / 200
            pressure += .08 * skill
        if target_matches(ins.pressing_target, player):
            skill = (attribute(marker, 'mental.work_rate') + attribute(marker, 'physical.acceleration')) / 200
            pressure += .06 * skill * (0.6 + float(ins.pressing_intensity) / 125)
    return clamp(pressure, 0.0, .20)


def shooter_factor(player, team, defenders=(), points=None) -> float:
    ins = instructions(player)
    value = 1 + .55 * centered(ins.shooting_frequency) + .20 * centered(ins.attack_space)
    value += .10 * centered(ins.dribbling_frequency) - .12 * centered(ins.hold_up_play)
    if player.assigned_position is not Position.GK:
        points = points if points is not None else phase_points(team.tactic, 'in_possession')
        x, y = points.get(player.assigned_slot_id, (.5, .5))
        focus = centered(team.tactic.team_instructions.in_possession.central_focus)
        value *= 1 + focus * (.15 if abs(x - .5) < .22 else -.15)
        explicit = any(p.slot_id == player.assigned_slot_id for s in team.tactic.phase_shapes
                       if s.phase == 'in_possession' for p in s.points)
        if explicit:
            value *= clamp((1 - y) / .55, .35, 1.6)
    value *= 1 - targeted_pressure(player, defenders)
    return clamp(value, .15, 2.5)


def creator_factor(player) -> float:
    ins = instructions(player)
    # More creative risk yields more potential assists but lowers pass completion.
    return clamp(1 + .32 * centered(ins.passing_risk) + .22 * centered(ins.crossing_frequency)
                 + .10 * centered(ins.hold_up_play) - .10 * centered(ins.shooting_frequency), .35, 1.8)


def pass_share_factor(player) -> float:
    ins = instructions(player)
    return clamp(1 + .22 * centered(ins.hold_up_play) - .16 * centered(ins.dribbling_frequency)
                 - .10 * centered(ins.attack_space), .5, 1.5)


def action_quality(xg, shooter, creator, attacker, defenders, random):
    """Resolve shot construction, including explicit long shots and cross types.

    Every route has an independent RNG namespace, so changing a control never
    inserts unrelated random draws into the rest of the match.
    """
    ins = instructions(shooter)
    team_ins = attacker.tactic.team_instructions.in_possession
    long_probability = clamp(.15 + .10 * centered(team_ins.long_shot_frequency)
                             + .04 * centered(ins.shooting_frequency), .02, .35)
    long_shot = random.fork('long-shot').random() < long_probability
    if long_shot:
        ability = (attribute(shooter, 'technical.long_shots') + attribute(shooter, 'technical.shot_power')) / 2
        xg = clamp(xg * .48 + (ability - 65) * .0003, .012, .13)
    else:
        dribble = centered(ins.dribbling_frequency)
        if random.fork('dribble').random() < clamp(.18 + .15 * dribble, .03, .4):
            defense = mean(attribute(p, 'technical.tackling') for p in defenders) if defenders else 50
            quality = (attribute(shooter, 'technical.dribbling') + attribute(shooter, 'physical.acceleration')) / 2
            xg *= clamp(1 + (quality - defense) / 240, .80, 1.20)
        if creator is not None:
            cins = instructions(creator)
            cross_probability = clamp(.25 + .13 * centered(team_ins.crossing_frequency)
                                      + .12 * centered(cins.crossing_frequency)
                                      - .08 * centered(team_ins.central_focus), .03, .60)
            if random.fork('cross').random() < cross_probability:
                kind = cins.cross_type
                aerial_defense = mean((attribute(p, 'technical.heading') + attribute(p, 'physical.jumping_reach')) / 2
                                      for p in defenders if p.assigned_position is not Position.GK) if len(defenders) > 1 else 65
                if kind in (CrossType.HIGH, CrossType.EARLY):
                    skill = (attribute(shooter, 'technical.heading') + attribute(shooter, 'physical.jumping_reach')) / 2
                    xg *= clamp(.94 + (skill - aerial_defense) / 170, .72, 1.20)
                    if kind is CrossType.EARLY:
                        xg *= .94
                elif kind in (CrossType.LOW, CrossType.CUTBACK):
                    skill = (attribute(shooter, 'mental.off_the_ball') + attribute(creator, 'technical.crossing')) / 2
                    xg *= clamp(1.0 + (skill - 65) / 240, .85, 1.15)
                    if kind is CrossType.CUTBACK:
                        # Reaching the byline takes technique; it is not a free xG upgrade.
                        xg *= clamp(.92 + (attribute(creator, 'technical.dribbling') - 50) / 250, .8, 1.1)
                elif kind is CrossType.BYLINE:
                    xg *= clamp(.92 + (attribute(creator, 'physical.acceleration') - 50) / 230, .80, 1.12)
    xg *= 1 - targeted_pressure(shooter, defenders)
    return clamp(xg, .005, .65), long_shot
