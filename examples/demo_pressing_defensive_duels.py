from __future__ import annotations

from dataclasses import replace

from demo_match_factory import build_demo_snapshot
from football_manager.domain import ForceDirection, Level, MarkingStyle, PressingScheme
from football_manager.simulation import SpatialMatchEngine, TeamSide, Vector2


def with_away_defence(snapshot, **changes):
    team = snapshot.away_team
    instructions = team.tactic.team_instructions
    out = replace(instructions.out_of_possession, **changes)
    tactic = replace(
        team.tactic,
        team_instructions=replace(instructions, out_of_possession=out),
    )
    return replace(snapshot, away_team=replace(team, tactic=tactic))


def arrange_press(engine: SpatialMatchEngine):
    carrier = engine.state.player_for_slot(TeamSide.HOME, "cm")
    carrier.location = Vector2(50.0, 34.0)
    for slot, location in {
        "cm": Vector2(56.0, 34.0),
        "rcm": Vector2(58.0, 29.0),
        "lcm": Vector2(58.0, 39.0),
        "st": Vector2(60.0, 34.0),
    }.items():
        engine.state.player_for_slot(TeamSide.AWAY, slot).location = location
    for slot in ("rb", "rcb", "lcb", "lb", "rw", "lw"):
        engine.state.player_for_slot(TeamSide.AWAY, slot).location = Vector2(92.0, 62.0)
    engine.give_ball_to(carrier.agent_id)
    engine.set_player_velocity(carrier.agent_id, Vector2.zero())
    return carrier


def scenario_pressing_intensity() -> None:
    low_snapshot = with_away_defence(
        build_demo_snapshot(seed=5401),
        pressing_intensity=Level.VERY_LOW,
        pressing_scheme=PressingScheme.STANDARD,
    )
    high_snapshot = with_away_defence(
        build_demo_snapshot(seed=5401),
        pressing_intensity=Level.VERY_HIGH,
        pressing_scheme=PressingScheme.STANDARD,
    )
    low = SpatialMatchEngine(low_snapshot)
    high = SpatialMatchEngine(high_snapshot)
    low_carrier = arrange_press(low)
    high_carrier = arrange_press(high)

    low_plan = low.pressing_plan(TeamSide.AWAY)
    high_plan = high.pressing_plan(TeamSide.AWAY)

    print("=" * 92)
    print("SCENARIO A - SAME POSITION, DIFFERENT TEAM PRESSING INTENSITY")
    print("=" * 92)
    print(f"Ball carrier: HOME CM at ({high_carrier.location.x:.1f}, {high_carrier.location.y:.1f})")
    print(f"VERY LOW press -> {len(low_plan.pressing_assignments)} active presser(s)")
    print(f"VERY HIGH press -> {len(high_plan.pressing_assignments)} active presser(s)")
    print("High-press assignments:")
    for assignment in high_plan.pressing_assignments:
        slot = high.state.agent(assignment.defender_agent_id).slot_id.upper()
        print(
            f"  {slot:4s} distance={assignment.distance_m:4.1f} m | "
            f"closing speed={assignment.closing_speed_mps:4.1f} m/s | "
            f"primary={'YES' if assignment.primary else 'NO'}"
        )

    primary = high_plan.primary
    assert primary is not None
    primary_player = high.state.agent(primary.defender_agent_id)
    before = primary_player.location.distance_to(high_carrier.location)
    high.advance_ticks(8)  # 2.0 seconds using the normal 0.25 s simulation path.
    after = primary_player.location.distance_to(high_carrier.location)
    print(f"Primary presser distance after 2.0 s: {before:.2f} m -> {after:.2f} m")


