from __future__ import annotations

from dataclasses import replace

import pytest

from football_manager.domain import (
    InPossessionPosition,
    Level,
    OutOfPossessionPosition,
    PlayerInstructions,
    RoleExecutionSnapshot,
)
from football_manager.simulation import (
    SpatialMatchEngine,
    TacticalPhase,
    TeamSide,
    render_team_tactical_ascii,
)

from test_spatial_core import make_snapshot


def _replace_home_in_possession(snapshot, **changes):
    instructions = snapshot.home_team.tactic.team_instructions
    in_possession = replace(instructions.in_possession, **changes)
    team_instructions = replace(instructions, in_possession=in_possession)
    tactic = replace(snapshot.home_team.tactic, team_instructions=team_instructions)
    home_team = replace(snapshot.home_team, tactic=tactic)
    return replace(snapshot, home_team=home_team)


def _replace_home_out_of_possession(snapshot, **changes):
    instructions = snapshot.home_team.tactic.team_instructions
    out_of_possession = replace(instructions.out_of_possession, **changes)
    team_instructions = replace(instructions, out_of_possession=out_of_possession)
    tactic = replace(snapshot.home_team.tactic, team_instructions=team_instructions)
    home_team = replace(snapshot.home_team, tactic=tactic)
    return replace(snapshot, home_team=home_team)


def _replace_home_player(snapshot, slot_id: str, **changes):
    starters = tuple(
        replace(player, **changes) if player.assigned_slot_id == slot_id else player
        for player in snapshot.home_team.starters
    )
    return replace(snapshot, home_team=replace(snapshot.home_team, starters=starters))


def _force_home_phase(engine: SpatialMatchEngine, phase: TacticalPhase) -> None:
    side = TeamSide.HOME if phase is TacticalPhase.IN_POSSESSION else TeamSide.AWAY
    engine.set_team_possession(side)


def test_possession_side_uses_in_possession_shape_and_opponent_defends() -> None:
    engine = SpatialMatchEngine(make_snapshot(seed=5))
    engine.set_team_possession(TeamSide.HOME)

    assert all(player.tactical_phase is TacticalPhase.IN_POSSESSION for player in engine.state.home_players)
    assert all(player.tactical_phase is TacticalPhase.OUT_OF_POSSESSION for player in engine.state.away_players)


def test_wider_in_possession_defensive_line_increases_target_width() -> None:
    narrow = _replace_home_in_possession(
        make_snapshot(seed=10),
        defensive_line_width=Level.VERY_LOW,
    )
    wide = _replace_home_in_possession(
        make_snapshot(seed=10),
        defensive_line_width=Level.VERY_HIGH,
    )

    narrow_engine = SpatialMatchEngine(narrow)
    wide_engine = SpatialMatchEngine(wide)
    _force_home_phase(narrow_engine, TacticalPhase.IN_POSSESSION)
    _force_home_phase(wide_engine, TacticalPhase.IN_POSSESSION)

    narrow_width = narrow_engine.positioning.shape_metrics(
        narrow_engine.state, TeamSide.HOME
    ).defensive_width_m
    wide_width = wide_engine.positioning.shape_metrics(
        wide_engine.state, TeamSide.HOME
    ).defensive_width_m

    assert wide_width > narrow_width + 10.0


def test_out_of_possession_central_protection_narrows_defensive_shape() -> None:
    open_shape = _replace_home_out_of_possession(
        make_snapshot(seed=11),
        defensive_line_width=Level.HIGH,
        horizontal_compactness=Level.LOW,
        protect_centre=Level.LOW,
        cross_tolerance=Level.LOW,
    )
    protect_centre = _replace_home_out_of_possession(
        make_snapshot(seed=11),
        defensive_line_width=Level.HIGH,
        horizontal_compactness=Level.VERY_HIGH,
        protect_centre=Level.VERY_HIGH,
        cross_tolerance=Level.VERY_HIGH,
    )

    open_engine = SpatialMatchEngine(open_shape)
    compact_engine = SpatialMatchEngine(protect_centre)
    _force_home_phase(open_engine, TacticalPhase.OUT_OF_POSSESSION)
    _force_home_phase(compact_engine, TacticalPhase.OUT_OF_POSSESSION)

    open_width = open_engine.positioning.shape_metrics(
        open_engine.state, TeamSide.HOME
    ).defensive_width_m
    compact_width = compact_engine.positioning.shape_metrics(
        compact_engine.state, TeamSide.HOME
    ).defensive_width_m

    assert compact_width < open_width


