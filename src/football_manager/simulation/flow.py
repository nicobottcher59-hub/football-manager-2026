from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import StrEnum
from math import ceil

from football_manager.domain import (
    MatchDecider,
    MatchSnapshot,
    PlayerMatchSnapshot,
    Position,
    TacticMatchSnapshot,
    get_role,
)

from football_manager.domain.snapshot_assignment import assign_match_player

from .decisions import ActionType, PlayerDecision
from .geometry import Vector2
from .match_context_effects import CardType, FoulAssessment
from .passing import PASS_ACTION_TYPES, PassOutcome
from .positioning_anchors import normalized_anchor
from .progression import CarryOutcome, CrossOutcome, DribbleOutcome
from .shooting import ShotOutcome
from .spatial_initializer import create_initial_match_state
from .spatial_state import PlayerAgentState, TeamSide
from .engine import SpatialMatchEngine


class MatchPhase(StrEnum):
    PRE_MATCH = "pre_match"
    FIRST_HALF = "first_half"
    HALF_TIME = "half_time"
    SECOND_HALF = "second_half"
    EXTRA_TIME_FIRST_HALF = "extra_time_first_half"
    EXTRA_TIME_INTERVAL = "extra_time_interval"
    EXTRA_TIME_SECOND_HALF = "extra_time_second_half"
    PENALTY_SHOOTOUT = "penalty_shootout"
    FINISHED = "finished"


class RestartType(StrEnum):
    KICKOFF = "kickoff"
    THROW_IN = "throw_in"
    GOAL_KICK = "goal_kick"
    CORNER = "corner"
    FREE_KICK = "free_kick"
    PENALTY = "penalty"


class MatchEventType(StrEnum):
    MATCH_START = "match_start"
    PERIOD_START = "period_start"
    ADDED_TIME = "added_time"
    HALF_TIME = "half_time"
    EXTRA_TIME = "extra_time"
    PENALTY_SHOOTOUT = "penalty_shootout"
    MATCH_END = "match_end"
    RESTART = "restart"
    PASS = "pass"
    CARRY = "carry"
    DRIBBLE = "dribble"
    CROSS = "cross"
    SHOT = "shot"
    GOAL = "goal"
    SAVE = "save"
    BLOCK = "block"
    WOODWORK = "woodwork"
    OFF_TARGET = "off_target"
    RECOVERY = "recovery"
    TACKLE = "tackle"
    FOUL = "foul"
    CARD = "card"
    PENALTY_AWARDED = "penalty_awarded"
    PENALTY_KICK = "penalty_kick"
    SUBSTITUTION = "substitution"
    TACTICAL_CHANGE = "tactical_change"


class MatchEndReason(StrEnum):
    DRAW = "draw"
    REGULATION = "regulation"
    EXTRA_TIME = "extra_time"
    PENALTIES = "penalties"


@dataclass(frozen=True, slots=True)
class FlowConfig:
    regulation_half_seconds: float = 45.0 * 60.0
    extra_time_half_seconds: float = 15.0 * 60.0
    decision_cooldown_seconds: float = 5.4
    loose_ball_collection_seconds: float = 1.0
    forced_loose_ball_collection_seconds: float = 2.5
    duel_recovery_seconds: float = 2.5
    added_time_unit_seconds: float = 60.0
    regulation_added_time_cap_seconds: float = 5.0 * 60.0
    extra_time_added_time_cap_seconds: float = 2.0 * 60.0
    autonomous_actions: bool = True
    autonomous_tackles: bool = True

    def __post_init__(self) -> None:
        positive = (
            "regulation_half_seconds",
            "extra_time_half_seconds",
            "decision_cooldown_seconds",
            "loose_ball_collection_seconds",
            "forced_loose_ball_collection_seconds",
            "duel_recovery_seconds",
            "added_time_unit_seconds",
        )
        for name in positive:
            if getattr(self, name) <= 0.0:
                raise ValueError(f"{name} must be positive")
        if self.regulation_added_time_cap_seconds < 0.0:
            raise ValueError("regulation added-time cap cannot be negative")
        if self.extra_time_added_time_cap_seconds < 0.0:
            raise ValueError("extra-time added-time cap cannot be negative")
        if self.forced_loose_ball_collection_seconds < self.loose_ball_collection_seconds:
            raise ValueError(
                "forced loose-ball collection must not be faster than normal collection"
            )


@dataclass(slots=True)
class MatchScore:
    home: int = 0
    away: int = 0
    penalties_home: int = 0
    penalties_away: int = 0

    def add_goal(self, side: TeamSide) -> None:
        if TeamSide(side) is TeamSide.HOME:
            self.home += 1
        else:
            self.away += 1


@dataclass(frozen=True, slots=True)
class MatchEventDetails:
    """Typed view over legacy event metadata.

    Phase 5.10B keeps ``MatchEvent.data`` for backwards compatibility with the
    viewer/commentary, but simulation statistics and calibration can consume
    these typed fields instead of repeatedly parsing ad-hoc strings.
    """

    action: str | None = None
    status: str | None = None
    outcome: str | None = None
    shot_id: str | None = None
    body_part: str | None = None
    chance_origin: str | None = None
    card: str | None = None
    label: str | None = None
    reason: str | None = None
    xg: float | None = None
    probability: float | None = None
    severity: float | None = None
    foul_probability: float | None = None
    x: float | None = None
    y: float | None = None
    seconds: int | None = None
    yellow_count: int | None = None
    remaining: int | None = None
    advantage: bool | None = None
    penalty_area: bool | None = None
    dismissed: bool | None = None
    scored: bool | None = None
    shootout: bool | None = None
    penalty: bool | None = None

    @classmethod
    def from_pairs(cls, pairs: tuple[tuple[str, str], ...]) -> "MatchEventDetails":
        values = dict(pairs)

        def as_float(key: str) -> float | None:
            value = values.get(key)
            if value is None:
                return None
            try:
                return float(value)
            except (TypeError, ValueError):
                return None

        def as_int(key: str) -> int | None:
            value = values.get(key)
            if value is None:
                return None
            try:
                return int(value)
            except (TypeError, ValueError):
                return None

        def as_bool(key: str) -> bool | None:
            value = values.get(key)
            if value is None:
                return None
            normalized = value.strip().lower()
            if normalized == "true":
                return True
            if normalized == "false":
                return False
            return None

        return cls(
            action=values.get("action"),
            status=values.get("status"),
            outcome=values.get("outcome"),
            shot_id=values.get("shot_id"),
            body_part=values.get("body_part"),
            chance_origin=values.get("chance_origin"),
            card=values.get("card"),
            label=values.get("label"),
            reason=values.get("reason"),
            xg=as_float("xg"),
            probability=as_float("probability"),
            severity=as_float("severity"),
            foul_probability=as_float("foul_probability"),
            x=as_float("x"),
            y=as_float("y"),
            seconds=as_int("seconds"),
            yellow_count=as_int("yellow_count"),
            remaining=as_int("remaining"),
            advantage=as_bool("advantage"),
            penalty_area=as_bool("penalty_area"),
            dismissed=as_bool("dismissed"),
            scored=as_bool("scored"),
            shootout=as_bool("shootout"),
            penalty=as_bool("penalty"),
        )


