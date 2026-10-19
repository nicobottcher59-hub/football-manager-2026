from __future__ import annotations

from dataclasses import dataclass, replace
import tkinter as tk
from tkinter import ttk

from football_manager.domain import (
    Formation,
    FormationSlot,
    Level,
    MatchSnapshot,
    Position,
    TacticalSlotSnapshot,
    analyze_tactical_style,
    default_role_for_position,
    get_role,
    roles_for_position,
)
from football_manager.simulation import MatchPhase, TacticalLine, TeamSide, Vector2, tactical_line

from .commentary import CommentaryDensity, CommentaryFormatter
from .playback import MatchPlaybackSession, PlaybackSpeed


@dataclass(frozen=True, slots=True)
class PitchProjector:
    width_px: float
    height_px: float
    margin_px: float = 28.0

    def to_canvas(self, pitch_length_m: float, pitch_width_m: float, point: Vector2) -> tuple[float, float]:
        usable_w = max(self.width_px - self.margin_px * 2.0, 1.0)
        usable_h = max(self.height_px - self.margin_px * 2.0, 1.0)
        x = self.margin_px + point.x / pitch_length_m * usable_w
        y = self.margin_px + point.y / pitch_width_m * usable_h
        return x, y

    @property
    def bounds(self) -> tuple[float, float, float, float]:
        return (
            self.margin_px,
            self.margin_px,
            max(self.width_px - self.margin_px, self.margin_px + 1.0),
            max(self.height_px - self.margin_px, self.margin_px + 1.0),
        )


def convex_hull(points: list[tuple[float, float]]) -> list[tuple[float, float]]:
    """Return a deterministic 2D convex hull for debug team-shape outlines."""

    unique = sorted(set(points))
    if len(unique) <= 1:
        return unique

    def cross(o, a, b) -> float:
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    lower: list[tuple[float, float]] = []
    for point in unique:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], point) <= 0:
            lower.pop()
        lower.append(point)

    upper: list[tuple[float, float]] = []
    for point in reversed(unique):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], point) <= 0:
            upper.pop()
        upper.append(point)

    return lower[:-1] + upper[:-1]