def test_high_defensive_block_moves_defensive_line_upfield() -> None:
    low = _replace_home_out_of_possession(
        make_snapshot(seed=12),
        block_height=Level.VERY_LOW,
        defensive_line_height=Level.VERY_LOW,
    )
    high = _replace_home_out_of_possession(
        make_snapshot(seed=12),
        block_height=Level.VERY_HIGH,
        defensive_line_height=Level.VERY_HIGH,
    )

    low_engine = SpatialMatchEngine(low)
    high_engine = SpatialMatchEngine(high)
    _force_home_phase(low_engine, TacticalPhase.OUT_OF_POSSESSION)
    _force_home_phase(high_engine, TacticalPhase.OUT_OF_POSSESSION)

    low_cb = low_engine.state.player_for_slot(TeamSide.HOME, "lcb").tactical_target
    high_cb = high_engine.state.player_for_slot(TeamSide.HOME, "lcb").tactical_target

    assert low_cb is not None
    assert high_cb is not None
    assert high_cb.x > low_cb.x + 20.0


def test_vertical_compactness_reduces_distances_between_lines() -> None:
    stretched = _replace_home_out_of_possession(
        make_snapshot(seed=13),
        vertical_compactness=Level.VERY_LOW,
        defense_midfield_gap=Level.HIGH,
        midfield_attack_gap=Level.HIGH,
    )
    compact = _replace_home_out_of_possession(
        make_snapshot(seed=13),
        vertical_compactness=Level.VERY_HIGH,
        defense_midfield_gap=Level.HIGH,
        midfield_attack_gap=Level.HIGH,
    )

    stretched_engine = SpatialMatchEngine(stretched)
    compact_engine = SpatialMatchEngine(compact)
    _force_home_phase(stretched_engine, TacticalPhase.OUT_OF_POSSESSION)
    _force_home_phase(compact_engine, TacticalPhase.OUT_OF_POSSESSION)

    stretched_metrics = stretched_engine.positioning.shape_metrics(
        stretched_engine.state, TeamSide.HOME
    )
    compact_metrics = compact_engine.positioning.shape_metrics(
        compact_engine.state, TeamSide.HOME
    )

    assert compact_metrics.defense_midfield_gap_m < stretched_metrics.defense_midfield_gap_m
    assert compact_metrics.midfield_attack_gap_m < stretched_metrics.midfield_attack_gap_m


def test_in_possession_inter_line_gap_instruction_changes_shape() -> None:
    close = _replace_home_in_possession(
        make_snapshot(seed=14),
        defense_midfield_gap=Level.VERY_LOW,
        midfield_attack_gap=Level.VERY_LOW,
    )
    spread = _replace_home_in_possession(
        make_snapshot(seed=14),
        defense_midfield_gap=Level.VERY_HIGH,
        midfield_attack_gap=Level.VERY_HIGH,
    )

    close_engine = SpatialMatchEngine(close)
    spread_engine = SpatialMatchEngine(spread)
    _force_home_phase(close_engine, TacticalPhase.IN_POSSESSION)
    _force_home_phase(spread_engine, TacticalPhase.IN_POSSESSION)

    close_metrics = close_engine.positioning.shape_metrics(close_engine.state, TeamSide.HOME)
    spread_metrics = spread_engine.positioning.shape_metrics(spread_engine.state, TeamSide.HOME)

    assert spread_metrics.defense_midfield_gap_m > close_metrics.defense_midfield_gap_m
    assert spread_metrics.midfield_attack_gap_m > close_metrics.midfield_attack_gap_m


