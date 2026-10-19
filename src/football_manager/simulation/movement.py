from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from hashlib import blake2b

from football_manager.domain import (
    InPossessionPosition,
    MatchSnapshot,
    Position,
    TacticMatchSnapshot,
)

from .geometry import Vector2
from .match_context_effects import MatchContextSystem
from .spatial_state import MatchState, PlayerAgentState, TeamSide


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return min(max(value, minimum), maximum)


def _lerp(a: float, b: float, weight: float) -> float:
    weight = _clamp(weight, 0.0, 1.0)
    return a + (b - a) * weight


class MovementIntentType(StrEnum):
    """Short-lived football intentions for players without the ball.

    A player's registered position and tactical formation remain references.  The
    current intention explains what the player is *actually trying to do now*.
    Intentions persist for several simulated seconds so movement develops as a
    trajectory rather than a new formation target every 0.25 s.
    """

    HOLD_STRUCTURE = "hold_structure"
    SUPPORT_BALL = "support_ball"
    OFFER_LANE = "offer_lane"
    DROP_TO_RECEIVE = "drop_to_receive"
    RUN_IN_BEHIND = "run_in_behind"
    ATTACK_BOX = "attack_box"
    STAY_WIDE = "stay_wide"
    MOVE_INSIDE = "move_inside"
    OVERLAP = "overlap"
    UNDERLAP = "underlap"
    INVERT = "invert"
    DROP_BETWEEN_CBS = "drop_between_cbs"
    STEP_INTO_SPACE = "step_into_space"
    COVER_SPACE = "cover_space"
    TRACK_RUNNER = "track_runner"
    RECOVER_SHAPE = "recover_shape"


@dataclass(frozen=True, slots=True)
class MovementIntent:
    agent_id: str
    intent_type: MovementIntentType
    target: Vector2
    started_tick: int
    expires_tick: int
    priority: float
    reason: str

    def is_expired(self, tick: int) -> bool:
        return tick >= self.expires_tick


@dataclass(frozen=True, slots=True)
class OrganicMovementConfig:
    min_intent_seconds: float = 3.0
    max_intent_seconds: float = 7.0
    arrival_radius_m: float = 0.75
    base_off_ball_speed_mps: float = 4.75
    max_acceleration_mps2: float = 4.2
    max_deceleration_mps2: float = 5.8
    teammate_spacing_m: float = 3.8
    touchline_margin_m: float = 2.0
    max_attacking_lead_m: float = 33.0
    max_support_lead_m: float = 17.0
    max_support_trail_m: float = 36.0
    offside_buffer_m: float = 0.65

    def __post_init__(self) -> None:
        if self.min_intent_seconds <= 0.0:
            raise ValueError("min_intent_seconds must be positive")
        if self.max_intent_seconds < self.min_intent_seconds:
            raise ValueError("max_intent_seconds must be >= min_intent_seconds")
        if self.arrival_radius_m <= 0.0:
            raise ValueError("arrival_radius_m must be positive")
        if self.base_off_ball_speed_mps <= 0.0:
            raise ValueError("base_off_ball_speed_mps must be positive")
        if self.max_acceleration_mps2 <= 0.0 or self.max_deceleration_mps2 <= 0.0:
            raise ValueError("movement acceleration/deceleration must be positive")
        if self.teammate_spacing_m < 0.0:
            raise ValueError("teammate_spacing_m cannot be negative")
        if self.max_attacking_lead_m <= self.max_support_lead_m:
            raise ValueError("attacking lead must exceed support lead")
        if self.offside_buffer_m < 0.0:
            raise ValueError("offside_buffer_m cannot be negative")


@dataclass(frozen=True, slots=True)
class _IntentCandidate:
    intent_type: MovementIntentType
    score: float
    reason: str


