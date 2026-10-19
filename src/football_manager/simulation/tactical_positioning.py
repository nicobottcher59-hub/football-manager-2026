from __future__ import annotations

from dataclasses import dataclass, replace
from enum import StrEnum
from football_manager.domain import (
    InPossessionPosition,
    MatchSnapshot,
    OutOfPossessionPosition,
    PlayerInstructions,
    Position,
    TeamMatchSnapshot,
    TacticMatchSnapshot,
)

from .geometry import Vector2
from football_manager.domain.tactical_shapes import phase_target
from .match_context_effects import MatchContextSystem
from .positioning_anchors import normalized_anchor
from .spatial_state import MatchState, PlayerAgentState, TacticalPhase, TeamSide


class TacticalLine(StrEnum):
    GOALKEEPER = "goalkeeper"
    DEFENCE = "defence"
    MIDFIELD = "midfield"
    ATTACK = "attack"


@dataclass(frozen=True, slots=True)
class TacticalMovementConfig:
    base_reposition_speed_mps: float = 4.4
    arrival_radius_m: float = 0.20
    pitch_margin_m: float = 1.5

    def __post_init__(self) -> None:
        if self.base_reposition_speed_mps <= 0:
            raise ValueError("base reposition speed must be positive")
        if self.arrival_radius_m < 0:
            raise ValueError("arrival radius cannot be negative")
        if self.pitch_margin_m < 0:
            raise ValueError("pitch margin cannot be negative")


@dataclass(frozen=True, slots=True)
class TacticalTarget:
    agent_id: str
    side: TeamSide
    phase: TacticalPhase
    line: TacticalLine
    location: Vector2


@dataclass(frozen=True, slots=True)
class TeamShapeMetrics:
    side: TeamSide
    phase: TacticalPhase
    defensive_width_m: float
    midfield_width_m: float
    attacking_width_m: float
    defense_midfield_gap_m: float
    midfield_attack_gap_m: float


def tactical_line(position: Position) -> TacticalLine:
    if position is Position.GK:
        return TacticalLine.GOALKEEPER
    if position in {
        Position.RB,
        Position.RCB,
        Position.CB,
        Position.LCB,
        Position.LB,
        Position.RWB,
        Position.LWB,
    }:
        return TacticalLine.DEFENCE
    if position in {Position.DM, Position.RCM, Position.CM, Position.LCM, Position.AM}:
        return TacticalLine.MIDFIELD
    return TacticalLine.ATTACK


def _line_width_level(team: TeamMatchSnapshot, line: TacticalLine, phase: TacticalPhase) -> float:
    if phase is TacticalPhase.IN_POSSESSION:
        instructions = team.tactic.team_instructions.in_possession
    else:
        instructions = team.tactic.team_instructions.out_of_possession

    if line is TacticalLine.DEFENCE:
        return float(instructions.defensive_line_width)
    if line is TacticalLine.MIDFIELD:
        return float(instructions.midfield_width)
    if line is TacticalLine.ATTACK:
        return float(instructions.attacking_line_width)
    return 50.0


def _width_scale(level: float) -> float:
    # Normal = 1.0. Extreme settings alter the base formation without allowing
    # lines to become unrealistically flat against the touchline.
    return 0.65 + (level / 100.0) * 0.70


def _line_centre_from_anchors(line: TacticalLine) -> float:
    positions: dict[TacticalLine, tuple[Position, ...]] = {
        TacticalLine.GOALKEEPER: (Position.GK,),
        TacticalLine.DEFENCE: (
            Position.RB,
            Position.RCB,
            Position.CB,
            Position.LCB,
            Position.LB,
            Position.RWB,
            Position.LWB,
        ),
        TacticalLine.MIDFIELD: (Position.DM, Position.RCM, Position.CM, Position.LCM, Position.AM),
        TacticalLine.ATTACK: (Position.RW, Position.LW, Position.SS, Position.ST),
    }
    xs = [normalized_anchor(position)[0] for position in positions[line]]
    return sum(xs) / len(xs)


_BASE_LINE_CENTRES = {
    TacticalLine.GOALKEEPER: _line_centre_from_anchors(TacticalLine.GOALKEEPER),
    TacticalLine.DEFENCE: _line_centre_from_anchors(TacticalLine.DEFENCE),
    TacticalLine.MIDFIELD: _line_centre_from_anchors(TacticalLine.MIDFIELD),
    TacticalLine.ATTACK: _line_centre_from_anchors(TacticalLine.ATTACK),
}