@dataclass(frozen=True, slots=True)
class MatchEvent:
    sequence: int
    tick: int
    time_label: str
    phase: MatchPhase
    event_type: MatchEventType
    side: TeamSide | None = None
    actor_agent_id: str | None = None
    secondary_agent_id: str | None = None
    restart_type: RestartType | None = None
    data: tuple[tuple[str, str], ...] = ()
    details: MatchEventDetails | None = None

    def __post_init__(self) -> None:
        if self.details is None:
            object.__setattr__(self, "details", MatchEventDetails.from_pairs(self.data))

    def value(self, key: str) -> str | None:
        for item_key, item_value in self.data:
            if item_key == key:
                return item_value
        return None


@dataclass(frozen=True, slots=True)
class PlayerConditionResult:
    agent_id: str
    fitness: float
    fatigue: float


@dataclass(frozen=True, slots=True)
class PlayerDisciplineResult:
    agent_id: str
    yellow_cards: int
    dismissed: bool


@dataclass(frozen=True, slots=True)
class MatchResult:
    match_id: str
    home_goals: int
    away_goals: int
    aggregate_home_goals: int
    aggregate_away_goals: int
    winner: TeamSide | None
    end_reason: MatchEndReason
    penalties_home: int = 0
    penalties_away: int = 0
    player_conditions: tuple[PlayerConditionResult, ...] = ()
    discipline: tuple[PlayerDisciplineResult, ...] = ()
    events: tuple[MatchEvent, ...] = ()


@dataclass(slots=True)
class _PeriodRuntime:
    start_tick: int
    nominal_seconds: float
    stoppage_seconds: float = 0.0
    added_seconds: float | None = None


