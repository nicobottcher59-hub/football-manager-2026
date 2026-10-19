# TS-18.2 - Roles & Position Integrity

## Scope

Bugfix only. The original position/role OVR calculation and ACT adjustments are **unchanged**. No new formation, role, tactical instruction, match event, gameplay rule or user interface element is added.

## Confirmed defects

1. **Live tactical changes:** the spatial match engine reused `ACT - OVR` from the previous assignment. That difference included the *previous role's* familiarity and chemistry, so a change of role or tactic could apply the wrong execution rating. A repeatable case produced 71.3 ACT instead of the canonical 64.7.
2. **Spatial substitutions:** an incoming substitute inherited only their neutral pre-match state delta, omitting the already-defined role/tactic ACT modifiers. In the synthetic regression, the result was 69.6 instead of the canonical 64.0.
3. **Extra-time fast substitutions:** a separate approximation with lower role/tactic penalties produced values different from the canonical formula for the same player and position. In the same regression, the result was 67.0 instead of 64.0.
4. **Partial live tactical updates:** an incompatible role encountered late in a team-wide change could leave agents from earlier slots already modified despite the failed operation.
5. **Match chemistry on reassignments:** snapshot ratings contained match chemistry in their original ACT, but didn't retain the input to recalculate it correctly after a role change or substitute introduction.

## Repair

- Use `domain/snapshot_assignment.py` to rebuild an *ephemeral rating-only Player* from a frozen match snapshot, then invoke `Player.current_rating(CurrentRatingContext(...))`. **No formula or weighting is duplicated or changed.**
- Capture the chemistry input in `PlayerMatchSnapshot.rating_chemistry` (neutral default 65 for backwards compatibility); the bench carries the supplied chemistry too.
- Use this one assignment calculation in spatial live tactics, spatial substitutions and fast extra-time substitutions.
- Validate tactic slot and position coherence, then compute all updated agents before mutating the live spatial state. Incompatible roles leave the runtime team unchanged.

## Tests and contracts

`tests/test_ts_18_2_roles_position_integrity.py` covers role changes with non-neutral chemistry; repeatable switches back; spatial substitutes; fast substitutes with role familiarity 0 / 65 / 100; invalid role changes atomicity.

```
python -m pytest -ra tests/test_ts_18_2_roles_position_integrity.py
python -m pytest -ra
```

No TS-18.3 (tactical consumers), balancing, new roles, or formation-editing features are included.
