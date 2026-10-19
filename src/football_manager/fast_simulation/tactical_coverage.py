"""Auditable fast-simulator coverage of the existing tactical control schema.

The presence of a field in the UI or in a style description does *not* mean it
has a gameplay effect.  This inventory is deliberately conservative; unknown
fields are reported as not modelled. It does not change the UX.
"""

from __future__ import annotations

from dataclasses import dataclass, fields

from football_manager.domain.tactical_instructions import (
    GameManagementInstructions,
    InPossessionInstructions,
    OutOfPossessionInstructions,
    PlayerInstructions,
    TransitionInstructions,
)


# Field keys use the public group/field names of TeamInstructions.
_FAST_TEAM_FIELDS = frozenset({
    "in_possession.defensive_line_width",
    "in_possession.midfield_width",
    "in_possession.attacking_line_width",
    "in_possession.tempo",
    "in_possession.pass_speed",
    "in_possession.pass_length",
    "in_possession.verticality",
    "in_possession.passing_risk",
    "in_possession.build_from_back",
    "in_possession.support_closeness",
    "in_possession.patience",
    "in_possession.crossing_frequency",
    "transition.after_loss",
    "transition.after_win",
    "transition.transition_speed",
    "transition.counterattack_risk",
    "out_of_possession.defense_midfield_gap",
    "out_of_possession.midfield_attack_gap",
    "out_of_possession.block_height",
    "out_of_possession.defensive_line_height",
    "out_of_possession.horizontal_compactness",
    "out_of_possession.vertical_compactness",
    "out_of_possession.pressing_intensity",
    "out_of_possession.pressing_scheme",
    "out_of_possession.protect_box",
    "out_of_possession.protect_centre",
    "out_of_possession.cross_tolerance",
    "out_of_possession.defensive_aggression",
    "out_of_possession.offside_trap",
})
# These existing controls respond to score state rather than granting a
# pre-match bonus. Other instructions deliberately remain out of scope.
_PARTIAL_TEAM_FIELDS = frozenset({
    "game_management.time_wasting", "game_management.urgency_when_trailing",
    "game_management.risk_when_leading",
})
_LABEL_ONLY_TEAM_FIELDS = frozenset({"out_of_possession.defensive_line_width"})

_PHYSICAL_LOAD_PLAYER_FIELDS = frozenset({
    "forward_runs", "pressing_intensity", "defensive_tracking", "roaming",
})

# A deliberate backlog, not an implicit fallback: any new tactical field needs
# an explicit decision here or in one of the consumer sets above.
_NOT_MODELLED_TEAM_FIELDS = frozenset({
    "in_possession.defense_midfield_gap",
    "in_possession.midfield_attack_gap",
    "in_possession.switch_play",
    "in_possession.central_focus",
    "in_possession.overlap_frequency",
    "in_possession.long_shot_frequency",
    "transition.goalkeeper_release_speed",
    "out_of_possession.midfield_width",
    "out_of_possession.attacking_line_width",
    "out_of_possession.force_direction",
    "out_of_possession.marking_style",
})
_NOT_MODELLED_PLAYER_FIELDS = frozenset({
    "dribbling_frequency", "crossing_frequency", "shooting_frequency",
    "passing_risk", "hold_up_play", "attack_space", "in_possession_position",
    "out_of_possession_position", "cross_type", "marking", "pressing_target",
})


# TS-19 adds real consumers, with bounded tradeoffs documented in
# tactical_effects.py and tactical_geometry.py. Score-sensitive management
# remains conditional. Retain the explicit inventory so future controls cannot
# silently claim support. Physical effects of runs/tracking/roaming are retained.
_FAST_TEAM_FIELDS = _FAST_TEAM_FIELDS | _NOT_MODELLED_TEAM_FIELDS | _LABEL_ONLY_TEAM_FIELDS
_FAST_PLAYER_FIELDS = _NOT_MODELLED_PLAYER_FIELDS
_NOT_MODELLED_TEAM_FIELDS = frozenset()
_NOT_MODELLED_PLAYER_FIELDS = frozenset()
_LABEL_ONLY_TEAM_FIELDS = frozenset()


@dataclass(frozen=True, slots=True)
class TacticalConsumerEntry:
    control: str
    status: str


def tactical_consumer_coverage() -> tuple[TacticalConsumerEntry, ...]:
    """Return the fast-engine coverage of every declared tactical instruction.

    Status meanings:
      - match_effect: changes fast-simulator gameplay or collective statistics
      - partial_match_effect: only specific intensities and score states matter
      - player_conditioning: changes player workload / match-end physical state
      - style_label_only: visible in a description, not in fast calculations
      - not_modelled: no confirmed fast-simulator consumer
    """
    groups = (
        ("in_possession", InPossessionInstructions),
        ("transition", TransitionInstructions),
        ("out_of_possession", OutOfPossessionInstructions),
        ("game_management", GameManagementInstructions),
    )
    result: list[TacticalConsumerEntry] = []
    for prefix, schema in groups:
        for field in fields(schema):
            name = f"{prefix}.{field.name}"
            if name in _FAST_TEAM_FIELDS:
                status = "match_effect"
            elif name in _PARTIAL_TEAM_FIELDS:
                status = "partial_match_effect"
            elif name in _LABEL_ONLY_TEAM_FIELDS:
                status = "style_label_only"
            elif name in _NOT_MODELLED_TEAM_FIELDS:
                status = "not_modelled"
            else:
                raise ValueError(f"unclassified team tactical control: {name}")
            result.append(TacticalConsumerEntry(name, status))
    for field in fields(PlayerInstructions):
        if field.name in _PHYSICAL_LOAD_PLAYER_FIELDS:
            status = "player_conditioning"
        elif field.name in _FAST_PLAYER_FIELDS:
            status = "match_effect"
        elif field.name in _NOT_MODELLED_PLAYER_FIELDS:
            status = "not_modelled"
        else:
            raise ValueError(f"unclassified player tactical control: {field.name}")
        result.append(TacticalConsumerEntry(f"player.{field.name}", status))
    return tuple(result)
