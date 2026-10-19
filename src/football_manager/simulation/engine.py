from __future__ import annotations

from dataclasses import replace

from football_manager.domain import (
    MatchSnapshot,
    TacticMatchSnapshot,
    get_role,
)

from football_manager.domain.snapshot_assignment import assign_match_player

from .clock import DEFAULT_TIMESTEP_SECONDS
from .decisions import ActionOption, DecisionSystem, PlayerDecision
from .defending import (
    DefensiveDuelProfile,
    DefensiveDuelResult,
    DefendingSystem,
    PressingPlan,
)
from .geometry import Vector2
from .match_context_effects import MatchContextSystem
from .movement import OrganicMovementSystem
from .passing import ActivePass, PassResult, PassingSystem
from .perception import PerceptionSystem, PlayerPerception
from .progression import (
    ActiveCarry,
    ActiveCross,
    CarryResult,
    CrossResult,
    DribbleProfile,
    DribbleResult,
    OffBallRun,
    BallProgressionSystem,
)
from .randomness import MatchRandom
from .spatial_initializer import create_initial_match_state
from .spatial_state import MatchState, TeamSide
from .shooting import (
    ActiveShot,
    ChanceOrigin,
    ShotBodyPart,
    ShotExecutionProfile,
    ShotResult,
    ShootingSystem,
)
from .tactical_positioning import TacticalPositioningSystem


