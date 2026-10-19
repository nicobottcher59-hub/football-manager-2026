> **LEGACY 2D DOCUMENT — HISTORICAL / EXPERIMENTAL**
>
> This document describes the original spatial 2D implementation built in Phase 5.0-5.9. That engine is now frozen and is **not** the critical-path match resolver. Core game systems use `FastMatchSimulator`. Do not extend this phase as the basis for new management features. A future 2D mode will be rebuilt incrementally; see `FUTURE_2D_REBUILD.md`.

# Phase 5.5 — Ball Progression

## Objective

Phase 5.5 turns the possession choices introduced in Phase 5.2 into real spatial attacking progression beyond ordinary passing.

The engine now supports:

- controlled carries;
- one-on-one dribbles;
- forward off-ball runs;
- overlaps and underlaps;
- inside and wide runs;
- more aggressive progressive passes into moving space;
- crosses;
- low crosses;
- high crosses;
- early crosses;
- byline crosses;
- cutbacks.

These actions operate on the same 2D `MatchState` used by tactical positioning, passing and defending.

---

## Design rule

Tactical instructions influence behaviour and action selection. They do not rewrite player attributes.

Examples:

```text
attack_space = VERY_HIGH
→ longer/more aggressive carry and run targets
→ no bonus to dribbling or pace
```

```text
dribbles frequently
→ dribble receives more decision weight in Phase 5.2
→ actual success still depends on attacker/defender quality and spatial context
```

```text
cross_type = CUTBACK
→ changes the physical cross target and trajectory
→ does not increase crossing attribute
```

---

## Controlled carries

A carry has a spatial profile containing:

- origin;
- target;
- distance;
- movement speed;
- ball-control quality;
- probability of retaining control;
- expected duration.

The target is selected from real forward space rather than by applying a hidden progression bonus.

The carrier moves through normal fixed simulation ticks. The ball remains attached to the actual carrier while controlled.

Possible carry outcomes currently are:

```text
COMPLETED
LOOSE_BALL
```

The carry system is deliberately separate from the decision layer:

```text
DecisionSystem
→ decides CARRY

BallProgressionSystem
→ executes the carry
```

---

## Carry direction and space

The engine evaluates multiple forward candidate directions and checks real opponent pressure at the candidate destination.

This means an open diagonal can be preferred over running straight into a defender.

Current tactical inputs include:

- individual `attack_space`;
- individual in-possession positional behaviour;
- team `central_focus`;
- current opponent pressure.

---

## Off-ball runs

The engine can build and activate explicit off-ball run plans for the team in possession.

Run priority consumes:

- `forward_runs`;
- `attack_space`;
- `roaming`;
- off-the-ball movement;
- anticipation;
- pace;
- acceleration.

Goalkeepers and the current ball carrier are excluded from the run plan.

Run movement occurs through the normal fixed-step spatial engine, not teleportation.

---

## Run types

Current run types are:

```text
FORWARD
OVERLAP
UNDERLAP
INSIDE
WIDE
```

### Overlap / underlap

The existing team `overlap_frequency` instruction now has an explicit progression consumer.

Example:

```text
LW moves inside
+ overlap frequency high
→ LB is more likely to receive an OVERLAP target outside
```

If the winger stays wide, the full-back can instead receive an `UNDERLAP` target toward an interior lane.

This is represented by actual X/Y targets and movement.

---

## Dribbling

A dribble is treated as a real one-on-one duel.

The attacker currently consumes attributes including:

- dribbling;
- technique;
- agility;
- acceleration;
- balance;
- decisions;
- composure.

The defender consumes attributes including:

- tackling;
- anticipation;
- positioning;
- agility;
- acceleration;
- balance;
- strength.

Spatial context also matters:

- local pressure;
- available forward space;
- physical distance to the nearest defender.

Possible outcomes:

```text
BEATS_DEFENDER
DEFENDER_WINS
LOOSE_BALL
```

A successful dribble does not teleport the attacker beyond the defender.

Instead:

```text
successful dribble duel
→ create escape target
→ start a real spatial carry
→ attacker moves through fixed ticks
```

---

## Progressive passes into space

The Phase 5.3 passing engine already leads moving receivers.

Phase 5.5 extends that behaviour so a progressive pass leads a forward-running receiver more aggressively than an ordinary short pass.

The amount of lead consumes:

- the receiver's current real velocity;
- `forward_runs`;
- `attack_space`;
- pass type.

This creates the first through-ball / pass-into-space foundation without adding a separate artificial success bonus.

---

## Crosses and cutbacks

Crosses now use a real spatial ball trajectory.

A cross profile contains:

- crosser;
- intended receiver;
- cross type;
- origin;
- intended target;
- actual target after execution error;
- speed;
- maximum height;
- travel time;
- execution quality.

Supported existing `CrossType` values are consumed:

```text
EARLY
BYLINE
LOW
HIGH
CUTBACK
MIXED
```

`MIXED` is resolved contextually in this first version. For example, a player very close to the byline can naturally select a cutback trajectory.

---

## Cross execution

Cross execution consumes:

- crossing;
- technique;
- vision;
- decisions;
- composure;
- current pressure.

The ball moves through the same fixed 0.25-second simulation ticks.

High crosses receive real temporary ball height. Low crosses and cutbacks remain close to the ground.

Possible outcomes are:

```text
COMPLETED
INTERCEPTED
MISPLACED
BAD_CONTROL
```

Opponents can intercept the physical cross path.

Receiver control is resolved separately from the quality of the cross.

Headers as goal attempts and final chance resolution remain Phase 5.6 work.

---

## Determinism

Every random progression resolution uses the match-owned seeded random source.

Therefore:

```text
same MatchSnapshot
+ same seed
+ same spatial setup
+ same action sequence
= same progression result
```

---

## Scope boundary

Phase 5.5 does **not** yet implement:

- shot resolution;
- xG;
- goalkeeper saves;
- goals;
- full autonomous 90-minute action scheduling;
- final event commentary.

Those belong to later Phase 5 sub-phases.

---

## Debug review

Run:

```powershell
$env:PYTHONPATH = "src"
python examples/demo_ball_progression.py
```

The demo checks:

1. a controlled carry through open space;
2. off-ball runs including overlap/underlap behaviour;
3. a real one-on-one dribble and spatial escape;
4. a byline cutback travelling through the 2D ball state.

---

## Automated validation

Phase 5.5 adds tests covering:

- carry validation and fixed-step movement;
- deterministic carry execution;
- `attack_space` affecting distance rather than attributes;
- pressure-aware carry direction;
- off-ball run eligibility;
- `forward_runs` affecting real run distance/priority;
- overlap and underlap targets;
- fixed-step off-ball movement;
- dribble engagement distance;
- attacker/defender attribute effects;
- deterministic dribble resolution;
- successful dribble escape movement;
- failed dribble possession outcomes;
- cutback selection near the byline;
- explicit high-cross trajectory;
- real ball height during aerial crosses;
- cross path interception;
- pressure affecting cross execution;
- deterministic crossing;
- progressive passes leading forward runners more than short passes.

Expected full suite after this phase:

```text
177 passed
```
