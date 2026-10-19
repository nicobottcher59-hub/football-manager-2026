from __future__ import annotations

from dataclasses import dataclass, field, replace

from .formation import Formation
from .tactical_shapes import PHASES, PhaseShape, SlotPoint, validate_shapes
from .roles import default_role_for_position, get_role
from .tactical_instructions import (
    AfterLossBehavior,
    AfterWinBehavior,
    Level,
    PlayerInstructionOverrides,
    PlayerInstructions,
    TeamInstructions,
    apply_player_overrides,
)
from .tactical_presets import TacticalPreset, instructions_for_preset


@dataclass(frozen=True, slots=True)
class RoleAssignment:
    role_id: str
    overrides: PlayerInstructionOverrides = PlayerInstructionOverrides()

    def __post_init__(self) -> None:
        if not self.role_id.strip():
            raise ValueError("role_id cannot be empty")
        get_role(self.role_id)


@dataclass(frozen=True, slots=True)
class TacticalStyleAnalysis:
    label: str
    possession: float
    pressing: float
    directness: float
    defensive_depth: float
    tempo: float
    width: float
    risk: float
    in_possession_width: float
    out_of_possession_width: float
    defensive_compactness: float
    central_protection: float
    cross_tolerance: float


@dataclass(slots=True)
class Tactic:
    tactic_id: str
    name: str
    formation: Formation
    preset_origin: TacticalPreset
    team_instructions: TeamInstructions
    role_assignments: dict[str, RoleAssignment] = field(default_factory=dict)
    phase_shapes: tuple[PhaseShape, ...] = ()

    def __post_init__(self) -> None:
        if not self.tactic_id.strip():
            raise ValueError("tactic_id cannot be empty")
        if not self.name.strip():
            raise ValueError("tactic name cannot be empty")
        if not isinstance(self.preset_origin, TacticalPreset):
            self.preset_origin = TacticalPreset(self.preset_origin)
        self._validate_role_assignments()
        validate_shapes(self.phase_shapes, self.formation.slot_ids)

    @classmethod
    def from_preset(
        cls,
        tactic_id: str,
        name: str,
        formation: Formation,
        preset: TacticalPreset,
    ) -> Tactic:
        assignments = {
            slot.slot_id: RoleAssignment(default_role_for_position(slot.position).role_id)
            for slot in formation.slots
        }
        return cls(
            tactic_id=tactic_id,
            name=name,
            formation=formation,
            preset_origin=preset,
            team_instructions=instructions_for_preset(preset),
            role_assignments=assignments,
        )

    def _validate_role_assignments(self) -> None:
        expected = self.formation.slot_ids
        actual = frozenset(self.role_assignments)
        if expected != actual:
            missing = expected - actual
            unknown = actual - expected
            details: list[str] = []
            if missing:
                details.append(f"missing role slots: {sorted(missing)}")
            if unknown:
                details.append(f"unknown role slots: {sorted(unknown)}")
            raise ValueError("tactic roles do not match formation (" + "; ".join(details) + ")")

        for slot_id, assignment in self.role_assignments.items():
            position = self.formation.slot(slot_id).position
            role = get_role(assignment.role_id)
            if not role.supports(position):
                raise ValueError(
                    f"role {assignment.role_id!r} is not compatible with "
                    f"slot {slot_id!r} ({position.value})"
                )

    def set_role(
        self,
        slot_id: str,
        role_id: str,
        overrides: PlayerInstructionOverrides | None = None,
    ) -> None:
        position = self.formation.slot(slot_id).position
        role = get_role(role_id)
        if not role.supports(position):
            raise ValueError(
                f"role {role_id!r} is not compatible with slot {slot_id!r} ({position.value})"
            )
        self.role_assignments[slot_id] = RoleAssignment(
            role_id=role_id,
            overrides=overrides or PlayerInstructionOverrides(),
        )

    def set_player_overrides(
        self,
        slot_id: str,
        overrides: PlayerInstructionOverrides,
    ) -> None:
        self.formation.slot(slot_id)
        current = self.role_assignments[slot_id]
        self.role_assignments[slot_id] = RoleAssignment(current.role_id, overrides)

    def role_for_slot(self, slot_id: str):
        self.formation.slot(slot_id)
        return get_role(self.role_assignments[slot_id].role_id)

    def effective_player_instructions(self, slot_id: str) -> PlayerInstructions:
        assignment = self.role_assignments[slot_id]
        role = self.role_for_slot(slot_id)
        return apply_player_overrides(role.default_instructions, assignment.overrides)

    def update_in_possession(self, **changes: object) -> None:
        updated = replace(self.team_instructions.in_possession, **changes)
        self.team_instructions = replace(self.team_instructions, in_possession=updated)

    def update_transition(self, **changes: object) -> None:
        updated = replace(self.team_instructions.transition, **changes)
        self.team_instructions = replace(self.team_instructions, transition=updated)

    def update_out_of_possession(self, **changes: object) -> None:
        updated = replace(self.team_instructions.out_of_possession, **changes)
        self.team_instructions = replace(self.team_instructions, out_of_possession=updated)

    def update_game_management(self, **changes: object) -> None:
        updated = replace(self.team_instructions.game_management, **changes)
        self.team_instructions = replace(self.team_instructions, game_management=updated)

    def set_phase_point(self, phase: str, slot_id: str, x: float | None, y: float | None) -> None:
        """Set an explicit spatial target; None restores automatic positioning."""
        if phase not in PHASES:
            raise ValueError("unknown tactical phase")
        self.formation.slot(slot_id)
        points = {p.slot_id: p for shape in self.phase_shapes if shape.phase == phase for p in shape.points}
        if x is None and y is None:
            points.pop(slot_id, None)
        elif x is None or y is None:
            raise ValueError("both tactical coordinates are required")
        else:
            points[slot_id] = SlotPoint(slot_id, x, y)
        self.replace_phase_shape(phase, tuple(points[k] for k in sorted(points)))

    def replace_phase_shape(self, phase: str, points: tuple[SlotPoint, ...]) -> None:
        shape = PhaseShape(phase, points)
        candidate = tuple(s for s in self.phase_shapes if s.phase != phase)
        if points:
            candidate += (shape,)
        candidate = tuple(sorted(candidate, key=lambda s: s.phase))
        validate_shapes(candidate, self.formation.slot_ids)
        self.phase_shapes = candidate

    def analyze_style(self) -> TacticalStyleAnalysis:
        return analyze_tactical_style(self.team_instructions)


