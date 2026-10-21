# TS-UI-02.11 — Squad 01A directory/header refinement

## Scope
Refine the improved Squad directory screen by:
- tidying the lower attribute statistics area,
- reducing crest/shirt overlap and preserving more shirt detail,
- adding compact header metadata for height and weight when available (fallback to `—` if unrecorded),
- replacing textual foot metadata with left/right boot indicators, highlighting the preferred foot.

## Files changed
- `frontend/public/squad/squad_ui02.js`
- `frontend/public/squad/squad_ui029.css`
- `tests/test_ts_ui_02_11_profile_refinement.py`

## Behaviour summary
- Header metadata now shows age + height + weight + a left/right preferred-foot control.
- Preferred foot is represented visually with two boot pills; the active foot is highlighted.
- Shirt/crest art remains driven only by existing club identity assets; overlap is reduced by softer crest staging and less horizontal shirt stretching.
- Lower attribute groups keep the same real Python data but use cleaner card framing and row spacing.
- No new stylesheet or extra view layer was introduced.

## Validation executed
```text
node --check frontend/public/squad/squad_ui02.js
python -m pytest -q \
  tests/test_ts_ui_02_10_directory.py \
  tests/test_ts_ui_02_11_profile_refinement.py \
  tests/test_ts_ui_02_9_squad_fidelity.py \
  tests/test_ts_ui_02_8_squad_rebuild.py \
  tests/test_ts_ui_02_7_squad_polish.py \
  tests/test_ts_ui_02_6_squad_layout.py \
  tests/test_ts_ui_02_5_squad_polish.py \
  tests/test_ts_ui_02_4_profile.py \
  tests/test_ts_ui_02_3_squad_visual.py \
  tests/test_ts_ui_02_2_squad_split.py
```

## Result
- JS syntax check: **PASS**
- Pytest subset: **PASS**
- Total tests executed in the UI-02 subset above: **86 passed**

## Notes
- The current read model does not provide anthropometric values for all players. The UI therefore renders height/weight slots safely, showing `—` when those values are not recorded by Python.
- No football logic, attributes, or role calculations were changed.
