from __future__ import annotations

from demo_match_factory import build_demo_snapshot
from football_manager.simulation import SpatialMatchEngine, TeamSide, Vector2


def print_report(engine: SpatialMatchEngine, owner_id: str, title: str) -> None:
    owner = engine.state.agent(owner_id)
    perception = engine.perceive(owner_id)
    options = engine.decision_options(owner_id)

    print("=" * 88)
    print(title)
    print("=" * 88)
    print(
        f"Owner: {owner.slot_id.upper()} | location=({owner.location.x:.1f}, {owner.location.y:.1f}) "
        f"| pressure={perception.pressure:.2f} | local space={perception.local_space:.2f}"
    )
    print(
        f"Goal distance: {perception.goal_distance_m:.1f} m | "
        f"aware teammates={len(perception.teammates)} | opponents={len(perception.opponents)}"
    )

    print("\nBest perceived passing lanes:")
    for lane in sorted(
        perception.passing_lanes,
        key=lambda item: (-(item.lane_openness * item.receiver_space), item.distance_m),
    )[:6]:
        receiver = engine.state.agent(lane.receiver_agent_id)
        print(
            f"  -> {receiver.slot_id.upper():4s}  dist={lane.distance_m:5.1f} m  "
            f"progress={lane.forward_progress_m:6.1f} m  "
            f"lane={lane.lane_openness:4.2f}  receiver-space={lane.receiver_space:4.2f}"
        )

    try:
        striker = engine.state.player_for_slot(TeamSide.HOME, "st")
        striker_lane = perception.lane_to(striker.agent_id)
        print(
            f"\nDirect lane to ST: openness={striker_lane.lane_openness:.2f} "
            f"receiver-space={striker_lane.receiver_space:.2f} "
            f"progress={striker_lane.forward_progress_m:.1f} m"
        )
    except KeyError:
        pass

    print("\nTop decision options (decision only; nothing is executed):")
    for option in options[:8]:
        target = "-"
        if option.target_agent_id is not None:
            target = engine.state.agent(option.target_agent_id).slot_id.upper()
        factors = option.factors
        print(
            f"  {option.action_type.value:17s} target={target:4s} utility={option.utility:5.1f} "
            f"[tac={factors.tactical_fit:4.0f} spatial={factors.spatial_value:4.0f} "
            f"ability={factors.capability:4.0f} decision={factors.decision_quality:4.0f} "
            f"risk={factors.risk:4.0f}]"
        )

    decision = engine.decide(owner_id)
    target = "-"
    if decision.target_agent_id is not None:
        target = engine.state.agent(decision.target_agent_id).slot_id.upper()
    print(
        f"\nSeeded choice: {decision.action_type.value} -> {target} "
        f"(utility={decision.utility:.1f}, options={decision.considered_options})"
    )
    print()


def normal_scenario() -> tuple[SpatialMatchEngine, str]:
    engine = SpatialMatchEngine(build_demo_snapshot(seed=5201))
    engine.set_team_possession(TeamSide.HOME)
    engine.advance_ticks(24)  # six seconds of movement toward the attacking structure
    owner = engine.state.player_for_slot(TeamSide.HOME, "cm")
    engine.give_ball_to(owner.agent_id)
    return engine, owner.agent_id


def pressured_scenario() -> tuple[SpatialMatchEngine, str]:
    engine = SpatialMatchEngine(build_demo_snapshot(seed=5202))
    engine.set_team_possession(TeamSide.HOME)
    engine.advance_ticks(24)
    owner = engine.state.player_for_slot(TeamSide.HOME, "cm")
    engine.give_ball_to(owner.agent_id)

    # Create a deliberately inspectable pressure situation. Two opponents close
    # the midfielder while another sits in the direct lane toward the striker.
    away_cm = engine.state.player_for_slot(TeamSide.AWAY, "cm")
    away_lcm = engine.state.player_for_slot(TeamSide.AWAY, "lcm")
    away_rcm = engine.state.player_for_slot(TeamSide.AWAY, "rcm")
    striker = engine.state.player_for_slot(TeamSide.HOME, "st")
    away_cm.location = owner.location + Vector2(2.2, 0.8)
    away_lcm.location = owner.location + Vector2(3.7, -1.2)
    away_rcm.location = Vector2(
        (owner.location.x + striker.location.x) / 2.0,
        (owner.location.y + striker.location.y) / 2.0,
    )
    return engine, owner.agent_id


def main() -> None:
    print("PHASE 5.2 - PERCEPTION & DECISION MAKING DEBUG")
    print("The engine is choosing intentions only. No pass/dribble/shot is executed yet.\n")

    engine, owner_id = normal_scenario()
    print_report(engine, owner_id, "SCENARIO A - MIDFIELDER IN NORMAL BUILD-UP")

    pressure_engine, pressure_owner_id = pressured_scenario()
    print_report(
        pressure_engine,
        pressure_owner_id,
        "SCENARIO B - SAME TYPE OF PLAYER UNDER HEAVY PRESSURE + BLOCKED CENTRAL LANE",
    )


if __name__ == "__main__":
    main()
