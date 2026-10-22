# TS-UI-06.01 — Dressing Room visual implementation

## Scope

Redesigned **only** `frontend/portable/dressing_room.js` and `frontend/portable/dressing_room.css`, preserving the existing Dressing Room introductory header (photo/banner changes intentionally deferred) and the surrounding shell. No Python simulation, REST endpoints, save formats, staff, training, medical, Squad or finance files were modified.

- Uses the existing read-only `/api/dressing-room` projection; tier membership, influence, morale, integration, relationships, dates and events come from the real Python session.
- Four **actual trapezoidal** levels: Team leaders, Influential players, Established group, Developing influence. Adapts to the number of players in each tier.
- Selected-player detail panel keeps integration, actual appearances/minutes, the social morale effect, best observed connections, career link and existing Inbox conversation action.
- Two lower modules: clickable connection graph highlighting up to six actual strongest links, and the existing recorded events/empty state and Refresh action.
- Consumes `FMPortraits` with stable player IDs; no hard-coded Sunderland, fixed players, synthetic injury, friendship, morale or club-specific photo added.
- Mobile network stays within its own horizontally scrollable region; selecting a player and resizing centres the active node. Never generates document-wide horizontal overflow.

## Verification

- **Python targeted regression: 10 tests passed**: 6 new TS-UI-06.01 contracts + 4 selected TS-20 model invariants, executed together with `PYTHONPATH=src python3 -m pytest -q tests/test_ts_ui_06_01_dressing_room.py tests/test_ts_20_dressing_room.py -k 'test_ts_ui_06_01_dressing_room or new_state_is_neutral or api_has_no_hidden_personality_numbers_or_player_seed or reads_and_lineup_experiments_do_not_advance_hierarchy_or_penalize or first_week_without_matches'`.
- `node --check frontend/portable/dressing_room.js`: passed.
- Chromium using **actual JS/CSS and a real Python DevelopmentSession read projection**, with a mocked HTTP transport (not a live Windows browser/server): **1680, 1366, 980, 560, and 390 px**, no JS exceptions or whole-page horizontal overflow. All 22 players rendered in the correct four tiers, with tier counts 2 / 10 / 9 / 1 in this development session.
- Chromium interactions: mouse selection for multiple members changes the detail panel, selecting a graph node and a relationship entry works, `Talk to player` routes through `FMNavigation.navigate('Inbox',false,{player:id})`, and Refresh makes a GET for `/api/dressing-room`.
- Historic full TS-20 suite: attempted but **timed out** during longer simulations; therefore **not** claimed as fully passing. Full-app/server and user's own Windows save remain untested here.

## Install

Incremental over **TS-UI-05.01**. Stop Python, unzip with relative paths over the repository root, restart with `PYTHONPATH=src python3 -m football_manager.ui_shell` and refresh the web UI (Ctrl+F5). No save migration.
