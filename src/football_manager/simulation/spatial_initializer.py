from __future__ import annotations

from collections import defaultdict

from football_manager.domain import MatchSnapshot, Position, TeamMatchSnapshot

from .clock import MatchClock
from .geometry import Vector2
from .positioning_anchors import normalized_anchor
from .randomness import MatchRandom
from .spatial_state import (
    BallState,
    MatchState,
    PitchDimensions,
    PlayerAgentState,
    PossessionState,
    TeamSide,
)


def _duplicate_offsets(count: int, spacing: float = 0.13) -> tuple[float, ...]:
    if count <= 1:
        return (0.0,)
    centre = (count - 1) / 2.0
    return tuple((index - centre) * spacing for index in range(count))


def _home_locations(team: TeamMatchSnapshot, pitch: PitchDimensions) -> dict[str, Vector2]:
    by_position: dict[Position, list[str]] = defaultdict(list)
    for player in team.starters:
        assert player.assigned_position is not None
        assert player.assigned_slot_id is not None
        by_position[player.assigned_position].append(player.assigned_slot_id)

    slot_offsets: dict[str, float] = {}
    for position, slot_ids in by_position.items():
        for slot_id, offset in zip(
            sorted(slot_ids),
            _duplicate_offsets(len(slot_ids)),
            strict=True,
        ):
            slot_offsets[slot_id] = offset

    result: dict[str, Vector2] = {}
    for player in team.starters:
        assert player.assigned_position is not None
        assert player.assigned_slot_id is not None
        normalized_x, normalized_y = normalized_anchor(player.assigned_position)
        normalized_y = min(max(normalized_y + slot_offsets[player.assigned_slot_id], 0.05), 0.95)
        result[player.assigned_slot_id] = Vector2(
            normalized_x * pitch.length_m,
            normalized_y * pitch.width_m,
        )
    return result


def _agent_id(side: TeamSide, player_id: str) -> str:
    return f"{side.value}:{player_id}"


def _build_team_agents(
    team: TeamMatchSnapshot,
    side: TeamSide,
    pitch: PitchDimensions,
) -> dict[str, PlayerAgentState]:
    home_locations = _home_locations(team, pitch)
    agents: dict[str, PlayerAgentState] = {}

    for player in team.starters:
        assert player.assigned_slot_id is not None
        assert player.assigned_position is not None
        location = home_locations[player.assigned_slot_id]
        if side is TeamSide.AWAY:
            location = pitch.mirror(location)

        agent_id = _agent_id(side, player.player_id)
        facing = Vector2(1.0, 0.0) if side is TeamSide.HOME else Vector2(-1.0, 0.0)
        agents[agent_id] = PlayerAgentState(
            agent_id=agent_id,
            side=side,
            player=player,
            slot_id=player.assigned_slot_id,
            assigned_position=player.assigned_position,
            location=location,
            facing=facing,
        )

    return agents


def create_initial_match_state(
    snapshot: MatchSnapshot,
    random_source: MatchRandom | None = None,
) -> MatchState:
    """Create the mutable spatial state owned by a match simulation."""

    rng = random_source or MatchRandom(snapshot.seed)
    pitch = PitchDimensions(
        length_m=float(snapshot.context.stadium.pitch_length_m),
        width_m=float(snapshot.context.stadium.pitch_width_m),
    )

    players = {
        **_build_team_agents(snapshot.home_team, TeamSide.HOME, pitch),
        **_build_team_agents(snapshot.away_team, TeamSide.AWAY, pitch),
    }

    kickoff_side = rng.choice((TeamSide.HOME, TeamSide.AWAY))
    ball = BallState(location=pitch.centre)

    return MatchState(
        match_id=snapshot.match_id,
        seed=snapshot.seed,
        pitch=pitch,
        clock=MatchClock(),
        players=players,
        ball=ball,
        possession=PossessionState(team_side=kickoff_side, owner_agent_id=None),
        kickoff_side=kickoff_side,
    )
