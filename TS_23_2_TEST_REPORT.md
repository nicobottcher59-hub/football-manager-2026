# TS-23.2 - U17/U21 formation board and avatar pass

## Scope

This patch is a presentation-only refinement for the Youth Academy screens introduced in TS-23 and TS-23.1. It keeps the approved U15 intake preview and scouting redesign, and improves only the U17/U21 views.

Implemented changes:

- Added a **visual formation board** above the detailed management table for **U17** and **U21 / Reserves**.
- The board uses a simple **4-3-3 preview** generated from the current youth squad and their positions.
- Added **illustrated youth avatars** so players no longer appear only as plain initial tiles.
- Added a compact **rest-of-squad strip** below the board, while preserving the existing detailed roster table and the right-hand match/results/table rail.

No changes were made to youth development rules, match simulation, promotions, releases, scouting logic, finances, or save migration.

## Save and compatibility

- Save graph version remains **11**.
- Existing TS-23.1 saves remain compatible.
- No migration or data transformation is required.

## Verified here

- JavaScript syntax check passed for `frontend/portable/youth_academy.js` using `node --check`.
- A lightweight asset-contract regression test was added and passed: `tests/test_ts_23_2_u17_u21_layout.py`.
- Manual source review confirms that the U17/U21 roster page now renders the formation board before the roster management table and preserves the existing management actions.

## Limitations

- The formation board is still a **preview**; it does not introduce playable youth matches or a tactical youth editor.
- Youth portraits remain generated/stylized UI avatars, not unique face-generation assets.
- The U15 and scouting screens were not materially changed in this patch.
