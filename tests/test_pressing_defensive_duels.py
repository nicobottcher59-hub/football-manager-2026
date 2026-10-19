from __future__ import annotations

from dataclasses import replace

import pytest

from football_manager.domain import (
    ForceDirection,
    Level,
    MarkingStyle,
    PlayerInstructions,
    PressingScheme,
    TacticalTarget,
    TargetKind,
)
from football_manager.simulation import (
    DefensiveDuelOutcome,
    SpatialMatchEngine,
    TeamSide,
    Vector2,
)

from test_spatial_core import make_snapshot


def _replace_out_of_possession(snapshot, side: TeamSide, **changes):
    team = snapshot.home_team if side is TeamSide.HOME else snapshot.away_team
    instructions = team.tactic.team_instructions
    out = replace(instructions.out_of_possession, **changes)
    tactic = replace(
        team.tactic,
        team_instructions=replace(instructions, out_of_possession=out),
    )
    new_team = replace(team, tactic=tactic)
    if side is TeamSide.HOME:
        return replace(snapshot, home_team=new_team)
    return replace(snapshot, away_team=new_team)


def _replace_starter(snapshot, side: TeamSide, slot_id: str, transform):
    team = snapshot.home_team if side is TeamSide.HOME else snapshot.away_team
    starters = tuple(
        transform(player) if player.assigned_slot_id == slot_id else player
        for player in team.starters
    )
    new_team = replace(team, starters=starters)
    if side is TeamSide.HOME:
        return replace(snapshot, home_team=new_team)
    return replace(snapshot, away_team=new_team)


def _with_player_instructions(snapshot, side: TeamSide, slot_id: str, **changes):
    def transform(player):
        base = player.effective_instructions or PlayerInstructions()
        return replace(player, effective_instructions=replace(base, **changes))

    return _replace_starter(snapshot, side, slot_id, transform)


def _with_duel_attributes(
    snapshot,
    *,
    defender_tackling: int,
    defender_strength: int,
    attacker_dribbling: int,
    attacker_balance: int,
):
    def defender_transform(player):
        tech = replace(player.attributes.technical, tackling=defender_tackling)
        physical = replace(player.attributes.physical, strength=defender_strength)
        mental = replace(
            player.attributes.mental,
            anticipation=defender_tackling,
            positioning=defender_tackling,
            decisions=defender_tackling,
        )
        return replace(
            player,
            attributes=replace(
                player.attributes,
                technical=tech,
                physical=physical,
                mental=mental,
            ),
        )

    def attacker_transform(player):
        tech = replace(
            player.attributes.technical,
            dribbling=attacker_dribbling,
            technique=attacker_dribbling,
            first_touch=attacker_dribbling,
        )
        physical = replace(
            player.attributes.physical,
            balance=attacker_balance,
            agility=attacker_balance,
        )
        return replace(
            player,
            attributes=replace(player.attributes, technical=tech, physical=physical),
        )

    snapshot = _replace_starter(snapshot, TeamSide.AWAY, "cm", defender_transform)
    return _replace_starter(snapshot, TeamSide.HOME, "cm", attacker_transform)


def _place_press_scenario(engine: SpatialMatchEngine) -> tuple[object, object]:
    carrier = engine.state.player_for_slot(TeamSide.HOME, "cm")
    defender = engine.state.player_for_slot(TeamSide.AWAY, "cm")
    carrier.location = Vector2(50.0, 34.0)
    defender.location = Vector2(57.0, 34.0)
    for agent in engine.state.away_players:
        if agent.agent_id != defender.agent_id:
            agent.location = Vector2(95.0, 62.0)
    engine.give_ball_to(carrier.agent_id)
    return carrier, defender


def _duel_engine(seed: int, snapshot=None) -> tuple[SpatialMatchEngine, object, object]:
    engine = SpatialMatchEngine(snapshot or make_snapshot(seed=seed))
    carrier = engine.state.player_for_slot(TeamSide.HOME, "cm")
    defender = engine.state.player_for_slot(TeamSide.AWAY, "cm")
    carrier.location = Vector2(50.0, 34.0)
    defender.location = Vector2(51.0, 34.0)
    for agent in engine.state.players.values():
        if agent.agent_id not in {carrier.agent_id, defender.agent_id}:
            if agent.side is TeamSide.AWAY:
                agent.location = Vector2(90.0, 62.0)
            else:
                agent.location = Vector2(15.0, 8.0)
    engine.give_ball_to(carrier.agent_id)
    for agent in engine.state.players.values():
        engine.set_player_velocity(agent.agent_id, Vector2.zero())
    return engine, carrier, defender


