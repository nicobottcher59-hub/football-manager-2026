# TS-UI-02.6 — Test report

**Base:** TS-UI-02.5.

### Verified

- Node syntax check: `node -c frontend/public/squad/squad_ui02.js` — PASS.
- Directed Python structural/regression tests:
  `pytest -q tests/test_ts_ui_02_6_squad_layout.py tests/test_ts_ui_02_5_squad_polish.py tests/test_ts_ui_02_4_profile.py tests/test_ts_ui_02_3_squad_visual.py tests/test_ts_ui_02_2_squad_split.py` — **51 passed**.
- Isolated Chromium rendering on **1680×980 / 1366×860 / 980×800** — PASS; no page errors or horizontal page overflow.
- Browser checks — PASS: left directory rows, right hero composition, shirt/crest asset fallbacks, SVG map and comparison radar, captain visibility, number `22` fixture, no full inspector/root remount when changing internal tabs, and asynchronous identity name update from fictional world club label to catalogued display name.
- No Python simulation, save schema, finance, competitions or contract model changes.

### Not verified

- Native Windows application and user's local monitor/browser scaling.
- Full 20-season simulation/regression.
- Pixel-exact parity with an image-generation mockup; acceptance should be based on the real Windows rendering and additional UI inspection if needed.
