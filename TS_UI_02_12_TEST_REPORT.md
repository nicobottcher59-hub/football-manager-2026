# TS-UI-02.12 — Squad: Status & development + Contract & actions

**Base:** TS-UI-02.11 (must already be installed)  
**Date:** 2026-10-21  
**Scope:** Frontend presentation only; no engine, save schema, player ability, simulation, or roster data changes.

## Updated files

1. `frontend/public/squad/squad_ui02.js`
2. `frontend/public/squad/presentation.js`
3. `frontend/public/squad/squad_ui029.css`
4. `tests/test_ts_ui_02_12_status_contract.py` (new)
5. `TS_UI_02_12_TEST_REPORT.md` (this report)

## UX changes

### Status & development (01C)

- Three compact summary cards using real player condition, sharpness, fatigue, form, morale, and availability.
- Semantic rings/meters are normalized to the existing 0–100 Python fields; unavailable metrics render as `—`.
- A compact, separately loaded development board includes reference OVR, focus selection, tracking date, next review, minutes and last recorded review change.
- A line is drawn **only when at least two actual monthly reference-OVR observations exist**. First-review and single-review states display an honest empty state instead. The chart shows neither hidden potential nor an invented time series.
- Existing training focus POST wiring and readonly blocking are preserved. Detailed notes and recorded change history are kept behind an accessible expandable disclosure rather than a wall of text.

### Contract & actions (01D)

- Four compact recorded contract facts with a separate status summary and an expiry countdown calculated from the existing `date` and `expires_on` values.
- The status motif does not represent an invented percentage of the contract's term (a start date is not in the model).
- Preserves the registered/expired/unrecorded states, squad number editor, transfer-status editor, contract negotiations shortcut and navigation to Dressing Room, Training, Tactics and Medical Centre.
- Rival profiles remain readonly with the existing transfer-offer action. No unavailable loan-management controls have been invented.

### Intentionally unchanged

- Season statistics (01B): **byte-identical function markup compared against TS-UI-02.11**, guarded by the prior-source SHA-256 test.
- Profile / Attributes (01A), roster directory, club header, player hero, kit/crest assets, club identity registry, backend APIs, career data, engine, saving and fixture simulation.
- CSS updates are appended to `squad_ui029.css`; **no additional stylesheet is introduced**.

## Executed verification

- `node --check frontend/public/squad/squad_ui02.js` — PASS.
- `node --check frontend/public/squad/presentation.js` — PASS.
- Selected Squad UI pytest regression modules `test_ts_ui_02_2` through `test_ts_ui_02_12` — **96 passed**.
- Chromium live-read-model visual checks: **1680, 1366, 980, 560 px**, both updated tabs; no JavaScript runtime errors, no horizontal inspector overflow, correct active tab; responsive internal scrolling at smaller widths.
- Chromium behavior checks, using actual API read-model payloads and stubbed transport for write requests: training focus command payload, two-review chart logic, squad number/transfer command payloads, existing action buttons, readonly restrictions, and unchanged player hero/list identity — PASS.
- Synthetic chart observations in one visual test were explicitly test-only fixtures; they were **not written to any real save**.
- ZIP member paths, hashes and CRC are verified in packaging.

## Additional regression-suite limitation

A larger historical test group `tests/test_ts_22_presentation.py` was also attempted. It stops at a stale schema assertion expecting `GRAPH_VERSION == 17`, while the current project has version `22` (`test_save_current_version_roundtrip_has_exact_stats_and_deterministic_continuation`). This is outside the TS-UI-02.12 frontend scope and has **not** been presented as passing. The broader combined suite was not completed. No Python code or save format was modified to bypass that assertion.

## Installation

1. Stop the Python server and close FM.
2. Extract the ZIP in the **root** of your `football-manager-2026` folder, keeping internal directory paths and replacing files.
3. Restart the Python UI (`PYTHONPATH=src python3 -m football_manager.ui_shell`).
4. Hard-refresh the browser (`Ctrl + F5`) if cached styles appear.
5. Confirm Squad → Status & development / Contract & actions. Season statistics should look unchanged.

In GitHub Desktop, commit on `wip/squad-01a-redesign` (or your corresponding working branch) after your own visual review. A Windows real-career manual acceptance check remains pending.