def test_no_controlled_ball_owner_produces_no_pressing_assignments() -> None:
    engine = SpatialMatchEngine(make_snapshot(seed=401))
    engine.set_team_possession(TeamSide.HOME)

    plan = engine.pressing_plan(TeamSide.AWAY)

    assert plan.ball_carrier_agent_id is None
    assert plan.pressing_assignments == ()
    assert plan.coverage_assignments == ()


def test_pressing_plan_selects_a_nearby_defender_against_ball_carrier() -> None:
    engine = SpatialMatchEngine(make_snapshot(seed=402))
    carrier, defender = _place_press_scenario(engine)

    plan = engine.pressing_plan(TeamSide.AWAY)

    assert plan.ball_carrier_agent_id == carrier.agent_id
    assert plan.primary is not None
    assert plan.primary.defender_agent_id == defender.agent_id
    assert plan.primary.target_agent_id == carrier.agent_id


def test_higher_team_pressing_intensity_commits_more_pressers() -> None:
    low_snapshot = _replace_out_of_possession(
        make_snapshot(seed=403),
        TeamSide.AWAY,
        pressing_intensity=Level.VERY_LOW,
        pressing_scheme=PressingScheme.STANDARD,
    )
    high_snapshot = _replace_out_of_possession(
        make_snapshot(seed=403),
        TeamSide.AWAY,
        pressing_intensity=Level.VERY_HIGH,
        pressing_scheme=PressingScheme.STANDARD,
    )
    low = SpatialMatchEngine(low_snapshot)
    high = SpatialMatchEngine(high_snapshot)

    for engine in (low, high):
        carrier = engine.state.player_for_slot(TeamSide.HOME, "cm")
        carrier.location = Vector2(50.0, 34.0)
        for slot, location in {
            "cm": Vector2(56.0, 34.0),
            "rcm": Vector2(58.0, 29.0),
            "lcm": Vector2(58.0, 39.0),
            "st": Vector2(60.0, 34.0),
        }.items():
            engine.state.player_for_slot(TeamSide.AWAY, slot).location = location
        engine.give_ball_to(carrier.agent_id)

    low_plan = low.pressing_plan(TeamSide.AWAY)
    high_plan = high.pressing_plan(TeamSide.AWAY)

    assert len(low_plan.pressing_assignments) == 1
    assert len(high_plan.pressing_assignments) >= 3


def test_constant_press_scheme_extends_pressing_commitment() -> None:
    standard = _replace_out_of_possession(
        make_snapshot(seed=404),
        TeamSide.AWAY,
        pressing_intensity=Level.HIGH,
        pressing_scheme=PressingScheme.STANDARD,
    )
    constant = _replace_out_of_possession(
        make_snapshot(seed=404),
        TeamSide.AWAY,
        pressing_intensity=Level.HIGH,
        pressing_scheme=PressingScheme.CONSTANT,
    )
    standard_engine = SpatialMatchEngine(standard)
    constant_engine = SpatialMatchEngine(constant)
    for engine in (standard_engine, constant_engine):
        carrier = engine.state.player_for_slot(TeamSide.HOME, "cm")
        carrier.location = Vector2(50.0, 34.0)
        for slot, location in {
            "cm": Vector2(56.0, 34.0),
            "rcm": Vector2(60.0, 28.0),
            "lcm": Vector2(60.0, 40.0),
            "st": Vector2(62.0, 34.0),
        }.items():
            engine.state.player_for_slot(TeamSide.AWAY, slot).location = location
        engine.give_ball_to(carrier.agent_id)

    assert len(constant_engine.pressing_plan(TeamSide.AWAY).pressing_assignments) > len(
        standard_engine.pressing_plan(TeamSide.AWAY).pressing_assignments
    )


def test_individual_pressing_target_can_prioritize_a_specific_ball_carrier() -> None:
    snapshot = _replace_out_of_possession(
        make_snapshot(seed=405), TeamSide.AWAY, pressing_intensity=Level.LOW
    )
    snapshot = _with_player_instructions(
        snapshot,
        TeamSide.AWAY,
        "lcm",
        pressing_target=TacticalTarget(TargetKind.PLAYER, "home-cm"),
    )
    engine = SpatialMatchEngine(snapshot)
    carrier = engine.state.player_for_slot(TeamSide.HOME, "cm")
    nearer = engine.state.player_for_slot(TeamSide.AWAY, "rcm")
    targeted = engine.state.player_for_slot(TeamSide.AWAY, "lcm")
    carrier.location = Vector2(50.0, 34.0)
    nearer.location = Vector2(54.0, 34.0)
    targeted.location = Vector2(58.0, 34.0)
    for agent in engine.state.away_players:
        if agent.agent_id not in {nearer.agent_id, targeted.agent_id}:
            agent.location = Vector2(95.0, 62.0)
    engine.give_ball_to(carrier.agent_id)

    plan = engine.pressing_plan(TeamSide.AWAY)

    assert plan.primary is not None
    assert plan.primary.defender_agent_id == targeted.agent_id


