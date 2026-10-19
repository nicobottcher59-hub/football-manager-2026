from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from football_manager.domain import (  # noqa: E402
    Formation,
    FormationSlot,
    InPossessionPosition,
    Level,
    OutOfPossessionPosition,
    PlayerInstructionOverrides,
    Position,
    TacticalPreset,
    TacticalTarget,
    TargetKind,
    Tactic,
)


def make_433() -> Formation:
    return Formation(
        formation_id="4-3-3-demo",
        name="4-3-3 Demo",
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


def level_name(value: Level) -> str:
    labels = {
        Level.VERY_LOW: "Muy bajo",
        Level.LOW: "Bajo",
        Level.NORMAL: "Normal",
        Level.HIGH: "Alto",
        Level.VERY_HIGH: "Muy alto",
    }
    return labels[value]


def show_team_tactic(tactic: Tactic) -> None:
    analysis = tactic.analyze_style()
    possession = tactic.team_instructions.in_possession
    transition = tactic.team_instructions.transition
    defending = tactic.team_instructions.out_of_possession

    print(f"TACTICA: {tactic.name}")
    print(f"Preset de origen: {tactic.preset_origin.value}")
    print(f"Estilo detectado: {analysis.label}")
    print()
    print("Equipo")
    print(f"- Ritmo: {level_name(possession.tempo)}")
    print(f"- Velocidad de pase: {level_name(possession.pass_speed)}")
    print(f"- Longitud de pase: {possession.pass_length.name}")
    print(f"- Verticalidad: {level_name(possession.verticality)}")
    print(f"- Presion: {level_name(defending.pressing_intensity)}")
    print(f"- Altura del bloque: {level_name(defending.block_height)}")
    print(f"- Linea defensiva: {level_name(defending.defensive_line_height)}")
    print(f"- Tras perdida: {transition.after_loss.value}")
    print(f"- Tras recuperacion: {transition.after_win.value}")
    print(
        "- Analisis numerico: "
        f"posesion={analysis.possession:.0f}, "
        f"presion={analysis.pressing:.0f}, "
        f"directitud={analysis.directness:.0f}, "
        f"profundidad={analysis.defensive_depth:.0f}, "
        f"ritmo={analysis.tempo:.0f}"
    )


def show_player_instruction_demo(tactic: Tactic) -> None:
    tactic.set_role("lb", "inverted_fullback")
    tactic.set_player_overrides(
        "lb",
        PlayerInstructionOverrides(
            forward_runs=Level.LOW,
            dribbling_frequency=Level.LOW,
            pressing_intensity=Level.HIGH,
            defensive_tracking=Level.VERY_HIGH,
            in_possession_position=InPossessionPosition.MIDFIELD,
            out_of_possession_position=OutOfPossessionPosition.RETURN_TO_BASE,
            marking=TacticalTarget(TargetKind.POSITION, Position.RW.value),
        ),
    )
    tactic.set_role(
        "st",
        "pressing_forward",
        PlayerInstructionOverrides(
            attack_space=Level.VERY_HIGH,
            pressing_intensity=Level.VERY_HIGH,
            pressing_target=TacticalTarget(TargetKind.PLAYER, "opponent-gk"),
        ),
    )

    lb_role = tactic.role_for_slot("lb")
    lb = tactic.effective_player_instructions("lb")
    st_role = tactic.role_for_slot("st")
    st = tactic.effective_player_instructions("st")

    print()
    print("Instrucciones individuales")
    print(f"LI - Rol: {lb_role.name}")
    print(f"- Posicion con pelota: {lb.in_possession_position.value}")
    print(f"- Posicion sin pelota: {lb.out_of_possession_position.value}")
    print(f"- Subidas: {level_name(lb.forward_runs)}")
    print(f"- Regates: {level_name(lb.dribbling_frequency)}")
    print(f"- Presion: {level_name(lb.pressing_intensity)}")
    print(f"- Marca: posicion rival {lb.marking.target_id if lb.marking else '-'}")
    print()
    print(f"DC - Rol: {st_role.name}")
    print(f"- Atacar espacios: {level_name(st.attack_space)}")
    print(f"- Presion: {level_name(st.pressing_intensity)}")
    print(f"- Objetivo de presion: {st.pressing_target.target_id if st.pressing_target else '-'}")


def main() -> None:
    formation = make_433()

    print("=" * 68)
    print("DEMO VISUAL - FASE 3: TACTICAS")
    print("=" * 68)
    print()

    tiki = Tactic.from_preset(
        tactic_id="demo-tiki",
        name="Nico Ball 4-3-3",
        formation=formation,
        preset=TacticalPreset.TIKI_TAKA,
    )
    show_team_tactic(tiki)
    show_player_instruction_demo(tiki)

    print()
    print("-" * 68)
    print()

    defensive = Tactic.from_preset(
        tactic_id="demo-catenaccio",
        name="Cerrar y dormir el partido",
        formation=formation,
        preset=TacticalPreset.CATENACCIO,
    )
    show_team_tactic(defensive)

    print()
    print("Verificacion visual completada: OK")
    print("Nota: esto demuestra configuracion y analisis tactico; aun no simula partidos.")


if __name__ == "__main__":
    main()
