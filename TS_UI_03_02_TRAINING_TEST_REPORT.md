# TS-UI-03.02 — Training automation, individual workload and shared assets

## Scope
Incremental patch **over TS-UI-03.01**. Includes the previously requested
training photograph/shared Squad portrait catalogue integration, plus new
manager-configurable automatic bands and player-specific exceptions.

## Gameplay (Python)
- `TrainingPolicy`: four integers defining **two independent ordered pairs**:
  - Sharpness: `performance_max` (50) < `performance_focus` (60)
  - Condition: `energy_max` (50) < `energy_focus` (60)
- Invalid overlapping pairs move the neighbouring limit automatically, with
  the most recently edited control taking precedence. Values remain 0–100.
  This is enforced in JS *and* the Python service.
- When **Automatic** is selected as the squad group or specific-player mode,
  physical condition takes priority over sharpness, then the game uses the
  existing group-dependent automatic fallback (an individual Auto exception
  uses a group-independent fallback). Existing 70/85 physical protection
  thresholds can still lower a training intensity for safety; injury never
  initiates training.
- Manual **individual player** intensity overrides are persisted by player ID,
  not lineup group. Modes are Auto, Light, Balanced and Intense. Group mode
  removes the override. The effective mode actually feeds the existing daily
  training/recovery and monthly development ledger.
- Changing an individual player's *development focus* calls the same existing
  `/api/development/focus` action as Squad. It does not increase abilities
  immediately and takes effect at the next monthly review.
- `apply_auto_all` switches all three groups to Auto only on explicit click;
  existing group settings are not implicitly overwritten on upgrade.
- No change to the underlying match engine, injury resolution, development
  formula, roster IDs, balance multipliers, or stored physical parameters.

## Career save migration
- `GRAPH_VERSION` upgraded from 22 to **23** due to the five new TrainingPolicy
  fields. Explicit migration supplies defaults only to older TrainingPolicy
  objects when loading old careers.
- Old group settings (`starters`,`bench`,`rest`) and physical safety (`low_condition`,
  `medium_condition`, `protection`) are preserved as stored.
- New-version round trips persist individualized workloads and automatic bands.
- Original graph integrity checks, whitelist, bounded ranges, and retention
  limits are unchanged. Source test assertions that specifically expected
  version 22 were updated to expect 23; older, unrelated historical tests
  that still hard-code older graph versions are outside this directed run.

## Verification actually performed
1. Directed pytest regression suite:
   `PYTHONPATH=src python3 -m pytest -q tests/test_ts_ui_training_01.py tests/test_ts_ui_training_02.py tests/test_ts_ui_training_03_adaptive.py tests/test_ts_ui_02_14_final_squad_polish.py`
   **24 passed** (incl. new thresholds, real daily workload change,
   invalid-operation atomicity, single-player override, per-player focus,
   old v22 -> v23 migration, current v23 roundtrip).
2. Original TS-26 behaviour:
   `PYTHONPATH=src python3 -m pytest -q tests/test_ts_26_club_support.py::test_training_groups_and_condition_protection`
   **1 passed**.
3. Chromium 1680, 1366, 980, 560, 390 px: no JS errors or horizontal
   overflows; banner photo renders.
4. Chromium browser interactions: edited an automatic slider past another,
   verified linked adjustment in DOM and both numbers, verified outgoing
   `/api/training` payload, selected an explicit player intensity, verified
   its POST and appearance in the player row + exceptions list, changed focus
   through `/api/development/focus`, returned player to their group, selected
   a different player, and triggered apply-to-all. All passed.
5. Node JS syntax and Python compile checks passed.
6. Checked exact byte identity of the three approved Squad 02.14 source files
   against prior snapshot. All unchanged.
7. **Not claimed:** full historical pytest suite, real Windows game save,
   or extended match simulation balance beyond the targeted one-day test.

## Known boundaries / expectations
- Thresholds control **automatic workload selection**, not guaranteed
  statistical gains or invented training sessions. Existing monthly player
  development resolves recorded training via the original ledger.
- If all three group modes remain fixed and no individual mode is Auto,
  automatic thresholds remain inactive; use the explicit *Apply to all groups*
  button or select Auto for any group/individual to activate them.
- Rule pairs are separate quantities: condition percentages and match
  sharpness percentages are not directly compared to each other.
- This patch is additive to TS-UI-03.01 and includes the missing banner-photo
  asset from the previous Training discussion; it does not require a separate
  03.02 photo-only installation.
