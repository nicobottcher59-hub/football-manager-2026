# TS-UI-08.01 — Professional Scouting Hub

Base: TS-UI-07.02 (Youth Academy); install this ZIP in repository root, preserving paths.

## Scope
- New Scouting Hub: free discovery search, automatic territory recommendations, hired scout assignments, shortlist overview. No duplicated Inbox panel.
- Player Search and Shortlist: shared left roster/right inspector interaction inspired by Squad; shared portrait renderer; public information with unknown ability, potential, attributes and market price until report.
- Professional scouts: destination by nationality or league, same staff payroll/negotiation as Staff, observation slots and duration driven by existing Python world calendar. Completed reports delivered to existing Inbox.
- Persistent shortlist with top/future/monitor categories, saved by player IDs; independent of scouting work slots.
- Club title/crest/accent comes exclusively from FMClubIdentity. Sidebar selection and right inspector use the same theme. Generic background image reused from Staff (no baked club crest).
- Old transfer negotiation module remains authoritative; only players with a scouting report expose the negotiation entry point from the new Scouting inspector.
- Height and weight shown as unavailable if not present in the game data model; no fabricated data.

## Tests performed and results
- `PYTHONPATH=src pytest -q tests/test_ts_ui_08_scouting_hub.py`: **4 passed**. Includes no hidden-player-data leakage, independent shortlist, destination validation, calendar progression to report, Inbox notification, and graph roundtrip.
- `node --check frontend/portable/scouting_hub.js` and `node --check frontend/portable/portable.js`: **pass**.
- Python `compileall` for modified service, domain, codec and server: **pass**.
- Actual Python HTTP transport on ephemeral 127.0.0.1 port (not browser): **GET /api/scouting/hub, POST shortlist_add, destination and assign all HTTP 200; subsequent GET confirmed changes**.
- Actual SQLite SaveRepository: **save and reload with shortlist target, scout destination, in-progress individual assignment: pass**.
- Graph v24 compatibility: **pass** (old records without the new fields reconstruct empty defaults under graph codec v25).
- Chromium with real `scouting_hub.js`, shared `club_identity.js`, shared `portraits.js`, and real CSS, fed actual Python read-model data through a stubbed fetch boundary: **Hub, Search, Shortlist, Network at 1680, 1366, 980, 560 and 390 px; no horizontal overflow or JS errors**. Interactions for select, shortlist, scout assignment, destination edit, profile tabs: **pass**.
- Alternate identity: synthetic catalog entry with a long display name and a distinct color: **pass at 390 px**. Fallback crest remains neutral without an entry.

## Limitations
- Browser-to-localhost was blocked by this execution environment (`ERR_BLOCKED_BY_ADMINISTRATOR`). Browser rendering/interactions were verified with a fetch stub; the real Python HTTP API was checked independently. No end-to-end Chromium-to-Python success claim is made.
- Historical full test suite was not completed; some long-running saved-game test groups exceed time bounds. Tests pinning the old graph v24 expectation have been updated for v25.
- DevelopmentSession's source model does not provide height/weight for all players. The UI shows an em dash, not invented figures.
- Only the existing club-identity catalog can provide real club crests/colors. Unregistered clubs fall back to the shared neutral identity, as in other sections.
- Recommender is a current-time discovery read model restricted to each scout's assigned territory; it does not simulate separate background travel timers. Observation reports *do* progress only with calendar days.
- A full run inside the user's Codespaces/Windows game is still needed.
