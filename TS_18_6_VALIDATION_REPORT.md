# TS-18.6 - Extended validation evidence

Base: user-provided football-manager-game.zip (TS-18.4) + TS-18.5 revised incremental patch + TS-18.6 original tests. Environment: Linux, Python 3.13.

## Verified in this validation run

- TS-18.5 + original TS-18.6 tests: **128 passed** (exit code 0, 2.94 seconds).
- TS-18.1/18.2/18.3/18.4 + 2D match flow: **77 passed** (exit code 0, 15.20 seconds).
- NEW supplementary 2D short-clock seeded flow tests: **24 passed** (exit code 0, 0.57 seconds).
- Sum of separate successful runs: 229 test executions. This is NOT a full-project regression count and does not prove universal coverage.

## Incomplete checks

- Full `python -m pytest -ra` stopped at approximately 21% due to the execution timeout; no successful full-suite exit code was recorded.
- A wider run that included full-season integration stopped during setup/run of expensive scenarios at ~63%; no successful exit code was recorded.
- Multi-season endurance and full length 2D match stress were not completed.

## Scope

- No product/gameplay files changed in this TS-18.6 extension.
- Original TS-18.6 seeded fast-sim test preserved.
- New 2D tests exercise 24 deterministic seeds with intentionally shortened match periods; these are smoke/regression tests, not a replacement for real-time full-match tests.
- Do not merge or mark full stabilization complete until the full suite and longitudinal runs have finished and any failures are triaged.

## Windows checks (from project root)

```
python -m pytest -ra tests/test_ts_18_6_football_regression_stress.py tests/test_ts_18_6_spatial_seeded_regression.py
python -m pytest -ra
python -m pytest -ra tests/test_phase6_7_full_season_integration.py tests/test_ts_17_1_multiseason_scheduling.py tests/test_ts_17_4_long_career_persistence.py
```

Record exit code, pass/fail summary, runtime, and any exception. A timeout is *inconclusive*, not a pass.
