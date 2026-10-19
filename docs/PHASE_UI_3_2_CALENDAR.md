# UI-3.2 — Managed Calendar & Pitch Position Sorting

## Scope and approach

Continuation of UI-3.1, not a season-engine rewrite. Implemented as a **read-only Calendar panel** in the portable Python-backed UI, styled to the approved dark calendar mockup; additionally corrected Squad sorting by football position rather than alphabetically.

The Calendar uses the existing `DevelopmentSession` and canonical `SeasonCalendar` / `WorldSeasonRunner` data. `GET /api/calendar` returns the managed club's currently known, dated fixtures, generated opponent names, competition and round, current local/away status, UTC kickoff, actual results (if registered), shootouts and available two-leg aggregate context. No fixtures or scores are fabricated to fill an attractive visual grid. No fixed-date "TBD if qualified" placeholders are recreated: fixtures are added only once a draw has produced genuine participants.

## Behaviors

- Monthly seven-column Monday–Sunday calendar, past/future navigation, **Today** shortcut, current day highlight and an empty state for months without known fixtures.
- Filters **only** show competitions with fixtures in the current Python-managed schedule; all/each competition. In the initial DEV world, Northbridge has Premier League, Carabao Cup and UEFA Champions League fixtures; FA Cup later ties are not displayed until drawn. EFL Trophy is not incorrectly shown as Northbridge's competition.
- Individual match cards carry provisional **two-club crests** (derived from club names, not licensed identities), H/A, opponent, competition-specific tint, and kickoff or recorded score. A result border is green (win), grey (draw), red (loss) from the managed club's viewpoint. Penalties determine the win/loss status when a shootout occurs, **without changing the individual 1–1/0–0 score**.
- Click a fixture for a right-hand details panel with real home and away club names, round, date, UTC kickoff, result and penalty shootout as independent values. A two-legged cup tie, if present and partly/fully played, also shows **separate aggregate and qualification**, resolved through the existing knockout domain function, not UI-only logic.
- Upcoming fixtures list comes from the same Python read model; selecting one navigates to that month and game. **Match Preview** on Home now navigates to this Calendar.
- Squad POSITION / MAIN POS sorts by on-pitch order (GK, fullbacks, center backs, other defenders, holding mids, center mids, attacking mids, wingers, strikers) with reverse on second click; equal-position groups are ordered by descending OVR.

## Limitations

- Initial UI Python session begins **15 Aug 2026** with **no managed match yet completed**, so **past wins and losses are not made up**. They appear when actual `WorldSeasonRunner` results exist; selected tests inject registered sporting results in isolated test sessions.
- Match time is displayed in **UTC**, as stored by `SeasonCalendar`; stadium/referee/weather/opponent dossiers are **not** available from this simple session. They are not invented.
- `Continue` remains disabled, and there is still no save/reload of roster and tactic changes in the browser runtime. The sandbox Tkinter's own runner is separate and unchanged.
- This UI remains a **portable HTML/CSS/JS application with a stdlib Python loopback server**, runnable on Windows via `INICIAR_INTERFAZ_WINDOWS.bat` without Node.js or npm. The React/Vite source is not yet the production desktop host.
- This patch does **not** introduce SQLite, contracts, social dynamics, a player-season ledger or a new match simulator.

## Tests

`PYTHONPATH=src python -m pytest -q tests/test_ui32_calendar.py` covers canonical fixture provenance, real scores, shootout V/E/D outcomes, separated two-legged aggregate, HTTP API assets and position sorting source coverage. Existing `tests/test_ui31_visual_live_home.py`, `tests/test_ui3_roster.py`, `tests/test_ui_shell_squad.py` and the Phase 6.5 scheduling suite remain the relevant regressions.
