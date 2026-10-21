# TS-UI-02.14 — Squad final polish

## Scope and baseline

Apply over **TS-UI-02.13**. This is code, not a mockup. It changes only:
- **01B Season statistics:** six equal summary metrics (Apps, Starts, Minutes, Goals, Assists, Avg. rating); three equal, colored Shooting, Passing, and Defence & discipline panels; full-width data-coverage footer. All displayed values are read from the existing Python season-statistics contract. Unsupported/missing values remain `—`.
- **01C Status & development:** five colorful, visible skill-area bars (Attacking, Defending, Physical, Mental, Goalkeeping). Bar lengths are arithmetic means of *recorded current player attributes*. Attacking/Defending are subsets of Technical. The selected supported training focus is highlighted. **These are not actual training progress measurements or a prediction of improvement.** The existing Python development focus action remains unchanged.
- **01D Contract & actions:** more whitespace, larger status seal and cards, taller action tiles, and two custom dark dropdowns replacing OS-native menus. Both retain the original `rt-player-number` and `rt-transfer-status` `<select>` elements as hidden dispatch adapters; selecting an item forwards the original change event and Python command.

No changes to 01A Profile / Attributes, the player directory, the hero, the club catalogue, gameplay, Python, simulation, or persistence.

## Changed files
- `frontend/public/squad/squad_ui02.js`
- `frontend/public/squad/presentation.js`
- `frontend/public/squad/squad_ui029.css`
- `tests/test_ts_ui_02_14_final_squad_polish.py`
- `tests/test_ts_ui_02_12_status_contract.py` (update an obsolete checksum-only assertion for the newly approved 01B change)
- `tests/test_ts_ui_02_13_visual_depth.py` (same compatibility update)
- `TS_UI_02_14_TEST_REPORT.md`

No new stylesheet added. Files are packaged preserving their paths relative to the repository root.

## Validation completed

- JavaScript syntax: `node --check frontend/public/squad/squad_ui02.js` and `node --check frontend/public/squad/presentation.js`: **pass**.
- Squad UI tests 02.2 through 02.14: **109/109 passing**. The two older season-freeze checks now permit TS-UI-02.14 while still checking the original hash for earlier versions.
- Chromium snapshots at 1680, 1366, 980, 560 pixels: **12 content views checked**, no horizontal content overflow in the three revised tabs.
- Chromium dark picker: verified CSS background `rgb(9,34,54)` and open state.
- Chrome DOM interaction: selecting `Transfer listed` produced the existing `{'action': 'transfer_status', 'player_id': 'northbridge-1', 'status': 'transfer_listed'}` command through the existing `onChange` dispatcher.
- Chrome DOM interaction: selecting `physical` via development focus response highlighted only the Physical area. Actual Python mutation and save were **not** performed in this test.
- Snapshot data: real `DevelopmentSession` and Python squad/profile read models (Northbridge FC), with production Squad and presentation JavaScript. Chromium sandbox policy blocked direct loopback navigation, so the HTML/CSS was provided to `set_content` instead of testing the full HTTP UI. **This does not prove visual fidelity in the user's Windows environment.**
- A broader suite including server tests was attempted, but timed out and is **not** claimed as passing.
- Windows test with user's actual career: **pending**.

## UI limits kept deliberate
- Percentages for imaginary training progress were not introduced. Only current recorded attributes are shown, labeled **Current abilities · Focus highlighted · not growth**.
- Potential remains hidden. No fabricated shots/maps/trends are created for empty seasons.
- Some tab contents exceed the visible height; they use the existing internal vertical scroll, not a new full-page layout.
- Visual category colors are semantically distinct. Club branding and assets continue to flow through the club identity catalogue.

## Installation

1. Close the Football Manager game and stop its Python server.
2. Extract TS-UI-02.14 over the repository that already includes TS-UI-02.13, preserving folder structure and replacing files.
3. Relaunch the Python UI and press `Ctrl + F5` if styles are cached.
4. Verify 01B/01C/01D with your career data before committing.
