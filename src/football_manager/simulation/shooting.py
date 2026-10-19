from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from math import acos, exp, pi, sin

from football_manager.domain import MatchSnapshot, Position

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


def _sigmoid(value: float) -> float:
    return 1.0 / (1.0 + exp(-value))


class ShotBodyPart(StrEnum):
    FOOT = "foot"
    HEAD = "head"


class ChanceOrigin(StrEnum):
    OPEN_PLAY = "open_play"
    THROUGH_BALL = "through_ball"
    CROSS = "cross"
    CUTBACK = "cutback"
    REBOUND = "rebound"
    SET_PIECE = "set_piece"


class ShotOutcome(StrEnum):
    GOAL = "goal"
    SAVED = "saved"
    PARRIED = "parried"
    BLOCKED = "blocked"
    OFF_TARGET = "off_target"
    WOODWORK = "woodwork"


@dataclass(frozen=True, slots=True)
class ShootingConfig:
    goal_width_m: float = 7.32
    goal_height_m: float = 2.44
    post_contact_margin_m: float = 0.11
    block_base_radius_m: float = 0.72
    foot_base_speed_mps: float = 18.0
    foot_power_speed_bonus_mps: float = 13.0
    header_base_speed_mps: float = 10.5
    header_power_speed_bonus_mps: float = 8.5
    goalkeeper_goal_line_offset_m: float = 0.75


@dataclass(frozen=True, slots=True)
class ShotExecutionProfile:
    shooter_agent_id: str
    goalkeeper_agent_id: str
    body_part: ShotBodyPart
    chance_origin: ChanceOrigin
    origin: Vector2
    origin_height_m: float
    goal_x: float
    goal_centre_y: float
    intended_target_y: float
    intended_target_height_m: float
    actual_target_y: float
    actual_target_height_m: float
    distance_m: float
    shot_angle_radians: float
    pressure: float
    blocker_count: int
    xg: float
    execution_quality: float
    target_error_m: float
    shot_speed_mps: float
    expected_travel_seconds: float
    goalkeeper_quality: float
    goalkeeper_start_location: Vector2
    goalkeeper_target_location: Vector2
    goalkeeper_position_disadvantage: float
    goalkeeper_reaction_seconds: float
    transition_speed: float | None

    @property
    def actual_target(self) -> Vector2:
        return Vector2(self.goal_x, self.actual_target_y)


@dataclass(slots=True)
class ActiveShot:
    profile: ShotExecutionProfile
    started_tick: int
    elapsed_seconds: float = 0.0
    tested_blocker_ids: set[str] = field(default_factory=set)


@dataclass(frozen=True, slots=True)
class ShotResult:
    outcome: ShotOutcome
    shooter_agent_id: str
    goalkeeper_agent_id: str
    body_part: ShotBodyPart
    chance_origin: ChanceOrigin
    started_tick: int
    resolved_tick: int
    xg: float
    on_target: bool
    execution_quality: float
    target_error_m: float
    controller_agent_id: str | None = None
    blocker_agent_id: str | None = None
    save_probability: float | None = None
    rebound_location: Vector2 | None = None


