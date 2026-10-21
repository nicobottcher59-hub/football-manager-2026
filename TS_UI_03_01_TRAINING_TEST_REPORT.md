# TS-UI-03.01 — Training centre (Training UX)

## Scope

Replaces the TS-26 Training centre layout with a single club-scalable dashboard. The original training group intensities, player focus, protection toggle, threshold update endpoint, staff/medical panels, and player-profile navigation remain connected to the original handlers. All Squad 02.14 files are untouched.

## Files

- `frontend/portable/club_support.js`: Training view, aggregations, roster filtering, custom dark menus and existing command handlers.
- `frontend/portable/club_support.css`: Training-specific responsive visual design, club theme, subtle animation, reduced-motion support.
- `frontend/portable/portable.js`: training route active-state CSS hook only.
- `src/football_manager/services/club_support.py`: **read-only** `training_read_model` fields: club ID/name, player position, real current match sharpness, whether saved protection rules actually reduced intensity and by which mechanism. No training logic, fixture, save, model or simulation mutation.
- `tests/test_ts_ui_training_01.py`: 5 targeted backend regression checks.

## Visual implementation

- Club catalog drives crest/name and CSS club palette; no Sunderland-specific Training code.
- Three hero KPIs: squad average condition; recorded average match sharpness; players whose effective workload is **actually reduced** by physical protection.
- Three training-group tiles with functional dark custom dropdowns; original `configure` endpoint receives unchanged group/intensity payload.
- Protection panel: toggle, range + numeric fields, save button, grounded current-policy impact counts.
- Three live analytics: condition-band population; effective training workload; **recorded** individual development focus frequency. No invented performance growth or injuries.
- Player-card roster with original portrait service, identity, position, condition, sharpness, workload, focus, actual protection state, profile navigation, search, group/focus filters.
- Responsive browser test at 1680, 1366, 980, 560 and 390 px.

## Checks performed

- `PYTHONPATH=src python -m pytest -q tests/test_ts_ui_training_01.py`: **5 passed**.
- `node --check frontend/portable/club_support.js`: passed.
- `node --check frontend/portable/portable.js`: passed.
- `python -m compileall -q src/football_manager/services/club_support.py`: passed.
- Chromium Playwright: 1680, 1366, 980, 560, 390 px; zero JS page errors; zero document/screen/roster horizontal overflow.
- Chromium UI interactions: live search; squad group and focus filters; custom dropdown group intensity POST; numeric threshold slider synchronization and POST; protection toggle POST; custom menu popup computed background rgb(10,36,57), **dark**.
- SHA256 comparison: `frontend/public/squad/squad_ui02.js`, `squad_ui029.css`, `presentation.js` identical to installed TS-UI-02.14.
- Historical `test_ts_26_club_support.py::test_training_groups_and_condition_protection` was attempted; the existing test ran beyond a 60-second execution limit. **Not reported as passed**. Global suite and Windows save verification not run.

## Known boundary

The screenshots are production Training JS rendered in an isolated Chromium shell using the Python DevelopmentSession read model, with Sunderland visual identity resolved from the checked-in club catalog. The user's actual Windows save, local navigation and image asset loading should be checked after installation.

## Install

1. Start from fully installed TS-UI-02.14.
2. Stop Python server and unzip this patch **at the repository root**, preserving relative paths.
3. Restart with `PYTHONPATH=src python3 -m football_manager.ui_shell` (or your working Windows launcher); hard refresh with Ctrl+F5.
4. In Training test changing a group intensity, physical protection and thresholds, filters, click on player profile, and confirm Squad 01A/01B/01C/01D untouched.

Date: 2026-10-21. 
