from __future__ import annotations

from dataclasses import replace

from football_manager.domain import GoalkeepingAttributes
from football_manager.simulation import (
    ActionType,
    ChanceOrigin,
    PlayerDecision,
    ShotBodyPart,
    ShotOutcome,
    SpatialMatchEngine,
    TeamSide,
    Vector2,
)

from demo_match_factory import build_demo_snapshot


def decision(agent) -> PlayerDecision:
    return PlayerDecision(
        agent_id=agent.agent_id,
        action_type=ActionType.SHOOT,
        target_agent_id=None,
        utility=85.0,
        considered_options=8,
    )


def freeze(engine: SpatialMatchEngine) -> None:
    for agent in engine.state.players.values():
        engine.set_player_velocity(agent.agent_id, Vector2.zero())


def replace_starter(snapshot, side: TeamSide, slot_id: str, transform):
    team = snapshot.home_team if side is TeamSide.HOME else snapshot.away_team
    starters = tuple(
        transform(player) if player.assigned_slot_id == slot_id else player
        for player in team.starters
    )
    team = replace(team, starters=starters)
    return replace(snapshot, home_team=team) if side is TeamSide.HOME else replace(snapshot, away_team=team)


def with_finisher(snapshot, quality: int):
    def transform(player):
        technical = replace(
            player.attributes.technical,
            finishing=quality,
            long_shots=quality,
            technique=quality,
            shot_power=quality,
        )
        mental = replace(player.attributes.mental, composure=quality, decisions=quality)
        return replace(
            player,
            attributes=replace(player.attributes, technical=technical, mental=mental),
        )

    return replace_starter(snapshot, TeamSide.HOME, "st", transform)


def with_goalkeeper(snapshot, quality: int):
    def transform(player):
        attributes = GoalkeepingAttributes(
            reflexes=quality,
            handling=quality,
            one_on_ones=quality,
            aerial_reach=quality,
            command_of_area=quality,
            kicking=quality,
            throwing=quality,
            goalkeeper_positioning=quality,
        )
        return replace(
            player,
            attributes=replace(player.attributes, goalkeeping=attributes),
        )

    return replace_starter(snapshot, TeamSide.AWAY, "gk", transform)


def setup(snapshot, shooter_location=Vector2(88.0, 34.0), goalkeeper_location=Vector2(103.5, 34.0)):
    engine = SpatialMatchEngine(snapshot)
    freeze(engine)
    shooter = engine.state.player_for_slot(TeamSide.HOME, "st")
    goalkeeper = engine.state.player_for_slot(TeamSide.AWAY, "gk")
    shooter.location = shooter_location
    goalkeeper.location = goalkeeper_location
    for opponent in engine.state.away_players:
        if opponent.agent_id != goalkeeper.agent_id:
            opponent.location = Vector2(35.0, 62.0)
    engine.give_ball_to(shooter.agent_id)
    freeze(engine)
    return engine, shooter, goalkeeper


def scenario_xg_vs_finishing() -> None:
    print("=" * 96)
    print("SCENARIO A - SAME CHANCE, DIFFERENT FINISHER QUALITY")
    print("=" * 96)
    poor, poor_shooter, _ = setup(with_finisher(build_demo_snapshot(seed=5615), 25))
    elite, elite_shooter, _ = setup(with_finisher(build_demo_snapshot(seed=5615), 95))
    poor_profile = poor.start_shot(decision(poor_shooter)).profile
    elite_profile = elite.start_shot(decision(elite_shooter)).profile

    print(
        f"Poor finisher -> xG={poor_profile.xg:.3f} | execution={poor_profile.execution_quality:.1f}/100 | "
        f"target error={poor_profile.target_error_m:.2f} m"
    )
    print(
        f"Elite finisher -> xG={elite_profile.xg:.3f} | execution={elite_profile.execution_quality:.1f}/100 | "
        f"target error={elite_profile.target_error_m:.2f} m"
    )
    print("xG stays the same because the chance is the same; finishing changes execution, not chance quality.")
    print()


def scenario_chance_quality() -> None:
    print("=" * 96)
    print("SCENARIO B - LOCATION / ANGLE / PRESSURE CHANGE CHANCE QUALITY")
    print("=" * 96)
    close, close_shooter, _ = setup(build_demo_snapshot(seed=5620), Vector2(94.0, 34.0))
    far, far_shooter, _ = setup(build_demo_snapshot(seed=5620), Vector2(73.0, 34.0))
    wide, wide_shooter, _ = setup(build_demo_snapshot(seed=5620), Vector2(88.0, 9.0))
    pressured, pressured_shooter, _ = setup(build_demo_snapshot(seed=5620), Vector2(88.0, 34.0))
    marker = pressured.state.player_for_slot(TeamSide.AWAY, "cm")
    marker.location = pressured_shooter.location + Vector2(0.0, 3.0)

    close_p = close.start_shot(decision(close_shooter)).profile
    far_p = far.start_shot(decision(far_shooter)).profile
    wide_p = wide.start_shot(decision(wide_shooter)).profile
    pressure_p = pressured.start_shot(decision(pressured_shooter)).profile

    print(f"Close central chance : distance={close_p.distance_m:4.1f} m | xG={close_p.xg:.3f}")
    print(f"Long-range chance   : distance={far_p.distance_m:4.1f} m | xG={far_p.xg:.3f}")
    print(f"Wide-angle chance   : distance={wide_p.distance_m:4.1f} m | xG={wide_p.xg:.3f}")
    print(f"Pressured chance    : pressure={pressure_p.pressure:.2f} | xG={pressure_p.xg:.3f}")
    print()


