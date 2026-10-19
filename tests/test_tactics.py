from dataclasses import replace
from datetime import date

import pytest

from football_manager.domain import (
    Foot,
    Formation,
    FormationSlot,
    InPossessionPosition,
    Level,
    MentalAttributes,
    OutOfPossessionPosition,
    PassLength,
    PhysicalAttributes,
    Player,
    PlayerAttributes,
    PlayerIdentity,
    PlayerInstructionOverrides,
    Position,
    PositionalFamiliarity,
    TacticalFamiliarity,
    TacticalPreset,
    TacticalTarget,
    TargetKind,
    TechnicalAttributes,
    Tactic,
    default_role_for_position,
    evaluate_role_context,
    get_role,
    instructions_for_preset,
    role_similarity,
    role_suitability,
    roles_for_position,
)


def make_formation() -> Formation:
    return Formation(
        formation_id="4-3-3-tactics",
        name="4-3-3 Tactics",
        slots=(
            FormationSlot("gk", Position.GK),
            FormationSlot("rb", Position.RB),
            FormationSlot("rcb", Position.RCB),
            FormationSlot("lcb", Position.LCB),
            FormationSlot("lb", Position.LB),
            FormationSlot("rcm", Position.RCM),
            FormationSlot("cm", Position.CM),
            FormationSlot("lcm", Position.LCM),
            FormationSlot("rw", Position.RW),
            FormationSlot("st", Position.ST),
            FormationSlot("lw", Position.LW),
        ),
    )


def make_winger() -> Player:
    return Player(
        identity=PlayerIdentity(
            player_id="winger-1",
            first_name="Fast",
            last_name="Winger",
            birth_date=date(2002, 1, 1),
            nationality="Argentina",
            dominant_foot=Foot.RIGHT,
        ),
        attributes=PlayerAttributes(
            technical=TechnicalAttributes(
                passing=76,
                technique=84,
                finishing=78,
                first_touch=83,
                dribbling=88,
                crossing=84,
                tackling=42,
                heading=43,
                long_shots=72,
                shot_power=73,
                marking=38,
                set_pieces=67,
                penalties=65,
            ),
            mental=MentalAttributes(
                vision=77,
                decisions=74,
                anticipation=79,
                concentration=66,
                composure=76,
                positioning=50,
                off_the_ball=84,
                teamwork=72,
                work_rate=81,
                aggression=62,
                bravery=58,
                creativity=80,
                tactical_intelligence=74,
            ),
            physical=PhysicalAttributes(
                pace=90,
                acceleration=91,
                strength=49,
                stamina=82,
                agility=89,
                balance=78,
                jumping_reach=45,
                natural_fitness=84,
            ),
        ),
        positional_familiarity=PositionalFamiliarity(
            {Position.LW: 95, Position.RW: 86, Position.ST: 48}
        ),
        original_position=Position.LW,
        primary_position=Position.LW,
        tactical_familiarity=TacticalFamiliarity(
            tactic_values={"nico-ball": 72},
            role_values={"advanced_forward": 55, "target_forward": 20},
        ),
    )


def test_every_position_has_exactly_five_base_roles() -> None:
    for position in Position:
        roles = roles_for_position(position)
        assert len(roles) == 5, position
        assert all(role.supports(position) for role in roles)


def test_default_role_is_compatible_with_every_position() -> None:
    for position in Position:
        assert default_role_for_position(position).supports(position)


def test_tactic_from_preset_assigns_role_to_every_formation_slot() -> None:
    formation = make_formation()
    tactic = Tactic.from_preset(
        tactic_id="t1",
        name="Base",
        formation=formation,
        preset=TacticalPreset.BALANCED,
    )

    assert frozenset(tactic.role_assignments) == formation.slot_ids
    assert tactic.role_for_slot("st").supports(Position.ST)
    assert tactic.role_for_slot("lb").supports(Position.LB)


def test_incompatible_role_cannot_be_assigned_to_slot() -> None:
    tactic = Tactic.from_preset("t1", "Base", make_formation(), TacticalPreset.BALANCED)

    with pytest.raises(ValueError, match="not compatible"):
        tactic.set_role("lb", "target_forward")


def test_role_defaults_can_be_overridden_without_mutating_catalog() -> None:
    tactic = Tactic.from_preset("t1", "Base", make_formation(), TacticalPreset.BALANCED)
    tactic.set_role("lb", "defensive_fullback")
    original = get_role("defensive_fullback").default_instructions

    overrides = PlayerInstructionOverrides(
        forward_runs=Level.HIGH,
        dribbling_frequency=Level.HIGH,
        in_possession_position=InPossessionPosition.MIDFIELD,
        out_of_possession_position=OutOfPossessionPosition.RETURN_TO_BASE,
    )
    tactic.set_player_overrides("lb", overrides)
    effective = tactic.effective_player_instructions("lb")

    assert effective.forward_runs is Level.HIGH
    assert effective.dribbling_frequency is Level.HIGH
    assert effective.in_possession_position is InPossessionPosition.MIDFIELD
    assert original.forward_runs is Level.VERY_LOW
    assert original.in_possession_position is InPossessionPosition.BASE


