# TS-07.1 — Match & Lineup Integrity (consolidated)

This single patch replaces the planned TS-07.1 / TS-07.2 / TS-07.3 split.
**Required baseline:** the TS-07 match-result contract must already be present.
It introduces no new gameplay mechanics, UI changes, database schema changes,
or new third-party dependencies.

## Changes

1. **Canonical fixture identity** — `record_managed_match()` now looks up the
   requested fixture ID in `WorldSeasonRunner.fixtures` and verifies the
   supplied home/away participants against that authoritative entry before
   recording anything. A forged or stale fixture with the right ID but
   inverted participants is rejected. The existing home/away score contract
   remains active, and a valid caller-supplied value copy is still accepted.
2. **Temporary tactics isolation** — the web `quick_sim` handler deep-copies the
   manager's *permanent tactic* before applying match-only commands to the
   temporary session. The played match still uses the temporary formation,
   role, player and team instructions; after it finishes, the permanent plan
   is restored while normal match consequences remain.
3. **Canonical player identity / kickoff eligibility** — `Club.validate_lineup`
   now verifies that every selected player is the same canonical `Player`
   object held by that club and is still available at kickoff. This covers
   starters and bench after injury, suspension or zero fitness changes since
   lineup submission. Validation is invoked at the existing snapshot boundary
   and therefore covers direct simulation as well as the HTTP UI.

**Compatibility:** The existing spatial engine intentionally scopes player IDs
by side, so different clubs may legitimately use identical *local* player IDs
in certain synthetic matches. TS-07.1 intentionally does not introduce global
player-ID uniqueness checks or modify those established mechanics.

## Tests

Run in Windows PowerShell from the repository root (no Node.js required):

```powershell
python -m pytest -q -ra tests/test_ts_07_1_match_lineup_integrity.py tests/test_ts_07_match_result_contract.py tests/test_match_snapshot.py tests/test_spatial_core.py tests/test_ui35_matchday.py
```

Then optionally run the full regression:

```powershell
python -m pytest -q -ra
```

New tests deliberately reproduce the bugs on the pre-patch baseline, and cover
rejection without world mutation, restoration of match-only instructions,
formation/bench changes, eligibility immediately before kickoff, canonical
player references, valid league scores and side-scoped IDs.

## Manual checks

1. Start the existing portable UI and open a managed match preview.
2. Change a team instruction and a player's role or individual instruction.
3. Simulate the match; confirm it completes and records a real result.
4. Reopen the permanent Squad/Tactics panel; confirm the temporary choices did
   not replace the persistent tactic. Match fatigue and morale should update.
5. Repeat with a different match-only formation or bench player; after the
   match the permanent XI/formation must still be the selected ones.

This patch does **not** tackle score coercion/winner semantics (TS-08), calendar
invariants (TS-09), or persistent roster-edit transactions (TS-11).
