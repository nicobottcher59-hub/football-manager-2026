# Developer Notes

> **TS-20 - Player DNA & Dressing Room:** automatic, evolving squad hierarchy,
> private personality profiles and a small, capped social morale context. Includes
> the portable Dressing Room page; no mandatory meetings or manual relationships.
> See [installation](TS_20_INSTRUCTIONS.txt), [design](docs/TS_20_PLAYER_DNA_DRESSING_ROOM.md)
> and [validation](TS_20_TEST_REPORT.md). Reads old careers; writes career format 4.
> Back up saves before upgrading. No Node.js is required to run the game.

> **TS-19 - Tactical Studio 2.0:** integrated portable editor, independent phase targets,
> tactic library, scheduled match plans and fast tactical consumers. See
> [installation](TS_19_TACTICAL_STUDIO_INSTRUCTIONS.txt), [implementation](docs/TS_19_TACTICAL_STUDIO.md)
> and [executed validation](TS_19_TEST_REPORT.md). No Node.js is required to run the game.

## Current state

- Phase 1 player domain model implemented.
- Phase 1.1 expanded attribute model implemented.
- Phase 2 club, squad, formation and lineup domain implemented.
- Phase 3 tactical domain implemented.
- Phase 3.1 independent in-possession/out-of-possession team shapes implemented.
- Phase 4 immutable MatchSnapshot and pre-match context implemented.
- Phase 5.0 spatial Match Engine core implemented.
- Phase 5.1 tactical positioning implemented.
- Phase 5.2 perception and possession decision-making implemented.
- Phase 5.3 passing and controlled-possession execution implemented.
- Phase 5.4 pressing, coverage and defensive-duel foundation implemented.
- Phase 5.5 ball progression, off-ball runs, dribbling and crossing implemented.
- Phase 5.6 contextual xG, physical shooting, shot blocks, goalkeeper reactions, saves, rebounds and goals implemented.
- Phase 5.7 autonomous match flow, periods, added time, restarts, score, extra time, penalties and structured events implemented.
- Phase 5.8 live match context, fatigue, weather/pitch effects, referee decisions, cards and in-match penalties implemented.
- Phase 5.9 output/playback layer, integrated-match stabilization and the large organic movement overhaul are implemented; final visual review is pending.
- Phase 5.10A/B/C calibration harness, RNG/event integrity, strength curves and tactical ablation are implemented.
- Phase 5.11A player OVR/ACT foundation, confidence baseline, adaptability, conservative positive modifiers, total-context excellence and snapshot rating integration are implemented.
- Phase 5.11B Fast Match Simulator MVP is implemented as a separate non-spatial path with seeded outcomes, team/player statistics, scorers/assists and competition tiebreak support.
- Phase 5.11C Fast Simulator calibration is implemented with a clean neutral benchmark, mixed batches, strength/ACT curves, meaningful tactical execution, tactical ablations, opponent-dependent tactical matchups, an explicit coach-vs-squad-quality benchmark and a synthetic 20-team league.
- Phase 6.0 disposable development UI is implemented with Home, Squad, Tactics, Calendar and Competitions pages, real Quick Sim integration, XI/bench swapping, a drag-and-drop tactical pitch for starter slot swaps, manual formation/role/team-instruction editing, and collective familiarity/chemistry/condition/morale diagnostics.
- Phase 6.0b contextual role OVR and dynamic position learning are implemented: role attribute weights now drive assignment-specific OVR, positional familiarity and side/foot fit modify that OVR, ACT remains the current-execution layer, and match minutes can grow/decay positional familiarity with automatic primary/secondary interpretation.
- Phase 6.1 generic Competition Framework is implemented: stable competition definitions, season editions, ordered stages, unscheduled sporting fixtures, competition regulations, configurable qualification routes and lightweight dict serialization. League positions can map to continental competition berths, promotion, relegation or playoffs without league-specific hardcoding.
- Phase 6.2 Round-Robin League is implemented: 20-club double round-robin generation/validation, seeded-vs-generated fixture provenance, reusable fixture templates for later seasons, league results, standings, configurable points/tie-breaks and StandingRowSnapshot integration.
- Phase 6.3 Knockout Competitions is implemented: seeded/generated draws, single-leg and two-legged ties, aggregate resolution without away-goals rules, deciding-leg extra time/penalties context, automatic winner advancement and a disposable bracket inspector.
- Phase 6.4 Multi-Stage Competitions is implemented: standings-based stage routing (direct advance / playoff / elimination), recombination of direct qualifiers with playoff winners, a disposable league-phase-to-knockout inspector, cross-competition DEV scheduling and result-driven morale changes.
- The current 2D engine is frozen as a legacy/experimental path; new game systems will target the Fast Match Simulator.
- Player data is loaded from JSON.
- Outfield and goalkeeper attribute profiles are supported.
- Player state and positional familiarity are separated from base ability.
- Starting XI and bench validation are in place.
- MatchSnapshot freezes lineups, tactics, player state/familiarity, competition context,
  kits, weather, pitch, stadium and referee data for simulation.