def test_individual_instructions_support_position_marking_and_specific_pressing_target() -> None:
    tactic = Tactic.from_preset("t1", "Base", make_formation(), TacticalPreset.BALANCED)
    overrides = PlayerInstructionOverrides(
        marking=TacticalTarget(TargetKind.POSITION, Position.RW.value),
        pressing_target=TacticalTarget(TargetKind.PLAYER, "opponent-gk-1"),
        defensive_tracking=Level.VERY_HIGH,
        pressing_intensity=Level.VERY_HIGH,
    )
    tactic.set_player_overrides("lb", overrides)
    effective = tactic.effective_player_instructions("lb")

    assert effective.marking == TacticalTarget(TargetKind.POSITION, "RW")
    assert effective.pressing_target == TacticalTarget(TargetKind.PLAYER, "opponent-gk-1")
    assert effective.defensive_tracking is Level.VERY_HIGH


def test_position_target_rejects_unknown_position() -> None:
    with pytest.raises(ValueError):
        TacticalTarget(TargetKind.POSITION, "NOT_A_POSITION")


def test_team_preset_is_a_starting_point_and_can_be_customized() -> None:
    tactic = Tactic.from_preset(
        "t1",
        "Modified Tiki",
        make_formation(),
        TacticalPreset.TIKI_TAKA,
    )
    original_pass_length = tactic.team_instructions.in_possession.pass_length

    tactic.update_in_possession(
        pass_length=PassLength.LONG,
        verticality=Level.VERY_HIGH,
        patience=Level.VERY_LOW,
    )

    assert original_pass_length is PassLength.VERY_SHORT
    assert tactic.team_instructions.in_possession.pass_length is PassLength.LONG
    assert tactic.preset_origin is TacticalPreset.TIKI_TAKA


def test_tactical_style_analyzer_reads_real_configuration_not_preset_name() -> None:
    tactic = Tactic.from_preset(
        "nico-ball",
        "Nico Ball",
        make_formation(),
        TacticalPreset.CUSTOM,
    )
    tactic.team_instructions = instructions_for_preset(TacticalPreset.CATENACCIO)

    analysis = tactic.analyze_style()

    assert tactic.name == "Nico Ball"
    assert tactic.preset_origin is TacticalPreset.CUSTOM
    assert analysis.label == "Defensa profunda + ralentizar el partido"
    assert analysis.defensive_depth < 30


def test_tiki_taka_is_detected_as_pressing_plus_possession() -> None:
    tactic = Tactic.from_preset(
        "t1",
        "Tiki",
        make_formation(),
        TacticalPreset.TIKI_TAKA,
    )

    analysis = tactic.analyze_style()

    assert analysis.label == "Presion alta + posesion"
    assert analysis.possession >= 65
    assert analysis.pressing >= 70


def test_wide_attack_is_detected_from_actual_width_and_crossing_settings() -> None:
    tactic = Tactic.from_preset(
        "t1",
        "Wide",
        make_formation(),
        TacticalPreset.WIDE_ATTACK,
    )

    assert tactic.analyze_style().label == "Ataque por bandas + amplitud"


def test_winger_role_is_behaviorally_closer_to_advanced_forward_than_target_forward() -> None:
    assert role_similarity("winger", "advanced_forward") > role_similarity(
        "winger", "target_forward"
    )


def test_role_suitability_uses_attributes_without_changing_player_ability() -> None:
    player = make_winger()
    before = player.attributes

    advanced_fit = role_suitability(player, "advanced_forward")
    target_fit = role_suitability(player, "target_forward")

    assert advanced_fit > target_fit
    assert player.attributes is before
    assert player.attributes.technical.dribbling == 88
    assert player.attributes.physical.strength == 49


def test_position_role_tactic_familiarity_and_suitability_are_separate_values() -> None:
    player = make_winger()

    context = evaluate_role_context(
        player=player,
        position=Position.ST,
        role="advanced_forward",
        tactic_id="nico-ball",
    )

    assert context.position_familiarity == 48
    assert context.role_familiarity == 55
    assert context.tactic_familiarity == 72
    assert 1 <= context.role_suitability <= 100


def test_tactical_familiarity_improves_and_caps_at_one_hundred() -> None:
    familiarity = TacticalFamiliarity(
        tactic_values={"t1": 95},
        role_values={"advanced_forward": 92},
    )

    assert familiarity.improve_tactic("t1", 10) == 100
    assert familiarity.improve_role("advanced_forward", 20) == 100


def test_tactical_familiarity_rejects_negative_improvement() -> None:
    familiarity = TacticalFamiliarity()

    with pytest.raises(ValueError):
        familiarity.improve_role("advanced_forward", -1)


def test_direct_tactic_construction_requires_roles_for_all_formation_slots() -> None:
    formation = make_formation()

    with pytest.raises(ValueError, match="roles do not match formation"):
        Tactic(
            tactic_id="bad",
            name="Bad",
            formation=formation,
            preset_origin=TacticalPreset.CUSTOM,
            team_instructions=instructions_for_preset(TacticalPreset.CUSTOM),
            role_assignments={},
        )


