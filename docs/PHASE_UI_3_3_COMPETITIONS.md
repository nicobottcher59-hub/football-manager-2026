# UI-3.3 — Competitions Centre (October 2026)

## Purpose and scope

Read-only competition viewing for the current Python DEV world, consistent with the approved dark interface. One broad main panel displays either a full league table or **an actual drawn knockout bracket**. A separate secondary panel **always** shows all games of the selected matchday or knockout round, not only the controlled club. Keep the existing Home/Squad/Tactics/Calendar layout and Windows launcher. Do not modify the simulation engines or perform day advancement.

## Delivered views

1. **English domestic leagues:** Premier (20 teams, 38 matchdays), Championship / League One / League Two (24 teams, 46 matchdays), full table including played, W/D/L, GF/GA/GD and points. Each round shows every currently registered home/away fixture; past results only when actually registered.
2. **FA Cup / Carabao Cup:** rounds and ties from the original `KnockoutRoundPlan` objects, shown in a pan/zoom bracket; `My path` focuses already drawn fixtures involving Northbridge. `All ties` displays every drawn tie. Round navigation keeps the entire real schedule of that round in the right pane. Undrawn rounds are labeled awaiting draw. The bracket draws connecting lines ONLY when a settled winner is explicitly present in a subsequent ACTUALLY drawn tie; otherwise no speculative links. Leg scores, aggregate and penalties remain distinct.
3. **UEFA Champions/Europa/Conference:** 36-team league-phase tables and all 18 fixtures per matchday. 8 matches per club in Champions/Europa, 6 in Conference, based on the existing season engine. Internal tabs switch between league and knockout even before knockout is drawn; undrawn opponent fields stay blank/TBD. No pre-draw bracket predictions.
4. **EFL Trophy:** group tables for the 16 registered groups, all 32 fixtures per group-stage matchday across those groups, plus a future/actual knockout tab with the same drawn-only rule.

The competition selector lists **the actual registrations** of `DevelopmentSession._world` on each new session. It does not hardcode a list of mocked official fixtures. Fictional clubs receive local provisional monogram crests; no licensed club badges are bundled. Kickoff times in the secondary panel are labeled UTC.

## Local bridge (Python source of truth)

- `src/football_manager/ui_shell/competitions.py` projects standings, all fixture dates/results, competition rounds and resolved ties using the existing world, not a second state store.
- `GET /api/competitions`: index with `id`, name, type, family and managed-participant indicator.
- `GET /api/competitions/{id}`: requested competition only, including `stages`, `table`, `rounds`, `knockout`, `groups`, known scores and penalties. Unknown IDs yield HTTP 404; endpoint is loopback-only and uses existing shared session lock.
- `frontend/portable/competitions.js` and `.css`: navigation, zoom, scrollable bracket, all-club right panel and stage/group controls. Escapes source-provided names when rendering HTML.
- The desktop entry remains `INICIAR_INTERFAZ_WINDOWS.bat` (Python standard-library HTTP server; Node/npm unnecessary).

## Intentionally not implemented

- Real Continue/day advancement, persistent squad or manager save, simulate-to-date, complete career history.
- Fabricated future cup pairings or unsanctioned bracket projections, inferred weather/official appointments.
- Physical/licensed club insignia, official generated fixtures from outside Python.
- Premature changes to WorldRunner, FastMatchSimulator, JSON storage, frontend dependencies or domain scheduling.

**Before implementation of Continue**, conduct the agreed Technical Review & Stabilization checkpoint: architecture, save consistency, performance benchmarks, calendar collision stress tests and Ruff/type-checking feasibility. No architecture rewrite without tests demonstrating its value.

## QA and release

Run from root: `python -m pytest -q tests/test_ui33_competitions.py` (set `PYTHONPATH=src` as needed), alongside earlier UI tests. Visual smoke checks include domestic table + round navigation, cups focused/full bracket and zoom, UEFA stage toggle, EFL Trophy group picker and all-club fixture count. User validates in Windows at the preferred browser zoom.

Apply **only the UI-3.3 incremental patch** over an unchanged accepted UI-3.2 repository branch, keeping file paths. No game-wide archive or engine rewrite.