- Spatial match state contains 22 active agents, ball state, fixed-step clock and
  deterministic match-owned randomness.
- Tactical positioning converts team/role instructions into measurable spatial targets
  and bounded player movement for in-possession and out-of-possession shapes.
- Player perception exposes pressure, local space, goal context, candidate receivers and
  passing-lane quality from the actual spatial state.
- The decision layer evaluates context-valid possession actions from tactical fit, spatial
  value, player capability, decision quality and risk.
- The passing layer executes short/progressive/long pass intentions through the actual 2D
  ball trajectory, interception and first-touch resolution before possession transfers.
- The defending layer turns pressing intensity/schemes, force direction, marking and player
  instructions into real closing/coverage movement, then resolves tackles as separate spatial
  duels with defender-control, attacker-retains and loose-ball outcomes.
- The progression layer executes carries, one-on-one dribbles, forward/inside/wide runs,
  overlaps/underlaps, progressive passes into moving space and physical cross/cutback trajectories.
- The shooting layer separates chance xG from player finishing, executes foot shots/headers through
  real ball trajectories, allows physical blocks, moves the goalkeeper during the shot, and resolves
  saved/parried/blocked/off-target/woodwork/goal outcomes.
- The match-flow layer orchestrates existing decisions/actions into complete periods, handles score and dead-ball restarts, resolves competition-derived extra time/penalties, and emits structured events for later presentation.
- The match-context layer evolves runtime fatigue/fitness and feeds weather, pitch, surface, small situational home context and referee tendencies into the systems that actually consume them without mutating base player ratings.
- Yellow/second-yellow/direct-red cards remove dismissed players from active spatial play while preserving their match record, and penalty-area fouls can resolve as in-match penalty events.

## Run tests

```powershell
python -m pytest
```

Expected current result:

```text
570 tests collected (run by blocks when calibration suites exceed the runner time budget)
```


## Run the Phase 6.0 disposable development UI

```powershell
$env:PYTHONPATH = "src"
python -m football_manager.dev_ui
```

This Tkinter UI is intentionally disposable. It is a development shell for making OVR/ACT, lineup choices, drag-and-drop starter position swaps, manually editable formations/roles/team instructions, collective familiarity/chemistry/condition/morale, Fast Match Simulator results and post-match state visible before the final UI exists. Calendar now exposes the full known DEV schedule for the managed club across Premier, FA Cup, Carabao Cup and Development Continental, including conditional TBD knockout slots. Continue follows that cross-competition chronology and recovery uses the actual DEV day gap. Competitions exposes League / legacy Development Cup / Multi-stage / EFL leagues plus an FA Cup / Carabao bracket inspector. From Phase 6.5, the managed DEV chronology is backed by the real `SeasonCalendar` domain rather than a second scheduling model. A separate Calendar tab exposes the packaged official Premier League 2026/27 fixture dataset as a data inspector only; it is not bound to Northbridge or the fictional DEV clubs. Phase 6.5a adds a third Calendar tab for EFL kickoff-slot templates (three fictional 24-club divisions, 552 generated fixtures each) and an EFL leagues spectator tab with strength bands, league table, 46-round selector and DEV-only round simulation.

## Official schedule data

