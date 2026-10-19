from __future__ import annotations

from dataclasses import dataclass

from football_manager.domain import MatchSnapshot
from football_manager.simulation import MatchEvent, MatchEventType, MatchScore, RestartType, TeamSide


@dataclass(slots=True)
class _MutableTeamStatistics:
    possession_ticks: int = 0
    passes_attempted: int = 0
    passes_completed: int = 0
    shots: int = 0
    shots_on_target: int = 0
    xg: float = 0.0
    goals: int = 0
    saves: int = 0
    tackles: int = 0
    successful_tackles: int = 0
    recoveries: int = 0
    dribbles: int = 0
    successful_dribbles: int = 0
    crosses: int = 0
    completed_crosses: int = 0
    fouls: int = 0
    yellow_cards: int = 0
    red_cards: int = 0
    corners: int = 0


@dataclass(frozen=True, slots=True)
class TeamStatistics:
    possession_pct: float
    passes_attempted: int
    passes_completed: int
    shots: int
    shots_on_target: int
    xg: float
    goals: int
    saves: int
    tackles: int
    successful_tackles: int
    recoveries: int
    dribbles: int
    successful_dribbles: int
    crosses: int
    completed_crosses: int
    fouls: int
    yellow_cards: int
    red_cards: int
    corners: int

    @property
    def pass_completion_pct(self) -> float:
        if self.passes_attempted <= 0:
            return 0.0
        return self.passes_completed / self.passes_attempted * 100.0


@dataclass(frozen=True, slots=True)
class MatchStatistics:
    home: TeamStatistics
    away: TeamStatistics


class MatchStatisticsTracker:
    """Presentation-side match statistics derived from state time and events.

    This tracker never influences simulation. It consumes the same state/event stream
    used by the 2D viewer and text commentary, so changing presentation cannot alter
    the match result.
    """

    def __init__(self, snapshot: MatchSnapshot) -> None:
        self._stats = {
            TeamSide.HOME: _MutableTeamStatistics(),
            TeamSide.AWAY: _MutableTeamStatistics(),
        }
        self._agent_side: dict[str, TeamSide] = {}
        for side, team in (
            (TeamSide.HOME, snapshot.home_team),
            (TeamSide.AWAY, snapshot.away_team),
        ):
            for player in team.starters + team.bench:
                self._agent_side[f"{side.value}:{player.player_id}"] = side

    def observe_possession(self, side: TeamSide | None, ticks: int = 1) -> None:
        if ticks < 0:
            raise ValueError("ticks cannot be negative")
        if side is None or ticks == 0:
            return
        self._stats[TeamSide(side)].possession_ticks += ticks

    def consume(self, events: tuple[MatchEvent, ...] | list[MatchEvent]) -> None:
        for event in events:
            self._consume_event(event)

    def snapshot(self, score: MatchScore | None = None) -> MatchStatistics:
        total_possession = sum(item.possession_ticks for item in self._stats.values())

        def freeze(side: TeamSide) -> TeamStatistics:
            item = self._stats[side]
            possession = (
                item.possession_ticks / total_possession * 100.0
                if total_possession > 0
                else 50.0
            )
            goals = item.goals
            if score is not None:
                goals = score.home if side is TeamSide.HOME else score.away
            return TeamStatistics(
                possession_pct=possession,
                passes_attempted=item.passes_attempted,
                passes_completed=item.passes_completed,
                shots=item.shots,
                shots_on_target=item.shots_on_target,
                xg=item.xg,
                goals=goals,
                saves=item.saves,
                tackles=item.tackles,
                successful_tackles=item.successful_tackles,
                recoveries=item.recoveries,
                dribbles=item.dribbles,
                successful_dribbles=item.successful_dribbles,
                crosses=item.crosses,
                completed_crosses=item.completed_crosses,
                fouls=item.fouls,
                yellow_cards=item.yellow_cards,
                red_cards=item.red_cards,
                corners=item.corners,
            )

        return MatchStatistics(home=freeze(TeamSide.HOME), away=freeze(TeamSide.AWAY))

    def _consume_event(self, event: MatchEvent) -> None:
        event_type = event.event_type
        actor_side = self._side_for_agent(event.actor_agent_id)
        details = event.details
        assert details is not None

        if event_type is MatchEventType.PASS:
            status = details.status
            outcome = details.outcome
            if status == "attempt" and actor_side is not None:
                self._stats[actor_side].passes_attempted += 1
            elif outcome == "completed" and actor_side is not None:
                self._stats[actor_side].passes_completed += 1
            return

        if event_type is MatchEventType.SHOT and actor_side is not None:
            self._stats[actor_side].shots += 1
            self._stats[actor_side].xg += details.xg or 0.0
            return

        if event_type is MatchEventType.PENALTY_KICK and event.side is not None:
            # Shootout kicks decide the tie but are not ordinary match shots/xG.
            if details.shootout is True:
                return
            side = TeamSide(event.side)
            self._stats[side].shots += 1
            self._stats[side].shots_on_target += 1
            self._stats[side].xg += details.probability or 0.0
            return

        if event_type is MatchEventType.GOAL and event.side is not None:
            self._stats[TeamSide(event.side)].goals += 1
            # Open-play shots were already counted when the SHOT event started.
            if details.penalty is not True:
                self._stats[TeamSide(event.side)].shots_on_target += 1
            return

        if event_type is MatchEventType.SAVE and actor_side is not None:
            self._stats[actor_side].saves += 1
            if details.penalty is not True:
                shooter_side = self._side_for_agent(event.secondary_agent_id)
                if shooter_side is not None:
                    self._stats[shooter_side].shots_on_target += 1
            return

        if event_type is MatchEventType.TACKLE and actor_side is not None:
            item = self._stats[actor_side]
            item.tackles += 1
            if details.outcome == "defender_control":
                item.successful_tackles += 1
            return

        if event_type is MatchEventType.RECOVERY and event.side is not None:
            self._stats[TeamSide(event.side)].recoveries += 1
            return

        if event_type is MatchEventType.DRIBBLE and actor_side is not None:
            item = self._stats[actor_side]
            item.dribbles += 1
            if details.outcome == "beats_defender":
                item.successful_dribbles += 1
            return

        if event_type is MatchEventType.CROSS and actor_side is not None:
            status = details.status
            outcome = details.outcome
            if status == "attempt":
                self._stats[actor_side].crosses += 1
            elif outcome == "completed":
                self._stats[actor_side].completed_crosses += 1
            return

        if event_type is MatchEventType.FOUL and actor_side is not None:
            self._stats[actor_side].fouls += 1
            return

        if event_type is MatchEventType.CARD and actor_side is not None:
            card = details.card
            if card == "yellow":
                self._stats[actor_side].yellow_cards += 1
            elif card == "second_yellow_red":
                self._stats[actor_side].yellow_cards += 1
                self._stats[actor_side].red_cards += 1
            elif card == "red":
                self._stats[actor_side].red_cards += 1
            return

        if (
            event_type is MatchEventType.RESTART
            and event.restart_type is RestartType.CORNER
            and event.side is not None
        ):
            self._stats[TeamSide(event.side)].corners += 1

    def _side_for_agent(self, agent_id: str | None) -> TeamSide | None:
        if agent_id is None:
            return None
        known = self._agent_side.get(agent_id)
        if known is not None:
            return known
        if agent_id.startswith("home:"):
            return TeamSide.HOME
        if agent_id.startswith("away:"):
            return TeamSide.AWAY
        return None

