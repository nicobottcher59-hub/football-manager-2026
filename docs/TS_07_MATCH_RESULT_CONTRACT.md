# TS-07 — Match Simulation Contracts (foundation)

Incremental technical patch based on TS-06. The user-facing game mechanics, simulation algorithms, random generation, scores, events, UX, frontend and save format are unchanged.

## Problem

The managed FastMatchSimulator returns a detailed `FastMatchResult`, while `WorldSeasonRunner` persists a lightweight `WorldMatchResult`. There was no boundary verifying that the fast result being recorded actually belonged to the currently scheduled home and away clubs. Future 2D and background resolvers need a safe shared contract without duplicating world logic.

## Change

- Introduce the engine-independent `FixtureMatchOutcome` projection and `MatchScoreSource` typing protocol, which accept score-shaped output from any engine without depending on 2D or frontend objects.
- Validate fixture participants and canonical score semantics before handing a managed result to the world runner. The runner retains the final authority on competition/knockout rules.
- Route the existing `DevelopmentSession._record_active_match_result` managed-world path through `record_managed_match`. Preserve its transaction/rollback from TS-04.
- Provide `from_world_result` to project background or imported results into the same contract without fabricating shots or player statistics.
- Keep internal fast simulation IDs separate from world fixture IDs; their formats do not have to match.

## Tests (Python only)

```
python -m pytest -q -ra tests/test_ts_07_match_result_contract.py tests/test_ts_04_managed_match_transactions.py
```

Test a real managed match, a synthetic score source suitable for future 2D, background results, swapped home/away teams, invalid scores and mismatched fixture IDs. Full suite: `python -m pytest -q -ra`.

## Limits

This is a **contract-level foundation**, not unification of fast- and background-match statistical models. Background simulations still use the lightweight resolver. Injuries, officials, substitutions and other future deep-game consequences are not added here. The 2D engine remains out of scope.
