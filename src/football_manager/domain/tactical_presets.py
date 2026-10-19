from __future__ import annotations

from enum import StrEnum

from .tactical_instructions import (
    AfterLossBehavior,
    AfterWinBehavior,
    ForceDirection,
    GameManagementInstructions,
    InPossessionInstructions,
    Level,
    MarkingStyle,
    OutOfPossessionInstructions,
    PassLength,
    PressingScheme,
    TeamInstructions,
    TransitionInstructions,
)


class TacticalPreset(StrEnum):
    BALANCED = "balanced"
    TIKI_TAKA = "tiki_taka"
    POSSESSION = "possession"
    CONSTANT_PRESS = "constant_press"
    COUNTERPRESS = "counterpress"
    COUNTER_ATTACK = "counter_attack"
    DIRECT_COUNTER = "direct_counter"
    CATENACCIO = "catenaccio"
    LOW_BLOCK = "low_block"
    DIRECT_PLAY = "direct_play"
    WIDE_ATTACK = "wide_attack"
    CUSTOM = "custom"


def instructions_for_preset(preset: TacticalPreset) -> TeamInstructions:
    if preset in (TacticalPreset.BALANCED, TacticalPreset.CUSTOM):
        return TeamInstructions()

    if preset is TacticalPreset.TIKI_TAKA:
        return TeamInstructions(
            in_possession=InPossessionInstructions(
                defensive_line_width=Level.NORMAL,
                midfield_width=Level.NORMAL,
                attacking_line_width=Level.NORMAL,
                defense_midfield_gap=Level.LOW,
                midfield_attack_gap=Level.LOW,
                tempo=Level.NORMAL,
                pass_speed=Level.HIGH,
                pass_length=PassLength.VERY_SHORT,
                verticality=Level.LOW,
                passing_risk=Level.NORMAL,
                build_from_back=Level.VERY_HIGH,
                support_closeness=Level.VERY_HIGH,
                switch_play=Level.NORMAL,
                central_focus=Level.HIGH,
                overlap_frequency=Level.NORMAL,
                patience=Level.HIGH,
                crossing_frequency=Level.LOW,
                long_shot_frequency=Level.LOW,
            ),
            transition=TransitionInstructions(
                after_loss=AfterLossBehavior.COUNTERPRESS,
                after_win=AfterWinBehavior.HOLD_POSSESSION,
                transition_speed=Level.NORMAL,
                counterattack_risk=Level.LOW,
                goalkeeper_release_speed=Level.NORMAL,
            ),
            out_of_possession=OutOfPossessionInstructions(
                defensive_line_width=Level.LOW,
                midfield_width=Level.LOW,
                attacking_line_width=Level.NORMAL,
                defense_midfield_gap=Level.LOW,
                midfield_attack_gap=Level.LOW,
                block_height=Level.HIGH,
                defensive_line_height=Level.HIGH,
                horizontal_compactness=Level.HIGH,
                vertical_compactness=Level.VERY_HIGH,
                pressing_intensity=Level.HIGH,
                pressing_scheme=PressingScheme.ZONAL,
                marking_style=MarkingStyle.ZONAL,
                offside_trap=True,
                defensive_aggression=Level.NORMAL,
                protect_box=Level.NORMAL,
            ),
        )

    if preset is TacticalPreset.POSSESSION:
        return TeamInstructions(
            in_possession=InPossessionInstructions(
                defense_midfield_gap=Level.LOW,
                midfield_attack_gap=Level.LOW,
                tempo=Level.LOW,
                pass_speed=Level.NORMAL,
                pass_length=PassLength.SHORT,
                verticality=Level.LOW,
                passing_risk=Level.LOW,
                build_from_back=Level.VERY_HIGH,
                support_closeness=Level.VERY_HIGH,
                switch_play=Level.HIGH,
                patience=Level.VERY_HIGH,
                crossing_frequency=Level.LOW,
                long_shot_frequency=Level.VERY_LOW,
            ),
            transition=TransitionInstructions(
                after_loss=AfterLossBehavior.HOLD_SHAPE,
                after_win=AfterWinBehavior.HOLD_POSSESSION,
                transition_speed=Level.LOW,
                counterattack_risk=Level.VERY_LOW,
                goalkeeper_release_speed=Level.LOW,
            ),
            out_of_possession=OutOfPossessionInstructions(
                defensive_line_width=Level.NORMAL,
                midfield_width=Level.NORMAL,
                attacking_line_width=Level.NORMAL,
                defense_midfield_gap=Level.LOW,
                midfield_attack_gap=Level.LOW,
                block_height=Level.NORMAL,
                defensive_line_height=Level.NORMAL,
                horizontal_compactness=Level.HIGH,
                vertical_compactness=Level.HIGH,
                pressing_intensity=Level.NORMAL,
                pressing_scheme=PressingScheme.ZONAL,
                marking_style=MarkingStyle.ZONAL,
            ),
        )

    if preset is TacticalPreset.CONSTANT_PRESS:
        return TeamInstructions(
            in_possession=InPossessionInstructions(
                defense_midfield_gap=Level.LOW,
                midfield_attack_gap=Level.LOW,
                tempo=Level.HIGH,
                pass_speed=Level.HIGH,
                verticality=Level.HIGH,
                passing_risk=Level.HIGH,
                support_closeness=Level.HIGH,
            ),
            transition=TransitionInstructions(
                after_loss=AfterLossBehavior.COUNTERPRESS,
                after_win=AfterWinBehavior.COUNTER,
                transition_speed=Level.VERY_HIGH,
                counterattack_risk=Level.HIGH,
                goalkeeper_release_speed=Level.HIGH,
            ),
            out_of_possession=OutOfPossessionInstructions(
                defensive_line_width=Level.NORMAL,
                midfield_width=Level.NORMAL,
                attacking_line_width=Level.NORMAL,
                defense_midfield_gap=Level.VERY_LOW,
                midfield_attack_gap=Level.VERY_LOW,
                block_height=Level.VERY_HIGH,
                defensive_line_height=Level.HIGH,
                horizontal_compactness=Level.HIGH,
                vertical_compactness=Level.VERY_HIGH,
                pressing_intensity=Level.VERY_HIGH,
                pressing_scheme=PressingScheme.CONSTANT,
                marking_style=MarkingStyle.MIXED,
                offside_trap=True,
                defensive_aggression=Level.HIGH,
                protect_box=Level.LOW,
            ),
        )

    if preset is TacticalPreset.COUNTERPRESS:
        return TeamInstructions(
            in_possession=InPossessionInstructions(
                defense_midfield_gap=Level.LOW,
                midfield_attack_gap=Level.LOW,
                tempo=Level.HIGH,
                pass_speed=Level.HIGH,
                pass_length=PassLength.MIXED,
                verticality=Level.HIGH,
                passing_risk=Level.HIGH,
                support_closeness=Level.HIGH,
            ),
            transition=TransitionInstructions(
                after_loss=AfterLossBehavior.COUNTERPRESS,
                after_win=AfterWinBehavior.COUNTER,
                transition_speed=Level.VERY_HIGH,
                counterattack_risk=Level.HIGH,
                goalkeeper_release_speed=Level.HIGH,
            ),
            out_of_possession=OutOfPossessionInstructions(
                defensive_line_width=Level.LOW,
                midfield_width=Level.LOW,
                attacking_line_width=Level.NORMAL,
                defense_midfield_gap=Level.LOW,
                midfield_attack_gap=Level.LOW,
                block_height=Level.HIGH,
                defensive_line_height=Level.HIGH,
                horizontal_compactness=Level.HIGH,
                vertical_compactness=Level.VERY_HIGH,
                pressing_intensity=Level.VERY_HIGH,
                pressing_scheme=PressingScheme.MAN_ORIENTED,
                marking_style=MarkingStyle.MIXED,
                defensive_aggression=Level.HIGH,
            ),
        )

    if preset is TacticalPreset.COUNTER_ATTACK:
        return TeamInstructions(
            in_possession=InPossessionInstructions(
                defensive_line_width=Level.NORMAL,
                midfield_width=Level.NORMAL,
                attacking_line_width=Level.HIGH,
                defense_midfield_gap=Level.NORMAL,
                midfield_attack_gap=Level.HIGH,
                tempo=Level.HIGH,
                pass_speed=Level.HIGH,
                pass_length=PassLength.LONG,
                verticality=Level.VERY_HIGH,
                passing_risk=Level.HIGH,
                build_from_back=Level.LOW,
                support_closeness=Level.LOW,
                switch_play=Level.HIGH,
                patience=Level.VERY_LOW,
            ),
            transition=TransitionInstructions(
                after_loss=AfterLossBehavior.REGROUP,
                after_win=AfterWinBehavior.COUNTER,
                transition_speed=Level.VERY_HIGH,
                counterattack_risk=Level.HIGH,
                goalkeeper_release_speed=Level.VERY_HIGH,
            ),
            out_of_possession=OutOfPossessionInstructions(
                defensive_line_width=Level.LOW,
                midfield_width=Level.LOW,
                attacking_line_width=Level.NORMAL,
                defense_midfield_gap=Level.LOW,
                midfield_attack_gap=Level.LOW,
                block_height=Level.LOW,
                defensive_line_height=Level.LOW,
                horizontal_compactness=Level.HIGH,
                vertical_compactness=Level.HIGH,
                pressing_intensity=Level.LOW,
                pressing_scheme=PressingScheme.ZONAL,
                marking_style=MarkingStyle.ZONAL,
                protect_box=Level.HIGH,
                protect_centre=Level.HIGH,
                cross_tolerance=Level.HIGH,
            ),
        )

    if preset is TacticalPreset.DIRECT_COUNTER:
        return TeamInstructions(
            in_possession=InPossessionInstructions(
                attacking_line_width=Level.HIGH,
                defense_midfield_gap=Level.NORMAL,
                midfield_attack_gap=Level.VERY_HIGH,
                tempo=Level.VERY_HIGH,
                pass_speed=Level.VERY_HIGH,
                pass_length=PassLength.VERY_LONG,
                verticality=Level.VERY_HIGH,
                passing_risk=Level.VERY_HIGH,
                build_from_back=Level.VERY_LOW,
                support_closeness=Level.VERY_LOW,
                switch_play=Level.HIGH,
                patience=Level.VERY_LOW,
                crossing_frequency=Level.HIGH,
            ),
            transition=TransitionInstructions(
                after_loss=AfterLossBehavior.REGROUP,
                after_win=AfterWinBehavior.DIRECT,
                transition_speed=Level.VERY_HIGH,
                counterattack_risk=Level.VERY_HIGH,
                goalkeeper_release_speed=Level.VERY_HIGH,
            ),
            out_of_possession=OutOfPossessionInstructions(
                defensive_line_width=Level.LOW,
                midfield_width=Level.LOW,
                attacking_line_width=Level.NORMAL,
                defense_midfield_gap=Level.LOW,
                midfield_attack_gap=Level.LOW,
                block_height=Level.LOW,
                defensive_line_height=Level.LOW,
                horizontal_compactness=Level.HIGH,
                vertical_compactness=Level.HIGH,
                pressing_intensity=Level.LOW,
                pressing_scheme=PressingScheme.ZONAL,
                protect_box=Level.HIGH,
            ),
        )

    if preset is TacticalPreset.CATENACCIO:
        return TeamInstructions(
            in_possession=InPossessionInstructions(
                defensive_line_width=Level.LOW,
                midfield_width=Level.LOW,
                attacking_line_width=Level.NORMAL,
                defense_midfield_gap=Level.VERY_LOW,
                midfield_attack_gap=Level.LOW,
                tempo=Level.LOW,
                pass_speed=Level.LOW,
                pass_length=PassLength.LONG,
                verticality=Level.HIGH,
                passing_risk=Level.LOW,
                build_from_back=Level.LOW,
                support_closeness=Level.HIGH,
                patience=Level.NORMAL,
                crossing_frequency=Level.NORMAL,
            ),
            transition=TransitionInstructions(
                after_loss=AfterLossBehavior.REGROUP,
                after_win=AfterWinBehavior.COUNTER,
                transition_speed=Level.HIGH,
                counterattack_risk=Level.NORMAL,
                goalkeeper_release_speed=Level.LOW,
            ),
            out_of_possession=OutOfPossessionInstructions(
                defensive_line_width=Level.VERY_LOW,
                midfield_width=Level.LOW,
                attacking_line_width=Level.LOW,
                defense_midfield_gap=Level.VERY_LOW,
                midfield_attack_gap=Level.VERY_LOW,
                block_height=Level.VERY_LOW,
                defensive_line_height=Level.LOW,
                horizontal_compactness=Level.VERY_HIGH,
                vertical_compactness=Level.VERY_HIGH,
                pressing_intensity=Level.LOW,
                pressing_scheme=PressingScheme.MAN_ORIENTED,
                force_direction=ForceDirection.OUTSIDE,
                marking_style=MarkingStyle.MIXED,
                offside_trap=False,
                defensive_aggression=Level.HIGH,
                protect_box=Level.VERY_HIGH,
                protect_centre=Level.VERY_HIGH,
                cross_tolerance=Level.VERY_HIGH,
            ),
            game_management=GameManagementInstructions(
                time_wasting=Level.HIGH,
                risk_when_leading=Level.VERY_LOW,
                urgency_when_trailing=Level.NORMAL,
            ),
        )

    if preset is TacticalPreset.LOW_BLOCK:
        return TeamInstructions(
            in_possession=InPossessionInstructions(
                defensive_line_width=Level.LOW,
                midfield_width=Level.LOW,
                defense_midfield_gap=Level.VERY_LOW,
                midfield_attack_gap=Level.NORMAL,
                tempo=Level.LOW,
                pass_length=PassLength.MIXED,
                verticality=Level.NORMAL,
                passing_risk=Level.LOW,
                build_from_back=Level.LOW,
                patience=Level.HIGH,
            ),
            transition=TransitionInstructions(
                after_loss=AfterLossBehavior.REGROUP,
                after_win=AfterWinBehavior.PAUSE,
                transition_speed=Level.LOW,
                counterattack_risk=Level.LOW,
                goalkeeper_release_speed=Level.LOW,
            ),
            out_of_possession=OutOfPossessionInstructions(
                defensive_line_width=Level.VERY_LOW,
                midfield_width=Level.LOW,
                attacking_line_width=Level.LOW,
                defense_midfield_gap=Level.VERY_LOW,
                midfield_attack_gap=Level.VERY_LOW,
                block_height=Level.VERY_LOW,
                defensive_line_height=Level.VERY_LOW,
                horizontal_compactness=Level.VERY_HIGH,
                vertical_compactness=Level.VERY_HIGH,
                pressing_intensity=Level.VERY_LOW,
                pressing_scheme=PressingScheme.ZONAL,
                marking_style=MarkingStyle.ZONAL,
                protect_box=Level.VERY_HIGH,
                protect_centre=Level.VERY_HIGH,
                cross_tolerance=Level.VERY_HIGH,
            ),
            game_management=GameManagementInstructions(
                time_wasting=Level.NORMAL,
                risk_when_leading=Level.LOW,
                urgency_when_trailing=Level.HIGH,
            ),
        )

    if preset is TacticalPreset.DIRECT_PLAY:
        return TeamInstructions(
            in_possession=InPossessionInstructions(
                attacking_line_width=Level.HIGH,
                defense_midfield_gap=Level.NORMAL,
                midfield_attack_gap=Level.HIGH,
                tempo=Level.HIGH,
                pass_speed=Level.HIGH,
                pass_length=PassLength.VERY_LONG,
                verticality=Level.VERY_HIGH,
                passing_risk=Level.HIGH,
                build_from_back=Level.VERY_LOW,
                support_closeness=Level.LOW,
                switch_play=Level.HIGH,
                patience=Level.VERY_LOW,
                crossing_frequency=Level.HIGH,
            ),
            transition=TransitionInstructions(
                after_loss=AfterLossBehavior.HOLD_SHAPE,
                after_win=AfterWinBehavior.DIRECT,
                transition_speed=Level.HIGH,
                counterattack_risk=Level.HIGH,
                goalkeeper_release_speed=Level.VERY_HIGH,
            ),
            out_of_possession=OutOfPossessionInstructions(
                pressing_intensity=Level.NORMAL,
                pressing_scheme=PressingScheme.STANDARD,
                marking_style=MarkingStyle.MIXED,
                defensive_aggression=Level.HIGH,
            ),
        )

    if preset is TacticalPreset.WIDE_ATTACK:
        return TeamInstructions(
            in_possession=InPossessionInstructions(
                defensive_line_width=Level.HIGH,
                midfield_width=Level.HIGH,
                attacking_line_width=Level.VERY_HIGH,
                tempo=Level.HIGH,
                pass_speed=Level.HIGH,
                pass_length=PassLength.MIXED,
                verticality=Level.NORMAL,
                passing_risk=Level.NORMAL,
                build_from_back=Level.NORMAL,
                support_closeness=Level.NORMAL,
                switch_play=Level.VERY_HIGH,
                central_focus=Level.VERY_LOW,
                overlap_frequency=Level.VERY_HIGH,
                patience=Level.NORMAL,
                crossing_frequency=Level.VERY_HIGH,
            ),
            transition=TransitionInstructions(
                after_loss=AfterLossBehavior.HOLD_SHAPE,
                after_win=AfterWinBehavior.EXPAND,
                transition_speed=Level.HIGH,
                counterattack_risk=Level.NORMAL,
                goalkeeper_release_speed=Level.NORMAL,
            ),
            out_of_possession=OutOfPossessionInstructions(
                defensive_line_width=Level.NORMAL,
                midfield_width=Level.NORMAL,
                attacking_line_width=Level.NORMAL,
                defense_midfield_gap=Level.NORMAL,
                midfield_attack_gap=Level.NORMAL,
                block_height=Level.NORMAL,
                defensive_line_height=Level.NORMAL,
                horizontal_compactness=Level.NORMAL,
                vertical_compactness=Level.NORMAL,
                pressing_intensity=Level.NORMAL,
                pressing_scheme=PressingScheme.TRAP_INSIDE,
                force_direction=ForceDirection.INSIDE,
                marking_style=MarkingStyle.ZONAL,
            ),
        )

    raise ValueError(f"unsupported tactical preset: {preset}")
