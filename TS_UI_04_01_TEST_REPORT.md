# TS-UI-04.01 — Medical Centre & Training Staff

## Scope

Base: `TS-UI-03.03` (unified automatic training + Squad click fix).

- Medical Centre redesign based on the approved composition and user-provided physiotherapy-room photograph.
- Display real live counts for injured players, currently available squad members, medical and fitness staff, staff capacity, recorded return windows, treatment decisions and condition distribution.
- Retain actual `conservative` / `aggressive` treatment commands, player-history navigation, and Staff navigation.
- Add a compact Training header chip with **active** coaches and fitness staff, read from the same club staff records as Staff and Medical Centre.
- Sunderland-specific medical banner only when the Sunderland club identity is selected; neutral crest-free facility crop for other clubs with shared club-theme colors.
- No risk prediction, future injury simulation, invented staffing levels or fictitious future treatments.

## Files in incremental patch

- `frontend/portable/club_support.js`
- `frontend/portable/club_support.css`
- `frontend/portable/assets/medical/sunderland-physio-suite.webp`
- `frontend/portable/assets/medical/medical-suite-generic.webp`
- `src/football_manager/services/club_support.py`
- `tests/test_ts_ui_04_01_medical_training_staff.py`
- `TS_UI_04_01_TEST_REPORT.md`

## Checks performed

1. `node --check frontend/portable/club_support.js` — PASS.
2. `python3 -m py_compile src/football_manager/services/club_support.py` — PASS.
3. `PYTHONPATH=src pytest -q tests/test_ts_ui_04_01_medical_training_staff.py tests/test_ts_ui_training_01.py::test_training_model_exposes_shared_identity_and_real_current_values tests/test_ts_ui_training_01.py::test_training_read_model_is_pure` — **6 PASS**.
4. Headless Chromium, actual `club_support.js` + production CSS + live Python read-model with stubbed HTTP transport: Medical Centre at 1680 / 1366 / 980 / 560 / 390 px; additional injured-player scenario; Training at 1680 / 1366 px; a generic-club scenario at 1680 px. **9 renders PASS**, no JS errors, missing images or horizontal page/panel overflow.
5. Chromium interaction verified Medical Centre → Staff and both actual treatment command payloads to `/api/medical`.
6. User-supplied photo is actually used for Sunderland; generic club uses neutral crop (no Sunderland crest).
7. Confirmed that Squad, Training commands and save format are unchanged; only read models gain additive fields.

## Limitations

- The whole repository-wide suite was **not** completed: an older simulation-heavy test stalled during an exploratory full departmental test run. Do not infer global-suite approval.
- Real user's Windows career has not been loaded here. Install and test with a backup of your save as good practice.
- Counts reflect active contracts. 'Medical staff' means the existing Python `medic` role; 'Fitness coaches' means `fitness` role. There is no separate 'physio' role in the current engine.
- 'Recorded returns' groups already recorded return dates, not a forecast of future injuries or new injuries.
