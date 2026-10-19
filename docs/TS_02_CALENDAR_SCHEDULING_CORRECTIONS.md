# TS-02 — Calendar Scheduling Corrections

Technical stabilization only. Does not change UI, match engine, saves, or sporting draw rules. Requires TS-01.

## Defects fixed

1. A cup fixture could be placed two days *before* its published anchor although the anchor was free. Ranking now prefers fewer forced league postponements and, for equal conflicts, the date closest to the preferred round window. Ties are deterministic.
2. A new knockout round could be programmed before an unusually delayed predecessor had finished. New domestic/staged rounds now require at least 48 hours after the latest actual kickoff in the preceding round/phase. Unresolvable bounds cause a clear failure, automatically rolled back by TS-01.
3. A dynamically generated UEFA fixture could drift to a Monday/Saturday to solve a collision. UEFA and EFL Trophy assignments now enforce competition-specific weekday windows (including their known final and first-matchday exceptions). If a window is infeasible, registration is rejected rather than inventing an implausible date.
4. Published `ScheduleSource.OFFICIAL` league matches and already played matches may not be displaced by generated cup/staged fixtures. The scheduler tries an alternate eligible date or fails safely.
5. Domestic cup fallback dates are restricted to the modeled season boundary; no match is silently placed in July.

## Intentionally not covered

- TV broadcaster selections, pitch/stadium bookings, weather postponements and travel are not simulated yet.
- A full global constraint solver, historical fixture imports, and new multi-country calendars are out of scope.
- UEFA policies apply to the current competition templates, not every historical or future regulation revision; published edition-specific rules must be updated when appropriate.
- League fallback rescheduling still uses a bounded deterministic forward search. TS-05 will profile and optimize that search.

## Validation

`python -m pytest -q -ra tests/test_ts_02_calendar_scheduling.py tests/test_ts_01_atomic_world_operations.py`

Full regression: `python -m pytest -q -ra` (may take several minutes). No local Node.js required.