Phase 6.5 packages the official Premier League 2026/27 fixture snapshot under `football_manager.data/official/england/`. Load it through `load_premier_league_2026_27()`; UI/application code should not parse the CSV directly. The loader validates all 380 fixtures as a complete 20-club double round-robin and returns both the competition edition and a `SeasonCalendar`. The snapshot records its official source metadata and remains subject to later real-world fixture changes.

## EFL 2026/27 fictional clubs / real published date slots

Use `load_efl_2026_27_slots("championship" | "league-one" | "league-two")` to parse the three bundled 46-round × 12-slot templates. `build_development_efl_2026_27(key)` builds each fictional 24-team double round-robin + `SeasonCalendar`; the `ScheduledFixture.source` values remain `GENERATED` because no real EFL pairings or real club identities are imported. Date/time slots are UTC and preserve the published distribution, including occasional later rescheduled kickoffs. Data sources and limitations: `docs/PHASE_6_5A_EFL_FIXTURE_SLOTS.md`.

In the sandbox check `Calendar -> EFL 2026/27 — fictional clubs`, and `Competitions -> EFL leagues (DEV)` for standings/strength/round simulation. Phase 6.6 now automatically advances spectator leagues and cup fixtures chronologically as the managed club plays/continues; the manual DEV EFL round inspector is an optional shortcut against the same persistent results ledger.

## Phase 6.5b + 6.6 — English cups and persistent world results

Run the usual sandbox and inspect `Competitions -> FA Cup / Carabao`. The legacy eight-club Development Cup is now **inspector-only** and is not part of the managed English season. `Quick Sim` registers a managed Premier/FA Cup/Carabao fixture once in `WorldSeasonRunner`; `Continue` advances background fixtures for all four leagues and both cups only as far as the next managed event. Cup winners trigger the next generated draw with new dated fixtures. Northbridge's calendar interleaves these competitions. The original eight-club continental test remains a legacy inspector; Phase 6.6b adds the modern 36-club UEFA competitions to the canonical world runner.

`WorldSeasonRunner.save_json(path)` and `load_json(path)` persist fixture IDs, statuses, all league and cup results, exact cup draw history, season provenance and deterministic DEV strength/seed inputs. Saves are written atomically. In the sandbox, sidebar buttons `Save world results (JSON)` / `Load world results (JSON)` operate on **competition results only**. They do NOT save/restore player fitness, morale, tactics, match RNG seed, lineup decisions or a complete career; a comprehensive game save is a separate future feature. Avoid interpreting this tool as a full saved game.

The Carabao preliminary, Round One and Round Two structure uses 92 fictional professional clubs; nine *fictionally designated* Premier European entrants join in Round Three. Semi-finals are two-legged. FA Cup starts the simulated qualifier at Fourth Qualifying with 64 fictional non-league clubs; earlier FA qualifying stages are stored as **published dates only**, not fully simulated. EFL regionalisation of early Carabao draws and exact real first-season draw pairings are **not simulated**, because fictional clubs have no grounded regional identity. First-season official cup window dates are distinct from `GENERATED` simulated pairings.

To inspect the canonical ledger programmatically:

```powershell
$env:PYTHONPATH = "src"
python -c "from football_manager.dev_ui import DevelopmentSession; s = DevelopmentSession(); print(s.world_summary)"
```

Details and official calendar sources: `docs/PHASE_6_5B_6_6_ENGLISH_CUPS_WORLD_RUNNER.md`.

## Run the Fast Match Simulator MVP

```powershell
$env:PYTHONPATH = "src"
python examples/demo_fast_match_simulator.py
```

The demo prints one full result, verifies same-seed reproducibility and runs a 1000-match equal-team speed/distribution sample.

## Run Fast Simulator calibration

```powershell
$env:PYTHONPATH = "src"
python tools/calibrate_fast.py --matches 200
```

This runs the clean neutral benchmark, mixed fixtures, quality and ACT curves, tactical execution/ablations, tactical matchup counters and a synthetic league. CSV/Markdown reports are written to `reports/fast_calibration/`.

## Run the current 2D prototype (legacy / experimental)

```powershell
$env:PYTHONPATH = "src"
python -m football_manager.main
```

## Run the Phase 5.9 debug match viewer

