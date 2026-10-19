# Phase 5.11A - Player Rating & Current Performance Foundation

## Objective

Phase 5.11A creates the player-quality foundation required by the future Fast Match
Simulator without adding any dependency on the legacy 2D Match Engine.

The phase formalizes two separate visible ratings:

- `OVR`: underlying football quality;
- `ACT`: current effective performance level in the present context.

The central rule is:

```text
OVR answers: "How good is this footballer?"
ACT answers: "How much of that quality can he express right now?"
```

`ACT` never rewrites `OVR`.

## Overall (OVR)

`OVR` is derived from the player's real attributes. It is not an independent hidden
ability and it is not a simple arithmetic mean.

The first implementation uses position-profile weightings anchored to the player's
`original_position`. This means moving a winger to striker or centre-back does not
change his OVR by itself.

Only changes to the underlying attributes can change OVR.

The weighting tables are an initial model and can be calibrated later. They are not
per-role ratings.

The Match Engine and Fast Match Simulator must still use specific attributes for
specific football actions. OVR is a summary and a team-quality input, not a universal
action resolver.

## Current effective rating (ACT)

`ACT` starts from OVR and applies current contextual adjustments.

Most positive-context scales use `65` as their neutral point:

```text
0..64  -> penalty
65     -> neutral
66..100 -> bonus
```

This rule applies to:

- form;
- confidence;
- morale;
- match sharpness;
- positional familiarity;
- role familiarity;
- tactical familiarity;
- chemistry.

Penalties and bonuses are deliberately asymmetric and non-linear.

The middle of the scale is intentionally soft: ordinary bad form, low confidence or
partial unfamiliarity should nudge ACT rather than destroy it. Severe drops are reserved
for genuinely extreme cases.

Positive adjustments are deliberately conservative. A single excellent factor must not
turn a good player into an elite one. Position, role, confidence, form, tactical
familiarity and chemistry each provide only a small standalone upside.

A larger `context_excellence` bonus exists only for exceptional total alignment. It is
calculated multiplicatively across form, confidence, morale, match sharpness, positional
familiarity, role familiarity, tactical familiarity and chemistry, with physical
condition acting only as a gate. If one of those dimensions is merely average, the
exceptional bonus collapses quickly.

For calibration, an `80 OVR` player with every relevant contextual dimension at `100`
and full condition can reach approximately `97 ACT`. A merely very good context should
remain far below that ceiling.

Positional unfamiliarity is the strongest contextual factor because asking a player to
perform in a completely alien position can radically reduce how much of his ability is
usable. Role and tactical unfamiliarity are materially lighter modifiers: they matter,
but they must not behave like hidden alternate Overall ratings.

This allows both directions:

```text
84 OVR / 72 ACT
```

A high-quality player is currently struggling.

```text
78 OVR / 82 ACT
```

A lower-quality player is currently in an excellent context and performing above his
structural level.

## Physical condition exception

Physical condition is intentionally one-sided.

`fitness` remains the stored legacy field for compatibility, while the rating model
exposes it conceptually as `condition`:

```text
75..100 -> no ACT modifier
below 75 -> progressive penalty
```

Being at 100 condition does not make a player better than his normal level. It simply
means he is physically ready to express it.

`fatigue` remains available as workload/recovery state, but it is not applied as a
second direct ACT penalty. Existing fatigue mechanics already reduce fitness/condition,
so using both directly would double-count the same physical problem.

## Adaptability

`adaptability` is now an explicit mental attribute.

It does not increase OVR or grant a free ACT bonus.

Instead, it changes how strongly an unfamiliar context hurts the player while he is
still adapting:

- high adaptability softens unfamiliarity penalties;
- low adaptability makes the same unfamiliarity more damaging;
- once familiarity reaches the neutral zone, adaptability no longer creates a bonus by
  itself.

Long-term rules for learning speed, failed adaptation and career development are not
implemented in 5.11A. This phase only establishes the attribute and the match-time
performance interpretation required by later systems.

## No hidden Overall by role

There is no separate permanent rating such as:

```text
Advanced Forward: 88
Target Forward: 72
False Nine: 84
```

A player's OVR remains the same.

Role familiarity can raise or lower ACT around the neutral point, but its modifier is
bounded and intentionally much smaller than the penalty for a completely alien position.
The specific attributes required by a role remain available to the simulator when
resolving actual football actions.

This preserves the distinction between:

```text
quality of the player
!=
quality of execution in the current role
```

## Confidence

Confidence is a first-class player-state value on the same 0-100 scale.

The neutral value is 65:

- above 65 it can improve ACT;
- below 65 it can reduce ACT;
- ordinary low confidence produces a moderate penalty rather than a collapse;
- the penalty becomes sharply more severe only below 5, representing an exceptionally
  broken confidence state;
- changing confidence never directly rewrites OVR.

The state object exposes bounded helpers for confidence and form changes so later
match/world-update systems can safely apply performance consequences.

Automatic confidence evolution from goals, mistakes, playing time, manager decisions
and season outcomes belongs to a later development phase.

## MatchSnapshot integration

`PlayerMatchSnapshot` now freezes both:

- `overall_rating`;
- `current_rating`.

The current rating for a starter is calculated with his actual assigned position, role
and tactic at kickoff.

This gives the future Fast Match Simulator stable, immutable player-quality inputs
without importing or running 2D spatial agents.

The snapshot also already contains the underlying attributes, state and familiarity
values, so Fast Match Simulator events can use specific inputs instead of relying on
ACT alone.

## Phase boundary

Phase 5.11A does **not** implement:

- Fast Match Simulator match resolution;
- automatic post-match confidence/form changes;
- positional/role learning over time;
- failed-adaptation career loops;
- long-term OVR progression or regression;
- scouting uncertainty around OVR/ACT;
- UI diamonds.

Those systems will consume this foundation later.

The next implementation step is Phase 5.11B - Fast Match Simulator MVP.
