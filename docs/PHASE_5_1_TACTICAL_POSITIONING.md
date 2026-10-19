> **LEGACY 2D DOCUMENT — HISTORICAL / EXPERIMENTAL**
>
> This document describes the original spatial 2D implementation built in Phase 5.0-5.9. That engine is now frozen and is **not** the critical-path match resolver. Core game systems use `FastMatchSimulator`. Do not extend this phase as the basis for new management features. A future 2D mode will be rebuilt incrementally; see `FUTURE_2D_REBUILD.md`.

# Phase 5.1 - Tactical Positioning

## Goal

Phase 5.1 makes the 22 spatial agents react to the frozen tactical plan inside the
actual Match Engine.

The phase still does **not** choose passes, simulate pressure duels, create shots
or decide match results. Its responsibility is spatial: calculate where every
player should try to be and move them smoothly toward that target.

This is the first phase where tactical settings produce measurable behaviour on
the virtual pitch.

---

## Tactical phases

Each team is always interpreted relative to current possession:

```text
team has possession     -> IN_POSSESSION shape
opponent has possession -> OUT_OF_POSSESSION shape
```

When possession changes, the target shape changes immediately, but players do not
teleport. They travel toward the new target using the fixed-step movement system.

---

## Team shape consumers

### In possession

The positioning system currently consumes:

- defensive-line width;
- midfield width;
- attacking-line width;
- defence-to-midfield gap;
- midfield-to-attack gap.

This means a tactical instruction such as:

```text
wide defensive line with the ball
```

creates a measurably wider first build-up line rather than a hidden statistical
bonus.

### Out of possession

The system currently consumes:

- defensive-line width;
- midfield width;
- attacking-line width;
- block height;
- defensive-line height;
- horizontal compactness;
- vertical compactness;
- defence-to-midfield gap;
- midfield-to-attack gap;
- protect centre;
- cross tolerance.

A setup such as:

```text
narrow defensive width
+ very high central protection
+ high cross tolerance
```

therefore collapses the defensive shape toward central areas and leaves more
space outside.

Later match-engine phases will determine how opponents exploit that space and how
many actual crosses or central progressions occur.

---

## Role and individual positional behaviour

Phase 5.1 starts consuming effective player instructions from the frozen
`MatchSnapshot`.

Supported spatial behaviours include:

- `WIDE`;
- `INSIDE`;
- `MIDFIELD`;
- `ADVANCE`;
- `DROP_DEEP`;
- `STEP_UP`;
- `DROP`;
- forward-run intensity;
- defensive tracking for attacking players.

Examples:

```text
Inverted Full-Back
-> moves inside and toward midfield with possession.
```

```text
Covering Defender
-> holds a deeper defensive target.
```

```text
Defensive Winger
-> recovers closer to midfield without the ball.
```

Role names themselves do not give bonuses. The engine consumes the effective
instructions created by the role preset plus user overrides.

---

## Tactical familiarity and movement

Tactical target location and the player's ability to reach that target are kept
separate.

The target is defined by the tactical plan.

The bounded repositioning speed is influenced by:

- player pace;
- player acceleration;
- positional familiarity;
- role familiarity;
- tactical familiarity.

This does not modify the player's attributes or Overall. A less familiar player
simply reorganizes more slowly inside the tactical structure.

This is an early spatial use of familiarity; future decision/action phases will
use familiarity in additional ways.

---

## Movement and transitions

Every tick:

```text
1. Determine possession phase.
2. Calculate tactical target for each player.
3. Calculate bounded movement velocity toward the target.
4. Advance the normal fixed 0.25-second spatial timestep.
```

Arrival speed is capped so players do not overshoot targets.

Manual/debug velocity overrides remain supported so Phase 5.0 movement tests and
future debugging tools can directly control an agent when necessary.

---

## Home / away orientation

Tactical targets are calculated from a home-perspective coordinate system and
then mirrored for the away team.

This preserves the global convention:

```text
HOME attacks toward +X
AWAY attacks toward -X
```

Equivalent home/away tactical positions are therefore geometric mirrors.

---

## Tactical shape metrics

The positioning system exposes measurable shape metrics for a team:

- defensive width;
- midfield width;
- attacking width;
- defence-midfield gap;
- midfield-attack gap.

These metrics are intentionally useful for automated validation and future
calibration.

We can test statements such as:

```text
VERY_HIGH defensive width > VERY_LOW defensive width
```

instead of relying only on visual judgement.

---

## Debug visualization

A deliberately crude ASCII tactical-pitch renderer was added for engine
development.

Run:

```powershell
python examples/demo_tactical_positioning.py
```

The demo shows the same home team:

1. with the ball, using a wide build-up structure and an inverted full-back;
2. without the ball, using a narrow compact block that protects the centre;
3. transitioning toward the new defensive target without teleporting.

This is not the final match viewer. It is a debugging surface used to validate
football logic before frontend work.

---

## Automated validation

Phase 5.1 adds tests for:

- possession phase assignment;
- attacking defensive-line width;
- central-protection narrowing;
- block-height movement;
- vertical compactness;
- in-possession inter-line gaps;
- inverted full-back positioning;
- defender step-up/drop instructions;
- winger defensive tracking;
- smooth possession-phase transitions;
- home/away target mirroring;
- pitch-bound target clamping;
- familiarity-dependent reposition speed;
- ASCII debug rendering.

Expected project result after Phase 5.1:

```text
92 passed
```

---

## Not implemented yet

Phase 5.1 deliberately does not implement:

- perception;
- action utility;
- decision making;
- pass selection;
- passing trajectories;
- pressing duels;
- interceptions;
- tackles;
- dribbling;
- crosses as ball actions;
- shots;
- xG;
- goals;
- match commentary;
- final 2D frontend animation.

The players now know **where they should be**. They do not yet decide **what to do
with the football**.

---

## Next step

Phase 5.2 - Perception & Decision Making.

The next phase will allow PlayerAgents to inspect their spatial context and build
a set of possible football actions based on:

- teammates;
- opponents;
- pressure;
- passing lanes;
- open space;
- tactical responsibilities;
- player attributes;
- risk.

That will establish the decision layer required before real passing and
possession logic in Phase 5.3.
