from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from math import sin, pi

from football_manager.domain import (
    CrossType,
    InPossessionPosition,
    Level,
    MatchSnapshot,
    Position,
)

from .decisions import ActionType, PlayerDecision
from .geometry import Vector2
from .match_context_effects import MatchContextSystem
from .perception import PerceptionSystem
from .randomness import MatchRandom
from .spatial_state import MatchState, PlayerAgentState, TeamSide


def _clamp(value: float, minimum: float = 0.0, maximum: float = 100.0) -> float:
    return min(max(value, minimum), maximum)


def _clamp01(value: float) -> float:
    return min(max(value, 0.0), 1.0)


class RunType(StrEnum):
    FORWARD = "forward"
    OVERLAP = "overlap"
    UNDERLAP = "underlap"
    INSIDE = "inside"
    WIDE = "wide"


class CarryOutcome(StrEnum):
    COMPLETED = "completed"
    LOOSE_BALL = "loose_ball"


class DribbleOutcome(StrEnum):
    BEATS_DEFENDER = "beats_defender"
    DEFENDER_WINS = "defender_wins"
    LOOSE_BALL = "loose_ball"


class CrossOutcome(StrEnum):
    COMPLETED = "completed"
    INTERCEPTED = "intercepted"
    MISPLACED = "misplaced"
    BAD_CONTROL = "bad_control"


@dataclass(frozen=True, slots=True)
class OffBallRun:
    runner_agent_id: str
    run_type: RunType
    origin: Vector2
    target: Vector2
    priority: float
    speed_mps: float


@dataclass(frozen=True, slots=True)
class CarryProfile:
    carrier_agent_id: str
    origin: Vector2
    target: Vector2
    distance_m: float
    speed_mps: float
    control_quality: float
    retain_probability: float
    expected_seconds: float


@dataclass(slots=True)
class ActiveCarry:
    profile: CarryProfile
    started_tick: int
    elapsed_seconds: float = 0.0


@dataclass(frozen=True, slots=True)
class CarryResult:
    outcome: CarryOutcome
    carrier_agent_id: str
    started_tick: int
    resolved_tick: int
    distance_covered_m: float
    control_quality: float
    retain_probability: float
    loose_ball_location: Vector2 | None = None


@dataclass(frozen=True, slots=True)
class DribbleProfile:
    attacker_agent_id: str
    defender_agent_id: str
    attacker_quality: float
    defender_quality: float
    local_pressure: float
    forward_space: float
    success_probability: float
    clean_defender_control_probability: float
    escape_target: Vector2


@dataclass(frozen=True, slots=True)
class DribbleResult:
    outcome: DribbleOutcome
    attacker_agent_id: str
    defender_agent_id: str
    controller_agent_id: str | None
    success_probability: float
    resolved_tick: int
    escape_target: Vector2 | None = None
    loose_ball_location: Vector2 | None = None


@dataclass(frozen=True, slots=True)
class CrossExecutionProfile:
    crosser_agent_id: str
    receiver_agent_id: str
    cross_type: CrossType
    origin: Vector2
    intended_target: Vector2
    actual_target: Vector2
    distance_m: float
    execution_quality: float
    target_error_m: float
    ball_speed_mps: float
    max_height_m: float
    expected_travel_seconds: float


@dataclass(slots=True)
class ActiveCross:
    profile: CrossExecutionProfile
    started_tick: int
    elapsed_seconds: float = 0.0


@dataclass(frozen=True, slots=True)
class CrossResult:
    outcome: CrossOutcome
    crosser_agent_id: str
    intended_receiver_agent_id: str
    controller_agent_id: str | None
    cross_type: CrossType
    started_tick: int
    resolved_tick: int
    execution_quality: float
    target_error_m: float
    interception_agent_id: str | None = None
    first_touch_probability: float | None = None


@dataclass(frozen=True, slots=True)
class ProgressionConfig:
    max_off_ball_runs: int = 4
    off_ball_arrival_radius_m: float = 0.65
    carry_arrival_radius_m: float = 0.45
    dribble_engagement_radius_m: float = 5.0
    cross_interception_radius_m: float = 1.15
    cross_collection_radius_m: float = 2.35

    def __post_init__(self) -> None:
        if self.max_off_ball_runs <= 0:
            raise ValueError("max_off_ball_runs must be positive")
        for name in (
            "off_ball_arrival_radius_m",
            "carry_arrival_radius_m",
            "dribble_engagement_radius_m",
            "cross_interception_radius_m",
            "cross_collection_radius_m",
        ):
            if getattr(self, name) <= 0.0:
                raise ValueError(f"{name} must be positive")


