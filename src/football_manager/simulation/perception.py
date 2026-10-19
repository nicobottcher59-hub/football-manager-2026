from __future__ import annotations

from dataclasses import dataclass
from math import inf, isinf

from .geometry import Vector2
from .match_context_effects import MatchContextSystem
from .spatial_state import MatchState, PlayerAgentState, TeamSide


def _clamp01(value: float) -> float:
    return min(max(value, 0.0), 1.0)


@dataclass(frozen=True, slots=True)
class PerceptionConfig:
    base_awareness_radius_m: float = 38.0
    vision_awareness_bonus_m: float = 22.0
    pressure_radius_m: float = 6.5
    receiver_pressure_radius_m: float = 6.0
    lane_open_distance_m: float = 4.0
    lane_blocked_distance_m: float = 0.8


@dataclass(frozen=True, slots=True)
class ObservedPlayer:
    agent_id: str
    side: TeamSide
    location: Vector2
    distance_m: float
    forward_progress_m: float


@dataclass(frozen=True, slots=True)
class PassingLaneAssessment:
    receiver_agent_id: str
    distance_m: float
    forward_progress_m: float
    lane_openness: float
    receiver_space: float
    nearest_lane_opponent_m: float | None

    @property
    def is_progressive(self) -> bool:
        return self.forward_progress_m >= 7.0


@dataclass(frozen=True, slots=True)
class PlayerPerception:
    agent_id: str
    awareness_radius_m: float
    pressure: float
    local_space: float
    goal_location: Vector2
    goal_direction: Vector2
    goal_distance_m: float
    teammates: tuple[ObservedPlayer, ...]
    opponents: tuple[ObservedPlayer, ...]
    passing_lanes: tuple[PassingLaneAssessment, ...]

    def lane_to(self, receiver_agent_id: str) -> PassingLaneAssessment:
        for lane in self.passing_lanes:
            if lane.receiver_agent_id == receiver_agent_id:
                return lane
        raise KeyError(f"no perceived passing lane to {receiver_agent_id!r}")


