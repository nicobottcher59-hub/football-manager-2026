from __future__ import annotations

from dataclasses import replace

from football_manager.domain import InPossessionPosition, Level, PlayerInstructions
from football_manager.simulation import (
    ActionType,
    PlayerDecision,
    SpatialMatchEngine,
    TeamSide,
    Vector2,
)

from demo_match_factory import build_demo_snapshot


def decision(agent, action: ActionType, target=None) -> PlayerDecision:
    return PlayerDecision(
        agent_id=agent.agent_id,
        action_type=action,
        target_agent_id=target.agent_id if target is not None else None,
        utility=80.0,
        considered_options=8,
    )


def freeze(engine: SpatialMatchEngine) -> None:
    for agent in engine.state.players.values():
        engine.set_player_velocity(agent.agent_id, Vector2.zero())


def with_player_instructions(snapshot, side: TeamSide, slot_id: str, **changes):
    team = snapshot.home_team if side is TeamSide.HOME else snapshot.away_team

    def transform(player):
        if player.assigned_slot_id != slot_id:
            return player
        base = player.effective_instructions or PlayerInstructions()
        return replace(player, effective_instructions=replace(base, **changes))

    team = replace(team, starters=tuple(transform(player) for player in team.starters))
    return replace(snapshot, home_team=team) if side is TeamSide.HOME else replace(snapshot, away_team=team)


def with_home_overlap(snapshot, level: Level):
    team = snapshot.home_team
    instructions = team.tactic.team_instructions
    in_possession = replace(instructions.in_possession, overlap_frequency=level)
    tactic = replace(
        team.tactic,
        team_instructions=replace(instructions, in_possession=in_possession),
    )
    return replace(snapshot, home_team=replace(team, tactic=tactic))


def scenario_carry() -> None:
    print("=" * 92)
    print("SCENARIO A - CONTROLLED CARRY INTO OPEN SPACE")
    print("=" * 92)
    engine = SpatialMatchEngine(build_demo_snapshot(seed=5505))
    freeze(engine)
    carrier = engine.state.player_for_slot(TeamSide.HOME, "cm")
    carrier.location = Vector2(42.0, 34.0)
    for opponent in engine.state.away_players:
        opponent.location = Vector2(95.0, 62.0)
    engine.give_ball_to(carrier.agent_id)
    freeze(engine)

    start = carrier.location
    active = engine.start_carry(decision(carrier, ActionType.CARRY))
    result = engine.resolve_active_carry()

    print(f"Carrier: CM | origin=({start.x:.1f}, {start.y:.1f})")
    print(
        f"Target=({active.profile.target.x:.1f}, {active.profile.target.y:.1f}) | "
        f"distance={active.profile.distance_m:.1f} m | speed={active.profile.speed_mps:.1f} m/s"
    )
    print(
        f"Control quality={active.profile.control_quality:.1f}/100 | "
        f"retain probability={active.profile.retain_probability * 100:.1f}%"
    )
    print(
        f"Result={result.outcome.value.upper()} | final=({carrier.location.x:.1f}, {carrier.location.y:.1f}) | "
        f"covered={result.distance_covered_m:.1f} m"
    )
    print()


def scenario_runs() -> None:
    print("=" * 92)
    print("SCENARIO B - OFF-BALL RUNS + OVERLAP / UNDERLAP LOGIC")
    print("=" * 92)
    snapshot = build_demo_snapshot(seed=5512)
    snapshot = with_home_overlap(snapshot, Level.VERY_HIGH)
    snapshot = with_player_instructions(
        snapshot,
        TeamSide.HOME,
        "lw",
        in_possession_position=InPossessionPosition.INSIDE,
        forward_runs=Level.HIGH,
        attack_space=Level.HIGH,
    )
    engine = SpatialMatchEngine(snapshot)
    carrier = engine.state.player_for_slot(TeamSide.HOME, "cm")
    engine.give_ball_to(carrier.agent_id)

    runs = engine.off_ball_run_plan(TeamSide.HOME, max_runners=10)
    for run in runs:
        runner = engine.state.agent(run.runner_agent_id)
        if runner.slot_id in {"lb", "lw", "st", "rw"}:
            print(
                f"{runner.slot_id.upper():3s} -> {run.run_type.value:9s} | "
                f"({run.origin.x:4.1f},{run.origin.y:4.1f}) -> ({run.target.x:4.1f},{run.target.y:4.1f}) | "
                f"priority={run.priority:4.1f}"
            )
    lb_run = next(run for run in runs if engine.state.agent(run.runner_agent_id).slot_id == "lb")
    print(f"\nLB run type with LW moving inside + VERY HIGH overlap: {lb_run.run_type.value.upper()}")
    print()


