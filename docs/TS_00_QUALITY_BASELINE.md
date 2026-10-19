# TS-00 - Quality baseline and regression cleanup

## Intent and guarantees

This is an engineering-only stabilization patch. It does not alter the football
model, the runtime Python application, the web UI, assets, calendar data, or
user-facing workflows.

- Replace obsolete date assumptions in two tests after TC-E2.1. The matchday
  HTTP test asserts a **one-day progression from the actual match date**.
- The development-session progression test asserts that **the next fixture
  belongs to the next scheduled competition**, whether that is the Premier
  League, Carabao Cup or another tournament. Its match snapshot must use
  the active fixture's participants, not the cached league fixture.
- Add a regression test comparing two fresh sessions across **two real managed
  matches and their intervening background results**, without fixing scores.
- Add GitHub Actions checks on Python 3.11 (Linux), Python 3.13 (Windows), and
  Node 22 (plain JavaScript syntax and board behavior).

## Run locally (Windows, from repository root)

```powershell
python -m compileall -q src tests tools
python -m pytest -q -ra
node tests/ui/test_board.cjs
```

Optional, to syntax-check JavaScript files manually, run `node --check` on
specific files (for example `frontend/portable/match.js`). Full automated
plain-JavaScript syntax checking runs in GitHub Actions on Linux.

This baseline intentionally does **not** claim to validate a Vite/React
production build. The frontend has no committed `package-lock.json` in the
provided snapshot; a reproducible frontend dependency/build gate should be
introduced in a separate, validated patch. The existing code and UX are not
altered here.

## Still open after TS-00

- One test marked `xfail` documents non-atomic world competition registration.
  It is **not fixed** here and belongs to TS-01 (atomic operations and rollback).
- TC-E2.2 calendar reprogramming correctness and future-season stress testing
  are separate patches.
- This patch provides no guarantee that the current branch contains all changes
  from your latest local commits; compare target files before overwriting if
  work has continued since the exported ZIP.

## Acceptance

The full pytest suite passes without unexpected failures. Its expected failure
is reported separately (do not convert it into a skip or delete it). The Node
board smoke test and Python syntax checks pass. The GitHub Actions results on
Windows and Python 3.11 must be confirmed in GitHub after pushing the branch;
they cannot be certified by tests run on Linux alone.