class PerceptionSystem:
    """Builds a deterministic spatial perception snapshot for one player.

    Phase 5.2 deliberately models football awareness rather than literal rendering
    visibility. A player with better vision/tactical intelligence considers a
    somewhat larger useful radius, while pressure, space and passing lanes are
    derived from the actual spatial state.
    """

    def __init__(
        self,
        config: PerceptionConfig | None = None,
        context: MatchContextSystem | None = None,
    ) -> None:
        self.config = config or PerceptionConfig()
        self.context = context

    def perceive(self, state: MatchState, agent_id: str) -> PlayerPerception:
        agent = state.agent(agent_id)
        awareness_radius = self._awareness_radius(agent)
        goal = self._opponent_goal(state, agent.side)
        goal_delta = goal - agent.location

        teammates: list[ObservedPlayer] = []
        opponents: list[ObservedPlayer] = []
        for other in state.active_players:
            if other.agent_id == agent.agent_id:
                continue
            distance = agent.location.distance_to(other.location)
            if distance > awareness_radius:
                continue
            observed = ObservedPlayer(
                agent_id=other.agent_id,
                side=other.side,
                location=other.location,
                distance_m=distance,
                forward_progress_m=(other.location.x - agent.location.x) * agent.side.attack_sign,
            )
            if other.side is agent.side:
                teammates.append(observed)
            else:
                opponents.append(observed)

        teammates.sort(key=lambda item: (item.distance_m, item.agent_id))
        opponents.sort(key=lambda item: (item.distance_m, item.agent_id))

        pressure = self.pressure_at(state, agent.side, agent.location, self.config.pressure_radius_m)
        passing_lanes = tuple(
            sorted(
                (
                    self._passing_lane(state, agent, state.agent(teammate.agent_id))
                    for teammate in teammates
                ),
                key=lambda lane: (lane.distance_m, lane.receiver_agent_id),
            )
        )

        return PlayerPerception(
            agent_id=agent.agent_id,
            awareness_radius_m=awareness_radius,
            pressure=pressure,
            local_space=1.0 - pressure,
            goal_location=goal,
            goal_direction=goal_delta.normalized(),
            goal_distance_m=goal_delta.magnitude,
            teammates=tuple(teammates),
            opponents=tuple(opponents),
            passing_lanes=passing_lanes,
        )

    def pressure_at(
        self,
        state: MatchState,
        friendly_side: TeamSide,
        location: Vector2,
        radius_m: float | None = None,
    ) -> float:
        """Return 0..1 pressure created by opponents around a location."""

        radius = radius_m or self.config.pressure_radius_m
        if radius <= 0:
            raise ValueError("pressure radius must be positive")

        # Multiple nearby opponents compound pressure, while one distant player
        # contributes only mildly. Product form naturally stays in 0..1.
        remaining_space = 1.0
        for opponent in state.active_players:
            if opponent.side is friendly_side:
                continue
            distance = opponent.location.distance_to(location)
            if distance >= radius:
                continue
            proximity = 1.0 - (distance / radius)
            contribution = _clamp01(proximity * 0.9)
            remaining_space *= 1.0 - contribution
        return _clamp01(1.0 - remaining_space)

    def _awareness_radius(self, agent: PlayerAgentState) -> float:
        mental = agent.player.attributes.mental
        awareness_quality = (
            mental.vision * 0.55
            + mental.tactical_intelligence * 0.30
            + mental.anticipation * 0.15
        ) / 100.0
        radius = self.config.base_awareness_radius_m + (
            self.config.vision_awareness_bonus_m * awareness_quality
        )
        if self.context is not None:
            radius *= self.context.awareness_multiplier()
        return radius

    @staticmethod
    def _opponent_goal(state: MatchState, side: TeamSide) -> Vector2:
        x = state.pitch.length_m if side is TeamSide.HOME else 0.0
        return Vector2(x, state.pitch.width_m / 2.0)

    def _passing_lane(
        self,
        state: MatchState,
        passer: PlayerAgentState,
        receiver: PlayerAgentState,
    ) -> PassingLaneAssessment:
        nearest = inf
        for opponent in state.active_players:
            if opponent.side is passer.side:
                continue
            lane_distance = _distance_to_open_segment(
                opponent.location,
                passer.location,
                receiver.location,
            )
            nearest = min(nearest, lane_distance)

        if isinf(nearest):
            nearest_lane_opponent: float | None = None
            lane_openness = 1.0
        else:
            nearest_lane_opponent = nearest
            low = self.config.lane_blocked_distance_m
            high = self.config.lane_open_distance_m
            if high <= low:
                raise ValueError("lane_open_distance_m must exceed lane_blocked_distance_m")
            lane_openness = _clamp01((nearest - low) / (high - low))

        receiver_pressure = self.pressure_at(
            state,
            passer.side,
            receiver.location,
            self.config.receiver_pressure_radius_m,
        )
        return PassingLaneAssessment(
            receiver_agent_id=receiver.agent_id,
            distance_m=passer.location.distance_to(receiver.location),
            forward_progress_m=(receiver.location.x - passer.location.x) * passer.side.attack_sign,
            lane_openness=lane_openness,
            receiver_space=1.0 - receiver_pressure,
            nearest_lane_opponent_m=nearest_lane_opponent,
        )


def _distance_to_open_segment(point: Vector2, start: Vector2, end: Vector2) -> float:
    """Distance to the useful interior of a pass lane.

    Opponents extremely close to the passer or receiver are handled primarily by
    passer pressure / receiver space, so the lane metric focuses on interception
    risk through the middle of the trajectory.
    """

    segment = end - start
    length_sq = segment.x * segment.x + segment.y * segment.y
    if length_sq == 0.0:
        return point.distance_to(start)

    relative = point - start
    projection = (relative.x * segment.x + relative.y * segment.y) / length_sq
    if projection <= 0.08 or projection >= 0.92:
        return inf
    closest = Vector2(
        start.x + segment.x * projection,
        start.y + segment.y * projection,
    )
    return point.distance_to(closest)
