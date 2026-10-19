# TS-18.3 - Tactical Logic & Instructions (bug fixes)

## Scope and invariants

Applies **after TS-18.2**. This is a correction to existing tactical consumers, not a tactical feature release. All formation presets, individual role instructions, OVR/ACT formulas, match-event models, UI and save formats are unchanged. Existing match-resolution coefficients were not tuned.

The older `docs/TS_13_TACTICAL_CONSUMER_COVERAGE.md` describes the state **at TS-13**. This document supersedes only the two confirmed defects below.

## Bug A: `game_management.risk_when_leading` leaked into the whole match

**Before:** `analyze_tactical_style()` averaged `risk_when_leading` unconditionally with team passing risk and counterattack risk. The fast simulator consumed that average to compute shots, shot quality and tactical complexity *before either team had taken the lead*, including drawn matches. The first reproduction test compared `VERY_LOW` and `VERY_HIGH`: `style.risk` incorrectly differed by 33.33 points before kick-off.

**Fix:** retain the established three-factor average with its neutral management component (50) as the **baseline**. Keep the selected conditional instruction in `FastTeamProfile.risk_when_leading` (default 50 for manually constructed profiles). If and only if the score favors that team, the fast simulator uses the existing average's original contribution `(risk_when_leading - 50) / 3`. No new risk coefficients or bonuses are introduced. On a later equalizer or loss of the lead, risk reverts to baseline. The change applies to shots generated *after* the minute of the score change, never before it.

To preserve normal simulation outcomes, the initial full-match shot generation and RNG stream remain unchanged. If a lead activates a non-neutral setting, only the remaining minutes are recalculated using isolated deterministic RNG streams, with the same `_expected_shots`, `_chance_xg` and finishing rules. The same approach handles the two extra-time periods while respecting their existing pace and energy factors. Simultaneous goals at the same minute are evaluated together. This is still a minute-resolution fast simulator, not a live spatial replay.

## Bug B: urgency-created chances bypassed `time_wasting`

**Before:** TS-13 filtered all existing shots chronologically for time wasting and **then** appended urgency-driven late shots. These new shots could escape a leader's active time-wasting filter even though normal shots were subject to it.

**Fix:** filter the original timeline up to minute 70, decide urgency using its **accepted** score, generate the existing urgency shots, and then filter *all* remaining events (original + urgency) chronologically. Retained goals are the only ones counted for subsequent score-sensitive decisions. The pre-existing minute-65 / minute-70 triggers, maximum 22% rejection probability, 0.42 urgency pace multiplier and named RNG streams are unchanged. When urgency and time wasting do not overlap, the former result is preserved.

## Tests / evidence

- First failure confirmed against the TS-18.2 base: changing `risk_when_leading` changed the unconditional style risk before kickoff.
- Second failure confirmed against the provisional TS-18.3 base: an urgency-created chance was never offered to the time-wasting filter.
- Targeted tests cover leading, trailing, tied, simultaneous goals, equalizers, minute 90, entering extra time with a lead, isolated RNG, deterministic matches and coverage catalogue.
- Paired experiment: **400** seeds comparing extremely low/high leading risk; the **first regulation goal** was identical in all 400 comparisons, with 183 pairs yielding subsequent differences. Among the 43 scoreless pairs, results were identical.
- Baseline comparison against TS-18.2: **120** seeded default-tactic matches and **120** seeded matches with time wasting active produced exactly the same outputs when no conflicting instructions were active.
- Run focused: `python -m pytest -ra tests/test_ts_18_3_tactical_logic_instructions.py tests/test_ts_13_tactical_consumer_coverage.py`
- Run all: `python -m pytest -ra`

## What intentionally remains outside TS-18.3

The **22** controls marked `not_modelled` in `fast_simulation/tactical_coverage.py` stay unimplemented in the fast simulator. In particular, player shooting/dribbling/attack-space instructions already exist in the spatial engine but do not gain invented behavior in the fast simulation. The catalogue now reports 29 direct effects, 3 partial effects, 4 workload effects, 1 label-only field and 22 unmodelled fields.

The fast-simulator clock is an approximation: the late urgency rule is still evaluated at its established minute-70 checkpoint, and time wasting at minute 65. Regulation score-sensitive control processing happens after the initial chances are generated; it is not intended to model a 2D real-time decision loop. Precise interleaving of multiple management instructions and the spatial motor's future individual-level features require a separate product decision, not an undocumented patch.