def test_preset_factory_returns_independent_instruction_objects() -> None:
    first = instructions_for_preset(TacticalPreset.TIKI_TAKA)
    second = instructions_for_preset(TacticalPreset.TIKI_TAKA)

    modified_first = replace(
        first,
        in_possession=replace(first.in_possession, tempo=Level.VERY_LOW),
    )

    assert modified_first.in_possession.tempo is Level.VERY_LOW
    assert second.in_possession.tempo is Level.NORMAL


def test_in_and_out_of_possession_shapes_are_independent() -> None:
    tactic = Tactic.from_preset(
        "shape-split",
        "Wide build-up, narrow defence",
        make_formation(),
        TacticalPreset.CUSTOM,
    )

    tactic.update_in_possession(
        defensive_line_width=Level.VERY_HIGH,
        midfield_width=Level.HIGH,
        attacking_line_width=Level.HIGH,
        defense_midfield_gap=Level.NORMAL,
        midfield_attack_gap=Level.HIGH,
    )
    tactic.update_out_of_possession(
        defensive_line_width=Level.VERY_LOW,
        midfield_width=Level.LOW,
        attacking_line_width=Level.LOW,
        defense_midfield_gap=Level.VERY_LOW,
        midfield_attack_gap=Level.VERY_LOW,
        protect_centre=Level.VERY_HIGH,
        cross_tolerance=Level.VERY_HIGH,
    )

    assert tactic.team_instructions.in_possession.defensive_line_width is Level.VERY_HIGH
    assert tactic.team_instructions.out_of_possession.defensive_line_width is Level.VERY_LOW
    assert tactic.team_instructions.in_possession.midfield_attack_gap is Level.HIGH
    assert tactic.team_instructions.out_of_possession.midfield_attack_gap is Level.VERY_LOW


def test_style_analyzer_detects_wide_build_up_and_narrow_defensive_block() -> None:
    tactic = Tactic.from_preset(
        "shape-style",
        "Open with ball, close without it",
        make_formation(),
        TacticalPreset.CUSTOM,
    )
    tactic.update_in_possession(
        defensive_line_width=Level.VERY_HIGH,
        midfield_width=Level.HIGH,
        attacking_line_width=Level.HIGH,
    )
    tactic.update_out_of_possession(
        defensive_line_width=Level.VERY_LOW,
        midfield_width=Level.LOW,
        attacking_line_width=Level.LOW,
        horizontal_compactness=Level.VERY_HIGH,
        vertical_compactness=Level.VERY_HIGH,
        defense_midfield_gap=Level.VERY_LOW,
        midfield_attack_gap=Level.VERY_LOW,
        protect_box=Level.VERY_HIGH,
        protect_centre=Level.VERY_HIGH,
        cross_tolerance=Level.VERY_HIGH,
    )

    analysis = tactic.analyze_style()

    assert analysis.label == "Salida ancha + bloque defensivo compacto"
    assert analysis.in_possession_width > analysis.out_of_possession_width
    assert analysis.central_protection == 100
    assert analysis.cross_tolerance == 100


def test_deep_defensive_presets_protect_centre_and_accept_crosses() -> None:
    catenaccio = instructions_for_preset(TacticalPreset.CATENACCIO)
    low_block = instructions_for_preset(TacticalPreset.LOW_BLOCK)

    for instructions in (catenaccio, low_block):
        defensive = instructions.out_of_possession
        assert defensive.defensive_line_width is Level.VERY_LOW
        assert defensive.midfield_width is Level.LOW
        assert defensive.protect_centre is Level.VERY_HIGH
        assert defensive.cross_tolerance is Level.VERY_HIGH


def test_style_analysis_exposes_phase_width_and_defensive_compactness() -> None:
    tactic = Tactic.from_preset(
        "metrics",
        "Metrics",
        make_formation(),
        TacticalPreset.CUSTOM,
    )
    tactic.update_in_possession(
        defensive_line_width=Level.HIGH,
        midfield_width=Level.HIGH,
        attacking_line_width=Level.VERY_HIGH,
    )
    tactic.update_out_of_possession(
        defensive_line_width=Level.LOW,
        midfield_width=Level.LOW,
        attacking_line_width=Level.LOW,
        horizontal_compactness=Level.VERY_HIGH,
        vertical_compactness=Level.VERY_HIGH,
        defense_midfield_gap=Level.VERY_LOW,
        midfield_attack_gap=Level.LOW,
        protect_box=Level.HIGH,
        protect_centre=Level.VERY_HIGH,
        cross_tolerance=Level.HIGH,
    )

    analysis = tactic.analyze_style()

    assert analysis.width == analysis.in_possession_width
    assert analysis.in_possession_width > 80
    assert analysis.out_of_possession_width == 25
    assert analysis.defensive_compactness >= 90
    assert analysis.central_protection >= 87
    assert analysis.cross_tolerance == 75
