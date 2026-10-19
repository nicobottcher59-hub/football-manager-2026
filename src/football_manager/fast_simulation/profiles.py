from __future__ import annotations

from dataclasses import dataclass
from .tactical_effects import TacticalFeatures, build_tactical_features

from football_manager.domain import PlayerMatchSnapshot, Position, TeamMatchSnapshot


_ATTACK_POS_WEIGHT = {
    Position.GK: 0.02,
    Position.RB: 0.55,
    Position.RCB: 0.20,
    Position.CB: 0.18,
    Position.LCB: 0.20,
    Position.LB: 0.55,
    Position.RWB: 0.80,
    Position.LWB: 0.80,
    Position.DM: 0.55,
    Position.RCM: 0.90,
    Position.CM: 0.95,
    Position.LCM: 0.90,
    Position.AM: 1.30,
    Position.RW: 1.45,
    Position.LW: 1.45,
    Position.SS: 1.50,
    Position.ST: 1.60,
}

_CONTROL_POS_WEIGHT = {
    Position.GK: 0.25,
    Position.RB: 0.85,
    Position.RCB: 0.70,
    Position.CB: 0.70,
    Position.LCB: 0.70,
    Position.LB: 0.85,
    Position.RWB: 0.95,
    Position.LWB: 0.95,
    Position.DM: 1.35,
    Position.RCM: 1.45,
    Position.CM: 1.50,
    Position.LCM: 1.45,
    Position.AM: 1.30,
    Position.RW: 0.95,
    Position.LW: 0.95,
    Position.SS: 0.90,
    Position.ST: 0.65,
}

_DEFENSE_POS_WEIGHT = {
    Position.GK: 0.0,
    Position.RB: 1.30,
    Position.RCB: 1.60,
    Position.CB: 1.65,
    Position.LCB: 1.60,
    Position.LB: 1.30,
    Position.RWB: 1.05,
    Position.LWB: 1.05,
    Position.DM: 1.40,
    Position.RCM: 0.80,
    Position.CM: 0.80,
    Position.LCM: 0.80,
    Position.AM: 0.40,
    Position.RW: 0.35,
    Position.LW: 0.35,
    Position.SS: 0.25,
    Position.ST: 0.20,
}


@dataclass(frozen=True, slots=True)
class FastTeamProfile:
    club_id: str
    overall: float
    current: float
    attack: float
    control: float
    defense: float
    goalkeeping: float
    set_pieces: float
    discipline: float
    tactical_execution: float
    possession_style: float
    pressing: float
    directness: float
    defensive_depth: float
    tempo: float
    width: float
    risk: float
    defensive_compactness: float
    central_protection: float
    cross_tolerance: float
    crossing_frequency: float
    defensive_aggression: float
    # Match-only controls. Defaults retain existing manually constructed profiles.
    offside_trap: bool = False
    time_wasting: float = 0.0
    urgency_when_trailing: float = 75.0
    risk_when_leading: float = 50.0
    tactical_features: TacticalFeatures = TacticalFeatures()


def _mean(values: list[float], *, fallback: float = 65.0) -> float:
    if not values:
        return fallback
    return sum(values) / len(values)


def _attr(player: PlayerMatchSnapshot, path: str) -> float:
    current: object = player.attributes
    for part in path.split("."):
        current = getattr(current, part)
        if current is None:
            return 50.0
    return float(current)


def _attr_mean(player: PlayerMatchSnapshot, *paths: str) -> float:
    return _mean([_attr(player, path) for path in paths])


def _execution_scaled_action_quality(
    player: PlayerMatchSnapshot,
    action_quality: float,
) -> float:
    """Translate raw attributes into usable quality in the current context.

    ACT already captures condition, confidence and positional/tactical familiarity.
    Raw attributes still shape *which* actions a player is good at, but a player
    operating wildly outside his context should not be able to express 100% of
    those attributes.  This prevents a striker parked at centre-back from keeping
    an almost-normal defensive unit merely because his generic attributes are high.
    """

    structural = max(1.0, player.overall_rating)
    ratio = player.current_rating / structural
    if ratio >= 1.0:
        execution = min(1.05, 1.0 + (ratio - 1.0) * 0.35)
    else:
        execution = max(0.45, ratio)
    return action_quality * execution


def _weighted_unit(
    players: tuple[PlayerMatchSnapshot, ...],
    *,
    position_weights: dict[Position, float],
    action_paths: tuple[str, ...],
) -> float:
    weighted = 0.0
    total = 0.0
    for player in players:
        position = player.assigned_position
        if position is None:
            continue
        weight = position_weights.get(position, 0.5)
        action_quality = _attr_mean(player, *action_paths)
        usable_action_quality = _execution_scaled_action_quality(player, action_quality)
        contribution = 0.60 * player.current_rating + 0.40 * usable_action_quality
        weighted += contribution * weight
        total += weight
    return weighted / total if total > 0.0 else 50.0


