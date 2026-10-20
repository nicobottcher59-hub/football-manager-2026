# TS-UI-02.5 — Test report

Base: TS-UI-02.4 (only Squad presentation files and the existing Sunderland shirt asset changed).

- JS syntax: `node --check frontend/public/squad/squad_ui02.js` — PASS.
- Directed + previous structural regressions: **40 passed** (`test_ts_ui_02_5_squad_polish.py`, `test_ts_ui_02_4_profile.py`, `test_ts_ui_02_3_squad_visual.py`, `test_ts_ui_02_2_squad_split.py`).
- Isolated Chromium UI: **1680x980, 1366x860, 980x800** — PASS, no JavaScript errors or horizontal overflow.
- Function checks in Chromium: tab transitions preserve inspector, position mapping, role comparison radar, roster search/sort preserving the hero, captain present only for effective ID, unassigned number fallback, kit within hero and separated from ratings — PASS.
- Existing contracts, simulation, SQLite, save format: unchanged. No full-integral season stress test was run.
- Native Windows validation is **pending**; especially verify club assets, compact roster, real captain assignment and long names on the actual app.