def scenario_dribble() -> None:
    print("=" * 92)
    print("SCENARIO C - ONE-ON-ONE DRIBBLE")
    print("=" * 92)
    engine = SpatialMatchEngine(build_demo_snapshot(seed=2))
    freeze(engine)
    attacker = engine.state.player_for_slot(TeamSide.HOME, "cm")
    defender = engine.state.player_for_slot(TeamSide.AWAY, "cm")
    attacker.location = Vector2(50.0, 34.0)
    defender.location = Vector2(53.0, 34.0)
    for opponent in engine.state.away_players:
        if opponent.agent_id != defender.agent_id:
            opponent.location = Vector2(96.0, 62.0)
    engine.give_ball_to(attacker.agent_id)
    freeze(engine)

    profile = engine.dribble_profile(attacker.agent_id)
    start = attacker.location
    result = engine.attempt_dribble(decision(attacker, ActionType.DRIBBLE))

    print(
        f"Attacker quality={profile.attacker_quality:.1f} | defender quality={profile.defender_quality:.1f} | "
        f"success chance={profile.success_probability * 100:.1f}%"
    )
    print(f"Seeded result: {result.outcome.value.upper()}")
    if engine.active_carry is not None:
        engine.advance_ticks(6)
        print(
            f"Successful dribble creates an escape carry: "
            f"({start.x:.1f},{start.y:.1f}) -> ({attacker.location.x:.1f},{attacker.location.y:.1f}) after 1.5 s"
        )
    print()


def scenario_cutback() -> None:
    print("=" * 92)
    print("SCENARIO D - BYLINE CROSS BECOMES A REAL CUTBACK")
    print("=" * 92)
    engine = SpatialMatchEngine(build_demo_snapshot(seed=1))
    freeze(engine)
    crosser = engine.state.player_for_slot(TeamSide.HOME, "rw")
    striker = engine.state.player_for_slot(TeamSide.HOME, "st")
    crosser.location = Vector2(94.0, 8.0)
    striker.location = Vector2(91.0, 34.0)
    for teammate in engine.state.home_players:
        if teammate.agent_id not in {crosser.agent_id, striker.agent_id}:
            teammate.location = Vector2(40.0, 55.0)
    for opponent in engine.state.away_players:
        opponent.location = Vector2(20.0, 62.0)
    engine.give_ball_to(crosser.agent_id)
    freeze(engine)

    active = engine.start_cross(decision(crosser, ActionType.CROSS, striker))
    print(
        f"Cross type={active.profile.cross_type.value.upper()} | distance={active.profile.distance_m:.1f} m | "
        f"speed={active.profile.ball_speed_mps:.1f} m/s | max height={active.profile.max_height_m:.2f} m"
    )
    engine.step()
    print(
        f"After first 0.25 s tick: ball=({engine.state.ball.location.x:.1f}, {engine.state.ball.location.y:.1f}) | "
        f"height={engine.state.ball.height_m:.2f} m"
    )
    result = engine.resolve_active_cross()
    print(
        f"Result={result.outcome.value.upper()} | intended receiver=ST | "
        f"controller={result.controller_agent_id or '-'}"
    )
    print()


def main() -> None:
    print("PHASE 5.5 - BALL PROGRESSION DEBUG\n")
    scenario_carry()
    scenario_runs()
    scenario_dribble()
    scenario_cutback()


if __name__ == "__main__":
    main()
