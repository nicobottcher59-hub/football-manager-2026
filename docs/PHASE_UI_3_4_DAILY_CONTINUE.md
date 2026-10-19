# UI-3.4 — Daily Continue & Calendar Auto-Simulation (Python DEV)

## Approved interaction contract

- **Continue** advances the current Python-world date by **exactly one calendar day**. Background fixtures due that day are processed via `WorldSeasonRunner`; players recover for the actual elapsed day. The UI never increments an independent mock clock.
- **Matchday:** when the controlled club has an unplayed fixture **today**, the header button reads **Go to Match** ("Ir al partido") and normal Continue cannot skip it. Clicking this button currently explains that the separate match screen / new browser tab has not yet been designed or implemented. It does **not** silently simulate the managed match.
- **Calendar → click any date → Simulate to this date** processes every day through the selected date, **including the controlled club's own games**, without pausing at them. Managed fixtures are resolved with the real `FastMatchSimulator`, using the current selected XI and tactics. Other matches use `WorldSeasonRunner`. Cup round draws only emerge after actual results; no future opponents are fabricated.
- If an actionable manager decision becomes part of the game in a later phase, fast-forward should halt on that decision. **There is no actionable decision/event queue in the current DEV session**, so this version has nothing of that type to pause for. It does not pretend to implement transfers, contracts, promises or injury decisions.
- Past dates and dates past the currently simulated season's June 30 cutoff are rejected. **Season-to-season transition is not yet connected to the portable UI**; existing Phase 6.7 `WorldCareer.begin_next_season` remains in Python.

## Architecture

`src/football_manager/ui_shell/progression.py` is a small adapter over existing `DevelopmentSession`, `WorldSeasonRunner`, `FastMatchSimulator` and `recover_player_between_matches`. It does not duplicate match algorithms.

The Python HTTP server exposes:

- `GET /api/progression`: authoritative day, season, next unplayed managed fixture, button state and feature limitations.
- `POST /api/progression`, `{"action":"advance_day"}`: one-day background advance; never simulate an unplayed managed match on or before today's date.
- `POST /api/progression`, `{"action":"simulate_until","date":"YYYY-MM-DD"}`: resolve the entire interval including managed FastMatchSimulator matches. Returns actual match IDs, outcomes, counts and updated world state.

The runtime **deep-copies the in-memory session**, processes the validated operation, and swaps the active session **only on success**. Thus a mid-progress scheduling failure cannot leave a partially advanced *active* in-memory timeline. This is not an on-disk transaction/save. Requests are serialized under the existing local runtime lock; only local origins/Host are accepted.

Home now refreshes the **real managed league table and recent five played match outcomes** from the Python APIs. Calendar displays the latest played scores, dates, winner colours, penalty details and aggregate qualification independently. The entire navbar displays the same Python date. Squad/Tactics are reloaded from Python after world progression. Competitions and Other Leagues remain separate, preserve the club/other partition and display current standings/results.

## Limitations, intentionally visible

- **No persistent complete save game.** Closing the Windows server resets the temporary DEV session. `WorldSeasonRunner.save_json` and `WorldCareer.save_json` only store results/competition career; they are not complete player/manager-state snapshots. Do not claim recovery of fatigue, tactics or roster edits after restart.
- **Go to Match is not yet the full match screen.** The user will decide its design, including opening a separate browser tab, later. Automatic managed match simulation is currently available via Calendar only.
- No event/deadline/manager-decision system exists to interrupt fast-forward yet. Add actual decision blockers when those domain systems are built.
- Player seasonal ledgers, contracts, happiness, transfer UI actions, manager finances and most news are still DEV placeholders.
- This release operates within the current season; extending the action through the 2027/28 transition requires the dedicated persistent career integration.
- Browser progress requests are synchronous and show a busy state. More complex background worker/status support can be added if later profiling demonstrates multi-season latency.

## Verification

- Tests `tests/test_ui34_daily_progression.py` cover initial match hold, one-day advance, same-day Calendar auto-sim, crossing several managed matches, full-season 2,959 results (55 managed in the tested DEV seed), invalid dates, HTTP wiring and rollback on simulated failure.
- Existing UI-3.1/3.2/3.3/3.3.2/roster/roles tests run in separate regression blocks, and JavaScript syntax checks pass.
- Chromium visual exercise (with a Python-side bridge because Chromium is blocked from direct loopback in this test environment) tests initial **Go to Match**, Calendar auto-sim of first match, single-day Continue, a skip from August 16 to September 30, the Comp. screen's four club tournaments and live Home league table. No JS runtime errors in that exercise.
- Final acceptance belongs to the user's Windows system (same `.bat` entrypoint, no Node/npm).

## Windows installation

Apply UI-3.4 **on top of the UI-3.3.2 final Hotfix 2**. Extract the ZIP's repository-relative files into the game root. Close all old Python server windows, start `INICIAR_INTERFAZ_WINDOWS.bat`, and hard-refresh Chrome with `Ctrl+Shift+R`. Do not open `index.html` via file:// because game advancement requires the local Python API.