def _emergency_goalkeeper_quality(keeper: PlayerMatchSnapshot) -> float:
    """Estimate a non-GK's emergency shot-stopping level.

    Outfield technique is not a substitute for handling, reflexes or one-on-ones.
    Athletic/mental traits provide a small floor, but an outfielder with no keeper
    attributes must remain dramatically worse than a specialist goalkeeper.
    """

    support = _mean(
        [
            _attr(keeper, "physical.agility"),
            _attr(keeper, "physical.jumping_reach"),
            _attr(keeper, "mental.anticipation"),
            _attr(keeper, "mental.concentration"),
            _attr(keeper, "mental.composure"),
            _attr(keeper, "mental.bravery"),
        ]
    )
    familiarity = keeper.familiarity.position_score(Position.GK)
    specialist = 6.0 + support * 0.30 + familiarity * 0.05
    specialist = max(8.0, min(38.0, specialist))
    return 0.15 * keeper.current_rating + 0.85 * specialist


def _goalkeeper_quality(team: TeamMatchSnapshot) -> float:
    keepers = [player for player in team.starters if player.assigned_position is Position.GK]
    if not keepers:
        return 20.0
    keeper = keepers[0]
    goalkeeping = keeper.attributes.goalkeeping
    if goalkeeping is None:
        if keeper.original_position is not Position.GK:
            return _emergency_goalkeeper_quality(keeper)
        # Compatibility for old fixtures whose *real* goalkeeper predates the
        # specialist attribute group.  Do not apply this fallback to outfielders.
        specialist = keeper.attributes.outfield_average()
        current = specialist
    else:
        specialist = _mean(
            [
                float(goalkeeping.reflexes),
                float(goalkeeping.handling),
                float(goalkeeping.one_on_ones),
                float(goalkeeping.aerial_reach),
                float(goalkeeping.command_of_area),
                float(goalkeeping.goalkeeper_positioning),
            ]
        )
        current = keeper.current_rating
    return 0.55 * current + 0.45 * specialist


def _tactical_execution(team: TeamMatchSnapshot) -> float:
    values: list[float] = []
    for player in team.starters:
        ctx = player.role_context
        if ctx is None:
            values.append(65.0)
            continue
        values.append(
            0.25 * ctx.position_familiarity
            + 0.30 * ctx.role_familiarity
            + 0.45 * ctx.tactic_familiarity
        )
    return _mean(values)


def build_fast_team_profile(team: TeamMatchSnapshot) -> FastTeamProfile:
    starters = team.starters
    overall = _mean([player.overall_rating for player in starters])
    current = _mean([player.current_rating for player in starters])

    attack = _weighted_unit(
        starters,
        position_weights=_ATTACK_POS_WEIGHT,
        action_paths=(
            "technical.finishing",
            "technical.first_touch",
            "technical.technique",
            "technical.dribbling",
            "technical.crossing",
            "mental.off_the_ball",
            "mental.composure",
            "mental.anticipation",
            "physical.acceleration",
            "physical.pace",
        ),
    )
    control = _weighted_unit(
        starters,
        position_weights=_CONTROL_POS_WEIGHT,
        action_paths=(
            "technical.passing",
            "technical.first_touch",
            "technical.technique",
            "mental.vision",
            "mental.decisions",
            "mental.composure",
            "mental.teamwork",
            "mental.tactical_intelligence",
        ),
    )
    defense = _weighted_unit(
        starters,
        position_weights=_DEFENSE_POS_WEIGHT,
        action_paths=(
            "technical.tackling",
            "technical.marking",
            "technical.heading",
            "mental.positioning",
            "mental.anticipation",
            "mental.concentration",
            "mental.teamwork",
            "physical.strength",
            "physical.pace",
        ),
    )

    outfield = [player for player in starters if player.assigned_position is not Position.GK]
    set_pieces = _mean(
        [
            0.45 * _attr(player, "technical.set_pieces")
            + 0.20 * _attr(player, "technical.crossing")
            + 0.15 * _attr(player, "technical.penalties")
            + 0.10 * _attr(player, "technical.heading")
            + 0.10 * _attr(player, "physical.jumping_reach")
            for player in outfield
        ]
    )
    discipline = _mean(
        [
            0.40 * _attr(player, "mental.composure")
            + 0.30 * _attr(player, "mental.decisions")
            + 0.30 * _attr(player, "mental.concentration")
            - max(0.0, _attr(player, "mental.aggression") - 65.0) * 0.20
            for player in outfield
        ]
    )

    style = team.tactic.style
    instructions = team.tactic.team_instructions
    return FastTeamProfile(
        club_id=team.club_id,
        overall=overall,
        current=current,
        attack=attack,
        control=control,
        defense=defense,
        goalkeeping=_goalkeeper_quality(team),
        set_pieces=set_pieces,
        discipline=discipline,
        tactical_execution=_tactical_execution(team),
        possession_style=style.possession,
        pressing=style.pressing,
        directness=style.directness,
        defensive_depth=style.defensive_depth,
        tempo=style.tempo,
        width=style.width,
        risk=style.risk,
        defensive_compactness=style.defensive_compactness,
        central_protection=style.central_protection,
        cross_tolerance=style.cross_tolerance,
        crossing_frequency=float(instructions.in_possession.crossing_frequency),
        defensive_aggression=float(instructions.out_of_possession.defensive_aggression),
        offside_trap=instructions.out_of_possession.offside_trap,
        time_wasting=float(instructions.game_management.time_wasting),
        urgency_when_trailing=float(instructions.game_management.urgency_when_trailing),
        risk_when_leading=float(instructions.game_management.risk_when_leading),
        tactical_features=build_tactical_features(team),
    )
