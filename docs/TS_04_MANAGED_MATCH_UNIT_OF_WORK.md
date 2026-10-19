# TS-04 — Managed Match Unit of Work (Architecture / Reliability)

**Incremental TS-04 slice**, built upon TS-03. It preserves all current UI text, graphics, navigation and match mechanics.

## Why

The application currently applies condition, fatigue, positional learning and morale before writing the managed result to the canonical world. If a later world registration, knockout draw or view refresh fails, TS-01 rolls back the world but the player's mutable state remains changed. Repeating the match then carries unearned fatigue and morale.

## Architecture improvement

- Introduces a public `WorldSeasonRunner.transaction()` context for application-orchestrated atomic world commands. It shares the existing TS-01 journal and is single-threaded.
- Moves mutable player checkpoint/restore into `services/managed_match_transaction.py`. Players, state objects and positional-familiarity objects preserve identity on failure. This is an application service, not presentation logic.
- Treats the managed match as one unit of work: player condition, positional learning, morale, world result, world-generated knockout plans, calendar projections and session seed/match flags either commit together or roll back together.
- Does not clone the entire world for every match: TS-01 journals only changed world entries; this patch copies only the two clubs' mutable player state and lightweight session projections.
- Retains the existing deterministic FastMatchSimulator and all public UI methods.

## Tests

`python -m pytest -q -ra tests/test_ts_04_managed_match_transactions.py tests/test_ts_03_world_integrity.py`

The four new fault-injection and reproducibility tests cover: failure after a completed world write, failure after a partial view refresh, failure during player positional learning, and normal deterministic match simulation.

Full regression: `python -m pytest -q -ra`.

## Limits / future TS-04.1

- This patch focuses on `DevelopmentSession.quick_simulate()`. Complete session-wide atomicity for `continue_to_next_match()`, manual editing, and legacy DEV-only matches requires further review.
- It does not introduce multithreaded access, concurrency locks, a savegame overhaul, or new UI features.
- The 3,000+ line development session still merits gradual service extraction; a wholesale split in one patch was deliberately avoided to preserve working game behavior.