def test_inverted_fullback_moves_inside_and_toward_midfield_with_ball() -> None:
    snapshot = make_snapshot(seed=15)
    base_engine = SpatialMatchEngine(snapshot)
    _force_home_phase(base_engine, TacticalPhase.IN_POSSESSION)
    base_target = base_engine.state.player_for_slot(TeamSide.HOME, "lb").tactical_target

    lb = snapshot.home_team.player_for_slot("lb")
    instructions = replace(
        lb.effective_instructions or PlayerInstructions(),
        in_possession_position=InPossessionPosition.MIDFIELD,
    )
    inverted_snapshot = _replace_home_player(
        snapshot,
        "lb",
        effective_instructions=instructions,
    )
    inverted_engine = SpatialMatchEngine(inverted_snapshot)
    _force_home_phase(inverted_engine, TacticalPhase.IN_POSSESSION)
    inverted_target = inverted_engine.state.player_for_slot(TeamSide.HOME, "lb").tactical_target

    assert base_target is not None
    assert inverted_target is not None
    centre_y = inverted_engine.state.pitch.width_m / 2.0
    assert inverted_target.x > base_target.x
    assert abs(inverted_target.y - centre_y) < abs(base_target.y - centre_y)


def test_defensive_role_step_up_and_drop_create_different_depth_targets() -> None:
    snapshot = make_snapshot(seed=16)
    player = snapshot.home_team.player_for_slot("lcb")
    base = player.effective_instructions or PlayerInstructions()

    step_snapshot = _replace_home_player(
        snapshot,
        "lcb",
        effective_instructions=replace(
            base, out_of_possession_position=OutOfPossessionPosition.STEP_UP
        ),
    )
    drop_snapshot = _replace_home_player(
        snapshot,
        "lcb",
        effective_instructions=replace(
            base, out_of_possession_position=OutOfPossessionPosition.DROP
        ),
    )
    step_engine = SpatialMatchEngine(step_snapshot)
    drop_engine = SpatialMatchEngine(drop_snapshot)
    _force_home_phase(step_engine, TacticalPhase.OUT_OF_POSSESSION)
    _force_home_phase(drop_engine, TacticalPhase.OUT_OF_POSSESSION)

    step_target = step_engine.state.player_for_slot(TeamSide.HOME, "lcb").tactical_target
    drop_target = drop_engine.state.player_for_slot(TeamSide.HOME, "lcb").tactical_target

    assert step_target is not None
    assert drop_target is not None
    assert step_target.x > drop_target.x + 8.0


def test_high_defensive_tracking_pulls_winger_deeper_without_ball() -> None:
    snapshot = make_snapshot(seed=17)
    winger = snapshot.home_team.player_for_slot("lw")
    base = winger.effective_instructions or PlayerInstructions()

    low_snapshot = _replace_home_player(
        snapshot,
        "lw",
        effective_instructions=replace(base, defensive_tracking=Level.VERY_LOW),
    )
    high_snapshot = _replace_home_player(
        snapshot,
        "lw",
        effective_instructions=replace(base, defensive_tracking=Level.VERY_HIGH),
    )
    low_engine = SpatialMatchEngine(low_snapshot)
    high_engine = SpatialMatchEngine(high_snapshot)
    _force_home_phase(low_engine, TacticalPhase.OUT_OF_POSSESSION)
    _force_home_phase(high_engine, TacticalPhase.OUT_OF_POSSESSION)

    low_target = low_engine.state.player_for_slot(TeamSide.HOME, "lw").tactical_target
    high_target = high_engine.state.player_for_slot(TeamSide.HOME, "lw").tactical_target

    assert low_target is not None
    assert high_target is not None
    assert high_target.x < low_target.x


