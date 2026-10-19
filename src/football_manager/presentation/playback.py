from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum

from football_manager.domain import MatchSnapshot
from football_manager.simulation import FlowConfig, MatchEvent, MatchFlowController, MatchResult

from .statistics import MatchStatistics, MatchStatisticsTracker


class PlaybackSpeed(IntEnum):
    X1 = 1
    X2 = 2
    X4 = 4


@dataclass(frozen=True, slots=True)
class PlaybackAdvance:
    ticks_advanced: int
    events: tuple[MatchEvent, ...]
    finished: bool


class MatchPlaybackSession:
    """Presentation runner over the one and only MatchFlowController.

    x1/x2/x4 only change how many fixed simulation ticks are consumed per UI
    pulse. Instant result repeatedly consumes the same fixed-step path without
    waiting or rendering. No alternative result engine exists here.
    """

    def __init__(
        self,
        snapshot: MatchSnapshot,
        *,
        flow_config: FlowConfig | None = None,
    ) -> None:
        self.snapshot = snapshot
        self.flow = MatchFlowController(snapshot, config=flow_config)
        self.statistics = MatchStatisticsTracker(snapshot)
        self.speed = PlaybackSpeed.X1

    @property
    def result(self) -> MatchResult | None:
        return self.flow.result

    @property
    def is_finished(self) -> bool:
        return self.flow.is_finished

    @property
    def stats(self) -> MatchStatistics:
        return self.statistics.snapshot(self.flow.score)

    def set_speed(self, speed: PlaybackSpeed | int) -> None:
        self.speed = PlaybackSpeed(speed)

    def advance_pulse(self, *, base_ticks: int = 1) -> PlaybackAdvance:
        if base_ticks <= 0:
            raise ValueError("base_ticks must be positive")
        return self.advance_ticks(base_ticks * int(self.speed))

    def advance_ticks(self, ticks: int) -> PlaybackAdvance:
        """Consume exactly `ticks` fixed simulation ticks when possible.

        Phase transitions and penalty-shootout orchestration can consume a flow
        iteration without advancing the spatial clock; those transitions are still
        processed, but they do not count against the requested fixed ticks.
        """

        if ticks < 0:
            raise ValueError("ticks must be non-negative")
        if ticks == 0 or self.flow.is_finished:
            return PlaybackAdvance(0, (), self.flow.is_finished)

        start_event_index = len(self.flow.events)
        advanced = 0
        transition_guard = 0

        while advanced < ticks and not self.flow.is_finished:
            before_tick = self.flow.engine.state.clock.tick_count
            self.flow.step()
            after_tick = self.flow.engine.state.clock.tick_count
            delta = after_tick - before_tick
            if delta < 0 or delta > 1:
                raise RuntimeError("match flow advanced an unexpected number of fixed ticks")
            if delta == 0:
                transition_guard += 1
                if transition_guard > 32:
                    raise RuntimeError("match flow is stuck in zero-tick transitions")
            else:
                transition_guard = 0
                advanced += delta
                self.statistics.observe_possession(
                    self.flow.engine.state.possession.team_side,
                    delta,
                )

        events = tuple(self.flow.events[start_event_index:])
        self.statistics.consume(events)
        return PlaybackAdvance(advanced, events, self.flow.is_finished)

    def request_substitution(
        self,
        side,
        outgoing_agent_id: str,
        incoming_player_id: str,
    ) -> bool:
        start = len(self.flow.events)
        immediate = self.flow.request_substitution(side, outgoing_agent_id, incoming_player_id)
        self.statistics.consume(self.flow.events[start:])
        return immediate

    def make_substitution(
        self,
        side,
        outgoing_agent_id: str,
        incoming_player_id: str,
    ) -> str:
        start = len(self.flow.events)
        new_agent_id = self.flow.make_substitution(side, outgoing_agent_id, incoming_player_id)
        self.statistics.consume(self.flow.events[start:])
        return new_agent_id

    def apply_runtime_tactic(self, side, tactic, *, label: str | None = None) -> None:
        start = len(self.flow.events)
        self.flow.apply_runtime_tactic(side, tactic, label=label)
        self.statistics.consume(self.flow.events[start:])

    def run_instant(self, *, batch_ticks: int = 256) -> PlaybackAdvance:
        if batch_ticks <= 0:
            raise ValueError("batch_ticks must be positive")
        start_event_index = len(self.flow.events)
        total_ticks = 0
        while not self.flow.is_finished:
            advance = self.advance_ticks(batch_ticks)
            total_ticks += advance.ticks_advanced
        return PlaybackAdvance(
            ticks_advanced=total_ticks,
            events=tuple(self.flow.events[start_event_index:]),
            finished=True,
        )