def test_individual_pressing_intensity_changes_real_closing_speed() -> None:
    low_snapshot = _with_player_instructions(
        make_snapshot(seed=406), TeamSide.AWAY, "cm", pressing_intensity=Level.VERY_LOW
    )
    high_snapshot = _with_player_instructions(
        make_snapshot(seed=406), TeamSide.AWAY, "cm", pressing_intensity=Level.VERY_HIGH
    )
    low = SpatialMatchEngine(low_snapshot)
    high = SpatialMatchEngine(high_snapshot)
    _, low_defender = _place_press_scenario(low)
    _, high_defender = _place_press_scenario(high)

    low_assignment = next(
        item for item in low.pressing_plan(TeamSide.AWAY).pressing_assignments
        if item.defender_agent_id == low_defender.agent_id
    )
    high_assignment = next(
        item for item in high.pressing_plan(TeamSide.AWAY).pressing_assignments
        if item.defender_agent_id == high_defender.agent_id
    )

    assert high_assignment.closing_speed_mps > low_assignment.closing_speed_mps


def test_force_outside_changes_the_real_pressing_approach_angle() -> None:
    snapshot = _replace_out_of_possession(
        make_snapshot(seed=407),
        TeamSide.AWAY,
        pressing_intensity=Level.HIGH,
        force_direction=ForceDirection.OUTSIDE,
    )
    engine = SpatialMatchEngine(snapshot)
    carrier, _ = _place_press_scenario(engine)
    carrier.location = Vector2(50.0, 15.0)
    engine.state.player_for_slot(TeamSide.AWAY, "cm").location = Vector2(57.0, 15.0)
    engine.state.ball.location = carrier.location
    engine.refresh_tactical_positioning()

    primary = engine.pressing_plan(TeamSide.AWAY).primary

    assert primary is not None
    assert primary.approach_target.y > carrier.location.y


def test_trap_outside_scheme_consumes_direction_even_when_force_direction_is_neutral() -> None:
    snapshot = _replace_out_of_possession(
        make_snapshot(seed=408),
        TeamSide.AWAY,
        pressing_intensity=Level.HIGH,
        pressing_scheme=PressingScheme.TRAP_OUTSIDE,
        force_direction=ForceDirection.NEUTRAL,
    )
    engine = SpatialMatchEngine(snapshot)
    carrier, _ = _place_press_scenario(engine)
    carrier.location = Vector2(50.0, 15.0)
    engine.state.player_for_slot(TeamSide.AWAY, "cm").location = Vector2(57.0, 15.0)
    engine.state.ball.location = carrier.location
    engine.refresh_tactical_positioning()

    primary = engine.pressing_plan(TeamSide.AWAY).primary

    assert primary is not None
    assert primary.approach_target.y > carrier.location.y


def test_active_presser_physically_closes_distance_over_fixed_ticks() -> None:
    snapshot = _replace_out_of_possession(
        make_snapshot(seed=409), TeamSide.AWAY, pressing_intensity=Level.VERY_HIGH
    )
    engine = SpatialMatchEngine(snapshot)
    carrier, defender = _place_press_scenario(engine)
    engine.set_player_velocity(carrier.agent_id, Vector2.zero())
    before = defender.location.distance_to(carrier.location)

    engine.advance_ticks(4)

    after = defender.location.distance_to(carrier.location)
    assert after < before


def test_manual_velocity_override_is_not_overwritten_by_pressing() -> None:
    snapshot = _replace_out_of_possession(
        make_snapshot(seed=410), TeamSide.AWAY, pressing_intensity=Level.VERY_HIGH
    )
    engine = SpatialMatchEngine(snapshot)
    carrier, defender = _place_press_scenario(engine)
    engine.set_player_velocity(carrier.agent_id, Vector2.zero())
    engine.set_player_velocity(defender.agent_id, Vector2.zero())
    before = defender.location

    engine.step()

    assert defender.location == before


