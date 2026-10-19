# TS-23.2.1 - Compact U17/U21 pitch cards hotfix

## Diagnosis

TS-23.2 used `flex: 1 1 190px` for every on-pitch player. That stretched cards to the width of each formation row, including one full-width goalkeeper. It also inserted an unnecessary duplicate reserve list above the detailed roster table and substituted basic generic avatars.

## Fix

The U17/U21 formation has four explicit rows (3-3-4-1) with fixed-size cards representing a 4-3-3. Each card shows an illustrated ID-stable portrait, current GRL, natural position, name and age. The goalkeeper is centered rather than stretched. The board is placed in the left content column and the existing detailed roster table follows directly below it; the match/results/league rail remains on the right. Formation is still a read-only preview and does not change simulated youth tactics.

TS-23.1 U15 preview and scouting remain unaffected. Promotion, release, training and save format are unchanged; the complete save graph remains version 11.

## Validation

- `11 passed`: four TS-23.2 updated layout tests and seven TS-23.1 targeted checks.
- `3 passed`: existing selected TS-23 API, read-only and full SQLite save regressions.
- JS parser: `node --check frontend/portable/youth_academy.js` passed in the build environment; no Node is required on the user's Windows PC.
- Chromium local DOM render with actual `youth_read_model` data (without HTTP navigation): verified 11 cards in U17 and U21; cards have fixed widths of 115-126px, no overlap, table below pitch, zero uncaught page JavaScript errors. Tested viewport widths: 1785, 1380, 1050px.
- Full native Windows testing and full historical suite not run. Browser HTTP end-to-end navigation was blocked by a container administrator policy; the DOM render used a stubbed fetch response from actual Python read models instead.

## Installation

Incremental patch for TS-23.2 only. Apply to project root with file overwrite and run `python tools/verify_ts2321_package.py`, then `python -m pytest -ra tests/test_ts_23_2_u17_u21_layout.py`. Restart server and use Ctrl+F5.
