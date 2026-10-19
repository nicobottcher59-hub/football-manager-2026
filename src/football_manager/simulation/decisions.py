from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from math import exp

from football_manager.domain import MatchSnapshot, Position

from .perception import PassingLaneAssessment, PerceptionSystem, PlayerPerception
from .randomness import MatchRandom
from .spatial_state import MatchState, PlayerAgentState, TeamSide


def _clamp(value: float, minimum: float = 0.0, maximum: float = 100.0) -> float:
    return min(max(value, minimum), maximum)


class ActionType(StrEnum):
    HOLD = "hold"
    SHORT_PASS = "short_pass"
    PROGRESSIVE_PASS = "progressive_pass"
    LONG_PASS = "long_pass"
    CARRY = "carry"
    DRIBBLE = "dribble"
    CROSS = "cross"
    SHOOT = "shoot"
    CLEARANCE = "clearance"


@dataclass(frozen=True, slots=True)
class DecisionFactors:
    tactical_fit: float
    spatial_value: float
    capability: float
    decision_quality: float
    risk: float


@dataclass(frozen=True, slots=True)
class ActionOption:
    action_type: ActionType
    utility: float
    factors: DecisionFactors
    target_agent_id: str | None = None


@dataclass(frozen=True, slots=True)
class PlayerDecision:
    agent_id: str
    action_type: ActionType
    target_agent_id: str | None
    utility: float
    considered_options: int