class OrganicMovementSystem:
    """Continuous off-ball behaviour for every active outfield player.

    Phase 5.1 formation coordinates are intentionally treated as *anchors*, not
    rails.  The live target is built from the ball, the team phase, nearby space,
    role/player instructions and persistent individual intentions.  The result is
    still tactically coherent, but a full-back can overlap, a pivot can drop
    between centre-backs, an interior can attack the box and a winger can come
    inside without being pulled back to a rigid row on the next tick.

    The current ball owner is deliberately excluded.  On-ball movement must be an
    explicit carry/dribble/action so the event stream and 2D state cannot diverge.
    """

    _ATTACKING_INTENTS = frozenset(
        {
            MovementIntentType.SUPPORT_BALL,
            MovementIntentType.OFFER_LANE,
            MovementIntentType.DROP_TO_RECEIVE,
            MovementIntentType.RUN_IN_BEHIND,
            MovementIntentType.ATTACK_BOX,
            MovementIntentType.STAY_WIDE,
            MovementIntentType.MOVE_INSIDE,
            MovementIntentType.OVERLAP,
            MovementIntentType.UNDERLAP,
            MovementIntentType.INVERT,
            MovementIntentType.DROP_BETWEEN_CBS,
            MovementIntentType.STEP_INTO_SPACE,
        }
    )
    _DEFENDING_INTENTS = frozenset(
        {
            MovementIntentType.COVER_SPACE,
            MovementIntentType.TRACK_RUNNER,
            MovementIntentType.RECOVER_SHAPE,
        }
    )
    _COMMITTED_RUNS = frozenset(
        {
            MovementIntentType.RUN_IN_BEHIND,
            MovementIntentType.ATTACK_BOX,
            MovementIntentType.OVERLAP,
            MovementIntentType.UNDERLAP,
        }
    )

    def __init__(
        self,
        snapshot: MatchSnapshot,
        *,
        context: MatchContextSystem | None = None,
        config: OrganicMovementConfig | None = None,
    ) -> None:
        self.snapshot = snapshot
        self.context = context or MatchContextSystem(snapshot)
        self.config = config or OrganicMovementConfig()
        self._runtime_tactics: dict[TeamSide, TacticMatchSnapshot] = {
            TeamSide.HOME: snapshot.home_team.tactic,
            TeamSide.AWAY: snapshot.away_team.tactic,
        }
        self._intents: dict[str, MovementIntent] = {}
        self._intent_serial: dict[str, int] = {}
        self._last_possession_side: TeamSide | None = None
        self._possession_epoch = 0

    @property
    def intents(self) -> tuple[MovementIntent, ...]:
        return tuple(sorted(self._intents.values(), key=lambda item: item.agent_id))

    def intent_for(self, agent_id: str) -> MovementIntent | None:
        return self._intents.get(agent_id)

    def set_runtime_tactic(self, side: TeamSide, tactic: TacticMatchSnapshot) -> None:
        self._runtime_tactics[TeamSide(side)] = tactic
        # A manager intervention should be visible immediately.
        self._intents.clear()

    def reset(self) -> None:
        self._intents.clear()
        self._intent_serial.clear()
        self._last_possession_side = None
        self._possession_epoch = 0

    def update_velocities(
        self,
        state: MatchState,
        *,
        excluded_agent_ids: frozenset[str] = frozenset(),
    ) -> None:
        possession_side = state.possession.team_side
        if possession_side is not self._last_possession_side:
            self._intents.clear()
            self._last_possession_side = possession_side
            self._possession_epoch += 1

        active_ids = {agent.agent_id for agent in state.active_players}
        for agent_id in tuple(self._intents):
            if agent_id not in active_ids:
                self._intents.pop(agent_id, None)

        owner_id = state.ball.owner_agent_id
        structural_only = (
            owner_id is None
            and state.ball.velocity.magnitude <= 0.01
            and state.ball.height_m <= 0.01
        )

        for agent in state.active_players:
            if agent.agent_id == owner_id:
                agent.movement_intent = None
                agent.movement_target = None
                continue
            if agent.agent_id in excluded_agent_ids:
                continue

            # A no-owner/no-flight state is mostly used by tactical debug/tests.
            # In that state direct movement toward the tactical reference remains
            # intuitive and preserves the Phase 5.1 contract.
            if structural_only:
                target = agent.tactical_target or agent.location
                agent.movement_intent = MovementIntentType.HOLD_STRUCTURE.value
                agent.movement_target = target
                self._move_toward(agent, target, self._speed_for_structure(agent), state.clock.tick_seconds)
                continue

            intent = self._ensure_intent(state, agent)
            target = self._dynamic_target(state, agent, intent)
            target = self._apply_cohesion_envelope(state, agent, intent.intent_type, target)
            target = self._apply_spacing(state, agent, target)
            target = self._clamp_playable(state, target)

            refreshed = MovementIntent(
                agent_id=intent.agent_id,
                intent_type=intent.intent_type,
                target=target,
                started_tick=intent.started_tick,
                expires_tick=intent.expires_tick,
                priority=intent.priority,
                reason=intent.reason,
            )
            self._intents[agent.agent_id] = refreshed
            agent.movement_intent = refreshed.intent_type.value
            agent.movement_target = refreshed.target
            self._move_toward(agent, refreshed.target, self._speed(agent, refreshed), state.clock.tick_seconds)

    # ------------------------------------------------------------------
    # Intent lifecycle / deterministic variation
    # ------------------------------------------------------------------
    def _ensure_intent(self, state: MatchState, agent: PlayerAgentState) -> MovementIntent:
        current = self._intents.get(agent.agent_id)
        if current is not None and not current.is_expired(state.clock.tick_count):
            if self._intent_still_valid(state, agent, current):
                return current

        candidate = self._choose_intent(state, agent)
        target = self._target_for_type(state, agent, candidate.intent_type)
        duration = self._intent_duration_seconds(agent, candidate.intent_type)
        expires = state.clock.tick_count + max(1, round(duration / state.clock.tick_seconds))
        intent = MovementIntent(
            agent_id=agent.agent_id,
            intent_type=candidate.intent_type,
            target=target,
            started_tick=state.clock.tick_count,
            expires_tick=expires,
            priority=candidate.score,
            reason=candidate.reason,
        )
        self._intents[agent.agent_id] = intent
        return intent

    def _intent_still_valid(
        self,
        state: MatchState,
        agent: PlayerAgentState,
        intent: MovementIntent,
    ) -> bool:
        in_possession = state.possession.team_side is agent.side
        if in_possession and intent.intent_type in self._DEFENDING_INTENTS:
            return False
        if not in_possession and intent.intent_type in self._ATTACKING_INTENTS:
            return False

        # Do not let a committed run become a player camping 30 metres beyond
        # the ball.  Once the runner is clearly disconnected, re-evaluate early.
        if in_possession and intent.intent_type in self._COMMITTED_RUNS:
            current = self._to_local(state, agent.side, agent.location)
            ball = self._to_local(state, agent.side, state.ball.location)
            if current.x - ball.x > self.config.max_attacking_lead_m + 3.0:
                return False

        if intent.intent_type is MovementIntentType.TRACK_RUNNER:
            runner = self._nearest_dangerous_opponent(state, agent)
            if runner is None or runner.location.distance_to(agent.location) > 20.0:
                return False
        return True

    def _intent_duration_seconds(
        self,
        agent: PlayerAgentState,
        intent_type: MovementIntentType,
    ) -> float:
        mental = agent.player.attributes.mental
        instructions = agent.player.effective_instructions
        roaming = float(instructions.roaming) if instructions is not None else 50.0
        intelligence = (
            mental.tactical_intelligence + mental.decisions + mental.anticipation
        ) / 300.0
        stable = (sum(ord(char) for char in agent.agent_id) % 19) / 18.0
        duration = (
            self.config.min_intent_seconds
            + (self.config.max_intent_seconds - self.config.min_intent_seconds)
            * (0.24 + intelligence * 0.34 + stable * 0.16 + (100.0 - roaming) / 100.0 * 0.16)
        )
        if intent_type in self._COMMITTED_RUNS:
            duration += 1.0
        elif intent_type in {MovementIntentType.OFFER_LANE, MovementIntentType.SUPPORT_BALL}:
            duration -= 0.5
        return _clamp(duration, self.config.min_intent_seconds, self.config.max_intent_seconds + 1.0)

    def _choose_intent(self, state: MatchState, agent: PlayerAgentState) -> _IntentCandidate:
        candidates = (
            self._attacking_candidates(state, agent)
            if state.possession.team_side is agent.side
            else self._defending_candidates(state, agent)
        )
        if not candidates:
            return _IntentCandidate(
                MovementIntentType.HOLD_STRUCTURE,
                50.0,
                "fallback structure reference",
            )
        return self._weighted_candidate(state, agent, candidates)

    def _weighted_candidate(
        self,
        state: MatchState,
        agent: PlayerAgentState,
        candidates: list[_IntentCandidate],
    ) -> _IntentCandidate:
        # Keep only plausible alternatives.  This gives natural variety without
        # allowing a nonsensical low-score action to win by pure randomness.
        best = max(item.score for item in candidates)
        viable = [item for item in candidates if item.score >= best - 24.0]
        viable.sort(key=lambda item: (-item.score, item.intent_type.value, item.reason))

        serial = self._intent_serial.get(agent.agent_id, 0) + 1
        self._intent_serial[agent.agent_id] = serial
        roll = self._stable_roll(
            f"{self.snapshot.seed}|{self._possession_epoch}|{agent.agent_id}|{serial}|{state.clock.tick_count}"
        )
        weights = [max(1.0, item.score - (best - 28.0)) ** 1.35 for item in viable]
        total = sum(weights)
        needle = roll * total
        cumulative = 0.0
        for item, weight in zip(viable, weights, strict=True):
            cumulative += weight
            if needle <= cumulative:
                return item
        return viable[-1]

    @staticmethod
    def _stable_roll(payload: str) -> float:
        digest = blake2b(payload.encode("utf-8"), digest_size=8).digest()
        value = int.from_bytes(digest, "big")
        return value / float(2**64)

    # ------------------------------------------------------------------
    # Candidate scoring
    # ------------------------------------------------------------------
    def _attacking_candidates(
        self,
        state: MatchState,
        agent: PlayerAgentState,
    ) -> list[_IntentCandidate]:
        position = agent.assigned_position
        instructions = agent.player.effective_instructions
        forward_runs = float(instructions.forward_runs) if instructions is not None else 50.0
        attack_space = float(instructions.attack_space) if instructions is not None else 50.0
        hold_up = float(instructions.hold_up_play) if instructions is not None else 50.0
        roaming = float(instructions.roaming) if instructions is not None else 50.0
        position_cmd = (
            instructions.in_possession_position
            if instructions is not None
            else InPossessionPosition.BASE
        )
        team = self._runtime_tactics[agent.side].team_instructions.in_possession
        ball = self._to_local(state, agent.side, state.ball.location)
        current = self._to_local(state, agent.side, agent.location)
        progress = ball.x / state.pitch.length_m
        ahead = current.x - ball.x
        same_flank = self._same_flank(ball.y, current.y, state.pitch.width_m)
        far_ahead_penalty = max(0.0, ahead - 18.0) * 2.4
        owner = self._owner(state)
        owner_is_wide = owner is not None and owner.assigned_position in {
            Position.RB,
            Position.LB,
            Position.RWB,
            Position.LWB,
            Position.RW,
            Position.LW,
        }

        if position is Position.GK:
            return [_IntentCandidate(MovementIntentType.HOLD_STRUCTURE, 90.0, "goalkeeper supports behind play")]

        if position in {Position.RCB, Position.CB, Position.LCB}:
            step_score = 38.0 + max(0.0, 0.58 - progress) * 32.0
            if agent.player.role_id in {"ball_playing_defender", "wide_center_back"}:
                step_score += 14.0
            if self._space_ahead(state, agent, 10.0) > 0.62:
                step_score += 10.0
            return [
                _IntentCandidate(MovementIntentType.SUPPORT_BALL, 72.0, "back line follows possession from behind"),
                _IntentCandidate(MovementIntentType.STEP_INTO_SPACE, step_score, "centre-back can step into free build-up space"),
            ]

        if position in {Position.RB, Position.LB, Position.RWB, Position.LWB}:
            winger = self._wide_teammate(state, agent)
            winger_inside = self._teammate_is_inside(winger)
            opposite_fullback_attacking = self._opposite_fullback_is_attacking(state, agent)
            ball_side_bonus = 12.0 if same_flank else -8.0
            if owner_is_wide and owner is not None and owner.side is agent.side:
                owner_local = self._to_local(state, agent.side, owner.location)
                if self._same_flank(ball.y, owner_local.y, state.pitch.width_m) == same_flank:
                    ball_side_bonus += 6.0
            overlap = (
                36.0
                + float(team.overlap_frequency) * 0.30
                + forward_runs * 0.22
                + ball_side_bonus
                + (18.0 if winger_inside else 0.0)
                - (14.0 if opposite_fullback_attacking else 0.0)
                - far_ahead_penalty
            )
            underlap = (
                31.0
                + float(team.overlap_frequency) * 0.23
                + forward_runs * 0.18
                + ball_side_bonus
                + (10.0 if not winger_inside else -3.0)
                - (10.0 if opposite_fullback_attacking else 0.0)
                - far_ahead_penalty
            )
            offer = 55.0 + progress * 18.0 + max(0.0, 55.0 - forward_runs) * 0.10
            support = (
                60.0
                + (10.0 if not same_flank else 0.0)
                + max(0.0, ahead - 20.0)
                + (15.0 if opposite_fullback_attacking else 0.0)
            )
            candidates = [
                _IntentCandidate(MovementIntentType.SUPPORT_BALL, support, "full-back gives rest-defence/support"),
                _IntentCandidate(MovementIntentType.OFFER_LANE, offer, "full-back advances into a supporting lane"),
                _IntentCandidate(MovementIntentType.OVERLAP, overlap, "full-back attacks outside the winger"),
                _IntentCandidate(MovementIntentType.UNDERLAP, underlap, "full-back attacks the inside channel"),
            ]
            if position_cmd is InPossessionPosition.MIDFIELD:
                candidates.append(_IntentCandidate(MovementIntentType.INVERT, 98.0, "instruction asks full-back to invert"))
            elif position_cmd is InPossessionPosition.WIDE:
                candidates.append(_IntentCandidate(MovementIntentType.OVERLAP, 94.0, "instruction keeps full-back wide and advancing"))
            return candidates

        if position is Position.DM:
            build_score = 38.0 + float(team.build_from_back) * 0.42 + max(0.0, 0.42 - progress) * 70.0
            if position_cmd is InPossessionPosition.DROP_DEEP:
                build_score = 100.0
            return [
                _IntentCandidate(MovementIntentType.DROP_BETWEEN_CBS, build_score, "pivot drops into the first build-up line"),
                _IntentCandidate(MovementIntentType.SUPPORT_BALL, 76.0 + progress * 10.0, "pivot balances behind the ball"),
                _IntentCandidate(MovementIntentType.OFFER_LANE, 61.0 + roaming * 0.10, "pivot changes the passing angle"),
            ]

        if position in {Position.RCM, Position.CM, Position.LCM}:
            other_runner = self._another_midfielder_is_running(state, agent)
            pivot_dropping = self._pivot_is_dropping(state, agent.side)
            striker_dropping = self._striker_is_dropping(state, agent.side)
            run_score = (
                38.0
                + forward_runs * 0.36
                + attack_space * 0.20
                + roaming * 0.12
                + progress * 22.0
                - far_ahead_penalty
                - (18.0 if other_runner else 0.0)
                + (9.0 if pivot_dropping and position is not Position.CM else 0.0)
                + (7.0 if striker_dropping else 0.0)
            )
            box_score = (
                24.0
                + forward_runs * 0.30
                + attack_space * 0.22
                + max(0.0, progress - 0.47) * 80.0
                - far_ahead_penalty
                - (15.0 if other_runner else 0.0)
                + (8.0 if pivot_dropping and position is not Position.CM else 0.0)
            )
            offer_score = 68.0 + (12.0 if abs(current.y - ball.y) <= 14.0 else 3.0)
            support_score = 64.0 + (12.0 if other_runner else 0.0) + max(0.0, ahead - 16.0) * 1.7
            candidates = [
                _IntentCandidate(MovementIntentType.SUPPORT_BALL, support_score, "interior balances the possession"),
                _IntentCandidate(MovementIntentType.OFFER_LANE, offer_score, "interior creates a passing angle"),
                _IntentCandidate(MovementIntentType.RUN_IN_BEHIND, run_score, "interior attacks space beyond the ball"),
                _IntentCandidate(MovementIntentType.ATTACK_BOX, box_score, "interior joins the final line"),
            ]
            # In a three-man midfield the central CM often behaves as the pivot
            # even when the formation data calls the slot "CM" rather than "DM".
            # Build-up instructions can therefore make that player drop into the
            # first line while the two interiors advance around them.
            if position is Position.CM:
                pivot_score = (
                    30.0
                    + float(team.build_from_back) * 0.34
                    + max(0.0, 0.46 - progress) * 72.0
                    + max(0.0, 55.0 - forward_runs) * 0.10
                )
                if position_cmd is InPossessionPosition.DROP_DEEP:
                    pivot_score += 32.0
                candidates.append(
                    _IntentCandidate(
                        MovementIntentType.DROP_BETWEEN_CBS,
                        pivot_score,
                        "central midfielder drops between centre-backs to build",
                    )
                )
            return candidates

        if position is Position.AM:
            return [
                _IntentCandidate(MovementIntentType.OFFER_LANE, 76.0 + max(0.0, 0.55 - progress) * 20.0, "attacking midfielder finds space between lines"),
                _IntentCandidate(MovementIntentType.RUN_IN_BEHIND, 47.0 + forward_runs * 0.33 + attack_space * 0.18 - far_ahead_penalty, "attacking midfielder attacks depth"),
                _IntentCandidate(MovementIntentType.ATTACK_BOX, 38.0 + max(0.0, progress - 0.48) * 100.0 + forward_runs * 0.20 - far_ahead_penalty, "attacking midfielder attacks the box"),
                _IntentCandidate(MovementIntentType.DROP_TO_RECEIVE, 48.0 + hold_up * 0.20 + max(0.0, ahead - 18.0) * 2.2, "attacking midfielder checks toward the ball"),
            ]

        if position in {Position.RW, Position.LW}:
            fullback = self._same_flank_fullback(state, agent)
            fullback_overlap = self._intent_is(fullback, {MovementIntentType.OVERLAP, MovementIntentType.UNDERLAP})
            striker_dropping = self._striker_is_dropping(state, agent.side)
            far_side = not same_flank
            drop_score = 34.0 + max(0.0, ahead - 18.0) * 2.9 + max(0.0, 0.44 - progress) * 35.0
            run_score = (
                42.0
                + forward_runs * 0.32
                + attack_space * 0.24
                + (8.0 if same_flank else -4.0)
                + (11.0 if striker_dropping else 0.0)
                - far_ahead_penalty
            )
            wide_score = 58.0 + (10.0 if not fullback_overlap else -8.0) + (6.0 if far_side else 0.0)
            inside_score = 46.0 + roaming * 0.16 + (18.0 if fullback_overlap else 0.0)
            box_score = 20.0 + max(0.0, progress - 0.62) * 120.0 + (18.0 if far_side else 0.0) - far_ahead_penalty
            if position_cmd in {InPossessionPosition.INSIDE, InPossessionPosition.MIDFIELD}:
                inside_score += 45.0
            elif position_cmd is InPossessionPosition.WIDE:
                # A positional instruction is a bias, not a rail.  Even a winger
                # asked to hold width can come inside when the full-back overlaps
                # or the local space invites it.
                wide_score += 16.0
            elif position_cmd is InPossessionPosition.DROP_DEEP:
                drop_score += 28.0
            return [
                _IntentCandidate(MovementIntentType.STAY_WIDE, wide_score, "winger preserves width"),
                _IntentCandidate(MovementIntentType.MOVE_INSIDE, inside_score, "winger moves into the half-space"),
                _IntentCandidate(MovementIntentType.RUN_IN_BEHIND, run_score, "winger attacks depth"),
                _IntentCandidate(MovementIntentType.DROP_TO_RECEIVE, drop_score, "winger checks back toward the ball"),
                _IntentCandidate(MovementIntentType.ATTACK_BOX, box_score, "far winger attacks the box"),
            ]

        if position in {Position.ST, Position.SS}:
            wide_runner_count = self._wide_runner_count(state, agent.side)
            drop_score = 44.0 + hold_up * 0.27 + max(0.0, ahead - 16.0) * 3.0 + max(0.0, 0.42 - progress) * 38.0
            run_score = 45.0 + forward_runs * 0.33 + attack_space * 0.25 - far_ahead_penalty
            box_score = 32.0 + max(0.0, progress - 0.54) * 115.0 + attack_space * 0.15 - far_ahead_penalty
            offer_score = 45.0 + hold_up * 0.18 + max(0.0, 0.50 - progress) * 22.0
            if wide_runner_count >= 1:
                drop_score += 7.0
                offer_score += 5.0
            if wide_runner_count >= 2:
                drop_score += 7.0
            if position_cmd is InPossessionPosition.DROP_DEEP:
                drop_score += 32.0
            elif position_cmd is InPossessionPosition.ADVANCE:
                # Advanced forwards threaten depth most often, but they are not
                # nailed to the last line for 90 minutes.
                run_score += 18.0
            return [
                _IntentCandidate(MovementIntentType.DROP_TO_RECEIVE, drop_score, "forward drops to connect play"),
                _IntentCandidate(MovementIntentType.RUN_IN_BEHIND, run_score, "forward threatens the space behind"),
                _IntentCandidate(MovementIntentType.ATTACK_BOX, box_score, "forward attacks the scoring zone"),
                _IntentCandidate(MovementIntentType.OFFER_LANE, offer_score, "forward offers a central wall pass"),
            ]

        return [_IntentCandidate(MovementIntentType.HOLD_STRUCTURE, 60.0, "formation reference")]

    def _defending_candidates(
        self,
        state: MatchState,
        agent: PlayerAgentState,
    ) -> list[_IntentCandidate]:
        position = agent.assigned_position
        ball = self._to_local(state, agent.side, state.ball.location)
        current = self._to_local(state, agent.side, agent.location)
        runner = self._nearest_dangerous_opponent(state, agent)
        track_score = 0.0
        if runner is not None:
            runner_local = self._to_local(state, agent.side, runner.location)
            distance = agent.location.distance_to(runner.location)
            behind_line = max(0.0, current.x - runner_local.x)
            run_intent = self._intent_is(
                runner,
                {MovementIntentType.RUN_IN_BEHIND, MovementIntentType.ATTACK_BOX},
            )
            primary_tracker = self._is_primary_tracker(state, agent, runner)
            # Tracking is a local defensive responsibility, not permission to
            # chase an opponent across the whole pitch.  Only the one/two most
            # plausible nearby defenders receive a strong tracking score.
            if primary_tracker and distance <= (20.0 if run_intent else 16.0):
                track_score = (
                    73.0
                    - distance * 1.65
                    + min(behind_line, 10.0) * 1.15
                    + (15.0 if run_intent else 0.0)
                )
            else:
                track_score = 18.0 - distance * 0.7

        if position is Position.GK:
            return [_IntentCandidate(MovementIntentType.HOLD_STRUCTURE, 95.0, "goalkeeper protects goal reference")]

        if position in {Position.RB, Position.LB, Position.RWB, Position.LWB, Position.RCB, Position.CB, Position.LCB}:
            return [
                _IntentCandidate(MovementIntentType.TRACK_RUNNER, track_score, "defender follows a dangerous runner"),
                _IntentCandidate(MovementIntentType.COVER_SPACE, 76.0 + max(0.0, 0.45 - ball.x / state.pitch.length_m) * 20.0, "defender protects space behind pressure"),
                _IntentCandidate(MovementIntentType.RECOVER_SHAPE, 66.0, "defender reconnects with the line"),
            ]

        if position in {Position.DM, Position.RCM, Position.CM, Position.LCM, Position.AM}:
            ball_side = abs(current.y - ball.y) < state.pitch.width_m * 0.30
            return [
                _IntentCandidate(MovementIntentType.COVER_SPACE, 78.0 if ball_side else 66.0, "midfielder compresses the active zone"),
                _IntentCandidate(MovementIntentType.TRACK_RUNNER, track_score - 5.0, "midfielder follows a runner through midfield"),
                _IntentCandidate(MovementIntentType.RECOVER_SHAPE, 71.0 if not ball_side else 61.0, "midfielder protects central access"),
            ]

        # Forwards screen and recover instead of remaining parked on a starting row.
        return [
            _IntentCandidate(MovementIntentType.COVER_SPACE, 66.0 if ball.x > 48.0 else 57.0, "forward screens central progression"),
            _IntentCandidate(MovementIntentType.RECOVER_SHAPE, 69.0 if ball.x < 58.0 else 58.0, "forward drops with the block"),
        ]

    # ------------------------------------------------------------------
    # Dynamic targets
    # ------------------------------------------------------------------
    def _dynamic_target(
        self,
        state: MatchState,
        agent: PlayerAgentState,
        intent: MovementIntent,
    ) -> Vector2:
        # Runs in behind and committed box attacks keep their originally chosen
        # channel for a few seconds.  Support/cover behaviours are live relative
        # to the ball and therefore continuously breathe with the possession.
        static_types = {
            MovementIntentType.RUN_IN_BEHIND,
            MovementIntentType.DROP_TO_RECEIVE,
        }
        if intent.intent_type in static_types:
            return intent.target
        return self._target_for_type(state, agent, intent.intent_type)

    def _target_for_type(
        self,
        state: MatchState,
        agent: PlayerAgentState,
        intent_type: MovementIntentType,
    ) -> Vector2:
        pitch = state.pitch
        structure = self._structure_reference(state, agent)
        current = self._to_local(state, agent.side, agent.location)
        ball = self._to_local(state, agent.side, state.ball.location)
        centre_y = pitch.width_m / 2.0
        position = agent.assigned_position
        instructions = agent.player.effective_instructions
        forward_runs = float(instructions.forward_runs) if instructions is not None else 50.0
        attack_space = float(instructions.attack_space) if instructions is not None else 50.0
        local = structure

        if intent_type is MovementIntentType.HOLD_STRUCTURE:
            local = structure

        elif intent_type is MovementIntentType.SUPPORT_BALL:
            depth = 9.0
            if position in {Position.RCB, Position.CB, Position.LCB}:
                depth = 25.0
            elif position in {Position.RB, Position.LB, Position.RWB, Position.LWB}:
                depth = 17.0
            elif position is Position.DM:
                depth = 13.0
            elif position in {Position.RCM, Position.CM, Position.LCM}:
                depth = 6.5
            desired_x = ball.x - depth
            x = _lerp(structure.x, desired_x, 0.58)
            y = _lerp(structure.y, ball.y, 0.22)
            # When a pivot drops between centre-backs, the centre-backs naturally
            # fan out instead of occupying the exact same lane.
            if position in {Position.RCB, Position.LCB, Position.CB} and self._pivot_is_dropping(state, agent.side):
                if position in {Position.LCB}:
                    y -= 5.0
                elif position in {Position.RCB}:
                    y += 5.0
            local = Vector2(x, y)

        elif intent_type is MovementIntentType.OFFER_LANE:
            side_sign = -1.0 if current.y <= ball.y else 1.0
            if abs(current.y - ball.y) < 4.0:
                side_sign = -1.0 if self._stable_roll(agent.agent_id) < 0.5 else 1.0
            forward_offset = 4.0
            lateral_offset = 8.0
            if position in {Position.RB, Position.LB, Position.RWB, Position.LWB, Position.RW, Position.LW}:
                forward_offset = 7.0
                lateral_offset = 10.0
            x = _lerp(structure.x, ball.x + forward_offset, 0.64)
            y = _lerp(structure.y, ball.y + side_sign * lateral_offset, 0.68)
            local = Vector2(x, y)

        elif intent_type is MovementIntentType.DROP_TO_RECEIVE:
            target_x = min(current.x - 8.0, ball.x + 10.0)
            target_x = max(target_x, ball.x + 3.0)
            x = _lerp(structure.x, target_x, 0.78)
            y = _lerp(structure.y, centre_y, 0.34)
            local = Vector2(x, y)

        elif intent_type is MovementIntentType.RUN_IN_BEHIND:
            run_distance = 16.0 + forward_runs / 100.0 * 8.0 + attack_space / 100.0 * 5.0
            x = max(structure.x + 8.0, ball.x + run_distance)
            x = min(x, pitch.length_m - 4.0)
            y = self._best_run_lane_y(state, agent, x)
            local = Vector2(x, y)

        elif intent_type is MovementIntentType.ATTACK_BOX:
            x = _clamp(max(ball.x + 9.0, pitch.length_m - 22.0), pitch.length_m - 26.0, pitch.length_m - 5.0)
            lane = self._box_lane_index(agent)
            if lane == 0:
                y = centre_y
            elif lane == 1:
                y = centre_y - 8.0
            else:
                y = centre_y + 8.0
            # Far-side players attack the back-post lane rather than stacking on
            # the striker's exact coordinate.
            if position in {Position.LW, Position.LCM} and ball.y > centre_y:
                y = centre_y - 10.0
            elif position in {Position.RW, Position.RCM} and ball.y < centre_y:
                y = centre_y + 10.0
            local = Vector2(x, y)

        elif intent_type is MovementIntentType.STAY_WIDE:
            is_left = structure.y < centre_y
            y = self.config.touchline_margin_m + 1.0 if is_left else pitch.width_m - self.config.touchline_margin_m - 1.0
            x = _lerp(structure.x, min(ball.x + 8.0, pitch.length_m - 6.0), 0.55)
            local = Vector2(x, y)

        elif intent_type is MovementIntentType.MOVE_INSIDE:
            is_left = structure.y < centre_y
            halfspace_y = centre_y - 8.0 if is_left else centre_y + 8.0
            x = _lerp(structure.x, min(ball.x + 9.0, pitch.length_m - 6.0), 0.68)
            local = Vector2(x, halfspace_y)

        elif intent_type is MovementIntentType.OVERLAP:
            is_left = structure.y < centre_y
            y = self.config.touchline_margin_m + 1.0 if is_left else pitch.width_m - self.config.touchline_margin_m - 1.0
            x = max(structure.x + 8.0, ball.x + 12.0)
            local = Vector2(min(x, pitch.length_m - 4.0), y)

        elif intent_type is MovementIntentType.UNDERLAP:
            is_left = structure.y < centre_y
            y = centre_y - 10.0 if is_left else centre_y + 10.0
            x = max(structure.x + 7.0, ball.x + 10.0)
            local = Vector2(min(x, pitch.length_m - 5.0), y)

        elif intent_type is MovementIntentType.INVERT:
            is_left = structure.y < centre_y
            y = centre_y - 7.0 if is_left else centre_y + 7.0
            x = _lerp(structure.x, ball.x - 7.0, 0.70)
            local = Vector2(_clamp(x, 28.0, 78.0), y)

        elif intent_type is MovementIntentType.DROP_BETWEEN_CBS:
            cb_line_x = _clamp(ball.x - 24.0, 18.0, 50.0)
            local = Vector2(cb_line_x, centre_y)

        elif intent_type is MovementIntentType.STEP_INTO_SPACE:
            x = max(structure.x + 7.0, min(ball.x - 7.0, 62.0))
            y = _lerp(structure.y, ball.y, 0.26)
            local = Vector2(x, y)

        elif intent_type is MovementIntentType.COVER_SPACE:
            # The structural reference already squeezes with the ball.  Coverage
            # adds stronger lateral ball-orientation without pinning to a lane.
            x = _lerp(structure.x, max(10.0, ball.x - 8.0), 0.22)
            y = _lerp(structure.y, ball.y, 0.38)
            local = Vector2(x, y)

        elif intent_type is MovementIntentType.TRACK_RUNNER:
            runner = self._nearest_dangerous_opponent(state, agent)
            if runner is None:
                local = structure
            else:
                opp = self._to_local(state, agent.side, runner.location)
                # Stay goal-side of the runner, but keep the tracking movement
                # connected to the team's defensive reference.  This prevents a
                # centre-back from following a winger 50 metres into a different
                # line while still allowing genuine diagonal tracking.
                if position in {Position.RB, Position.LB, Position.RWB, Position.LWB}:
                    x_back, x_front, y_span = 12.0, 12.0, 22.0
                elif position in {Position.RCB, Position.CB, Position.LCB}:
                    x_back, x_front, y_span = 11.0, 9.0, 18.0
                else:
                    x_back, x_front, y_span = 14.0, 14.0, 20.0
                goal_side_x = opp.x - 1.8
                x = _clamp(goal_side_x, structure.x - x_back, structure.x + x_front)
                y = _clamp(opp.y, structure.y - y_span, structure.y + y_span)
                local = Vector2(max(2.0, x), y)

        elif intent_type is MovementIntentType.RECOVER_SHAPE:
            local = structure

        return self._from_local(state, agent.side, local)

    def _structure_reference(self, state: MatchState, agent: PlayerAgentState) -> Vector2:
        """Ball-relative collective reference, intentionally softer than a target.

        This is the antidote to both failure modes seen in the first viewers:
        eleven isolated formation dots and eleven rigidly translated dots.  The
        reference tells a player roughly where the team currently lives; the
        intention can then move them far away from it for a football reason.
        """

        base_global = agent.tactical_target or agent.location
        base = self._to_local(state, agent.side, base_global)
        ball = self._to_local(state, agent.side, state.ball.location)
        pitch = state.pitch
        position = agent.assigned_position
        in_possession = state.possession.team_side is agent.side

        if in_possession:
            if position is Position.GK:
                dynamic_x = _clamp(ball.x - 46.0, 4.5, 18.0)
                weight = 0.45
            elif position in {Position.RCB, Position.CB, Position.LCB}:
                dynamic_x = _clamp(ball.x - 27.0, 20.0, 62.0)
                weight = 0.68
            elif position in {Position.RB, Position.LB, Position.RWB, Position.LWB}:
                dynamic_x = _clamp(ball.x - 18.0, 24.0, 76.0)
                weight = 0.62
            elif position is Position.DM:
                dynamic_x = _clamp(ball.x - 13.0, 27.0, 78.0)
                weight = 0.68
            elif position in {Position.RCM, Position.CM, Position.LCM}:
                dynamic_x = _clamp(ball.x - 4.0, 32.0, 85.0)
                weight = 0.68
            elif position is Position.AM:
                dynamic_x = _clamp(ball.x + 5.0, 40.0, 91.0)
                weight = 0.70
            else:
                dynamic_x = _clamp(ball.x + 11.0, 46.0, 95.0)
                weight = 0.66
            x = _lerp(base.x, dynamic_x, weight)
            lateral_weight = 0.10 if position in {Position.RCB, Position.CB, Position.LCB} else 0.16
            y = _lerp(base.y, ball.y, lateral_weight)
        else:
            out = self._runtime_tactics[agent.side].team_instructions.out_of_possession
            if position is Position.GK:
                dynamic_x = 5.5
                weight = 0.35
            elif position in {Position.RB, Position.LB, Position.RWB, Position.LWB, Position.RCB, Position.CB, Position.LCB}:
                dynamic_x = _clamp(ball.x - 16.0, 12.0, 59.0)
                weight = 0.74
            elif position in {Position.DM, Position.RCM, Position.CM, Position.LCM, Position.AM}:
                dynamic_x = _clamp(ball.x + 1.0, 24.0, 70.0)
                weight = 0.72
            else:
                dynamic_x = _clamp(ball.x + 17.0, 38.0, 84.0)
                weight = 0.68
            x = _lerp(base.x, dynamic_x, weight)
            compactness = float(out.horizontal_compactness) / 100.0
            centre_y = pitch.width_m / 2.0
            base_compact = _lerp(base.y, centre_y, compactness * 0.20)
            y = _lerp(base_compact, ball.y, 0.20 + compactness * 0.12)

        return Vector2(x, y)

    # ------------------------------------------------------------------
    # Spatial helpers / coordinated relationships
    # ------------------------------------------------------------------
    def _apply_cohesion_envelope(
        self,
        state: MatchState,
        agent: PlayerAgentState,
        intent_type: MovementIntentType,
        target: Vector2,
    ) -> Vector2:
        if state.possession.team_side is not agent.side:
            return target
        local_target = self._to_local(state, agent.side, target)
        local_ball = self._to_local(state, agent.side, state.ball.location)

        if intent_type in self._COMMITTED_RUNS:
            max_x = local_ball.x + self.config.max_attacking_lead_m
            # Time runs from an onside starting position.  Once a pass is played,
            # the passing layer can lead the receiver beyond the line while the
            # ball is in flight; before the release we do not let a striker camp
            # ten metres behind the defence waiting for a decision tick.
            max_x = min(max_x, self._onside_limit_x(state, agent.side))
        else:
            max_x = local_ball.x + self.config.max_support_lead_m
        min_x = local_ball.x - self.config.max_support_trail_m

        if agent.assigned_position is Position.GK:
            min_x = 2.0
            max_x = min(max_x, 22.0)
        local_target = Vector2(_clamp(local_target.x, min_x, max_x), local_target.y)
        return self._from_local(state, agent.side, local_target)


    def _onside_limit_x(self, state: MatchState, attacking_side: TeamSide) -> float:
        """Return the furthest sensible onside x in the attacker's local frame."""

        pitch = state.pitch
        ball = self._to_local(state, attacking_side, state.ball.location)
        opponent_x = sorted(
            (
                self._to_local(state, attacking_side, opponent.location).x
                for opponent in state.active_players
                if opponent.side is not attacking_side
            ),
            reverse=True,
        )
        if len(opponent_x) >= 2:
            second_last = opponent_x[1]
        elif opponent_x:
            second_last = opponent_x[0]
        else:
            return pitch.length_m - self.config.touchline_margin_m

        # A player cannot be offside in their own half.  In the opposition half
        # they stay behind whichever is further forward: ball or second-last
        # opponent.  A small buffer avoids visual line-sharing/flicker.
        legal_line = max(pitch.length_m / 2.0, ball.x, second_last)
        return _clamp(
            legal_line - self.config.offside_buffer_m,
            pitch.length_m / 2.0 - self.config.offside_buffer_m,
            pitch.length_m - self.config.touchline_margin_m,
        )

    def _apply_spacing(
        self,
        state: MatchState,
        agent: PlayerAgentState,
        target: Vector2,
    ) -> Vector2:
        if self.config.teammate_spacing_m <= 0.0:
            return target
        push = Vector2.zero()
        for teammate in state.active_players:
            if teammate.side is not agent.side or teammate.agent_id == agent.agent_id:
                continue
            reference_points = [teammate.location]
            # Teammates should not independently choose the exact same future
            # pocket.  Using the previous tick's live target as a soft repulsor
            # creates natural staggering without assigning rigid lanes.
            if teammate.movement_target is not None:
                reference_points.append(teammate.movement_target)
            for reference in reference_points:
                distance = target.distance_to(reference)
                if distance <= 0.001 or distance >= self.config.teammate_spacing_m:
                    continue
                away = target - reference
                strength = (self.config.teammate_spacing_m - distance) / self.config.teammate_spacing_m
                push = push + away.normalized().scale(1.7 * strength)
        if push.magnitude > 2.4:
            push = push.normalized().scale(2.4)
        return target + push

    def _best_run_lane_y(self, state: MatchState, agent: PlayerAgentState, target_x_local: float) -> float:
        pitch = state.pitch
        current = self._to_local(state, agent.side, agent.location)
        structure = self._structure_reference(state, agent)
        centre = pitch.width_m / 2.0
        candidate_ys = {
            _clamp(current.y, 4.0, pitch.width_m - 4.0),
            _clamp(structure.y, 4.0, pitch.width_m - 4.0),
            centre - 9.0,
            centre + 9.0,
            centre - 17.0,
            centre + 17.0,
        }
        best: tuple[float, float] | None = None
        for y in candidate_ys:
            local_target = Vector2(target_x_local, y)
            global_target = self._from_local(state, agent.side, local_target)
            nearest_opponent = min(
                (
                    global_target.distance_to(opponent.location)
                    for opponent in state.active_players
                    if opponent.side is not agent.side
                ),
                default=12.0,
            )
            teammate_congestion = sum(
                1
                for teammate in state.active_players
                if teammate.side is agent.side
                and teammate.agent_id != agent.agent_id
                and global_target.distance_to(teammate.location) < 7.0
            )
            travel = abs(y - current.y)
            score = nearest_opponent * 1.2 - teammate_congestion * 5.0 - travel * 0.08
            candidate = (score, y)
            if best is None or candidate > best:
                best = candidate
        assert best is not None
        return best[1]

    def _space_ahead(self, state: MatchState, agent: PlayerAgentState, metres: float) -> float:
        target = state.pitch.clamp(
            agent.location + Vector2(agent.side.attack_sign * metres, 0.0)
        )
        nearest = min(
            (
                target.distance_to(opponent.location)
                for opponent in state.active_players
                if opponent.side is not agent.side
            ),
            default=12.0,
        )
        return _clamp(nearest / 10.0, 0.0, 1.0)

    def _clamp_playable(self, state: MatchState, target: Vector2) -> Vector2:
        margin = self.config.touchline_margin_m
        return Vector2(
            _clamp(target.x, margin, state.pitch.length_m - margin),
            _clamp(target.y, margin, state.pitch.width_m - margin),
        )

    def _speed(self, agent: PlayerAgentState, intent: MovementIntent) -> float:
        physical = agent.player.attributes.physical
        mental = agent.player.attributes.mental
        physical_factor = 0.78 + ((physical.pace + physical.acceleration) / 200.0) * 0.43
        work_factor = 0.88 + mental.work_rate / 100.0 * 0.20
        familiarity_factor = self._familiarity_speed_factor(agent)
        intent_factor = 1.0
        if intent.intent_type in self._COMMITTED_RUNS or intent.intent_type is MovementIntentType.TRACK_RUNNER:
            intent_factor = 1.22
        elif intent.intent_type in {MovementIntentType.RECOVER_SHAPE, MovementIntentType.COVER_SPACE}:
            intent_factor = 1.08
        return (
            self.config.base_off_ball_speed_mps
            * physical_factor
            * work_factor
            * familiarity_factor
            * intent_factor
            * self.context.movement_speed_multiplier(agent)
        )

    def _speed_for_structure(self, agent: PlayerAgentState) -> float:
        return (
            self.config.base_off_ball_speed_mps
            * 0.88
            * self._familiarity_speed_factor(agent)
            * self.context.movement_speed_multiplier(agent)
        )

    @staticmethod
    def _familiarity_speed_factor(agent: PlayerAgentState) -> float:
        context = agent.player.role_context
        if context is None:
            return 1.0
        familiarity = (
            context.position_familiarity * 0.45
            + context.role_familiarity * 0.30
            + context.tactic_familiarity * 0.25
        ) / 100.0
        return 0.84 + familiarity * 0.20

    def _move_toward(
        self,
        agent: PlayerAgentState,
        target: Vector2,
        speed_mps: float,
        dt: float,
    ) -> None:
        """Steer toward a football target with acceleration and momentum.

        The first spatial prototypes replaced velocity with a full-speed vector
        every tick, which made otherwise correct runs look like chess pieces
        sliding on straight rails.  Off-ball players now accelerate, turn and
        brake over several fixed ticks.  Direct action systems may still
        override velocity when a duel/pass/carry requires it.
        """

        delta = target - agent.location
        distance = delta.magnitude
        if distance <= 0.001:
            desired = Vector2.zero()
        else:
            # Ease into the destination instead of snapping from sprint to stop.
            arrival_factor = _clamp(distance / 3.0, 0.0, 1.0)
            desired = delta.normalized().scale(speed_mps * arrival_factor)

        change = desired - agent.velocity
        if change.magnitude <= 0.001:
            return
        slowing = desired.magnitude < agent.velocity.magnitude
        max_change = (
            self.config.max_deceleration_mps2 if slowing else self.config.max_acceleration_mps2
        ) * dt
        if change.magnitude <= max_change:
            agent.velocity = desired
        else:
            agent.velocity = agent.velocity + change.normalized().scale(max_change)

        if distance <= self.config.arrival_radius_m and agent.velocity.magnitude < 0.35:
            agent.velocity = Vector2.zero()

    def _owner(self, state: MatchState) -> PlayerAgentState | None:
        if state.ball.owner_agent_id is None:
            return None
        owner = state.agent(state.ball.owner_agent_id)
        return owner if owner.is_active else None

    @staticmethod
    def _same_flank(ball_y: float, agent_y: float, width_m: float) -> bool:
        centre = width_m / 2.0
        return (ball_y < centre and agent_y < centre) or (ball_y >= centre and agent_y >= centre)

    def _wide_teammate(self, state: MatchState, fullback: PlayerAgentState) -> PlayerAgentState | None:
        wanted = Position.LW if fullback.assigned_position in {Position.LB, Position.LWB} else Position.RW
        for teammate in state.active_players:
            if teammate.side is fullback.side and teammate.assigned_position is wanted:
                return teammate
        return None

    def _same_flank_fullback(self, state: MatchState, winger: PlayerAgentState) -> PlayerAgentState | None:
        wanted = {Position.LB, Position.LWB} if winger.assigned_position is Position.LW else {Position.RB, Position.RWB}
        for teammate in state.active_players:
            if teammate.side is winger.side and teammate.assigned_position in wanted:
                return teammate
        return None

    def _teammate_is_inside(self, teammate: PlayerAgentState | None) -> bool:
        if teammate is None:
            return False
        instructions = teammate.player.effective_instructions
        if instructions is not None and instructions.in_possession_position in {
            InPossessionPosition.INSIDE,
            InPossessionPosition.MIDFIELD,
        }:
            return True
        return self._intent_is(teammate, {MovementIntentType.MOVE_INSIDE})

    def _intent_is(
        self,
        agent: PlayerAgentState | None,
        intent_types: set[MovementIntentType] | frozenset[MovementIntentType],
    ) -> bool:
        if agent is None:
            return False
        current = self._intents.get(agent.agent_id)
        return current is not None and current.intent_type in intent_types

    def _pivot_is_dropping(self, state: MatchState, side: TeamSide) -> bool:
        for intent in self._intents.values():
            if intent.intent_type is not MovementIntentType.DROP_BETWEEN_CBS:
                continue
            try:
                pivot = state.agent(intent.agent_id)
            except KeyError:
                continue
            if pivot.side is side and pivot.assigned_position in {Position.DM, Position.CM}:
                return True
        return False

    def _another_midfielder_is_running(self, state: MatchState, agent: PlayerAgentState) -> bool:
        midfield_positions = {Position.RCM, Position.CM, Position.LCM, Position.AM}
        for intent in self._intents.values():
            if intent.agent_id == agent.agent_id:
                continue
            try:
                teammate = state.agent(intent.agent_id)
            except KeyError:
                continue
            if teammate.side is not agent.side or teammate.assigned_position not in midfield_positions:
                continue
            if intent.intent_type in {MovementIntentType.RUN_IN_BEHIND, MovementIntentType.ATTACK_BOX}:
                return True
        return False

    def _opposite_fullback_is_attacking(
        self,
        state: MatchState,
        fullback: PlayerAgentState,
    ) -> bool:
        wanted = (
            {Position.RB, Position.RWB}
            if fullback.assigned_position in {Position.LB, Position.LWB}
            else {Position.LB, Position.LWB}
        )
        for teammate in state.active_players:
            if teammate.side is not fullback.side or teammate.assigned_position not in wanted:
                continue
            if self._intent_is(
                teammate,
                {MovementIntentType.OVERLAP, MovementIntentType.UNDERLAP},
            ):
                return True
        return False

    def _striker_is_dropping(self, state: MatchState, side: TeamSide) -> bool:
        for teammate in state.active_players:
            if teammate.side is not side or teammate.assigned_position not in {Position.ST, Position.SS}:
                continue
            if self._intent_is(
                teammate,
                {MovementIntentType.DROP_TO_RECEIVE, MovementIntentType.OFFER_LANE},
            ):
                return True
        return False

    def _wide_runner_count(self, state: MatchState, side: TeamSide) -> int:
        count = 0
        for teammate in state.active_players:
            if teammate.side is not side or teammate.assigned_position not in {Position.RW, Position.LW}:
                continue
            if self._intent_is(
                teammate,
                {MovementIntentType.RUN_IN_BEHIND, MovementIntentType.ATTACK_BOX},
            ):
                count += 1
        return count

    @staticmethod
    def _box_lane_index(agent: PlayerAgentState) -> int:
        return sum(ord(char) for char in agent.agent_id) % 3


    def _is_primary_tracker(
        self,
        state: MatchState,
        agent: PlayerAgentState,
        runner: PlayerAgentState,
    ) -> bool:
        eligible_positions = {
            Position.RB,
            Position.LB,
            Position.RWB,
            Position.LWB,
            Position.RCB,
            Position.CB,
            Position.LCB,
            Position.DM,
            Position.RCM,
            Position.CM,
            Position.LCM,
            Position.AM,
        }
        candidates = [
            teammate
            for teammate in state.active_players
            if teammate.side is agent.side
            and teammate.assigned_position in eligible_positions
        ]
        candidates.sort(
            key=lambda teammate: (
                teammate.location.distance_to(runner.location),
                teammate.agent_id,
            )
        )
        # A runner can be handed over between two nearby players, but should not
        # drag half the team into the same lane.
        return agent.agent_id in {item.agent_id for item in candidates[:2]}

    def _nearest_dangerous_opponent(
        self,
        state: MatchState,
        agent: PlayerAgentState,
    ) -> PlayerAgentState | None:
        candidates: list[tuple[float, str, PlayerAgentState]] = []
        agent_local = self._to_local(state, agent.side, agent.location)
        for opponent in state.active_players:
            if opponent.side is agent.side or opponent.assigned_position is Position.GK:
                continue
            opp_local = self._to_local(state, agent.side, opponent.location)
            goal_threat = max(0.0, agent_local.x - opp_local.x)
            distance = agent.location.distance_to(opponent.location)
            current = self._intents.get(opponent.agent_id)
            run_bonus = 5.0 if current is not None and current.intent_type in {
                MovementIntentType.RUN_IN_BEHIND,
                MovementIntentType.ATTACK_BOX,
            } else 0.0
            score = distance - goal_threat * 0.24 - run_bonus
            candidates.append((score, opponent.agent_id, opponent))
        if not candidates:
            return None
        candidates.sort(key=lambda item: (item[0], item[1]))
        return candidates[0][2]

    @staticmethod
    def _to_local(state: MatchState, side: TeamSide, point: Vector2) -> Vector2:
        return point if side is TeamSide.HOME else state.pitch.mirror(point)

    @staticmethod
    def _from_local(state: MatchState, side: TeamSide, point: Vector2) -> Vector2:
        return point if side is TeamSide.HOME else state.pitch.mirror(point)