def scenario_goalkeeper() -> None:
    print("=" * 96)
    print("SCENARIO C - GOALKEEPER QUALITY AFFECTS THE SAVE, NOT THE CHANCE xG")
    print("=" * 96)
    weak, weak_shooter, _ = setup(with_goalkeeper(build_demo_snapshot(seed=5622), 25))
    elite, elite_shooter, _ = setup(with_goalkeeper(build_demo_snapshot(seed=5622), 95))
    weak_p = weak.start_shot(decision(weak_shooter)).profile
    elite_p = elite.start_shot(decision(elite_shooter)).profile
    weak_save = weak.shooting.save_probability(weak.state, weak_p)
    elite_save = elite.shooting.save_probability(elite.state, elite_p)

    print(f"Weak GK  -> xG={weak_p.xg:.3f} | GK quality={weak_p.goalkeeper_quality:.1f} | save chance={weak_save*100:.1f}%")
    print(f"Elite GK -> xG={elite_p.xg:.3f} | GK quality={elite_p.goalkeeper_quality:.1f} | save chance={elite_save*100:.1f}%")
    print("The same shot situation keeps the same xG; the goalkeeper gets a separate save resolution.")
    print()


def scenario_real_shot_flight() -> None:
    print("=" * 96)
    print("SCENARIO D - REAL SHOT FLIGHT + GOALKEEPER REACTION")
    print("=" * 96)
    engine, shooter, goalkeeper = setup(build_demo_snapshot(seed=5602))
    start_gk = goalkeeper.location
    active = engine.start_shot(decision(shooter))
    print(
        f"Shot: distance={active.profile.distance_m:.1f} m | speed={active.profile.shot_speed_mps:.1f} m/s | "
        f"xG={active.profile.xg:.3f}"
    )
    engine.step()
    print(
        f"After 0.25 s -> ball=({engine.state.ball.location.x:.1f},{engine.state.ball.location.y:.1f}) "
        f"height={engine.state.ball.height_m:.2f} m | GK=({goalkeeper.location.x:.1f},{goalkeeper.location.y:.1f})"
    )
    result = engine.resolve_active_shot()
    print(
        f"Result={result.outcome.value.upper()} | on target={result.on_target} | "
        f"GK moved {start_gk.distance_to(goalkeeper.location):.2f} m"
    )
    print()


def scenario_block_and_header() -> None:
    print("=" * 96)
    print("SCENARIO E - SHOT BLOCK + HEADER MODEL")
    print("=" * 96)
    blocked, shooter, _ = setup(build_demo_snapshot(seed=5600), Vector2(84.0, 34.0))
    blocker = blocked.state.player_for_slot(TeamSide.AWAY, "cm")
    active = blocked.start_shot(decision(shooter))
    blocker.location = active.profile.origin + (active.profile.actual_target - active.profile.origin).scale(0.40)
    result = blocked.resolve_active_shot()
    print(
        f"Block example -> result={result.outcome.value.upper()} | blocker={result.blocker_agent_id} | "
        f"rebound=({result.rebound_location.x:.1f},{result.rebound_location.y:.1f})"
    )

    foot, foot_shooter, _ = setup(build_demo_snapshot(seed=5617), Vector2(93.0, 34.0))
    head, head_shooter, _ = setup(build_demo_snapshot(seed=5617), Vector2(93.0, 34.0))
    foot_p = foot.start_shot(decision(foot_shooter), body_part=ShotBodyPart.FOOT).profile
    head_p = head.start_shot(
        decision(head_shooter),
        body_part=ShotBodyPart.HEAD,
        chance_origin=ChanceOrigin.CROSS,
    ).profile
    print(
        f"Same location -> foot xG={foot_p.xg:.3f}, speed={foot_p.shot_speed_mps:.1f} m/s | "
        f"header xG={head_p.xg:.3f}, speed={head_p.shot_speed_mps:.1f} m/s"
    )
    print()


def main() -> None:
    print("PHASE 5.6 - CHANCES, SHOOTING & GOALKEEPERS DEBUG\n")
    scenario_xg_vs_finishing()
    scenario_chance_quality()
    scenario_goalkeeper()
    scenario_real_shot_flight()
    scenario_block_and_header()


if __name__ == "__main__":
    main()
