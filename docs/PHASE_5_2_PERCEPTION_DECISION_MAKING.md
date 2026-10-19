> **LEGACY 2D DOCUMENT — HISTORICAL / EXPERIMENTAL**
>
> This document describes the original spatial 2D implementation built in Phase 5.0-5.9. That engine is now frozen and is **not** the critical-path match resolver. Core game systems use `FastMatchSimulator`. Do not extend this phase as the basis for new management features. A future 2D mode will be rebuilt incrementally; see `FUTURE_2D_REBUILD.md`.

# Phase 5.2 - Perception & Decision Making

## Goal

Phase 5.2 gives spatial PlayerAgents the ability to inspect the current football
situation and choose an **intended action**.

This phase deliberately separates:

```text
DECISION
what the player wants to try

from

EXECUTION
whether the player actually succeeds
```

A player can therefore decide to attempt a difficult progressive pass because the
tactic encourages it, while Phase 5.3 can later determine that the pass is
misplaced or intercepted.

No pass, dribble, cross or shot is executed by Phase 5.2.

---

## Perception model

`PerceptionSystem` creates a deterministic spatial perception snapshot for an
active player.

It currently evaluates:

- nearby teammates;
- nearby opponents;
- distance to each perceived player;
- forward progress relative to the team's attacking direction;
- pressure around the player;
- usable local space;
- opponent goal position;
- direction and distance to goal;
- candidate receivers;
- passing-lane openness;
- receiver space.

The awareness radius is influenced by existing mental attributes:

- vision;
- tactical intelligence;
- anticipation.

This is football awareness, not a literal rendering camera or a hard human field
of view.

---

## Pressure and space

Pressure is derived from the actual distance of opponents around a location.
Multiple nearby opponents compound the pressure score.

```text
opponents close to player
        ↓
higher pressure
        ↓
lower local space
```

Pressure is represented internally on a normalized `0..1` scale.

It does not reduce the player's attributes.

---

## Passing lanes

For every perceived teammate, the engine evaluates a passing lane.

The lane currently includes:

- pass distance;
- forward progress;
- nearest opponent through the useful interior of the lane;
- lane openness;
- pressure around the receiver;
- receiver space.

An opponent standing directly between passer and receiver therefore makes the
lane less attractive without applying a hidden statistical penalty.

Opponents very close to the passer or receiver are represented mainly by passer
pressure and receiver-space pressure rather than being counted twice as lane
blockers.

---

## Possession ownership

Phase 5.2 introduces explicit controlled ball ownership through the spatial match
state.

When an active player owns the ball:

- `BallState.owner_agent_id` points to that player;
- possession team and possession owner are synchronized;
- exactly one active player has `has_ball=True`;
- while the owner moves, the ball follows the owner's spatial position.

This is only controlled possession state. Ball trajectories and pass execution
belong to Phase 5.3.

---

## Candidate possession actions

The decision layer can currently consider:

- `HOLD`;
- `SHORT_PASS`;
- `PROGRESSIVE_PASS`;
- `LONG_PASS`;
- `CARRY`;
- `DRIBBLE`;
- `CROSS`;
- `SHOOT`;
- `CLEARANCE`.

Actions are context-valid rather than universally available.

Examples:

```text
SHOOT
-> only becomes an option in plausible attacking range.
```

```text
CROSS
-> requires a sufficiently wide and advanced position.
```

```text
DRIBBLE
-> requires an opponent close enough to engage.
```

```text
CLEARANCE
-> becomes relevant in the defensive third or under heavy pressure.
```

These are intended actions only. Phase 5.2 does not resolve their outcome.

---

## Action utility

Every candidate action receives an evaluation made from five separate factors:

```text
Action utility
=
Tactical fit
+ Spatial value
+ Player capability
+ Decision quality
- Risk
```

The factors are kept visible for debugging and future calibration.

### Tactical fit

Consumes effective tactical behaviour rather than preset names.

Examples include:

