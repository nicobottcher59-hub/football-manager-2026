# TS-UI-02.13 — Squad 01C + 01D Visual Depth Pass

**Date:** 2026-10-21  
**Prerequisite:** TS-UI-02.12 installed  
**Scope:** Frontend presentation for **Status & development** and **Contract & actions** only.

## Updated files (patch contents)

1. `frontend/public/squad/squad_ui02.js` — refreshed 01C/01D markup, recorded-morale face and reusable action tiles.
2. `frontend/public/squad/presentation.js` — compact development board, improved truthful no-review state and training-focus panel.
3. `frontend/public/squad/squad_ui029.css` — scoped visual depth and motion rules inside the existing Squad CSS; **no additional stylesheet**.
4. `tests/test_ts_ui_02_13_visual_depth.py` — regression assertions for scope, semantics and active actions.
5. `TS_UI_02_13_TEST_REPORT.md` — this report.

## UX implemented

### 01C: Status & development

- Three distinct dashboard panels with green fitness, cyan form, and contextual gold/green morale treatments; differentiated depth and visual hierarchy rather than identical flat cards.
- Recorded player condition (0–100) displayed with a vivid accessible ring, real match sharpness/fatigue meters; recorded form with an animated bar; recorded morale with a reactive expression and meter.
- Current availability is still computed from injury/suspension/available fields. No happiness value is inferred from morale.
- Development workspace combines a brighter reference-OVR scene and training-focus control with subtle background geometry.
- **No fake matches, trend points, or player potential:** a development line is drawn only from two or more recorded monthly reference-OVR observations. Pending state uses purely decorative vector motifs and explicit text.
- Detailed recorded reviews/methodology remain behind the original accessible disclosure.

### 01D: Contract & actions

- Weekly wage and market valuation are prominent and visually distinct; expiry date, squad number and contract status have improved hierarchy.
- Status seal draws on recorded contract state and a real expiration countdown; **no fabricated contract-completion percentage**.
- Existing actionable contracts, player number assignment, transfer-list status and cross-section navigation were retained. Buttons are now compact game-style action tiles with consistent accessible labels and visible focus/hover states.
- Rival player profiles remain read-only, with only the already-supported transfer-offer shortcut.

### Unchanged

- 01A Profile / Attributes, 01B Season statistics (**approved function byte-for-byte unchanged by SHA-256 check**), roster directory, player hero, kits/crests, club registry, Python endpoints and commands, gameplay, persistence and save formats.
- Club scaling through `--s2-club-*` theme tokens; no Sunderland/Brighton CSS overrides.

## Verification performed

- `node --check frontend/public/squad/squad_ui02.js` — PASS.
- `node --check frontend/public/squad/presentation.js` — PASS.
- `PYTHONPATH=src pytest tests/test_ts_ui_02_*.py -v` — **103 passed**.
- Chromium: responsive render checks at **1680, 1366, 1250, 980, 730, 560 and 390 px**, with both changed tabs; no page script errors or horizontal inspector overflow. Smaller layouts keep vertical scrolling within the tab.
- Chromium functional interaction checks using **actual Python read-model responses**, with stubbed transport for browser API calls: training focus command and receipt, squad-number command, transfer status command, original selection/tab identity, readonly controls and player-review chart thresholds — PASS.
- Only synthetic **test fixture** development observations were used to exercise the optional history curve. These were never persisted into a save or presented as real player history.

Browser visual checks use Chromium to paint the actual project CSS/JS against responses retrieved from the Python game server; the test environment restricts Chromium's direct localhost navigation, so only browser fetch transport was stubbed. **Final user acceptance in Windows with an actual saved career is pending.**

## Install

1. Stop the game/Python UI.
2. Extract this ZIP over the root of `football-manager-2026` **on top of TS-UI-02.12**, preserving folder paths and replacing matching files.
3. Start the Python UI. On Codespaces: `cd /workspaces/football-manager-2026 && PYTHONPATH=src python3 -m football_manager.ui_shell`.
4. Open Squad -> Status & development and Contract & actions; if an older layout persists, hard-refresh with `Ctrl + F5`.

### Suggested commit

Branch: `wip/squad-01a-redesign`  
Summary: `feat(ui): TS-UI-02.13 add depth to Squad status and contracts`  
Description: `Add visually rich, responsive status and contract dashboards with contextual lighting, animated real-value meters, honest development empty states and elevated action tiles. Preserve approved Profile/Attributes and Season statistics, club scaling, read-only restrictions, gameplay and save data.`
