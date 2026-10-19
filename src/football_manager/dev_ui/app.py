from __future__ import annotations

import tkinter as tk
from queue import Empty, Queue
from threading import Thread
from tkinter import filedialog, messagebox, ttk

from football_manager.domain import TacticalPreset

from .session import DevelopmentSession


class DevelopmentUI(tk.Tk):
    """Disposable Tkinter shell for making the simulation tangible during development."""

    def __init__(self, session: DevelopmentSession | None = None) -> None:
        super().__init__()
        self.session = session or DevelopmentSession()
        # Default to the user's requested favorable testing mode in the DEV
        # sandbox, but keep raw DevelopmentSession / production balance neutral.
        # The checkbox remains reversible at any time before a bulk run.
        if session is None:
            self.session.set_dev_favorable_mode(True)
        self.title("Football Manager Project - Development UI")
        self.geometry("1500x860")
        self.minsize(1180, 720)

        self._active_page = "home"
        self._pages: dict[str, ttk.Frame] = {}
        self._nav_buttons: dict[str, ttk.Button] = {}
        self._bulk_running = False
        self._configure_styles()
        self._build_shell()
        self.show_page("home")

    def _configure_styles(self) -> None:
        style = ttk.Style(self)
        if "clam" in style.theme_names():
            style.theme_use("clam")
        style.configure("Title.TLabel", font=("Segoe UI", 18, "bold"))
        style.configure("Heading.TLabel", font=("Segoe UI", 12, "bold"))
        style.configure("Muted.TLabel", foreground="#666666")
        style.configure("Card.TLabelframe", padding=12)
        style.configure("Card.TLabelframe.Label", font=("Segoe UI", 10, "bold"))
        style.configure("Nav.TButton", anchor="w", padding=(14, 10))
        style.configure("Primary.TButton", padding=(16, 10))
        style.configure("Treeview", rowheight=26)
        style.configure("Treeview.Heading", font=("Segoe UI", 9, "bold"))

    def _build_shell(self) -> None:
        self.columnconfigure(1, weight=1)
        self.rowconfigure(1, weight=1)

        top = ttk.Frame(self, padding=(18, 12))
        top.grid(row=0, column=0, columnspan=2, sticky="ew")
        top.columnconfigure(1, weight=1)
        ttk.Label(top, text="FM PROJECT", style="Heading.TLabel").grid(row=0, column=0, sticky="w")
        self.header_var = tk.StringVar()
        ttk.Label(top, textvariable=self.header_var).grid(row=0, column=1, sticky="e")
        ttk.Label(top, text="DEV UI - disposable", style="Muted.TLabel").grid(row=1, column=1, sticky="e")

        sidebar = ttk.Frame(self, padding=(10, 12))
        sidebar.grid(row=1, column=0, sticky="nsw")
        for page, label in (
            ("home", "Home"),
            ("squad", "Squad"),
            ("tactics", "Tactics"),
            ("calendar", "Calendar"),
            ("competitions", "Competitions"),
        ):
            button = ttk.Button(
                sidebar,
                text=label,
                style="Nav.TButton",
                width=20,
                command=lambda target=page: self.show_page(target),
            )
            button.pack(fill="x", pady=2)
            self._nav_buttons[page] = button

        ttk.Separator(sidebar).pack(fill="x", pady=12)
        self.reset_button = ttk.Button(sidebar, text="Reset sandbox", command=self._reset_sandbox)
        self.reset_button.pack(fill="x", pady=2)
        ttk.Separator(sidebar).pack(fill="x", pady=(10, 6))
        ttk.Label(sidebar, text="Competition results only", style="Muted.TLabel").pack(anchor="w")
        self.save_world_button = ttk.Button(sidebar, text="Save current season results", command=self._save_world_results)
        self.save_world_button.pack(fill="x", pady=2)
        self.load_world_button = ttk.Button(sidebar, text="Load current season results", command=self._load_world_results)
        self.load_world_button.pack(fill="x", pady=2)
        ttk.Separator(sidebar).pack(fill="x", pady=8)
        ttk.Label(sidebar, text="Results archive (all seasons)", style="Muted.TLabel").pack(anchor="w")
        self.save_career_button = ttk.Button(sidebar, text="Save career results (JSON)", command=self._save_career_results)
        self.save_career_button.pack(fill="x", pady=2)
        self.load_career_button = ttk.Button(sidebar, text="Load career results (JSON)", command=self._load_career_results)
        self.load_career_button.pack(fill="x", pady=2)
        ttk.Label(
            sidebar,
            text="Phase 6.x DEV\nCross-competition test schedule.",
            style="Muted.TLabel",
            justify="left",
        ).pack(fill="x", pady=(16, 0))

        self.content = ttk.Frame(self, padding=(18, 14))
        self.content.grid(row=1, column=1, sticky="nsew")
        self.content.columnconfigure(0, weight=1)
        self.content.rowconfigure(0, weight=1)

        self.status_var = tk.StringVar(value="Ready")
        ttk.Label(self, textvariable=self.status_var, padding=(12, 5), relief="sunken").grid(
            row=2, column=0, columnspan=2, sticky="ew"
        )
        self._refresh_header()

    def show_page(self, page: str) -> None:
        for frame in self._pages.values():
            frame.grid_remove()
        frame = self._pages.get(page)
        if frame is None:
            frame = self._build_page(page)
            self._pages[page] = frame
        frame.grid(row=0, column=0, sticky="nsew")
        self._active_page = page
        self._refresh_page(page)

    def _build_page(self, page: str) -> ttk.Frame:
        builders = {
            "home": self._build_home_page,
            "squad": self._build_squad_page,
            "tactics": self._build_tactics_page,
            "calendar": self._build_calendar_page,
            "competitions": self._build_competitions_page,
        }
        return builders[page]()

    def _build_home_page(self) -> ttk.Frame:
        frame = ttk.Frame(self.content)
        frame.columnconfigure(0, weight=2)
        frame.columnconfigure(1, weight=1)
        ttk.Label(frame, text="Home", style="Title.TLabel").grid(row=0, column=0, columnspan=2, sticky="w")
        ttk.Label(
            frame,
            text="Development dashboard wired to the real ratings, tactics and Fast Match Simulator.",
            style="Muted.TLabel",
        ).grid(row=1, column=0, columnspan=2, sticky="w", pady=(2, 16))

        match_card = ttk.LabelFrame(frame, text="Next match", style="Card.TLabelframe")
        match_card.grid(row=2, column=0, sticky="nsew", padx=(0, 10), pady=(0, 10))
        match_card.columnconfigure(0, weight=1)
        self.home_match_var = tk.StringVar()
        self.home_match_meta_var = tk.StringVar()
        ttk.Label(match_card, textvariable=self.home_match_var, font=("Segoe UI", 15, "bold")).grid(
            row=0, column=0, sticky="w"
        )
        ttk.Label(match_card, textvariable=self.home_match_meta_var).grid(row=1, column=0, sticky="w", pady=(4, 12))
        match_actions = ttk.Frame(match_card)
        match_actions.grid(row=2, column=0, sticky="w")
        self.quick_sim_button = ttk.Button(
            match_actions,
            text="Quick Sim",
            style="Primary.TButton",
            command=self._quick_sim,
        )
        self.quick_sim_button.pack(side="left")
        self.continue_button = ttk.Button(
            match_actions,
            text="Continue to next match (DEV)",
            command=self._continue_to_next_match,
        )
        self.continue_button.pack(side="left", padx=(8, 0))
        season_actions = ttk.Frame(match_card)
        season_actions.grid(row=3, column=0, sticky="w", pady=(8, 4))
        self.simulate_season_button = ttk.Button(
            season_actions, text="Simulate entire season (DEV)", command=self._simulate_entire_season,
        )
        self.simulate_season_button.pack(side="left")
        self.next_season_button = ttk.Button(
            season_actions, text="Start next season", command=self._start_next_season,
        )
        self.next_season_button.pack(side="left", padx=(8, 0))
        self.dev_advantage_var = tk.BooleanVar(value=self.session.dev_favorable_mode)
        self.dev_advantage_check = ttk.Checkbutton(
            match_card, text="DEV advantage: weaker rivals (no scripted wins)",
            variable=self.dev_advantage_var, command=self._toggle_dev_advantage,
        )
        self.dev_advantage_check.grid(row=4, column=0, sticky="w", pady=(4, 0))
        self.bulk_progress_var = tk.StringVar(value="")
        ttk.Label(match_card, textvariable=self.bulk_progress_var, style="Muted.TLabel").grid(
            row=5, column=0, sticky="w", pady=(4, 0),
        )

        tactic_card = ttk.LabelFrame(frame, text="Current tactical plan", style="Card.TLabelframe")
        tactic_card.grid(row=2, column=1, sticky="nsew", pady=(0, 10))
        self.home_tactic_var = tk.StringVar()
        ttk.Label(tactic_card, textvariable=self.home_tactic_var, justify="left").pack(anchor="w")

        result_card = ttk.LabelFrame(frame, text="Latest result", style="Card.TLabelframe")
        result_card.grid(row=3, column=0, columnspan=2, sticky="nsew")
        self.home_result_var = tk.StringVar()
        ttk.Label(result_card, textvariable=self.home_result_var, justify="left").pack(anchor="w")
        self.career_summary_var = tk.StringVar(value="")
        ttk.Label(result_card, textvariable=self.career_summary_var, justify="left",
                  style="Muted.TLabel", wraplength=1150).pack(anchor="w", pady=(8, 0))
        return frame

    def _build_squad_page(self) -> ttk.Frame:
        frame = ttk.Frame(self.content)
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(3, weight=1)
        ttk.Label(frame, text="Squad", style="Title.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(
            frame,
            text="OVR is role/position-specific; ACT adds current execution context. Select XI + bench players to swap them.",
            style="Muted.TLabel",
        ).grid(row=1, column=0, sticky="w", pady=(2, 10))

        controls = ttk.Frame(frame)
        controls.grid(row=2, column=0, sticky="ew", pady=(0, 8))
        ttk.Label(controls, text="XI:").pack(side="left")
        self.xi_swap_var = tk.StringVar()
        self.xi_swap_combo = ttk.Combobox(controls, textvariable=self.xi_swap_var, state="readonly", width=24)
        self.xi_swap_combo.pack(side="left", padx=(5, 10))
        ttk.Label(controls, text="Bench:").pack(side="left")
        self.bench_swap_var = tk.StringVar()
        self.bench_swap_combo = ttk.Combobox(controls, textvariable=self.bench_swap_var, state="readonly", width=24)
        self.bench_swap_combo.pack(side="left", padx=(5, 10))
        self.swap_button = ttk.Button(controls, text="Swap", command=self._swap_selected)
        self.swap_button.pack(side="left")
        ttk.Label(controls, text="  Out-of-position swaps are allowed; role attributes now drive OVR.", style="Muted.TLabel").pack(side="left", padx=(8, 0))

        columns = ("status", "name", "pos", "sec", "slot", "role", "fit", "fam", "ovr", "act", "cond", "fat", "conf", "form", "sharp")
        self.squad_tree = ttk.Treeview(frame, columns=columns, show="headings", selectmode="extended")
        headings = {
            "status": "Status",
            "name": "Player",
            "pos": "Main",
            "sec": "Secondary",
            "slot": "Slot",
            "role": "Role",
            "fit": "Attr Fit",
            "fam": "Pos Fam",
            "ovr": "OVR",
            "act": "ACT",
            "cond": "Cond",
            "fat": "Fatigue",
            "conf": "Conf",
            "form": "Form",
            "sharp": "Sharp",
        }
        widths = {"status": 58, "name": 140, "pos": 45, "sec": 80, "slot": 45, "role": 135, "fit": 58, "fam": 58, "ovr": 52, "act": 52, "cond": 55, "fat": 58, "conf": 52, "form": 52, "sharp": 55}
        for key in columns:
            self.squad_tree.heading(key, text=headings[key])
            self.squad_tree.column(key, width=widths[key], anchor="center" if key != "name" and key != "role" else "w")
        self.squad_tree.grid(row=3, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=self.squad_tree.yview)
        scrollbar.grid(row=3, column=1, sticky="ns")
        self.squad_tree.configure(yscrollcommand=scrollbar.set)
        return frame

    def _build_tactics_page(self) -> ttk.Frame:
        frame = ttk.Frame(self.content)
        frame.columnconfigure(0, weight=1, minsize=275)
        frame.columnconfigure(1, weight=2, minsize=480)
        frame.columnconfigure(2, weight=2, minsize=520)
        frame.rowconfigure(3, weight=1)
        ttk.Label(frame, text="Tactics", style="Title.TLabel").grid(
            row=0, column=0, columnspan=3, sticky="w"
        )
        ttk.Label(
            frame,
            text=(
                "Presets are only starting points. Formation, roles and team instructions can be edited "
                "manually; the widgets only call the real tactic/domain layer."
            ),
            style="Muted.TLabel",
        ).grid(row=1, column=0, columnspan=3, sticky="w", pady=(2, 10))

        state = ttk.Frame(frame)
        state.grid(row=2, column=0, columnspan=3, sticky="ew", pady=(0, 10))
        for column in range(4):
            state.columnconfigure(column, weight=1)
        self.team_state_value_vars: dict[str, tk.StringVar] = {}
        self.team_state_note_vars: dict[str, tk.StringVar] = {}
        self.team_state_bars: dict[str, ttk.Progressbar] = {}
        for column, (key, title) in enumerate((
            ("familiarity", "Tactical familiarity"),
            ("chemistry", "Chemistry"),
            ("condition", "Condition"),
            ("morale", "Morale"),
        )):
            card = ttk.LabelFrame(state, text=title, style="Card.TLabelframe")
            card.grid(row=0, column=column, sticky="ew", padx=(0 if column == 0 else 5, 0))
            value_var = tk.StringVar()
            note_var = tk.StringVar()
            ttk.Label(card, textvariable=value_var, font=("Segoe UI", 13, "bold")).pack(anchor="w")
            bar = ttk.Progressbar(card, maximum=100, length=210)
            bar.pack(fill="x", pady=(5, 4))
            ttk.Label(card, textvariable=note_var, style="Muted.TLabel").pack(anchor="w")
            self.team_state_value_vars[key] = value_var
            self.team_state_note_vars[key] = note_var
            self.team_state_bars[key] = bar

        controls = ttk.LabelFrame(frame, text="Plan", style="Card.TLabelframe")
        controls.grid(row=3, column=0, sticky="nsew", padx=(0, 10))

        ttk.Label(controls, text="Formation", style="Heading.TLabel").pack(anchor="w")
        self.formation_var = tk.StringVar()
        formation_names = [name for _formation_id, name in self.session.available_formations]
        self.formation_combo = ttk.Combobox(
            controls, textvariable=self.formation_var, values=formation_names, state="readonly", width=25
        )
        self.formation_combo.pack(anchor="w", fill="x", pady=(4, 0))
        ttk.Button(controls, text="Apply formation", command=self._apply_formation).pack(
            anchor="w", pady=(6, 14)
        )

        ttk.Label(controls, text="Preset", style="Heading.TLabel").pack(anchor="w")
        self.preset_var = tk.StringVar()
        values = [preset.value for preset in self.session.tactical_presets]
        self.preset_combo = ttk.Combobox(
            controls, textvariable=self.preset_var, values=values, state="readonly", width=25
        )
        self.preset_combo.pack(anchor="w", fill="x", pady=(4, 0))
        ttk.Button(controls, text="Apply preset", command=self._apply_preset).pack(
            anchor="w", pady=(6, 12)
        )
        ttk.Label(
            controls,
            text="Applying a preset resets team instructions and roles for the current formation. You can edit them afterwards.",
            style="Muted.TLabel",
            wraplength=245,
            justify="left",
        ).pack(anchor="w", pady=(0, 10))

        self.tactic_summary_var = tk.StringVar()
        ttk.Separator(controls).pack(fill="x", pady=(2, 10))
        ttk.Label(controls, textvariable=self.tactic_summary_var, justify="left").pack(anchor="w")

        instructions = ttk.LabelFrame(frame, text="Team instructions", style="Card.TLabelframe")
        instructions.grid(row=3, column=1, sticky="nsew", padx=(0, 10))
        instructions.columnconfigure(0, weight=1)
        instructions.rowconfigure(0, weight=1)
        notebook = ttk.Notebook(instructions)
        notebook.grid(row=0, column=0, sticky="nsew")
        self._instruction_vars: dict[tuple[str, str], tk.StringVar] = {}
        grouped: dict[str, list] = {}
        for item in self.session.tactical_instruction_fields():
            grouped.setdefault(item.group, []).append(item)
        group_titles = {
            "in_possession": "In possession",
            "transition": "Transition",
            "out_of_possession": "Out of possession",
            "game_management": "Game management",
        }
        for group, title in group_titles.items():
            tab = ttk.Frame(notebook, padding=8)
            notebook.add(tab, text=title)
            entries = grouped.get(group, [])
            rows_per_column = 10
            for index, item in enumerate(entries):
                block = index // rows_per_column
                row = index % rows_per_column
                label_col = block * 2
                value_col = label_col + 1
                tab.columnconfigure(value_col, weight=1)
                ttk.Label(tab, text=item.label).grid(
                    row=row, column=label_col, sticky="w", padx=(0 if block == 0 else 12, 5), pady=3
                )
                var = tk.StringVar(value=item.value)
                combo = ttk.Combobox(
                    tab, textvariable=var, values=item.options, state="readonly", width=16
                )
                combo.grid(row=row, column=value_col, sticky="ew", pady=3)
                combo.bind(
                    "<<ComboboxSelected>>",
                    lambda _event, g=item.group, f=item.field: self._change_instruction(g, f),
                )
                self._instruction_vars[(item.group, item.field)] = var

        lineup = ttk.LabelFrame(frame, text="Starting XI - drag players between positions", style="Card.TLabelframe")
        lineup.grid(row=3, column=2, sticky="nsew")
        lineup.columnconfigure(0, weight=1)
        lineup.rowconfigure(0, weight=1)
        self._selected_tactic_slot: str | None = None
        self._drag_tactic_slot: str | None = None
        self._drag_last_xy: tuple[int, int] | None = None
        self._board_slot_centers: dict[str, tuple[float, float]] = {}
        self.tactics_board = tk.Canvas(
            lineup,
            width=520,
            height=520,
            background="#46764b",
            highlightthickness=1,
            highlightbackground="#777777",
        )
        self.tactics_board.grid(row=0, column=0, sticky="nsew")
        self.tactics_board.bind("<ButtonPress-1>", self._on_tactics_board_press)
        self.tactics_board.bind("<B1-Motion>", self._on_tactics_board_motion)
        self.tactics_board.bind("<ButtonRelease-1>", self._on_tactics_board_release)
        self.tactics_board.bind("<Configure>", self._on_tactics_board_resize)

        role_editor = ttk.Frame(lineup)
        role_editor.grid(row=1, column=0, sticky="ew", pady=(10, 0))
        role_editor.columnconfigure(1, weight=1)
        self.role_slot_var = tk.StringVar(value="Select a slot")
        ttk.Label(role_editor, textvariable=self.role_slot_var).grid(row=0, column=0, sticky="w", padx=(0, 6))
        self.role_var = tk.StringVar()
        self.role_combo = ttk.Combobox(role_editor, textvariable=self.role_var, state="readonly", width=22)
        self.role_combo.grid(row=0, column=1, sticky="ew")
        ttk.Button(role_editor, text="Apply role", command=self._apply_role).grid(
            row=0, column=2, padx=(6, 0)
        )
        self.role_context_var = tk.StringVar(value="")
        ttk.Label(role_editor, textvariable=self.role_context_var, style="Muted.TLabel").grid(
            row=1, column=0, columnspan=3, sticky="w", pady=(4, 0)
        )
        ttk.Label(
            lineup,
            text=(
                "Drag one player card onto another slot to swap the two players. Slots keep their tactical "
                "position and role, so extreme out-of-position tests are allowed and ACT/familiarity should react."
            ),
            style="Muted.TLabel",
            wraplength=500,
            justify="left",
        ).grid(row=2, column=0, sticky="w", pady=(8, 0))
        return frame

    def _build_calendar_page(self) -> ttk.Frame:
        frame = ttk.Frame(self.content)
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(2, weight=1)
        ttk.Label(frame, text="Calendar", style="Title.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(
            frame,
            text=(
                "Phase 6.6b: four English leagues, FA Cup, Carabao Cup, "
                "UEFA competitions and EFL Trophy share a world calendar. All playable clubs are fictional."
            ),
            style="Muted.TLabel",
            wraplength=1040,
            justify="left",
        ).grid(row=1, column=0, sticky="w", pady=(2, 10))

        notebook = ttk.Notebook(frame)
        notebook.grid(row=2, column=0, sticky="nsew")

        managed_tab = ttk.Frame(notebook, padding=8)
        managed_tab.columnconfigure(0, weight=1)
        managed_tab.rowconfigure(1, weight=1)
        notebook.add(managed_tab, text="Managed DEV calendar")
        ttk.Label(
            managed_tab,
            text=(
                "League, domestic cups and Champions League share one managed calendar. "
                "Only confirmed knockout fixtures appear; no duplicate conditional placeholders."
            ),
            style="Muted.TLabel",
        ).grid(row=0, column=0, sticky="w", pady=(0, 6))
        managed_area = ttk.Frame(managed_tab)
        managed_area.grid(row=1, column=0, sticky="nsew")
        managed_area.columnconfigure(0, weight=1)
        managed_area.rowconfigure(0, weight=1)
        columns = ("date", "competition", "opponent", "venue", "outcome", "status")
        self.calendar_tree = ttk.Treeview(managed_area, columns=columns, show="headings")
        for key, title, width in (
            ("date", "Date", 110),
            ("competition", "Competition", 200),
            ("opponent", "Opponent", 210),
            ("venue", "H/A", 65),
            ("outcome", "V/E/D", 62),
            ("status", "Stage / Status", 280),
        ):
            self.calendar_tree.heading(key, text=title)
            self.calendar_tree.column(key, width=width, anchor="w")
        self.calendar_tree.tag_configure("win", foreground="#137b35")
        self.calendar_tree.tag_configure("loss", foreground="#bf3030")
        self.calendar_tree.tag_configure("draw", foreground="#707070")
        managed_scroll = ttk.Scrollbar(managed_area, orient="vertical", command=self.calendar_tree.yview)
        self.calendar_tree.configure(yscrollcommand=managed_scroll.set)
        self.calendar_tree.grid(row=0, column=0, sticky="nsew")
        managed_scroll.grid(row=0, column=1, sticky="ns")

        official_tab = ttk.Frame(notebook, padding=8)
        official_tab.columnconfigure(0, weight=1)
        official_tab.rowconfigure(1, weight=1)
        notebook.add(official_tab, text="Premier League 2026/27 — Official data")
        self.official_calendar_summary_var = tk.StringVar(value="")
        ttk.Label(
            official_tab,
            textvariable=self.official_calendar_summary_var,
            style="Muted.TLabel",
            wraplength=1040,
            justify="left",
        ).grid(row=0, column=0, sticky="w", pady=(0, 6))
        official_area = ttk.Frame(official_tab)
        official_area.grid(row=1, column=0, sticky="nsew")
        official_area.columnconfigure(0, weight=1)
        official_area.rowconfigure(0, weight=1)
        official_columns = ("date", "mw", "home", "away", "kickoff", "source")
        self.official_calendar_tree = ttk.Treeview(
            official_area, columns=official_columns, show="headings"
        )
        for key, title, width in (
            ("date", "Date", 110),
            ("mw", "MW", 48),
            ("home", "Home", 210),
            ("away", "Away", 210),
            ("kickoff", "Kickoff", 110),
            ("source", "Source", 90),
        ):
            self.official_calendar_tree.heading(key, text=title)
            self.official_calendar_tree.column(key, width=width, anchor="w")
        official_scroll = ttk.Scrollbar(
            official_area, orient="vertical", command=self.official_calendar_tree.yview
        )
        self.official_calendar_tree.configure(yscrollcommand=official_scroll.set)
        self.official_calendar_tree.grid(row=0, column=0, sticky="nsew")
        official_scroll.grid(row=0, column=1, sticky="ns")

        efl_tab = ttk.Frame(notebook, padding=8)
        efl_tab.columnconfigure(0, weight=1)
        efl_tab.rowconfigure(2, weight=1)
        notebook.add(efl_tab, text="EFL 2026/27 — fictional clubs")
        efl_header = ttk.Frame(efl_tab)
        efl_header.grid(row=0, column=0, sticky="ew", pady=(0, 5))
        ttk.Label(efl_header, text="Division:").pack(side="left", padx=(0, 6))
        self.efl_calendar_division_var = tk.StringVar(value="Championship")
        self.efl_calendar_select = ttk.Combobox(
            efl_header, textvariable=self.efl_calendar_division_var,
            values=[name for _key, name in self.session.efl_division_options],
            state="readonly", width=22,
        )
        self.efl_calendar_select.pack(side="left")
        self.efl_calendar_select.bind("<<ComboboxSelected>>", lambda _event: self._refresh_efl_calendar())
        self.efl_calendar_summary_var = tk.StringVar(value="")
        ttk.Label(
            efl_tab, textvariable=self.efl_calendar_summary_var,
            style="Muted.TLabel", wraplength=1000, justify="left",
        ).grid(row=1, column=0, sticky="w", pady=(0, 5))
        efl_area = ttk.Frame(efl_tab)
        efl_area.grid(row=2, column=0, sticky="nsew")
        efl_area.columnconfigure(0, weight=1)
        efl_area.rowconfigure(0, weight=1)
        self.efl_calendar_tree = ttk.Treeview(
            efl_area, columns=official_columns, show="headings",
        )
        for key, title, width in (
            ("date", "Date", 115), ("mw", "Round", 65),
            ("home", "Fictional home", 210), ("away", "Fictional away", 210),
            ("kickoff", "Kickoff", 105), ("source", "Provenance", 130),
        ):
            self.efl_calendar_tree.heading(key, text=title)
            self.efl_calendar_tree.column(key, width=width, anchor="w")
        efl_scroll = ttk.Scrollbar(efl_area, orient="vertical", command=self.efl_calendar_tree.yview)
        self.efl_calendar_tree.configure(yscrollcommand=efl_scroll.set)
        self.efl_calendar_tree.grid(row=0, column=0, sticky="nsew")
        efl_scroll.grid(row=0, column=1, sticky="ns")

        staged_tab = ttk.Frame(notebook, padding=8)
        staged_tab.columnconfigure(0, weight=1)
        staged_tab.rowconfigure(2, weight=1)
        notebook.add(staged_tab, text="UEFA / EFL Trophy (DEV)")
        staged_controls = ttk.Frame(staged_tab)
        staged_controls.grid(row=0, column=0, sticky="w", pady=(0, 5))
        ttk.Label(staged_controls, text="Competition:").pack(side="left", padx=(0, 6))
        self.staged_calendar_competition_var = tk.StringVar(value="UEFA Champions League")
        staged_select = ttk.Combobox(
            staged_controls, textvariable=self.staged_calendar_competition_var,
            values=[name for _key, name in self.session.staged_competition_options],
            state="readonly", width=27,
        )
        staged_select.pack(side="left")
        staged_select.bind("<<ComboboxSelected>>", lambda _event: self._refresh_staged_calendar())
        self.staged_calendar_summary_var = tk.StringVar(value="")
        ttk.Label(staged_tab, textvariable=self.staged_calendar_summary_var,
                  style="Muted.TLabel", wraplength=1030).grid(row=1, column=0, sticky="w", pady=(0, 6))
        staged_area = ttk.Frame(staged_tab)
        staged_area.grid(row=2, column=0, sticky="nsew")
        staged_area.columnconfigure(0, weight=1)
        staged_area.rowconfigure(0, weight=1)
        self.staged_calendar_tree = ttk.Treeview(staged_area, columns=official_columns, show="headings")
        for key, title, width in (("date", "Date", 105), ("mw", "MD", 45),
                                  ("home", "Fictional home", 200), ("away", "Fictional away", 200),
                                  ("kickoff", "Kickoff DEV", 120), ("source", "Stage / provenance", 260)):
            self.staged_calendar_tree.heading(key, text=title)
            self.staged_calendar_tree.column(key, width=width, anchor="w")
        self.staged_calendar_tree.grid(row=0, column=0, sticky="nsew")
        staged_scroll = ttk.Scrollbar(staged_area, orient="vertical", command=self.staged_calendar_tree.yview)
        self.staged_calendar_tree.configure(yscrollcommand=staged_scroll.set)
        staged_scroll.grid(row=0, column=1, sticky="ns")
        return frame

    def _build_competitions_page(self) -> ttk.Frame:
        frame = ttk.Frame(self.content)
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(3, weight=1)
        ttk.Label(frame, text="Competitions", style="Title.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(
            frame,
            text="Development inspection only. Sporting logic lives in the domain layer; the tabs just expose it.",
            style="Muted.TLabel",
        ).grid(row=1, column=0, sticky="w", pady=(2, 8))

        columns = ("competition", "format", "status")
        self.competitions_tree = ttk.Treeview(frame, columns=columns, show="headings", height=6)
        for key, title, width in (
            ("competition", "Competition", 220),
            ("format", "Format", 220),
            ("status", "Implementation", 520),
        ):
            self.competitions_tree.heading(key, text=title)
            self.competitions_tree.column(key, width=width, anchor="w")
        self.competitions_tree.grid(row=2, column=0, sticky="ew", pady=(0, 8))

        notebook = ttk.Notebook(frame)
        notebook.grid(row=3, column=0, sticky="nsew")

        league_tab = ttk.Frame(notebook, padding=8)
        league_tab.columnconfigure(0, weight=1)
        league_tab.rowconfigure(1, weight=1)
        notebook.add(league_tab, text="League")
        self.league_summary_var = tk.StringVar(value="")
        ttk.Label(league_tab, textvariable=self.league_summary_var, style="Muted.TLabel").grid(
            row=0, column=0, sticky="w", pady=(0, 6)
        )
        league_area = ttk.Panedwindow(league_tab, orient=tk.HORIZONTAL)
        league_area.grid(row=1, column=0, sticky="nsew")
        standings_frame = ttk.Frame(league_area)
        standings_frame.columnconfigure(0, weight=1)
        standings_frame.rowconfigure(1, weight=1)
        self.managed_league_label_var = tk.StringVar(value="Development Premier League table")
        ttk.Label(standings_frame, textvariable=self.managed_league_label_var).grid(
            row=0, column=0, sticky="w", pady=(0, 4))
        table_columns = ("pos", "club", "p", "w", "d", "l", "gf", "ga", "gd", "pts", "qual")
        self.league_table_tree = ttk.Treeview(standings_frame, columns=table_columns, show="headings")
        for key, title, width, anchor in (
            ("pos", "#", 36, "center"), ("club", "Club", 160, "w"),
            ("p", "P", 36, "center"), ("w", "W", 36, "center"),
            ("d", "D", 36, "center"), ("l", "L", 36, "center"),
            ("gf", "GF", 40, "center"), ("ga", "GA", 40, "center"),
            ("gd", "GD", 42, "center"), ("pts", "Pts", 44, "center"),
            ("qual", "Route", 105, "w"),
        ):
            self.league_table_tree.heading(key, text=title)
            self.league_table_tree.column(key, width=width, anchor=anchor, stretch=key in {"club", "qual"})
        self.league_table_tree.grid(row=1, column=0, sticky="nsew")
        league_area.add(standings_frame, weight=3)
        fixtures_frame = ttk.Frame(league_area)
        fixtures_frame.columnconfigure(0, weight=1)
        fixtures_frame.rowconfigure(1, weight=1)
        self.league_round_var = tk.StringVar(value="Round 1 fixtures")
        ttk.Label(fixtures_frame, textvariable=self.league_round_var).grid(row=0, column=0, sticky="w", pady=(0, 4))
        fixture_columns = ("home", "away", "status")
        self.league_fixtures_tree = ttk.Treeview(fixtures_frame, columns=fixture_columns, show="headings")
        for key, title, width in (("home", "Home", 145), ("away", "Away", 145), ("status", "Status", 140)):
            self.league_fixtures_tree.heading(key, text=title)
            self.league_fixtures_tree.column(key, width=width, anchor="w")
        self.league_fixtures_tree.grid(row=1, column=0, sticky="nsew")
        league_area.add(fixtures_frame, weight=2)

        cup_tab = ttk.Frame(notebook, padding=8)
        cup_tab.columnconfigure(0, weight=1)
        cup_tab.rowconfigure(2, weight=1)
        notebook.add(cup_tab, text="Knockout")
        cup_header = ttk.Frame(cup_tab)
        cup_header.grid(row=0, column=0, sticky="ew", pady=(0, 4))
        cup_header.columnconfigure(0, weight=1)
        self.cup_summary_var = tk.StringVar(value="")
        ttk.Label(cup_header, textvariable=self.cup_summary_var, style="Muted.TLabel").grid(row=0, column=0, sticky="w")
        self.cup_sim_button = ttk.Button(cup_header, text="Resolve current round in background (DEV)", command=self._simulate_dev_cup_round)
        self.cup_sim_button.grid(row=0, column=1, sticky="e")
        ttk.Label(cup_tab, text="Development Cup bracket").grid(row=1, column=0, sticky="w", pady=(0, 4))
        cup_columns = ("round", "tie", "leg", "home", "away", "score", "status")
        self.cup_tree = ttk.Treeview(cup_tab, columns=cup_columns, show="headings")
        for key, title, width, anchor in (
            ("round", "Round", 110, "w"), ("tie", "Tie", 42, "center"),
            ("leg", "Leg", 42, "center"), ("home", "Home", 155, "w"),
            ("away", "Away", 155, "w"), ("score", "Score", 120, "center"),
            ("status", "Status", 200, "w"),
        ):
            self.cup_tree.heading(key, text=title)
            self.cup_tree.column(key, width=width, anchor=anchor, stretch=key in {"home", "away", "status"})
        self.cup_tree.grid(row=2, column=0, sticky="nsew")

        # English cups are the 2026/27 world competitions. The 8-club
        # Development Cup above is retained only as an isolated legacy inspector.
        english_cups_tab = ttk.Frame(notebook, padding=8)
        english_cups_tab.columnconfigure(0, weight=1)
        english_cups_tab.rowconfigure(2, weight=1)
        notebook.add(english_cups_tab, text="Domestic cups / Playoffs")
        cup_controls = ttk.Frame(english_cups_tab)
        cup_controls.grid(row=0, column=0, sticky="ew", pady=(0, 5))
        ttk.Label(cup_controls, text="Competition:").pack(side="left", padx=(0, 6))
        self.english_cup_var = tk.StringVar(value="FA Cup")
        self._world_cup_titles = {
            "FA Cup": "fa-cup", "Carabao Cup": "carabao-cup",
            "Championship Playoffs": "championship-playoffs",
            "League One Playoffs": "league-one-playoffs",
            "League Two Playoffs": "league-two-playoffs",
        }
        english_cup_select = ttk.Combobox(
            cup_controls, textvariable=self.english_cup_var,
            values=tuple(self._world_cup_titles), state="readonly", width=24,
        )
        english_cup_select.pack(side="left")
        english_cup_select.bind("<<ComboboxSelected>>", lambda _event: self._refresh_english_cups())
        self.world_summary_var = tk.StringVar(value="")
        self.english_cup_summary_var = tk.StringVar(value="")
        ttk.Label(cup_controls, textvariable=self.world_summary_var, style="Muted.TLabel").pack(side="left", padx=(20, 0))
        ttk.Label(english_cups_tab, textvariable=self.english_cup_summary_var,
                  style="Muted.TLabel", wraplength=1000).grid(row=1, column=0, sticky="w", pady=(0, 5))
        bracket_area = ttk.Frame(english_cups_tab)
        bracket_area.grid(row=2, column=0, sticky="nsew")
        bracket_area.columnconfigure(0, weight=1)
        bracket_area.rowconfigure(0, weight=1)
        self.english_cup_tree = ttk.Treeview(
            bracket_area, columns=cup_columns, show="headings",
        )
        for key, title, width, anchor in (
            ("round", "Round", 145, "w"), ("tie", "Tie", 42, "center"),
            ("leg", "Leg", 42, "center"), ("home", "Home", 165, "w"),
            ("away", "Away", 165, "w"), ("score", "Score", 135, "center"),
            ("status", "Kickoff / Status", 200, "w"),
        ):
            self.english_cup_tree.heading(key, text=title)
            self.english_cup_tree.column(key, width=width, anchor=anchor,
                                          stretch=key in {"home", "away", "status"})
        self.english_cup_tree.grid(row=0, column=0, sticky="nsew")
        cup_scroll = ttk.Scrollbar(bracket_area, orient="vertical", command=self.english_cup_tree.yview)
        self.english_cup_tree.configure(yscrollcommand=cup_scroll.set)
        cup_scroll.grid(row=0, column=1, sticky="ns")

        multi_tab = ttk.Frame(notebook, padding=8)
        multi_tab.columnconfigure(0, weight=1)
        multi_tab.rowconfigure(2, weight=1)
        notebook.add(multi_tab, text="Multi-stage")
        self.continental_summary_var = tk.StringVar(value="")
        ttk.Label(multi_tab, textvariable=self.continental_summary_var, style="Muted.TLabel").grid(row=0, column=0, sticky="w", pady=(0, 6))
        multi_area = ttk.Panedwindow(multi_tab, orient=tk.VERTICAL)
        multi_area.grid(row=2, column=0, sticky="nsew")
        multi_table_frame = ttk.Frame(multi_area)
        multi_table_frame.columnconfigure(0, weight=1)
        multi_table_frame.rowconfigure(1, weight=1)
        ttk.Label(multi_table_frame, text="League phase table / route").grid(row=0, column=0, sticky="w", pady=(0, 4))
        self.continental_table_tree = ttk.Treeview(multi_table_frame, columns=table_columns, show="headings", height=8)
        for key, title, width, anchor in (
            ("pos", "#", 36, "center"), ("club", "Club", 160, "w"),
            ("p", "P", 36, "center"), ("w", "W", 36, "center"),
            ("d", "D", 36, "center"), ("l", "L", 36, "center"),
            ("gf", "GF", 40, "center"), ("ga", "GA", 40, "center"),
            ("gd", "GD", 42, "center"), ("pts", "Pts", 44, "center"),
            ("qual", "Route", 115, "w"),
        ):
            self.continental_table_tree.heading(key, text=title)
            self.continental_table_tree.column(key, width=width, anchor=anchor, stretch=key in {"club", "qual"})
        self.continental_table_tree.grid(row=1, column=0, sticky="nsew")
        multi_area.add(multi_table_frame, weight=2)
        multi_bracket_frame = ttk.Frame(multi_area)
        multi_bracket_frame.columnconfigure(0, weight=1)
        multi_bracket_frame.rowconfigure(1, weight=1)
        ttk.Label(multi_bracket_frame, text="Playoff / knockout bracket").grid(row=0, column=0, sticky="w", pady=(6, 4))
        self.continental_tree = ttk.Treeview(multi_bracket_frame, columns=cup_columns, show="headings", height=7)
        for key, title, width, anchor in (
            ("round", "Round", 110, "w"), ("tie", "Tie", 42, "center"),
            ("leg", "Leg", 42, "center"), ("home", "Home", 155, "w"),
            ("away", "Away", 155, "w"), ("score", "Score", 120, "center"),
            ("status", "Status", 200, "w"),
        ):
            self.continental_tree.heading(key, text=title)
            self.continental_tree.column(key, width=width, anchor=anchor, stretch=key in {"home", "away", "status"})
        self.continental_tree.grid(row=1, column=0, sticky="nsew")
        multi_area.add(multi_bracket_frame, weight=1)

        efl_tab = ttk.Frame(notebook, padding=8)
        efl_tab.columnconfigure(0, weight=1)
        efl_tab.rowconfigure(2, weight=1)
        notebook.add(efl_tab, text="EFL leagues (DEV)")
        efl_controls = ttk.Frame(efl_tab)
        efl_controls.grid(row=0, column=0, sticky="ew", pady=(0, 5))
        ttk.Label(efl_controls, text="Division:").pack(side="left", padx=(0, 5))
        self.efl_league_division_var = tk.StringVar(value="Championship")
        efl_division_select = ttk.Combobox(
            efl_controls, textvariable=self.efl_league_division_var,
            values=[name for _key, name in self.session.efl_division_options],
            state="readonly", width=20,
        )
        efl_division_select.pack(side="left", padx=(0, 16))
        efl_division_select.bind("<<ComboboxSelected>>", lambda _event: self._on_efl_league_division_changed())
        ttk.Label(efl_controls, text="Round:").pack(side="left", padx=(0, 4))
        self.efl_round_selected_var = tk.StringVar(value="1")
        self.efl_round_select = ttk.Combobox(
            efl_controls, textvariable=self.efl_round_selected_var,
            values=[str(i) for i in range(1, 47)],
            state="readonly", width=5,
        )
        self.efl_round_select.pack(side="left", padx=(0, 20))
        self.efl_round_select.bind("<<ComboboxSelected>>", lambda _event: self._refresh_efl_competitions())
        self.efl_sim_button = ttk.Button(
            efl_controls, text="Simulate next DEV round", command=self._simulate_dev_efl_round,
        )
        self.efl_sim_button.pack(side="left")
        self.efl_league_summary_var = tk.StringVar(value="")
        ttk.Label(
            efl_tab, textvariable=self.efl_league_summary_var,
            style="Muted.TLabel", wraplength=1000, justify="left",
        ).grid(row=1, column=0, sticky="w", pady=(0, 5))
        efl_area = ttk.Panedwindow(efl_tab, orient=tk.HORIZONTAL)
        efl_area.grid(row=2, column=0, sticky="nsew")
        efl_table_frame = ttk.Frame(efl_area)
        efl_table_frame.columnconfigure(0, weight=1)
        efl_table_frame.rowconfigure(1, weight=1)
        ttk.Label(efl_table_frame, text="Fictional division standings / quality").grid(row=0, column=0, sticky="w")
        self.efl_table_tree = ttk.Treeview(
            efl_table_frame, columns=table_columns, show="headings",
        )
        for key, title, width, anchor in (
            ("pos", "#", 36, "center"), ("club", "Club", 155, "w"),
            ("p", "P", 34, "center"), ("w", "W", 34, "center"),
            ("d", "D", 34, "center"), ("l", "L", 34, "center"),
            ("gf", "GF", 35, "center"), ("ga", "GA", 35, "center"),
            ("gd", "GD", 38, "center"), ("pts", "Pts", 39, "center"),
            ("qual", "DEV Strength", 99, "w"),
        ):
            self.efl_table_tree.heading(key, text=title)
            self.efl_table_tree.column(key, width=width, anchor=anchor,
                                       stretch=key in {"club", "qual"})
        self.efl_table_tree.grid(row=1, column=0, sticky="nsew")
        efl_table_scroll = ttk.Scrollbar(efl_table_frame, orient="vertical", command=self.efl_table_tree.yview)
        self.efl_table_tree.configure(yscrollcommand=efl_table_scroll.set)
        efl_table_scroll.grid(row=1, column=1, sticky="ns")
        efl_area.add(efl_table_frame, weight=3)
        efl_fixture_frame = ttk.Frame(efl_area)
        efl_fixture_frame.columnconfigure(0, weight=1)
        efl_fixture_frame.rowconfigure(1, weight=1)
        ttk.Label(efl_fixture_frame, text="Matchweek pairings / EFL date slots").grid(row=0, column=0, sticky="w")
        self.efl_fixtures_tree = ttk.Treeview(
            efl_fixture_frame, columns=fixture_columns, show="headings",
        )
        for key, title, width in (
            ("home", "Fictional home", 150), ("away", "Fictional away", 150),
            ("status", "Kickoff / Status", 230),
        ):
            self.efl_fixtures_tree.heading(key, text=title)
            self.efl_fixtures_tree.column(key, width=width, anchor="w")
        self.efl_fixtures_tree.grid(row=1, column=0, sticky="nsew")
        efl_area.add(efl_fixture_frame, weight=2)

        world_staged_tab = ttk.Frame(notebook, padding=8)
        world_staged_tab.columnconfigure(0, weight=1)
        world_staged_tab.rowconfigure(2, weight=1)
        notebook.add(world_staged_tab, text="UEFA / EFL Trophy")
        stage_controls = ttk.Frame(world_staged_tab)
        stage_controls.grid(row=0, column=0, sticky="ew", pady=(0, 5))
        ttk.Label(stage_controls, text="Tournament:").pack(side="left", padx=(0, 5))
        self.world_staged_var = tk.StringVar(value="UEFA Champions League")
        stage_combo = ttk.Combobox(
            stage_controls, textvariable=self.world_staged_var,
            values=[name for _key, name in self.session.staged_competition_options],
            state="readonly", width=29,
        )
        stage_combo.pack(side="left", padx=(0, 15))
        stage_combo.bind("<<ComboboxSelected>>", lambda _event: self._refresh_world_staged())
        ttk.Label(stage_controls, text="Trophy group:").pack(side="left", padx=(0, 5))
        self.staged_group_var = tk.StringVar(value="north-1")
        self.staged_group_combo = ttk.Combobox(
            stage_controls, textvariable=self.staged_group_var,
            values=("north-1",), state="readonly", width=16,
        )
        self.staged_group_combo.pack(side="left")
        self.staged_group_combo.bind("<<ComboboxSelected>>", lambda _event: self._refresh_world_staged())
        self.staged_world_summary_var = tk.StringVar(value="")
        ttk.Label(world_staged_tab, textvariable=self.staged_world_summary_var,
                  style="Muted.TLabel", wraplength=980).grid(row=1, column=0, sticky="w", pady=(0, 5))
        staged_panels = ttk.Panedwindow(world_staged_tab, orient=tk.VERTICAL)
        staged_panels.grid(row=2, column=0, sticky="nsew")
        staged_table_frame = ttk.Frame(staged_panels)
        staged_table_frame.columnconfigure(0, weight=1)
        staged_table_frame.rowconfigure(0, weight=1)
        self.staged_table_tree = ttk.Treeview(
            staged_table_frame, columns=table_columns, show="headings", height=12,
        )
        for key, title, width, anchor in (
            ("pos", "#", 36, "center"), ("club", "Club", 200, "w"),
            ("p", "P", 36, "center"), ("w", "W", 36, "center"),
            ("d", "D", 36, "center"), ("l", "L", 36, "center"),
            ("gf", "GF", 40, "center"), ("ga", "GA", 40, "center"),
            ("gd", "GD", 42, "center"), ("pts", "Pts", 44, "center"),
            ("qual", "Route", 115, "w"),
        ):
            self.staged_table_tree.heading(key, text=title)
            self.staged_table_tree.column(key, width=width, anchor=anchor,
                                          stretch=key in {"club", "qual"})
        self.staged_table_tree.grid(row=0, column=0, sticky="nsew")
        stage_table_scroll = ttk.Scrollbar(staged_table_frame, orient="vertical", command=self.staged_table_tree.yview)
        self.staged_table_tree.configure(yscrollcommand=stage_table_scroll.set)
        stage_table_scroll.grid(row=0, column=1, sticky="ns")
        staged_panels.add(staged_table_frame, weight=2)
        staged_bracket_frame = ttk.Frame(staged_panels)
        staged_bracket_frame.columnconfigure(0, weight=1)
        staged_bracket_frame.rowconfigure(0, weight=1)
        self.staged_bracket_tree = ttk.Treeview(
            staged_bracket_frame, columns=cup_columns, show="headings", height=10,
        )
        for key, title, width in (
            ("round", "Stage", 130), ("tie", "Tie", 40), ("leg", "Leg", 40),
            ("home", "Home", 165), ("away", "Away", 165),
            ("score", "Score", 130), ("status", "Kickoff / Status", 170),
        ):
            self.staged_bracket_tree.heading(key, text=title)
            self.staged_bracket_tree.column(key, width=width, anchor="w")
        self.staged_bracket_tree.grid(row=0, column=0, sticky="nsew")
        stage_bracket_scroll = ttk.Scrollbar(staged_bracket_frame, orient="vertical", command=self.staged_bracket_tree.yview)
        self.staged_bracket_tree.configure(yscrollcommand=stage_bracket_scroll.set)
        stage_bracket_scroll.grid(row=0, column=1, sticky="ns")
        staged_panels.add(staged_bracket_frame, weight=2)
        return frame

    def _refresh_page(self, page: str) -> None:
        self._refresh_header()
        if page == "home":
            self._refresh_home()
        elif page == "squad":
            self._refresh_squad()
        elif page == "tactics":
            self._refresh_tactics()
        elif page == "calendar":
            self._refresh_calendar()
        elif page == "competitions":
            self._refresh_competitions()

    def _refresh_header(self) -> None:
        self.header_var.set(f"{self.session.home_club.name} | {self.session.current_date:%d %b %Y}")

    def _refresh_home(self) -> None:
        self.home_match_var.set(self.session.next_match_label)
        self.home_match_meta_var.set(self.session.next_match_meta)
        tactical = self.session.tactical_view()
        self.home_tactic_var.set(
            f"{tactical.formation_name}\n"
            f"Preset: {tactical.preset.value}\n"
            f"Style: {tactical.style_label}\n"
            f"Pressing {tactical.pressing:.0f} | Tempo {tactical.tempo:.0f} | Directness {tactical.directness:.0f}"
        )
        summary = self.session.match_summary()
        if summary is None:
            self.home_result_var.set("No match simulated yet.")
        else:
            self.home_result_var.set(
                f"{summary.scoreline}\n{summary.stats_line}\n{summary.possession_line}\n{summary.discipline_line}"
            )
        reports = self.session.archived_season_reports
        if reports:
            report = reports[-1]
            def fmt(cid):
                return ", ".join(self.session._world_club_names.get(club, club)
                                 for club in report.promoted[cid])
            self.career_summary_var.set(
                f"Last completed: {report.season_label} | Premier champion: "
                f"{self.session._world_club_names.get(report.champions['dev-premier'], report.champions['dev-premier'])} | "
                f"Promoted to Premier: {fmt('dev-championship')} | "
                f"Promoted to Championship: {fmt('dev-league-one')} | "
                f"Promoted to League One: {fmt('dev-league-two')}"
            )
        else:
            self.career_summary_var.set("Season archive appears here after starting the next season.")
        self.quick_sim_button.configure(
            state="normal" if not self._bulk_running and self.session.can_quick_sim else "disabled")
        self.continue_button.configure(
            state="normal" if not self._bulk_running and self.session.can_continue else "disabled")
        self.simulate_season_button.configure(
            state="normal" if not self._bulk_running and not self.session.season_finished else "disabled")
        self.next_season_button.configure(
            state="normal" if not self._bulk_running and self.session.season_finished else "disabled")
        self.dev_advantage_check.configure(state="disabled" if self._bulk_running else "normal")
        self.dev_advantage_var.set(self.session.dev_favorable_mode)

    def _refresh_squad(self) -> None:
        self.squad_tree.delete(*self.squad_tree.get_children())
        rows = self.session.squad_rows()
        xi_labels = [f"{row.name} ({row.slot})" for row in rows if row.squad_status == "XI"]
        bench_labels = [f"{row.name} ({row.position})" for row in rows if row.squad_status == "BENCH"]
        self._xi_label_to_id = {f"{row.name} ({row.slot})": row.player_id for row in rows if row.squad_status == "XI"}
        self._bench_label_to_id = {f"{row.name} ({row.position})": row.player_id for row in rows if row.squad_status == "BENCH"}
        self.xi_swap_combo.configure(values=xi_labels)
        self.bench_swap_combo.configure(values=bench_labels)
        self.xi_swap_var.set(xi_labels[0] if xi_labels else "")
        self.bench_swap_var.set(bench_labels[0] if bench_labels else "")
        for row in rows:
            self.squad_tree.insert(
                "",
                "end",
                iid=row.player_id,
                values=(
                    row.squad_status,
                    row.name,
                    row.position,
                    row.secondary_positions,
                    row.slot,
                    row.role,
                    f"{row.role_fit:.1f}",
                    f"{row.assigned_familiarity:.1f}",
                    f"{row.overall:.1f}",
                    f"{row.current:.1f}",
                    f"{row.condition:.1f}",
                    f"{row.fatigue:.1f}",
                    f"{row.confidence:.0f}",
                    f"{row.form:.0f}",
                    f"{row.sharpness:.0f}",
                ),
            )

    def _refresh_tactics(self) -> None:
        tactical = self.session.tactical_view()
        state = self.session.tactical_team_state()

        self._formation_name_to_id = {name: formation_id for formation_id, name in self.session.available_formations}
        self.formation_combo.configure(values=list(self._formation_name_to_id))
        self.formation_var.set(tactical.formation_name)
        self.preset_var.set(tactical.preset.value)
        self.tactic_summary_var.set(
            f"Formation: {tactical.formation_name}\n"
            f"Origin: {tactical.preset.value}\n"
            f"Style: {tactical.style_label}\n\n"
            f"Possession: {tactical.possession:.0f}\n"
            f"Pressing: {tactical.pressing:.0f}\n"
            f"Directness: {tactical.directness:.0f}\n"
            f"Defensive depth: {tactical.defensive_depth:.0f}\n"
            f"Tempo: {tactical.tempo:.0f}\n"
            f"Width: {tactical.width:.0f}\n"
            f"Risk: {tactical.risk:.0f}"
        )

        self.team_state_value_vars["familiarity"].set(f"{state.xi_familiarity:.1f} / 100")
        self.team_state_note_vars["familiarity"].set(f"Squad: {state.squad_familiarity:.1f}")
        self.team_state_bars["familiarity"]["value"] = state.xi_familiarity

        self.team_state_value_vars["chemistry"].set(f"{state.xi_chemistry:.1f} / 100")
        self.team_state_note_vars["chemistry"].set("Starting XI cohesion")
        self.team_state_bars["chemistry"]["value"] = state.xi_chemistry

        self.team_state_value_vars["condition"].set(f"{state.xi_condition:.1f} / 100")
        self.team_state_note_vars["condition"].set(
            f"{state.condition_below_75} below 75 | {state.condition_below_60} below 60"
        )
        self.team_state_bars["condition"]["value"] = state.xi_condition

        self.team_state_value_vars["morale"].set(f"{state.squad_morale:.1f} / 100")
        self.team_state_note_vars["morale"].set(f"XI: {state.xi_morale:.1f} | squad average")
        self.team_state_bars["morale"]["value"] = state.squad_morale

        current_fields = {(item.group, item.field): item for item in self.session.tactical_instruction_fields()}
        for key, var in self._instruction_vars.items():
            item = current_fields.get(key)
            if item is not None:
                var.set(item.value)

        starter_slots = [row.slot.lower() for row in self.session.squad_rows() if row.squad_status == "XI"]
        selected_slot = getattr(self, "_selected_tactic_slot", None)
        if starter_slots:
            target = selected_slot if selected_slot in starter_slots else starter_slots[0]
            self._selected_tactic_slot = target
            self._draw_tactics_board()
            self._update_role_editor(target)

    def _efl_key_from_label(self, label: str) -> str:
        for key, name in self.session.efl_division_options:
            if name == label:
                return key
        return "championship"

    def _refresh_efl_calendar(self) -> None:
        key = self._efl_key_from_label(self.efl_calendar_division_var.get())
        self.efl_calendar_summary_var.set(self.session.efl_calendar_summary(key))
        self.efl_calendar_tree.delete(*self.efl_calendar_tree.get_children())
        for item in self.session.efl_calendar_rows(key):
            self.efl_calendar_tree.insert(
                "", "end", values=(
                    item.date_label, item.matchweek, item.home, item.away,
                    item.kickoff, item.source,
                ),
            )

    def _on_efl_league_division_changed(self) -> None:
        key = self._efl_key_from_label(self.efl_league_division_var.get())
        self.efl_round_selected_var.set(str(min(46, self.session.efl_current_round(key))))
        self._refresh_efl_competitions()

    def _refresh_efl_competitions(self) -> None:
        key = self._efl_key_from_label(self.efl_league_division_var.get())
        try:
            round_number = int(self.efl_round_selected_var.get())
        except ValueError:
            round_number = 1
        self.efl_league_summary_var.set(self.session.efl_league_summary(key))
        self.efl_table_tree.delete(*self.efl_table_tree.get_children())
        for row in self.session.efl_table_rows(key):
            self.efl_table_tree.insert("", "end", values=(
                row.position, row.club, row.played, row.won, row.drawn, row.lost,
                row.goals_for, row.goals_against, f"{row.goal_difference:+d}",
                row.points, row.qualification,
            ))
        self.efl_fixtures_tree.delete(*self.efl_fixtures_tree.get_children())
        for row in self.session.efl_fixture_rows(key, round_number):
            self.efl_fixtures_tree.insert("", "end", values=(row.home, row.away, row.status))
        self.efl_sim_button.configure(
            state="normal" if self.session.efl_current_round(key) <= 46 else "disabled"
        )

    def _simulate_dev_efl_round(self) -> None:
        key = self._efl_key_from_label(self.efl_league_division_var.get())
        try:
            completed = self.session.simulate_next_efl_round(key)
        except (ValueError, RuntimeError) as exc:
            messagebox.showerror("EFL DEV inspector", str(exc))
            return
        self.efl_round_selected_var.set(str(min(46, self.session.efl_current_round(key))))
        self.status_var.set(f"EFL DEV {key}: completed round {completed} of 46")
        self._refresh_efl_competitions()

    def _refresh_calendar(self) -> None:
        self.calendar_tree.delete(*self.calendar_tree.get_children())
        for item in self.session.calendar_rows:
            self.calendar_tree.insert(
                "",
                "end",
                values=(
                    item.date_label,
                    item.competition,
                    item.opponent,
                    item.venue,
                    item.outcome,
                    item.status,
                ),
                tags=(({"V": "win", "D": "loss", "E": "draw"}.get(item.outcome),)
                      if item.outcome else ()),
            )

        self.official_calendar_summary_var.set(self.session.official_calendar_summary)
        self.official_calendar_tree.delete(*self.official_calendar_tree.get_children())
        for item in self.session.official_calendar_rows:
            self.official_calendar_tree.insert(
                "",
                "end",
                values=(
                    item.date_label,
                    item.matchweek,
                    item.home,
                    item.away,
                    item.kickoff,
                    item.source,
                ),
            )

        self._refresh_efl_calendar()
        self._refresh_staged_calendar()

    def _staged_id_for_name(self, name: str) -> str:
        return next(cid for cid, title in self.session.staged_competition_options if title == name)

    def _refresh_staged_calendar(self) -> None:
        cid = self._staged_id_for_name(self.staged_calendar_competition_var.get())
        self.staged_calendar_summary_var.set(
            self.session.staged_competition_summary(cid) + " | Calendar dates are DEV kickoffs"
        )
        self.staged_calendar_tree.delete(*self.staged_calendar_tree.get_children())
        for item in self.session.staged_calendar_rows(cid):
            self.staged_calendar_tree.insert("", "end", values=(
                item.date_label, item.matchweek, item.home, item.away, item.kickoff, item.source,
            ))

    def _refresh_world_staged(self) -> None:
        cid = self._staged_id_for_name(self.world_staged_var.get())
        groups = self.session.staged_competition_groups(cid)
        self.staged_group_combo.configure(values=groups, state="readonly" if groups else "disabled")
        if groups and self.staged_group_var.get() not in groups:
            self.staged_group_var.set(groups[0])
        self.staged_world_summary_var.set(self.session.staged_competition_summary(cid))
        self.staged_table_tree.delete(*self.staged_table_tree.get_children())
        group = self.staged_group_var.get() if groups else None
        for row in self.session.staged_competition_table_rows(cid, group):
            self.staged_table_tree.insert("", "end", values=(
                row.position, row.club, row.played, row.won, row.drawn, row.lost,
                row.goals_for, row.goals_against, f"{row.goal_difference:+d}",
                row.points, row.qualification,
            ))
        self.staged_bracket_tree.delete(*self.staged_bracket_tree.get_children())
        for row in self.session.staged_competition_bracket_rows(cid):
            self.staged_bracket_tree.insert("", "end", values=(
                row.round_name, row.tie_number, row.leg_number, row.home, row.away,
                row.score, row.status,
            ))

    def _refresh_english_cups(self) -> None:
        cup_id = self._world_cup_titles[self.english_cup_var.get()]
        self.world_summary_var.set(self.session.world_summary)
        self.english_cup_tree.delete(*self.english_cup_tree.get_children())
        if cup_id not in self.session._world.cups:
            self.english_cup_summary_var.set(
                "Playoff draw is generated from FINAL EFL league standings; no fixtures yet."
            )
            return
        self.english_cup_summary_var.set(self.session.world_cup_summary(cup_id))
        for item in self.session.world_cup_bracket_rows(cup_id):
            self.english_cup_tree.insert("", "end", values=(
                item.round_name, item.tie_number, item.leg_number,
                item.home, item.away, item.score, item.status,
            ))

    def _refresh_competitions(self) -> None:
        self.competitions_tree.delete(*self.competitions_tree.get_children())
        for item in self.session.competition_rows:
            self.competitions_tree.insert("", "end", values=item)

        self.league_summary_var.set(self.session.league_summary)
        self.managed_league_label_var.set(
            f"Development {self.session._league_edition.competition.name} table")
        self.league_table_tree.delete(*self.league_table_tree.get_children())
        for row in self.session.league_table_rows():
            self.league_table_tree.insert(
                "",
                "end",
                values=(
                    row.position,
                    row.club,
                    row.played,
                    row.won,
                    row.drawn,
                    row.lost,
                    row.goals_for,
                    row.goals_against,
                    f"{row.goal_difference:+d}",
                    row.points,
                    row.qualification,
                ),
            )

        self.league_round_var.set(f"Round {self.session.current_league_round} fixtures")
        self.league_fixtures_tree.delete(*self.league_fixtures_tree.get_children())
        for row in self.session.league_fixture_rows(self.session.current_league_round):
            self.league_fixtures_tree.insert(
                "", "end", values=(row.home, row.away, row.status)
            )

        self.cup_summary_var.set(self.session.cup_summary)
        self.cup_tree.delete(*self.cup_tree.get_children())
        for row in self.session.cup_bracket_rows():
            self.cup_tree.insert(
                "",
                "end",
                values=(
                    row.round_name,
                    row.tie_number,
                    row.leg_number,
                    row.home,
                    row.away,
                    row.score,
                    row.status,
                ),
            )
        self.cup_sim_button.configure(
            state="normal" if self.session.can_simulate_cup_round else "disabled"
        )


        self.continental_summary_var.set(self.session.continental_summary)
        self.continental_table_tree.delete(*self.continental_table_tree.get_children())
        for row in self.session.continental_table_rows():
            self.continental_table_tree.insert(
                "",
                "end",
                values=(
                    row.position,
                    row.club,
                    row.played,
                    row.won,
                    row.drawn,
                    row.lost,
                    row.goals_for,
                    row.goals_against,
                    f"{row.goal_difference:+d}",
                    row.points,
                    row.qualification,
                ),
            )
        self.continental_tree.delete(*self.continental_tree.get_children())
        for row in self.session.continental_bracket_rows():
            self.continental_tree.insert(
                "",
                "end",
                values=(
                    row.round_name,
                    row.tie_number,
                    row.leg_number,
                    row.home,
                    row.away,
                    row.score,
                    row.status,
                ),
            )

        self._refresh_efl_competitions()
        self._refresh_english_cups()
        self._refresh_world_staged()

    def _simulate_dev_cup_round(self) -> None:
        try:
            self.session.simulate_dev_cup_round()
        except Exception as exc:
            messagebox.showerror("Development Cup", str(exc), parent=self)
            return
        self.status_var.set(
            "Development Cup round resolved in disposable background mode."
        )
        self._refresh_competitions()

    def _apply_formation(self) -> None:
        formation_id = getattr(self, "_formation_name_to_id", {}).get(self.formation_var.get())
        if formation_id is None:
            messagebox.showinfo("Formation", "Choose a formation.", parent=self)
            return
        try:
            self.session.set_formation(formation_id)
        except Exception as exc:
            messagebox.showerror("Formation", str(exc), parent=self)
            return
        self.status_var.set(f"Formation changed to {self.formation_var.get()}. Roles were reset for the new shape.")
        self._refresh_tactics()

    def _on_tactics_board_resize(self, _event=None) -> None:
        if getattr(self, "_drag_tactic_slot", None) is None:
            self._draw_tactics_board()

    def _draw_tactics_board(self) -> None:
        if not hasattr(self, "tactics_board"):
            return
        canvas = self.tactics_board
        width = max(canvas.winfo_width(), 500)
        height = max(canvas.winfo_height(), 470)
        canvas.delete("all")

        margin = 14
        line = "#edf4ed"
        canvas.create_rectangle(margin, margin, width - margin, height - margin, outline=line, width=2)
        canvas.create_line(margin, height / 2, width - margin, height / 2, fill=line, width=2)
        radius = min(width, height) * 0.09
        canvas.create_oval(
            width / 2 - radius,
            height / 2 - radius,
            width / 2 + radius,
            height / 2 + radius,
            outline=line,
            width=2,
        )
        canvas.create_oval(width / 2 - 2, height / 2 - 2, width / 2 + 2, height / 2 + 2, fill=line, outline=line)
        box_width = width * 0.42
        box_depth = height * 0.14
        canvas.create_rectangle(
            width / 2 - box_width / 2,
            margin,
            width / 2 + box_width / 2,
            margin + box_depth,
            outline=line,
            width=2,
        )
        canvas.create_rectangle(
            width / 2 - box_width / 2,
            height - margin - box_depth,
            width / 2 + box_width / 2,
            height - margin,
            outline=line,
            width=2,
        )

        layout = self._formation_board_layout(self.session.home_lineup.formation.formation_id)
        rows = {row.slot.lower(): row for row in self.session.squad_rows() if row.squad_status == "XI"}
        self._board_slot_centers = {}
        usable_width = width - 2 * margin
        usable_height = height - 2 * margin
        card_width = min(112.0, max(92.0, usable_width * 0.22))
        card_height = 58.0
        for slot_id, (nx, ny) in layout.items():
            row = rows.get(slot_id)
            if row is None:
                continue
            x = margin + nx * usable_width
            y = margin + ny * usable_height
            self._board_slot_centers[slot_id] = (x, y)
            selected = slot_id == getattr(self, "_selected_tactic_slot", None)
            tag = f"slot:{slot_id}"
            fill = "#f5f1dc" if not selected else "#fff2ad"
            outline = "#1e2c20" if not selected else "#8a6b00"
            canvas.create_rectangle(
                x - card_width / 2,
                y - card_height / 2,
                x + card_width / 2,
                y + card_height / 2,
                fill=fill,
                outline=outline,
                width=2 if selected else 1,
                tags=(tag, "player_card"),
            )
            assigned_position = self.session.home_lineup.formation.slot(slot_id).position.value
            canvas.create_text(
                x,
                y - 18,
                text=assigned_position,
                font=("Segoe UI", 8, "bold"),
                fill="#1d1d1d",
                tags=(tag, "player_card"),
            )
            canvas.create_text(
                x,
                y - 2,
                text=row.name,
                width=card_width - 6,
                font=("Segoe UI", 8, "bold"),
                fill="#111111",
                tags=(tag, "player_card"),
            )
            canvas.create_text(
                x,
                y + 18,
                text=f"{row.position} | OVR {row.overall:.1f} ACT {row.current:.1f} | F {row.assigned_familiarity:.0f}",
                font=("Segoe UI", 7),
                fill="#333333",
                tags=(tag, "player_card"),
            )

    @staticmethod
    def _formation_board_layout(formation_id: str) -> dict[str, tuple[float, float]]:
        from .formations import formation_board_layouts

        return formation_board_layouts().get(formation_id, {})

    def _slot_from_board_event(self, event) -> str | None:
        items = self.tactics_board.find_overlapping(event.x - 2, event.y - 2, event.x + 2, event.y + 2)
        for item in reversed(items):
            for tag in self.tactics_board.gettags(item):
                if tag.startswith("slot:"):
                    return tag.split(":", 1)[1]
        return None

    def _nearest_board_slot(self, x: int, y: int) -> str | None:
        if not self._board_slot_centers:
            return None
        slot_id, (target_x, target_y) = min(
            self._board_slot_centers.items(),
            key=lambda item: (item[1][0] - x) ** 2 + (item[1][1] - y) ** 2,
        )
        distance_squared = (target_x - x) ** 2 + (target_y - y) ** 2
        return slot_id if distance_squared <= 115.0**2 else None

    def _on_tactics_board_press(self, event) -> None:
        slot_id = self._slot_from_board_event(event)
        if slot_id is None:
            return
        self._selected_tactic_slot = slot_id
        self._drag_tactic_slot = slot_id
        self._drag_last_xy = (event.x, event.y)
        self._update_role_editor(slot_id)
        self._draw_tactics_board()

    def _on_tactics_board_motion(self, event) -> None:
        slot_id = getattr(self, "_drag_tactic_slot", None)
        last = getattr(self, "_drag_last_xy", None)
        if slot_id is None or last is None:
            return
        dx = event.x - last[0]
        dy = event.y - last[1]
        self.tactics_board.move(f"slot:{slot_id}", dx, dy)
        self._drag_last_xy = (event.x, event.y)

    def _on_tactics_board_release(self, event) -> None:
        source = getattr(self, "_drag_tactic_slot", None)
        self._drag_tactic_slot = None
        self._drag_last_xy = None
        if source is None:
            return
        target = self._nearest_board_slot(event.x, event.y)
        if target is not None and target != source:
            source_player = self.session.home_lineup.player_for_slot(source).full_name
            target_player = self.session.home_lineup.player_for_slot(target).full_name
            try:
                self.session.swap_starting_slots(source, target)
            except Exception as exc:
                messagebox.showerror("Tactical board", str(exc), parent=self)
                self._selected_tactic_slot = source
                self._refresh_tactics()
                return
            self._selected_tactic_slot = target
            self.status_var.set(
                f"Swapped {source_player} ({source.upper()}) with {target_player} ({target.upper()}). "
                "ACT and tactical familiarity were recalculated."
            )
        else:
            self._selected_tactic_slot = source
        self._refresh_tactics()

    def _update_role_editor(self, slot_id: str) -> None:
        options = self.session.role_options_for_slot(slot_id)
        self._role_name_to_id = {option.name: option.role_id for option in options}
        names = list(self._role_name_to_id)
        self.role_combo.configure(values=names)
        row = next(
            (item for item in self.session.squad_rows() if item.squad_status == "XI" and item.slot.lower() == slot_id),
            None,
        )
        current_role = row.role if row is not None else ""
        player_name = row.name if row is not None else ""
        self.role_slot_var.set(f"{slot_id.upper()} role - {player_name}")
        self.role_var.set(current_role if current_role in self._role_name_to_id else (names[0] if names else ""))
        if row is not None and hasattr(self, "role_context_var"):
            self.role_context_var.set(
                f"Attributes for role: {row.role_fit:.1f} | Position familiarity: {row.assigned_familiarity:.1f} | "
                f"OVR: {row.overall:.1f} | ACT: {row.current:.1f}"
            )

    def _apply_role(self) -> None:
        slot_id = getattr(self, "_selected_tactic_slot", None)
        role_id = getattr(self, "_role_name_to_id", {}).get(self.role_var.get())
        if slot_id is None or role_id is None:
            messagebox.showinfo("Role", "Select a starting slot and a compatible role.", parent=self)
            return
        try:
            self.session.set_role(slot_id, role_id)
        except Exception as exc:
            messagebox.showerror("Role", str(exc), parent=self)
            return
        self.status_var.set(f"Role updated for {slot_id.upper()}. ACT/familiarity were recalculated.")
        self._refresh_tactics()

    def _change_instruction(self, group: str, field_name: str) -> None:
        var = self._instruction_vars[(group, field_name)]
        try:
            self.session.set_team_instruction(group, field_name, var.get())
        except Exception as exc:
            messagebox.showerror("Team instruction", str(exc), parent=self)
            self._refresh_tactics()
            return
        self.status_var.set(f"Manual tactic: {field_name.replace('_', ' ')} = {var.get()}")
        self._refresh_tactics()

    def _apply_preset(self) -> None:
        try:
            self.session.set_tactical_preset(TacticalPreset(self.preset_var.get()))
        except Exception as exc:
            messagebox.showerror("Tactics", str(exc), parent=self)
            return
        self.status_var.set(f"Applied tactical preset: {self.preset_var.get()}")
        self._refresh_tactics()

    def _swap_selected(self) -> None:
        starter_id = getattr(self, "_xi_label_to_id", {}).get(self.xi_swap_var.get())
        bench_id = getattr(self, "_bench_label_to_id", {}).get(self.bench_swap_var.get())
        if starter_id is None or bench_id is None:
            messagebox.showinfo("Lineup", "Choose one XI player and one bench player.", parent=self)
            return
        try:
            self.session.swap_lineup(starter_id, bench_id)
        except Exception as exc:
            messagebox.showerror("Lineup", str(exc), parent=self)
            return
        self.status_var.set("Starting XI updated. Check ACT for any position mismatch.")
        self._refresh_squad()

    def _quick_sim(self) -> None:
        try:
            result = self.session.quick_simulate()
        except Exception as exc:
            messagebox.showerror("Quick Sim", str(exc), parent=self)
            return
        self.status_var.set("Match simulated with the real Fast Match Simulator. Condition, position experience and morale were persisted.")
        self._refresh_home()
        summary = self.session.match_summary()
        messagebox.showinfo(
            "Quick Sim result",
            f"{summary.scoreline if summary else 'Match complete'}\n\n"
            f"xG {result.statistics_home.xg:.2f}-{result.statistics_away.xg:.2f}\n"
            f"Shots {result.statistics_home.shots}-{result.statistics_away.shots}\n"
            f"Possession {result.statistics_home.possession_pct:.1f}% - {result.statistics_away.possession_pct:.1f}%\n\n"
            "Post-match condition/morale are persisted. Use Continue to load the next scheduled match across competitions.",
            parent=self,
        )

    def _continue_to_next_match(self) -> None:
        try:
            self.session.continue_to_next_match()
        except Exception as exc:
            messagebox.showerror("Continue", str(exc), parent=self)
            return
        self.status_var.set(
            f"Advanced to {self.session.next_match_meta}. Other fixtures were resolved in DEV background mode."
        )
        self._refresh_header()
        self._refresh_home()
        self._refresh_calendar()
        self._refresh_competitions()

    def _toggle_dev_advantage(self) -> None:
        self.session.set_dev_favorable_mode(self.dev_advantage_var.get())
        self.status_var.set("DEV-only opponent handicap " + ("enabled" if self.session.dev_favorable_mode else "disabled")
                            + ". FastMatchSimulator still resolves every managed match.")
        self._refresh_home()
        self._refresh_tactics()

    def _set_bulk_busy(self, busy: bool) -> None:
        self._bulk_running = busy
        for button in self._nav_buttons.values():
            button.configure(state="disabled" if busy else "normal")
        for button in (self.reset_button, self.save_world_button, self.load_world_button,
                       self.save_career_button, self.load_career_button):
            button.configure(state="disabled" if busy else "normal")
        self._refresh_home()

    def _simulate_entire_season(self) -> None:
        if self._bulk_running or self.session.season_finished:
            return
        if not messagebox.askyesno(
            "DEV full-season simulation",
            "Simulate every remaining Northbridge match using FastMatchSimulator, "
            "and all other matches in the World Runner? This may take some time.", parent=self,
        ):
            return
        self._bulk_events = Queue()
        self._set_bulk_busy(True)
        self.bulk_progress_var.set("Simulating managed matches and advancing the entire world...")
        self.status_var.set("DEV season simulation running in a background worker...")

        def worker() -> None:
            try:
                count = self.session.simulate_remaining_season(
                    on_progress=lambda played: self._bulk_events.put(("progress", played))
                )
                self._bulk_events.put(("done", count))
            except Exception as exc:
                self._bulk_events.put(("error", str(exc)))

        Thread(target=worker, daemon=True).start()
        self.after(100, self._poll_bulk_simulation)

    def _poll_bulk_simulation(self) -> None:
        finished = False
        while True:
            try:
                kind, payload = self._bulk_events.get_nowait()
            except Empty:
                break
            if kind == "progress":
                self.bulk_progress_var.set(f"Managed matches played: {payload}. Other games also advancing...")
            elif kind == "done":
                finished = True
                self.bulk_progress_var.set(f"Season complete: {payload} managed matches simulated.")
                self.status_var.set(f"Season {self.session._world.season_label} finished. Inspect cups/playoffs, then start next season.")
            else:
                finished = True
                self.status_var.set("Season simulation stopped: " + payload)
                messagebox.showerror("DEV season simulation", payload, parent=self)
        if finished:
            self._set_bulk_busy(False)
            self._refresh_header()
            for page in list(self._pages):
                self._refresh_page(page)
        else:
            self.after(150, self._poll_bulk_simulation)

    def _start_next_season(self) -> None:
        if self._bulk_running or not self.session.season_finished:
            return
        try:
            report = self.session.begin_next_season()
        except Exception as exc:
            messagebox.showerror("Next season", str(exc), parent=self)
            return
        self.status_var.set(
            f"Archived {report.season_label}; generated {self.session._world.season_label} "
            "with promoted/relegated clubs and UEFA qualifiers (DEV data)."
        )
        self.bulk_progress_var.set("New season ready. Check the league standings and calendar.")
        for page in list(self._pages):
            self._refresh_page(page)
        self._refresh_header()

    def _save_career_results(self) -> None:
        path = filedialog.asksaveasfilename(
            parent=self, title="Save all season results, NOT a full manager career",
            defaultextension=".json", filetypes=(("JSON files", "*.json"),),
        )
        if path:
            try:
                self.session.save_career_results(path)
                self.status_var.set("Career result archive saved (no squad/tactics/player state).")
            except Exception as exc:
                messagebox.showerror("Save career results", str(exc), parent=self)

    def _load_career_results(self) -> None:
        path = filedialog.askopenfilename(
            parent=self, title="Load all season results (no squad state)",
            filetypes=(("JSON files", "*.json"),),
        )
        if path:
            try:
                self.session.load_career_results(path)
                self.dev_advantage_var.set(self.session.dev_favorable_mode)
                for page in list(self._pages):
                    self._refresh_page(page)
                self._refresh_header()
                self.status_var.set("Career result archive loaded; player/lineup state was NOT restored.")
            except Exception as exc:
                messagebox.showerror("Load career results", str(exc), parent=self)

    def _save_world_results(self) -> None:
        path = filedialog.asksaveasfilename(
            parent=self, title="Save English world results only",
            defaultextension=".json", filetypes=(("JSON files", "*.json"),),
        )
        if not path:
            return
        try:
            self.session.save_world(path)
        except (OSError, ValueError, RuntimeError) as exc:
            messagebox.showerror("Save English world", str(exc), parent=self)
            return
        self.status_var.set("World results saved (not full player/squad save).")

    def _load_world_results(self) -> None:
        path = filedialog.askopenfilename(
            parent=self, title="Load English world results only",
            filetypes=(("JSON files", "*.json"),),
        )
        if not path:
            return
        try:
            self.session.load_world(path)
        except (OSError, ValueError, RuntimeError, KeyError) as exc:
            messagebox.showerror("Load English world", str(exc), parent=self)
            return
        self.status_var.set("World results loaded (player/squad state is not restored).")
        self._refresh_page(self._active_page)

    def _reset_sandbox(self) -> None:
        self.session.reset()
        self.status_var.set("Sandbox reset to its initial state.")
        self._refresh_header()
        for page in list(self._pages):
            self._refresh_page(page)


def run() -> None:
    app = DevelopmentUI()
    app.mainloop()