```powershell
$env:PYTHONPATH = "src"
python examples/demo_match_viewer.py
```

The viewer supports 2D/text/combined views, commentary densities, live match stats, x1/x2/x4, instant result, same/new seed controls, substitutions, live tactical/formation/role adjustments and optional debug overlays. x1 is presentation-compressed to roughly a nine-minute real-time full match while the simulation continues to use the fixed 0.25-second internal timestep.

Optional headless playback check:

```powershell
$env:PYTHONPATH = "src"
python examples/demo_output_playback.py
```

## Fast knockout benchmark

Phase 5.11D extra-time and penalty-shootout validation:

```powershell
$env:PYTHONPATH = "src"
python tools/calibrate_fast_knockout.py --matches 500
```

This benchmark verifies extra-time pace/fatigue, extra-time substitutions, shootout conversion/length/balance and the effect of penalty specialists without using the 2D engine.

## Run condition / recovery calibration

Phase 5.11E physical-state validation:

```powershell
$env:PYTHONPATH = "src"
python tools/calibrate_condition.py --matches 200
```

This benchmark checks 90/120-minute depletion, stamina, tactical workload, natural-fitness recovery and integrated Fast Simulator post-match condition/fatigue.

## Documentation

See:

- `docs/PHASE_1_IMPLEMENTATION.md`
- `docs/PHASE_1_1_ATTRIBUTES.md`
- `docs/PHASE_2_CLUBS_LINEUPS.md`
- `docs/PHASE_3_TACTICS.md`
- `docs/PHASE_3_1_PHASE_SHAPES.md`
- `docs/PHASE_4_MATCH_SNAPSHOT.md`
- `docs/PHASE_5_SPATIAL_MATCH_ENGINE_ROADMAP.md`
- `docs/PHASE_5_0_SPATIAL_CORE.md`
- `docs/PHASE_5_1_TACTICAL_POSITIONING.md`
- `docs/PHASE_5_2_PERCEPTION_DECISION_MAKING.md`
- `docs/PHASE_5_3_PASSING_POSSESSION.md`
- `docs/PHASE_5_4_PRESSING_DEFENSIVE_DUELS.md`
- `docs/PHASE_5_5_BALL_PROGRESSION.md`
- `docs/PHASE_5_6_CHANCES_SHOOTING_GOALKEEPERS.md`
- `docs/PHASE_5_7_MATCH_FLOW.md`
- `docs/PHASE_5_8_MATCH_CONTEXT.md`
- `docs/PHASE_5_9_OUTPUT_PLAYBACK.md`
- `docs/PHASE_5_10_CALIBRATION.md`
- `docs/PHASE_5_11A_PLAYER_RATINGS.md`
- `docs/PHASE_5_11B_FAST_MATCH_SIMULATOR.md`
- `docs/PHASE_5_11C_FAST_SIMULATOR_CALIBRATION.md`
- `docs/PHASE_5_11D_EXTRA_TIME_PENALTIES.md`
- `docs/PHASE_5_11E_CONDITION_RECOVERY.md`
- `docs/PHASE_6_0_DEVELOPMENT_UI.md`
- `docs/PHASE_6_0B_ROLE_OVR_POSITION_LEARNING.md`
- `docs/PHASE_6_1_COMPETITION_FRAMEWORK.md`
- `docs/PHASE_6_2_ROUND_ROBIN_LEAGUE.md`
- `docs/PHASE_6_3_KNOCKOUT_COMPETITIONS.md`
- `docs/PHASE_6_4_MULTI_STAGE_COMPETITIONS.md`
- `docs/PHASE_6_5_CALENDAR_SCHEDULING.md`
- `docs/CURRENT_STATUS.md`

## Phase 6.6a + 6.6b - UEFA, EFL Trophy, ACT and calendar

One WorldSeasonRunner now includes four leagues, FA Cup, Carabao Cup, three UEFA tournaments, and EFL Trophy. `Competitions -> UEFA / EFL Trophy` displays league-phase/group standings, Trophy group selector, knockout brackets and champions. `Calendar -> UEFA / EFL Trophy` lists dated generated fixtures; the managed Calendar includes Champions games, no Development Continental placeholders, with V/E/D indicators. Every staged result and draw is stored in the world-results JSON, but NOT player/tactic/career state. The managed team plays its Champions fixtures with FastMatchSimulator. See `docs/PHASE_6_6A_6_6B_UEFA_TROPHY_FIXES.md` for official round windows versus generated fixture provenance and draw limitations.

