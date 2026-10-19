# TS-03 — World State Integrity

Technical stabilization following TS-02. No gameplay, UI, database or save-schema changes.

## Background

`WorldSeasonRunner.record_result()` already enforced knockout deciders and phase-specific penalties, but `from_dict()` reconstructed results without checking those sporting rules. A valid JSON archive could therefore claim a league penalty shootout, leave a knockout draw undecided, or name a champion inconsistent with its final. A caller could also save a directly corrupted in-memory fixture ledger.

## Implemented

- Extracted the existing result-validation rules into `_validate_result_semantics` and reused them during live matches and save validation.
- Added `validate_integrity()` for explicit diagnostics and use at load/save boundaries. Checks fixture ownership, played/result consistency, club-strength availability, score validity, knockout round progression and final winner claims.
- `save_json()` validates before creating a destination file. Invalid archives are rejected on load, without silent repair.
- Historical save schemas 1/2/3 retain their current decoding/migration paths; version remains 3.
- Validation runs only at persistence/diagnostic boundaries, **not for every match**, to preserve simulation throughput.

## Tests

`python -m pytest -q -ra tests/test_ts_03_world_integrity.py tests/test_ts_02_calendar_scheduling.py tests/test_ts_01_atomic_world_operations.py`

Full regression: `python -m pytest -q -ra`.

## Limits

- This detects internally contradictory data; it is not a complete football-rule audit for all past and future editions.
- External mutation of live Python objects is not globally blocked; invalid data is detected at audit/save time.
- Player, finances, staff and building state are not yet part of the world-result save format. Full career persistence is separate future work.
