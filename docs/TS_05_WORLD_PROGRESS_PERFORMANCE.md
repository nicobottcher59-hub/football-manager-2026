# TS-05 — World progression performance

Incremental technical patch based on TS-04. No UI, sporting probabilities, scheduling policy, save-schema or Python dependency changes.

## Observed bottleneck

`WorldSeasonRunner.advance_until()` previously rebuilt and sorted all due fixtures after *each* simulated game. That repeated O(N) scanning and O(N log N) sorting even though most fixtures were unchanged.

## Change

- Use a temporary min-heap keyed by `(kickoff, fixture_id)`, matching the existing ordering exactly.
- Add newly scheduled or reprogrammed fixtures while a progression command is running. Stale entries are ignored using object identity after the ledger is updated.
- Free the heap in `finally`, even when simulation raises an exception. No heap is saved in the world JSON.
- Keep the world result resolver, random seeds, knockout generation and `protected_club_id` behavior unchanged.
- Leave conflict matching / season generation optimization to a separate profiled patch; this only affects day advancement.

## Measurement (one warm-up-independent run, Linux environment)

| Synthetic leagues | Fixtures | Before (s) | After (s) |
|---:|---:|---:|---:|
| 2 | 760 | 0.075 | 0.014 |
| 4 | 1,520 | 0.284 | 0.023 |
| 8 | 3,040 | 1.165 | 0.046 |

These are indicative measurements in one runtime, not guaranteed speedups on Windows. Run the included benchmark to profile your own machine. The time only measures world advancement, not world building or rendering.

## Tests (no Node.js required)

```
python -m pytest -q -ra tests/test_ts_05_world_progression_performance.py tests/test_ts_04_managed_match_transactions.py
python tools/benchmark_world_progression.py --leagues 4 8
```

The TS-05 tests compare the entire persisted world with the original slow scheduling algorithm, covering multiple leagues, new knockout rounds, user-protected fixtures, resume, deterministic results and error cleanup. Timing values are deliberately **not** asserted in CI.

## Boundaries

Runner access is single-threaded, as it was before TS-05. Future asynchronous world simulation requires explicit concurrency controls. This patch does not add multi-process workers.
