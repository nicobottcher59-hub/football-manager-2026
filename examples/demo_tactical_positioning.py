from __future__ import annotations

from football_manager.domain import Level
from football_manager.simulation import (
    SpatialMatchEngine,
    TeamSide,
    render_team_tactical_ascii,
)

from demo_match_factory import build_demo_snapshot


def configure_home(tactic) -> None:
    # The specific setup we discussed: open the first line to build short, then
    # collapse centrally without the ball and accept more play toward the wings.
    tactic.update_in_possession(
        defensive_line_width=Level.VERY_HIGH,
        midfield_width=Level.NORMAL,
        attacking_line_width=Level.HIGH,
        defense_midfield_gap=Level.NORMAL,
        midfield_attack_gap=Level.NORMAL,
    )
    tactic.update_out_of_possession(
        defensive_line_width=Level.LOW,
        midfield_width=Level.LOW,
        attacking_line_width=Level.NORMAL,
        block_height=Level.LOW,
        defensive_line_height=Level.LOW,
        horizontal_compactness=Level.VERY_HIGH,
        vertical_compactness=Level.VERY_HIGH,
        protect_centre=Level.VERY_HIGH,
        cross_tolerance=Level.HIGH,
    )
    tactic.set_role("lb", "inverted_fullback")
    tactic.set_role("lw", "defensive_winger")


def print_metrics(engine: SpatialMatchEngine) -> None:
    metrics = engine.positioning.shape_metrics(engine.state, TeamSide.HOME)
    print(
        f"Defensive width: {metrics.defensive_width_m:.1f} m | "
        f"Midfield width: {metrics.midfield_width_m:.1f} m | "
        f"Attack width: {metrics.attacking_width_m:.1f} m"
    )
    print(
        f"Defence-mid gap: {metrics.defense_midfield_gap_m:.1f} m | "
        f"Mid-attack gap: {metrics.midfield_attack_gap_m:.1f} m"
    )


def main() -> None:
    engine = SpatialMatchEngine(build_demo_snapshot(configure_home=configure_home))

    print("PHASE 5.1 - TACTICAL POSITIONING DEBUG")
    print("=" * 72)
    print("\nHOME WITH THE BALL\n")
    engine.set_team_possession(TeamSide.HOME)
    print(render_team_tactical_ascii(engine.state, TeamSide.HOME))
    print_metrics(engine)
    lb = engine.state.player_for_slot(TeamSide.HOME, "lb")
    print(f"LB/Inverted FB target: ({lb.tactical_target.x:.1f}, {lb.tactical_target.y:.1f})")

    print("\n" + "=" * 72)
    print("\nHOME WITHOUT THE BALL\n")
    engine.set_team_possession(TeamSide.AWAY)
    print(render_team_tactical_ascii(engine.state, TeamSide.HOME))
    print_metrics(engine)
    lb = engine.state.player_for_slot(TeamSide.HOME, "lb")
    print(f"LB defensive target: ({lb.tactical_target.x:.1f}, {lb.tactical_target.y:.1f})")

    print("\n" + "=" * 72)
    print("\nTRANSITION CHECK\n")
    player = engine.state.player_for_slot(TeamSide.HOME, "cm")
    target = player.tactical_target
    before = player.location.distance_to(target)
    engine.advance_ticks(8)  # two seconds of fixed-step movement
    after = player.location.distance_to(target)
    print(f"CM distance to defensive target: {before:.2f} m -> {after:.2f} m after 2.0 s")
    print("No teleport: the player moves toward the new shape using bounded speed.")


if __name__ == "__main__":
    main()
