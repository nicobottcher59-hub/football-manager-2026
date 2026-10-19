from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from math import pi, sin

from football_manager.domain import MatchSnapshot

from .decisions import ActionType, PlayerDecision
from .geometry import Vector2
from .match_context_effects import MatchContextSystem
from .perception import PerceptionSystem
from .randomness import MatchRandom
from .spatial_state import MatchState, PlayerAgentState, TeamSide


PASS_ACTION_TYPES = frozenset(
    {
        ActionType.SHORT_PASS,
        ActionType.PROGRESSIVE_PASS,
        ActionType.LONG_PASS,
    }
)


def _clamp(value: float, minimum: float = 0.0, maximum: float = 100.0) -> float:
    return min(max(value, minimum), maximum)


def _clamp01(value: float) -> float:
    return min(max(value, 0.0), 1.0)


class PassOutcome(StrEnum):
    COMPLETED = "completed"
    INTERCEPTED = "intercepted"
    MISPLACED = "misplaced"
    BAD_CONTROL = "bad_control"


@dataclass(frozen=True, slots=True)
class PassExecutionProfile:
    passer_agent_id: str
    receiver_agent_id: str
    action_type: ActionType
    origin: Vector2
    intended_target: Vector2
    actual_target: Vector2
    distance_m: float
    passer_pressure: float
    lane_openness: float
    receiver_space: float
    execution_quality: float
    lateral_error_m: float
    longitudinal_error_m: float
    target_error_m: float
    ball_speed_mps: float
    max_height_m: float
    expected_travel_seconds: float


@dataclass(slots=True)
class ActivePass:
    profile: PassExecutionProfile
    started_tick: int
    elapsed_seconds: float = 0.0

    @property
    def remaining_seconds(self) -> float:
        return max(self.profile.expected_travel_seconds - self.elapsed_seconds, 0.0)


@dataclass(frozen=True, slots=True)
class PassResult:
    outcome: PassOutcome
    passer_agent_id: str
    intended_receiver_agent_id: str
    controller_agent_id: str | None
    action_type: ActionType
    started_tick: int
    resolved_tick: int
    travel_seconds: float
    execution_quality: float
    target_error_m: float
    interception_agent_id: str | None = None
    first_touch_quality: float | None = None
    first_touch_probability: float | None = None


@dataclass(frozen=True, slots=True)
class PassingConfig:
    short_pass_speed_mps: float = 15.0
    progressive_pass_speed_mps: float = 19.0
    long_pass_speed_mps: float = 23.0
    interception_base_radius_m: float = 0.78
    receiver_control_radius_m: float = 1.75
    endpoint_collection_radius_m: float = 2.0

    def __post_init__(self) -> None:
        for name in (
            "short_pass_speed_mps",
            "progressive_pass_speed_mps",
            "long_pass_speed_mps",
            "interception_base_radius_m",
            "receiver_control_radius_m",
            "endpoint_collection_radius_m",
        ):
            if getattr(self, name) <= 0.0:
                raise ValueError(f"{name} must be positive")