def _gap_adjustment_m(level: float) -> float:
    # Normal preserves formation spacing. Extremes can add/subtract roughly six
    # metres between adjacent lines.
    return ((level - 50.0) / 50.0) * 6.0


def _out_of_possession_gap_m(level: float, compactness: float) -> float:
    requested = 7.0 + (level / 100.0) * 12.0
    compactness_factor = 1.25 - (compactness / 100.0) * 0.50
    return requested * compactness_factor


def _apply_horizontal_shape(
    normalized_y: float,
    *,
    width_level: float,
    horizontal_compactness: float | None = None,
    protect_centre: float | None = None,
    cross_tolerance: float | None = None,
) -> float:
    scale = _width_scale(width_level)
    if horizontal_compactness is not None:
        scale *= 1.0 - ((horizontal_compactness - 50.0) / 50.0) * 0.18
    if protect_centre is not None and protect_centre > 50.0:
        scale *= 1.0 - ((protect_centre - 50.0) / 50.0) * 0.15
    if cross_tolerance is not None and cross_tolerance > 50.0:
        scale *= 1.0 - ((cross_tolerance - 50.0) / 50.0) * 0.10
    return 0.5 + (normalized_y - 0.5) * scale


def _clamp_normalized(value: float, margin_norm: float) -> float:
    return min(max(value, margin_norm), 1.0 - margin_norm)


def _instruction_for(agent: PlayerAgentState) -> PlayerInstructions:
    return agent.player.effective_instructions or PlayerInstructions()


def _apply_in_possession_role(
    x_m: float,
    y_m: float,
    *,
    agent: PlayerAgentState,
    pitch_length_m: float,
    pitch_width_m: float,
) -> tuple[float, float]:
    instructions = _instruction_for(agent)
    command = instructions.in_possession_position

    centre_y = pitch_width_m / 2.0
    midfield_x = _BASE_LINE_CENTRES[TacticalLine.MIDFIELD] * pitch_length_m
    defensive_x = _BASE_LINE_CENTRES[TacticalLine.DEFENCE] * pitch_length_m

    if command is InPossessionPosition.WIDE:
        y_m = centre_y + (y_m - centre_y) * 1.18
    elif command is InPossessionPosition.INSIDE:
        y_m = centre_y + (y_m - centre_y) * 0.55
    elif command is InPossessionPosition.MIDFIELD:
        x_m = max(x_m, midfield_x)
        y_m = centre_y + (y_m - centre_y) * 0.45
    elif command is InPossessionPosition.ADVANCE:
        x_m += 7.0
    elif command is InPossessionPosition.DROP_DEEP:
        line = tactical_line(agent.assigned_position)
        if line is TacticalLine.MIDFIELD:
            # Half-backs and similar midfield roles can drop into the first line.
            x_m = min(x_m - 6.0, defensive_x + 4.0)
        else:
            # False nines/deep forwards drop toward midfield, not into defence.
            x_m -= 8.0

    # Forward-run instructions alter how aggressively the role occupies depth.
    x_m += ((float(instructions.forward_runs) - 50.0) / 50.0) * 4.0
    return x_m, y_m


def _apply_out_of_possession_role(
    x_m: float,
    y_m: float,
    *,
    agent: PlayerAgentState,
) -> tuple[float, float]:
    instructions = _instruction_for(agent)
    command = instructions.out_of_possession_position

    if command is OutOfPossessionPosition.STEP_UP:
        x_m += 4.5
    elif command is OutOfPossessionPosition.DROP:
        x_m -= 4.5

    line = tactical_line(agent.assigned_position)
    if line is TacticalLine.ATTACK:
        # High tracking asks attacking players to recover closer to midfield.
        x_m -= max(0.0, (float(instructions.defensive_tracking) - 50.0) / 50.0) * 5.0

    return x_m, y_m