## Phase 6.7 — Multi-season world career and full-season DEV test button

- Start `python -m football_manager.dev_ui`; the new **Simulate entire season (DEV)** button lives on Home. By default, the sandbox checkbox **DEV advantage: weaker rivals** is ON, but it can be turned off at any point before the run; game-engine calibration and background club strengths are unchanged. The simulated Northbridge matches are genuine FastMatchSimulator results, never scripted victories.
- The GUI runs the bulk action on a worker thread, displays managed-match progress and disables conflicting actions. Once the world is finished, **Start next season** archives the edition, applies English promotion/relegation and European allocation, and generates 2027/28 fixture editions. Repeat for subsequent seasons.
- Championships playoffs from 2026/27 use six teams; League One and Two use four. Their generated schedules are visible in **Competitions → Knockout** when each table is final, and all 17 matches are registered in the Runner. The season finishes with 2,959 world results in the reference scenario.
- **Save/Load career results (JSON)** preserves the season results archive (`WorldCareer`, current schema 1 and `WorldSeasonRunner` schema 3). It does NOT save/restore manager squads, player physical state, tactic settings or contracts. Single-season result save remains available separately.
- Future competition dates and opponent pairs are GENERATED, not official fixture release data. `EuropeanAccessPolicy` is configurable and intentionally not a fixed 2027/28 UEFA access list.
- Key files: `src/football_manager/domain/season_cycle.py`, `domain/career.py`, `data/future_seasons.py`; new integration coverage `tests/test_phase6_7_full_season_integration.py`. More detail in `docs/PHASE_6_7_FULL_SEASON_INTEGRATION.md`.

## UI-1 (after Phase 6.7) — React frontend preview

The user-approved dashboard layout now has a React + TypeScript implementation under `frontend/`; this is a **presentation prototype** and **not** a Tkinter replacement or engine integration. To start: `cd frontend`, `npm install`, `npm run dev`, then open http://127.0.0.1:5173 . `npm run build` is the frontend type-check + build validation. The actual Python sandbox and all its previous tests remain unchanged.

All UI-1 values come from `frontend/src/data/dashboard.ts` and are illustrative. Continue adds exactly one **demo** date; no simulated world event occurs. Refer to `docs/PHASE_UI_1_DASHBOARD_SHELL.md` for contracts, integration risks and next increments. The older "next development step: 6.7" text above describes the prior 6.x milestone; 6.7 is already present in the supplied ZIP.

## UI-1 portable Windows launcher (no installs required)

Double-click `INICIAR_INTERFAZ_WINDOWS.bat` from the repository root, or open `frontend/portable/index.html` in a modern browser. The bundled files are an offline HTML/CSS/JavaScript **pre-rendered snapshot** of the UI-1 React components, with mock-only navigation, competition tabs, dialogs, stories and Continue date display. There is no Node, npm or Python dependency to view the portable snapshot. These files are intentionally not a production React build or an engine bridge; real career progression is unaffected.

The React + TypeScript source of truth stays in `frontend/src/`. Refresh the portable snapshot when UI source changes. See `UI_1_PORTABLE_INSTRUCTIONS.txt`.


## UI-2 — Squad + roles + tacticas (Python DEV runtime)

El lanzamiento portable de UI-1 queda **sustituido** por `INICIAR_INTERFAZ_WINDOWS.bat`: ahora requiere Python (ya instalado para el juego) y NO requiere Node/npm. El .bat lanza `python -m football_manager.ui_shell` usando `PYTHONPATH=src`, abre el Dashboard portable desde un servidor stdlib de loopback, y permite acceder a Squad y Tactics. Abrir el archivo HTML directamente sirve solo para consultar la maqueta UI-1 sin acciones de Python.

