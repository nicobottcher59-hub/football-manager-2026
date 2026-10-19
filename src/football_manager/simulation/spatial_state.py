from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from football_manager.domain import PlayerMatchSnapshot, Position

from .clock import MatchClock
from .geometry import Vector2


class TacticalPhase(StrEnum):
    IN_POSSESSION = "in_possession"
    OUT_OF_POSSESSION = "out_of_possession"


class TeamSide(StrEnum):
    HOME = "home"
    AWAY = "away"

    @property
    def opponent(self) -> "TeamSide":
        return TeamSide.AWAY if self is TeamSide.HOME else TeamSide.HOME

    @property
    def attack_sign(self) -> float:
        return 1.0 if self is TeamSide.HOME else -1.0


@dataclass(frozen=True, slots=True)
class PitchDimensions:
    length_m: float
    width_m: float

    def __post_init__(self) -> None:
        if self.length_m <= 0:
            raise ValueError("pitch length must be positive")
        if self.width_m <= 0:
            raise ValueError("pitch width must be positive")

    @property
    def centre(self) -> Vector2:
        return Vector2(self.length_m / 2.0, self.width_m / 2.0)

    def contains(self, location: Vector2) -> bool:
        return 0.0 <= location.x <= self.length_m and 0.0 <= location.y <= self.width_m

    def clamp(self, location: Vector2) -> Vector2:
        return Vector2(
            min(max(location.x, 0.0), self.length_m),
            min(max(location.y, 0.0), self.width_m),
        )

    def mirror(self, location: Vector2) -> Vector2:
        """Rotate a home-perspective point 180 degrees for the away team."""

        return Vector2(self.length_m - location.x, self.width_m - location.y)


@dataclass(slots=True)
class PlayerAgentState:
    agent_id: str
    side: TeamSide
    player: PlayerMatchSnapshot
    slot_id: str
    assigned_position: Position
    location: Vector2
    velocity: Vector2 = field(default_factory=Vector2.zero)
    facing: Vector2 = field(default_factory=lambda: Vector2(1.0, 0.0))
    has_ball: bool = False
    tactical_target: Vector2 | None = None
    tactical_phase: TacticalPhase | None = None
    movement_intent: str | None = None
    movement_target: Vector2 | None = None
    current_fitness: float | None = None
    current_fatigue: float | None = None
    yellow_cards: int = 0
    dismissed: bool = False

    def __post_init__(self) -> None:
        if not self.agent_id.strip():
            raise ValueError("agent_id cannot be empty")
        if not self.slot_id.strip():
            raise ValueError("slot_id cannot be empty")
        if not isinstance(self.side, TeamSide):
            self.side = TeamSide(self.side)
        if not isinstance(self.assigned_position, Position):
            self.assigned_position = Position(self.assigned_position)
        if self.player.player_id == "":
            raise ValueError("player snapshot must have a player_id")
        if self.current_fitness is None:
            self.current_fitness = float(self.player.state.fitness)
        if self.current_fatigue is None:
            self.current_fatigue = float(self.player.state.fatigue)
        if not 0.0 <= self.current_fitness <= 100.0:
            raise ValueError("current_fitness must be between 0 and 100")
        if not 0.0 <= self.current_fatigue <= 100.0:
            raise ValueError("current_fatigue must be between 0 and 100")
        if self.yellow_cards < 0:
            raise ValueError("yellow_cards cannot be negative")

    @property
    def is_active(self) -> bool:
        return not self.dismissed


@dataclass(slots=True)
class BallState:
    location: Vector2
    velocity: Vector2 = field(default_factory=Vector2.zero)
    height_m: float = 0.0
    owner_agent_id: str | None = None
    last_touch_agent_id: str | None = None

    def __post_init__(self) -> None:
        if self.height_m < 0:
            raise ValueError("ball height cannot be negative")


@dataclass(slots=True)
class PossessionState:
    team_side: TeamSide | None = None
    owner_agent_id: str | None = None

    def __post_init__(self) -> None:
        if self.team_side is not None and not isinstance(self.team_side, TeamSide):
            self.team_side = TeamSide(self.team_side)