- team pass length;
- verticality;
- passing risk;
- patience;
- team crossing frequency;
- long-shot frequency;
- individual passing risk;
- individual dribbling frequency;
- individual crossing frequency;
- individual shooting frequency;
- hold-up play;
- attack-space behaviour.

Role influence enters through the effective player instructions created by the
role preset plus any user overrides.

### Spatial value

Uses actual current geometry, for example:

- open/blocked pass lane;
- receiver space;
- forward progress;
- local free space;
- distance to goal;
- central shooting angle;
- wide crossing position;
- space in front of a carrier.

### Player capability

The decision layer can consider whether an action fits the player's abilities,
but it does **not** determine execution success.

Relevant attributes differ by action.

Examples:

```text
pass
-> passing, technique, first touch, vision, creativity
```

```text
dribble
-> dribbling, technique, agility, acceleration, decisions
```

```text
shot
-> finishing / long shots, technique, shot power, composure, decisions
```

### Decision quality

Uses mental attributes such as:

- decisions;
- composure;
- tactical intelligence;
- anticipation.

### Risk

Risk is derived from the current action context rather than a generic random
failure value.

Examples:

- blocked passing lane;
- marked receiver;
- passer under pressure;
- pass distance;
- lack of forward space;
- poor shooting location.

---

## Probabilistic decision selection

The engine does not always choose the action with the highest utility.

Instead it performs a controlled weighted choice among the valid options.

Better decision makers are more strongly biased toward higher-utility actions,
but football remains probabilistic.

All randomness comes from the match-owned seeded random source.

Therefore equivalent engines with:

```text
same MatchSnapshot
+ same seed
+ same state
+ same decision call order
```

choose the same action.

---

## Decision is not execution

Calling the decision system:

```text
engine.decide(player_id)
```

returns an intention such as:

```text
PROGRESSIVE_PASS -> ST
```

It does **not**:

- move the ball;
- transfer possession;
- decide pass success;
- generate an interception;
- create a shot result;
- change the score.

This boundary is intentional and is required before Phase 5.3.

---

## Debug review

Run:

```powershell
python examples/demo_perception_decisions.py
```

The debug report compares:

1. a midfielder in normal build-up;
2. a midfielder under heavy pressure with the direct central lane blocked.

It prints:

- pressure;
- local space;
- perceived teammates/opponents;
- candidate passing lanes;
- direct lane to the striker;
- top action options;
- tactical/spatial/capability/decision/risk factors;
- the final seeded decision.

This is a decision-engine debugging surface, not final match commentary.

---

## Automated validation

Phase 5.2 adds tests for:

- perception excluding the player himself;
- distance-sorted perceived players;
- opponent proximity creating pressure;
- pressure reducing local space;
- passing-lane blocking;
- receiver pressure reducing receiver space;
- home/away goal direction;
- synchronized ball ownership;
- possessed ball following its owner;
- possession decisions requiring the actual ball owner;
- context-valid base actions;
- blocked lanes reducing pass utility;
- pass-length tactics changing pass preference;
- individual dribble instructions changing dribble preference;
- dribble context validation;
- shot context validation;
- cross context validation;
- clearance context validation;
- seeded decision reproducibility;
- decision selection not executing the chosen action.

Expected project result after Phase 5.2:

```text
110 passed
```

---

## Not implemented yet

Phase 5.2 deliberately does not implement:

- pass trajectories;
- pass completion/failure;
- first-touch resolution;
- interceptions as resolved actions;
- possession circulation;
- pressing duels;
- tackles;
- dribble outcomes;
- cross trajectories;
- shot outcomes;
- xG;
- goalkeeper actions;
- goals;
- full match flow;
- commentary output.

The players can now answer:

```text
What is happening around me?
What could I try?
What do I choose?
```

They still cannot answer:

```text
Did I execute it successfully?
```

---

## Next step

Phase 5.3 - Passing & Possession.

The next phase will take selected pass intentions and resolve actual football
execution:

- pass target;
- trajectory;
- travel time;
- passer execution quality;
- receiver movement;
- first touch;
- misplaced passes;
- interceptions;
- possession transfer;
- coherent passing sequences.