Tacticas/roles/formacion usan los metodos existentes de `DevelopmentSession`, `Tactic` y los modelos de `football_manager.domain`. Ninguna valoracion se recalcula en JavaScript. La vista usa la implementacion compartida `frontend/public/squad/` tanto en el shell HTML como en el frontend React con un iframe, como compromiso transitorio para soporte Windows sin npm. API: GET/POST `/api/squad` solo por 127.0.0.1:8765; Vite hace proxy en modo dev si se utiliza React.

Al abrir `http://127.0.0.1:8765/`, el servidor redirige a `/portable/` para que los enlaces relativos `styles.css`, `data/demo.js`, `portable.js` y `assets/` se resuelvan correctamente. Si el navegador muestra HTML sin estilos y 404 en esos archivos, cierra el proceso Python, aplica el hotfix de rutas UI-2 y relanza el `.bat`.

Tests UI-2: `python -m pytest -q tests/test_ui_shell_squad.py`. Adicional (en entorno con Node): `node tests/ui/test_board.cjs`. Para regresion: `python -m pytest -q tests/test_phase6_0_development_ui.py tests/test_tactics.py tests/test_phase6_0b_role_ovr_familiarity.py`.

**Limites:** La sesion DEV es efimera; los cambios se pierden al cerrar el servidor. Home/Continue son demo. No confundir panel de pelota parada con una funcion implementada. La visualizacion de fichitas es un esquema explicativo, no el simulador 2D congelado. Ver `docs/PHASE_UI_2_SQUAD_TACTICS.md`.


## UI-3 — Squad roster + Tactics polish (after UI-2 and its asset hotfix)

Three sortable Squad table views (General, Attributes [all current domain attributes], Season Stats [explicitly unavailable until season aggregation]), fixed player column, player-row expansion with **dynamic position familiarity**, ephemeral UI-only shirt numbers and player availability. Tactics keeps its approved XI, individual role/instructions and 44-parameter team editor together; the one in/out possession selector is shared. OVR/ACT use one-decimal display throughout updated views.

Apply the incremental UI-3 ZIP over committed UI-2 + 404 hotfix; launch the same `INICIAR_INTERFAZ_WINDOWS.bat`. New Python shell admin state is NOT a player-market or manager save: contract, negotiations, training, xA, season ledger and external player photos remain unimplemented, displayed as `—` or disabled. The underlying match engine / runner are unchanged.

Tests: `python -m pytest -q tests/test_ui3_roster.py`, `python -m pytest -q tests/test_ui_shell_squad.py` and the Phase 6.0 development-ui/tactics/role regression suite. See `docs/PHASE_UI_3_SQUAD_ROSTER.md`.

## UI-3.1 — Visual polish + Home connected to Python DEV

UI-3.1 keeps the UI-3 layout and scale, enhances depth/color and adds consistent deterministic illustrated player portraits in **Home, Squad and Tactics**, including nationality in roster and player details. Squad's expanded row now separates profile, current state, positional familiarity, attribute highlights and player-management actions. The Home starting XI, formation, dynamic status metrics, current date and opponent read **the same local Python DEV session** used by Squad/Tactics; returning to Home after changing a starter shows the changed team. OVR/ACT use one decimal.

Start in Windows with `INICIAR_INTERFAZ_WINDOWS.bat` (no npm). **This is still a temporary DEV session**: no persistence, no daily Continue, no contracts/market/training/player conversations/season ledger. The league table, news, manager/club story content and several club card fields remain labeled visual demo data; Python calendar match metadata is only partially available. See `docs/PHASE_UI_3_1_VISUAL_POLISH.md`.

## UI-3.2 — Canonical managed Calendar (Python development UI)

The portable UI now exposes `GET /api/calendar` from `src/football_manager/ui_shell/calendar.py`. It is a read-only projection of `DevelopmentSession._season_calendar` + `WorldSeasonRunner`; the source world remains authoritative. The browser uses `frontend/portable/calendar.js` and `calendar.css`. Clicking Home's Match Preview opens Calendar, not a demo result modal. Calendar monthly navigation does not call any simulation command. A missing future cup draw is omitted rather than replaced with a fictitious conditional match.

Position sorting in Squad is now a documented football order with reverse sorting, covering all current `Position` enum values. Tests: `PYTHONPATH=src python -m pytest -q tests/test_ui32_calendar.py`. Detailed capabilities: `docs/PHASE_UI_3_2_CALENDAR.md`.