class BallProgressionSystem:
    """Execute ball-carrying, dribbling, off-ball runs and crossing.

    Phase 5.5 intentionally builds on the earlier layers rather than bypassing
    them. Decisions still decide *what to try*; this system resolves how those
    progression actions alter the actual 2D match state.
    """

    def __init__(
        self,
        snapshot: MatchSnapshot,
        random_source: MatchRandom,
        perception: PerceptionSystem | None = None,
        config: ProgressionConfig | None = None,
        context: MatchContextSystem | None = None,
    ) -> None:
        self.snapshot = snapshot
        self.random = random_source
        self.perception = perception or PerceptionSystem()
        self.config = config or ProgressionConfig()
        self.context = context or MatchContextSystem(snapshot)
        self.active_carry: ActiveCarry | None = None
        self.active_cross: ActiveCross | None = None
        self.active_runs: dict[str, OffBallRun] = {}
        self.last_carry_result: CarryResult | None = None
        self.last_dribble_result: DribbleResult | None = None
        self.last_cross_result: CrossResult | None = None
        self._team_tactics = {
            TeamSide.HOME: snapshot.home_team.tactic,
            TeamSide.AWAY: snapshot.away_team.tactic,
        }

    @property
    def active_mover_ids(self) -> frozenset[str]:
        ids = set(self.active_runs)
        if self.active_carry is not None:
            ids.add(self.active_carry.profile.carrier_agent_id)
        return frozenset(ids)

    @property
    def ball_in_cross_flight(self) -> bool:
        return self.active_cross is not None

    def cancel(self) -> None:
        self.active_carry = None
        self.active_cross = None
        self.active_runs.clear()

    def cancel_carry(self) -> None:
        self.active_carry = None

    def cancel_cross(self) -> None:
        self.active_cross = None

    # ------------------------------------------------------------------
    # Off-ball running
    # ------------------------------------------------------------------
    def off_ball_run_plan(
        self,
        state: MatchState,
        attacking_side: TeamSide,
        *,
        max_runners: int | None = None,
    ) -> tuple[OffBallRun, ...]:
        side = TeamSide(attacking_side)
        if state.possession.team_side is not side:
            return ()

        carrier_id = state.ball.owner_agent_id
        limit = max_runners if max_runners is not None else self.config.max_off_ball_runs
        if limit <= 0:
            raise ValueError("max_runners must be positive")

        candidates: list[OffBallRun] = []
        for agent in state.active_players:
            if agent.side is not side or agent.agent_id == carrier_id:
                continue
            if agent.assigned_position is Position.GK:
                continue
            run = self._build_run(state, agent)
            if run.priority >= 35.0:
                candidates.append(run)

        candidates.sort(key=lambda item: (-item.priority, item.runner_agent_id))
        return tuple(candidates[:limit])

    def start_off_ball_runs(
        self,
        state: MatchState,
        attacking_side: TeamSide,
        *,
        max_runners: int | None = None,
    ) -> tuple[OffBallRun, ...]:
        runs = self.off_ball_run_plan(state, attacking_side, max_runners=max_runners)
        self.active_runs = {run.runner_agent_id: run for run in runs}
        return runs

    def _build_run(self, state: MatchState, agent: PlayerAgentState) -> OffBallRun:
        instructions = agent.player.effective_instructions
        forward_runs = float(instructions.forward_runs) if instructions is not None else 50.0
        attack_space = float(instructions.attack_space) if instructions is not None else 50.0
        roaming = float(instructions.roaming) if instructions is not None else 50.0
        mental = agent.player.attributes.mental
        physical = agent.player.attributes.physical
        team = self._team_tactics[agent.side].team_instructions.in_possession

        run_type = RunType.FORWARD
        y_target = agent.location.y
        centre_y = state.pitch.width_m / 2.0
        position_instruction = (
            instructions.in_possession_position
            if instructions is not None
            else InPossessionPosition.BASE
        )

        if position_instruction is InPossessionPosition.INSIDE:
            run_type = RunType.INSIDE
            y_target += (centre_y - agent.location.y) * 0.55
        elif position_instruction is InPossessionPosition.WIDE:
            run_type = RunType.WIDE
            touchline = 2.0 if agent.location.y < centre_y else state.pitch.width_m - 2.0
            y_target += (touchline - agent.location.y) * 0.65
        elif agent.assigned_position in {Position.LB, Position.RB} and float(team.overlap_frequency) >= 40.0:
            winger = self._same_side_winger(state, agent)
            if winger is not None:
                winger_instruction = winger.player.effective_instructions
                winger_inside = (
                    winger_instruction is not None
                    and winger_instruction.in_possession_position
                    in {InPossessionPosition.INSIDE, InPossessionPosition.MIDFIELD}
                )
                if winger_inside:
                    run_type = RunType.OVERLAP
                    touchline = 2.5 if agent.assigned_position is Position.LB else state.pitch.width_m - 2.5
                    y_target += (touchline - agent.location.y) * 0.70
                else:
                    run_type = RunType.UNDERLAP
                    y_target += (centre_y - agent.location.y) * 0.42

        base_distance = 5.0 + forward_runs / 100.0 * 8.0 + attack_space / 100.0 * 3.0
        if run_type in {RunType.OVERLAP, RunType.UNDERLAP}:
            base_distance += float(team.overlap_frequency) / 100.0 * 3.0
        x_target = agent.location.x + agent.side.attack_sign * base_distance
        target = state.pitch.clamp(Vector2(x_target, y_target))

        priority = _clamp(
            forward_runs * 0.32
            + attack_space * 0.23
            + roaming * 0.08
            + mental.off_the_ball * 0.16
            + mental.anticipation * 0.08
            + physical.pace * 0.07
            + physical.acceleration * 0.06
        )
        if run_type in {RunType.OVERLAP, RunType.UNDERLAP}:
            priority = _clamp(priority + float(team.overlap_frequency) * 0.12)

        speed = (
            3.8 + physical.pace / 100.0 * 2.0 + physical.acceleration / 100.0 * 0.8
        ) * self.context.movement_speed_multiplier(agent)
        return OffBallRun(
            runner_agent_id=agent.agent_id,
            run_type=run_type,
            origin=agent.location,
            target=target,
            priority=priority,
            speed_mps=speed,
        )

    def _same_side_winger(
        self,
        state: MatchState,
        fullback: PlayerAgentState,
    ) -> PlayerAgentState | None:
        wanted = Position.LW if fullback.assigned_position is Position.LB else Position.RW
        for agent in state.active_players:
            if agent.side is fullback.side and agent.assigned_position is wanted:
                return agent
        return None

    # ------------------------------------------------------------------
    # Carries
    # ------------------------------------------------------------------
    def start_carry(self, state: MatchState, decision: PlayerDecision) -> ActiveCarry:
        if decision.action_type is not ActionType.CARRY:
            raise ValueError("carry system requires a carry decision")
        carrier = state.agent(decision.agent_id)
        self._require_controlled_carrier(state, carrier)
        profile = self._build_carry_profile(state, carrier)
        self.active_carry = ActiveCarry(profile=profile, started_tick=state.clock.tick_count)
        self.last_carry_result = None
        return self.active_carry

    def _build_carry_profile(
        self,
        state: MatchState,
        carrier: PlayerAgentState,
        *,
        forced_target: Vector2 | None = None,
    ) -> CarryProfile:
        perception = self.perception.perceive(state, carrier.agent_id)
        instructions = carrier.player.effective_instructions
        attack_space = float(instructions.attack_space) if instructions is not None else 50.0
        technical = carrier.player.attributes.technical
        mental = carrier.player.attributes.mental
        physical = carrier.player.attributes.physical

        if forced_target is None:
            distance = 5.0 + attack_space / 100.0 * 6.0
            target = self._best_carry_target(state, carrier, distance)
        else:
            target = state.pitch.clamp(forced_target)
            distance = carrier.location.distance_to(target)

        speed = (
            2.9 + physical.pace / 100.0 * 1.4 + physical.acceleration / 100.0 * 0.9
        ) * self.context.movement_speed_multiplier(carrier)
        control_quality = _clamp(
            technical.dribbling * 0.30
            + technical.technique * 0.20
            + technical.first_touch * 0.12
            + physical.agility * 0.13
            + physical.balance * 0.10
            + mental.composure * 0.08
            + mental.decisions * 0.07
            - perception.pressure * 16.0
            + self.context.execution_adjustment(
                carrier,
                pressure=perception.pressure,
                distance_m=distance,
            )
            + self.context.first_touch_adjustment(carrier) * 0.45
        )
        retain_probability = _clamp01(
            0.68
            + control_quality / 100.0 * 0.28
            - perception.pressure * 0.20
            - max(distance - 9.0, 0.0) * 0.012
        )
        retain_probability = min(max(retain_probability, 0.35), 0.98)
        expected = max(distance / max(speed, 0.1), state.clock.tick_seconds)
        return CarryProfile(
            carrier_agent_id=carrier.agent_id,
            origin=carrier.location,
            target=target,
            distance_m=distance,
            speed_mps=speed,
            control_quality=control_quality,
            retain_probability=retain_probability,
            expected_seconds=expected,
        )

    def _best_carry_target(
        self,
        state: MatchState,
        carrier: PlayerAgentState,
        distance: float,
    ) -> Vector2:
        centre_y = state.pitch.width_m / 2.0
        directions = (
            Vector2(carrier.side.attack_sign, 0.0),
            Vector2(carrier.side.attack_sign, -0.48),
            Vector2(carrier.side.attack_sign, 0.48),
        )
        instructions = carrier.player.effective_instructions
        position_instruction = (
            instructions.in_possession_position
            if instructions is not None
            else InPossessionPosition.BASE
        )
        team = self._team_tactics[carrier.side].team_instructions.in_possession

        ranked: list[tuple[float, float, float, Vector2]] = []
        for direction in directions:
            unit = direction.normalized()
            target = state.pitch.clamp(carrier.location + unit.scale(distance))
            pressure = self.perception.pressure_at(state, carrier.side, target)
            centrality = 1.0 - min(abs(target.y - centre_y) / centre_y, 1.0)
            tactical = 0.0
            if position_instruction is InPossessionPosition.INSIDE:
                tactical += centrality * 0.25
            elif position_instruction is InPossessionPosition.WIDE:
                tactical += (1.0 - centrality) * 0.25
            else:
                central_bias = float(team.central_focus) / 100.0
                tactical += centrality * central_bias * 0.12
            score = (1.0 - pressure) * 0.76 + tactical
            ranked.append((score, -pressure, -abs(target.y - carrier.location.y), target))
        ranked.sort(key=lambda item: (item[0], item[1], item[2]), reverse=True)
        return ranked[0][3]

    # ------------------------------------------------------------------
    # Dribbling
    # ------------------------------------------------------------------
    def dribble_profile(self, state: MatchState, attacker_agent_id: str) -> DribbleProfile:
        attacker = state.agent(attacker_agent_id)
        self._require_controlled_carrier(state, attacker)
        defender = self._nearest_dribble_defender(state, attacker)
        if defender is None:
            raise ValueError("no opponent is close enough for a dribble duel")

        perception = self.perception.perceive(state, attacker.agent_id)
        technical = attacker.player.attributes.technical
        mental = attacker.player.attributes.mental
        physical = attacker.player.attributes.physical
        dtech = defender.player.attributes.technical
        dmental = defender.player.attributes.mental
        dphysical = defender.player.attributes.physical

        attacker_quality = _clamp(
            technical.dribbling * 0.34
            + technical.technique * 0.18
            + physical.agility * 0.16
            + physical.acceleration * 0.12
            + physical.balance * 0.08
            + mental.decisions * 0.06
            + mental.composure * 0.06
            + self.context.execution_adjustment(attacker, pressure=perception.pressure)
            + self.context.first_touch_adjustment(attacker) * 0.35
        )
        defender_quality = _clamp(
            dtech.tackling * 0.30
            + dmental.anticipation * 0.18
            + dmental.positioning * 0.18
            + dphysical.agility * 0.10
            + dphysical.acceleration * 0.10
            + dphysical.balance * 0.07
            + dphysical.strength * 0.07
            + self.context.execution_adjustment(defender) * 0.55
        )
        forward_point = state.pitch.clamp(
            attacker.location + Vector2(attacker.side.attack_sign * 5.0, 0.0)
        )
        forward_space = 1.0 - self.perception.pressure_at(state, attacker.side, forward_point)
        success = _clamp01(
            0.50
            + (attacker_quality - defender_quality) * 0.0043
            + forward_space * 0.11
            - perception.pressure * 0.11
        )
        success = min(max(success, 0.12), 0.88)
        defender_control = _clamp01(
            0.48
            + defender_quality / 100.0 * 0.28
            + dmental.composure / 100.0 * 0.10
            - attacker_quality / 100.0 * 0.08
        )
        defender_control = min(max(defender_control, 0.35), 0.88)

        escape_target = self._dribble_escape_target(state, attacker, defender)
        return DribbleProfile(
            attacker_agent_id=attacker.agent_id,
            defender_agent_id=defender.agent_id,
            attacker_quality=attacker_quality,
            defender_quality=defender_quality,
            local_pressure=perception.pressure,
            forward_space=forward_space,
            success_probability=success,
            clean_defender_control_probability=defender_control,
            escape_target=escape_target,
        )

    def attempt_dribble(self, state: MatchState, decision: PlayerDecision) -> DribbleResult:
        if decision.action_type is not ActionType.DRIBBLE:
            raise ValueError("dribble resolver requires a dribble decision")
        profile = self.dribble_profile(state, decision.agent_id)
        attacker = state.agent(profile.attacker_agent_id)
        defender = state.agent(profile.defender_agent_id)

        if self.random.random() <= profile.success_probability:
            carry_profile = self._build_carry_profile(
                state,
                attacker,
                forced_target=profile.escape_target,
            )
            self.active_carry = ActiveCarry(
                profile=carry_profile,
                started_tick=state.clock.tick_count,
            )
            result = DribbleResult(
                outcome=DribbleOutcome.BEATS_DEFENDER,
                attacker_agent_id=attacker.agent_id,
                defender_agent_id=defender.agent_id,
                controller_agent_id=attacker.agent_id,
                success_probability=profile.success_probability,
                resolved_tick=state.clock.tick_count,
                escape_target=profile.escape_target,
            )
        elif self.random.random() <= profile.clean_defender_control_probability:
            self._give_control(state, defender)
            self.active_carry = None
            result = DribbleResult(
                outcome=DribbleOutcome.DEFENDER_WINS,
                attacker_agent_id=attacker.agent_id,
                defender_agent_id=defender.agent_id,
                controller_agent_id=defender.agent_id,
                success_probability=profile.success_probability,
                resolved_tick=state.clock.tick_count,
            )
        else:
            loose = self._loose_ball_after_duel(state, attacker, defender)
            self._leave_ball_loose(state, loose, last_touch=defender.agent_id)
            self.active_carry = None
            result = DribbleResult(
                outcome=DribbleOutcome.LOOSE_BALL,
                attacker_agent_id=attacker.agent_id,
                defender_agent_id=defender.agent_id,
                controller_agent_id=None,
                success_probability=profile.success_probability,
                resolved_tick=state.clock.tick_count,
                loose_ball_location=loose,
            )
        self.last_dribble_result = result
        return result

    def _nearest_dribble_defender(
        self,
        state: MatchState,
        attacker: PlayerAgentState,
    ) -> PlayerAgentState | None:
        candidates = [
            opponent
            for opponent in state.active_players
            if opponent.side is not attacker.side
            and opponent.location.distance_to(attacker.location)
            <= self.config.dribble_engagement_radius_m
        ]
        if not candidates:
            return None
        return min(
            candidates,
            key=lambda opponent: (
                opponent.location.distance_to(attacker.location),
                opponent.agent_id,
            ),
        )

    def _dribble_escape_target(
        self,
        state: MatchState,
        attacker: PlayerAgentState,
        defender: PlayerAgentState,
    ) -> Vector2:
        goalward = Vector2(attacker.side.attack_sign, 0.0)
        defender_vector = defender.location - attacker.location
        side_sign = -1.0 if defender_vector.y >= 0.0 else 1.0
        diagonal = Vector2(attacker.side.attack_sign, side_sign * 0.55).normalized()
        straight_target = state.pitch.clamp(attacker.location + goalward.scale(6.0))
        diagonal_target = state.pitch.clamp(attacker.location + diagonal.scale(6.5))
        straight_pressure = self.perception.pressure_at(state, attacker.side, straight_target)
        diagonal_pressure = self.perception.pressure_at(state, attacker.side, diagonal_target)
        return diagonal_target if diagonal_pressure + 0.05 < straight_pressure else straight_target

    # ------------------------------------------------------------------
    # Crosses / cutbacks
    # ------------------------------------------------------------------
    def start_cross(self, state: MatchState, decision: PlayerDecision) -> ActiveCross:
        if decision.action_type is not ActionType.CROSS:
            raise ValueError("crossing system requires a cross decision")
        if self.active_cross is not None:
            raise ValueError("cannot start a cross while another cross is in flight")
        crosser = state.agent(decision.agent_id)
        self._require_controlled_carrier(state, crosser)
        receiver = (
            state.agent(decision.target_agent_id)
            if decision.target_agent_id is not None
            else self._select_cross_receiver(state, crosser)
        )
        if receiver.side is not crosser.side or receiver.agent_id == crosser.agent_id:
            raise ValueError("cross receiver must be a teammate")

        profile = self._build_cross_profile(state, crosser, receiver)
        self.active_cross = ActiveCross(profile=profile, started_tick=state.clock.tick_count)
        self.last_cross_result = None
        self.active_carry = None

        state.possession.team_side = crosser.side
        state.possession.owner_agent_id = None
        state.ball.owner_agent_id = None
        state.ball.last_touch_agent_id = crosser.agent_id
        state.ball.location = crosser.location
        state.ball.height_m = 0.0
        direction = (profile.actual_target - profile.origin).normalized()
        state.ball.velocity = direction.scale(profile.ball_speed_mps)
        for agent in state.players.values():
            agent.has_ball = False
        return self.active_cross

    def _select_cross_receiver(
        self,
        state: MatchState,
        crosser: PlayerAgentState,
    ) -> PlayerAgentState:
        cross_type = self._effective_cross_type(state, crosser)
        attacking_positions = {
            Position.ST,
            Position.SS,
            Position.RW,
            Position.LW,
            Position.AM,
            Position.RCM,
            Position.CM,
            Position.LCM,
        }
        centre_y = state.pitch.width_m / 2.0
        goal_x = state.pitch.length_m if crosser.side is TeamSide.HOME else 0.0
        crosser_progress = self._attack_progress(state, crosser)

        candidates: list[PlayerAgentState] = []
        for agent in state.active_players:
            if agent.side is not crosser.side or agent.agent_id == crosser.agent_id:
                continue
            if agent.assigned_position not in attacking_positions:
                continue
            receiver_progress = self._attack_progress(state, agent)
            goal_distance = abs(goal_x - agent.location.x)
            central_enough = abs(agent.location.y - centre_y) <= 21.0
            if cross_type is CrossType.CUTBACK:
                # Cutbacks look for a trailing runner around the box, not a
                # defender standing 40 metres behind the play.
                valid = (
                    receiver_progress >= 0.68
                    and receiver_progress >= crosser_progress - 0.22
                    and goal_distance <= 34.0
                    and central_enough
                )
            else:
                valid = receiver_progress >= 0.55 and goal_distance <= 48.0 and central_enough
            if valid:
                candidates.append(agent)

        if not candidates:
            # Keep open-play crosses attached to plausible attacking runners. A
            # centre-back can still participate in dedicated set-piece logic
            # later, but should not become the default target simply because no
            # forward has reached the box yet.
            candidates = [
                agent
                for agent in state.active_players
                if agent.side is crosser.side
                and agent.agent_id != crosser.agent_id
                and agent.assigned_position in attacking_positions
            ]
        if not candidates:
            raise ValueError("cross requires at least one attacking teammate")

        ranked: list[tuple[float, str, PlayerAgentState]] = []
        for receiver in candidates:
            progress = (receiver.location.x - crosser.location.x) * crosser.side.attack_sign
            goal_distance = abs(goal_x - receiver.location.x)
            centrality = 1.0 - min(abs(receiver.location.y - centre_y) / centre_y, 1.0)
            pressure = self.perception.pressure_at(state, crosser.side, receiver.location)
            tech = receiver.player.attributes.technical
            mental = receiver.player.attributes.mental
            physical = receiver.player.attributes.physical

            if cross_type is CrossType.CUTBACK:
                trailing_fit = _clamp(100.0 - abs(progress + 7.0) * 5.0)
                score = (
                    trailing_fit * 0.36
                    + centrality * 100.0 * 0.22
                    + (1.0 - pressure) * 100.0 * 0.20
                    + tech.finishing * 0.10
                    + mental.off_the_ball * 0.12
                )
            else:
                box_fit = _clamp(100.0 - max(goal_distance - 18.0, 0.0) * 4.0)
                aerial = tech.heading * 0.55 + physical.jumping_reach * 0.45
                receiver_skill = aerial if cross_type is CrossType.HIGH else tech.first_touch
                score = (
                    box_fit * 0.30
                    + centrality * 100.0 * 0.18
                    + (1.0 - pressure) * 100.0 * 0.18
                    + receiver_skill * 0.16
                    + mental.off_the_ball * 0.12
                    + _clamp(50.0 + progress * 2.0) * 0.06
                )
            ranked.append((score, receiver.agent_id, receiver))
        ranked.sort(key=lambda item: (-item[0], item[1]))
        return ranked[0][2]

    def _effective_cross_type(
        self,
        state: MatchState,
        crosser: PlayerAgentState,
    ) -> CrossType:
        instructions = crosser.player.effective_instructions
        requested = instructions.cross_type if instructions is not None else CrossType.MIXED
        if requested is not CrossType.MIXED:
            return requested
        progress = self._attack_progress(state, crosser)
        if progress >= 0.88:
            return CrossType.CUTBACK
        if progress < 0.68:
            return CrossType.EARLY
        return CrossType.LOW

    def _build_cross_profile(
        self,
        state: MatchState,
        crosser: PlayerAgentState,
        receiver: PlayerAgentState,
    ) -> CrossExecutionProfile:
        cross_type = self._effective_cross_type(state, crosser)
        perception = self.perception.perceive(state, crosser.agent_id)
        technical = crosser.player.attributes.technical
        mental = crosser.player.attributes.mental
        execution = _clamp(
            technical.crossing * 0.48
            + technical.technique * 0.17
            + mental.vision * 0.13
            + mental.decisions * 0.10
            + mental.composure * 0.12
            - perception.pressure * 16.0
            + self.context.execution_adjustment(
                crosser,
                pressure=perception.pressure,
                distance_m=crosser.location.distance_to(receiver.location),
                aerial=True,
            )
        )

        lead = 0.45 if cross_type is CrossType.CUTBACK else 0.75
        intended = state.pitch.clamp(receiver.location + receiver.velocity.scale(lead))
        path = intended - crosser.location
        distance = max(path.magnitude, 0.01)
        direction = path.normalized()
        perpendicular = Vector2(-direction.y, direction.x)

        type_error = {
            CrossType.EARLY: 0.115,
            CrossType.BYLINE: 0.085,
            CrossType.LOW: 0.080,
            CrossType.HIGH: 0.105,
            CrossType.CUTBACK: 0.060,
            CrossType.MIXED: 0.095,
        }[cross_type]
        error_factor = (100.0 - execution) / 100.0
        context_error = self.context.error_multiplier(distance_m=distance, aerial=True)
        lateral_limit = (0.15 + distance * error_factor * type_error) * context_error
        longitudinal_limit = (0.10 + distance * error_factor * type_error * 0.45) * context_error
        lateral = self.random.uniform(-lateral_limit, lateral_limit)
        longitudinal = self.random.uniform(-longitudinal_limit, longitudinal_limit)
        actual = state.pitch.clamp(
            intended + perpendicular.scale(lateral) + direction.scale(longitudinal)
        )
        actual_distance = max(crosser.location.distance_to(actual), 0.01)
        speed = {
            CrossType.CUTBACK: 15.5,
            CrossType.LOW: 18.0,
            CrossType.BYLINE: 19.0,
            CrossType.EARLY: 21.0,
            CrossType.HIGH: 20.0,
            CrossType.MIXED: 19.0,
        }[cross_type]
        speed *= 0.93 + technical.crossing / 100.0 * 0.12
        speed *= self.context.ball_speed_multiplier(aerial=True)
        max_height = {
            CrossType.CUTBACK: 0.15,
            CrossType.LOW: 0.35,
            CrossType.BYLINE: 1.35,
            CrossType.EARLY: 2.2,
            CrossType.HIGH: 3.3,
            CrossType.MIXED: 1.6,
        }[cross_type]
        return CrossExecutionProfile(
            crosser_agent_id=crosser.agent_id,
            receiver_agent_id=receiver.agent_id,
            cross_type=cross_type,
            origin=crosser.location,
            intended_target=intended,
            actual_target=actual,
            distance_m=actual_distance,
            execution_quality=execution,
            target_error_m=intended.distance_to(actual),
            ball_speed_mps=speed,
            max_height_m=max_height,
            expected_travel_seconds=max(actual_distance / speed, state.clock.tick_seconds),
        )

    # ------------------------------------------------------------------
    # Fixed-step updates
    # ------------------------------------------------------------------
    def update_movement_velocities(self, state: MatchState) -> None:
        self._prune_invalid_actions(state)

        if self.active_carry is not None:
            profile = self.active_carry.profile
            carrier = state.agent(profile.carrier_agent_id)
            self._move_toward(carrier, profile.target, profile.speed_mps)

        for agent_id, run in list(self.active_runs.items()):
            runner = state.agent(agent_id)
            if runner.side is not state.possession.team_side:
                self.active_runs.pop(agent_id, None)
                continue
            if runner.location.distance_to(run.target) <= self.config.off_ball_arrival_radius_m:
                runner.velocity = Vector2.zero()
                self.active_runs.pop(agent_id, None)
                continue
            self._move_toward(runner, run.target, run.speed_mps)

    def advance(self, state: MatchState, dt: float) -> None:
        if dt <= 0.0:
            raise ValueError("progression timestep must be positive")
        self._advance_carry(state, dt)
        self._advance_cross(state, dt)

    def _advance_carry(self, state: MatchState, dt: float) -> CarryResult | None:
        active = self.active_carry
        if active is None:
            return None
        carrier = state.agent(active.profile.carrier_agent_id)
        if state.ball.owner_agent_id != carrier.agent_id:
            self.active_carry = None
            return None

        active.elapsed_seconds += dt
        remaining = carrier.location.distance_to(active.profile.target)
        if remaining > self.config.carry_arrival_radius_m and active.elapsed_seconds < active.profile.expected_seconds + 0.75:
            return None

        carrier.velocity = Vector2.zero()
        covered = active.profile.origin.distance_to(carrier.location)
        if self.random.random() <= active.profile.retain_probability:
            result = CarryResult(
                outcome=CarryOutcome.COMPLETED,
                carrier_agent_id=carrier.agent_id,
                started_tick=active.started_tick,
                resolved_tick=state.clock.tick_count + 1,
                distance_covered_m=covered,
                control_quality=active.profile.control_quality,
                retain_probability=active.profile.retain_probability,
            )
        else:
            forward = Vector2(carrier.side.attack_sign, 0.0)
            side = -1.0 if self.random.random() < 0.5 else 1.0
            loose = state.pitch.clamp(
                carrier.location
                + forward.scale(self.random.uniform(0.8, 1.8))
                + Vector2(0.0, side * self.random.uniform(0.5, 1.5))
            )
            self._leave_ball_loose(state, loose, last_touch=carrier.agent_id)
            result = CarryResult(
                outcome=CarryOutcome.LOOSE_BALL,
                carrier_agent_id=carrier.agent_id,
                started_tick=active.started_tick,
                resolved_tick=state.clock.tick_count + 1,
                distance_covered_m=covered,
                control_quality=active.profile.control_quality,
                retain_probability=active.profile.retain_probability,
                loose_ball_location=loose,
            )
        self.active_carry = None
        self.last_carry_result = result
        return result

    def _advance_cross(self, state: MatchState, dt: float) -> CrossResult | None:
        active = self.active_cross
        if active is None:
            return None
        profile = active.profile
        previous = state.ball.location
        active.elapsed_seconds = min(
            active.elapsed_seconds + dt,
            profile.expected_travel_seconds,
        )
        progress = _clamp01(active.elapsed_seconds / profile.expected_travel_seconds)
        path = profile.actual_target - profile.origin
        state.ball.location = state.pitch.clamp(profile.origin + path.scale(progress))
        state.ball.velocity = path.normalized().scale(profile.ball_speed_mps)
        state.ball.height_m = profile.max_height_m * sin(pi * progress)

        interceptor = self._try_cross_interception(state, previous, state.ball.location, profile)
        if interceptor is not None:
            self._give_control(state, interceptor)
            result = CrossResult(
                outcome=CrossOutcome.INTERCEPTED,
                crosser_agent_id=profile.crosser_agent_id,
                intended_receiver_agent_id=profile.receiver_agent_id,
                controller_agent_id=interceptor.agent_id,
                cross_type=profile.cross_type,
                started_tick=active.started_tick,
                resolved_tick=state.clock.tick_count + 1,
                execution_quality=profile.execution_quality,
                target_error_m=profile.target_error_m,
                interception_agent_id=interceptor.agent_id,
            )
            self.active_cross = None
            self.last_cross_result = result
            return result

        if progress < 1.0:
            return None
        return self._resolve_cross_arrival(state, active)

    def _try_cross_interception(
        self,
        state: MatchState,
        start: Vector2,
        end: Vector2,
        profile: CrossExecutionProfile,
    ) -> PlayerAgentState | None:
        crosser = state.agent(profile.crosser_agent_id)
        candidates: list[tuple[float, str, PlayerAgentState]] = []
        for opponent in state.active_players:
            if opponent.side is crosser.side:
                continue
            distance = _distance_to_segment(opponent.location, start, end)
            if distance <= self.config.cross_interception_radius_m:
                candidates.append((distance, opponent.agent_id, opponent))

        for distance, _, opponent in sorted(candidates, key=lambda item: (item[0], item[1])):
            mental = opponent.player.attributes.mental
            technical = opponent.player.attributes.technical
            physical = opponent.player.attributes.physical
            defensive_quality = _clamp(
                mental.anticipation * 0.24
                + mental.positioning * 0.22
                + mental.concentration * 0.16
                + technical.heading * 0.14
                + physical.jumping_reach * 0.12
                + physical.agility * 0.12
            )
            proximity = 1.0 - min(distance / self.config.cross_interception_radius_m, 1.0)
            height_difficulty = min(state.ball.height_m / 3.3, 1.0)
            aerial_bonus = (technical.heading + physical.jumping_reach) / 200.0
            probability = _clamp01(
                0.06
                + defensive_quality / 100.0 * 0.30
                + proximity * 0.34
                + height_difficulty * aerial_bonus * 0.15
                - profile.execution_quality / 100.0 * 0.10
            )
            if self.random.random() <= probability:
                return opponent
        return None

    def _resolve_cross_arrival(self, state: MatchState, active: ActiveCross) -> CrossResult:
        profile = active.profile
        receiver = state.agent(profile.receiver_agent_id)
        collector = self._cross_collector(state, profile, receiver)
        state.ball.height_m = 0.0

        if collector is None:
            self._leave_ball_loose(state, profile.actual_target, last_touch=profile.crosser_agent_id)
            result = CrossResult(
                outcome=CrossOutcome.MISPLACED,
                crosser_agent_id=profile.crosser_agent_id,
                intended_receiver_agent_id=profile.receiver_agent_id,
                controller_agent_id=None,
                cross_type=profile.cross_type,
                started_tick=active.started_tick,
                resolved_tick=state.clock.tick_count + 1,
                execution_quality=profile.execution_quality,
                target_error_m=profile.target_error_m,
            )
        elif collector.side is not state.agent(profile.crosser_agent_id).side:
            self._give_control(state, collector)
            result = CrossResult(
                outcome=CrossOutcome.INTERCEPTED,
                crosser_agent_id=profile.crosser_agent_id,
                intended_receiver_agent_id=profile.receiver_agent_id,
                controller_agent_id=collector.agent_id,
                cross_type=profile.cross_type,
                started_tick=active.started_tick,
                resolved_tick=state.clock.tick_count + 1,
                execution_quality=profile.execution_quality,
                target_error_m=profile.target_error_m,
                interception_agent_id=collector.agent_id,
            )
        else:
            probability = self._cross_control_probability(state, collector, profile)
            if self.random.random() <= probability:
                self._give_control(state, collector)
                result = CrossResult(
                    outcome=CrossOutcome.COMPLETED,
                    crosser_agent_id=profile.crosser_agent_id,
                    intended_receiver_agent_id=profile.receiver_agent_id,
                    controller_agent_id=collector.agent_id,
                    cross_type=profile.cross_type,
                    started_tick=active.started_tick,
                    resolved_tick=state.clock.tick_count + 1,
                    execution_quality=profile.execution_quality,
                    target_error_m=profile.target_error_m,
                    first_touch_probability=probability,
                )
            else:
                loose = state.pitch.clamp(
                    collector.location + Vector2(collector.side.attack_sign * 1.2, 0.7)
                )
                self._leave_ball_loose(state, loose, last_touch=collector.agent_id)
                result = CrossResult(
                    outcome=CrossOutcome.BAD_CONTROL,
                    crosser_agent_id=profile.crosser_agent_id,
                    intended_receiver_agent_id=profile.receiver_agent_id,
                    controller_agent_id=None,
                    cross_type=profile.cross_type,
                    started_tick=active.started_tick,
                    resolved_tick=state.clock.tick_count + 1,
                    execution_quality=profile.execution_quality,
                    target_error_m=profile.target_error_m,
                    first_touch_probability=probability,
                )

        self.active_cross = None
        self.last_cross_result = result
        return result

    def _cross_collector(
        self,
        state: MatchState,
        profile: CrossExecutionProfile,
        intended_receiver: PlayerAgentState,
    ) -> PlayerAgentState | None:
        candidates: list[tuple[float, int, str, PlayerAgentState]] = []
        for agent in state.active_players:
            if agent.agent_id == profile.crosser_agent_id:
                continue
            distance = agent.location.distance_to(profile.actual_target)
            if distance <= self.config.cross_collection_radius_m:
                priority = 0 if agent.agent_id == intended_receiver.agent_id else 1
                candidates.append((distance, priority, agent.agent_id, agent))
        if not candidates:
            return None
        return min(candidates, key=lambda item: (item[0], item[1], item[2]))[3]

    def _cross_control_probability(
        self,
        state: MatchState,
        receiver: PlayerAgentState,
        profile: CrossExecutionProfile,
    ) -> float:
        technical = receiver.player.attributes.technical
        mental = receiver.player.attributes.mental
        physical = receiver.player.attributes.physical
        pressure = self.perception.pressure_at(state, receiver.side, receiver.location)
        if profile.cross_type is CrossType.HIGH:
            control_quality = technical.heading * 0.45 + physical.jumping_reach * 0.25 + mental.anticipation * 0.15 + mental.composure * 0.15
        else:
            control_quality = technical.first_touch * 0.46 + technical.technique * 0.20 + mental.anticipation * 0.14 + mental.composure * 0.12 + physical.balance * 0.08
        control_quality += self.context.first_touch_adjustment(receiver)
        return min(max(0.34 + control_quality / 100.0 * 0.55 - pressure * 0.18, 0.18), 0.94)

    # ------------------------------------------------------------------
    # Shared helpers
    # ------------------------------------------------------------------
    def _prune_invalid_actions(self, state: MatchState) -> None:
        if self.active_carry is not None:
            carrier_id = self.active_carry.profile.carrier_agent_id
            if state.ball.owner_agent_id != carrier_id:
                self.active_carry = None
        if self.active_runs and state.possession.team_side is None:
            self.active_runs.clear()

    @staticmethod
    def _move_toward(agent: PlayerAgentState, target: Vector2, speed_mps: float) -> None:
        delta = target - agent.location
        if delta.magnitude == 0.0:
            agent.velocity = Vector2.zero()
            return
        agent.velocity = delta.normalized().scale(speed_mps)

    @staticmethod
    def _require_controlled_carrier(state: MatchState, carrier: PlayerAgentState) -> None:
        if not carrier.is_active:
            raise ValueError("dismissed player cannot perform progression actions")
        if state.ball.owner_agent_id != carrier.agent_id:
            raise ValueError("progression action requires the player to control the ball")
        if state.possession.owner_agent_id != carrier.agent_id:
            raise ValueError("progression action requires synchronized possession ownership")
        if state.possession.team_side is not carrier.side:
            raise ValueError("possession team must match the ball carrier")

    @staticmethod
    def _give_control(state: MatchState, controller: PlayerAgentState) -> None:
        state.possession.team_side = controller.side
        state.possession.owner_agent_id = controller.agent_id
        state.ball.owner_agent_id = controller.agent_id
        state.ball.last_touch_agent_id = controller.agent_id
        state.ball.location = controller.location
        state.ball.velocity = Vector2.zero()
        state.ball.height_m = 0.0
        for agent in state.players.values():
            agent.has_ball = agent.agent_id == controller.agent_id

    @staticmethod
    def _leave_ball_loose(
        state: MatchState,
        location: Vector2,
        *,
        last_touch: str | None,
    ) -> None:
        state.possession.team_side = None
        state.possession.owner_agent_id = None
        state.ball.owner_agent_id = None
        state.ball.last_touch_agent_id = last_touch
        state.ball.location = state.pitch.clamp(location)
        state.ball.velocity = Vector2.zero()
        state.ball.height_m = 0.0
        for agent in state.players.values():
            agent.has_ball = False

    def _loose_ball_after_duel(
        self,
        state: MatchState,
        attacker: PlayerAgentState,
        defender: PlayerAgentState,
    ) -> Vector2:
        forward = Vector2(attacker.side.attack_sign, 0.0)
        side = -1.0 if defender.location.y >= attacker.location.y else 1.0
        return state.pitch.clamp(
            attacker.location + forward.scale(1.2) + Vector2(0.0, side * 0.8)
        )

    @staticmethod
    def _attack_progress(state: MatchState, agent: PlayerAgentState) -> float:
        if agent.side is TeamSide.HOME:
            return agent.location.x / state.pitch.length_m
        return (state.pitch.length_m - agent.location.x) / state.pitch.length_m


def _distance_to_segment(point: Vector2, start: Vector2, end: Vector2) -> float:
    segment = end - start
    length_sq = segment.x * segment.x + segment.y * segment.y
    if length_sq == 0.0:
        return point.distance_to(start)
    relative = point - start
    projection = (relative.x * segment.x + relative.y * segment.y) / length_sq
    projection = min(max(projection, 0.0), 1.0)
    closest = Vector2(
        start.x + segment.x * projection,
        start.y + segment.y * projection,
    )
    return point.distance_to(closest)