def _mean(*values: float) -> float:
    return sum(values) / len(values)


def analyze_tactical_style(instructions: TeamInstructions) -> TacticalStyleAnalysis:
    in_possession = instructions.in_possession
    transition = instructions.transition
    out_of_possession = instructions.out_of_possession
    management = instructions.game_management

    possession = _mean(
        100.0 - float(in_possession.pass_length),
        float(in_possession.build_from_back),
        float(in_possession.patience),
        float(in_possession.support_closeness),
        100.0 - float(in_possession.verticality),
    )

    after_loss_press = {
        AfterLossBehavior.COUNTERPRESS: 100.0,
        AfterLossBehavior.HOLD_SHAPE: 50.0,
        AfterLossBehavior.REGROUP: 0.0,
    }[transition.after_loss]
    scheme_bonus = 100.0 if out_of_possession.pressing_scheme.value == "constant" else 50.0
    pressing = _mean(
        float(out_of_possession.pressing_intensity),
        after_loss_press,
        scheme_bonus,
    )

    after_win_directness = {
        AfterWinBehavior.DIRECT: 100.0,
        AfterWinBehavior.COUNTER: 85.0,
        AfterWinBehavior.EXPAND: 60.0,
        AfterWinBehavior.PAUSE: 25.0,
        AfterWinBehavior.HOLD_POSSESSION: 0.0,
    }[transition.after_win]
    directness = _mean(
        float(in_possession.pass_length),
        float(in_possession.verticality),
        after_win_directness,
        100.0 - float(in_possession.patience),
    )

    defensive_depth = _mean(
        float(out_of_possession.block_height),
        float(out_of_possession.defensive_line_height),
    )
    tempo = _mean(
        float(in_possession.tempo),
        float(in_possession.pass_speed),
        float(transition.transition_speed),
    )
    in_possession_width = _mean(
        float(in_possession.defensive_line_width),
        float(in_possession.midfield_width),
        float(in_possession.attacking_line_width),
    )
    out_of_possession_width = _mean(
        float(out_of_possession.defensive_line_width),
        float(out_of_possession.midfield_width),
        float(out_of_possession.attacking_line_width),
    )
    defensive_compactness = _mean(
        float(out_of_possession.horizontal_compactness),
        float(out_of_possession.vertical_compactness),
        100.0 - float(out_of_possession.defense_midfield_gap),
        100.0 - float(out_of_possession.midfield_attack_gap),
    )
    central_protection = _mean(
        float(out_of_possession.protect_box),
        float(out_of_possession.protect_centre),
    )
    cross_tolerance = float(out_of_possession.cross_tolerance)
    # Keep ``width`` as the backwards-compatible headline width metric. It
    # describes the shape with the ball; defensive width is exposed separately.
    width = in_possession_width
    # A conditional instruction cannot change the pre-match/base risk. The
    # existing three-factor average is retained, with a neutral management
    # value until the team actually takes the lead.
    risk = _mean(
        float(in_possession.passing_risk),
        float(transition.counterattack_risk),
        float(Level.NORMAL),
    )

    if defensive_depth <= 30 and float(management.time_wasting) >= float(Level.HIGH):
        label = "Defensa profunda + ralentizar el partido"
    elif (
        float(in_possession.defensive_line_width) >= float(Level.HIGH)
        and float(out_of_possession.defensive_line_width) <= float(Level.LOW)
        and central_protection >= 75
    ):
        label = "Salida ancha + bloque defensivo compacto"
    elif pressing >= 70 and possession >= 65:
        label = "Presion alta + posesion"
    elif pressing >= 70 and directness >= 65:
        label = "Presion intensa + juego vertical"
    elif possession >= 70 and tempo <= 45:
        label = "Posesion paciente + control del ritmo"
    elif defensive_depth <= 35 and directness >= 65:
        label = "Defensa profunda + contraataque directo"
    elif width >= 70 and float(in_possession.crossing_frequency) >= float(Level.HIGH):
        label = "Ataque por bandas + amplitud"
    elif directness >= 70 and width >= 55:
        label = "Juego directo + amplitud"
    elif directness >= 70:
        label = "Juego directo"
    elif pressing >= 70:
        label = "Presion intensa"
    elif possession >= 65:
        label = "Posesion de pelota"
    elif defensive_depth <= 35:
        label = "Bloque bajo"
    else:
        label = "Equilibrada"

    return TacticalStyleAnalysis(
        label=label,
        possession=possession,
        pressing=pressing,
        directness=directness,
        defensive_depth=defensive_depth,
        tempo=tempo,
        width=width,
        risk=risk,
        in_possession_width=in_possession_width,
        out_of_possession_width=out_of_possession_width,
        defensive_compactness=defensive_compactness,
        central_protection=central_protection,
        cross_tolerance=cross_tolerance,
    )