def scenario_force_direction_and_coverage() -> None:
    snapshot = with_away_defence(
        build_demo_snapshot(seed=5403),
        pressing_intensity=Level.HIGH,
        pressing_scheme=PressingScheme.STANDARD,
        force_direction=ForceDirection.OUTSIDE,
        marking_style=MarkingStyle.MAN,
    )
    engine = SpatialMatchEngine(snapshot)
    carrier = engine.state.player_for_slot(TeamSide.HOME, "cm")
    carrier.location = Vector2(50.0, 15.0)
    engine.state.player_for_slot(TeamSide.AWAY, "cm").location = Vector2(57.0, 15.0)
    engine.state.player_for_slot(TeamSide.HOME, "st").location = Vector2(62.0, 25.0)
    engine.state.player_for_slot(TeamSide.HOME, "lw").location = Vector2(59.0, 8.0)
    engine.give_ball_to(carrier.agent_id)

    plan = engine.pressing_plan(TeamSide.AWAY)
    primary = plan.primary
    assert primary is not None

    print()
    print("=" * 92)
    print("SCENARIO B - PRESS ANGLE + DEFENSIVE COVERAGE")
    print("=" * 92)
    print(
        f"Carrier is wide at y={carrier.location.y:.1f}. Force direction=OUTSIDE means "
        "the primary presser approaches from the central side."
    )
    print(
        f"Primary approach target: ({primary.approach_target.x:.1f}, "
        f"{primary.approach_target.y:.1f})"
    )
    print("Coverage assignments behind/around the press:")
    for assignment in plan.coverage_assignments:
        defender = engine.state.agent(assignment.defender_agent_id).slot_id.upper()
        target = engine.state.agent(assignment.target_agent_id).slot_id.upper()
        print(
            f"  {defender:4s} covers {target:4s} | "
            f"marking strength={assignment.marking_strength:.2f} | "
            f"target=({assignment.target_location.x:.1f}, {assignment.target_location.y:.1f})"
        )


def scenario_tackle_and_broken_press() -> None:
    engine = SpatialMatchEngine(build_demo_snapshot(seed=5404))
    carrier = engine.state.player_for_slot(TeamSide.HOME, "cm")
    defender = engine.state.player_for_slot(TeamSide.AWAY, "cm")
    carrier.location = Vector2(50.0, 34.0)
    defender.location = Vector2(51.0, 34.0)
    for agent in engine.state.players.values():
        if agent.agent_id not in {carrier.agent_id, defender.agent_id}:
            agent.location = Vector2(90.0, 62.0) if agent.side is TeamSide.AWAY else Vector2(15.0, 8.0)
    engine.give_ball_to(carrier.agent_id)
    for agent in engine.state.players.values():
        engine.set_player_velocity(agent.agent_id, Vector2.zero())

    profile = engine.defensive_duel_profile(defender.agent_id)
    result = engine.attempt_tackle(defender.agent_id)

    print()
    print("=" * 92)
    print("SCENARIO C - TACKLE IS A SEPARATE DUEL, NOT AN AUTOMATIC STEAL")
    print("=" * 92)
    print(
        f"Defender quality={profile.defender_quality:.1f} | "
        f"attacker resistance={profile.attacker_resistance:.1f} | "
        f"support={profile.support:.2f}"
    )
    print(
        f"Tackle willingness={profile.tackle_willingness:.1f}/100 | "
        f"success chance={profile.success_probability:.1%} | "
        f"clean-control chance after winning={profile.clean_control_probability:.1%}"
    )
    print(f"Seeded duel result: {result.outcome.value.upper()}")
    print(f"Possession after duel: {engine.state.possession.team_side.value.upper() if engine.state.possession.team_side else 'LOOSE BALL'}")

    broken_snapshot = with_away_defence(
        build_demo_snapshot(seed=5405),
        pressing_intensity=Level.VERY_LOW,
        pressing_scheme=PressingScheme.STANDARD,
    )
    broken = SpatialMatchEngine(broken_snapshot)
    runner = broken.state.player_for_slot(TeamSide.HOME, "cm")
    presser = broken.state.player_for_slot(TeamSide.AWAY, "cm")
    runner.location = Vector2(50.0, 34.0)
    presser.location = Vector2(52.0, 34.0)
    for agent in broken.state.away_players:
        if agent.agent_id != presser.agent_id:
            agent.location = Vector2(95.0, 62.0)
    broken.give_ball_to(runner.agent_id)
    plan = broken.pressing_plan(TeamSide.AWAY)
    runner.location = Vector2(59.0, 34.0)
    broken.state.ball.location = runner.location
    print(f"Carrier manually moved beyond the primary presser -> press broken? {broken.press_is_broken(plan)}")


def main() -> None:
    print("PHASE 5.4 - PRESSING & DEFENSIVE DUELS DEBUG")
    scenario_pressing_intensity()
    scenario_force_direction_and_coverage()
    scenario_tackle_and_broken_press()


if __name__ == "__main__":
    main()