class DecisionSystem:
    """Creates and selects possession actions without executing them.

    This phase decides *what a player wants to try*. Pass completion, dribble
    success, shot outcome and every other execution result are intentionally left
    to later action resolvers.
    """

    def __init__(
        self,
        snapshot: MatchSnapshot,
        random_source: MatchRandom,
        perception: PerceptionSystem | None = None,
    ) -> None:
        self.snapshot = snapshot
        self.random = random_source
        self.perception = perception or PerceptionSystem()
        self._team_tactics = {
            TeamSide.HOME: snapshot.home_team.tactic,
            TeamSide.AWAY: snapshot.away_team.tactic,
        }

    def options_for(self, state: MatchState, agent_id: str) -> tuple[ActionOption, ...]:
        agent = state.agent(agent_id)
        self._require_ball_owner(state, agent)
        perception = self.perception.perceive(state, agent_id)

        options: list[ActionOption] = [self._hold_option(agent, perception)]
        options.extend(self._pass_options(state, agent, perception))

        if agent.assigned_position is not Position.GK:
            options.append(self._carry_option(state, agent, perception))
            if self._can_dribble(perception):
                options.append(self._dribble_option(state, agent, perception))
            if self._can_cross(state, agent):
                options.append(self._cross_option(state, agent, perception))
            if self._can_shoot(state, agent, perception):
                options.append(self._shoot_option(state, agent, perception))

        if self._can_clear(state, agent, perception):
            options.append(self._clearance_option(state, agent, perception))

        return tuple(
            sorted(
                options,
                key=lambda option: (
                    -option.utility,
                    option.action_type.value,
                    option.target_agent_id or "",
                ),
            )
        )

    def decide(self, state: MatchState, agent_id: str) -> PlayerDecision:
        options = self.options_for(state, agent_id)
        agent = state.agent(agent_id)
        mental = agent.player.attributes.mental
        decision_quality = (
            mental.decisions * 0.55
            + mental.composure * 0.25
            + mental.tactical_intelligence * 0.20
        ) / 100.0

        # Better decision makers are more likely to favour the best-rated action,
        # but nobody is perfectly deterministic.  Selection is deliberately
        # two-stage: first choose an action *family*, then a target inside that
        # family.  Without this normalization ten possible pass receivers counted
        # as ten votes against one carry/dribble option, so integrated matches
        # became mechanically pass-heavy even when carrying or dribbling had a
        # similar utility.
        temperature = 15.0 - (decision_quality * 8.0)
        families: dict[str, list[ActionOption]] = {}
        for option in options:
            family = self._action_family(option.action_type)
            families.setdefault(family, []).append(option)

        family_items = sorted(families.items(), key=lambda item: item[0])
        # Family priors are deliberately small compared with the option utility,
        # but they encode football plausibility that is lost when every action
        # family gets exactly one lottery ticket.  In particular, a clearance is
        # an emergency action, not an equal peer of a normal pass just because it
        # is available in the player's own third.
        family_priors = {
            "pass": 5.0,
            ActionType.CARRY.value: 3.0,
            ActionType.DRIBBLE.value: 2.0,
            ActionType.CROSS.value: 3.5,
            ActionType.SHOOT.value: 7.0,
            ActionType.HOLD.value: -4.0,
            ActionType.CLEARANCE.value: -15.0,
        }
        family_utilities = [
            max(option.utility for option in items) + family_priors.get(name, 0.0)
            for name, items in family_items
        ]
        max_family_utility = max(family_utilities)
        family_weights = [
            exp((utility - max_family_utility) / temperature)
            for utility in family_utilities
        ]
        family_index = self._weighted_index(family_weights)
        chosen_family = tuple(family_items[family_index][1])

        family_max = max(option.utility for option in chosen_family)
        target_temperature = max(4.5, temperature * 0.72)
        target_weights = [
            exp((option.utility - family_max) / target_temperature)
            for option in chosen_family
        ]
        chosen = self._weighted_choice(chosen_family, target_weights)
        return PlayerDecision(
            agent_id=agent.agent_id,
            action_type=chosen.action_type,
            target_agent_id=chosen.target_agent_id,
            utility=chosen.utility,
            considered_options=len(options),
        )

    @staticmethod
    def _action_family(action: ActionType) -> str:
        if action in {ActionType.SHORT_PASS, ActionType.PROGRESSIVE_PASS, ActionType.LONG_PASS}:
            return "pass"
        return action.value

    def _weighted_index(self, weights: list[float]) -> int:
        total = sum(weights)
        if total <= 0.0:
            return 0
        needle = self.random.random() * total
        cumulative = 0.0
        for index, weight in enumerate(weights):
            cumulative += weight
            if needle <= cumulative:
                return index
        return len(weights) - 1

    def _weighted_choice(
        self,
        options: tuple[ActionOption, ...],
        weights: list[float],
    ) -> ActionOption:
        total = sum(weights)
        if total <= 0.0:
            return options[0]
        needle = self.random.random() * total
        cumulative = 0.0
        for option, weight in zip(options, weights, strict=True):
            cumulative += weight
            if needle <= cumulative:
                return option
        return options[-1]

    @staticmethod
    def _require_ball_owner(state: MatchState, agent: PlayerAgentState) -> None:
        if not agent.is_active:
            raise ValueError("dismissed player cannot make possession decisions")
        if state.ball.owner_agent_id != agent.agent_id:
            raise ValueError("possession decisions require the player to own the ball")
        if state.possession.owner_agent_id != agent.agent_id:
            raise ValueError("ball owner and possession owner must match")
        if state.possession.team_side is not agent.side:
            raise ValueError("possession team must match the ball owner")

    def _pass_options(
        self,
        state: MatchState,
        agent: PlayerAgentState,
        perception: PlayerPerception,
    ) -> list[ActionOption]:
        options: list[ActionOption] = []
        for lane in perception.passing_lanes:
            # Distance and progression are separate ideas. A 35 m ball into a
            # runner's path is still a LONG_PASS even when it breaks lines; the
            # old classifier mislabeled almost every forward long ball as merely
            # progressive, which made the integrated match look unnaturally short.
            if lane.distance_m <= 18.0:
                action = ActionType.SHORT_PASS
            elif lane.distance_m >= 32.0:
                action = ActionType.LONG_PASS
            elif lane.forward_progress_m >= 6.0:
                action = ActionType.PROGRESSIVE_PASS
            else:
                action = ActionType.SHORT_PASS
            options.append(self._pass_option(state, agent, perception, lane, action))
        return options

    def _pass_option(
        self,
        state: MatchState,
        agent: PlayerAgentState,
        perception: PlayerPerception,
        lane: PassingLaneAssessment,
        action: ActionType,
    ) -> ActionOption:
        instructions = self._team_tactics[agent.side].team_instructions.in_possession
        player_instructions = agent.player.effective_instructions
        technical = agent.player.attributes.technical
        mental = agent.player.attributes.mental

        target_length = {
            ActionType.SHORT_PASS: 25.0,
            ActionType.PROGRESSIVE_PASS: 50.0,
            ActionType.LONG_PASS: 80.0,
        }[action]
        pass_length_fit = 100.0 - abs(float(instructions.pass_length) - target_length)
        progressive_bias = _clamp(50.0 + lane.forward_progress_m * 2.0)
        if action is ActionType.SHORT_PASS:
            vertical_fit = 100.0 - abs(float(instructions.verticality) - 35.0)
        elif action is ActionType.PROGRESSIVE_PASS:
            vertical_fit = 100.0 - abs(float(instructions.verticality) - 65.0)
        else:
            vertical_fit = 100.0 - abs(float(instructions.verticality) - 80.0)

        individual_risk = (
            float(player_instructions.passing_risk)
            if player_instructions is not None
            else 50.0
        )
        tactical_fit = _clamp(
            pass_length_fit * 0.38
            + vertical_fit * 0.28
            + float(instructions.passing_risk) * 0.17
            + individual_risk * 0.17
        )
        if action is ActionType.SHORT_PASS:
            tactical_fit = _clamp(tactical_fit + float(instructions.patience) * 0.12)
        elif action in (ActionType.PROGRESSIVE_PASS, ActionType.LONG_PASS):
            tactical_fit = _clamp(tactical_fit * 0.85 + progressive_bias * 0.15)

        distance_fit = _clamp(100.0 - max(0.0, lane.distance_m - 8.0) * 1.7)
        progress_value = _clamp(50.0 + lane.forward_progress_m * 2.2)
        spatial_value = _clamp(
            lane.lane_openness * 45.0
            + lane.receiver_space * 30.0
            + distance_fit * 0.10
            + progress_value * 0.15
        )
        receiver = state.agent(lane.receiver_agent_id)
        active_run = receiver.movement_intent in {
            "run_in_behind",
            "attack_box",
            "overlap",
            "underlap",
        }
        if active_run and lane.forward_progress_m >= 5.0:
            # A live run creates a real reason to play into space.  The boost is
            # attached to the spatial option, not to the receiver's attributes.
            run_bonus = min(18.0, 7.0 + lane.forward_progress_m * 0.35)
            spatial_value = _clamp(spatial_value + run_bonus)
            if action in {ActionType.PROGRESSIVE_PASS, ActionType.LONG_PASS}:
                tactical_fit = _clamp(tactical_fit + 8.0)
        capability = _clamp(
            technical.passing * 0.42
            + technical.technique * 0.18
            + technical.first_touch * 0.08
            + mental.vision * 0.20
            + mental.creativity * 0.12
        )
        risk = _clamp(
            (1.0 - lane.lane_openness) * 48.0
            + (1.0 - lane.receiver_space) * 22.0
            + perception.pressure * 18.0
            + min(lane.distance_m / 45.0, 1.0) * 12.0
        )
        return self._option(
            agent,
            action,
            tactical_fit=tactical_fit,
            spatial_value=spatial_value,
            capability=capability,
            risk=risk,
            target_agent_id=lane.receiver_agent_id,
        )

    def _hold_option(
        self,
        agent: PlayerAgentState,
        perception: PlayerPerception,
    ) -> ActionOption:
        team = self._team_tactics[agent.side].team_instructions.in_possession
        player = agent.player.effective_instructions
        technical = agent.player.attributes.technical
        mental = agent.player.attributes.mental
        physical = agent.player.attributes.physical
        hold_up = float(player.hold_up_play) if player is not None else 50.0
        tactical_fit = _clamp(float(team.patience) * 0.65 + hold_up * 0.35)
        spatial_value = _clamp(perception.local_space * 80.0 + 20.0)
        capability = _clamp(
            technical.first_touch * 0.30
            + technical.technique * 0.20
            + mental.composure * 0.30
            + physical.strength * 0.20
        )
        risk = _clamp(perception.pressure * 65.0)
        return self._option(
            agent,
            ActionType.HOLD,
            tactical_fit=tactical_fit,
            spatial_value=spatial_value,
            capability=capability,
            risk=risk,
        )

    def _carry_option(
        self,
        state: MatchState,
        agent: PlayerAgentState,
        perception: PlayerPerception,
    ) -> ActionOption:
        player = agent.player.effective_instructions
        technical = agent.player.attributes.technical
        mental = agent.player.attributes.mental
        physical = agent.player.attributes.physical
        attack_space = float(player.attack_space) if player is not None else 50.0
        dribble_frequency = float(player.dribbling_frequency) if player is not None else 50.0
        tactical_fit = _clamp(attack_space * 0.65 + dribble_frequency * 0.35)
        forward_space = self._forward_space(state, agent, metres=7.0)
        spatial_value = _clamp(forward_space * 75.0 + perception.local_space * 25.0)
        capability = _clamp(
            technical.dribbling * 0.25
            + technical.technique * 0.15
            + physical.acceleration * 0.25
            + physical.agility * 0.20
            + physical.balance * 0.15
        )
        risk = _clamp(perception.pressure * 45.0 + (1.0 - forward_space) * 35.0)
        return self._option(
            agent,
            ActionType.CARRY,
            tactical_fit=tactical_fit,
            spatial_value=spatial_value,
            capability=capability,
            risk=risk,
        )

    def _dribble_option(
        self,
        state: MatchState,
        agent: PlayerAgentState,
        perception: PlayerPerception,
    ) -> ActionOption:
        player = agent.player.effective_instructions
        technical = agent.player.attributes.technical
        mental = agent.player.attributes.mental
        physical = agent.player.attributes.physical
        dribble_frequency = float(player.dribbling_frequency) if player is not None else 50.0
        attack_space = float(player.attack_space) if player is not None else 50.0
        attacking_role_bonus = 0.0
        if agent.assigned_position in {Position.RW, Position.LW, Position.AM, Position.SS, Position.ST}:
            attacking_role_bonus = 10.0
        tactical_fit = _clamp(
            dribble_frequency * 0.66
            + attack_space * 0.26
            + attacking_role_bonus
        )
        nearest = min((item.distance_m for item in perception.opponents), default=8.0)
        engagement = _clamp(100.0 - abs(nearest - 2.7) * 24.0)
        forward_space = self._forward_space(state, agent, metres=6.0)
        wide_one_v_one = 0.0
        if agent.assigned_position in {Position.RW, Position.LW, Position.RB, Position.LB, Position.RWB, Position.LWB}:
            wide_one_v_one = 12.0 * forward_space
        spatial_value = _clamp(engagement * 0.50 + forward_space * 42.0 + wide_one_v_one)
        capability = _clamp(
            technical.dribbling * 0.40
            + technical.technique * 0.18
            + physical.agility * 0.18
            + physical.acceleration * 0.14
            + mental.decisions * 0.10
        )
        risk = _clamp(perception.pressure * 58.0 + (1.0 - forward_space) * 30.0)
        return self._option(
            agent,
            ActionType.DRIBBLE,
            tactical_fit=tactical_fit,
            spatial_value=spatial_value,
            capability=capability,
            risk=risk,
        )

    def _cross_option(
        self,
        state: MatchState,
        agent: PlayerAgentState,
        perception: PlayerPerception,
    ) -> ActionOption:
        team = self._team_tactics[agent.side].team_instructions.in_possession
        player = agent.player.effective_instructions
        technical = agent.player.attributes.technical
        mental = agent.player.attributes.mental
        player_cross = float(player.crossing_frequency) if player is not None else 50.0
        tactical_fit = _clamp(float(team.crossing_frequency) * 0.55 + player_cross * 0.45)
        wide_distance = min(agent.location.y, state.pitch.width_m - agent.location.y)
        width_value = _clamp((17.0 - wide_distance) / 17.0 * 100.0)
        progress = self._attack_progress(state, agent)
        spatial_value = _clamp(width_value * 0.55 + progress * 100.0 * 0.45)
        capability = _clamp(
            technical.crossing * 0.52
            + technical.technique * 0.18
            + mental.vision * 0.15
            + mental.decisions * 0.15
        )
        risk = _clamp(perception.pressure * 35.0 + (1.0 - progress) * 20.0)
        return self._option(
            agent,
            ActionType.CROSS,
            tactical_fit=tactical_fit,
            spatial_value=spatial_value,
            capability=capability,
            risk=risk,
        )

    def _shoot_option(
        self,
        state: MatchState,
        agent: PlayerAgentState,
        perception: PlayerPerception,
    ) -> ActionOption:
        team = self._team_tactics[agent.side].team_instructions.in_possession
        player = agent.player.effective_instructions
        technical = agent.player.attributes.technical
        mental = agent.player.attributes.mental
        shooting_frequency = float(player.shooting_frequency) if player is not None else 50.0
        long_shot_bias = float(team.long_shot_frequency)
        distance = perception.goal_distance_m
        tactical_fit = shooting_frequency
        if distance > 22.0:
            tactical_fit = _clamp(shooting_frequency * 0.65 + long_shot_bias * 0.35)
        distance_value = _clamp((36.0 - distance) / 26.0 * 100.0)
        centre_offset = abs(agent.location.y - state.pitch.width_m / 2.0)
        angle_value = _clamp(100.0 - centre_offset * 2.2)
        spatial_value = _clamp(distance_value * 0.72 + angle_value * 0.28)
        finishing_weight = 0.48 if distance <= 22.0 else 0.25
        long_weight = 0.12 if distance <= 22.0 else 0.35
        capability = _clamp(
            technical.finishing * finishing_weight
            + technical.long_shots * long_weight
            + technical.technique * 0.12
            + technical.shot_power * 0.10
            + mental.composure * 0.10
            + mental.decisions * 0.08
        )
        risk = _clamp((100.0 - spatial_value) * 0.55 + perception.pressure * 22.0)
        return self._option(
            agent,
            ActionType.SHOOT,
            tactical_fit=tactical_fit,
            spatial_value=spatial_value,
            capability=capability,
            risk=risk,
        )

    def _clearance_option(
        self,
        state: MatchState,
        agent: PlayerAgentState,
        perception: PlayerPerception,
    ) -> ActionOption:
        technical = agent.player.attributes.technical
        mental = agent.player.attributes.mental
        own_third = 1.0 - self._attack_progress(state, agent)
        tactical_fit = _clamp(own_third * 75.0 + perception.pressure * 35.0)
        spatial_value = _clamp(own_third * 65.0 + perception.pressure * 45.0)
        capability = _clamp(
            technical.passing * 0.20
            + technical.technique * 0.15
            + technical.heading * 0.15
            + mental.decisions * 0.25
            + mental.composure * 0.25
        )
        risk = _clamp((1.0 - own_third) * 45.0 + perception.local_space * 20.0)
        return self._option(
            agent,
            ActionType.CLEARANCE,
            tactical_fit=tactical_fit,
            spatial_value=spatial_value,
            capability=capability,
            risk=risk,
        )

    def _option(
        self,
        agent: PlayerAgentState,
        action_type: ActionType,
        *,
        tactical_fit: float,
        spatial_value: float,
        capability: float,
        risk: float,
        target_agent_id: str | None = None,
    ) -> ActionOption:
        mental = agent.player.attributes.mental
        decision_quality = _clamp(
            mental.decisions * 0.50
            + mental.composure * 0.20
            + mental.tactical_intelligence * 0.20
            + mental.anticipation * 0.10
        )
        utility = _clamp(
            tactical_fit * 0.28
            + spatial_value * 0.30
            + capability * 0.20
            + decision_quality * 0.22
            - risk * 0.24
        )
        return ActionOption(
            action_type=action_type,
            target_agent_id=target_agent_id,
            utility=utility,
            factors=DecisionFactors(
                tactical_fit=_clamp(tactical_fit),
                spatial_value=_clamp(spatial_value),
                capability=_clamp(capability),
                decision_quality=decision_quality,
                risk=_clamp(risk),
            ),
        )

    def _forward_space(self, state: MatchState, agent: PlayerAgentState, metres: float) -> float:
        target_x = agent.location.x + metres * agent.side.attack_sign
        target = state.pitch.clamp(type(agent.location)(target_x, agent.location.y))
        pressure = self.perception.pressure_at(state, agent.side, target)
        return 1.0 - pressure

    @staticmethod
    def _attack_progress(state: MatchState, agent: PlayerAgentState) -> float:
        if agent.side is TeamSide.HOME:
            return _clamp(agent.location.x / state.pitch.length_m, 0.0, 1.0)
        return _clamp((state.pitch.length_m - agent.location.x) / state.pitch.length_m, 0.0, 1.0)

    @staticmethod
    def _can_dribble(perception: PlayerPerception) -> bool:
        return any(item.distance_m <= 5.0 for item in perception.opponents)

    @staticmethod
    def _can_cross(state: MatchState, agent: PlayerAgentState) -> bool:
        """Only offer a cross from a plausible wide attacking zone.

        The first integrated 5.9 viewer exposed a bad emergent behaviour: wide
        players could cross almost from halfway.  Crossing is now gated to an
        advanced wide zone; the progression layer separately chooses only
        attacking/midfield runners as open-play targets.
        """

        wide = min(agent.location.y, state.pitch.width_m - agent.location.y) <= 17.0
        progress = (
            agent.location.x / state.pitch.length_m
            if agent.side is TeamSide.HOME
            else (state.pitch.length_m - agent.location.x) / state.pitch.length_m
        )
        return wide and progress >= 0.58

    @staticmethod
    def _can_shoot(
        state: MatchState,
        agent: PlayerAgentState,
        perception: PlayerPerception,
    ) -> bool:
        progress = (
            agent.location.x / state.pitch.length_m
            if agent.side is TeamSide.HOME
            else (state.pitch.length_m - agent.location.x) / state.pitch.length_m
        )
        return progress >= 0.52 and perception.goal_distance_m <= 36.0

    @staticmethod
    def _can_clear(
        state: MatchState,
        agent: PlayerAgentState,
        perception: PlayerPerception,
    ) -> bool:
        progress = (
            agent.location.x / state.pitch.length_m
            if agent.side is TeamSide.HOME
            else (state.pitch.length_m - agent.location.x) / state.pitch.length_m
        )
        return progress <= 0.36 or perception.pressure >= 0.62
