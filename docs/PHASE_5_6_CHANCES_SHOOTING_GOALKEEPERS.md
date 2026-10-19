> **LEGACY 2D DOCUMENT — HISTORICAL / EXPERIMENTAL**
>
> This document describes the original spatial 2D implementation built in Phase 5.0-5.9. That engine is now frozen and is **not** the critical-path match resolver. Core game systems use `FastMatchSimulator`. Do not extend this phase as the basis for new management features. A future 2D mode will be rebuilt incrementally; see `FUTURE_2D_REBUILD.md`.

# Phase 5.6 — Chances, Shooting & Goalkeepers

## Objective

Phase 5.6 turns attacking progression into explicit chances and shot outcomes.

The Match Engine now supports:

- contextual chance quality (`xG`);
- foot shots;
- headers;
- physical shot trajectories through the 2D match state;
- shot placement and execution error;
- defensive blocks;
- goalkeeper reaction movement;
- saves;
- parries and rebounds;
- woodwork;
- off-target shots;
- goals.

This remains part of the same deterministic spatial simulation. There is no separate goal/result generator.

---

## Core rule: chance quality is separate from finishing

`xG` describes the quality of the simulated chance, not the shooter's finishing attribute.

Therefore, from the same situation:

```text
poor finisher
elite finisher
```

can receive the same pre-shot `xG`.

Their execution can still be very different because shot placement uses relevant player attributes.

Conceptually:

```text
Chance context
→ xG

Player ability + pressure + condition
→ shot execution

Shot trajectory + goalkeeper
→ final outcome
```

This prevents `xG` from becoming a hidden Overall/finishing bonus.

---

## Contextual xG

The first xG model consumes real simulated context including:

- shot distance;
- angle to goal;
- pressure on the shooter;
- defenders occupying the shot lane;
- body part;
- chance origin;
- goalkeeper position;
- transition speed when that context is explicitly available.

Current chance origins are:

```text
OPEN_PLAY
THROUGH_BALL
CROSS
CUTBACK
REBOUND
SET_PIECE
```

These are situational inputs, not guaranteed bonuses. They modify the description of the chance being evaluated.

The xG model will be statistically recalibrated in Phase 5.10.

---

## Shot execution

Foot-shot execution consumes relevant attributes such as:

- finishing;
- long shots;
- technique;
- shot power;
- composure;
- decisions;
- balance.

Distance and current defensive pressure also affect execution.

A better finisher does not receive higher xG merely for being better. Instead, the better player can produce more accurate shot placement from the same chance.

---

## Headers

Headers are represented explicitly with `ShotBodyPart.HEAD`.

Header execution consumes a different attribute mix including:

- heading;
- jumping reach;
- anticipation;
- bravery;
- composure;
- finishing.

Headers also have a distinct trajectory/speed profile and xG body-part adjustment.

This creates the execution foundation for converting the high-cross system from Phase 5.5 into aerial chances.

---

## Shot trajectory

Shots do not teleport to a result.

A started shot:

1. detaches the ball from the shooter;
2. calculates a real goal-plane target;
3. gives the ball physical velocity;
4. advances the ball through normal fixed `0.25 s` ticks;
5. exposes temporary ball height;
6. allows defenders and goalkeeper to react before resolution.

The internal simulation timestep remains unchanged by future x1/x2/x4 playback.

---

## Shot placement

The shooter first selects an intended target.

Execution quality then creates an actual target around that intention.

This allows:

```text
same decision to shoot
+ different finishing/composure/pressure
→ different placement accuracy
```

Shot power changes real ball speed/travel time rather than xG.

---

## Defensive blocks

Non-goalkeeper defenders can block the actual travelling shot path.

Blocking consumes defensive qualities such as:

- anticipation;
- positioning;
- bravery;
- tackling;
- agility;
- jumping reach.

The system also considers:

- physical distance to the shot segment;
- ball height;
- shot speed.

A blocked shot creates a real loose rebound location instead of automatically transferring possession.

---

## Goalkeeper reaction

The defending goalkeeper is identified from the active spatial lineup.

During a shot the goalkeeper receives a reaction target and can move through the same fixed-step player movement system.

Goalkeeper behaviour consumes dedicated goalkeeper attributes when available:

- reflexes;
- handling;
- one-on-ones;
- aerial reach;
- goalkeeper positioning.

Early fixtures that predate goalkeeper-specific data retain a backwards-compatible fallback based on existing mental/physical attributes.

Dedicated goalkeeper data should be used for real game content.

---

## Goalkeeper quality vs goalkeeper position

The model deliberately distinguishes these concepts.

Goalkeeper **position** can affect the quality of the chance itself. A completely stranded goalkeeper can make the goal more exposed.

Goalkeeper **ability** affects the later save resolution.

Therefore:

```text
same chance + same GK position
weak goalkeeper vs elite goalkeeper
→ same xG
→ different save probability
```

---

## Shot outcomes

Current outcomes are:

```text
GOAL
SAVED
PARRIED
BLOCKED
OFF_TARGET
WOODWORK
```

### Saved

The goalkeeper gains controlled possession.

### Parried

The ball becomes genuinely loose at a rebound location.

### Blocked

The defender deflects the ball into a loose spatial rebound.

### Off target

The shot misses the goal mouth. The later Match Flow layer will decide the correct restart.

### Woodwork

The ball rebounds into the field from the post/crossbar geometry.

### Goal

The shot result reports a goal. Scoreboard, kickoff reset and complete match flow are intentionally deferred to Phase 5.7.

---

## Determinism

All chance and shot randomness uses the match-owned seeded random source.

Therefore:

```text
same MatchSnapshot
+ same seed
+ same spatial setup
+ same action sequence
= same shot profile and outcome
```

Ball height is now also part of the deterministic `MatchState.signature()`.

---

## Scope boundary

Phase 5.6 does **not** yet implement:

- autonomous full-match action scheduling;
- score/half lifecycle;
- added time;
- extra time;
- penalty shootouts;
- throw-ins / corners / goal kicks as complete restarts;
- final match statistics aggregation;
- final event commentary.

Those belong to Phase 5.7 and later phases.

---

## Debug review

Run:

```powershell
$env:PYTHONPATH = "src"
python examples/demo_shooting_goalkeepers.py
```

The demo checks:

1. same chance with poor vs elite finishing;
2. xG changes caused by distance, angle and pressure;
3. goalkeeper quality separated from xG;
4. a real fixed-step shot flight and goalkeeper reaction;
5. a physical defensive block and header model.

---

## Automated validation

Phase 5.6 adds tests covering:

- shoot-decision validation;
- controlled possession detaching into a shot;
- fixed-step shot movement;
- contextual xG range;
- distance and angle effects;
- defensive pressure effects;
- blockers affecting chance quality;
- finishing quality separated from xG;
- shot power affecting real ball velocity rather than xG;
- header-specific execution;
- chance-origin effects;
- transition context;
- goalkeeper positional disadvantage;
- goalkeeper quality and save probability;
- physical goalkeeper reaction movement;
- shot blocks and rebounds;
- saves and controlled goalkeeper possession;
- parries and loose rebounds;
- goals;
- off-target shots;
- woodwork;
- home/away goal orientation;
- deterministic replay;
- ball height in deterministic state signatures.

Expected full suite after this phase:

```text
203 passed
```
