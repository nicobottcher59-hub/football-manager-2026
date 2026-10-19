from __future__ import annotations

from dataclasses import replace

from demo_match_factory import build_demo_snapshot
from football_manager.presentation import (
    CommentaryDensity,
    CommentaryFormatter,
    MatchPlaybackSession,
    PlaybackSpeed,
)
from football_manager.simulation import FlowConfig


def _config() -> FlowConfig:
    # Short periods keep this a fast orchestration demo. The GUI uses normal match time.
    return FlowConfig(
        regulation_half_seconds=8.0,
        extra_time_half_seconds=3.0,
        decision_cooldown_seconds=0.5,
        loose_ball_collection_seconds=0.5,
        forced_loose_ball_collection_seconds=1.0,
        added_time_unit_seconds=1.0,
        regulation_added_time_cap_seconds=2.0,
        extra_time_added_time_cap_seconds=1.0,
    )


def _signature(session: MatchPlaybackSession):
    result = session.result
    assert result is not None
    return (
        result.home_goals,
        result.away_goals,
        result.penalties_home,
        result.penalties_away,
        result.end_reason,
        tuple((event.event_type, event.actor_agent_id, event.data) for event in result.events),
    )


def main() -> None:
    snapshot = build_demo_snapshot(seed=5901)
    sessions: dict[str, MatchPlaybackSession] = {}

    for label, speed in (("x1", PlaybackSpeed.X1), ("x2", PlaybackSpeed.X2), ("x4", PlaybackSpeed.X4)):
        session = MatchPlaybackSession(snapshot, flow_config=_config())
        session.set_speed(speed)
        while not session.is_finished:
            session.advance_pulse(base_ticks=1)
        sessions[label] = session

    instant = MatchPlaybackSession(snapshot, flow_config=_config())
    instant.run_instant(batch_ticks=64)
    sessions["instant"] = instant

    reference = _signature(sessions["x1"])
    print("PHASE 5.9 - OUTPUT & PLAYBACK DEBUG")
    print("=" * 88)
    for label, session in sessions.items():
        result = session.result
        assert result is not None
        print(
            f"{label:>7}: {result.home_goals}-{result.away_goals} | "
            f"events={len(result.events):4d} | identical={_signature(session) == reference}"
        )

    print("\n" + "=" * 88)
    print("DETAILED COMMENTARY SAMPLE")
    print("=" * 88)
    formatter = CommentaryFormatter(snapshot, density=CommentaryDensity.DETAILED)
    lines = [
        line
        for event in sessions["instant"].result.events
        if (line := formatter.format_event(event)) is not None
    ]
    for line in lines[:20]:
        print(line)

    stats = sessions["instant"].stats
    print("\n" + "=" * 88)
    print("LIVE STATS SNAPSHOT")
    print("=" * 88)
    print(
        f"HOME possession={stats.home.possession_pct:.1f}% | "
        f"passes={stats.home.passes_completed}/{stats.home.passes_attempted} | "
        f"shots={stats.home.shots} | xG={stats.home.xg:.2f}"
    )
    print(
        f"AWAY possession={stats.away.possession_pct:.1f}% | "
        f"passes={stats.away.passes_completed}/{stats.away.passes_attempted} | "
        f"shots={stats.away.shots} | xG={stats.away.xg:.2f}"
    )


if __name__ == "__main__":
    main()