class MatchFlowController:
    """Autonomous match lifecycle over the existing spatial engine.

    The controller does not replace any action system. It schedules the already
    implemented decision, passing, defending, progression and shooting layers;
    handles dead-ball restarts and score; and decides when periods/end conditions
    are reached. It uses the engine's single seeded RNG, preserving reproducibility.
    """

    def __init__(
        self,
        snapshot: MatchSnapshot,
        *,
        config: FlowConfig | None = None,
    ) -> None:
        self.snapshot = snapshot
        self.config = config or FlowConfig()
        self.engine = SpatialMatchEngine(snapshot)
        self._duel_random = self.engine.random_root.fork("flow/duels")
        self._penalty_random = self.engine.random_root.fork("flow/penalties")
        self.phase = MatchPhase.PRE_MATCH
        self.score = MatchScore()
        self.events: list[MatchEvent] = []
        self._period: _PeriodRuntime | None = None
        self._next_action_tick = 0
        self._loose_since_tick: int | None = None
        self._result: MatchResult | None = None
        self._event_sequence = 0
        self._active_shot_id: str | None = None
        self._next_duel_tick_by_pair: dict[tuple[str, str], int] = {}
        self._used_substitutes: dict[TeamSide, set[str]] = {TeamSide.HOME: set(), TeamSide.AWAY: set()}
        self._substitutions_used: dict[TeamSide, int] = {TeamSide.HOME: 0, TeamSide.AWAY: 0}
        self._pending_substitutions: dict[TeamSide, list[tuple[str, str]]] = {
            TeamSide.HOME: [],
            TeamSide.AWAY: [],
        }
        self._substituted_out_conditions: list[PlayerConditionResult] = []
        self._substituted_out_discipline: list[PlayerDisciplineResult] = []

    @property
    def result(self) -> MatchResult | None:
        return self._result

    @property
    def is_finished(self) -> bool:
        return self.phase is MatchPhase.FINISHED

    @property
    def period_elapsed_seconds(self) -> float:
        if self._period is None:
            return 0.0
        ticks = self.engine.state.clock.tick_count - self._period.start_tick
        return ticks * self.engine.state.clock.tick_seconds

    @property
    def aggregate_score(self) -> tuple[int, int]:
        tie = self.snapshot.context.competition.cup_tie
        before_home = tie.home_aggregate_goals_before_match if tie is not None else 0
        before_away = tie.away_aggregate_goals_before_match if tie is not None else 0
        return before_home + self.score.home, before_away + self.score.away

    @property
    def time_label(self) -> str:
        if self.phase is MatchPhase.PRE_MATCH and self._period is None:
            return "0'"
        if self.phase is MatchPhase.PENALTY_SHOOTOUT:
            return "PEN"
        if self._period is None and self.events:
            # Preserve the last official match time while paused at half-time or
            # after the final whistle instead of visually jumping back to 0'.
            return self.events[-1].time_label
        return self._format_period_time(self.phase, self.period_elapsed_seconds)

    def start(self) -> None:
        if self.phase is not MatchPhase.PRE_MATCH:
            raise ValueError("match flow has already started")
        self._emit(MatchEventType.MATCH_START)
        self._start_period(MatchPhase.FIRST_HALF, self.engine.state.kickoff_side)

    def step(self) -> None:
        if self.phase is MatchPhase.PRE_MATCH:
            self.start()
        if self.phase is MatchPhase.FINISHED:
            return
        if self.phase is MatchPhase.HALF_TIME:
            self._start_period(MatchPhase.SECOND_HALF, self.engine.state.kickoff_side.opponent)
            return
        if self.phase is MatchPhase.EXTRA_TIME_INTERVAL:
            self._start_period(
                MatchPhase.EXTRA_TIME_SECOND_HALF,
                self.engine.state.kickoff_side.opponent,
            )
            return
        if self.phase is MatchPhase.PENALTY_SHOOTOUT:
            self._run_penalty_shootout()
            return

        self._schedule_live_play()
        self.engine.step()
        self._handle_resolved_actions()
        self._handle_loose_ball()
        self._maybe_set_added_time()
        self._maybe_end_period()

    def run_to_completion(self, *, max_ticks: int | None = None) -> MatchResult:
        if self.phase is MatchPhase.PRE_MATCH:
            self.start()

        if max_ticks is None:
            total_seconds = (
                self.config.regulation_half_seconds * 2
                + self.config.regulation_added_time_cap_seconds * 2
                + self.config.extra_time_half_seconds * 2
                + self.config.extra_time_added_time_cap_seconds * 2
                + 120.0
            )
            max_ticks = int(total_seconds / self.engine.timestep_seconds) + 1000
        if max_ticks <= 0:
            raise ValueError("max_ticks must be positive")

        for _ in range(max_ticks):
            if self.is_finished:
                assert self._result is not None
                return self._result
            self.step()
        raise RuntimeError("match did not finish within max_ticks")

    # ------------------------------------------------------------------
    # Period lifecycle
    # ------------------------------------------------------------------
    def _start_period(self, phase: MatchPhase, kickoff_side: TeamSide) -> None:
        if phase not in {
            MatchPhase.FIRST_HALF,
            MatchPhase.SECOND_HALF,
            MatchPhase.EXTRA_TIME_FIRST_HALF,
            MatchPhase.EXTRA_TIME_SECOND_HALF,
        }:
            raise ValueError("invalid live period")
        nominal = (
            self.config.regulation_half_seconds
            if phase in {MatchPhase.FIRST_HALF, MatchPhase.SECOND_HALF}
            else self.config.extra_time_half_seconds
        )
        self.phase = phase
        self._period = _PeriodRuntime(
            start_tick=self.engine.state.clock.tick_count,
            nominal_seconds=nominal,
        )
        self._loose_since_tick = None
        self._next_action_tick = self.engine.state.clock.tick_count
        self._apply_pending_substitutions()
        self._prepare_kickoff(TeamSide(kickoff_side))
        self._emit(
            MatchEventType.PERIOD_START,
            side=TeamSide(kickoff_side),
            restart_type=RestartType.KICKOFF,
        )

    def _maybe_set_added_time(self) -> None:
        period = self._period
        if period is None or period.added_seconds is not None:
            return
        if self.period_elapsed_seconds < period.nominal_seconds:
            return

        cap = (
            self.config.regulation_added_time_cap_seconds
            if self.phase in {MatchPhase.FIRST_HALF, MatchPhase.SECOND_HALF}
            else self.config.extra_time_added_time_cap_seconds
        )
        if period.stoppage_seconds <= 0.0 or cap <= 0.0:
            added = 0.0
        else:
            unit = self.config.added_time_unit_seconds
            added = min(ceil(period.stoppage_seconds / unit) * unit, cap)
        period.added_seconds = added
        if added > 0.0:
            self._emit(
                MatchEventType.ADDED_TIME,
                data=(("seconds", str(int(added))),),
            )

    def _maybe_end_period(self) -> None:
        period = self._period
        if period is None or period.added_seconds is None:
            return
        if self.period_elapsed_seconds < period.nominal_seconds + period.added_seconds:
            return
        if self._ball_action_active():
            return

        if self.phase is MatchPhase.FIRST_HALF:
            self._emit(MatchEventType.HALF_TIME)
            self.phase = MatchPhase.HALF_TIME
            self._period = None
            return

        if self.phase is MatchPhase.SECOND_HALF:
            if not self._tie_requires_resolution():
                self._finish_after_regulation()
                return
            decider = self.snapshot.context.competition.match_decider
            if decider is MatchDecider.PENALTIES_AFTER_90:
                self.phase = MatchPhase.PENALTY_SHOOTOUT
                self._period = None
                self._emit(MatchEventType.PENALTY_SHOOTOUT)
                return
            self._emit(MatchEventType.EXTRA_TIME)
            self._start_period(MatchPhase.EXTRA_TIME_FIRST_HALF, self.engine.state.kickoff_side)
            return

        if self.phase is MatchPhase.EXTRA_TIME_FIRST_HALF:
            self._emit(MatchEventType.HALF_TIME)
            self.phase = MatchPhase.EXTRA_TIME_INTERVAL
            self._period = None
            return

        if self.phase is MatchPhase.EXTRA_TIME_SECOND_HALF:
            if self._aggregate_is_tied():
                self.phase = MatchPhase.PENALTY_SHOOTOUT
                self._period = None
                self._emit(MatchEventType.PENALTY_SHOOTOUT)
            else:
                self._finish(MatchEndReason.EXTRA_TIME)

    def _finish_after_regulation(self) -> None:
        if self._aggregate_is_tied():
            self._finish(MatchEndReason.DRAW)
        else:
            self._finish(MatchEndReason.REGULATION)

    def _finish(self, reason: MatchEndReason, *, winner: TeamSide | None = None) -> None:
        if winner is None:
            aggregate_home, aggregate_away = self.aggregate_score
            if aggregate_home > aggregate_away:
                winner = TeamSide.HOME
            elif aggregate_away > aggregate_home:
                winner = TeamSide.AWAY
        aggregate_home, aggregate_away = self.aggregate_score
        self._emit(
            MatchEventType.MATCH_END,
            side=winner,
            data=(("reason", reason.value),),
        )
        self.phase = MatchPhase.FINISHED
        self._period = None
        self._result = MatchResult(
            match_id=self.snapshot.match_id,
            home_goals=self.score.home,
            away_goals=self.score.away,
            aggregate_home_goals=aggregate_home,
            aggregate_away_goals=aggregate_away,
            winner=winner,
            end_reason=reason,
            penalties_home=self.score.penalties_home,
            penalties_away=self.score.penalties_away,
            player_conditions=tuple(self._substituted_out_conditions) + tuple(
                PlayerConditionResult(
                    agent_id=agent.agent_id,
                    fitness=agent.current_fitness,
                    fatigue=agent.current_fatigue,
                )
                for agent in sorted(self.engine.state.players.values(), key=lambda item: item.agent_id)
            ),
            discipline=tuple(self._substituted_out_discipline) + tuple(
                PlayerDisciplineResult(
                    agent_id=agent.agent_id,
                    yellow_cards=agent.yellow_cards,
                    dismissed=agent.dismissed,
                )
                for agent in sorted(self.engine.state.players.values(), key=lambda item: item.agent_id)
            ),
            events=tuple(self.events),
        )

    def _tie_requires_resolution(self) -> bool:
        if not self._aggregate_is_tied():
            return False
        return self.snapshot.context.competition.match_decider is not MatchDecider.DRAW_ALLOWED

    def _aggregate_is_tied(self) -> bool:
        home, away = self.aggregate_score
        return home == away

    # ------------------------------------------------------------------
    # Autonomous live play
    # ------------------------------------------------------------------
    def _schedule_live_play(self) -> None:
        if not self.config.autonomous_actions:
            return
        if self._ball_action_active():
            return
        state = self.engine.state
        owner_id = state.ball.owner_agent_id
        if owner_id is None:
            return
        if state.clock.tick_count < self._next_action_tick:
            return

        if self.config.autonomous_tackles and self._maybe_tackle_or_foul(owner_id):
            return

        if state.ball.owner_agent_id != owner_id:
            return

        decision = self.engine.decide(owner_id)
        self._execute_decision(decision)
        cooldown_seconds = self._decision_cooldown_seconds(decision)
        cooldown_ticks = max(
            1,
            round(cooldown_seconds / self.engine.timestep_seconds),
        )
        self._next_action_tick = state.clock.tick_count + cooldown_ticks

    def _execute_decision(self, decision: PlayerDecision) -> None:
        action = decision.action_type
        if action is ActionType.HOLD:
            return
        if action in PASS_ACTION_TYPES:
            self.engine.start_pass(decision)
            self._emit(
                MatchEventType.PASS,
                actor_agent_id=decision.agent_id,
                secondary_agent_id=decision.target_agent_id,
                data=(("action", action.value), ("status", "attempt")),
            )
            return
        if action is ActionType.CARRY:
            self.engine.start_carry(decision)
            self._emit(MatchEventType.CARRY, actor_agent_id=decision.agent_id)
            return
        if action is ActionType.DRIBBLE:
            try:
                result = self.engine.attempt_dribble(decision)
            except ValueError:
                return
            self._emit(
                MatchEventType.DRIBBLE,
                actor_agent_id=result.attacker_agent_id,
                secondary_agent_id=result.defender_agent_id,
                data=(("outcome", result.outcome.value),),
            )
            return
        if action is ActionType.CROSS:
            self.engine.start_cross(decision)
            self._emit(
                MatchEventType.CROSS,
                actor_agent_id=decision.agent_id,
                secondary_agent_id=decision.target_agent_id,
                data=(("status", "attempt"),),
            )
            return
        if action is ActionType.SHOOT:
            active = self.engine.start_shot(decision)
            shooter = self.engine.state.agent(decision.agent_id)
            self._active_shot_id = (
                f"shot:{active.started_tick}:{decision.agent_id}:{self._event_sequence + 1}"
            )
            self._emit(
                MatchEventType.SHOT,
                side=shooter.side,
                actor_agent_id=decision.agent_id,
                data=(
                    ("shot_id", self._active_shot_id),
                    ("xg", f"{active.profile.xg:.4f}"),
                    ("body_part", active.profile.body_part.value),
                    ("chance_origin", active.profile.chance_origin.value),
                ),
            )
            return
        if action is ActionType.CLEARANCE:
            self._start_clearance(decision)

    def _start_clearance(self, decision: PlayerDecision) -> None:
        owner = self.engine.state.agent(decision.agent_id)
        perception = self.engine.perceive(owner.agent_id)
        if not perception.passing_lanes:
            return
        lane = max(
            perception.passing_lanes,
            key=lambda item: (
                item.forward_progress_m,
                item.distance_m,
                item.receiver_agent_id,
            ),
        )
        clearance = PlayerDecision(
            agent_id=owner.agent_id,
            action_type=ActionType.LONG_PASS,
            target_agent_id=lane.receiver_agent_id,
            utility=decision.utility,
            considered_options=decision.considered_options,
        )
        self.engine.start_pass(clearance)
        self._emit(
            MatchEventType.PASS,
            actor_agent_id=owner.agent_id,
            secondary_agent_id=lane.receiver_agent_id,
            data=(("action", ActionType.CLEARANCE.value), ("status", "attempt")),
        )

    def _maybe_tackle_or_foul(self, owner_id: str) -> bool:
        owner = self.engine.state.agent(owner_id)
        if not owner.is_active:
            return False
        plan = self.engine.pressing_plan(owner.side.opponent)
        primary = plan.primary
        if primary is None:
            return False
        defender = self.engine.state.agent(primary.defender_agent_id)
        distance = defender.location.distance_to(owner.location)
        if distance > self.engine.defending.config.tackle_radius_m:
            return False

        pair = (defender.agent_id, owner.agent_id)
        if self.engine.state.clock.tick_count < self._next_duel_tick_by_pair.get(pair, 0):
            return False
        try:
            profile = self.engine.defensive_duel_profile(defender.agent_id)
        except ValueError:
            return False

        # Contact/foul checks only happen when the defender actually commits to
        # a challenge. Previously every close pressing tick could become a foul,
        # creating dozens of fouls and cards per match.
        attempt_probability = min(max(profile.tackle_willingness / 100.0 * 0.22, 0.025), 0.24)
        if self._duel_random.random() > attempt_probability:
            return False

        recovery_ticks = max(
            1,
            round(self.config.duel_recovery_seconds / self.engine.timestep_seconds),
        )
        self._next_duel_tick_by_pair[pair] = self.engine.state.clock.tick_count + recovery_ticks

        foul = self.engine.context.foul_assessment(self.engine.state, defender, owner)
        if self._duel_random.random() <= foul.foul_probability:
            card = self.engine.context.choose_card(foul, self._duel_random.random())
            will_dismiss = (
                card is CardType.RED
                or (card is CardType.YELLOW and defender.yellow_cards >= 1)
            )
            advantage = (
                not will_dismiss
                and self._duel_random.random() <= foul.advantage_probability
            )
            self.register_foul(
                defender.agent_id,
                owner.agent_id,
                assessment=foul,
                card=card,
                advantage=advantage,
            )
            self._next_action_tick = max(
                self._next_action_tick,
                self.engine.state.clock.tick_count + recovery_ticks,
            )
            return not advantage

        result = self.engine.attempt_tackle(defender.agent_id)
        self._emit(
            MatchEventType.TACKLE,
            side=defender.side,
            actor_agent_id=defender.agent_id,
            secondary_agent_id=owner.agent_id,
            data=(("outcome", result.outcome.value),),
        )
        self._next_action_tick = max(
            self._next_action_tick,
            self.engine.state.clock.tick_count + recovery_ticks,
        )
        return True

    def _decision_cooldown_seconds(self, decision: PlayerDecision) -> float:
        owner = self.engine.state.agent(decision.agent_id)
        tactic = self.engine.runtime_tactic(owner.side)
        tempo = float(tactic.team_instructions.in_possession.tempo)
        # NORMAL tempo uses the configured baseline. Extreme tempo settings alter
        # cadence, but even VERY HIGH tempo still leaves human-scale time for the
        # action to develop on the pitch.
        tempo_factor = 1.28 - (tempo / 100.0) * 0.52
        action_factor = {
            ActionType.HOLD: 0.82,
            ActionType.SHORT_PASS: 0.96,
            ActionType.PROGRESSIVE_PASS: 1.04,
            ActionType.LONG_PASS: 1.10,
            ActionType.CARRY: 1.16,
            ActionType.DRIBBLE: 1.18,
            ActionType.CROSS: 1.12,
            ActionType.SHOOT: 1.15,
            ActionType.CLEARANCE: 1.00,
        }[decision.action_type]
        pressure = self.engine.perceive(owner.agent_id).pressure
        pressure_factor = 1.0 - min(max(pressure, 0.0), 1.0) * 0.12
        return min(
            max(self.config.decision_cooldown_seconds * tempo_factor * action_factor * pressure_factor, 2.6),
            7.5,
        )

    # ------------------------------------------------------------------
    # Action outcomes and score/restarts
    # ------------------------------------------------------------------
    def _handle_resolved_actions(self) -> None:
        tick = self.engine.state.clock.tick_count
        pass_result = self.engine.last_pass_result
        if pass_result is not None and pass_result.resolved_tick == tick:
            self._emit(
                MatchEventType.PASS,
                actor_agent_id=pass_result.passer_agent_id,
                secondary_agent_id=pass_result.controller_agent_id,
                data=(("outcome", pass_result.outcome.value),),
            )
            if pass_result.outcome is PassOutcome.MISPLACED:
                self._maybe_award_boundary_restart()

        carry_result = self.engine.last_carry_result
        if carry_result is not None and carry_result.resolved_tick == tick:
            self._emit(
                MatchEventType.CARRY,
                actor_agent_id=carry_result.carrier_agent_id,
                data=(("outcome", carry_result.outcome.value),),
            )

        cross_result = self.engine.last_cross_result
        if cross_result is not None and cross_result.resolved_tick == tick:
            self._emit(
                MatchEventType.CROSS,
                actor_agent_id=cross_result.crosser_agent_id,
                secondary_agent_id=cross_result.controller_agent_id,
                data=(("outcome", cross_result.outcome.value),),
            )
            if cross_result.outcome is CrossOutcome.MISPLACED:
                self._maybe_award_boundary_restart()

        shot_result = self.engine.last_shot_result
        if shot_result is not None and shot_result.resolved_tick == tick:
            shooter = self.engine.state.agent(shot_result.shooter_agent_id)
            shot_id = self._active_shot_id or (
                f"shot:{shot_result.started_tick}:{shot_result.shooter_agent_id}:recovered"
            )
            result_data = (
                ("shot_id", shot_id),
                ("xg", f"{shot_result.xg:.4f}"),
                ("outcome", shot_result.outcome.value),
            )
            if shot_result.outcome is ShotOutcome.GOAL:
                self.score.add_goal(shooter.side)
                self._record_stoppage(45.0)
                self._emit(
                    MatchEventType.GOAL,
                    side=shooter.side,
                    actor_agent_id=shooter.agent_id,
                    data=result_data,
                )
                self.award_restart(RestartType.KICKOFF, shooter.side.opponent)
            elif shot_result.outcome in {ShotOutcome.SAVED, ShotOutcome.PARRIED}:
                self._emit(
                    MatchEventType.SAVE,
                    side=shooter.side.opponent,
                    actor_agent_id=shot_result.goalkeeper_agent_id,
                    secondary_agent_id=shooter.agent_id,
                    data=result_data,
                )
            elif shot_result.outcome is ShotOutcome.BLOCKED:
                self._emit(
                    MatchEventType.BLOCK,
                    side=shooter.side.opponent,
                    actor_agent_id=shot_result.blocker_agent_id,
                    secondary_agent_id=shooter.agent_id,
                    data=result_data,
                )
            elif shot_result.outcome is ShotOutcome.WOODWORK:
                self._emit(
                    MatchEventType.WOODWORK,
                    side=shooter.side,
                    actor_agent_id=shooter.agent_id,
                    data=result_data,
                )
            elif shot_result.outcome is ShotOutcome.OFF_TARGET:
                self._emit(
                    MatchEventType.OFF_TARGET,
                    side=shooter.side,
                    actor_agent_id=shooter.agent_id,
                    data=result_data,
                )
                self.award_restart(RestartType.GOAL_KICK, shooter.side.opponent)
            self._active_shot_id = None

    def _ball_action_active(self) -> bool:
        return bool(
            self.engine.active_pass is not None
            or self.engine.active_carry is not None
            or self.engine.active_cross is not None
            or self.engine.active_shot is not None
        )

    def _handle_loose_ball(self) -> None:
        if self._ball_action_active() or self.engine.state.ball.owner_agent_id is not None:
            self._loose_since_tick = None
            return
        if self._maybe_award_boundary_restart():
            self._loose_since_tick = None
            return
        tick = self.engine.state.clock.tick_count
        if self._loose_since_tick is None:
            self._loose_since_tick = tick
            return
        elapsed = (tick - self._loose_since_tick) * self.engine.timestep_seconds
        nearest = min(
            self.engine.state.active_players,
            key=lambda agent: (agent.location.distance_to(self.engine.state.ball.location), agent.agent_id),
        )
        distance = nearest.location.distance_to(self.engine.state.ball.location)
        if elapsed < self.config.loose_ball_collection_seconds:
            return
        if distance > 8.0 and elapsed < self.config.forced_loose_ball_collection_seconds:
            return
        self.engine.give_ball_to(nearest.agent_id)
        self._emit(
            MatchEventType.RECOVERY,
            side=nearest.side,
            actor_agent_id=nearest.agent_id,
        )
        self._loose_since_tick = None

    # ------------------------------------------------------------------
    # Dead-ball restarts
    # ------------------------------------------------------------------
    def register_foul(
        self,
        committing_agent_id: str,
        fouled_agent_id: str,
        *,
        assessment: FoulAssessment | None = None,
        card: CardType | None = None,
        advantage: bool = False,
    ) -> None:
        committing = self.engine.state.agent(committing_agent_id)
        fouled = self.engine.state.agent(fouled_agent_id)
        if committing.side is fouled.side:
            raise ValueError("a foul requires players from opposing teams")
        location = fouled.location
        is_penalty = bool(assessment is not None and assessment.is_penalty_area)
        if is_penalty:
            advantage = False

        effective_card = card
        if card is CardType.YELLOW and committing.yellow_cards >= 1:
            effective_card = CardType.SECOND_YELLOW_RED
        if effective_card in {CardType.RED, CardType.SECOND_YELLOW_RED}:
            advantage = False

        foul_data: list[tuple[str, str]] = [
            ("advantage", "true" if advantage else "false"),
            ("penalty_area", "true" if is_penalty else "false"),
        ]
        if assessment is not None:
            foul_data.extend(
                (
                    ("severity", f"{assessment.severity:.4f}"),
                    ("foul_probability", f"{assessment.foul_probability:.4f}"),
                )
            )

        self._emit(
            MatchEventType.FOUL,
            side=fouled.side,
            actor_agent_id=committing.agent_id,
            secondary_agent_id=fouled.agent_id,
            data=tuple(foul_data),
        )

        actual_card = (
            self._apply_card(committing.agent_id, effective_card)
            if effective_card is not None
            else None
        )

        if advantage:
            return

        self._record_stoppage(24.0 if actual_card is not None else 20.0)
        if is_penalty:
            self._emit(
                MatchEventType.PENALTY_AWARDED,
                side=fouled.side,
                actor_agent_id=fouled.agent_id,
                secondary_agent_id=committing.agent_id,
                restart_type=RestartType.PENALTY,
            )
            self._take_in_match_penalty(fouled.side)
            return
        self.award_restart(RestartType.FREE_KICK, fouled.side, location=location)

    def _apply_card(self, agent_id: str, card: CardType | None) -> CardType | None:
        if card is None:
            return None
        agent = self.engine.state.agent(agent_id)
        actual = CardType(card)
        if actual is CardType.YELLOW:
            agent.yellow_cards += 1
            if agent.yellow_cards >= 2:
                actual = CardType.SECOND_YELLOW_RED
                agent.dismissed = True
        elif actual is CardType.SECOND_YELLOW_RED:
            agent.yellow_cards += 1
            agent.dismissed = True
        elif actual is CardType.RED:
            agent.dismissed = True

        if agent.dismissed:
            agent.velocity = Vector2.zero()
            agent.has_ball = False
            self.engine.progression.active_runs.pop(agent.agent_id, None)
            if agent.assigned_position is Position.GK:
                self._assign_emergency_goalkeeper(agent)
            self.engine.refresh_tactical_positioning()

        self._emit(
            MatchEventType.CARD,
            side=agent.side,
            actor_agent_id=agent.agent_id,
            data=(
                ("card", actual.value),
                ("yellow_count", str(agent.yellow_cards)),
                ("dismissed", "true" if agent.dismissed else "false"),
            ),
        )
        return actual

    def _assign_emergency_goalkeeper(self, dismissed_keeper: PlayerAgentState) -> None:
        """Keep an existing active outfielder in goal after a keeper red.

        The spatial shot, goal-kick and penalty systems all require an active
        goalkeeper. Use the same deterministic best-available-player fallback
        as the fast match engine, and the canonical in-match role/ACT rater.
        No player is added to the field, and the underlying lineup is intact.
        """
        side = dismissed_keeper.side
        candidates = tuple(
            player for player in self.engine.state.active_players_for_side(side)
            if player.assigned_position is not Position.GK
        )
        if not candidates:
            return
        replacement = max(candidates, key=lambda item: (item.player.current_rating, item.agent_id))
        tactic = self.engine.runtime_tactic(side)
        slot = tactic.slot(dismissed_keeper.slot_id)
        assigned = assign_match_player(
            replacement.player,
            slot_id=slot.slot_id,
            position=slot.position,
            role_id=slot.role_id,
            role_name=slot.role_name,
            tactic_id=tactic.tactic_id,
            instructions=slot.effective_instructions,
        )
        replacement.slot_id = slot.slot_id
        replacement.assigned_position = slot.position
        replacement.player = assigned
        # The referee has stopped play: the covering player can occupy the
        # vacated goalkeeper position before the restart.
        replacement.location = dismissed_keeper.location
        replacement.velocity = Vector2.zero()
        if self.engine.state.ball.owner_agent_id == replacement.agent_id:
            self.engine.state.ball.location = replacement.location

    def _take_in_match_penalty(self, side: TeamSide) -> bool:
        side = TeamSide(side)
        takers = self._penalty_takers(side)
        if not takers:
            raise RuntimeError("penalty requires an active outfield taker")
        taker = takers[0]
        goalkeeper = self.engine.state.player_for_slot(side.opponent, "gk")
        probability = self._penalty_probability(taker, goalkeeper)
        scored = self._penalty_random.random() <= probability
        self._emit(
            MatchEventType.PENALTY_KICK,
            side=side,
            actor_agent_id=taker.agent_id,
            secondary_agent_id=goalkeeper.agent_id,
            restart_type=RestartType.PENALTY,
            data=(
                ("scored", "true" if scored else "false"),
                ("probability", f"{probability:.4f}"),
                ("shootout", "false"),
            ),
        )
        if scored:
            self.score.add_goal(side)
            self._emit(
                MatchEventType.GOAL,
                side=side,
                actor_agent_id=taker.agent_id,
                data=(("penalty", "true"),),
            )
            self.award_restart(RestartType.KICKOFF, side.opponent)
        else:
            self.engine.give_ball_to(goalkeeper.agent_id)
            self._emit(
                MatchEventType.SAVE,
                side=goalkeeper.side,
                actor_agent_id=goalkeeper.agent_id,
                secondary_agent_id=taker.agent_id,
                data=(("penalty", "true"),),
            )
        return scored

    def award_restart(
        self,
        restart_type: RestartType,
        side: TeamSide,
        *,
        location: Vector2 | None = None,
    ) -> str:
        restart_type = RestartType(restart_type)
        side = TeamSide(side)
        self.engine.passing.cancel()
        self.engine.progression.cancel()
        self.engine.shooting.cancel()
        self._active_shot_id = None
        self._apply_pending_substitutions()
        self.engine.state.ball.height_m = 0.0
        self.engine.state.ball.velocity = Vector2.zero()

        if restart_type is RestartType.KICKOFF:
            controller_id = self._prepare_kickoff(side)
            controller = self.engine.state.agent(controller_id)
            restart_location = self.engine.state.pitch.centre
            stoppage = 0.0
        elif restart_type is RestartType.GOAL_KICK:
            controller = self.engine.state.player_for_slot(side, "gk")
            own_goal_x = 0.0 if side is TeamSide.HOME else self.engine.state.pitch.length_m
            restart_location = Vector2(
                own_goal_x + side.attack_sign * 5.5,
                self.engine.state.pitch.width_m / 2.0,
            )
            controller.location = restart_location
            self.engine.give_ball_to(controller.agent_id)
            stoppage = 15.0
        elif restart_type is RestartType.CORNER:
            restart_location = self._corner_location(side, location)
            controller = self._nearest_outfield(side, restart_location)
            controller.location = restart_location
            self.engine.give_ball_to(controller.agent_id)
            stoppage = 20.0
        elif restart_type is RestartType.THROW_IN:
            restart_location = self._throw_in_location(location)
            controller = self._nearest_outfield(side, restart_location)
            controller.location = restart_location
            self.engine.give_ball_to(controller.agent_id)
            stoppage = 10.0
        else:
            restart_location = self.engine.state.pitch.clamp(location or self.engine.state.ball.location)
            controller = self._nearest_outfield(side, restart_location)
            controller.location = restart_location
            self.engine.give_ball_to(controller.agent_id)
            stoppage = 12.0

        if stoppage > 0.0:
            self._record_stoppage(stoppage)
        self._emit(
            MatchEventType.RESTART,
            side=side,
            actor_agent_id=controller.agent_id,
            restart_type=restart_type,
            data=(
                ("x", f"{restart_location.x:.2f}"),
                ("y", f"{restart_location.y:.2f}"),
            ),
        )
        self._next_action_tick = self.engine.state.clock.tick_count + max(
            1,
            round(self.config.decision_cooldown_seconds / self.engine.timestep_seconds),
        )
        return controller.agent_id

    def _prepare_kickoff(self, side: TeamSide) -> str:
        # Rebuild a neutral restart shape from the *runtime* positions.  Looking
        # agents up by the immutable snapshot ID breaks after a substitution,
        # and using the snapshot formation would also ignore an in-match
        # formation change.
        pitch = self.engine.state.pitch
        active = list(self.engine.state.active_players)
        by_key: dict[tuple[TeamSide, Position], list[PlayerAgentState]] = {}
        for agent in active:
            by_key.setdefault((agent.side, agent.assigned_position), []).append(agent)

        for agents in by_key.values():
            agents.sort(key=lambda item: item.slot_id)
            count = len(agents)
            centre = (count - 1) / 2.0
            for index, agent in enumerate(agents):
                x_norm, y_norm = normalized_anchor(agent.assigned_position)
                if count > 1:
                    y_norm += (index - centre) * 0.13
                y_norm = min(max(y_norm, 0.05), 0.95)
                location = Vector2(x_norm * pitch.length_m, y_norm * pitch.width_m)
                if agent.side is TeamSide.AWAY:
                    location = pitch.mirror(location)
                agent.location = location
                agent.velocity = Vector2.zero()
                agent.facing = Vector2(agent.side.attack_sign, 0.0)
                agent.tactical_target = None
                agent.tactical_phase = None
                agent.has_ball = False

        for agent in self.engine.state.players.values():
            if not agent.is_active:
                agent.velocity = Vector2.zero()
                agent.tactical_target = None
                agent.tactical_phase = None
                agent.has_ball = False

        try:
            controller = self.engine.state.player_for_slot(side, "st")
        except KeyError:
            controller = self._nearest_outfield(side, pitch.centre)
        controller.location = pitch.centre
        self.engine.give_ball_to(controller.agent_id)
        return controller.agent_id

    def _maybe_award_boundary_restart(self) -> bool:
        state = self.engine.state
        if state.ball.owner_agent_id is not None or self._ball_action_active():
            return False
        eps = 0.05
        ball = state.ball.location
        at_touchline = ball.y <= eps or ball.y >= state.pitch.width_m - eps
        at_goal_line = ball.x <= eps or ball.x >= state.pitch.length_m - eps
        if not at_touchline and not at_goal_line:
            return False
        last = (
            state.agent(state.ball.last_touch_agent_id)
            if state.ball.last_touch_agent_id in state.players
            else None
        )
        if last is None:
            return False

        if at_touchline:
            self.award_restart(RestartType.THROW_IN, last.side.opponent, location=ball)
            return True

        defending_side = TeamSide.HOME if ball.x <= eps else TeamSide.AWAY
        attacking_side = defending_side.opponent
        if last.side is attacking_side:
            self.award_restart(RestartType.GOAL_KICK, defending_side, location=ball)
        else:
            self.award_restart(RestartType.CORNER, attacking_side, location=ball)
        return True

    def _corner_location(self, side: TeamSide, location: Vector2 | None) -> Vector2:
        x = self.engine.state.pitch.length_m if side is TeamSide.HOME else 0.0
        reference_y = (location.y if location is not None else self.engine.state.ball.location.y)
        y = 0.0 if reference_y <= self.engine.state.pitch.width_m / 2.0 else self.engine.state.pitch.width_m
        return Vector2(x, y)

    def _throw_in_location(self, location: Vector2 | None) -> Vector2:
        base = location or self.engine.state.ball.location
        y = 0.0 if base.y <= self.engine.state.pitch.width_m / 2.0 else self.engine.state.pitch.width_m
        return Vector2(min(max(base.x, 0.0), self.engine.state.pitch.length_m), y)

    def _nearest_outfield(self, side: TeamSide, location: Vector2):
        candidates = [
            agent
            for agent in self.engine.state.active_players
            if agent.side is side and agent.assigned_position is not Position.GK
        ]
        return min(candidates, key=lambda agent: (agent.location.distance_to(location), agent.agent_id))

    def record_stoppage(self, seconds: float) -> None:
        """Register dead time that can contribute to the current period's added time."""

        if seconds < 0.0:
            raise ValueError("stoppage seconds cannot be negative")
        self._record_stoppage(seconds)

    def _record_stoppage(self, seconds: float) -> None:
        if self._period is not None and seconds > 0.0:
            self._period.stoppage_seconds += seconds

    # ------------------------------------------------------------------
    # In-match management
    # ------------------------------------------------------------------
    def available_substitutes(self, side: TeamSide) -> tuple[PlayerMatchSnapshot, ...]:
        side = TeamSide(side)
        team = self.snapshot.home_team if side is TeamSide.HOME else self.snapshot.away_team
        used = self._used_substitutes[side]
        pending_incoming = {incoming for _, incoming in self._pending_substitutions[side]}
        active_player_ids = {
            agent.player.player_id
            for agent in self.engine.state.active_players_for_side(side)
        }
        return tuple(
            player
            for player in team.bench
            if player.player_id not in used
            and player.player_id not in pending_incoming
            and player.player_id not in active_player_ids
        )

    def pending_substitution_count(self, side: TeamSide) -> int:
        return len(self._pending_substitutions[TeamSide(side)])

    def substitutions_remaining(self, side: TeamSide) -> int:
        side = TeamSide(side)
        rules = self.snapshot.context.competition
        limit = rules.substitution_limit
        if self.phase in {
            MatchPhase.EXTRA_TIME_FIRST_HALF,
            MatchPhase.EXTRA_TIME_INTERVAL,
            MatchPhase.EXTRA_TIME_SECOND_HALF,
        }:
            limit += rules.extra_time_additional_substitutions
        return max(0, limit - self._substitutions_used[side])

    def request_substitution(
        self,
        side: TeamSide,
        outgoing_agent_id: str,
        incoming_player_id: str,
    ) -> bool:
        """Queue a manager substitution for the next natural stoppage.

        Returns ``True`` when it can be applied immediately (for example before
        live play starts at a period boundary) and ``False`` when it is queued.
        The debug UI can therefore accept changes at any match minute without
        cancelling a pass/shot that is already physically in flight.
        """

        side = TeamSide(side)
        if self.phase in {MatchPhase.PRE_MATCH, MatchPhase.PENALTY_SHOOTOUT, MatchPhase.FINISHED}:
            raise ValueError("substitutions are not available in the current match phase")
        if self.substitutions_remaining(side) - len(self._pending_substitutions[side]) <= 0:
            raise ValueError("no substitutions remaining")
        outgoing = self.engine.state.agent(outgoing_agent_id)
        if outgoing.side is not side or not outgoing.is_active:
            raise ValueError("outgoing player must be active for the selected side")
        if any(existing_out == outgoing_agent_id for existing_out, _ in self._pending_substitutions[side]):
            raise ValueError("that player already has a pending substitution")
        if incoming_player_id not in {player.player_id for player in self.available_substitutes(side)}:
            raise ValueError("incoming player is not an available substitute")

        # Half-time/extra-time interval is already a dead-ball state.
        if self.phase in {MatchPhase.HALF_TIME, MatchPhase.EXTRA_TIME_INTERVAL}:
            self.make_substitution(side, outgoing_agent_id, incoming_player_id)
            return True

        self._pending_substitutions[side].append((outgoing_agent_id, incoming_player_id))
        return False

    def _apply_pending_substitutions(self) -> None:
        for side in (TeamSide.HOME, TeamSide.AWAY):
            pending = list(self._pending_substitutions[side])
            self._pending_substitutions[side].clear()
            for outgoing_agent_id, incoming_player_id in pending:
                try:
                    self.make_substitution(side, outgoing_agent_id, incoming_player_id)
                except ValueError:
                    # A player can be dismissed/injured out of the active state
                    # before the requested stoppage. Do not corrupt match flow.
                    continue

    def make_substitution(
        self,
        side: TeamSide,
        outgoing_agent_id: str,
        incoming_player_id: str,
    ) -> str:
        """Replace one active player while preserving the tactical slot.

        The frozen MatchSnapshot is never mutated. The incoming bench snapshot is
        adapted to the outgoing player's current slot/role for the mutable runtime
        state. Position/role/tactic familiarity therefore still affects execution.
        """

        side = TeamSide(side)
        if self.phase in {MatchPhase.PRE_MATCH, MatchPhase.PENALTY_SHOOTOUT, MatchPhase.FINISHED}:
            raise ValueError("substitutions are not available in the current match phase")
        if self.substitutions_remaining(side) <= 0:
            raise ValueError("no substitutions remaining")
        if self._ball_action_active():
            raise ValueError("wait for the current ball action to resolve before substituting")

        outgoing = self.engine.state.agent(outgoing_agent_id)
        if outgoing.side is not side or not outgoing.is_active:
            raise ValueError("outgoing player must be active for the selected side")
        incoming = next(
            (player for player in self.available_substitutes(side) if player.player_id == incoming_player_id),
            None,
        )
        if incoming is None:
            raise ValueError("incoming player is not an available substitute")

        tactic = self.engine.runtime_tactic(side)
        slot = tactic.slot(outgoing.slot_id)
        runtime_player = assign_match_player(
            incoming,
            slot_id=outgoing.slot_id,
            position=slot.position,
            role_id=slot.role_id,
            role_name=slot.role_name,
            tactic_id=tactic.tactic_id,
            instructions=slot.effective_instructions,
        )
        new_agent_id = f"{side.value}:{incoming.player_id}"
        if new_agent_id in self.engine.state.players:
            raise ValueError("incoming player already exists in runtime state")

        was_owner = self.engine.state.ball.owner_agent_id == outgoing.agent_id
        new_agent = PlayerAgentState(
            agent_id=new_agent_id,
            side=side,
            player=runtime_player,
            slot_id=outgoing.slot_id,
            assigned_position=outgoing.assigned_position,
            location=outgoing.location,
            velocity=Vector2.zero(),
            facing=outgoing.facing,
            has_ball=was_owner,
            current_fitness=float(incoming.state.fitness),
            current_fatigue=float(incoming.state.fatigue),
        )

        self._substituted_out_conditions.append(
            PlayerConditionResult(
                agent_id=outgoing.agent_id,
                fitness=outgoing.current_fitness,
                fatigue=outgoing.current_fatigue,
            )
        )
        self._substituted_out_discipline.append(
            PlayerDisciplineResult(
                agent_id=outgoing.agent_id,
                yellow_cards=outgoing.yellow_cards,
                dismissed=outgoing.dismissed,
            )
        )
        self.engine.progression.cancel()
        del self.engine.state.players[outgoing.agent_id]
        self.engine.state.players[new_agent_id] = new_agent
        if was_owner:
            self.engine.state.ball.owner_agent_id = new_agent_id
            self.engine.state.ball.last_touch_agent_id = new_agent_id
            self.engine.state.possession.owner_agent_id = new_agent_id
            self.engine.state.possession.team_side = side
        elif self.engine.state.possession.owner_agent_id == outgoing.agent_id:
            self.engine.state.possession.owner_agent_id = None

        self._used_substitutes[side].add(incoming.player_id)
        self._substitutions_used[side] += 1
        self.engine.refresh_tactical_positioning()
        self._emit(
            MatchEventType.SUBSTITUTION,
            side=side,
            actor_agent_id=outgoing.agent_id,
            secondary_agent_id=new_agent_id,
            data=(
                ("slot_id", outgoing.slot_id),
                ("remaining", str(self.substitutions_remaining(side))),
            ),
        )
        return new_agent_id

    def apply_runtime_tactic(
        self,
        side: TeamSide,
        tactic: TacticMatchSnapshot,
        *,
        label: str | None = None,
    ) -> None:
        side = TeamSide(side)
        self.engine.set_runtime_tactic(side, tactic)
        self._emit(
            MatchEventType.TACTICAL_CHANGE,
            side=side,
            data=(("label", label or tactic.name),),
        )

    @staticmethod
    def _snapshot_role_suitability(player: PlayerMatchSnapshot, role_id: str) -> float:
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

    # ------------------------------------------------------------------
    # Penalty shootout
    # ------------------------------------------------------------------
    def _run_penalty_shootout(self) -> None:
        if self.phase is not MatchPhase.PENALTY_SHOOTOUT:
            raise ValueError("penalty shootout is not active")
        home_takers = self._penalty_takers(TeamSide.HOME)
        away_takers = self._penalty_takers(TeamSide.AWAY)
        home_kicks = 0
        away_kicks = 0

        for index in range(5):
            if self._take_penalty(TeamSide.HOME, home_takers[index % len(home_takers)]):
                self.score.penalties_home += 1
            home_kicks += 1
            if self._shootout_decided(home_kicks, away_kicks, 5):
                break
            if self._take_penalty(TeamSide.AWAY, away_takers[index % len(away_takers)]):
                self.score.penalties_away += 1
            away_kicks += 1
            if self._shootout_decided(home_kicks, away_kicks, 5):
                break

        sudden = 0
        while self.score.penalties_home == self.score.penalties_away:
            home_taker = home_takers[(5 + sudden) % len(home_takers)]
            away_taker = away_takers[(5 + sudden) % len(away_takers)]
            if self._take_penalty(TeamSide.HOME, home_taker):
                self.score.penalties_home += 1
            if self._take_penalty(TeamSide.AWAY, away_taker):
                self.score.penalties_away += 1
            sudden += 1
            # A penalty score may change only because of an actual kick.
            # Even a very long seeded shootout must not invent a winner or
            # award an unrecorded goal after an arbitrary number of rounds.

        winner = (
            TeamSide.HOME
            if self.score.penalties_home > self.score.penalties_away
            else TeamSide.AWAY
        )
        self._finish(MatchEndReason.PENALTIES, winner=winner)

    def _shootout_decided(self, home_kicks: int, away_kicks: int, scheduled: int) -> bool:
        home_remaining = scheduled - home_kicks
        away_remaining = scheduled - away_kicks
        return (
            self.score.penalties_home > self.score.penalties_away + away_remaining
            or self.score.penalties_away > self.score.penalties_home + home_remaining
        )

    def _penalty_takers(self, side: TeamSide):
        players = [
            agent
            for agent in self.engine.state.active_players
            if agent.side is side and agent.assigned_position is not Position.GK
        ]
        return tuple(
            sorted(
                players,
                key=lambda agent: (
                    -agent.player.attributes.technical.penalties,
                    -agent.player.attributes.mental.composure,
                    agent.agent_id,
                ),
            )
        )

    def _penalty_probability(self, taker, goalkeeper) -> float:
        tech = taker.player.attributes.technical
        mental = taker.player.attributes.mental
        taker_quality = tech.penalties * 0.55 + tech.finishing * 0.20 + mental.composure * 0.25
        taker_quality += ((taker.current_fitness - taker.current_fatigue) - 50.0) * 0.025
        gk = goalkeeper.player.attributes.goalkeeping
        if gk is not None:
            gk_quality = gk.one_on_ones * 0.45 + gk.reflexes * 0.35 + gk.goalkeeper_positioning * 0.20
        else:
            gk_quality = (
                goalkeeper.player.attributes.mental.anticipation * 0.40
                + goalkeeper.player.attributes.physical.agility * 0.35
                + goalkeeper.player.attributes.mental.positioning * 0.25
            )
        gk_quality += ((goalkeeper.current_fitness - goalkeeper.current_fatigue) - 50.0) * 0.02
        return min(
            max(0.76 + (taker_quality - 70.0) * 0.003 - (gk_quality - 70.0) * 0.0022, 0.52),
            0.94,
        )

    def _take_penalty(self, side: TeamSide, taker) -> bool:
        goalkeeper = self.engine.state.player_for_slot(side.opponent, "gk")
        probability = self._penalty_probability(taker, goalkeeper)
        scored = self._penalty_random.random() <= probability
        self._emit(
            MatchEventType.PENALTY_KICK,
            side=side,
            actor_agent_id=taker.agent_id,
            secondary_agent_id=goalkeeper.agent_id,
            data=(
                ("scored", "true" if scored else "false"),
                ("probability", f"{probability:.4f}"),
                ("shootout", "true"),
            ),
        )
        return scored

    # ------------------------------------------------------------------
    # Event/time helpers
    # ------------------------------------------------------------------
    def _emit(
        self,
        event_type: MatchEventType,
        *,
        side: TeamSide | None = None,
        actor_agent_id: str | None = None,
        secondary_agent_id: str | None = None,
        restart_type: RestartType | None = None,
        data: tuple[tuple[str, str], ...] = (),
    ) -> MatchEvent:
        self._event_sequence += 1
        event_data = list(data)
        existing_keys = {key for key, _ in event_data}
        if actor_agent_id in self.engine.state.players:
            actor = self.engine.state.agent(actor_agent_id)
            if "x" not in existing_keys:
                event_data.append(("x", f"{actor.location.x:.2f}"))
            if "y" not in existing_keys:
                event_data.append(("y", f"{actor.location.y:.2f}"))
        event = MatchEvent(
            sequence=self._event_sequence,
            tick=self.engine.state.clock.tick_count,
            time_label=self.time_label,
            phase=self.phase,
            event_type=MatchEventType(event_type),
            side=TeamSide(side) if side is not None else None,
            actor_agent_id=actor_agent_id,
            secondary_agent_id=secondary_agent_id,
            restart_type=RestartType(restart_type) if restart_type is not None else None,
            data=tuple(event_data),
        )
        self.events.append(event)
        return event

    def _format_period_time(self, phase: MatchPhase, elapsed_seconds: float) -> str:
        if phase in {MatchPhase.FIRST_HALF, MatchPhase.HALF_TIME}:
            base_minutes = 0
            nominal = self.config.regulation_half_seconds
            official_nominal = 45
        elif phase is MatchPhase.SECOND_HALF:
            base_minutes = 45
            nominal = self.config.regulation_half_seconds
            official_nominal = 90
        elif phase in {MatchPhase.EXTRA_TIME_FIRST_HALF, MatchPhase.EXTRA_TIME_INTERVAL}:
            base_minutes = 90
            nominal = self.config.extra_time_half_seconds
            official_nominal = 105
        elif phase is MatchPhase.EXTRA_TIME_SECOND_HALF:
            base_minutes = 105
            nominal = self.config.extra_time_half_seconds
            official_nominal = 120
        else:
            return "PEN" if phase is MatchPhase.PENALTY_SHOOTOUT else "0'"

        if elapsed_seconds <= nominal:
            fraction = elapsed_seconds / nominal if nominal > 0.0 else 0.0
            period_official_minutes = (official_nominal - base_minutes) * fraction
            minute = base_minutes + int(period_official_minutes)
            return f"{minute}'"

        extra_seconds = elapsed_seconds - nominal
        unit = self.config.added_time_unit_seconds
        extra_units = max(1, int(ceil(extra_seconds / unit)))
        # If live action overruns the announced minimum added time by a fraction
        # of a tick, do not visually invent an extra whole minute (45+9 after
        # announcing +8). The period can still finish after the active action.
        if self._period is not None and self._period.added_seconds is not None:
            announced_units = max(1, int(round(self._period.added_seconds / unit)))
            extra_units = min(extra_units, announced_units)
        return f"{official_nominal}+{extra_units}'"
