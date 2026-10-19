# TS-01 - Atomic World Operations

## Scope

This patch stabilizes `WorldSeasonRunner` only. It does **not** change the match
simulator, fictional draws, scheduling priorities, gameplay, HTTP API or UX.
It builds on the TS-00 + TS-00.1 checkpoint.

### The defect

Previously, `register_cup` / `register_staged` updated the competition ledger,
club strengths and individual fixture assignments as they went. If one later
fixture could not be scheduled, earlier writes stayed committed. Similarly,
`record_result` marked a fixture as played *before* generating its successor
round; a failed draw/schedule left a completed result with incomplete cup state.

### What changed

- A lightweight, per-operation undo journal records the previous value of each
  touched world dictionary entry. On failure it undoes those entries in reverse
  order (including existing league fixtures rescheduled for a cup).
- Before asking a mutable domestic cup or staged competition to advance, the
  runner also checkpoints its plans, qualifiers and champion. On failure these
  fields are restored **on the original object**, without replacing references
  that other callers may hold.
- Nested calls (for example a finished league match registering promotion
  playoffs) share the parent's transaction; if the outer operation fails, the
  nested registration is also rolled back.
- Atomic guards cover league/cup/staged registration, EFL playoff configuration,
  league fixture rescheduling and individual result registration.
- The `WorldSeasonRunner` JSON schema remains **version 3**; transactions are
  transient and are not part of a save file.
- The previous strict expected failure (`xfail`) for staged registration is
  now a regular passing regression test.

### Why a journal instead of a full-world snapshot

A game may resolve thousands of background fixtures in a single season.
Deep-copying all fixtures, clubs and results before **every** match would scale
poorly with the number of leagues. The undo journal saves only the modified
entries and a few short knockout-plan lists.

### Tests

`tests/test_ts_01_atomic_world_operations.py` covers:

- failed cup registration after one fixture was inserted;
- failed staged registration after one earlier fixture was scheduled;
- an existing league fixture moved by a failed staged registration;
- failed advancement to a new domestic cup round, then deterministic retry;
- failed advancement from UEFA league phase into knockout, then retry;
- champion assignment followed by an injected failure;
- partial EFL playoff configuration;
- an inner successful cup registration undone by a failing outer operation.

The other existing world/cup/calendar tests remain relevant and must continue
passing. No Node.js installation is required to validate this Python patch.

## Important boundaries

- Atomicity is **per world command**. `advance_until()` commits each completed
  fixture separately; it does not roll back an entire multi-day progression.
- `DevelopmentSession.quick_simulate()` currently updates player fitness,
  development and morale before committing the managed result. Transactional
  protection for the **whole session** remains separate work in TS-04.
- The runner is used as a single-threaded mutable simulation object. This
  patch does not introduce a concurrency lock or multi-user transaction support.
- Calendar scheduling-policy problems (competition weekdays, prioritization,
  round chronology, collision resolution) remain TC-E2.2 / TS-02 work. This
  patch prevents **partial state** when scheduling fails; it does not make all
  scheduling decisions more realistic.
- Direct, unjournaled modifications to `world.fixtures` or competition objects
  by external callers remain outside this transaction guarantee.

## Acceptance

1. Injection of an exception anywhere in registration/progression leaves
   `world.to_dict()` equal to its immediately prior representation, and restores
   external references to mutable tournament state.
2. A retry after removing the injected failure succeeds deterministically.
3. Old and new Python tests pass on the tested environment, without expected
   rollback failures. GitHub Actions provides additional Windows validation.
4. No additional local dependency is necessary for the player/developer.