def test_explicit_marking_target_creates_specific_coverage_assignment() -> None:
    snapshot = _with_player_instructions(
        make_snapshot(seed=411),
        TeamSide.AWAY,
        "lcb",
        marking=TacticalTarget(TargetKind.PLAYER, "home-st"),
    )
    engine = SpatialMatchEngine(snapshot)
    carrier = engine.state.player_for_slot(TeamSide.HOME, "cm")
    carrier.location = Vector2(48.0, 34.0)
    engine.state.player_for_slot(TeamSide.HOME, "st").location = Vector2(61.0, 34.0)
    engine.state.player_for_slot(TeamSide.AWAY, "cm").location = Vector2(52.0, 34.0)
    engine.state.player_for_slot(TeamSide.AWAY, "lcb").location = Vector2(61.0, 36.0)
    engine.give_ball_to(carrier.agent_id)

    plan = engine.pressing_plan(TeamSide.AWAY)
    assignment = next(
        item for item in plan.coverage_assignments
        if item.defender_agent_id == engine.state.player_for_slot(TeamSide.AWAY, "lcb").agent_id
    )

    assert assignment.target_agent_id == engine.state.player_for_slot(TeamSide.HOME, "st").agent_id
    assert assignment.explicit_mark


def test_man_marking_creates_tighter_coverage_than_zonal_marking() -> None:
    base = make_snapshot(seed=412)
    base = _with_player_instructions(
        base,
        TeamSide.AWAY,
        "lcb",
        marking=TacticalTarget(TargetKind.PLAYER, "home-st"),
    )
    zonal = _replace_out_of_possession(base, TeamSide.AWAY, marking_style=MarkingStyle.ZONAL)
    man = _replace_out_of_possession(base, TeamSide.AWAY, marking_style=MarkingStyle.MAN)
    zonal_engine = SpatialMatchEngine(zonal)
    man_engine = SpatialMatchEngine(man)
    for engine in (zonal_engine, man_engine):
        carrier = engine.state.player_for_slot(TeamSide.HOME, "cm")
        carrier.location = Vector2(48.0, 34.0)
        engine.state.player_for_slot(TeamSide.HOME, "st").location = Vector2(62.0, 34.0)
        engine.state.player_for_slot(TeamSide.AWAY, "cm").location = Vector2(52.0, 34.0)
        engine.state.player_for_slot(TeamSide.AWAY, "lcb").location = Vector2(62.0, 36.0)
        engine.give_ball_to(carrier.agent_id)

    zonal_assignment = next(
        item for item in zonal_engine.pressing_plan(TeamSide.AWAY).coverage_assignments
        if item.defender_agent_id == zonal_engine.state.player_for_slot(TeamSide.AWAY, "lcb").agent_id
    )
    man_assignment = next(
        item for item in man_engine.pressing_plan(TeamSide.AWAY).coverage_assignments
        if item.defender_agent_id == man_engine.state.player_for_slot(TeamSide.AWAY, "lcb").agent_id
    )

    assert man_assignment.marking_strength > zonal_assignment.marking_strength


def test_tackle_requires_defender_to_be_close_to_opposing_ball_carrier() -> None:
    engine, _, defender = _duel_engine(seed=413)
    defender.location = Vector2(60.0, 34.0)

    with pytest.raises(ValueError, match="too far away"):
        engine.defensive_duel_profile(defender.agent_id)


def test_defender_cannot_tackle_a_teammate() -> None:
    engine = SpatialMatchEngine(make_snapshot(seed=414))
    owner = engine.state.player_for_slot(TeamSide.AWAY, "cm")
    teammate = engine.state.player_for_slot(TeamSide.AWAY, "rcm")
    owner.location = Vector2(50.0, 34.0)
    teammate.location = Vector2(51.0, 34.0)
    engine.give_ball_to(owner.agent_id)

    with pytest.raises(ValueError, match="teammate"):
        engine.defensive_duel_profile(teammate.agent_id)


def test_strong_tackler_has_better_duel_probability_against_weak_dribbler() -> None:
    strong_snapshot = _with_duel_attributes(
        make_snapshot(seed=415),
        defender_tackling=95,
        defender_strength=90,
        attacker_dribbling=30,
        attacker_balance=35,
    )
    weak_snapshot = _with_duel_attributes(
        make_snapshot(seed=415),
        defender_tackling=30,
        defender_strength=35,
        attacker_dribbling=95,
        attacker_balance=90,
    )
    strong, _, strong_defender = _duel_engine(seed=415, snapshot=strong_snapshot)
    weak, _, weak_defender = _duel_engine(seed=415, snapshot=weak_snapshot)

    strong_profile = strong.defensive_duel_profile(strong_defender.agent_id)
    weak_profile = weak.defensive_duel_profile(weak_defender.agent_id)

    assert strong_profile.defender_quality > weak_profile.defender_quality
    assert strong_profile.attacker_resistance < weak_profile.attacker_resistance
    assert strong_profile.success_probability > weak_profile.success_probability