class ShootingSystem:
    """Resolve chances, xG, shot flight, blocks and goalkeeper actions.

    xG estimates the *situation* before finishing quality is applied. Finishing,
    technique and composure influence shot execution and placement, while the
    goalkeeper gets a separate save resolution. This prevents xG from becoming
    a disguised player-rating bonus.
    """

    def __init__(
        self,
        snapshot: MatchSnapshot,
        random_source: MatchRandom,
        perception: PerceptionSystem | None = None,
        config: ShootingConfig | None = None,
        context: MatchContextSystem | None = None,
    ) -> None:
        self.snapshot = snapshot
        self.random = random_source
        self.perception = perception or PerceptionSystem()
        self.config = config or ShootingConfig()
        self.context = context or MatchContextSystem(snapshot)
        self.active_shot: ActiveShot | None = None
        self.last_result: ShotResult | None = None

    @property
    def is_shot_in_flight(self) -> bool:
        return self.active_shot is not None

    @property
    def active_mover_ids(self) -> frozenset[str]:
        if self.active_shot is None:
            return frozenset()
        return frozenset({self.active_shot.profile.goalkeeper_agent_id})

    def cancel(self) -> None:
        self.active_shot = None

    def start(
        self,
        state: MatchState,
        decision: PlayerDecision,
        *,
        body_part: ShotBodyPart = ShotBodyPart.FOOT,
        chance_origin: ChanceOrigin = ChanceOrigin.OPEN_PLAY,
        transition_speed: float | None = None,
    ) -> ActiveShot:
        if self.active_shot is not None:
            raise ValueError("cannot start a shot while another shot is in flight")
        if decision.action_type is not ActionType.SHOOT:
            raise ValueError("shooting system requires a shoot decision")
        if transition_speed is not None and not 0.0 <= transition_speed <= 1.0:
            raise ValueError("transition_speed must be between 0 and 1")

        shooter = state.agent(decision.agent_id)
        self._require_controlled_shooter(state, shooter)
        body_part = ShotBodyPart(body_part)
        chance_origin = ChanceOrigin(chance_origin)
        goalkeeper = self._goalkeeper(state, shooter.side.opponent)
        profile = self._build_profile(
            state,
            shooter,
            goalkeeper,
            body_part=body_part,
            chance_origin=chance_origin,
            transition_speed=transition_speed,
        )

        self.active_shot = ActiveShot(profile=profile, started_tick=state.clock.tick_count)
        self.last_result = None

        state.possession.team_side = shooter.side
        state.possession.owner_agent_id = None
        state.ball.owner_agent_id = None
        state.ball.last_touch_agent_id = shooter.agent_id
        state.ball.location = shooter.location
        state.ball.height_m = profile.origin_height_m
        state.ball.velocity = (profile.actual_target - profile.origin).normalized().scale(
            profile.shot_speed_mps
        )
        for agent in state.players.values():
            agent.has_ball = False
        return self.active_shot

    def update_goalkeeper_velocity(self, state: MatchState) -> None:
        active = self.active_shot
        if active is None:
            return
        profile = active.profile
        goalkeeper = state.agent(profile.goalkeeper_agent_id)
        if active.elapsed_seconds < profile.goalkeeper_reaction_seconds:
            goalkeeper.velocity = Vector2.zero()
            return

        delta = profile.goalkeeper_target_location - goalkeeper.location
        if delta.magnitude <= 0.05:
            goalkeeper.velocity = Vector2.zero()
            return
        speed = self._goalkeeper_movement_speed(goalkeeper)
        goalkeeper.velocity = delta.normalized().scale(speed)

    def advance(self, state: MatchState, dt: float) -> ShotResult | None:
        active = self.active_shot
        if active is None:
            return None
        if dt <= 0.0:
            raise ValueError("shot timestep must be positive")

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
        state.ball.velocity = path.normalized().scale(profile.shot_speed_mps)
        state.ball.height_m = self._shot_height(profile, progress)

        blocker = self._try_block(
            state,
            active,
            previous_location,
            state.ball.location,
        )
        if blocker is not None:
            return self._resolve_block(state, active, blocker)

        if progress < 1.0:
            return None
        return self._resolve_goal_plane(state, active)

    def save_probability(
        self,
        state: MatchState,
        profile: ShotExecutionProfile,
    ) -> float:
        goalkeeper = state.agent(profile.goalkeeper_agent_id)
        values = self._goalkeeper_values(goalkeeper)
        quality = profile.goalkeeper_quality
        horizontal_gap = abs(goalkeeper.location.y - profile.actual_target_y)
        lateral_reach = 2.20 + (values["reflexes"] + values["aerial_reach"]) / 200.0 * 2.20
        lateral_factor = _clamp01(1.0 - horizontal_gap / max(lateral_reach, 0.1))

        vertical_excess = max(profile.actual_target_height_m - 1.05, 0.0)
        vertical_reach = 1.05 + values["aerial_reach"] / 100.0 * 1.65
        vertical_factor = _clamp01(1.0 - vertical_excess / max(vertical_reach, 0.1))
        reach = lateral_factor * vertical_factor

        half_width = self.config.goal_width_m / 2.0
        cornerness_y = _clamp01(
            abs(profile.actual_target_y - profile.goal_centre_y) / max(half_width, 0.1)
        )
        cornerness_z = _clamp01(profile.actual_target_height_m / self.config.goal_height_m)
        corner_difficulty = cornerness_y * 0.55 + cornerness_z * 0.25
        speed_difficulty = _clamp01((profile.shot_speed_mps - 15.0) / 20.0)
        execution_difficulty = profile.execution_quality / 100.0

        probability = (
            0.13
            + quality / 100.0 * 0.50
            + reach * 0.35
            - corner_difficulty * 0.20
            - speed_difficulty * 0.11
            - execution_difficulty * 0.08
        )
        return min(max(probability, 0.03), 0.92)

    def _build_profile(
        self,
        state: MatchState,
        shooter: PlayerAgentState,
        goalkeeper: PlayerAgentState,
        *,
        body_part: ShotBodyPart,
        chance_origin: ChanceOrigin,
        transition_speed: float | None,
    ) -> ShotExecutionProfile:
        goal_x = state.pitch.length_m if shooter.side is TeamSide.HOME else 0.0
        goal_centre_y = state.pitch.width_m / 2.0
        goal_centre = Vector2(goal_x, goal_centre_y)
        distance = shooter.location.distance_to(goal_centre)
        angle = self._goal_angle(state, shooter)
        perception = self.perception.perceive(state, shooter.agent_id)
        pressure = perception.pressure
        blocker_count = self._blocker_count(state, shooter, goal_centre)
        gk_quality = self._goalkeeper_quality(goalkeeper)
        gk_disadvantage = self._goalkeeper_position_disadvantage(
            state,
            shooter,
            goalkeeper,
            distance,
        )
        xg = self._expected_goals(
            distance_m=distance,
            angle_radians=angle,
            pressure=pressure,
            blocker_count=blocker_count,
            body_part=body_part,
            chance_origin=chance_origin,
            goalkeeper_position_disadvantage=gk_disadvantage,
            transition_speed=transition_speed,
        )
        execution = self._execution_quality(shooter, body_part, distance, pressure)

        intended_y, intended_height = self._intended_target(
            state,
            shooter,
            goalkeeper,
            execution,
            body_part,
        )
        actual_y, actual_height = self._actual_target(
            state,
            shooter,
            intended_y,
            intended_height,
            execution,
            distance,
            body_part,
        )
        error = ((actual_y - intended_y) ** 2 + (actual_height - intended_height) ** 2) ** 0.5
        speed = self._shot_speed(shooter, body_part)
        travel = max(distance / speed, state.clock.tick_seconds)
        gk_target = Vector2(
            goal_x - shooter.side.attack_sign * self.config.goalkeeper_goal_line_offset_m,
            min(
                max(actual_y, goal_centre_y - self.config.goal_width_m / 2.0),
                goal_centre_y + self.config.goal_width_m / 2.0,
            ),
        )
        gk_values = self._goalkeeper_values(goalkeeper)
        reaction = 0.33 - gk_values["reflexes"] / 100.0 * 0.19
        origin_height = 1.45 if body_part is ShotBodyPart.HEAD else 0.14

        return ShotExecutionProfile(
            shooter_agent_id=shooter.agent_id,
            goalkeeper_agent_id=goalkeeper.agent_id,
            body_part=body_part,
            chance_origin=chance_origin,
            origin=shooter.location,
            origin_height_m=origin_height,
            goal_x=goal_x,
            goal_centre_y=goal_centre_y,
            intended_target_y=intended_y,
            intended_target_height_m=intended_height,
            actual_target_y=actual_y,
            actual_target_height_m=actual_height,
            distance_m=distance,
            shot_angle_radians=angle,
            pressure=pressure,
            blocker_count=blocker_count,
            xg=xg,
            execution_quality=execution,
            target_error_m=error,
            shot_speed_mps=speed,
            expected_travel_seconds=travel,
            goalkeeper_quality=gk_quality,
            goalkeeper_start_location=goalkeeper.location,
            goalkeeper_target_location=state.pitch.clamp(gk_target),
            goalkeeper_position_disadvantage=gk_disadvantage,
            goalkeeper_reaction_seconds=max(reaction, 0.08),
            transition_speed=transition_speed,
        )

    def _expected_goals(
        self,
        *,
        distance_m: float,
        angle_radians: float,
        pressure: float,
        blocker_count: int,
        body_part: ShotBodyPart,
        chance_origin: ChanceOrigin,
        goalkeeper_position_disadvantage: float,
        transition_speed: float | None,
    ) -> float:
        angle_normalized = _clamp01(angle_radians / (pi / 2.0))
        blocker_density = min(blocker_count / 3.0, 1.0)
        origin_modifier = {
            ChanceOrigin.OPEN_PLAY: 0.0,
            ChanceOrigin.THROUGH_BALL: 0.16,
            ChanceOrigin.CROSS: -0.16,
            ChanceOrigin.CUTBACK: 0.26,
            ChanceOrigin.REBOUND: 0.12,
            ChanceOrigin.SET_PIECE: -0.08,
        }[chance_origin]
        body_modifier = -0.42 if body_part is ShotBodyPart.HEAD else 0.0
        transition_modifier = 0.0 if transition_speed is None else (transition_speed - 0.5) * 0.34

        logit = (
            1.58
            - distance_m * 0.17
            + angle_normalized * 2.05
            - pressure * 1.12
            - blocker_density * 0.70
            + body_modifier
            + origin_modifier
            + goalkeeper_position_disadvantage * 0.62
            + transition_modifier
        )
        return min(max(_sigmoid(logit), 0.01), 0.95)

    def _execution_quality(
        self,
        shooter: PlayerAgentState,
        body_part: ShotBodyPart,
        distance_m: float,
        pressure: float,
    ) -> float:
        technical = shooter.player.attributes.technical
        mental = shooter.player.attributes.mental
        physical = shooter.player.attributes.physical
        fitness = shooter.current_fitness
        fatigue = shooter.current_fatigue

        if body_part is ShotBodyPart.HEAD:
            base = (
                technical.heading * 0.40
                + physical.jumping_reach * 0.18
                + mental.anticipation * 0.12
                + mental.bravery * 0.10
                + mental.composure * 0.10
                + technical.finishing * 0.10
            )
            distance_penalty = max(distance_m - 12.0, 0.0) * 0.48
        else:
            long_weight = _clamp01((distance_m - 14.0) / 16.0)
            finishing_weight = 0.40 - long_weight * 0.15
            long_shot_weight = 0.08 + long_weight * 0.20
            base = (
                technical.finishing * finishing_weight
                + technical.long_shots * long_shot_weight
                + technical.technique * 0.14
                + technical.shot_power * 0.10
                + mental.composure * 0.14
                + mental.decisions * 0.09
                + physical.balance * 0.05
            )
            distance_penalty = max(distance_m - 18.0, 0.0) * 0.24

        condition = ((fitness - fatigue) - 50.0) * 0.05
        context_modifier = self.context.execution_adjustment(
            shooter,
            pressure=pressure,
            distance_m=distance_m,
            aerial=body_part is ShotBodyPart.HEAD,
        )
        return _clamp(
            base + condition + context_modifier - pressure * 17.0 - distance_penalty,
            5.0,
            98.0,
        )

    def _intended_target(
        self,
        state: MatchState,
        shooter: PlayerAgentState,
        goalkeeper: PlayerAgentState,
        execution_quality: float,
        body_part: ShotBodyPart,
    ) -> tuple[float, float]:
        centre = state.pitch.width_m / 2.0
        half_width = self.config.goal_width_m / 2.0
        # Better finishers are more capable of selecting the corner away from
        # the goalkeeper instead of aiming through the middle of the goal.
        opposite_sign = 1.0 if goalkeeper.location.y <= centre else -1.0
        if self.random.random() < 0.18:
            opposite_sign *= -1.0
        corner_fraction = 0.42 + execution_quality / 100.0 * 0.43
        intended_y = centre + opposite_sign * half_width * corner_fraction

        if body_part is ShotBodyPart.HEAD:
            intended_height = self.random.uniform(0.55, 1.85)
        else:
            high_bias = 0.30 + execution_quality / 100.0 * 0.45
            intended_height = self.random.uniform(0.28, 1.15 + high_bias)
        return intended_y, intended_height

    def _actual_target(
        self,
        state: MatchState,
        shooter: PlayerAgentState,
        intended_y: float,
        intended_height: float,
        execution_quality: float,
        distance_m: float,
        body_part: ShotBodyPart,
    ) -> tuple[float, float]:
        error_factor = (100.0 - execution_quality) / 100.0
        body_multiplier = 1.18 if body_part is ShotBodyPart.HEAD else 1.0
        context_error = self.context.error_multiplier(
            distance_m=distance_m,
            aerial=body_part is ShotBodyPart.HEAD,
        )
        lateral_error = (0.25 + distance_m * error_factor * 0.095) * body_multiplier * context_error
        vertical_error = (0.18 + error_factor * 1.32) * body_multiplier * context_error
        actual_y = intended_y + self.random.uniform(-lateral_error, lateral_error)
        actual_height = max(
            0.0,
            intended_height + self.random.uniform(-vertical_error, vertical_error),
        )
        return actual_y, actual_height

    def _shot_speed(self, shooter: PlayerAgentState, body_part: ShotBodyPart) -> float:
        technical = shooter.player.attributes.technical
        physical = shooter.player.attributes.physical
        if body_part is ShotBodyPart.HEAD:
            power = (technical.heading * 0.65 + physical.jumping_reach * 0.35) / 100.0
            speed = self.config.header_base_speed_mps + power * self.config.header_power_speed_bonus_mps
            return speed * self.context.ball_speed_multiplier(aerial=True)
        power = technical.shot_power / 100.0
        speed = self.config.foot_base_speed_mps + power * self.config.foot_power_speed_bonus_mps
        return speed * self.context.ball_speed_multiplier(aerial=False)

    def _goal_angle(self, state: MatchState, shooter: PlayerAgentState) -> float:
        goal_x = state.pitch.length_m if shooter.side is TeamSide.HOME else 0.0
        centre = state.pitch.width_m / 2.0
        half = self.config.goal_width_m / 2.0
        first = Vector2(goal_x, centre - half) - shooter.location
        second = Vector2(goal_x, centre + half) - shooter.location
        denominator = max(first.magnitude * second.magnitude, 1e-9)
        cosine = (first.x * second.x + first.y * second.y) / denominator
        return acos(min(max(cosine, -1.0), 1.0))

    def _blocker_count(
        self,
        state: MatchState,
        shooter: PlayerAgentState,
        goal_centre: Vector2,
    ) -> int:
        count = 0
        for opponent in state.active_players:
            if opponent.side is shooter.side or opponent.assigned_position is Position.GK:
                continue
            progress = (opponent.location.x - shooter.location.x) * shooter.side.attack_sign
            if progress <= 0.0:
                continue
            if _distance_to_segment(opponent.location, shooter.location, goal_centre) <= 2.2:
                count += 1
        return count

    def _try_block(
        self,
        state: MatchState,
        active: ActiveShot,
        segment_start: Vector2,
        segment_end: Vector2,
    ) -> PlayerAgentState | None:
        profile = active.profile
        shooter = state.agent(profile.shooter_agent_id)
        candidates: list[tuple[float, str, PlayerAgentState]] = []
        for opponent in state.active_players:
            if opponent.side is shooter.side or opponent.assigned_position is Position.GK:
                continue
            if opponent.agent_id in active.tested_blocker_ids:
                continue
            distance = _distance_to_segment(opponent.location, segment_start, segment_end)
            if distance <= self.config.block_base_radius_m:
                candidates.append((distance, opponent.agent_id, opponent))

        for distance, _, opponent in sorted(candidates, key=lambda item: (item[0], item[1])):
            active.tested_blocker_ids.add(opponent.agent_id)
            technical = opponent.player.attributes.technical
            mental = opponent.player.attributes.mental
            physical = opponent.player.attributes.physical
            block_quality = _clamp(
                technical.tackling * 0.20
                + mental.anticipation * 0.22
                + mental.positioning * 0.20
                + mental.bravery * 0.15
                + physical.agility * 0.11
                + physical.jumping_reach * 0.12
            )
            proximity = 1.0 - min(distance / self.config.block_base_radius_m, 1.0)
            height_difficulty = _clamp01((state.ball.height_m - 0.55) / 2.2)
            speed_difficulty = _clamp01((profile.shot_speed_mps - 17.0) / 16.0)
            probability = (
                0.08
                + block_quality / 100.0 * 0.34
                + proximity * 0.35
                - height_difficulty * 0.18
                - speed_difficulty * 0.12
            )
            if self.random.random() <= min(max(probability, 0.03), 0.86):
                return opponent
        return None

    def _resolve_block(
        self,
        state: MatchState,
        active: ActiveShot,
        blocker: PlayerAgentState,
    ) -> ShotResult:
        profile = active.profile
        shooter = state.agent(profile.shooter_agent_id)
        field_direction = Vector2(-shooter.side.attack_sign, 0.0)
        side = -1.0 if self.random.random() < 0.5 else 1.0
        rebound = state.pitch.clamp(
            blocker.location
            + field_direction.scale(self.random.uniform(0.6, 2.4))
            + Vector2(0.0, side * self.random.uniform(0.3, 1.8))
        )
        self._leave_ball_loose(state, rebound, last_touch=blocker.agent_id)
        result = ShotResult(
            outcome=ShotOutcome.BLOCKED,
            shooter_agent_id=profile.shooter_agent_id,
            goalkeeper_agent_id=profile.goalkeeper_agent_id,
            body_part=profile.body_part,
            chance_origin=profile.chance_origin,
            started_tick=active.started_tick,
            resolved_tick=state.clock.tick_count + 1,
            xg=profile.xg,
            on_target=False,
            execution_quality=profile.execution_quality,
            target_error_m=profile.target_error_m,
            blocker_agent_id=blocker.agent_id,
            rebound_location=rebound,
        )
        self.active_shot = None
        self.last_result = result
        return result

    def _resolve_goal_plane(self, state: MatchState, active: ActiveShot) -> ShotResult:
        profile = active.profile
        state.ball.velocity = Vector2.zero()
        centre = profile.goal_centre_y
        half = self.config.goal_width_m / 2.0
        lateral_edge_gap = abs(abs(profile.actual_target_y - centre) - half)
        bar_gap = abs(profile.actual_target_height_m - self.config.goal_height_m)
        within_lateral_bar_span = abs(profile.actual_target_y - centre) <= half + self.config.post_contact_margin_m
        within_vertical_post_span = profile.actual_target_height_m <= self.config.goal_height_m + self.config.post_contact_margin_m

        hits_post = (
            lateral_edge_gap <= self.config.post_contact_margin_m
            and within_vertical_post_span
        )
        hits_bar = (
            bar_gap <= self.config.post_contact_margin_m
            and within_lateral_bar_span
        )
        if hits_post or hits_bar:
            return self._resolve_woodwork(state, active)

        on_target = (
            centre - half < profile.actual_target_y < centre + half
            and 0.0 <= profile.actual_target_height_m < self.config.goal_height_m
        )
        if not on_target:
            self._clear_control(state)
            state.ball.location = state.pitch.clamp(profile.actual_target)
            state.ball.height_m = max(profile.actual_target_height_m, 0.0)
            result = self._base_result(
                active,
                ShotOutcome.OFF_TARGET,
                resolved_tick=state.clock.tick_count + 1,
                on_target=False,
            )
            self.active_shot = None
            self.last_result = result
            return result

        save_probability = self.save_probability(state, profile)
        goalkeeper = state.agent(profile.goalkeeper_agent_id)
        if self.random.random() <= save_probability:
            hold_probability = self._hold_probability(goalkeeper, profile)
            if self.random.random() <= hold_probability:
                self._give_control(state, goalkeeper)
                result = self._base_result(
                    active,
                    ShotOutcome.SAVED,
                    resolved_tick=state.clock.tick_count + 1,
                    on_target=True,
                    controller_agent_id=goalkeeper.agent_id,
                    save_probability=save_probability,
                )
            else:
                rebound = self._goalkeeper_rebound(state, profile, goalkeeper)
                self._leave_ball_loose(state, rebound, last_touch=goalkeeper.agent_id)
                result = self._base_result(
                    active,
                    ShotOutcome.PARRIED,
                    resolved_tick=state.clock.tick_count + 1,
                    on_target=True,
                    save_probability=save_probability,
                    rebound_location=rebound,
                )
        else:
            self._clear_control(state)
            state.ball.location = state.pitch.clamp(profile.actual_target)
            state.ball.height_m = max(profile.actual_target_height_m, 0.0)
            result = self._base_result(
                active,
                ShotOutcome.GOAL,
                resolved_tick=state.clock.tick_count + 1,
                on_target=True,
                save_probability=save_probability,
            )

        self.active_shot = None
        self.last_result = result
        return result

    def _resolve_woodwork(self, state: MatchState, active: ActiveShot) -> ShotResult:
        profile = active.profile
        shooter = state.agent(profile.shooter_agent_id)
        direction = Vector2(-shooter.side.attack_sign, 0.0)
        side = -1.0 if profile.actual_target_y <= profile.goal_centre_y else 1.0
        rebound = state.pitch.clamp(
            Vector2(profile.goal_x, profile.actual_target_y)
            + direction.scale(self.random.uniform(2.0, 6.0))
            + Vector2(0.0, side * self.random.uniform(-1.2, 1.2))
        )
        self._leave_ball_loose(state, rebound, last_touch=profile.shooter_agent_id)
        result = self._base_result(
            active,
            ShotOutcome.WOODWORK,
            resolved_tick=state.clock.tick_count + 1,
            on_target=False,
            rebound_location=rebound,
        )
        self.active_shot = None
        self.last_result = result
        return result

    def _base_result(
        self,
        active: ActiveShot,
        outcome: ShotOutcome,
        *,
        resolved_tick: int,
        on_target: bool,
        controller_agent_id: str | None = None,
        save_probability: float | None = None,
        rebound_location: Vector2 | None = None,
    ) -> ShotResult:
        profile = active.profile
        return ShotResult(
            outcome=outcome,
            shooter_agent_id=profile.shooter_agent_id,
            goalkeeper_agent_id=profile.goalkeeper_agent_id,
            body_part=profile.body_part,
            chance_origin=profile.chance_origin,
            started_tick=active.started_tick,
            resolved_tick=resolved_tick,
            xg=profile.xg,
            on_target=on_target,
            execution_quality=profile.execution_quality,
            target_error_m=profile.target_error_m,
            controller_agent_id=controller_agent_id,
            save_probability=save_probability,
            rebound_location=rebound_location,
        )

    def _hold_probability(
        self,
        goalkeeper: PlayerAgentState,
        profile: ShotExecutionProfile,
    ) -> float:
        values = self._goalkeeper_values(goalkeeper)
        speed = _clamp01((profile.shot_speed_mps - 15.0) / 20.0)
        height = _clamp01(profile.actual_target_height_m / self.config.goal_height_m)
        probability = (
            0.22
            + values["handling"] / 100.0 * 0.58
            + goalkeeper.player.attributes.mental.composure / 100.0 * 0.12
            - speed * 0.17
            - height * 0.08
        )
        return min(max(probability, 0.10), 0.92)

    def _goalkeeper_rebound(
        self,
        state: MatchState,
        profile: ShotExecutionProfile,
        goalkeeper: PlayerAgentState,
    ) -> Vector2:
        shooter = state.agent(profile.shooter_agent_id)
        field_direction = Vector2(-shooter.side.attack_sign, 0.0)
        lateral = -1.0 if self.random.random() < 0.5 else 1.0
        return state.pitch.clamp(
            goalkeeper.location
            + field_direction.scale(self.random.uniform(2.2, 5.8))
            + Vector2(0.0, lateral * self.random.uniform(0.7, 3.4))
        )

    def _shot_height(self, profile: ShotExecutionProfile, progress: float) -> float:
        direct = (
            profile.origin_height_m * (1.0 - progress)
            + profile.actual_target_height_m * progress
        )
        arc = (0.18 if profile.body_part is ShotBodyPart.HEAD else 0.30) * 4.0 * progress * (1.0 - progress)
        return max(direct + arc, 0.0)

    def _goalkeeper_position_disadvantage(
        self,
        state: MatchState,
        shooter: PlayerAgentState,
        goalkeeper: PlayerAgentState,
        shot_distance: float,
    ) -> float:
        goal_x = state.pitch.length_m if shooter.side is TeamSide.HOME else 0.0
        centre_y = state.pitch.width_m / 2.0
        ideal_depth = min(max(0.8 + (22.0 - min(shot_distance, 22.0)) * 0.07, 0.8), 2.2)
        ideal = Vector2(
            goal_x - shooter.side.attack_sign * ideal_depth,
            centre_y + (shooter.location.y - centre_y) * 0.10,
        )
        return _clamp01(goalkeeper.location.distance_to(ideal) / 9.0)

    def _goalkeeper_quality(self, goalkeeper: PlayerAgentState) -> float:
        values = self._goalkeeper_values(goalkeeper)
        mental = goalkeeper.player.attributes.mental
        return _clamp(
            values["reflexes"] * 0.28
            + values["goalkeeper_positioning"] * 0.23
            + values["one_on_ones"] * 0.18
            + values["handling"] * 0.11
            + values["aerial_reach"] * 0.08
            + mental.concentration * 0.07
            + mental.composure * 0.05
        )

    def _goalkeeper_movement_speed(self, goalkeeper: PlayerAgentState) -> float:
        values = self._goalkeeper_values(goalkeeper)
        physical = goalkeeper.player.attributes.physical
        score = (
            values["reflexes"] * 0.42
            + physical.agility * 0.33
            + physical.acceleration * 0.25
        ) / 100.0
        base = 3.1 + score * 3.5
        return base * self.context.movement_speed_multiplier(goalkeeper)

    @staticmethod
    def _goalkeeper_values(goalkeeper: PlayerAgentState) -> dict[str, float]:
        goalkeeping = goalkeeper.player.attributes.goalkeeping
        if goalkeeping is not None:
            return {
                "reflexes": float(goalkeeping.reflexes),
                "handling": float(goalkeeping.handling),
                "one_on_ones": float(goalkeeping.one_on_ones),
                "aerial_reach": float(goalkeeping.aerial_reach),
                "goalkeeper_positioning": float(goalkeeping.goalkeeper_positioning),
            }

        # Backward-compatible fallback for early test/demo data that predates
        # explicit goalkeeper attributes. Real goalkeeper data should provide
        # the dedicated attribute group.
        technical = goalkeeper.player.attributes.technical
        mental = goalkeeper.player.attributes.mental
        physical = goalkeeper.player.attributes.physical
        return {
            "reflexes": mental.anticipation * 0.45 + physical.agility * 0.55,
            "handling": technical.first_touch * 0.45 + mental.composure * 0.55,
            "one_on_ones": mental.positioning * 0.40 + mental.decisions * 0.30 + physical.agility * 0.30,
            "aerial_reach": physical.jumping_reach * 0.70 + physical.agility * 0.30,
            "goalkeeper_positioning": mental.positioning * 0.60 + mental.anticipation * 0.40,
        }

    @staticmethod
    def _goalkeeper(state: MatchState, side: TeamSide) -> PlayerAgentState:
        candidates = [
            agent
            for agent in state.active_players
            if agent.side is side and agent.assigned_position is Position.GK
        ]
        if len(candidates) != 1:
            raise ValueError("shooting requires exactly one active goalkeeper per side")
        return candidates[0]

    @staticmethod
    def _require_controlled_shooter(
        state: MatchState,
        shooter: PlayerAgentState,
    ) -> None:
        if not shooter.is_active:
            raise ValueError("dismissed player cannot shoot")
        if state.ball.owner_agent_id != shooter.agent_id:
            raise ValueError("shot requires the shooter to control the ball")
        if state.possession.owner_agent_id != shooter.agent_id:
            raise ValueError("shot requires synchronized controlled possession")
        if state.possession.team_side is not shooter.side:
            raise ValueError("shot possession team must match the shooter")

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
    def _clear_control(state: MatchState) -> None:
        state.possession.team_side = None
        state.possession.owner_agent_id = None
        state.ball.owner_agent_id = None
        for agent in state.players.values():
            agent.has_ball = False

    def _leave_ball_loose(
        self,
        state: MatchState,
        location: Vector2,
        *,
        last_touch: str,
    ) -> None:
        self._clear_control(state)
        state.ball.location = state.pitch.clamp(location)
        state.ball.velocity = Vector2.zero()
        state.ball.height_m = 0.0
        state.ball.last_touch_agent_id = last_touch


def _distance_to_segment(point: Vector2, start: Vector2, end: Vector2) -> float:
    segment = end - start
    length_sq = segment.x * segment.x + segment.y * segment.y
    if length_sq <= 1e-12:
        return point.distance_to(start)
    relative = point - start
    projection = (relative.x * segment.x + relative.y * segment.y) / length_sq
    projection = min(max(projection, 0.0), 1.0)
    closest = start + segment.scale(projection)
    return point.distance_to(closest)