class MatchDebugViewer:
    """Small functional 2D/text viewer for Match Engine validation.

    This is intentionally a debugging frontend, not the final game UI. It reads
    the live MatchFlowController through MatchPlaybackSession and never feeds
    presentation state back into simulation.
    """

    # One fixed 0.25 s simulation tick every 25 ms makes x1 roughly 10x real
    # match time: a 90-minute match takes about 9 real minutes.  x2/x4 only
    # consume more of the *same* fixed ticks; they never alter engine precision.
    PULSE_MS = 25
    BASE_TICKS_PER_PULSE = 1
    MAX_COMMENTARY_LINES = 2500

    def __init__(self, root: tk.Tk, snapshot: MatchSnapshot) -> None:
        self.root = root
        self.snapshot = snapshot
        self._original_snapshot = snapshot
        self.session = MatchPlaybackSession(snapshot)
        self.commentary = CommentaryFormatter(snapshot, density=CommentaryDensity.NORMAL)
        self.playing = False
        self.instant_running = False
        self._commentary_line_count = 0

        self.speed_var = tk.StringVar(value="x1")
        self.view_var = tk.StringVar(value="Ambas")
        self.density_var = tk.StringVar(value="Normal")
        self.show_targets = tk.BooleanVar(value=False)
        self.show_pressing = tk.BooleanVar(value=False)
        self.show_coverage = tk.BooleanVar(value=False)
        self.show_lanes = tk.BooleanVar(value=False)
        self.show_shape = tk.BooleanVar(value=False)
        self.show_coordinates = tk.BooleanVar(value=False)
        self.score_var = tk.StringVar()
        self.home_stats_var = tk.StringVar()
        self.away_stats_var = tk.StringVar()
        self.status_var = tk.StringVar()
        self.play_button_var = tk.StringVar(value="Reproducir")

        self._configure_window()
        self._build_ui()
        self._refresh_all()
        self.root.after(self.PULSE_MS, self._pulse)

    def _configure_window(self) -> None:
        self.root.title("Football Manager Game - Phase 5.9 Debug Match Viewer")
        self.root.minsize(1080, 700)
        self.root.geometry("1320x820")

    def _build_ui(self) -> None:
        shell = ttk.Frame(self.root, padding=10)
        shell.pack(fill=tk.BOTH, expand=True)

        header = ttk.Frame(shell)
        header.pack(fill=tk.X, pady=(0, 8))
        ttk.Label(header, textvariable=self.score_var, font=("Segoe UI", 18, "bold")).pack(side=tk.LEFT)
        ttk.Label(header, textvariable=self.status_var).pack(side=tk.RIGHT)

        controls = ttk.Frame(shell)
        controls.pack(fill=tk.X, pady=(0, 8))
        ttk.Button(controls, textvariable=self.play_button_var, command=self._toggle_play).pack(side=tk.LEFT, padx=(0, 6))
        for label, speed in (("x1", PlaybackSpeed.X1), ("x2", PlaybackSpeed.X2), ("x4", PlaybackSpeed.X4)):
            ttk.Radiobutton(
                controls,
                text=label,
                value=label,
                variable=self.speed_var,
                command=lambda value=speed: self._set_speed(value),
            ).pack(side=tk.LEFT)
        ttk.Button(controls, text="Instantáneo", command=self._start_instant).pack(side=tk.LEFT, padx=(8, 6))
        ttk.Button(controls, text="Reiniciar", command=self._restart).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(controls, text="Nueva seed", command=self._new_seed).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(controls, text="Cambios", command=self._open_substitution_dialog).pack(side=tk.LEFT, padx=(0, 14))

        ttk.Label(controls, text="Vista:").pack(side=tk.LEFT)
        view_box = ttk.Combobox(
            controls,
            textvariable=self.view_var,
            values=("Ambas", "2D", "Texto"),
            state="readonly",
            width=8,
        )
        view_box.pack(side=tk.LEFT, padx=(4, 10))
        view_box.bind("<<ComboboxSelected>>", lambda _event: self._apply_view_mode())

        ttk.Label(controls, text="Relato:").pack(side=tk.LEFT)
        density_box = ttk.Combobox(
            controls,
            textvariable=self.density_var,
            values=("Detallado", "Normal", "Solo destacados"),
            state="readonly",
            width=16,
        )
        density_box.pack(side=tk.LEFT, padx=(4, 8))
        density_box.bind("<<ComboboxSelected>>", lambda _event: self._set_density())

        self.tactical_mode_var = tk.StringVar(value="Base")
        ttk.Label(controls, text="Plan HOME:").pack(side=tk.LEFT)
        tactic_box = ttk.Combobox(
            controls,
            textvariable=self.tactical_mode_var,
            values=("Base", "Ofensivo", "Defensivo", "Presión alta"),
            state="readonly",
            width=12,
        )
        tactic_box.pack(side=tk.LEFT, padx=(4, 4))
        ttk.Button(controls, text="Aplicar", command=self._apply_home_tactical_mode).pack(side=tk.LEFT)
        ttk.Button(controls, text="Tactica avanzada", command=self._open_tactical_editor).pack(side=tk.LEFT, padx=(6, 0))

        debug = ttk.LabelFrame(shell, text="Debug overlays", padding=(6, 4))
        debug.pack(fill=tk.X, pady=(0, 8))
        for text, variable in (
            ("Intenciones / targets", self.show_targets),
            ("Presión", self.show_pressing),
            ("Coberturas", self.show_coverage),
            ("Líneas de pase", self.show_lanes),
            ("Forma del equipo", self.show_shape),
            ("Coordenadas", self.show_coordinates),
        ):
            ttk.Checkbutton(debug, text=text, variable=variable, command=self._draw_pitch).pack(side=tk.LEFT, padx=(0, 10))

        self.body = ttk.Frame(shell)
        self.body.pack(fill=tk.BOTH, expand=True)
        self.body.rowconfigure(0, weight=1)
        self.body.columnconfigure(0, weight=3)
        self.body.columnconfigure(1, weight=2)

        self.pitch_panel = ttk.Frame(self.body)
        self.pitch_canvas = tk.Canvas(self.pitch_panel, background="#2e7d32", highlightthickness=0)
        self.pitch_canvas.pack(fill=tk.BOTH, expand=True)
        self.pitch_canvas.bind("<Configure>", lambda _event: self._draw_pitch())

        self.commentary_panel = ttk.Frame(self.body)
        self.commentary_text = tk.Text(
            self.commentary_panel,
            wrap=tk.WORD,
            state=tk.DISABLED,
            font=("Consolas", 10),
            padx=8,
            pady=8,
        )
        scrollbar = ttk.Scrollbar(self.commentary_panel, command=self.commentary_text.yview)
        self.commentary_text.configure(yscrollcommand=scrollbar.set)
        self.commentary_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        stats = ttk.Frame(shell)
        stats.pack(fill=tk.X, pady=(8, 0))
        ttk.Label(stats, textvariable=self.home_stats_var).pack(anchor=tk.W)
        ttk.Label(stats, textvariable=self.away_stats_var).pack(anchor=tk.W)

        self._apply_view_mode()

    def _toggle_play(self) -> None:
        if self.session.is_finished:
            return
        self.playing = not self.playing
        self.play_button_var.set("Pausar" if self.playing else "Reproducir")

    def _set_speed(self, speed: PlaybackSpeed) -> None:
        self.session.set_speed(speed)
        self.speed_var.set(f"x{int(speed)}")
        self._refresh_status()

    def _set_density(self) -> None:
        mapping = {
            "Detallado": CommentaryDensity.DETAILED,
            "Normal": CommentaryDensity.NORMAL,
            "Solo destacados": CommentaryDensity.HIGHLIGHTS,
        }
        self.commentary.set_density(mapping[self.density_var.get()])

    def _apply_view_mode(self) -> None:
        self.pitch_panel.grid_forget()
        self.commentary_panel.grid_forget()
        mode = self.view_var.get()
        if mode == "2D":
            self.pitch_panel.grid(row=0, column=0, columnspan=2, sticky="nsew")
        elif mode == "Texto":
            self.commentary_panel.grid(row=0, column=0, columnspan=2, sticky="nsew")
        else:
            self.pitch_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
            self.commentary_panel.grid(row=0, column=1, sticky="nsew", padx=(6, 0))
        self._draw_pitch()

    def _pulse(self) -> None:
        if self.playing and not self.instant_running and not self.session.is_finished:
            advance = self.session.advance_pulse(base_ticks=self.BASE_TICKS_PER_PULSE)
            self._consume_events(advance.events)
            if advance.finished:
                self.playing = False
                self.play_button_var.set("Reproducir")
            self._refresh_all()
        self.root.after(self.PULSE_MS, self._pulse)

    def _start_instant(self) -> None:
        if self.session.is_finished or self.instant_running:
            return
        self.playing = False
        self.play_button_var.set("Reproducir")
        self.instant_running = True
        self.status_var.set("Simulando el mismo partido sin esperar/renderizar cada tick...")
        self.root.after(1, self._instant_chunk)

    def _instant_chunk(self) -> None:
        if not self.instant_running:
            return
        if self.session.is_finished:
            self.instant_running = False
            self._refresh_all()
            return
        advance = self.session.advance_ticks(512)
        self._consume_events(advance.events)
        if advance.finished:
            self.instant_running = False
            self._refresh_all()
            return
        self._refresh_all()
        self.root.after(1, self._instant_chunk)

    def _restart(self) -> None:
        self.playing = False
        self.instant_running = False
        self.play_button_var.set("Reproducir")
        self._reset_session(self.snapshot)

    def _new_seed(self) -> None:
        self.playing = False
        self.instant_running = False
        self.play_button_var.set("Reproducir")
        self.snapshot = replace(self._original_snapshot, seed=self.session.snapshot.seed + 1)
        self._reset_session(self.snapshot)

    def _reset_session(self, snapshot: MatchSnapshot) -> None:
        current_speed = self.session.speed
        self.session = MatchPlaybackSession(snapshot)
        self.session.set_speed(current_speed)
        self.commentary = CommentaryFormatter(
            snapshot,
            density={
                "Detallado": CommentaryDensity.DETAILED,
                "Normal": CommentaryDensity.NORMAL,
                "Solo destacados": CommentaryDensity.HIGHLIGHTS,
            }[self.density_var.get()],
        )
        self._commentary_line_count = 0
        self.commentary_text.configure(state=tk.NORMAL)
        self.commentary_text.delete("1.0", tk.END)
        self.commentary_text.configure(state=tk.DISABLED)
        self._refresh_all()

    def _open_substitution_dialog(self) -> None:
        if self.session.is_finished:
            return
        self.playing = False
        self.play_button_var.set("Reproducir")
        window = tk.Toplevel(self.root)
        window.title("Cambios - debug")
        window.resizable(False, False)
        frame = ttk.Frame(window, padding=12)
        frame.pack(fill=tk.BOTH, expand=True)

        side_var = tk.StringVar(value="HOME")
        outgoing_var = tk.StringVar()
        incoming_var = tk.StringVar()
        status_var = tk.StringVar()
        ttk.Label(frame, text="Equipo").grid(row=0, column=0, sticky="w")
        side_box = ttk.Combobox(frame, textvariable=side_var, values=("HOME", "AWAY"), state="readonly", width=10)
        side_box.grid(row=0, column=1, sticky="ew", padx=(8, 0))
        ttk.Label(frame, text="Sale").grid(row=1, column=0, sticky="w", pady=(8, 0))
        outgoing_box = ttk.Combobox(frame, textvariable=outgoing_var, state="readonly", width=34)
        outgoing_box.grid(row=1, column=1, sticky="ew", padx=(8, 0), pady=(8, 0))
        ttk.Label(frame, text="Entra").grid(row=2, column=0, sticky="w", pady=(8, 0))
        incoming_box = ttk.Combobox(frame, textvariable=incoming_var, state="readonly", width=34)
        incoming_box.grid(row=2, column=1, sticky="ew", padx=(8, 0), pady=(8, 0))
        ttk.Label(frame, textvariable=status_var).grid(row=3, column=0, columnspan=2, sticky="w", pady=(8, 0))

        outgoing_map: dict[str, str] = {}
        incoming_map: dict[str, str] = {}

        def refresh_choices(*_args) -> None:
            side = TeamSide.HOME if side_var.get() == "HOME" else TeamSide.AWAY
            outgoing_map.clear()
            for agent in sorted(
                self.session.flow.engine.state.active_players_for_side(side),
                key=lambda item: item.slot_id,
            ):
                label = f"{agent.slot_id.upper()} - {agent.player.full_name}"
                outgoing_map[label] = agent.agent_id
            incoming_map.clear()
            for player in self.session.flow.available_substitutes(side):
                label = player.full_name
                incoming_map[label] = player.player_id
            outgoing_box["values"] = tuple(outgoing_map)
            incoming_box["values"] = tuple(incoming_map)
            outgoing_var.set(next(iter(outgoing_map), ""))
            incoming_var.set(next(iter(incoming_map), ""))
            remaining = self.session.flow.substitutions_remaining(side) - self.session.flow.pending_substitution_count(side)
            status_var.set(f"Cambios disponibles (descontando pendientes): {remaining}")

        def apply_change() -> None:
            side = TeamSide.HOME if side_var.get() == "HOME" else TeamSide.AWAY
            outgoing_id = outgoing_map.get(outgoing_var.get())
            incoming_id = incoming_map.get(incoming_var.get())
            if not outgoing_id or not incoming_id:
                status_var.set("Elegí jugador que sale y jugador que entra.")
                return
            try:
                start = len(self.session.flow.events)
                immediate = self.session.request_substitution(side, outgoing_id, incoming_id)
                self._consume_events(self.session.flow.events[start:])
                if not immediate:
                    status_var.set("Cambio solicitado: se hara en la proxima interrupcion.")
            except ValueError as exc:
                status_var.set(str(exc))
                return
            refresh_choices()
            if not immediate:
                status_var.set("Cambio solicitado: se hara en la proxima interrupcion.")
            self._refresh_all()

        side_box.bind("<<ComboboxSelected>>", refresh_choices)
        ttk.Button(frame, text="Hacer cambio", command=apply_change).grid(row=4, column=0, columnspan=2, pady=(12, 0))
        refresh_choices()

    def _open_tactical_editor(self) -> None:
        """Small live-management editor for formation, team and role instructions.

        This is intentionally a debug control surface, not the final tactics UI.
        It proves that the live Match Engine can consume manager intervention
        without rebuilding the MatchSnapshot or restarting the match.
        """

        if self.session.is_finished:
            return
        self.playing = False
        self.play_button_var.set("Reproducir")

        window = tk.Toplevel(self.root)
        window.title("Tactica en partido - debug")
        window.resizable(False, False)
        frame = ttk.Frame(window, padding=12)
        frame.pack(fill=tk.BOTH, expand=True)

        level_labels = {
            "Muy baja": Level.VERY_LOW,
            "Baja": Level.LOW,
            "Normal": Level.NORMAL,
            "Alta": Level.HIGH,
            "Muy alta": Level.VERY_HIGH,
        }
        label_for_level = {int(value): label for label, value in level_labels.items()}

        side_var = tk.StringVar(value="HOME")
        formation_var = tk.StringVar(value="4-3-3")
        tempo_var = tk.StringVar()
        verticality_var = tk.StringVar()
        pass_risk_var = tk.StringVar()
        pressing_var = tk.StringVar()
        block_var = tk.StringVar()
        line_var = tk.StringVar()
        slot_var = tk.StringVar()
        role_var = tk.StringVar()
        forward_runs_var = tk.StringVar()
        dribble_var = tk.StringVar()
        crossing_var = tk.StringVar()
        individual_risk_var = tk.StringVar()
        status_var = tk.StringVar()

        row = 0
        ttk.Label(frame, text="Equipo").grid(row=row, column=0, sticky="w")
        side_box = ttk.Combobox(frame, textvariable=side_var, values=("HOME", "AWAY"), state="readonly", width=14)
        side_box.grid(row=row, column=1, sticky="ew", padx=(8, 0))
        row += 1

        ttk.Label(frame, text="Formacion").grid(row=row, column=0, sticky="w", pady=(6, 0))
        formation_box = ttk.Combobox(
            frame,
            textvariable=formation_var,
            values=("4-3-3", "4-2-3-1", "4-1-4-1"),
            state="readonly",
            width=14,
        )
        formation_box.grid(row=row, column=1, sticky="ew", padx=(8, 0), pady=(6, 0))
        row += 1

        ttk.Separator(frame).grid(row=row, column=0, columnspan=2, sticky="ew", pady=8)
        row += 1

        level_values = tuple(level_labels)
        team_fields = (
            ("Tempo", tempo_var),
            ("Verticalidad", verticality_var),
            ("Riesgo de pase", pass_risk_var),
            ("Presion", pressing_var),
            ("Altura del bloque", block_var),
            ("Linea defensiva", line_var),
        )
        for label, variable in team_fields:
            ttk.Label(frame, text=label).grid(row=row, column=0, sticky="w", pady=(4, 0))
            ttk.Combobox(frame, textvariable=variable, values=level_values, state="readonly", width=14).grid(
                row=row, column=1, sticky="ew", padx=(8, 0), pady=(4, 0)
            )
            row += 1

        ttk.Separator(frame).grid(row=row, column=0, columnspan=2, sticky="ew", pady=8)
        row += 1

        ttk.Label(frame, text="Slot / jugador").grid(row=row, column=0, sticky="w")
        slot_box = ttk.Combobox(frame, textvariable=slot_var, state="readonly", width=26)
        slot_box.grid(row=row, column=1, sticky="ew", padx=(8, 0))
        row += 1
        ttk.Label(frame, text="Rol").grid(row=row, column=0, sticky="w", pady=(4, 0))
        role_box = ttk.Combobox(frame, textvariable=role_var, state="readonly", width=26)
        role_box.grid(row=row, column=1, sticky="ew", padx=(8, 0), pady=(4, 0))
        row += 1

        individual_fields = (
            ("Desmarques", forward_runs_var),
            ("Regates", dribble_var),
            ("Centros", crossing_var),
            ("Riesgo individual", individual_risk_var),
        )
        for label, variable in individual_fields:
            ttk.Label(frame, text=label).grid(row=row, column=0, sticky="w", pady=(4, 0))
            ttk.Combobox(frame, textvariable=variable, values=level_values, state="readonly", width=14).grid(
                row=row, column=1, sticky="ew", padx=(8, 0), pady=(4, 0)
            )
            row += 1

        status_row = row
        ttk.Label(frame, textvariable=status_var, wraplength=430).grid(
            row=status_row, column=0, columnspan=2, sticky="w", pady=(10, 0)
        )
        row += 1

        role_label_to_id: dict[str, str] = {}
        slot_label_to_id: dict[str, str] = {}

        def selected_side() -> TeamSide:
            return TeamSide.HOME if side_var.get() == "HOME" else TeamSide.AWAY

        def original_team(side: TeamSide):
            return self.snapshot.home_team if side is TeamSide.HOME else self.snapshot.away_team

        def formation_for(side: TeamSide) -> Formation:
            base = original_team(side).formation
            standard = {"gk", "rb", "rcb", "lcb", "lb", "rcm", "cm", "lcm", "rw", "st", "lw"}
            if base.slot_ids != standard:
                return self.session.flow.engine.runtime_tactic(side).formation
            overrides: dict[str, Position] = {}
            if formation_var.get() == "4-2-3-1":
                overrides["cm"] = Position.AM
            elif formation_var.get() == "4-1-4-1":
                overrides["cm"] = Position.DM
            return Formation(
                formation_id=f"runtime-{formation_var.get().replace('-', '')}",
                name=formation_var.get(),
                slots=tuple(
                    FormationSlot(slot.slot_id, overrides.get(slot.slot_id, slot.position))
                    for slot in base.slots
                ),
            )

        def current_agent_for_slot(side: TeamSide, slot_id: str):
            for agent in self.session.flow.engine.state.players.values():
                if agent.side is side and agent.slot_id == slot_id and agent.is_active:
                    return agent
            return None

        def refresh_role_choices(*_args) -> None:
            side = selected_side()
            formation = formation_for(side)
            slot_id = slot_label_to_id.get(slot_var.get())
            if slot_id is None:
                return
            position = formation.slot(slot_id).position
            role_label_to_id.clear()
            for role in roles_for_position(position):
                label = f"{role.name} [{role.role_id}]"
                role_label_to_id[label] = role.role_id
            role_box["values"] = tuple(role_label_to_id)

            tactic = self.session.flow.engine.runtime_tactic(side)
            try:
                current = tactic.slot(slot_id)
            except KeyError:
                current = None
            preferred = None
            if current is not None and get_role(current.role_id).supports(position):
                preferred = current.role_id
            if preferred is None:
                preferred = default_role_for_position(position).role_id
            selected_label = next(
                (label for label, role_id in role_label_to_id.items() if role_id == preferred),
                next(iter(role_label_to_id), ""),
            )
            role_var.set(selected_label)

            if current is not None and get_role(current.role_id).supports(position):
                instructions = current.effective_instructions
            else:
                instructions = get_role(preferred).default_instructions
            forward_runs_var.set(label_for_level[int(instructions.forward_runs)])
            dribble_var.set(label_for_level[int(instructions.dribbling_frequency)])
            crossing_var.set(label_for_level[int(instructions.crossing_frequency)])
            individual_risk_var.set(label_for_level[int(instructions.passing_risk)])

        def refresh_all(*_args) -> None:
            side = selected_side()
            tactic = self.session.flow.engine.runtime_tactic(side)
            ip = tactic.team_instructions.in_possession
            oop = tactic.team_instructions.out_of_possession
            tempo_var.set(label_for_level[int(ip.tempo)])
            verticality_var.set(label_for_level[int(ip.verticality)])
            pass_risk_var.set(label_for_level[int(ip.passing_risk)])
            pressing_var.set(label_for_level[int(oop.pressing_intensity)])
            block_var.set(label_for_level[int(oop.block_height)])
            line_var.set(label_for_level[int(oop.defensive_line_height)])

            if tactic.formation.name in {"4-3-3", "4-2-3-1", "4-1-4-1"}:
                formation_var.set(tactic.formation.name)
            else:
                # The demo starts as 4-3-3. Custom future formations remain
                # untouched unless the user explicitly chooses a debug preset.
                formation_var.set("4-3-3")

            slot_label_to_id.clear()
            for agent in sorted(
                self.session.flow.engine.state.active_players_for_side(side),
                key=lambda item: item.slot_id,
            ):
                label = f"{agent.slot_id.upper()} - {agent.player.full_name}"
                slot_label_to_id[label] = agent.slot_id
            slot_box["values"] = tuple(slot_label_to_id)
            if slot_var.get() not in slot_label_to_id:
                slot_var.set(next(iter(slot_label_to_id), ""))
            refresh_role_choices()
            status_var.set("Los cambios se aplican al estado runtime; el MatchSnapshot original queda intacto.")

        def apply_tactic() -> None:
            side = selected_side()
            current = self.session.flow.engine.runtime_tactic(side)
            formation = formation_for(side)
            instructions = current.team_instructions
            in_possession = replace(
                instructions.in_possession,
                tempo=level_labels[tempo_var.get()],
                verticality=level_labels[verticality_var.get()],
                passing_risk=level_labels[pass_risk_var.get()],
            )
            out_of_possession = replace(
                instructions.out_of_possession,
                pressing_intensity=level_labels[pressing_var.get()],
                block_height=level_labels[block_var.get()],
                defensive_line_height=level_labels[line_var.get()],
            )
            team_instructions = replace(
                instructions,
                in_possession=in_possession,
                out_of_possession=out_of_possession,
            )

            selected_slot_id = slot_label_to_id.get(slot_var.get())
            selected_role_id = role_label_to_id.get(role_var.get())
            slots: list[TacticalSlotSnapshot] = []
            for formation_slot in formation.slots:
                old = current.slot(formation_slot.slot_id)
                if get_role(old.role_id).supports(formation_slot.position):
                    role_id = old.role_id
                    effective = old.effective_instructions
                else:
                    role = default_role_for_position(formation_slot.position)
                    role_id = role.role_id
                    effective = role.default_instructions

                if formation_slot.slot_id == selected_slot_id and selected_role_id is not None:
                    role = get_role(selected_role_id)
                    if not role.supports(formation_slot.position):
                        status_var.set("Ese rol no es compatible con la posicion elegida.")
                        return
                    role_id = selected_role_id
                    effective = replace(
                        role.default_instructions,
                        forward_runs=level_labels[forward_runs_var.get()],
                        dribbling_frequency=level_labels[dribble_var.get()],
                        crossing_frequency=level_labels[crossing_var.get()],
                        passing_risk=level_labels[individual_risk_var.get()],
                    )
                role = get_role(role_id)
                slots.append(
                    TacticalSlotSnapshot(
                        slot_id=formation_slot.slot_id,
                        position=formation_slot.position,
                        role_id=role.role_id,
                        role_name=role.name,
                        effective_instructions=effective,
                    )
                )

            tactic = replace(
                current,
                name=f"{current.name} runtime",
                formation=formation,
                team_instructions=team_instructions,
                slots=tuple(slots),
                style=analyze_tactical_style(team_instructions),
            )
            try:
                start = len(self.session.flow.events)
                self.session.apply_runtime_tactic(
                    side,
                    tactic,
                    label=f"{formation.name} / ajuste manual",
                )
                self._consume_events(self.session.flow.events[start:])
            except ValueError as exc:
                status_var.set(str(exc))
                return
            status_var.set("Ajuste aplicado. Mira targets/forma del equipo para ver el cambio.")
            self._refresh_all()
            refresh_all()

        side_box.bind("<<ComboboxSelected>>", refresh_all)
        formation_box.bind("<<ComboboxSelected>>", refresh_role_choices)
        slot_box.bind("<<ComboboxSelected>>", refresh_role_choices)
        ttk.Button(frame, text="Aplicar tactica", command=apply_tactic).grid(
            row=row, column=0, columnspan=2, pady=(12, 0)
        )
        refresh_all()

    def _apply_home_tactical_mode(self) -> None:
        from dataclasses import replace as dc_replace

        mode = self.tactical_mode_var.get()
        base = self.snapshot.home_team.tactic
        instructions = base.team_instructions
        if mode == "Base":
            tactic = base
        elif mode == "Ofensivo":
            tactic = dc_replace(
                base,
                team_instructions=dc_replace(
                    instructions,
                    in_possession=dc_replace(
                        instructions.in_possession,
                        tempo=Level.HIGH,
                        verticality=Level.HIGH,
                        passing_risk=Level.HIGH,
                        attacking_line_width=Level.HIGH,
                    ),
                    out_of_possession=dc_replace(
                        instructions.out_of_possession,
                        block_height=Level.HIGH,
                        defensive_line_height=Level.HIGH,
                        pressing_intensity=Level.HIGH,
                    ),
                ),
            )
        elif mode == "Defensivo":
            tactic = dc_replace(
                base,
                team_instructions=dc_replace(
                    instructions,
                    in_possession=dc_replace(
                        instructions.in_possession,
                        tempo=Level.LOW,
                        passing_risk=Level.LOW,
                        verticality=Level.LOW,
                    ),
                    out_of_possession=dc_replace(
                        instructions.out_of_possession,
                        block_height=Level.LOW,
                        defensive_line_height=Level.LOW,
                        horizontal_compactness=Level.HIGH,
                        vertical_compactness=Level.HIGH,
                        protect_centre=Level.HIGH,
                    ),
                ),
            )
        else:
            tactic = dc_replace(
                base,
                team_instructions=dc_replace(
                    instructions,
                    out_of_possession=dc_replace(
                        instructions.out_of_possession,
                        block_height=Level.VERY_HIGH,
                        defensive_line_height=Level.HIGH,
                        pressing_intensity=Level.VERY_HIGH,
                    ),
                ),
            )
        start = len(self.session.flow.events)
        self.session.apply_runtime_tactic(TeamSide.HOME, tactic, label=mode)
        self._consume_events(self.session.flow.events[start:])
        self._refresh_all()

    def _consume_events(self, events) -> None:
        lines: list[str] = []
        for event in events:
            line = self.commentary.format_event(event)
            if line is not None:
                lines.append(line)
        if not lines:
            return
        self.commentary_text.configure(state=tk.NORMAL)
        self.commentary_text.insert(tk.END, "\n".join(lines) + "\n")
        self._commentary_line_count += len(lines)
        if self._commentary_line_count > self.MAX_COMMENTARY_LINES:
            excess = self._commentary_line_count - self.MAX_COMMENTARY_LINES
            self.commentary_text.delete("1.0", f"{excess + 1}.0")
            self._commentary_line_count = self.MAX_COMMENTARY_LINES
        self.commentary_text.see(tk.END)
        self.commentary_text.configure(state=tk.DISABLED)

    def _refresh_all(self) -> None:
        self._refresh_scoreboard()
        self._refresh_stats()
        self._refresh_status()
        self._draw_pitch()

    def _refresh_scoreboard(self) -> None:
        flow = self.session.flow
        home = self.snapshot.home_team.club_short_name
        away = self.snapshot.away_team.club_short_name
        label = flow.time_label
        score = f"{home}  {flow.score.home} - {flow.score.away}  {away}     {label}"
        if flow.phase is MatchPhase.PENALTY_SHOOTOUT:
            score += f"   PEN {flow.score.penalties_home}-{flow.score.penalties_away}"
        elif flow.is_finished and flow.score.penalties_home + flow.score.penalties_away:
            score += f"   PEN {flow.score.penalties_home}-{flow.score.penalties_away}"
        self.score_var.set(score)

    def _refresh_stats(self) -> None:
        stats = self.session.stats
        home_name = self.snapshot.home_team.club_short_name
        away_name = self.snapshot.away_team.club_short_name
        self.home_stats_var.set(self._team_stats_line(home_name, stats.home))
        self.away_stats_var.set(self._team_stats_line(away_name, stats.away))

    @staticmethod
    def _team_stats_line(name, stats) -> str:
        return (
            f"{name}: Pos {stats.possession_pct:4.1f}% | Tiros {stats.shots} "
            f"({stats.shots_on_target} al arco) | xG {stats.xg:.2f} | "
            f"Pases {stats.passes_completed}/{stats.passes_attempted} | "
            f"Faltas {stats.fouls} | Tarj {stats.yellow_cards}A/{stats.red_cards}R | "
            f"Córners {stats.corners}"
        )

    def _refresh_status(self) -> None:
        if self.instant_running:
            return
        if self.session.is_finished:
            state = "Finalizado"
        elif self.playing:
            state = "Reproduciendo"
        else:
            state = "Pausado"
        self.status_var.set(
            f"{state} | {self.speed_var.get()} | timestep fijo 0.25 s | seed {self.session.snapshot.seed}"
        )

    def _draw_pitch(self) -> None:
        canvas = self.pitch_canvas
        if not canvas.winfo_exists():
            return
        width = max(float(canvas.winfo_width()), 320.0)
        height = max(float(canvas.winfo_height()), 240.0)
        canvas.delete("all")

        state = self.session.flow.engine.state
        pitch = state.pitch
        projector = PitchProjector(width, height)
        x0, y0, x1, y1 = projector.bounds

        canvas.create_rectangle(x0, y0, x1, y1, outline="white", width=2)
        centre_x, centre_y = projector.to_canvas(pitch.length_m, pitch.width_m, pitch.centre)
        canvas.create_line(centre_x, y0, centre_x, y1, fill="white", width=1)
        radius = min((x1 - x0) * 9.15 / pitch.length_m, (y1 - y0) * 9.15 / pitch.width_m)
        canvas.create_oval(centre_x - radius, centre_y - radius, centre_x + radius, centre_y + radius, outline="white")
        canvas.create_oval(centre_x - 2, centre_y - 2, centre_x + 2, centre_y + 2, fill="white", outline="white")
        self._draw_penalty_areas(canvas, projector, pitch.length_m, pitch.width_m)
        canvas.create_text(x0 + 6, y0 - 12, text="HOME →", fill="white", anchor=tk.W, font=("Segoe UI", 9, "bold"))
        canvas.create_text(x1 - 6, y0 - 12, text="← AWAY", fill="white", anchor=tk.E, font=("Segoe UI", 9, "bold"))

        if self.show_shape.get():
            self._draw_shapes(canvas, projector)
        if self.show_targets.get():
            self._draw_targets(canvas, projector)
        if self.show_pressing.get() or self.show_coverage.get():
            self._draw_defensive_overlays(canvas, projector)
        if self.show_lanes.get():
            self._draw_passing_lanes(canvas, projector)

        owner_id = state.ball.owner_agent_id
        for agent in sorted(state.players.values(), key=lambda item: (item.side.value, item.slot_id)):
            if not agent.is_active:
                continue
            x, y = projector.to_canvas(pitch.length_m, pitch.width_m, agent.location)
            fill = "#1565c0" if agent.side is TeamSide.HOME else "#c62828"
            outline = "#ffd54f" if agent.agent_id == owner_id else "white"
            width_line = 3 if agent.agent_id == owner_id else 1
            r = 10
            canvas.create_oval(x - r, y - r, x + r, y + r, fill=fill, outline=outline, width=width_line)
            canvas.create_text(x, y, text=agent.slot_id.upper(), fill="white", font=("Segoe UI", 7, "bold"))
            if self.show_coordinates.get():
                canvas.create_text(
                    x,
                    y + 16,
                    text=f"{agent.location.x:.0f},{agent.location.y:.0f}",
                    fill="white",
                    font=("Consolas", 7),
                )

        bx, by = projector.to_canvas(pitch.length_m, pitch.width_m, state.ball.location)
        canvas.create_oval(bx - 5, by - 5, bx + 5, by + 5, fill="#ffeb3b", outline="black", width=1)
        if state.ball.height_m > 0.15:
            canvas.create_text(bx + 8, by - 8, text=f"h{state.ball.height_m:.1f}", fill="#fff59d", anchor=tk.W, font=("Consolas", 7))

    @staticmethod
    def _draw_penalty_areas(canvas, projector: PitchProjector, length: float, width: float) -> None:
        for x_start, x_end in ((0.0, 16.5), (length - 16.5, length)):
            top = (width - 40.32) / 2.0
            bottom = top + 40.32
            ax, ay = projector.to_canvas(length, width, Vector2(x_start, top))
            bx, by = projector.to_canvas(length, width, Vector2(x_end, bottom))
            canvas.create_rectangle(min(ax, bx), min(ay, by), max(ax, bx), max(ay, by), outline="white")
        for x_start, x_end in ((0.0, 5.5), (length - 5.5, length)):
            top = (width - 18.32) / 2.0
            bottom = top + 18.32
            ax, ay = projector.to_canvas(length, width, Vector2(x_start, top))
            bx, by = projector.to_canvas(length, width, Vector2(x_end, bottom))
            canvas.create_rectangle(min(ax, bx), min(ay, by), max(ax, bx), max(ay, by), outline="white")

    def _draw_targets(self, canvas, projector: PitchProjector) -> None:
        state = self.session.flow.engine.state
        for agent in state.active_players:
            target = agent.movement_target or agent.tactical_target
            if target is None or agent.location.distance_to(target) < 1.0:
                continue
            ax, ay = projector.to_canvas(state.pitch.length_m, state.pitch.width_m, agent.location)
            tx, ty = projector.to_canvas(state.pitch.length_m, state.pitch.width_m, target)
            canvas.create_line(
                ax, ay, tx, ty,
                fill="#ffcc80",
                dash=(4, 4),
                width=1,
                arrow=tk.LAST,
            )
            canvas.create_oval(tx - 2, ty - 2, tx + 2, ty + 2, fill="#ffcc80", outline="")
            if agent.movement_intent:
                canvas.create_text(
                    tx + 4, ty - 4,
                    text=agent.movement_intent.replace("_", " "),
                    fill="#ffe0b2",
                    anchor=tk.SW,
                    font=("Consolas", 7),
                )

    def _draw_defensive_overlays(self, canvas, projector: PitchProjector) -> None:
        engine = self.session.flow.engine
        state = engine.state
        owner_id = state.ball.owner_agent_id
        if owner_id is None:
            return
        owner = state.agent(owner_id)
        plan = engine.pressing_plan(owner.side.opponent)
        if self.show_pressing.get():
            for assignment in plan.pressing_assignments:
                defender = state.agent(assignment.defender_agent_id)
                dx, dy = projector.to_canvas(state.pitch.length_m, state.pitch.width_m, defender.location)
                tx, ty = projector.to_canvas(state.pitch.length_m, state.pitch.width_m, assignment.approach_target)
                canvas.create_line(
                    dx,
                    dy,
                    tx,
                    ty,
                    fill="#ff9800",
                    width=3 if assignment.primary else 1,
                    arrow=tk.LAST,
                )
        if self.show_coverage.get():
            for assignment in plan.coverage_assignments:
                defender = state.agent(assignment.defender_agent_id)
                dx, dy = projector.to_canvas(state.pitch.length_m, state.pitch.width_m, defender.location)
                tx, ty = projector.to_canvas(state.pitch.length_m, state.pitch.width_m, assignment.target_location)
                canvas.create_line(dx, dy, tx, ty, fill="#ce93d8", dash=(3, 3), width=1)

    def _draw_passing_lanes(self, canvas, projector: PitchProjector) -> None:
        engine = self.session.flow.engine
        state = engine.state
        owner_id = state.ball.owner_agent_id
        if owner_id is None:
            return
        try:
            perception = engine.perceive(owner_id)
        except ValueError:
            return
        owner = state.agent(owner_id)
        ox, oy = projector.to_canvas(state.pitch.length_m, state.pitch.width_m, owner.location)
        lanes = [
            lane
            for lane in sorted(
                perception.passing_lanes,
                key=lambda lane: (lane.lane_openness, lane.receiver_space, -lane.distance_m),
                reverse=True,
            )
            if lane.lane_openness >= 0.25
        ][:5]
        for lane in lanes:
            receiver = state.agent(lane.receiver_agent_id)
            rx, ry = projector.to_canvas(state.pitch.length_m, state.pitch.width_m, receiver.location)
            canvas.create_line(
                ox, oy, rx, ry,
                fill="#80deea",
                dash=(6, 3),
                width=2 if lane.lane_openness >= 0.70 else 1,
            )

    def _draw_shapes(self, canvas, projector: PitchProjector) -> None:
        """Draw actual line relationships instead of one giant convex hull.

        The hull used in the first viewer made a compact team and a disconnected
        team look deceptively similar. Line chains make it obvious when a full-back
        advances, an interior joins attack or the defence fails to squeeze up.
        """

        state = self.session.flow.engine.state
        for side, colour in ((TeamSide.HOME, "#90caf9"), (TeamSide.AWAY, "#ef9a9a")):
            centroids: list[tuple[float, float]] = []
            for line in (TacticalLine.DEFENCE, TacticalLine.MIDFIELD, TacticalLine.ATTACK):
                agents = [
                    agent
                    for agent in state.active_players
                    if agent.side is side and tactical_line(agent.assigned_position) is line
                ]
                agents.sort(key=lambda item: item.location.y)
                points = [
                    projector.to_canvas(state.pitch.length_m, state.pitch.width_m, agent.location)
                    for agent in agents
                ]
                if len(points) >= 2:
                    flat = [coord for point in points for coord in point]
                    canvas.create_line(*flat, fill=colour, width=2, dash=(5, 3))
                if points:
                    centroids.append((
                        sum(point[0] for point in points) / len(points),
                        sum(point[1] for point in points) / len(points),
                    ))
            if len(centroids) >= 2:
                flat = [coord for point in centroids for coord in point]
                canvas.create_line(*flat, fill=colour, width=1, dash=(2, 5))


def run_debug_viewer(snapshot: MatchSnapshot) -> None:
    root = tk.Tk()
    MatchDebugViewer(root, snapshot)
    root.mainloop()
