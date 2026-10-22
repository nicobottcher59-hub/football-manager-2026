# TS-UI-06.02 — Dressing Room photographic club header

## Installation

Apply this incremental ZIP to the repository root **after TS-UI-06.01**. Keep relative paths and replace existing files. Restart the Python UI and refresh with Ctrl+F5. No save conversion is required.

## Scope

- Replace the previously plain TS-20 header in Dressing Room with the approved image-led layout.
- Use `FMClubIdentity.resolve(model.club_id,model.club)` for name and crest; `FMClubIdentity.applyTheme` for palette.
- Use one standalone club-neutral locker-room photograph cropped from the approved visual reference. It does not contain badge, team name, UI text, club ID or embedded stats. The sports clothing in the photo is generic.
- Repeat three **real** model-derived KPI summaries inside the hero, as present in the approved screenshot; retain the existing row of 3 KPI cards beneath the hero. No dummy morale or invented scores.
- Connect the navigation highlight to the shared club colours when the Dressing Room route is selected.
- Keep the four-level hierarchy pyramid, player selection, player details, network links, conversations, read-only Python dynamics and save schema unchanged.

## Verification (2026-10-22)

- `node --check frontend/portable/dressing_room.js`: passed
- `node --check frontend/portable/portable.js`: passed
- Directed UI tests (`test_ts_ui_06_01_dressing_room.py` and `test_ts_ui_06_02_dressing_header.py`): **10 passed**
- Two TS-20 backend compatibility tests (`test_new_state_is_neutral_and_does_not_invent_past_history`, `test_api_has_no_hidden_personality_numbers_or_player_seed`): **2 passed**
- Chromium rendered the actual modified Dressing Room JS/CSS with Python DevelopmentSession data at 1680, 1366, 980, 560 and 390 pixels: **0 JavaScript page exceptions; 0 horizontal document overflows; 22 player tiles, 3 hero KPIs and 3 existing KPIs**
- Chromium selected another player and the right inspector changed; opening the conversation sent Inbox route; replacing the mock identity provider with another club changed name and palette without a UI rewrite.
- Direct HTTP against a real local Python server and live Windows career save: **not run** (local server restricted).
- Wider historical TS-20 suite: **not complete**; it exceeded execution time during extended simulation tests. Do not interpret this as a pass.

## Changed files

1. `frontend/portable/dressing_room.js`
2. `frontend/portable/dressing_room.css`
3. `frontend/portable/portable.js`
4. `frontend/portable/assets/dressing-room/locker-room-team-talk.webp`
5. `tests/test_ts_ui_06_01_dressing_room.py` (updated previous header expectation)
6. `tests/test_ts_ui_06_02_dressing_header.py`
7. `TS_UI_06_02_TEST_REPORT.md`