class PassingSystem:
    """Resolve pass intentions through the spatial match state.

    Phase 5.3 keeps decision and execution explicitly separate. The decision
    layer says *which pass a player wants to attempt*. This system determines
    the physical target, travel time, execution error, possible interception
    and first-touch outcome using the actual spatial state.
    """

    def __init__(
        self,
        snapshot: MatchSnapshot,
        random_source: MatchRandom,
        perception: PerceptionSystem | None = None,
        config: PassingConfig | None = None,
        context: MatchContextSystem | None = None,
    ) -> None:
        self.snapshot = snapshot
        self.random = random_source
        self.perception = perception or PerceptionSystem()
        self.config = config or PassingConfig()
        self.context = context or MatchContextSystem(snapshot)
        self.active_pass: ActivePass | None = None
        self.last_result: PassResult | None = None
        self._team_tactics = {
            TeamSide.HOME: snapshot.home_team.tactic,
            TeamSide.AWAY: snapshot.away_team.tactic,
        }

    @property
    def is_ball_in_flight(self) -> bool:
        return self.active_pass is not None

    @property
    def active_mover_ids(self) -> frozenset[str]:
        if self.active_pass is None:
            return frozenset()
        return frozenset({self.active_pass.profile.receiver_agent_id})

    def update_receiver_velocity(self, state: MatchState) -> None:
        """Let the intended receiver actually meet the pass in space.

        The earlier isolated pass tests could resolve a target point without a
        live tactical world. In a full match the receiver kept following a
        tactical anchor during ball flight, often walking away from the pass and
        creating huge numbers of artificial MISPLACED outcomes. The receiver now
        adjusts toward the intended football target while the ball travels.
        """

        if self.active_pass is None:
            return
        profile = self.active_pass.profile
        receiver = state.agent(profile.receiver_agent_id)
        if not receiver.is_active:
            return
        delta = profile.intended_target - receiver.location
        if delta.magnitude <= 0.30:
            receiver.velocity = Vector2.zero()
            return
        physical = receiver.player.attributes.physical
        speed = 3.2 + physical.pace / 100.0 * 1.5 + physical.acceleration / 100.0 * 0.9
        receiver.velocity = delta.normalized().scale(speed * self.context.movement_speed_multiplier(receiver))

    def cancel(self) -> None:
        self.active_pass = None

    def start(self, state: MatchState, decision: PlayerDecision) -> ActivePass:
        if self.active_pass is not None:
            raise ValueError("cannot start a pass while another pass is in flight")
        if decision.action_type not in PASS_ACTION_TYPES:
            raise ValueError("passing system can only execute pass decisions")
        if decision.target_agent_id is None:
            raise ValueError("pass decision requires a target player")

        passer = state.agent(decision.agent_id)
        receiver = state.agent(decision.target_agent_id)
        self._validate_pass_state(state, passer, receiver)
        profile = self._build_profile(state, passer, receiver, decision.action_type)

        self.active_pass = ActivePass(profile=profile, started_tick=state.clock.tick_count)
        self.last_result = None

        # The attacking team still has the ball in a football sense while it is
        # travelling, but no individual player controls it.
        state.possession.team_side = passer.side
        state.possession.owner_agent_id = None
        state.ball.owner_agent_id = None
        state.ball.last_touch_agent_id = passer.agent_id
        state.ball.location = passer.location
        state.ball.height_m = 0.0
        direction = (profile.actual_target - profile.origin).normalized()
        state.ball.velocity = direction.scale(profile.ball_speed_mps)
        for agent in state.players.values():
            agent.has_ball = False
        return self.active_pass

    def advance(self, state: MatchState, dt: float) -> PassResult | None:
        active = self.active_pass
        if active is None:
            return None
        if dt <= 0.0:
            raise ValueError("pass timestep must be positive")

        profile = active.profile
        previous_location = state.ball.location
        active.elapsed_seconds = min(
            active.elapsed_seconds + dt,
            profile.expected_travel_seconds,
        )
        progress = _clamp01(active.elapsed_seconds / profile.expected_travel_seconds)
        path = profile.actual_target - profile.origin
        next_location = profile.origin + path.scale(progress)
        state.ball.location = state.pitch.clamp(next_location)
        state.ball.velocity = path.normalized().scale(profile.ball_speed_mps)
        state.ball.height_m = max(0.0, sin(pi * progress) * profile.max_height_m)

        interceptor = self._try_interception(
            state,
            previous_location,
            state.ball.location,
            profile,
        )
        if interceptor is not None:
            return self._resolve_interception(state, active, interceptor)

        if progress < 1.0:
            return None
        return self._resolve_arrival(state, active)

    def _build_profile(
        self,
        state: MatchState,
        passer: PlayerAgentState,
        receiver: PlayerAgentState,
        action_type: ActionType,
    ) -> PassExecutionProfile:
        perception = self.perception.perceive(state, passer.agent_id)
        lane = perception.lane_to(receiver.agent_id)
        distance = passer.location.distance_to(receiver.location)
        execution_quality = self._execution_quality(
            passer,
            action_type,
            distance,
            perception.pressure,
        )
        speed = self._ball_speed(passer, action_type)
        base_travel = max(distance / speed, state.clock.tick_seconds)

        # Lead the receiver using their current real movement rather than a
        # static formation coordinate. Progressive passes deliberately lead a
        # forward-running receiver more aggressively so Phase 5.5 can create
        # genuine passes into space without inventing a separate hidden bonus.
        receiver_instructions = receiver.player.effective_instructions
        forward_runs = (
            float(receiver_instructions.forward_runs)
            if receiver_instructions is not None
            else 50.0
        )
        attack_space = (
            float(receiver_instructions.attack_space)
            if receiver_instructions is not None
            else 50.0
        )
        run_bias = (forward_runs + attack_space) / 200.0
        lead_factor = {
            ActionType.SHORT_PASS: 0.55,
            ActionType.PROGRESSIVE_PASS: 1.15,
            ActionType.LONG_PASS: 0.85,
        }[action_type]
        lead_seconds = min(base_travel, 2.2) * lead_factor * (0.75 + run_bias * 0.50)
        intended_target = state.pitch.clamp(
            receiver.location + receiver.velocity.scale(lead_seconds)
        )
        path = intended_target - passer.location
        path_distance = max(path.magnitude, 0.01)
        direction = path.normalized()
        perpendicular = Vector2(-direction.y, direction.x)

        error_factor = (100.0 - execution_quality) / 100.0
        action_error_scale = {
            ActionType.SHORT_PASS: 0.060,
            ActionType.PROGRESSIVE_PASS: 0.085,
            ActionType.LONG_PASS: 0.115,
        }[action_type]
        context_error = self.context.error_multiplier(
            distance_m=path_distance,
            aerial=action_type is ActionType.LONG_PASS,
        )
        max_lateral_error = (0.18 + path_distance * error_factor * action_error_scale) * context_error
        max_longitudinal_error = (0.10 + path_distance * error_factor * action_error_scale * 0.55) * context_error
        lateral_error = self.random.uniform(-max_lateral_error, max_lateral_error)
        longitudinal_error = self.random.uniform(
            -max_longitudinal_error,
            max_longitudinal_error,
        )
        actual_target = state.pitch.clamp(
            intended_target
            + perpendicular.scale(lateral_error)
            + direction.scale(longitudinal_error)
        )
        actual_distance = max(passer.location.distance_to(actual_target), 0.01)
        travel_seconds = max(actual_distance / speed, state.clock.tick_seconds)
        max_height = {
            ActionType.SHORT_PASS: 0.08,
            ActionType.PROGRESSIVE_PASS: 0.22,
            ActionType.LONG_PASS: 2.8,
        }[action_type]

        return PassExecutionProfile(
            passer_agent_id=passer.agent_id,
            receiver_agent_id=receiver.agent_id,
            action_type=action_type,
            origin=passer.location,
            intended_target=intended_target,
            actual_target=actual_target,
            distance_m=actual_distance,
            passer_pressure=perception.pressure,
            lane_openness=lane.lane_openness,
            receiver_space=lane.receiver_space,
            execution_quality=execution_quality,
            lateral_error_m=lateral_error,
            longitudinal_error_m=longitudinal_error,
            target_error_m=intended_target.distance_to(actual_target),
            ball_speed_mps=speed,
            max_height_m=max_height,
            expected_travel_seconds=travel_seconds,
        )

    def _execution_quality(
        self,
        passer: PlayerAgentState,
        action_type: ActionType,
        distance_m: float,
        pressure: float,
    ) -> float:
        technical = passer.player.attributes.technical
        mental = passer.player.attributes.mental
        fitness = passer.current_fitness
        fatigue = passer.current_fatigue
        base = (
            technical.passing * 0.40
            + technical.technique * 0.20
            + mental.composure * 0.13
            + mental.vision * 0.12
            + mental.decisions * 0.10
            + technical.first_touch * 0.05
        )
        action_penalty = {
            ActionType.SHORT_PASS: 0.0,
            ActionType.PROGRESSIVE_PASS: 3.0,
            ActionType.LONG_PASS: 5.0,
        }[action_type]
        distance_threshold = {
            ActionType.SHORT_PASS: 12.0,
            ActionType.PROGRESSIVE_PASS: 20.0,
            ActionType.LONG_PASS: 30.0,
        }[action_type]
        distance_rate = {
            ActionType.SHORT_PASS: 0.42,
            ActionType.PROGRESSIVE_PASS: 0.28,
            ActionType.LONG_PASS: 0.18,
        }[action_type]
        distance_penalty = max(0.0, distance_m - distance_threshold) * distance_rate
        pressure_penalty = pressure * 18.0
        condition_modifier = ((fitness - fatigue) - 50.0) * 0.05
        context_modifier = self.context.execution_adjustment(
            passer,
            pressure=pressure,
            distance_m=distance_m,
            aerial=action_type is ActionType.LONG_PASS,
        )
        return _clamp(
            base + condition_modifier + context_modifier - action_penalty - distance_penalty - pressure_penalty,
            5.0,
            98.0,
        )

    def _ball_speed(self, passer: PlayerAgentState, action_type: ActionType) -> float:
        base = {
            ActionType.SHORT_PASS: self.config.short_pass_speed_mps,
            ActionType.PROGRESSIVE_PASS: self.config.progressive_pass_speed_mps,
            ActionType.LONG_PASS: self.config.long_pass_speed_mps,
        }[action_type]
        instructions = self._team_tactics[passer.side].team_instructions.in_possession
        tactical_scale = 0.86 + (float(instructions.pass_speed) / 100.0) * 0.28
        technique_scale = 0.94 + (passer.player.attributes.technical.passing / 100.0) * 0.12
        return (
            base
            * tactical_scale
            * technique_scale
            * self.context.ball_speed_multiplier(aerial=action_type is ActionType.LONG_PASS)
        )

    def _try_interception(
        self,
        state: MatchState,
        segment_start: Vector2,
        segment_end: Vector2,
        profile: PassExecutionProfile,
    ) -> PlayerAgentState | None:
        passer = state.agent(profile.passer_agent_id)
        candidates: list[tuple[float, str, PlayerAgentState]] = []
        for opponent in state.active_players:
            if opponent.side is passer.side:
                continue
            distance = _distance_to_segment(opponent.location, segment_start, segment_end)
            quality = self._interception_quality(opponent)
            radius = self.config.interception_base_radius_m + quality / 100.0 * 0.78
            if distance <= radius:
                candidates.append((distance, opponent.agent_id, opponent))

        for distance, _, opponent in sorted(candidates, key=lambda item: (item[0], item[1])):
            quality = self._interception_quality(opponent)
            radius = self.config.interception_base_radius_m + quality / 100.0 * 0.78
            proximity = 1.0 - min(distance / radius, 1.0)
            probability = _clamp01(
                0.08
                + quality / 100.0 * 0.36
                + proximity * 0.38
                - profile.ball_speed_mps / 100.0
                - profile.execution_quality / 100.0 * 0.08
            )
            if self.random.random() <= probability:
                return opponent
        return None

    @staticmethod
    def _interception_quality(agent: PlayerAgentState) -> float:
        mental = agent.player.attributes.mental
        technical = agent.player.attributes.technical
        physical = agent.player.attributes.physical
        return _clamp(
            mental.anticipation * 0.26
            + mental.positioning * 0.24
            + mental.concentration * 0.18
            + technical.marking * 0.12
            + physical.agility * 0.10
            + physical.acceleration * 0.10
        )

    def _resolve_interception(
        self,
        state: MatchState,
        active: ActivePass,
        interceptor: PlayerAgentState,
    ) -> PassResult:
        state.ball.location = interceptor.location
        self._give_control(state, interceptor)
        result = PassResult(
            outcome=PassOutcome.INTERCEPTED,
            passer_agent_id=active.profile.passer_agent_id,
            intended_receiver_agent_id=active.profile.receiver_agent_id,
            controller_agent_id=interceptor.agent_id,
            action_type=active.profile.action_type,
            started_tick=active.started_tick,
            resolved_tick=state.clock.tick_count + 1,
            travel_seconds=active.elapsed_seconds,
            execution_quality=active.profile.execution_quality,
            target_error_m=active.profile.target_error_m,
            interception_agent_id=interceptor.agent_id,
        )
        self.active_pass = None
        self.last_result = result
        return result

    def _resolve_arrival(self, state: MatchState, active: ActivePass) -> PassResult:
        profile = active.profile
        receiver = state.agent(profile.receiver_agent_id)
        collector = self._endpoint_collector(state, profile, receiver)

        if collector is None:
            self._leave_ball_loose(state, profile.actual_target)
            result = PassResult(
                outcome=PassOutcome.MISPLACED,
                passer_agent_id=profile.passer_agent_id,
                intended_receiver_agent_id=profile.receiver_agent_id,
                controller_agent_id=None,
                action_type=profile.action_type,
                started_tick=active.started_tick,
                resolved_tick=state.clock.tick_count + 1,
                travel_seconds=active.elapsed_seconds,
                execution_quality=profile.execution_quality,
                target_error_m=profile.target_error_m,
            )
            self.active_pass = None
            self.last_result = result
            return result

        if collector.side is not state.agent(profile.passer_agent_id).side:
            self._give_control(state, collector)
            result = PassResult(
                outcome=PassOutcome.INTERCEPTED,
                passer_agent_id=profile.passer_agent_id,
                intended_receiver_agent_id=profile.receiver_agent_id,
                controller_agent_id=collector.agent_id,
                action_type=profile.action_type,
                started_tick=active.started_tick,
                resolved_tick=state.clock.tick_count + 1,
                travel_seconds=active.elapsed_seconds,
                execution_quality=profile.execution_quality,
                target_error_m=profile.target_error_m,
                interception_agent_id=collector.agent_id,
            )
            self.active_pass = None
            self.last_result = result
            return result

        control_quality, control_probability = self._first_touch_profile(state, collector, profile)
        if self.random.random() <= control_probability:
            self._give_control(state, collector)
            result = PassResult(
                outcome=PassOutcome.COMPLETED,
                passer_agent_id=profile.passer_agent_id,
                intended_receiver_agent_id=profile.receiver_agent_id,
                controller_agent_id=collector.agent_id,
                action_type=profile.action_type,
                started_tick=active.started_tick,
                resolved_tick=state.clock.tick_count + 1,
                travel_seconds=active.elapsed_seconds,
                execution_quality=profile.execution_quality,
                target_error_m=profile.target_error_m,
                first_touch_quality=control_quality,
                first_touch_probability=control_probability,
            )
        else:
            bounce = self._bad_touch_location(state, collector, profile)
            state.ball.last_touch_agent_id = collector.agent_id
            self._leave_ball_loose(state, bounce)
            result = PassResult(
                outcome=PassOutcome.BAD_CONTROL,
                passer_agent_id=profile.passer_agent_id,
                intended_receiver_agent_id=profile.receiver_agent_id,
                controller_agent_id=None,
                action_type=profile.action_type,
                started_tick=active.started_tick,
                resolved_tick=state.clock.tick_count + 1,
                travel_seconds=active.elapsed_seconds,
                execution_quality=profile.execution_quality,
                target_error_m=profile.target_error_m,
                first_touch_quality=control_quality,
                first_touch_probability=control_probability,
            )

        self.active_pass = None
        self.last_result = result
        return result

    def _endpoint_collector(
        self,
        state: MatchState,
        profile: PassExecutionProfile,
        intended_receiver: PlayerAgentState,
    ) -> PlayerAgentState | None:
        candidates: list[tuple[float, int, str, PlayerAgentState]] = []
        for agent in state.active_players:
            distance = agent.location.distance_to(profile.actual_target)
            radius = (
                self.config.receiver_control_radius_m
                if agent.agent_id == intended_receiver.agent_id
                else self.config.endpoint_collection_radius_m
            )
            if distance <= radius:
                intended_priority = 0 if agent.agent_id == intended_receiver.agent_id else 1
                candidates.append((distance, intended_priority, agent.agent_id, agent))
        if not candidates:
            return None
        return min(candidates, key=lambda item: (item[0], item[1], item[2]))[3]

    def _first_touch_profile(
        self,
        state: MatchState,
        receiver: PlayerAgentState,
        profile: PassExecutionProfile,
    ) -> tuple[float, float]:
        technical = receiver.player.attributes.technical
        mental = receiver.player.attributes.mental
        physical = receiver.player.attributes.physical
        pressure = self.perception.pressure_at(state, receiver.side, receiver.location)
        quality = _clamp(
            technical.first_touch * 0.42
            + technical.technique * 0.20
            + mental.composure * 0.16
            + mental.anticipation * 0.10
            + physical.balance * 0.12
            - pressure * 18.0
            - max(0.0, profile.ball_speed_mps - 16.0) * 0.35
            + self.context.first_touch_adjustment(receiver)
        )
        probability = _clamp01(
            0.35
            + quality / 100.0 * 0.72
            + profile.execution_quality / 100.0 * 0.10
            - pressure * 0.12
        )
        probability = min(max(probability, 0.20), 0.98)
        return quality, probability

    def _bad_touch_location(
        self,
        state: MatchState,
        receiver: PlayerAgentState,
        profile: PassExecutionProfile,
    ) -> Vector2:
        incoming = (profile.actual_target - profile.origin).normalized()
        perpendicular = Vector2(-incoming.y, incoming.x)
        side = -1.0 if self.random.random() < 0.5 else 1.0
        distance = self.random.uniform(1.4, 3.0)
        forward = self.random.uniform(0.3, 1.2)
        return state.pitch.clamp(
            receiver.location
            + perpendicular.scale(side * distance)
            + incoming.scale(forward)
        )

    @staticmethod
    def _validate_pass_state(
        state: MatchState,
        passer: PlayerAgentState,
        receiver: PlayerAgentState,
    ) -> None:
        if state.ball.owner_agent_id != passer.agent_id:
            raise ValueError("passer must currently own the ball")
        if state.possession.owner_agent_id != passer.agent_id:
            raise ValueError("passer must be the current possession owner")
        if state.possession.team_side is not passer.side:
            raise ValueError("possession team must match passer side")
        if not passer.is_active or not receiver.is_active:
            raise ValueError("dismissed players cannot participate in a pass")
        if receiver.side is not passer.side:
            raise ValueError("pass receiver must be a teammate")
        if receiver.agent_id == passer.agent_id:
            raise ValueError("pass receiver must be another player")

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
    def _leave_ball_loose(state: MatchState, location: Vector2) -> None:
        state.possession.team_side = None
        state.possession.owner_agent_id = None
        state.ball.owner_agent_id = None
        state.ball.location = state.pitch.clamp(location)
        state.ball.velocity = Vector2.zero()
        state.ball.height_m = 0.0
        for agent in state.players.values():
            agent.has_ball = False


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