## UI-3.3 — Python-backed competition centre (Windows portable)

Run `INICIAR_INTERFAZ_WINDOWS.bat` from the repository root with Python installed; no Node or npm required. `GET /api/competitions` enumerates canonical `DevelopmentSession._world` leagues, cups and staged competitions. `GET /api/competitions/<id>` projects one complete table/matchday set or actual knockout draw history from `WorldSeasonRunner`; invalid IDs return 404. Both routes are read-only, loopback-only and use the existing runtime lock. Rendering assets: `frontend/portable/competitions.js` and `competitions.css`.

The main panel shows full standings for England's four tiers and UEFA's 36-team Swiss phases, or confirmed knockout ties with pan and 60–140% zoom. The secondary panel ALWAYS shows **all** fixtures of the chosen matchday/round, not just managed-club fixtures. For EFL Trophy, the standings picker covers 16 authentic model groups; each group-stage matchday sidebar includes all 32 games across groups. Fixtures, UTC kickoffs, scores, penalties and aggregates are read from canonical state. There is no hypothetical future draw or bracket predictor for randomly drawn competitions.

Run `python -m pytest -q tests/test_ui33_competitions.py` (from root; set `PYTHONPATH=src` if needed). This is a temporary DEV view, not full career persistence; no save, real Continue, team financial system, or imported licensed club logos are added. See `docs/PHASE_UI_3_3_COMPETITIONS.md`.


## UI-3.3.1 — Bilateral bracket / club-only tabs

The competitions index distinguishes `competitions` (managed club registrations, including later domestic cup entrants) from `other_competitions` (future Other Leagues screen). Bilateral bracket with semantic zoom and confirmed-only tie progression; no fake draw paths. Windows remains standard-library Python portable. See `docs/PHASE_UI_3_3_1_COMPETITIONS_REFINEMENT.md`.

## UI-3.3.2 — Competition Explorer (read-only)

`competition_options()` preserves the managed/other partition and directory metadata (`participant_type`, `scope`, `continent`, `country`, `division`, `competition_type`). After the UI-3.3.2 hotfix, there are TWO independent sidebar routes: `Competitions` (original UI-3.3.1 club tabs, including FA Cup even with a later entry date) and `Other Leagues` (directory-only filters). The competition renderer shares the canonical `GET /api/competitions` and per-ID endpoints, but its `mount(root, 'mine'|'other')` selects the correct route without modifying the world. The continent filter is always visible; national country options include future regions with empty-state feedback, not fabricated leagues. This specifically resolves the prior non-useful country picker that exposed only England.

The full bilateral bracket and its four-step semantic zoom are carried over from UI-3.3.1. No simulator, match generation or persistence code changed. Verify with `PYTHONPATH=src python -m pytest -q tests/test_ui33_competitions.py tests/test_ui332_competition_explorer.py` and run the normal `INICIAR_INTERFAZ_WINDOWS.bat` launcher on Windows. See `docs/PHASE_UI_3_3_2_COMPETITION_EXPLORER.md`.

## UI-3.4: Python World daily advance + Calendar fast-forward

Local API: `GET /api/progression`, `POST /api/progression` with `advance_day` or `simulate_until` (`date=YYYY-MM-DD`). One-day Continue halts on managed matchday; Calendar fast-forward deliberately **plays through managed matches** using the real FastMatchSimulator and records them in WorldSeasonRunner. State commit is transactional in-memory (copy-then-swap). Browser Go to Match currently shows an honest waiting dialog; the user-approved separate match tab is a later task.

Run `PYTHONPATH=src python -m pytest -q tests/test_ui34_daily_progression.py`. This remains a **temporary DEV session**, not a complete career save. See `docs/PHASE_UI_3_4_DAILY_CONTINUE.md` and `docs/TECHNICAL_PREFLIGHT_UI_3_4.md` for constraints and acceptance.

## UI-3.4.1 — Async Calendar simulation progress (portable, stdlib)