def test_possession_switch_changes_target_but_does_not_teleport_player() -> None:
    engine = SpatialMatchEngine(make_snapshot(seed=18))
    engine.set_team_possession(TeamSide.HOME)
    player = engine.state.player_for_slot(TeamSide.HOME, "cm")
    before_location = player.location
    attacking_target = player.tactical_target

    engine.set_team_possession(TeamSide.AWAY)
    defensive_target = player.tactical_target

    assert player.location == before_location
    assert attacking_target is not None
    assert defensive_target is not None
    assert defensive_target != attacking_target

    before_distance = player.location.distance_to(defensive_target)
    engine.step()
    after_distance = player.location.distance_to(defensive_target)
    assert after_distance < before_distance


def test_away_in_possession_target_is_mirror_of_equivalent_home_target() -> None:
    snapshot = make_snapshot(seed=19)
    engine = SpatialMatchEngine(snapshot)

    engine.set_team_possession(TeamSide.HOME)
    home_target = engine.state.player_for_slot(TeamSide.HOME, "rcm").tactical_target

    engine.set_team_possession(TeamSide.AWAY)
    away_target = engine.state.player_for_slot(TeamSide.AWAY, "rcm").tactical_target

    assert home_target is not None
    assert away_target is not None
    assert away_target == engine.state.pitch.mirror(home_target)


def test_all_tactical_targets_remain_inside_pitch_at_extreme_settings() -> None:
    snapshot = _replace_home_in_possession(
        make_snapshot(seed=20),
        defensive_line_width=Level.VERY_HIGH,
        midfield_width=Level.VERY_HIGH,
        attacking_line_width=Level.VERY_HIGH,
        defense_midfield_gap=Level.VERY_HIGH,
        midfield_attack_gap=Level.VERY_HIGH,
    )
    engine = SpatialMatchEngine(snapshot)
    engine.set_team_possession(TeamSide.HOME)

    assert all(
        agent.tactical_target is not None and engine.state.pitch.contains(agent.tactical_target)
        for agent in engine.state.players.values()
    )


def test_higher_familiarity_increases_tactical_reposition_speed_without_changing_target() -> None:
    snapshot = make_snapshot(seed=21)
    player = snapshot.home_team.player_for_slot("cm")
    assert player.role_context is not None

    low_context = RoleExecutionSnapshot(
        position_familiarity=20,
        role_familiarity=20,
        tactic_familiarity=20,
        role_suitability=player.role_context.role_suitability,
    )
    high_context = RoleExecutionSnapshot(
        position_familiarity=100,
        role_familiarity=100,
        tactic_familiarity=100,
        role_suitability=player.role_context.role_suitability,
    )
    low_snapshot = _replace_home_player(snapshot, "cm", role_context=low_context)
    high_snapshot = _replace_home_player(snapshot, "cm", role_context=high_context)

    low_engine = SpatialMatchEngine(low_snapshot)
    high_engine = SpatialMatchEngine(high_snapshot)
    low_engine.set_team_possession(TeamSide.AWAY)
    high_engine.set_team_possession(TeamSide.AWAY)
    low_agent = low_engine.state.player_for_slot(TeamSide.HOME, "cm")
    high_agent = high_engine.state.player_for_slot(TeamSide.HOME, "cm")

    # Put both agents far from the same tactical target so arrival capping does not
    # hide the familiarity-dependent reposition speed.
    far_location = low_engine.state.pitch.centre
    low_agent.location = far_location
    high_agent.location = far_location
    low_engine.refresh_tactical_positioning()
    high_engine.refresh_tactical_positioning()

    assert low_agent.tactical_target == high_agent.tactical_target
    assert high_agent.velocity.magnitude > low_agent.velocity.magnitude


def test_ascii_debug_renderer_exposes_phase_and_shape() -> None:
    engine = SpatialMatchEngine(make_snapshot(seed=22))
    engine.set_team_possession(TeamSide.HOME)

    output = render_team_tactical_ascii(engine.state, TeamSide.HOME)

    assert "HOME | in_possession" in output
    assert "ST" in output
    assert "GK" in output
    assert "┌" in output and "┘" in output
