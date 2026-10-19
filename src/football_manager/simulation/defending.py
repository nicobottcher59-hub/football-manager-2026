from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from football_manager.domain import (
    Foot,
    ForceDirection,
    MarkingStyle,
    MatchSnapshot,
    PlayerInstructions,
    PressingScheme,
    TacticalTarget as DomainTacticalTarget,
    TargetKind,
)

from .geometry import Vector2
from .match_context_effects import MatchContextSystem
from .randomness import MatchRandom
from .spatial_state import MatchState, PlayerAgentState, TeamSide


def _clamp(value: float, minimum: float = 0.0, maximum: float = 100.0) -> float:
    return min(max(value, minimum), maximum)


def _clamp01(value: float) -> float:
    return min(max(value, 0.0), 1.0)


class DefensiveDuelOutcome(StrEnum):
    DEFENDER_CONTROL = "defender_control"
    ATTACKER_RETAINS = "attacker_retains"
    LOOSE_BALL = "loose_ball"


@dataclass(frozen=True, slots=True)
class PressingAssignment:
    defender_agent_id: str
    target_agent_id: str
    distance_m: float
    priority: float
    pressing_intensity: float
    closing_speed_mps: float
    approach_target: Vector2
    primary: bool = False


@dataclass(frozen=True, slots=True)
class CoverageAssignment:
    defender_agent_id: str
    target_agent_id: str
    target_location: Vector2
    marking_strength: float
    explicit_mark: bool


@dataclass(frozen=True, slots=True)
class PressingPlan:
    defending_side: TeamSide
    ball_carrier_agent_id: str | None
    pressing_assignments: tuple[PressingAssignment, ...] = ()
    coverage_assignments: tuple[CoverageAssignment, ...] = ()

    @property
    def primary(self) -> PressingAssignment | None:
        return self.pressing_assignments[0] if self.pressing_assignments else None


@dataclass(frozen=True, slots=True)
class DefensiveDuelProfile:
    defender_agent_id: str
    attacker_agent_id: str
    distance_m: float
    defender_quality: float
    attacker_resistance: float
    support: float
    front_position_value: float
    tackle_willingness: float
    success_probability: float
    clean_control_probability: float


@dataclass(frozen=True, slots=True)
class DefensiveDuelResult:
    outcome: DefensiveDuelOutcome
    defender_agent_id: str
    attacker_agent_id: str
    controller_agent_id: str | None
    success_probability: float
    clean_control_probability: float
    resolved_tick: int
    loose_ball_location: Vector2 | None = None


@dataclass(frozen=True, slots=True)
class DefendingConfig:
    base_press_radius_m: float = 10.0
    max_press_radius_m: float = 22.0
    base_press_speed_mps: float = 4.2
    max_press_speed_mps: float = 7.4
    press_arrival_radius_m: float = 0.85
    coverage_ball_radius_m: float = 30.0
    coverage_goal_side_offset_m: float = 1.4
    tackle_radius_m: float = 1.85
    support_radius_m: float = 6.0
    broken_press_distance_m: float = 4.0
    broken_press_progress_m: float = 2.0

    def __post_init__(self) -> None:
        positive = (
            "base_press_radius_m",
            "max_press_radius_m",
            "base_press_speed_mps",
            "max_press_speed_mps",
            "press_arrival_radius_m",
            "coverage_ball_radius_m",
            "coverage_goal_side_offset_m",
            "tackle_radius_m",
            "support_radius_m",
            "broken_press_distance_m",
            "broken_press_progress_m",
        )
        for name in positive:
            if getattr(self, name) <= 0.0:
                raise ValueError(f"{name} must be positive")
        if self.max_press_radius_m < self.base_press_radius_m:
            raise ValueError("max_press_radius_m cannot be smaller than base_press_radius_m")
        if self.max_press_speed_mps < self.base_press_speed_mps:
            raise ValueError("max_press_speed_mps cannot be smaller than base_press_speed_mps")