`src/football_manager/ui_shell/simulation_jobs.py` implements an in-memory result-feed worker over a deep copy of the existing DEV session. `progression.simulate_until(..., on_day=...)` emits only canonical newly played fixtures (background WorldRunner or managed FastMatchSimulator). No match or calendar algorithm was replaced.

`POST /api/progression/jobs` starts a one-at-a-time job, while `GET /api/progression/jobs/<opaque-id>?after=<cursor>&limit=<1..100>` reports the real completed days, actual match results, and atomic commit/failure state. During an active job, writes are rejected with 409; normal GET routes still read the prior committed world. **Do not confuse in-memory transactionality with a complete persisted save game**.

The portable assets `calendar.js`, `calendar.css`, `simulation.js`, and `simulation.css` implement whole-cell dates, darker past days and the full-screen actual-results feed with optional display speed. The numeric progression bar measures Python's *processed days*, not animation progress. The overlay closes only after successful completion or a failure acknowledged by the user. UI-3.4's one-day Continue and Go to Match behavior remains unchanged.

Run `PYTHONPATH=src python -m pytest -q tests/test_ui341_calendar_progress.py tests/test_ui34_daily_progression.py` and inspect Windows at 75% browser zoom. See `docs/PHASE_UI_3_4_1_CALENDAR_PROGRESS.md`. No Node/npm or full saved manager career yet; pre-match screen is next.


### UI-3.4.1 hotfix — Club-only playback and custom confirm

The Python worker and progress API are **unchanged** and still process every world fixture. `simulation.js` paginates through all genuine result events using the normal server cursor, but queues/renders only events whose canonical `managed` flag is `true`. The status bar is authoritative for elapsed world days; the feed count means *managed club results shown*. No fake fixture, simulation delay or altered match result is introduced. A no-club-match interval shows an explicit empty state.

`FMSimulationOverlay.confirm({target,fromDate,knownMatches})` replaces the native `window.confirm()`. Its preview count includes *currently scheduled* club matches only; future cup draws may increase that count. Start and Cancel are explicit, and Escape / backdrop cancellation does not invoke the Python API. Both changes use existing portable assets and require no npm.

Run `PYTHONPATH=src python -m pytest -q tests/test_ui3411_calendar_club_results_modal.py` plus the previous UI-3.4.1 regressions. The frontend custom modal and feed filter were additionally exercised in a Chromium UI smoke test (Cancel/Escape, one server start, mixed managed/background result events).

## UI-3.5 — Matchday endpoints and transactional match tactics

`/portable/match.html` is a dedicated browser tab, not a React/Vite page. `GET /api/match` exports actual current-day managed XI/opponent/bench/availability/fixture metadata plus tactical edit schema. `POST /api/match` (`fixture_id` mandatory) accepts `match_tactic`, `reset_match_tactics`, `match_kits`, `quick_sim`; see `ui_shell/match.py` and `ui_shell/server.py`. Existing protected Calendar jobs block match edits. Match-tactic commands are **isolated per fixture**, replayed/validated against a deep copy, and discarded after match simulation. A single Quick Sim commits the successful result and state exactly once; repeat attempts are rejected. `FastMatchResult` supplies goals, cards, substitutions, shootout kicks, xG, possession, passes, fouls and corners. Referee pools, shirt colors and weather labels are presentation-only. Injuries during the match, tackle counts, ordinary missed penalties, actual staff identities and full save/load are **not implemented**. `tests/test_ui35_matchday.py` covers the HTTP contract and nonpersistent match tactics.

### UI-3.5.1 — Matchday controls (UI-only)

The match tab (`frontend/portable/match.js` and `match.css`) adds native HTML drag-and-drop on real starter and bench IDs. `swap_starters` operates on **slot IDs** and `swap_bench` on **starter/bench player IDs**, both wrapped by `POST /api/match` with `action=match_tactic`. Bench-click followed by starter-click and the existing dropdown replacement controls remain available for touch, keyboard and assistive users. Backend validation and match-only replay are unchanged. Shirt colour preview is staged in local UI state; only Save sends `action=match_kits`; Reset discards the preview locally. Events have a home/center/away layout with glyph and text grouped in the same team lane. Engine cannot generate in-match injury events or tackle counts. New tests: `tests/test_ui351_matchday_refinements.py`. No Node.js/npm required.
