# Phase 5.11D - Extra Time & Penalties Refinement

## Objective

Close the Fast Match Simulator knockout path before competition and season integration.

Phase 5.11D refines only the resolution of tied knockout matches. It does not alter the calibrated 90-minute Fast Simulator model and it does not import or execute the legacy spatial 2D engine.

The design rule remains the same as for normal play:

```text
never choose the winner first
```

Extra time is simulated through football processes and a shootout is resolved kick by kick.

## Explicit 90 / ET / shootout result split

`FastMatchResult` now exposes:

- regulation goals;
- extra-time goals;
- final football score;
- penalty-shootout score;
- individual penalty-kick events;
- extra-time substitution events.

Shootout kicks never count as match goals, shots or xG.

A result can therefore distinguish cleanly between:

```text
1-1 after 90
2-1 after extra time
```

and:

```text
1-1 after 90
1-1 after 120
4-3 on penalties
```

## Extra time is not another 30 minutes at full regulation pace

The 30 minutes are simulated as two separate 15-minute periods:

```text
91-105
106-120
```

The first extra-time half runs below normal regulation pace and the second is slower again.

Player energy is recalculated from:

- current condition;
- stamina;
- tactical tempo;
- pressing workload;
- minutes already played.

Fatigue affects attacking execution while tired defending can also concede better chances. The two effects are deliberately separate instead of applying one generic team-strength penalty.

## Extra-time substitutions

Competition rules already expose:

```text
extra_time_additional_substitutions
```

The Fast Simulator now consumes that rule when a match reaches extra time.

The automatic fast-sim selection considers:

- projected condition after 90 minutes;
- incoming player's current level;
- positional familiarity;
- role familiarity;
- tactical familiarity.

A player with extremely poor positional familiarity is not inserted merely because he is fresh.

The result records the outgoing player, incoming player, minute and position. Player statistics reconcile minutes correctly: a player replaced at the start of extra time receives 90 minutes and his replacement receives 30.

This phase intentionally models the *additional extra-time allowance*. Full regulation substitution strategy belongs to later manager/AI match-management work.

## Penalty shootouts

Shootouts are resolved one kick at a time.

The taker order prioritizes actual penalty suitability using:

- penalties;
- composure;
- finishing;
- confidence;
- current effective level.

Outfield players are ordered before the goalkeeper under normal circumstances.

Each kick probability considers:

- taker's penalty skill;
- finishing;
- composure;
- confidence;
- current rating;
- current condition / fatigue;
- opposing goalkeeper quality;
- goalkeeper confidence;
- goalkeeper condition;
- pressure of the moment.

Goalkeeper penalty quality uses specialist goalkeeper attributes when available:

- one-on-ones;
- reflexes;
- goalkeeper positioning.

Legacy fixtures without specialist goalkeeper attributes retain a compatibility fallback.

## Pressure

Pressure grows through the shootout.

Early kicks are relatively low pressure. Rounds four and five carry more weight and sudden death starts at a substantially higher pressure level.

Pressure does not apply a flat miss chance. Its effect depends on the taker's resilience, derived primarily from composure and confidence.

Therefore:

```text
high pressure + high composure/confidence
!=
high pressure + low composure/confidence
```

A mentally strong taker can remain reliable while a psychologically damaged player becomes significantly less reliable in decisive moments.

## Reproducibility and event integrity

Shootout randomness uses the Fast Simulator's isolated seeded RNG namespaces.

The same snapshot, seed and engine version therefore reproduce:

- whether extra time is reached;
- extra-time events;
- substitutions;
- penalty order;
- each scored/missed kick;
- final winner.

Every shootout event stores:

- sequence number;
- round;
- club;
- taker;
- goalkeeper;
- scored/missed result;
- sudden-death flag;
- pressure level;
- running shootout score.

## Reference knockout benchmark

A 500-match equal-team 70-v-70 reference run produced approximately:

```text
N=500
regulation winners=371
reached extra time=129
extra-time winners=49
penalty shootouts=80
```

For matches reaching extra time:

```text
added ET goals=0.64
added ET shots=6.34
added ET xG=0.70
extra-time substitutions=2.00 per match
```

This keeps extra time lower-paced than simply adding one third of a regulation match at unchanged intensity.

Reference condition from the original 5.11D pass was intentionally superseded by Phase 5.11E. The first 5.11D implementation proved that the knockout path worked, but its physical depletion was too mild to make rotation meaningful.

With the Phase 5.11E condition system, a neutral 70-level reference run is closer to:

```text
average participant condition after 90 minutes: ~58
outfield long-runners after 120 minutes:          ~30
```

Exact values vary by stamina, position, tactical workload and substitutions. See `PHASE_5_11E_CONDITION_RECOVERY.md` for the current physical-state model.

Reference equal-team shootouts after the Phase 5.11E physical-state upgrade remain in the same football-like range:

```text
conversion:        ~75%
average kicks:     ~10.7
sudden death:      ~20-25%
home/away wins:    broadly balanced
```

The lower late-match condition now has a real but bounded effect on shootout execution.

A separate same-quality specialist test used:

```text
HOME: penalties 95 / confidence 90
AWAY: penalties 45 / confidence 40
```

The stronger penalty side won approximately `72.6%` of shootouts: a strong football-derived edge, but not a guaranteed result.

## Regression protection

Phase 5.11D also reruns the Phase 5.11C 90-minute calibration.

The reference neutral 200-match output remains unchanged at approximately:

```text
goals=2.83
shots=25.16
SOT=9.29
xG=2.79
fouls=22.27
YC=3.35
corners=10.02
H/D/A=38.5/27.0/34.5
```

This is important: knockout refinement must not silently disturb the already calibrated regulation simulator.

## Validation command

```powershell
$env:PYTHONPATH = "src"
python tools/calibrate_fast_knockout.py --matches 500
```

The benchmark reports extra-time pace, condition, shootout conversion, shootout length, sudden death, home/away balance and a penalty-specialist comparison.
