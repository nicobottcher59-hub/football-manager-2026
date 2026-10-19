# TS-19.1.1 - Formation UI Refinement - Test Report

Date: 2026-10-15
Environment: Python 3.13, Linux; Node.js 22.16.0
Base: TS-19.1 Formation Expansion integrated over TS-18.5 / TS-18.6.

## Results

- Full regression: **1105 passed, 0 failed**, completed in **354.80 seconds**.
- Targeted Python tests: **26 passed** (TS-19.1.1, TS-19.1 and squad API tests).
- Geometry: **1120 passing layout scenarios** (28 formations x 2 phases x
  4 pitch sizes x 5 tactical instruction profiles). All checks assert card
  boundaries and no card collisions with fixed dimensions.
- Browser-independent modal lifecycle: 28 previews are rendered; canceling and
  browsing do not dispatch a Python command; confirming dispatches one
  established formation command.
- Existing Node board check: passed.
- Live HTTP asset check: `GET /squad/formation_layout.js` returned 200; squad
  API returned 28 preview entries with 308 tactical position markers.

## Scope and safety

- No football simulation, role, tactical instruction, OVR/ACT or persistence
  formula was changed. The sole Python edit adds read-only preview metadata.
- The existing Python command and role-reset behavior remain intact.
- New JavaScript only positions rendered cards within the actual pitch
  dimensions and supplies a confirmation modal.

## Known validation limitation

Chromium execution in this environment was blocked by the administrator for
local HTTP, file and data URLs, so an interactive visual screenshot review
could not be completed. Browser layout is verified by deterministic geometry
and mocked DOM/event tests, not by a real browser acceptance session.

The user should visually confirm all 28 shapes, mobile/desktop sizes and the
modal in Windows before committing and merging. Manual acceptance steps are
in `docs/TS_19_1_1_FORMATION_UI_REFINEMENT.md`.
