# TS-08 - Score & Persistence Contracts

## Goal

Prevent silent score corruption and reject invalid results-only career saves before
writing anything to disk. This patch is built on TS-07.1 and does not add new
screens, game mechanics, database dependencies, or a complete manager save.

## Changes

- `WorldMatchResult`, `LeagueResult` and `KnockoutMatchResult` now require real
  nonnegative Python integer score values (`bool`, floats and numeric strings
  are rejected). `from_dict()` no longer truncates/rewrites scores via `int()`.
- `FastMatchResult` validates all final, aggregate, regulation, extra-time and
  shootout score fields as integers, and checks that `winner_club_id` agrees
  with the aggregate score or the penalty shootout winner. This keeps the
  same aggregate-based winner semantics for two-legged ties.
- `WorldCareer.validate_integrity()` validates every included world and the
  season timeline before `save_json()` creates or replaces any file. World
  archives and results-only career archives now share the world integrity
  boundary, including when an existing file would be overwritten.
- The `WorldCareer` archive schema stays version 1; the `WorldSeasonRunner`
  schema stays version 3. Existing correctly encoded saves remain readable.

## Deliberate limits

- `WorldCareer` still archives *world results and transitions only*; complete
  club/player/tactical career persistence is a separate future milestone.
- No SQLite or other database has been introduced by this patch.
- Existing simulation mathematics and UX remain unchanged. Invalid constructed
  outcomes now fail fast rather than being written or displayed.

## Validation on Windows

Run from the repository root with Python and pytest, no local Node.js required:

```powershell
python -m pytest -q -ra tests/test_ts_08_score_persistence_contracts.py tests/test_ts_07_1_match_lineup_integrity.py tests/test_ts_03_world_integrity.py
python -m pytest -q -ra
```

Optional manual check: run a match via the existing UI; confirm the resulting
score and winner are correct. For a world-results archive already used in a
local workflow, save and reload it and verify that scores are identical.

No special data migration or frontend build is required.
