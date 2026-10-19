from __future__ import annotations

from collections import Counter
from dataclasses import replace

from football_manager.domain import MatchDecider
from football_manager.simulation import (
    FlowConfig,
    MatchEventType,
    MatchFlowController,
    MatchPhase,
    RestartType,
    TeamSide,
    Vector2,
)

from demo_match_factory import build_demo_snapshot


def fast_config(*, autonomous_actions: bool = False) -> FlowConfig:
    return FlowConfig(
        regulation_half_seconds=6.0,
        extra_time_half_seconds=3.0,
        decision_cooldown_seconds=0.5,
        loose_ball_collection_seconds=0.5,
        forced_loose_ball_collection_seconds=1.0,
        added_time_unit_seconds=1.0,
        regulation_added_time_cap_seconds=3.0,
        extra_time_added_time_cap_seconds=2.0,
        autonomous_actions=autonomous_actions,
        autonomous_tackles=autonomous_actions,
    )


def with_decider(snapshot, decider: MatchDecider):
    competition = replace(snapshot.context.competition, match_decider=decider)
    return replace(snapshot, context=replace(snapshot.context, competition=competition))


def scenario_regulation_added_time() -> None:
    print("=" * 96)
    print("SCENARIO A - REGULATION MATCH + ADDED TIME")
    print("=" * 96)
    flow = MatchFlowController(build_demo_snapshot(seed=5701), config=fast_config())
    flow.start()
    flow.record_stoppage(2.2)

    while flow.phase is MatchPhase.FIRST_HALF:
        flow.step()
    flow.step()  # start second half
    flow.record_stoppage(1.2)
    result = flow.run_to_completion()

    lifecycle = {
        MatchEventType.PERIOD_START,
        MatchEventType.ADDED_TIME,
        MatchEventType.HALF_TIME,
        MatchEventType.MATCH_END,
    }
    for event in result.events:
        if event.event_type in lifecycle:
            extra = f" ({event.value('seconds')} s added)" if event.event_type is MatchEventType.ADDED_TIME else ""
            print(f"{event.time_label:>6} | {event.event_type.value}{extra}")
    print(f"Final: {result.home_goals}-{result.away_goals} | end={result.end_reason.value}")
    print()


def scenario_extra_time_penalties() -> None:
    print("=" * 96)
    print("SCENARIO B - KNOCKOUT DRAW -> EXTRA TIME -> PENALTIES")
    print("=" * 96)
    snapshot = with_decider(
        build_demo_snapshot(seed=5702),
        MatchDecider.EXTRA_TIME_AND_PENALTIES,
    )
    flow = MatchFlowController(snapshot, config=fast_config())
    result = flow.run_to_completion()

    for event in result.events:
        if event.event_type in {
            MatchEventType.EXTRA_TIME,
            MatchEventType.PERIOD_START,
            MatchEventType.PENALTY_SHOOTOUT,
            MatchEventType.MATCH_END,
        }:
            print(f"{event.time_label:>6} | {event.event_type.value}")

    kicks = [event for event in result.events if event.event_type is MatchEventType.PENALTY_KICK]
    print(f"Shootout kicks: {len(kicks)}")
    print(
        f"Penalties: HOME {result.penalties_home}-{result.penalties_away} AWAY | "
        f"winner={result.winner.value if result.winner else '-'}"
    )
    print()


def scenario_restarts() -> None:
    print("=" * 96)
    print("SCENARIO C - BASIC DEAD-BALL RESTARTS")
    print("=" * 96)
    flow = MatchFlowController(build_demo_snapshot(seed=5703), config=fast_config())
    flow.start()

    flow.award_restart(RestartType.THROW_IN, TeamSide.HOME, location=Vector2(58.0, 0.0))
    throw = flow.events[-1]
    print(
        f"Throw-in -> side={throw.side.value} | taker={throw.actor_agent_id} | "
        f"ball=({flow.engine.state.ball.location.x:.1f},{flow.engine.state.ball.location.y:.1f})"
    )

    flow.award_restart(RestartType.CORNER, TeamSide.HOME, location=Vector2(105.0, 68.0))
    corner = flow.events[-1]
    print(
        f"Corner   -> side={corner.side.value} | taker={corner.actor_agent_id} | "
        f"ball=({flow.engine.state.ball.location.x:.1f},{flow.engine.state.ball.location.y:.1f})"
    )

    flow.award_restart(RestartType.GOAL_KICK, TeamSide.AWAY)
    goal_kick = flow.events[-1]
    print(
        f"Goal kick-> side={goal_kick.side.value} | taker={goal_kick.actor_agent_id} | "
        f"ball=({flow.engine.state.ball.location.x:.1f},{flow.engine.state.ball.location.y:.1f})"
    )

    offender = flow.engine.state.player_for_slot(TeamSide.AWAY, "cm")
    victim = flow.engine.state.player_for_slot(TeamSide.HOME, "cm")
    flow.register_foul(offender.agent_id, victim.agent_id)
    print(
        f"Foul     -> offender={offender.slot_id} | free kick side={flow.events[-1].side.value}"
    )
    print()


def scenario_autonomous_sequence() -> None:
    print("=" * 96)
    print("SCENARIO D - AUTONOMOUS MATCH FLOW (ACCELERATED DEBUG CLOCK)")
    print("=" * 96)
    flow = MatchFlowController(
        build_demo_snapshot(seed=5704),
        config=fast_config(autonomous_actions=True),
    )
    result = flow.run_to_completion()
    counts = Counter(event.event_type.value for event in result.events)
    print(f"Final: HOME {result.home_goals}-{result.away_goals} AWAY")
    print(
        "Events: "
        f"passes={counts['pass']} | carries={counts['carry']} | dribbles={counts['dribble']} | "
        f"crosses={counts['cross']} | shots={counts['shot']} | tackles={counts['tackle']} | "
        f"fouls={counts['foul']}"
    )
    print(f"Structured events emitted: {len(result.events)}")
    print("This scenario validates orchestration, not final statistical realism; calibration is Phase 5.10.")


if __name__ == "__main__":
    print("PHASE 5.7 - MATCH FLOW DEBUG")
    print()
    scenario_regulation_added_time()
    scenario_extra_time_penalties()
    scenario_restarts()
    scenario_autonomous_sequence()