class TacticalPositioningSystem:
    """Translate frozen tactics into spatial targets and bounded movement.

    Phase 5.1 does not make football decisions. It only determines where each
    player should try to be for the current possession phase and moves agents
    smoothly toward those locations.
    """

    def __init__(
        self,
        snapshot: MatchSnapshot,
        config: TacticalMovementConfig | None = None,
        context: MatchContextSystem | None = None,
    ) -> None:
        self.snapshot = snapshot
        self.config = config or TacticalMovementConfig()
        self.context = context or MatchContextSystem(snapshot)
        self._teams = {
            TeamSide.HOME: snapshot.home_team,
            TeamSide.AWAY: snapshot.away_team,
        }
        self._runtime_tactics = {
            TeamSide.HOME: snapshot.home_team.tactic,
            TeamSide.AWAY: snapshot.away_team.tactic,
        }

    def set_runtime_tactic(self, side: TeamSide, tactic: TacticMatchSnapshot) -> None:
        side = TeamSide(side)
        if tactic.formation.slot_ids != self._runtime_tactics[side].formation.slot_ids:
            raise ValueError("runtime formation changes must preserve tactical slot IDs")
        self._runtime_tactics[side] = tactic

    def phase_for_side(self, state: MatchState, side: TeamSide) -> TacticalPhase:
        if state.possession.team_side is side:
            return TacticalPhase.IN_POSSESSION
        return TacticalPhase.OUT_OF_POSSESSION

    def target_for_agent(self, state: MatchState, agent: PlayerAgentState) -> TacticalTarget:
        team = self._teams[agent.side]
        runtime_tactic = self._runtime_tactics[agent.side]
        phase = self.phase_for_side(state, agent.side)
        line = tactical_line(agent.assigned_position)
        x_norm, y_norm = normalized_anchor(agent.assigned_position)

        if phase is TacticalPhase.IN_POSSESSION:
            target = self._in_possession_target(
                team,
                agent,
                line,
                x_norm=x_norm,
                y_norm=y_norm,
                state=state,
            )
        else:
            target = self._out_of_possession_target(
                team,
                agent,
                line,
                x_norm=x_norm,
                y_norm=y_norm,
                state=state,
            )

        explicit = phase_target(runtime_tactic.phase_shapes, phase.value, agent.slot_id)
        if explicit is not None:
            # Explicit manager targets already describe the requested phase.
            # Do not reapply role offsets and do not mirror more than once.
            target = Vector2((1 - explicit.y) * state.pitch.length_m, explicit.x * state.pitch.width_m)
        if agent.side is TeamSide.AWAY:
            target = state.pitch.mirror(target)

        return TacticalTarget(
            agent_id=agent.agent_id,
            side=agent.side,
            phase=phase,
            line=line,
            location=target,
        )

    def targets(self, state: MatchState) -> dict[str, TacticalTarget]:
        return {
            agent.agent_id: self.target_for_agent(state, agent)
            for agent in state.active_players
        }

    def update_velocities(
        self,
        state: MatchState,
        *,
        excluded_agent_ids: frozenset[str] = frozenset(),
    ) -> None:
        self.refresh_targets(state)
        dt = state.clock.tick_seconds
        for agent in state.players.values():
            if not agent.is_active:
                continue

            if agent.agent_id in excluded_agent_ids:
                continue

            assert agent.tactical_target is not None
            delta = agent.tactical_target - agent.location
            distance = delta.magnitude
            if distance <= self.config.arrival_radius_m:
                agent.velocity = Vector2.zero()
                continue

            speed = self._reposition_speed(agent)
            # Arrival cap avoids overshooting the target on a fixed timestep.
            speed = min(speed, distance / dt)
            agent.velocity = delta.normalized().scale(speed)

    def refresh_targets(self, state: MatchState) -> None:
        """Refresh tactical references without prescribing player movement.

        Phase 5.1 used the tactical target as both a structural reference and the
        literal destination for every player.  That was useful while testing the
        shape system in isolation, but the integrated Match Engine now needs
        formation coordinates to behave as *anchors*, not rails.  The organic
        movement layer consumes these references and can temporarily move a
        player far away from them for an overlap, a drop, a run in behind, etc.

        ``update_velocities`` remains available for the Phase 5.1 tests/debug
        tools that intentionally want direct movement toward the tactical shape.
        """

        for agent in state.players.values():
            if not agent.is_active:
                agent.velocity = Vector2.zero()
                agent.tactical_target = None
                agent.tactical_phase = None
                continue
            target = self.target_for_agent(state, agent)
            agent.tactical_phase = target.phase
            agent.tactical_target = target.location

    def shape_metrics(self, state: MatchState, side: TeamSide) -> TeamShapeMetrics:
        side = TeamSide(side)
        targets = [
            self.target_for_agent(state, agent)
            for agent in state.active_players
            if agent.side is side
        ]
        phase = self.phase_for_side(state, side)

        def items_for(line: TacticalLine) -> list[Vector2]:
            return [item.location for item in targets if item.line is line]

        def width(line: TacticalLine) -> float:
            items = items_for(line)
            if len(items) < 2:
                return 0.0
            ys = [item.y for item in items]
            return max(ys) - min(ys)

        def mean_x(line: TacticalLine) -> float:
            items = items_for(line)
            if not items:
                return 0.0
            # Convert away orientation back to home perspective before comparing
            # vertical line gaps.
            if side is TeamSide.AWAY:
                return sum(state.pitch.length_m - item.x for item in items) / len(items)
            return sum(item.x for item in items) / len(items)

        defence_x = mean_x(TacticalLine.DEFENCE)
        midfield_x = mean_x(TacticalLine.MIDFIELD)
        attack_x = mean_x(TacticalLine.ATTACK)
        return TeamShapeMetrics(
            side=side,
            phase=phase,
            defensive_width_m=width(TacticalLine.DEFENCE),
            midfield_width_m=width(TacticalLine.MIDFIELD),
            attacking_width_m=width(TacticalLine.ATTACK),
            defense_midfield_gap_m=max(0.0, midfield_x - defence_x),
            midfield_attack_gap_m=max(0.0, attack_x - midfield_x),
        )

    def _in_possession_target(
        self,
        team: TeamMatchSnapshot,
        agent: PlayerAgentState,
        line: TacticalLine,
        *,
        x_norm: float,
        y_norm: float,
        state: MatchState,
    ) -> Vector2:
        instructions = self._runtime_tactics[agent.side].team_instructions.in_possession
        pitch = state.pitch
        margin_norm_y = self.config.pitch_margin_m / pitch.width_m
        margin_norm_x = self.config.pitch_margin_m / pitch.length_m

        runtime_team = replace(
            team,
            formation=self._runtime_tactics[agent.side].formation,
            tactic=self._runtime_tactics[agent.side],
        )
        width_level = _line_width_level(runtime_team, line, TacticalPhase.IN_POSSESSION)
        y_norm = _apply_horizontal_shape(y_norm, width_level=width_level)

        # Keep formation-specific variation within each line, then alter line gaps.
        x_m = x_norm * pitch.length_m
        if line in {TacticalLine.MIDFIELD, TacticalLine.ATTACK}:
            x_m += _gap_adjustment_m(float(instructions.defense_midfield_gap))
        if line is TacticalLine.ATTACK:
            x_m += _gap_adjustment_m(float(instructions.midfield_attack_gap))
        y_m = y_norm * pitch.width_m

        # The base formation is a reference shape, not a cage. During live play
        # the entire team must travel with the ball so a possession can actually
        # enter the opposition half/third. Work in the team's attacking
        # perspective, then mirror the final target for AWAY in target_for_agent.
        ball_local = (
            state.ball.location
            if agent.side is TeamSide.HOME
            else pitch.mirror(state.ball.location)
        )
        ball_shift_x = ball_local.x - pitch.length_m * 0.50
        line_follow = {
            TacticalLine.GOALKEEPER: 0.08,
            TacticalLine.DEFENCE: 0.30,
            TacticalLine.MIDFIELD: 0.48,
            TacticalLine.ATTACK: 0.45,
        }[line]
        x_m += ball_shift_x * line_follow

        ball_shift_y = ball_local.y - pitch.width_m * 0.50
        lateral_follow = {
            TacticalLine.GOALKEEPER: 0.06,
            TacticalLine.DEFENCE: 0.16,
            TacticalLine.MIDFIELD: 0.22,
            TacticalLine.ATTACK: 0.18,
        }[line]
        y_m += ball_shift_y * lateral_follow

        x_m, y_m = _apply_in_possession_role(
            x_m,
            y_m,
            agent=agent,
            pitch_length_m=pitch.length_m,
            pitch_width_m=pitch.width_m,
        )

        return Vector2(
            _clamp_normalized(x_m / pitch.length_m, margin_norm_x) * pitch.length_m,
            _clamp_normalized(y_m / pitch.width_m, margin_norm_y) * pitch.width_m,
        )

    def _out_of_possession_target(
        self,
        team: TeamMatchSnapshot,
        agent: PlayerAgentState,
        line: TacticalLine,
        *,
        x_norm: float,
        y_norm: float,
        state: MatchState,
    ) -> Vector2:
        instructions = self._runtime_tactics[agent.side].team_instructions.out_of_possession
        pitch = state.pitch
        margin_norm_y = self.config.pitch_margin_m / pitch.width_m
        margin_norm_x = self.config.pitch_margin_m / pitch.length_m

        runtime_team = replace(
            team,
            formation=self._runtime_tactics[agent.side].formation,
            tactic=self._runtime_tactics[agent.side],
        )
        width_level = _line_width_level(runtime_team, line, TacticalPhase.OUT_OF_POSSESSION)
        y_norm = _apply_horizontal_shape(
            y_norm,
            width_level=width_level,
            horizontal_compactness=float(instructions.horizontal_compactness),
            protect_centre=float(instructions.protect_centre),
            cross_tolerance=float(instructions.cross_tolerance),
        )

        depth_signal = (
            float(instructions.defensive_line_height) * 0.60
            + float(instructions.block_height) * 0.40
        )
        defence_x = 0.12 * pitch.length_m + (depth_signal / 100.0) * (0.28 * pitch.length_m)
        def_mid_gap = _out_of_possession_gap_m(
            float(instructions.defense_midfield_gap),
            float(instructions.vertical_compactness),
        )
        mid_att_gap = _out_of_possession_gap_m(
            float(instructions.midfield_attack_gap),
            float(instructions.vertical_compactness),
        )

        # The defensive block also travels with the ball. Without this, both
        # teams remain pinned to their starting halves while the event system
        # can still progress the ball, producing visually impossible football.
        ball_local = (
            state.ball.location
            if agent.side is TeamSide.HOME
            else pitch.mirror(state.ball.location)
        )
        block_shift = (ball_local.x - pitch.length_m * 0.50) * 0.34
        defence_x += block_shift

        if line is TacticalLine.GOALKEEPER:
            x_m = x_norm * pitch.length_m + block_shift * 0.12
        elif line is TacticalLine.DEFENCE:
            x_m = defence_x + (x_norm - _BASE_LINE_CENTRES[TacticalLine.DEFENCE]) * pitch.length_m * 0.25
        elif line is TacticalLine.MIDFIELD:
            x_m = defence_x + def_mid_gap + (x_norm - _BASE_LINE_CENTRES[TacticalLine.MIDFIELD]) * pitch.length_m * 0.25
        else:
            x_m = (
                defence_x
                + def_mid_gap
                + mid_att_gap
                + (x_norm - _BASE_LINE_CENTRES[TacticalLine.ATTACK]) * pitch.length_m * 0.25
            )

        y_m = y_norm * pitch.width_m
        y_m += (ball_local.y - pitch.width_m * 0.50) * 0.18
        x_m, y_m = _apply_out_of_possession_role(x_m, y_m, agent=agent)

        return Vector2(
            _clamp_normalized(x_m / pitch.length_m, margin_norm_x) * pitch.length_m,
            _clamp_normalized(y_m / pitch.width_m, margin_norm_y) * pitch.width_m,
        )

    def _reposition_speed(self, agent: PlayerAgentState) -> float:
        physical = agent.player.attributes.physical
        physical_score = (float(physical.pace) + float(physical.acceleration)) / 2.0
        physical_factor = 0.78 + (physical_score / 100.0) * 0.32

        role_context = agent.player.role_context
        if role_context is None:
            familiarity_score = 50.0
        else:
            familiarity_score = (
                role_context.position_familiarity
                + role_context.role_familiarity
                + role_context.tactic_familiarity
            ) / 3.0
        familiarity_factor = 0.72 + (familiarity_score / 100.0) * 0.28

        return (
            self.config.base_reposition_speed_mps
            * physical_factor
            * familiarity_factor
            * self.context.movement_speed_multiplier(agent)
        )