def test_nearby_defensive_support_increases_tackle_success_probability() -> None:
    isolated, carrier1, defender1 = _duel_engine(seed=416)
    supported, carrier2, defender2 = _duel_engine(seed=416)
    helper = supported.state.player_for_slot(TeamSide.AWAY, "rcm")
    helper.location = carrier2.location + Vector2(0.0, 2.0)

    isolated_profile = isolated.defensive_duel_profile(defender1.agent_id)
    supported_profile = supported.defensive_duel_profile(defender2.agent_id)

    assert supported_profile.support > isolated_profile.support
    assert supported_profile.success_probability > isolated_profile.success_probability


def test_defensive_aggression_changes_tackle_willingness_not_player_quality() -> None:
    low_snapshot = _replace_out_of_possession(
        make_snapshot(seed=417), TeamSide.AWAY, defensive_aggression=Level.VERY_LOW
    )
    high_snapshot = _replace_out_of_possession(
        make_snapshot(seed=417), TeamSide.AWAY, defensive_aggression=Level.VERY_HIGH
    )
    low, _, low_defender = _duel_engine(seed=417, snapshot=low_snapshot)
    high, _, high_defender = _duel_engine(seed=417, snapshot=high_snapshot)

    low_profile = low.defensive_duel_profile(low_defender.agent_id)
    high_profile = high.defensive_duel_profile(high_defender.agent_id)

    assert high_profile.tackle_willingness > low_profile.tackle_willingness
    assert high_profile.defender_quality == low_profile.defender_quality
    assert high_profile.success_probability == pytest.approx(low_profile.success_probability)


def test_same_seed_and_same_duel_produce_same_result_and_state() -> None:
    first, _, first_defender = _duel_engine(seed=418)
    second, _, second_defender = _duel_engine(seed=418)

    first_result = first.attempt_tackle(first_defender.agent_id)
    second_result = second.attempt_tackle(second_defender.agent_id)

    assert first_result == second_result
    assert first.state.signature() == second.state.signature()


def test_press_broken_detection_requires_carrier_to_escape_beyond_primary_presser() -> None:
    snapshot = _replace_out_of_possession(
        make_snapshot(seed=419), TeamSide.AWAY, pressing_intensity=Level.VERY_LOW
    )
    engine = SpatialMatchEngine(snapshot)
    carrier, defender = _place_press_scenario(engine)
    defender.location = Vector2(52.0, 34.0)
    engine.refresh_tactical_positioning()
    plan = engine.pressing_plan(TeamSide.AWAY)
    assert plan.primary is not None
    assert not engine.press_is_broken(plan)

    carrier.location = Vector2(59.0, 34.0)
    engine.state.ball.location = carrier.location

    assert engine.press_is_broken(plan)


def test_successful_tackle_can_transfer_control_to_defender() -> None:
    engine, carrier, defender = _duel_engine(seed=2)

    result = engine.attempt_tackle(defender.agent_id)

    assert result.outcome is DefensiveDuelOutcome.DEFENDER_CONTROL
    assert result.controller_agent_id == defender.agent_id
    assert engine.state.ball.owner_agent_id == defender.agent_id
    assert engine.state.possession.owner_agent_id == defender.agent_id
    assert engine.state.possession.team_side is TeamSide.AWAY
    assert defender.has_ball
    assert not carrier.has_ball


def test_failed_tackle_can_leave_attacker_in_control() -> None:
    engine, carrier, defender = _duel_engine(seed=420)

    result = engine.attempt_tackle(defender.agent_id)

    assert result.outcome is DefensiveDuelOutcome.ATTACKER_RETAINS
    assert result.controller_agent_id == carrier.agent_id
    assert engine.state.ball.owner_agent_id == carrier.agent_id
    assert engine.state.possession.team_side is TeamSide.HOME
    assert carrier.has_ball


def test_won_duel_can_create_a_loose_ball_instead_of_magic_possession() -> None:
    engine, _, defender = _duel_engine(seed=426)

    result = engine.attempt_tackle(defender.agent_id)

    assert result.outcome is DefensiveDuelOutcome.LOOSE_BALL
    assert result.controller_agent_id is None
    assert result.loose_ball_location is not None
    assert engine.state.ball.owner_agent_id is None
    assert engine.state.possession.owner_agent_id is None
    assert engine.state.possession.team_side is None
    assert engine.state.ball.location == result.loose_ball_location