class SpatialMatchEngine:
    """Fixed-step spatial Match Engine shell.

    Phase 5.6 adds contextual chance quality, physical shot trajectories,
    blocks, goalkeeper reactions, saves, rebounds and goals on top of the
    existing positioning, decision, passing, defending and progression layers.
    Decisions remain separate from execution and every action uses the same
    fixed-step 2D match state.
    """

    def __init__(self, snapshot: MatchSnapshot) -> None:
        self.snapshot = snapshot
        self.random_root = MatchRandom(snapshot.seed)
        # Named deterministic substreams keep systems reproducible in isolation.
        # ``self.random`` remains the flow/controller stream for backwards API
        # compatibility; action systems receive their own streams below.
        self.random = self.random_root.fork("flow")
        self._random_streams = {
            "initialization": self.random_root.fork("initialization"),
            "decisions": self.random_root.fork("decisions"),
            "passing": self.random_root.fork("passing"),
            "defending": self.random_root.fork("defending"),
            "progression": self.random_root.fork("progression"),
            "shooting": self.random_root.fork("shooting"),
        }
        self._runtime_tactics = {
            TeamSide.HOME: snapshot.home_team.tactic,
            TeamSide.AWAY: snapshot.away_team.tactic,
        }
        self.state = create_initial_match_state(snapshot, self._random_streams["initialization"])
        self.context = MatchContextSystem(snapshot)
        self.positioning = TacticalPositioningSystem(snapshot, context=self.context)
        self.movement = OrganicMovementSystem(snapshot, context=self.context)
        self.perception = PerceptionSystem(context=self.context)
        self.decisions = DecisionSystem(snapshot, self._random_streams["decisions"], self.perception)
        self.passing = PassingSystem(snapshot, self._random_streams["passing"], self.perception, context=self.context)
        self.defending = DefendingSystem(snapshot, self._random_streams["defending"], context=self.context)
        self.progression = BallProgressionSystem(snapshot, self._random_streams["progression"], self.perception, context=self.context)
        self.shooting = ShootingSystem(snapshot, self._random_streams["shooting"], self.perception, context=self.context)
        self._manual_velocity_overrides: set[str] = set()
        self.refresh_tactical_positioning()


    def runtime_tactic(self, side: TeamSide) -> TacticMatchSnapshot:
        return self._runtime_tactics[TeamSide(side)]

    def set_runtime_tactic(self, side: TeamSide, tactic: TacticMatchSnapshot) -> None:
        """Apply a live tactical change without mutating MatchSnapshot.

        A formation change is allowed when it preserves the runtime slot IDs.
        That lets the manager turn, for example, the existing ``cm`` slot into
        an ``AM`` while keeping the same eleven runtime agents.  Each agent gets
        the new position, role/instructions and execution context immediately;
        the underlying attributes and Overall-equivalent data never change.
        """

        side = TeamSide(side)
        current = self._runtime_tactics[side]
        if tactic.formation.slot_ids != current.formation.slot_ids:
            raise ValueError("runtime formation changes must preserve tactical slot IDs")

        # Validate every slot and compute every new rating before touching the
        # mutable match state.  Invalid role/position combinations must not leave
        # a partially updated team after an exception.
        if (
            len(tactic.slots) != len(tactic.formation.slots)
            or {slot.slot_id for slot in tactic.slots} != tactic.formation.slot_ids
        ):
            raise ValueError("runtime tactic slots do not match its formation")
        for slot in tactic.slots:
            if slot.position is not tactic.formation.slot(slot.slot_id).position:
                raise ValueError("runtime tactic slot position does not match formation")

        assignments = []
        for agent in self.state.players.values():
            if agent.side is not side:
                continue
            slot = tactic.slot(agent.slot_id)
            assigned = assign_match_player(
                agent.player,
                slot_id=agent.slot_id,
                position=slot.position,
                role_id=slot.role_id,
                role_name=slot.role_name,
                tactic_id=tactic.tactic_id,
                instructions=slot.effective_instructions,
            )
            assignments.append((agent, slot.position, assigned))
        for agent, position, assigned in assignments:
            agent.assigned_position = position
            agent.player = assigned

        self._runtime_tactics[side] = tactic
        self.decisions._team_tactics[side] = tactic
        self.passing._team_tactics[side] = tactic
        self.defending._team_tactics[side] = tactic
        self.progression._team_tactics[side] = tactic
        self.context._team_tactics[side] = tactic
        self.positioning.set_runtime_tactic(side, tactic)
        self.movement.set_runtime_tactic(side, tactic)
        self.refresh_tactical_positioning()

    @staticmethod
    def _snapshot_role_suitability(player, role_id: str) -> float:
        role = get_role(role_id)
        weighted = 0.0
        total = 0.0
        for path, weight in role.attribute_weights:
            current: object = player.attributes
            try:
                for part in path.split("."):
                    current = getattr(current, part)
                value = float(current)
            except (AttributeError, TypeError, ValueError):
                continue
            weighted += value * weight
            total += weight
        return weighted / total if total > 0.0 else 50.0

    def random_stream(self, namespace: str) -> MatchRandom:
        """Return a named action-system RNG stream owned by this match."""

        try:
            return self._random_streams[namespace]
        except KeyError as exc:
            raise KeyError(f"unknown match RNG stream: {namespace}") from exc

    @property
    def timestep_seconds(self) -> float:
        return DEFAULT_TIMESTEP_SECONDS

    @property
    def active_pass(self) -> ActivePass | None:
        return self.passing.active_pass

    @property
    def last_pass_result(self) -> PassResult | None:
        return self.passing.last_result

    @property
    def active_carry(self) -> ActiveCarry | None:
        return self.progression.active_carry

    @property
    def active_cross(self) -> ActiveCross | None:
        return self.progression.active_cross

    @property
    def last_carry_result(self) -> CarryResult | None:
        return self.progression.last_carry_result

    @property
    def last_dribble_result(self) -> DribbleResult | None:
        return self.progression.last_dribble_result

    @property
    def last_cross_result(self) -> CrossResult | None:
        return self.progression.last_cross_result

    @property
    def active_shot(self) -> ActiveShot | None:
        return self.shooting.active_shot

    @property
    def last_shot_result(self) -> ShotResult | None:
        return self.shooting.last_result

    def step(self) -> MatchState:
        dt = self.state.clock.tick_seconds

        progression_overrides = self.progression.active_mover_ids
        passing_overrides = self.passing.active_mover_ids
        shooting_overrides = self.shooting.active_mover_ids
        excluded = (
            frozenset(self._manual_velocity_overrides)
            | progression_overrides
            | passing_overrides
            | shooting_overrides
        )

        # Formation/tactical coordinates are structural references only in the
        # integrated engine.  Reset ambient velocity each tick, let the organic
        # layer move every off-ball player, and then allow direct action systems
        # (receiver runs, carries, pressing, goalkeeper reactions...) to override
        # those velocities.  This prevents a hidden formation target from dragging
        # the ball owner around without an explicit carry action.
        self.positioning.refresh_targets(self.state)
        # Preserve off-ball momentum so players can accelerate, arc into runs and
        # decelerate naturally.  The ball owner is the exception: without an
        # explicit carry/dribble action they must not drift with stale velocity.
        owner_id = self.state.ball.owner_agent_id
        if owner_id is not None and owner_id not in excluded:
            self.state.agent(owner_id).velocity = Vector2.zero()

        self.movement.update_velocities(
            self.state,
            excluded_agent_ids=excluded,
        )
        self.defending.update_defensive_velocities(
            self.state,
            excluded_agent_ids=excluded,
        )
        self.progression.update_movement_velocities(self.state)
        self.passing.update_receiver_velocity(self.state)
        self.shooting.update_goalkeeper_velocity(self.state)

        for agent in self.state.players.values():
            if not agent.is_active:
                agent.velocity = Vector2.zero()
                continue
            next_location = agent.location + agent.velocity.scale(dt)
            agent.location = self.state.pitch.clamp(next_location)
            if agent.velocity.magnitude > 0.0:
                agent.facing = agent.velocity.normalized()

        self.progression.advance(self.state, dt)
        self.context.update_player_condition(self.state, dt)

        if self.shooting.is_shot_in_flight:
            self.shooting.advance(self.state, dt)
        elif self.passing.is_ball_in_flight:
            self.passing.advance(self.state, dt)
        elif self.progression.ball_in_cross_flight:
            # Cross movement was already advanced by the progression layer.
            pass
        elif self.state.ball.owner_agent_id is not None:
            owner = self.state.agent(self.state.ball.owner_agent_id)
            self.state.ball.location = owner.location
            self.state.ball.velocity = owner.velocity
        else:
            next_ball_location = self.state.ball.location + self.state.ball.velocity.scale(dt)
            self.state.ball.location = self.state.pitch.clamp(next_ball_location)

        self.state.clock.advance()
        return self.state

    def advance_ticks(self, ticks: int) -> MatchState:
        """Advance by repeatedly executing fixed simulation ticks.

        Playback x1/x2/x4 or instant consumption must call this same fixed-step
        path rather than changing the simulation timestep.
        """

        if ticks < 0:
            raise ValueError("ticks must be non-negative")
        for _ in range(ticks):
            self.step()
        return self.state

    def refresh_tactical_positioning(self) -> MatchState:
        """Recalculate current targets/velocities without advancing the clock."""

        progression_overrides = self.progression.active_mover_ids
        passing_overrides = self.passing.active_mover_ids
        shooting_overrides = self.shooting.active_mover_ids
        excluded = (
            frozenset(self._manual_velocity_overrides)
            | progression_overrides
            | passing_overrides
            | shooting_overrides
        )
        self.positioning.update_velocities(
            self.state,
            excluded_agent_ids=excluded,
        )
        self.defending.update_defensive_velocities(
            self.state,
            excluded_agent_ids=excluded,
        )
        self.progression.update_movement_velocities(self.state)
        self.passing.update_receiver_velocity(self.state)
        self.shooting.update_goalkeeper_velocity(self.state)
        return self.state

    def set_team_possession(self, side: TeamSide) -> None:
        """Switch possession metadata and tactical phase for debug/setup use."""

        self.passing.cancel()
        self.progression.cancel()
        self.shooting.cancel()
        side = TeamSide(side)
        self.state.possession.team_side = side
        self.state.possession.owner_agent_id = None
        self.state.ball.owner_agent_id = None
        self.state.ball.velocity = Vector2.zero()
        for agent in self.state.players.values():
            agent.has_ball = False
        self.refresh_tactical_positioning()

    def give_ball_to(self, agent_id: str) -> None:
        """Assign controlled possession to an active player."""

        self.passing.cancel()
        self.progression.cancel()
        self.shooting.cancel()
        owner = self.state.agent(agent_id)
        if not owner.is_active:
            raise ValueError("dismissed player cannot receive controlled possession")
        self.state.possession.team_side = owner.side
        self.state.possession.owner_agent_id = owner.agent_id
        self.state.ball.owner_agent_id = owner.agent_id
        self.state.ball.last_touch_agent_id = owner.agent_id
        self.state.ball.location = owner.location
        self.state.ball.velocity = Vector2.zero()
        for agent in self.state.players.values():
            agent.has_ball = agent.agent_id == owner.agent_id
        self.refresh_tactical_positioning()

    def perceive(self, agent_id: str) -> PlayerPerception:
        """Return the current spatial perception for one active player."""

        return self.perception.perceive(self.state, agent_id)

    def decision_options(self, agent_id: str) -> tuple[ActionOption, ...]:
        """Evaluate possession actions without mutating match state."""

        return self.decisions.options_for(self.state, agent_id)

    def decide(self, agent_id: str) -> PlayerDecision:
        """Choose one seeded possession action without executing it."""

        return self.decisions.decide(self.state, agent_id)

    def start_pass(self, decision: PlayerDecision) -> ActivePass:
        """Execute the start of a previously chosen pass decision.

        The ball becomes free in flight immediately, while the outcome is
        resolved through normal fixed simulation ticks.
        """

        if self.shooting.is_shot_in_flight:
            raise ValueError("cannot start a pass while a shot is in flight")
        if self.progression.ball_in_cross_flight:
            raise ValueError("cannot start a pass while a cross is in flight")
        self.progression.cancel_carry()
        active = self.passing.start(self.state, decision)
        self.refresh_tactical_positioning()
        return active

    def resolve_active_pass(self, max_ticks: int = 240) -> PassResult:
        """Advance fixed ticks until the current pass resolves.

        This is a test/debug convenience, not an alternate simulation path.
        """

        if max_ticks <= 0:
            raise ValueError("max_ticks must be positive")
        if self.active_pass is None:
            raise ValueError("there is no active pass to resolve")
        for _ in range(max_ticks):
            self.step()
            if self.active_pass is None:
                assert self.last_pass_result is not None
                return self.last_pass_result
        raise RuntimeError("active pass did not resolve within max_ticks")


    def pressing_plan(self, defending_side: TeamSide) -> PressingPlan:
        """Return the current spatial pressing/coverage plan for one defending side."""

        return self.defending.plan(self.state, TeamSide(defending_side))

    def defensive_duel_profile(self, defender_agent_id: str) -> DefensiveDuelProfile:
        """Evaluate a possible tackle without mutating match state."""

        return self.defending.duel_profile(self.state, defender_agent_id)

    def attempt_tackle(self, defender_agent_id: str) -> DefensiveDuelResult:
        """Resolve one tackle against the current controlled ball carrier."""

        result = self.defending.attempt_tackle(self.state, defender_agent_id)
        if self.state.ball.owner_agent_id != (
            self.progression.active_carry.profile.carrier_agent_id
            if self.progression.active_carry is not None
            else None
        ):
            self.progression.cancel_carry()
        self.refresh_tactical_positioning()
        return result

    def press_is_broken(self, plan: PressingPlan) -> bool:
        """Report whether the carrier has escaped the supplied primary press."""

        return self.defending.press_is_broken(self.state, plan)

    def set_player_velocity(self, agent_id: str, velocity: Vector2) -> None:
        """Apply a manual/debug velocity that tactical positioning will not overwrite."""

        self.state.agent(agent_id).velocity = velocity
        self._manual_velocity_overrides.add(agent_id)

    def clear_player_velocity_override(self, agent_id: str) -> None:
        self.state.agent(agent_id)
        self._manual_velocity_overrides.discard(agent_id)
        self.refresh_tactical_positioning()

    def set_ball_velocity(self, velocity: Vector2) -> None:
        self.passing.cancel()
        self.progression.cancel()
        self.shooting.cancel()
        self.state.ball.velocity = velocity

    def off_ball_run_plan(
        self,
        attacking_side: TeamSide,
        *,
        max_runners: int | None = None,
    ) -> tuple[OffBallRun, ...]:
        """Return candidate off-ball runs without mutating player movement."""

        return self.progression.off_ball_run_plan(
            self.state,
            TeamSide(attacking_side),
            max_runners=max_runners,
        )

    def start_off_ball_runs(
        self,
        attacking_side: TeamSide,
        *,
        max_runners: int | None = None,
    ) -> tuple[OffBallRun, ...]:
        """Activate a bounded set of off-ball runs through normal fixed ticks."""

        runs = self.progression.start_off_ball_runs(
            self.state,
            TeamSide(attacking_side),
            max_runners=max_runners,
        )
        self.refresh_tactical_positioning()
        return runs

    def start_carry(self, decision: PlayerDecision) -> ActiveCarry:
        """Start a controlled ball carry selected by the decision layer."""

        if (
            self.passing.is_ball_in_flight
            or self.progression.ball_in_cross_flight
            or self.shooting.is_shot_in_flight
        ):
            raise ValueError("cannot start a carry while the ball is in flight")
        active = self.progression.start_carry(self.state, decision)
        self.refresh_tactical_positioning()
        return active

    def resolve_active_carry(self, max_ticks: int = 240) -> CarryResult:
        """Advance fixed ticks until the current carry resolves."""

        if max_ticks <= 0:
            raise ValueError("max_ticks must be positive")
        if self.active_carry is None:
            raise ValueError("there is no active carry to resolve")
        for _ in range(max_ticks):
            self.step()
            if self.active_carry is None:
                assert self.last_carry_result is not None
                return self.last_carry_result
        raise RuntimeError("active carry did not resolve within max_ticks")

    def dribble_profile(self, attacker_agent_id: str) -> DribbleProfile:
        """Evaluate a one-on-one dribble without mutating state."""

        return self.progression.dribble_profile(self.state, attacker_agent_id)

    def attempt_dribble(self, decision: PlayerDecision) -> DribbleResult:
        """Resolve the initial one-on-one result of a dribble attempt."""

        if (
            self.passing.is_ball_in_flight
            or self.progression.ball_in_cross_flight
            or self.shooting.is_shot_in_flight
        ):
            raise ValueError("cannot dribble while the ball is in flight")
        result = self.progression.attempt_dribble(self.state, decision)
        self.refresh_tactical_positioning()
        return result

    def start_cross(self, decision: PlayerDecision) -> ActiveCross:
        """Start a cross/cutback through the same fixed-step ball state."""

        if self.shooting.is_shot_in_flight:
            raise ValueError("cannot start a cross while a shot is in flight")
        if self.passing.is_ball_in_flight:
            raise ValueError("cannot start a cross while a pass is in flight")
        active = self.progression.start_cross(self.state, decision)
        self.refresh_tactical_positioning()
        return active

    def resolve_active_cross(self, max_ticks: int = 240) -> CrossResult:
        """Advance fixed ticks until the current cross resolves."""

        if max_ticks <= 0:
            raise ValueError("max_ticks must be positive")
        if self.active_cross is None:
            raise ValueError("there is no active cross to resolve")
        for _ in range(max_ticks):
            self.step()
            if self.active_cross is None:
                assert self.last_cross_result is not None
                return self.last_cross_result
        raise RuntimeError("active cross did not resolve within max_ticks")

    def start_shot(
        self,
        decision: PlayerDecision,
        *,
        body_part: ShotBodyPart = ShotBodyPart.FOOT,
        chance_origin: ChanceOrigin = ChanceOrigin.OPEN_PLAY,
        transition_speed: float | None = None,
    ) -> ActiveShot:
        """Start a real shot trajectory from a previously chosen SHOOT decision."""

        if self.passing.is_ball_in_flight or self.progression.ball_in_cross_flight:
            raise ValueError("cannot shoot while a pass or cross is in flight")
        self.progression.cancel_carry()
        active = self.shooting.start(
            self.state,
            decision,
            body_part=body_part,
            chance_origin=chance_origin,
            transition_speed=transition_speed,
        )
        self.refresh_tactical_positioning()
        return active

    def shot_profile(
        self,
        decision: PlayerDecision,
        *,
        body_part: ShotBodyPart = ShotBodyPart.FOOT,
        chance_origin: ChanceOrigin = ChanceOrigin.OPEN_PLAY,
        transition_speed: float | None = None,
    ) -> ShotExecutionProfile:
        """Build a shot by starting it and return its frozen execution profile.

        This helper is intended for deterministic tests/debug inspection. The
        shot remains active and must still be resolved or cancelled.
        """

        return self.start_shot(
            decision,
            body_part=body_part,
            chance_origin=chance_origin,
            transition_speed=transition_speed,
        ).profile

    def resolve_active_shot(self, max_ticks: int = 160) -> ShotResult:
        """Advance fixed ticks until the current shot resolves."""

        if max_ticks <= 0:
            raise ValueError("max_ticks must be positive")
        if self.active_shot is None:
            raise ValueError("there is no active shot to resolve")
        for _ in range(max_ticks):
            self.step()
            if self.active_shot is None:
                assert self.last_shot_result is not None
                return self.last_shot_result
        raise RuntimeError("active shot did not resolve within max_ticks")