class DefendingSystem:
    """Spatial pressing, coverage and defensive-duel foundation.

    Phase 5.4 makes out-of-possession instructions alter where defenders move and
    how willing they are to engage. Pressing is a movement/decision preference;
    tackle success is resolved separately from that preference.
    """

    def __init__(
        self,
        snapshot: MatchSnapshot,
        random_source: MatchRandom,
        config: DefendingConfig | None = None,
        context: MatchContextSystem | None = None,
    ) -> None:
        self.snapshot = snapshot
        self.random = random_source
        self.config = config or DefendingConfig()
        self.context = context or MatchContextSystem(snapshot)
        self._team_tactics = {
            TeamSide.HOME: snapshot.home_team.tactic,
            TeamSide.AWAY: snapshot.away_team.tactic,
        }

    def plan(self, state: MatchState, defending_side: TeamSide) -> PressingPlan:
        defending_side = TeamSide(defending_side)
        carrier = self._controlled_opponent(state, defending_side)
        if carrier is None:
            return PressingPlan(defending_side=defending_side, ball_carrier_agent_id=None)

        out = self._team_tactics[defending_side].team_instructions.out_of_possession
        team_intensity = float(out.pressing_intensity)
        scheme = out.pressing_scheme
        radius = self._press_radius(team_intensity, scheme)
        maximum_pressers = self._maximum_pressers(team_intensity, scheme)

        ranked: list[tuple[float, float, str, PlayerAgentState]] = []
        for defender in state.active_players:
            if defender.side is not defending_side:
                continue
            if defender.assigned_position.value == "GK":
                continue
            distance = defender.location.distance_to(carrier.location)
            if distance > radius:
                continue
            priority = self._press_priority(
                state,
                defender,
                carrier,
                distance_m=distance,
                team_intensity=team_intensity,
                scheme=scheme,
            )
            ranked.append((-priority, distance, defender.agent_id, defender))

        ranked.sort(key=lambda item: (item[0], item[1], item[2]))
        chosen = [item[3] for item in ranked[:maximum_pressers]]
        assignments: list[PressingAssignment] = []
        force_direction = self._effective_force_direction(out.force_direction, scheme)
        for index, defender in enumerate(chosen):
            distance = defender.location.distance_to(carrier.location)
            priority = -next(item[0] for item in ranked if item[3].agent_id == defender.agent_id)
            individual = self._instructions(defender)
            effective_intensity = _clamp(team_intensity * 0.58 + float(individual.pressing_intensity) * 0.42)
            speed = self._closing_speed(defender, effective_intensity)
            approach_target = self._press_approach_target(
                state,
                carrier,
                force_direction,
                primary=index == 0,
            )
            assignments.append(
                PressingAssignment(
                    defender_agent_id=defender.agent_id,
                    target_agent_id=carrier.agent_id,
                    distance_m=distance,
                    priority=priority,
                    pressing_intensity=effective_intensity,
                    closing_speed_mps=speed,
                    approach_target=approach_target,
                    primary=index == 0,
                )
            )

        coverage = self._coverage_assignments(
            state,
            defending_side,
            carrier,
            excluded_defender_ids={item.defender_agent_id for item in assignments},
        )
        return PressingPlan(
            defending_side=defending_side,
            ball_carrier_agent_id=carrier.agent_id,
            pressing_assignments=tuple(assignments),
            coverage_assignments=coverage,
        )

    def update_defensive_velocities(
        self,
        state: MatchState,
        *,
        excluded_agent_ids: frozenset[str] = frozenset(),
    ) -> tuple[PressingPlan, ...]:
        plans: list[PressingPlan] = []
        for side in (TeamSide.HOME, TeamSide.AWAY):
            plan = self.plan(state, side)
            plans.append(plan)

            for assignment in plan.pressing_assignments:
                if assignment.defender_agent_id in excluded_agent_ids:
                    continue
                defender = state.agent(assignment.defender_agent_id)
                self._move_toward(
                    defender,
                    assignment.approach_target,
                    assignment.closing_speed_mps,
                )

            pressing_ids = {item.defender_agent_id for item in plan.pressing_assignments}
            for coverage in plan.coverage_assignments:
                if coverage.defender_agent_id in excluded_agent_ids:
                    continue
                if coverage.defender_agent_id in pressing_ids:
                    continue
                defender = state.agent(coverage.defender_agent_id)
                speed = self._coverage_speed(defender)
                # Coverage influences an existing off-ball trajectory instead of
                # replacing it wholesale.  A defender should be able to hold the
                # line, hand over a runner and recover shape while respecting a
                # marking responsibility; only an explicit man-mark approaches a
                # near-hard override.
                delta = coverage.target_location - defender.location
                if delta.magnitude <= 0.30:
                    continue
                desired = delta.normalized().scale(speed)
                blend = 0.28 + coverage.marking_strength * 0.42
                if coverage.explicit_mark:
                    blend = max(blend, 0.82)
                defender.velocity = defender.velocity.scale(1.0 - blend) + desired.scale(blend)

        return tuple(plans)

    def duel_profile(self, state: MatchState, defender_agent_id: str) -> DefensiveDuelProfile:
        defender = state.agent(defender_agent_id)
        if not defender.is_active:
            raise ValueError("dismissed defender cannot attempt a tackle")
        attacker = self._require_opposing_ball_carrier(state, defender)
        distance = defender.location.distance_to(attacker.location)
        if distance > self.config.tackle_radius_m:
            raise ValueError("defender is too far away to attempt a tackle")

        defender_quality = _clamp(
            self._defender_duel_quality(defender)
            + self.context.execution_adjustment(defender)
        )
        attacker_resistance = _clamp(
            self._attacker_duel_resistance(attacker)
            + self.context.execution_adjustment(attacker)
        )
        support = self._support_value(state, defender, attacker)
        front_position = self._front_position_value(defender, attacker)
        willingness = self._tackle_willingness(defender)

        probability = _clamp01(
            0.46
            + (defender_quality - attacker_resistance) * 0.0042
            + support * 0.10
            + ((front_position - 50.0) / 100.0) * 0.14
            - max(distance - 0.8, 0.0) * 0.045
        )
        probability = min(max(probability, 0.10), 0.90)

        technical = defender.player.attributes.technical
        mental = defender.player.attributes.mental
        physical = defender.player.attributes.physical
        clean_control = _clamp01(
            0.34
            + technical.tackling / 100.0 * 0.24
            + mental.composure / 100.0 * 0.10
            + mental.anticipation / 100.0 * 0.08
            + physical.balance / 100.0 * 0.10
            + support * 0.08
        )
        clean_control = min(max(clean_control, 0.25), 0.90)

        return DefensiveDuelProfile(
            defender_agent_id=defender.agent_id,
            attacker_agent_id=attacker.agent_id,
            distance_m=distance,
            defender_quality=defender_quality,
            attacker_resistance=attacker_resistance,
            support=support,
            front_position_value=front_position,
            tackle_willingness=willingness,
            success_probability=probability,
            clean_control_probability=clean_control,
        )

    def attempt_tackle(self, state: MatchState, defender_agent_id: str) -> DefensiveDuelResult:
        profile = self.duel_profile(state, defender_agent_id)
        defender = state.agent(profile.defender_agent_id)
        attacker = state.agent(profile.attacker_agent_id)

        if self.random.random() > profile.success_probability:
            return DefensiveDuelResult(
                outcome=DefensiveDuelOutcome.ATTACKER_RETAINS,
                defender_agent_id=defender.agent_id,
                attacker_agent_id=attacker.agent_id,
                controller_agent_id=attacker.agent_id,
                success_probability=profile.success_probability,
                clean_control_probability=profile.clean_control_probability,
                resolved_tick=state.clock.tick_count,
            )

        if self.random.random() <= profile.clean_control_probability:
            self._give_control(state, defender)
            return DefensiveDuelResult(
                outcome=DefensiveDuelOutcome.DEFENDER_CONTROL,
                defender_agent_id=defender.agent_id,
                attacker_agent_id=attacker.agent_id,
                controller_agent_id=defender.agent_id,
                success_probability=profile.success_probability,
                clean_control_probability=profile.clean_control_probability,
                resolved_tick=state.clock.tick_count,
            )

        loose_location = self._duel_loose_ball_location(state, defender, attacker)
        self._leave_ball_loose(state, loose_location, last_touch=defender.agent_id)
        return DefensiveDuelResult(
            outcome=DefensiveDuelOutcome.LOOSE_BALL,
            defender_agent_id=defender.agent_id,
            attacker_agent_id=attacker.agent_id,
            controller_agent_id=None,
            success_probability=profile.success_probability,
            clean_control_probability=profile.clean_control_probability,
            resolved_tick=state.clock.tick_count,
            loose_ball_location=loose_location,
        )

    def press_is_broken(self, state: MatchState, plan: PressingPlan) -> bool:
        primary = plan.primary
        if primary is None or plan.ball_carrier_agent_id is None:
            return False
        if state.ball.owner_agent_id != plan.ball_carrier_agent_id:
            return False

        carrier = state.agent(plan.ball_carrier_agent_id)
        defender = state.agent(primary.defender_agent_id)
        distance = defender.location.distance_to(carrier.location)
        progress_beyond = (
            carrier.location.x - defender.location.x
        ) * carrier.side.attack_sign
        if distance < self.config.broken_press_distance_m:
            return False
        if progress_beyond < self.config.broken_press_progress_m:
            return False

        for assignment in plan.pressing_assignments[1:]:
            supporter = state.agent(assignment.defender_agent_id)
            if supporter.location.distance_to(carrier.location) < self.config.broken_press_distance_m:
                return False
        return True

    def _press_priority(
        self,
        state: MatchState,
        defender: PlayerAgentState,
        carrier: PlayerAgentState,
        *,
        distance_m: float,
        team_intensity: float,
        scheme: PressingScheme,
    ) -> float:
        instructions = self._instructions(defender)
        mental = defender.player.attributes.mental
        physical = defender.player.attributes.physical
        distance_score = _clamp(100.0 - distance_m * 5.0)
        target_bonus = 35.0 if self._target_matches(instructions.pressing_target, carrier) else 0.0
        scheme_bonus = 0.0
        if scheme is PressingScheme.CONSTANT:
            scheme_bonus = 12.0
        elif scheme is PressingScheme.MAN_ORIENTED:
            scheme_bonus = 6.0
        elif scheme is PressingScheme.ZONAL:
            scheme_bonus = -3.0

        return _clamp(
            distance_score * 0.43
            + float(instructions.pressing_intensity) * 0.22
            + team_intensity * 0.10
            + mental.work_rate * 0.09
            + mental.aggression * 0.06
            + mental.anticipation * 0.05
            + physical.acceleration * 0.05
            + target_bonus
            + scheme_bonus
        )

    def _coverage_assignments(
        self,
        state: MatchState,
        defending_side: TeamSide,
        carrier: PlayerAgentState,
        *,
        excluded_defender_ids: set[str],
    ) -> tuple[CoverageAssignment, ...]:
        out = self._team_tactics[defending_side].team_instructions.out_of_possession
        candidates = [
            agent
            for agent in state.active_players
            if agent.side is defending_side
            and agent.agent_id not in excluded_defender_ids
            and agent.assigned_position.value != "GK"
        ]
        opponents = [
            agent
            for agent in state.active_players
            if agent.side is carrier.side
            and agent.agent_id != carrier.agent_id
            and agent.location.distance_to(carrier.location) <= self.config.coverage_ball_radius_m
        ]
        if not candidates or not opponents:
            return ()

        # Explicit individual marking targets get first claim on their requested opponent.
        assignments: list[CoverageAssignment] = []
        used_defenders: set[str] = set()
        used_targets: set[str] = set()
        for defender in sorted(candidates, key=lambda item: item.agent_id):
            instructions = self._instructions(defender)
            if instructions.marking is None:
                continue
            matches = [opponent for opponent in opponents if self._target_matches(instructions.marking, opponent)]
            if not matches:
                continue
            opponent = min(matches, key=lambda item: defender.location.distance_to(item.location))
            assignments.append(
                self._coverage_assignment(
                    state,
                    defender,
                    opponent,
                    style=out.marking_style,
                    explicit=True,
                )
            )
            used_defenders.add(defender.agent_id)
            used_targets.add(opponent.agent_id)

        remaining_defenders = [item for item in candidates if item.agent_id not in used_defenders]
        remaining_opponents = [item for item in opponents if item.agent_id not in used_targets]
        danger_sorted = sorted(
            remaining_opponents,
            key=lambda item: (
                -self._opponent_danger(state, defending_side, carrier, item),
                item.agent_id,
            ),
        )

        max_coverage = {
            MarkingStyle.ZONAL: 2,
            MarkingStyle.MIXED: 3,
            MarkingStyle.MAN: 4,
        }[out.marking_style]
        for opponent in danger_sorted:
            if len(assignments) >= max_coverage:
                break
            if not remaining_defenders:
                break
            defender = min(
                remaining_defenders,
                key=lambda item: (item.location.distance_to(opponent.location), item.agent_id),
            )
            assignments.append(
                self._coverage_assignment(
                    state,
                    defender,
                    opponent,
                    style=out.marking_style,
                    explicit=False,
                )
            )
            remaining_defenders.remove(defender)

        assignments.sort(key=lambda item: (item.defender_agent_id, item.target_agent_id))
        return tuple(assignments)

    def _coverage_assignment(
        self,
        state: MatchState,
        defender: PlayerAgentState,
        opponent: PlayerAgentState,
        *,
        style: MarkingStyle,
        explicit: bool,
    ) -> CoverageAssignment:
        instructions = self._instructions(defender)
        base_strength = {
            MarkingStyle.ZONAL: 0.24,
            MarkingStyle.MIXED: 0.52,
            MarkingStyle.MAN: 0.78,
        }[style]
        tracking_adjustment = ((float(instructions.defensive_tracking) - 50.0) / 50.0) * 0.12
        strength = min(max(base_strength + tracking_adjustment + (0.16 if explicit else 0.0), 0.12), 0.96)

        own_goal = Vector2(
            0.0 if defender.side is TeamSide.HOME else state.pitch.length_m,
            state.pitch.width_m / 2.0,
        )
        goal_side = (own_goal - opponent.location).normalized()
        mark_point = state.pitch.clamp(
            opponent.location + goal_side.scale(self.config.coverage_goal_side_offset_m)
        )
        tactical = defender.tactical_target or defender.location
        target = state.pitch.clamp(
            tactical.scale(1.0 - strength) + mark_point.scale(strength)
        )
        return CoverageAssignment(
            defender_agent_id=defender.agent_id,
            target_agent_id=opponent.agent_id,
            target_location=target,
            marking_strength=strength,
            explicit_mark=explicit,
        )

    def _opponent_danger(
        self,
        state: MatchState,
        defending_side: TeamSide,
        carrier: PlayerAgentState,
        opponent: PlayerAgentState,
    ) -> float:
        distance_to_ball = carrier.location.distance_to(opponent.location)
        attacking_goal_x = state.pitch.length_m if carrier.side is TeamSide.HOME else 0.0
        distance_to_goal = abs(attacking_goal_x - opponent.location.x)
        return _clamp(
            100.0
            - min(distance_to_ball, 30.0) * 1.6
            - min(distance_to_goal, state.pitch.length_m) * 0.20
        )

    def _press_approach_target(
        self,
        state: MatchState,
        carrier: PlayerAgentState,
        force_direction: ForceDirection,
        *,
        primary: bool,
    ) -> Vector2:
        offset = 1.25 if primary else 1.75
        y_offset = 0.0
        centre_y = state.pitch.width_m / 2.0
        toward_centre = 1.0 if carrier.location.y < centre_y else -1.0

        if force_direction is ForceDirection.OUTSIDE:
            # Stand on the central side of the ball carrier to shepherd play wide.
            y_offset = toward_centre * offset
        elif force_direction is ForceDirection.INSIDE:
            # Stand on the touchline side to shepherd the carrier inward.
            y_offset = -toward_centre * offset
        elif force_direction is ForceDirection.WEAK_FOOT:
            foot = carrier.player.dominant_foot
            if foot is Foot.RIGHT:
                y_offset = carrier.side.attack_sign * offset
            elif foot is Foot.LEFT:
                y_offset = -carrier.side.attack_sign * offset

        # Slightly goal-side of the carrier avoids all pressers chasing the exact
        # same coordinate and creates a more football-like pressure angle.
        x_offset = carrier.side.attack_sign * (0.65 if primary else 0.25)
        return state.pitch.clamp(carrier.location + Vector2(x_offset, y_offset))

    def _press_radius(self, team_intensity: float, scheme: PressingScheme) -> float:
        scale = team_intensity / 100.0
        radius = self.config.base_press_radius_m + (
            self.config.max_press_radius_m - self.config.base_press_radius_m
        ) * scale
        if scheme is PressingScheme.CONSTANT:
            radius += 4.0
        elif scheme is PressingScheme.ZONAL:
            radius -= 1.5
        return max(radius, self.config.base_press_radius_m * 0.75)

    @staticmethod
    def _maximum_pressers(team_intensity: float, scheme: PressingScheme) -> int:
        if team_intensity >= 88.0:
            count = 3
        elif team_intensity >= 62.0:
            count = 2
        else:
            count = 1
        if scheme is PressingScheme.CONSTANT:
            count += 1
        elif scheme is PressingScheme.ZONAL:
            count = min(count, 2)
        return min(max(count, 1), 4)

    def _closing_speed(self, defender: PlayerAgentState, effective_intensity: float) -> float:
        physical = defender.player.attributes.physical
        mental = defender.player.attributes.mental
        fitness = defender.current_fitness
        fatigue = defender.current_fatigue
        physical_quality = (
            physical.acceleration * 0.42
            + physical.pace * 0.30
            + physical.stamina * 0.18
            + mental.work_rate * 0.10
        ) / 100.0
        condition = _clamp01((fitness - fatigue + 50.0) / 100.0)
        intensity = effective_intensity / 100.0
        raw = (
            self.config.base_press_speed_mps
            + (self.config.max_press_speed_mps - self.config.base_press_speed_mps)
            * (physical_quality * 0.55 + intensity * 0.35 + condition * 0.10)
        )
        bounded = min(max(raw, self.config.base_press_speed_mps), self.config.max_press_speed_mps)
        return bounded * self.context.movement_speed_multiplier(defender)

    def _coverage_speed(self, defender: PlayerAgentState) -> float:
        physical = defender.player.attributes.physical
        instructions = self._instructions(defender)
        quality = (
            physical.pace * 0.35
            + physical.acceleration * 0.35
            + float(instructions.defensive_tracking) * 0.30
        ) / 100.0
        return (3.4 + quality * 2.0) * self.context.movement_speed_multiplier(defender)

    def _tackle_willingness(self, defender: PlayerAgentState) -> float:
        out = self._team_tactics[defender.side].team_instructions.out_of_possession
        individual = self._instructions(defender)
        mental = defender.player.attributes.mental
        return _clamp(
            float(out.defensive_aggression) * 0.46
            + float(individual.pressing_intensity) * 0.24
            + mental.aggression * 0.20
            + mental.bravery * 0.10
        )

    @staticmethod
    def _defender_duel_quality(defender: PlayerAgentState) -> float:
        technical = defender.player.attributes.technical
        mental = defender.player.attributes.mental
        physical = defender.player.attributes.physical
        return _clamp(
            technical.tackling * 0.34
            + mental.anticipation * 0.13
            + mental.decisions * 0.10
            + mental.positioning * 0.10
            + mental.bravery * 0.07
            + physical.strength * 0.12
            + physical.balance * 0.07
            + physical.acceleration * 0.07
        )

    @staticmethod
    def _attacker_duel_resistance(attacker: PlayerAgentState) -> float:
        technical = attacker.player.attributes.technical
        mental = attacker.player.attributes.mental
        physical = attacker.player.attributes.physical
        return _clamp(
            technical.dribbling * 0.27
            + technical.technique * 0.16
            + technical.first_touch * 0.10
            + mental.composure * 0.10
            + mental.decisions * 0.07
            + physical.agility * 0.12
            + physical.balance * 0.11
            + physical.strength * 0.07
        )

    def _support_value(
        self,
        state: MatchState,
        defender: PlayerAgentState,
        attacker: PlayerAgentState,
    ) -> float:
        remaining = 1.0
        for teammate in state.active_players:
            if teammate.side is not defender.side or teammate.agent_id == defender.agent_id:
                continue
            distance = teammate.location.distance_to(attacker.location)
            if distance >= self.config.support_radius_m:
                continue
            contribution = (1.0 - distance / self.config.support_radius_m) * 0.65
            remaining *= 1.0 - _clamp01(contribution)
        return _clamp01(1.0 - remaining)

    @staticmethod
    def _front_position_value(defender: PlayerAgentState, attacker: PlayerAgentState) -> float:
        # Positive means the defender is goal-side / in front of the attacker's path.
        difference = (defender.location.x - attacker.location.x) * attacker.side.attack_sign
        return _clamp(50.0 + difference * 16.0)

    @staticmethod
    def _instructions(agent: PlayerAgentState) -> PlayerInstructions:
        return agent.player.effective_instructions or PlayerInstructions()

    @staticmethod
    def _target_matches(target: DomainTacticalTarget | None, opponent: PlayerAgentState) -> bool:
        if target is None:
            return False
        if target.kind is TargetKind.PLAYER:
            return target.target_id in {opponent.player.player_id, opponent.agent_id}
        if target.kind is TargetKind.POSITION:
            return target.target_id == opponent.assigned_position.value
        if target.kind is TargetKind.ROLE:
            return opponent.player.role_id is not None and target.target_id == opponent.player.role_id
        return False

    @staticmethod
    def _effective_force_direction(
        configured: ForceDirection,
        scheme: PressingScheme,
    ) -> ForceDirection:
        if configured is not ForceDirection.NEUTRAL:
            return configured
        if scheme is PressingScheme.TRAP_INSIDE:
            return ForceDirection.INSIDE
        if scheme is PressingScheme.TRAP_OUTSIDE:
            return ForceDirection.OUTSIDE
        return ForceDirection.NEUTRAL

    @staticmethod
    def _controlled_opponent(
        state: MatchState,
        defending_side: TeamSide,
    ) -> PlayerAgentState | None:
        owner_id = state.ball.owner_agent_id
        if owner_id is None:
            return None
        owner = state.agent(owner_id)
        if owner.side is defending_side:
            return None
        if state.possession.owner_agent_id != owner_id:
            return None
        if state.possession.team_side is not owner.side:
            return None
        return owner

    @staticmethod
    def _require_opposing_ball_carrier(
        state: MatchState,
        defender: PlayerAgentState,
    ) -> PlayerAgentState:
        owner_id = state.ball.owner_agent_id
        if owner_id is None or state.possession.owner_agent_id != owner_id:
            raise ValueError("a tackle requires a controlled opposing ball carrier")
        attacker = state.agent(owner_id)
        if attacker.side is defender.side:
            raise ValueError("defender cannot tackle a teammate")
        return attacker

    def _move_toward(
        self,
        defender: PlayerAgentState,
        target: Vector2,
        speed_mps: float,
    ) -> None:
        delta = target - defender.location
        if delta.magnitude <= self.config.press_arrival_radius_m:
            defender.velocity = Vector2.zero()
            return
        defender.velocity = delta.normalized().scale(speed_mps)

    def _duel_loose_ball_location(
        self,
        state: MatchState,
        defender: PlayerAgentState,
        attacker: PlayerAgentState,
    ) -> Vector2:
        midpoint = Vector2(
            (defender.location.x + attacker.location.x) / 2.0,
            (defender.location.y + attacker.location.y) / 2.0,
        )
        angle_vector = (attacker.location - defender.location).normalized()
        perpendicular = Vector2(-angle_vector.y, angle_vector.x)
        forward = self.random.uniform(-0.5, 1.2)
        lateral = self.random.uniform(-1.2, 1.2)
        return state.pitch.clamp(
            midpoint + angle_vector.scale(forward) + perpendicular.scale(lateral)
        )

    @staticmethod
    def _give_control(state: MatchState, controller: PlayerAgentState) -> None:
        state.possession.team_side = controller.side
        state.possession.owner_agent_id = controller.agent_id
        state.ball.owner_agent_id = controller.agent_id
        state.ball.last_touch_agent_id = controller.agent_id
        state.ball.location = controller.location
        state.ball.velocity = Vector2.zero()
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
        for agent in state.players.values():
            agent.has_ball = False
