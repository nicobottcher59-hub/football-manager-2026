# UI-1 — Dashboard visual (React + TypeScript)

**Status:** Visual prototype delivered for manual review; Python integration NOT implemented.
**Starting point:** The uploaded Phase 6.7 repository, including English/UEFA/EFL Trophy competitions, world runner and disposable Tkinter sandbox.
**Branch suggestion:** `phase-ui-1-react-dashboard-shell`.

## Product decisions already approved

- Keep the dark, three-column dashboard layout and its widget dimensions as the visual reference.
- Use the more lively club card: crest, manager, competition, standing, points, recent form, season, stadium capacity, objective and stadium background.
- Keep Next Match and a competition-switching table/cup widget.
- Combine Squad Status and Starting XI into **one large Tactical Overview**. Show compact morale, condition, chemistry and form metrics and the eleven players on the pitch with **contextual/general OVR, never a match rating**.
- Use the full right column for Inbox/Notifications and editorial Club News, including a story-style visual section and a way to switch the inbox view.
- Put **Continue** prominently in the top header. Product requirement: **advance exactly one calendar day**, not automatically jump to the next managed fixture.
- Desktop-first Windows experience, adapt layout reasonably at smaller sizes; no user customization/reordering of widgets.

## What UI-1 delivers

- New `frontend/` React 18 + TypeScript + Vite project, without changing Python packages or simulation.
- UI shell, sidebar, dashboard sections, club icons, stadium SVG, tactical pitch, player OVR badges, competition tabs, mini condition/morale/chemistry/form widgets, notification/story preview interactions, modal and responsive styling.
- **Explicitly fake/demo UI data:** sample standings, fictional player names/OVRs, match preview, news, and alerts are all in `frontend/src/data/dashboard.ts`. No implicit claim that they correspond to WorldCareer or Northbridge's current simulated season.
- The Continue button advances the **displayed demonstration date only** by one day. A visible notice makes clear that the Python world is **not** advanced. This is not a working career Continue command.
- Sidebar destinations other than Home are visible as placeholders, not false functional management screens.
- Tkinter DEV UI stays untouched. There is no change to the FastMatchSimulator, runner, ACT/OVR formulas, saves, or domain rules.
- No Electron/Tauri executable is included in UI-1: run the UI in a local browser for design review. Desktop packaging is a separate validation milestone.

## Running and checking on Windows (PowerShell)

From repository root (on the proposed new branch, after applying the patch):

```powershell
cd frontend
npm install
npm run dev
```

Open <http://127.0.0.1:5173> in the browser. Keep the terminal open; Vite supports live reload.

For a production-asset build check:

```powershell
npm run build
```

Build output goes to `frontend/dist/`. React/Vite packages are installed by `npm install` into `frontend/node_modules/` and recorded by npm in `package-lock.json` at installation time. Neither large generated directory belongs in the incremental patch.

The legacy DEV sandbox and regression tests can be launched unchanged:

```powershell
cd ..
python -m pytest
$env:PYTHONPATH = "src"
python -m football_manager.dev_ui
```

## Architectural boundary for UI-2 (proposed, **not** implemented)

```text
React UI (typed view models; actions)
             |
     localhost application API
             |
Python application services (queries / commands)
             |
Existing domain, FastMatchSimulator, SeasonCalendar, WorldCareer, persistence
```

Avoid binding React directly to private methods of `DevelopmentSession` or Tkinter widgets. The final Python application layer should expose typed JSON view models, not mutable domain object graphs.

Potential read-model fields (examples, not existing endpoints):

- `DashboardView`: manager club id/name, current day and season, crest reference, division, stadium (if it exists), objectives (if there is a board system), next fixture, ordered standings, notifications, stories.
- `LineupView`: player ID, slot/position/role, actual contextual OVR calculated by Python, availability and physical state. **Do not calculate OVR in TypeScript.**
- `CompetitionView`: league standings where they exist, knockout stage/bracket for cups, competition provenance and status.

Potential operations (contract design only): `GET /dashboard`, `POST /continue-day`, `GET /match-preview`, later `POST /play-match` / `POST /edit-lineup`. An eventual stateful local process should own a single world/session. Use idempotent command handling and do not simulate the same fixture twice.

### Daily Continue integration: prerequisites

`DevelopmentSession.continue_to_next_match()` currently requires a completed managed match and skips forward to the next managed fixture. **It is not a per-day command.** We must introduce a game-session/application-level daily advance with the following checks:

1. Determine the current calendar day from a persistent Python game session.
2. Before advancing, block or route the user to the relevant managed pre-match view on match days; never silently auto-simulate the managed club.
3. Run eligible background fixtures/events exactly once for the completed date, without skipping the next day, and honor scheduled changes.
4. Apply day-based recovery, moral/other daily effects only via existing services or explicit newly tested ones.
5. Persist/restore the world AND manager/lineup state once real career saves exist. Current `WorldCareer` JSON only saves competition results, not full player/tactic/world state.
6. Return a fresh typed dashboard view and notify the frontend of new events; do not infer results from sample data.

Other missing data should remain explicitly unavailable until built: injuries as events, finance figures, real portrait assets, stadium capacity/name fields, a production inbox/news event feed and durable objectives/manager profile. These are currently illustrations in the visual prototype.

## Next increments to authorize separately

- **UI-2:** Python read-only application service/API, wire club/fixtures/standings/lineup OVR to real state, and typed integration tests. No frontend calculation of game rules.
- **UI-3:** one-day Continue, managed fixture gate, deterministic processing, safe persistence + notification event sources, full integration tests.
- **UI-4:** evaluate Electron vs Tauri (or another desktop host), launch/manage Python locally, offline assets, robust error handling, Windows packaging and performance checks.

## Validation notes for this environment

Node.js and a TypeScript compiler are present, but the network cannot resolve the npm registry; therefore an actual Vite/React dependency installation and production browser build must be confirmed by the user via `npm install` / `npm run build` on Windows. A syntax parse of the TSX sources is possible here, but is **not a replacement** for a dependency-backed production build. The Python test suites can be checked independently.