@dataclass(slots=True)
class MatchState:
    match_id: str
    seed: int
    pitch: PitchDimensions
    clock: MatchClock
    players: dict[str, PlayerAgentState]
    ball: BallState
    possession: PossessionState
    kickoff_side: TeamSide

    def __post_init__(self) -> None:
        if not self.match_id.strip():
            raise ValueError("match state match_id cannot be empty")
        if self.seed < 0:
            raise ValueError("match state seed must be non-negative")
        if not isinstance(self.kickoff_side, TeamSide):
            self.kickoff_side = TeamSide(self.kickoff_side)

        if len(self.players) != 22:
            raise ValueError("spatial match state must contain exactly 22 active players")

        home = [agent for agent in self.players.values() if agent.side is TeamSide.HOME]
        away = [agent for agent in self.players.values() if agent.side is TeamSide.AWAY]
        if len(home) != 11 or len(away) != 11:
            raise ValueError("spatial match state must contain 11 players per team")

        if any(not self.pitch.contains(agent.location) for agent in self.players.values()):
            raise ValueError("all player locations must be inside the pitch")
        if not self.pitch.contains(self.ball.location):
            raise ValueError("ball location must be inside the pitch")

        if self.ball.owner_agent_id is not None and self.ball.owner_agent_id not in self.players:
            raise ValueError("ball owner must be an active player agent")
        if self.possession.owner_agent_id is not None and self.possession.owner_agent_id not in self.players:
            raise ValueError("possession owner must be an active player agent")

    @property
    def home_players(self) -> tuple[PlayerAgentState, ...]:
        return tuple(agent for agent in self.players.values() if agent.side is TeamSide.HOME)

    @property
    def away_players(self) -> tuple[PlayerAgentState, ...]:
        return tuple(agent for agent in self.players.values() if agent.side is TeamSide.AWAY)

    @property
    def active_players(self) -> tuple[PlayerAgentState, ...]:
        return tuple(agent for agent in self.players.values() if agent.is_active)

    def active_players_for_side(self, side: TeamSide) -> tuple[PlayerAgentState, ...]:
        side = TeamSide(side)
        return tuple(agent for agent in self.players.values() if agent.side is side and agent.is_active)

    def agent(self, agent_id: str) -> PlayerAgentState:
        try:
            return self.players[agent_id]
        except KeyError as exc:
            raise KeyError(f"player agent {agent_id!r} does not exist") from exc

    def player_for_slot(self, side: TeamSide, slot_id: str) -> PlayerAgentState:
        side = TeamSide(side)
        for agent in self.players.values():
            if agent.side is side and agent.slot_id == slot_id and agent.is_active:
                return agent
        raise KeyError(f"no {side.value} player assigned to slot {slot_id!r}")

    def signature(self) -> tuple[object, ...]:
        """Stable compact representation useful for deterministic tests/debugging."""

        player_signature = tuple(
            (
                agent.agent_id,
                agent.slot_id,
                round(agent.location.x, 6),
                round(agent.location.y, 6),
                round(agent.velocity.x, 6),
                round(agent.velocity.y, 6),
                round(agent.tactical_target.x, 6) if agent.tactical_target else None,
                round(agent.tactical_target.y, 6) if agent.tactical_target else None,
                agent.tactical_phase.value if agent.tactical_phase else None,
                agent.movement_intent,
                round(agent.movement_target.x, 6) if agent.movement_target else None,
                round(agent.movement_target.y, 6) if agent.movement_target else None,
                round(agent.current_fitness, 6),
                round(agent.current_fatigue, 6),
                agent.yellow_cards,
                agent.dismissed,
            )
            for agent in sorted(self.players.values(), key=lambda item: item.agent_id)
        )
        return (
            self.match_id,
            self.seed,
            self.kickoff_side.value,
            self.clock.tick_count,
            round(self.ball.location.x, 6),
            round(self.ball.location.y, 6),
            round(self.ball.velocity.x, 6),
            round(self.ball.velocity.y, 6),
            round(self.ball.height_m, 6),
            self.ball.owner_agent_id,
            self.ball.last_touch_agent_id,
            self.possession.team_side.value if self.possession.team_side else None,
            self.possession.owner_agent_id,
            player_signature,
        )
