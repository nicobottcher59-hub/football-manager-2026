from __future__ import annotations

from dataclasses import replace

from demo_match_factory import build_demo_snapshot
from football_manager.simulation import (
    ActionType,
    PassOutcome,
    PlayerDecision,
    SpatialMatchEngine,
    TeamSide,
    Vector2,
)


def freeze_all(engine: SpatialMatchEngine) -> None:
    for agent in engine.state.players.values():
        engine.set_player_velocity(agent.agent_id, Vector2.zero())


def pass_decision(passer, receiver, action_type: ActionType) -> PlayerDecision:
    return PlayerDecision(
        agent_id=passer.agent_id,
        action_type=action_type,
        target_agent_id=receiver.agent_id,
        utility=80.0,
        considered_options=5,
    )


def label(agent) -> str:
    return agent.slot_id.upper()


def print_profile(passer, receiver, profile) -> None:
    print(
        f"{label(passer)} -> {label(receiver)} | {profile.action_type.value} | "
        f"distance={profile.distance_m:.1f} m"
    )
    print(
        f"  passer pressure={profile.passer_pressure:.2f} | "
        f"execution quality={profile.execution_quality:.1f}/100"
    )
    print(
        f"  ball speed={profile.ball_speed_mps:.1f} m/s | "
        f"target error={profile.target_error_m:.2f} m | "
        f"expected travel={profile.expected_travel_seconds:.2f} s"
    )


def print_result(result) -> None:
    print(f"  RESULT: {result.outcome.value.upper()}")
    if result.interception_agent_id:
        print(f"  Interceptor: {result.interception_agent_id}")
    if result.first_touch_quality is not None:
        print(
            f"  First touch: quality={result.first_touch_quality:.1f}/100 | "
            f"control chance={result.first_touch_probability:.1%}"
        )
    print(f"  Actual travel time: {result.travel_seconds:.2f} s")


def scenario_open_sequence() -> None:
    engine = SpatialMatchEngine(build_demo_snapshot(seed=5300))
    freeze_all(engine)
    cm = engine.state.player_for_slot(TeamSide.HOME, "cm")
    rcm = engine.state.player_for_slot(TeamSide.HOME, "rcm")
    rw = engine.state.player_for_slot(TeamSide.HOME, "rw")
    cm.location = Vector2(38.0, 34.0)
    rcm.location = Vector2(50.0, 28.0)
    rw.location = Vector2(64.0, 18.0)
    for opponent in engine.state.away_players:
        opponent.location = Vector2(90.0, 60.0)
    engine.give_ball_to(cm.agent_id)
    freeze_all(engine)

    print("=" * 88)
    print("SCENARIO A - OPEN BUILD-UP: THE BALL REALLY TRAVELS AND POSSESSION CONTINUES")
    print("=" * 88)

    first = engine.start_pass(pass_decision(cm, rcm, ActionType.SHORT_PASS))
    print_profile(cm, rcm, first.profile)
    start = engine.state.ball.location
    engine.step()
    print(
        f"  After one 0.25 s tick: ball moved from "
        f"({start.x:.1f}, {start.y:.1f}) to "
        f"({engine.state.ball.location.x:.1f}, {engine.state.ball.location.y:.1f})"
    )
    first_result = engine.resolve_active_pass()
    print_result(first_result)

    if first_result.outcome is PassOutcome.COMPLETED:
        second = engine.start_pass(pass_decision(rcm, rw, ActionType.PROGRESSIVE_PASS))
        print()
        print_profile(rcm, rw, second.profile)
        second_result = engine.resolve_active_pass()
        print_result(second_result)
        print(
            f"  Final controlled owner: "
            f"{engine.state.agent(engine.state.ball.owner_agent_id).slot_id.upper()}"
            if engine.state.ball.owner_agent_id
            else "  Final controlled owner: NONE"
        )


def scenario_interception() -> None:
    engine = SpatialMatchEngine(build_demo_snapshot(seed=5303))
    freeze_all(engine)
    cm = engine.state.player_for_slot(TeamSide.HOME, "cm")
    st = engine.state.player_for_slot(TeamSide.HOME, "st")
    blocker = engine.state.player_for_slot(TeamSide.AWAY, "cm")
    cm.location = Vector2(40.0, 34.0)
    st.location = Vector2(65.0, 34.0)
    for opponent in engine.state.away_players:
        opponent.location = Vector2(92.0, 62.0)
    blocker.location = Vector2(52.0, 34.0)
    engine.give_ball_to(cm.agent_id)
    freeze_all(engine)

    print()
    print("=" * 88)
    print("SCENARIO B - FORCED PASS THROUGH A DEFENDER")
    print("=" * 88)
    active = engine.start_pass(pass_decision(cm, st, ActionType.PROGRESSIVE_PASS))
    print_profile(cm, st, active.profile)
    print(
        f"  Defender {blocker.slot_id.upper()} is standing directly in the physical ball path."
    )
    result = engine.resolve_active_pass()
    print_result(result)
    print(
        f"  Possession after action: {engine.state.possession.team_side.value.upper()} | "
        f"owner={engine.state.ball.owner_agent_id}"
    )


def low_first_touch_snapshot():
    snapshot = build_demo_snapshot(seed=301)
    starters = []
    for player in snapshot.home_team.starters:
        if player.assigned_slot_id == "rcm":
            technical = replace(player.attributes.technical, first_touch=1, technique=1)
            mental = replace(player.attributes.mental, composure=1, anticipation=1)
            physical = replace(player.attributes.physical, balance=1)
            player = replace(
                player,
                attributes=replace(
                    player.attributes,
                    technical=technical,
                    mental=mental,
                    physical=physical,
                ),
            )
        starters.append(player)
    return replace(snapshot, home_team=replace(snapshot.home_team, starters=tuple(starters)))


def scenario_bad_control() -> None:
    engine = SpatialMatchEngine(low_first_touch_snapshot())
    freeze_all(engine)
    cm = engine.state.player_for_slot(TeamSide.HOME, "cm")
    rcm = engine.state.player_for_slot(TeamSide.HOME, "rcm")
    marker = engine.state.player_for_slot(TeamSide.AWAY, "cm")
    cm.location = Vector2(40.0, 34.0)
    rcm.location = Vector2(52.0, 34.0)
    for opponent in engine.state.away_players:
        opponent.location = Vector2(92.0, 62.0)
    marker.location = Vector2(52.0, 37.2)
    engine.give_ball_to(cm.agent_id)
    freeze_all(engine)

    print()
    print("=" * 88)
    print("SCENARIO C - PASS ARRIVES, BUT RECEIVER HAS EXTREMELY POOR FIRST TOUCH")
    print("=" * 88)
    print("This is an intentionally extreme debug case to prove reception can fail.")
    active = engine.start_pass(pass_decision(cm, rcm, ActionType.SHORT_PASS))
    print_profile(cm, rcm, active.profile)
    result = engine.resolve_active_pass()
    print_result(result)
    print(
        f"  Ball controlled after action? {'YES' if engine.state.ball.owner_agent_id else 'NO - LOOSE BALL'}"
    )


def main() -> None:
    print("PHASE 5.3 - PASSING & POSSESSION DEBUG")
    scenario_open_sequence()
    scenario_interception()
    scenario_bad_control()


if __name__ == "__main__":
    main()
