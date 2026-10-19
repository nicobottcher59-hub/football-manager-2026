> **LEGACY 2D ROADMAP — SUPERSEDED**
>
> This was the original roadmap for a single spatial engine serving 2D, commentary and instant results. That strategy was superseded after Phase 5.9. The current architecture uses `FastMatchSimulator` for Quick Sim and all non-user fixtures, while a future 2D engine will be rebuilt as an optional immersive mode for the user's match. Statements below such as “one simulation engine” or “no separate simplified simulation” are historical decisions and are **not current architecture**. See `FAST_SIM_AND_PLAYER_RATING_DESIGN.md` and `FUTURE_2D_REBUILD.md`.

# Phase 5 — Spatial Match Engine Roadmap

## Objective

Phase 5 introduces the first real match simulation engine.

The goal is to build a spatial, agent-based football simulation where the 22 players and the ball exist on a virtual 2D pitch. Tactics, roles, player attributes, familiarity, fitness, match context and controlled randomness must influence what happens on the pitch.

The engine must be independent from the final user interface.

The same simulated match must be usable by:

- a 2D match viewer;
- detailed text commentary;
- highlights;
- x1 / x2 / x4 playback;
- instant result.

Historical decision (superseded): there must never be a separate simplified simulation for instant results.

---

## Core principles

### One simulation engine (historical, superseded)

All viewing modes consume the same match simulation.

```text
MatchSnapshot
      ↓
Match Engine
      ↓
Match State + Event Stream
      ↓
2D / Commentary / Highlights / Instant Result
```

### Deterministic simulation

```text
Same MatchSnapshot
+ Same random seed
= Same match
```

Playback speed must never affect the result.

### Decision is separate from execution

A player can choose an action and fail to execute it.

Example:

```text
Instruction: Dribble frequently
Dribbling: 48
```

The player may attempt many dribbles, but lose a high percentage of them.

### Tactics modify behaviour, not player ratings

Tactical instructions must influence:

- positioning;
- movement;
- available space;
- action selection;
- pressing;
- defensive coverage;
- transition behaviour.

They must not apply artificial bonuses or penalties to player attributes or Overall.

### Player Overall remains unchanged

The engine should use the player's actual:

- technical attributes;
- mental attributes;
- physical attributes;
- positional familiarity;
- role familiarity;
- tactical familiarity;
- role suitability;
- fitness;
- fatigue;
- form;
- match context.

A bad tactical fit can reduce performance without changing the player's underlying quality.

### Match Engine does not mutate the persistent world

The Match Engine receives a MatchSnapshot and returns a MatchResult / Event Stream.

A separate WorldUpdater will later apply:

- fatigue;
- statistics;
- table changes;
- suspensions;
- injuries;
- form changes;
- other persistent consequences.

---

# Phase 5.0 — Spatial Core

Build the spatial foundation of the simulation.

### Scope

- 105 x 68 metre virtual pitch;
- 22 PlayerAgents;
- BallState;
- X/Y coordinates;
- player velocity and direction;
- match clock;
- fixed simulation timestep;
- deterministic random generator using the MatchSnapshot seed;
- mutable MatchState;
- initial player placement from formation;
- home and away orientation;
- basic possession state.

### Playback architecture

The engine always simulates with the same internal timestep.

Playback modes:

- x1;
- x2;
- x4;
- instant result.

Playback speed changes only how quickly the already-defined simulation is consumed or displayed.

### Definition of done

We can:

- create a MatchState from a MatchSnapshot;
- place 22 players correctly on the pitch;
- place the ball;
- advance the match clock;
- reproduce the same initial simulation state using the same seed.

---

# Phase 5.1 — Tactical Positioning

Make players occupy spaces according to the tactics already implemented.

### Scope

- base positions from formation;
- in-possession team shape;
- out-of-possession team shape;
- defensive, midfield and attacking width;
- distances between lines;
- block height;
- vertical compactness;
- protect-centre behaviour;
- role-based positional adjustments;
- inverted full-back movement;
- player transitions between attacking and defensive structures;
- individual positional instructions.

### Expected behaviour

Examples:

```text
High defensive width in possession
→ centre-backs and full-backs spread wider.
```

```text
Low defensive width out of possession
+ high protect-centre
→ defenders collapse centrally and concede more outside space.
```

### Definition of done

Changing tactical width, height or compactness must produce measurable spatial differences.

---

# Phase 5.2 — Perception & Decision Making

Players begin evaluating the match around them.

### Scope

Each PlayerAgent can evaluate:

- nearby teammates;
- nearby opponents;
- pressure;
- passing lanes;
- open space;
- goal direction;
- tactical instructions;
- positional responsibilities;
- available actions;
- action risk.

Possible actions initially include:

- short pass;
- progressive pass;
- long pass;
- carry;
- dribble;
- cross;
- shot;
- clearance;
- hold possession.

### Decision model

Conceptually:

```text
Action utility
=
tactical value
+ role preference
+ individual instruction
+ spatial opportunity
+ player decision quality
- risk
- opponent pressure
```

Action selection should be probabilistic rather than always choosing the numerically best option.

---

# Phase 5.3 — Passing & Possession

Implement real ball circulation.

### Scope

- short passes;
- progressive passes;
- long passes;
- pass target selection;
- ball travel;
- first touch;
- reception;
- bad control;
- misplaced passes;
- interceptions;
- possession changes;
- build-up patterns;
- pressure affecting passing difficulty.

### Principle

Passing attribute must not equal pass success percentage.

Pass difficulty must depend on:

- distance;
- angle;
- pressure;
- passing lane;
- movement of receiver;
- defenders;
- player technique;
- composure;
- decisions;
- fatigue;
- weather when applicable.

### Definition of done

The engine can produce coherent sequences of possession and turnovers.

---

# Phase 5.4 — Pressing & Defensive Duels

Add meaningful defending.

### Scope

- pressing targets;
- pressing intensity;
- defensive coverage;
- tackles;
- interceptions;
- anticipation;
- physical duels;
- pressing traps;
- successful and broken presses;
- possession recovery.

### Tactical consequences

Example:

```text
High press
→ more recoveries high up the pitch
→ greater risk if the press is bypassed
→ higher physical cost later
```

No artificial `high_press = +X defence` bonus.

---

# Phase 5.5 — Ball Progression

Expand attacking behaviour.

### Scope

- carries;
- dribbles;
- one-on-one duels;
- off-ball runs;
- through balls;
- overlaps;
- underlaps;
- wide attacks;
- inside movements;
- crosses;
- cutbacks;
- attacking space behind the defence.

### Individual instructions

Examples:

- dribble frequency;
- crossing frequency;
- attacking runs;
- move inside;
- stay wide;
- support defensive transition;
- press goalkeeper.

Player instructions influence action choice but not player attributes.

---

# Phase 5.6 — Chances, Shooting & Goalkeepers

Turn attacks into scoring opportunities.

### Scope

- shot selection;
- shot execution;
- shot location;
- shot angle;
- pressure;
- body part;
- blocks;
- goalkeeper positioning;
- saves;
- rebounds;
- goals;
- headers;
- xG.

### xG

xG should be generated from the actual simulated situation.

Possible inputs:

- distance;
- angle;
- defensive pressure;
- defenders blocking;
- goalkeeper position;
- type of assist;
- body part;
- transition speed;
- type of chance.

### Definition of done

The engine can create:

```text
chance
→ shot
→ xG
→ save / miss / block / goal
```

---

# Phase 5.7 — Match Flow

Convert isolated football actions into a full match.

### Scope

- kickoff;
- 90-minute match clock;
- first half;
- halftime;
- second half;
- stoppage time;
- throw-ins;
- goal kicks;
- corners;
- basic fouls;
- restarts;
- possession transitions.

The match should be able to finish without requiring user interaction.

---

# Phase 5.8 — Match Context

Connect the MatchSnapshot context to the simulation.

### Scope

- fitness;
- fatigue accumulation;
- weather;
- temperature;
- wind;
- pitch condition;
- home advantage;
- referee tendencies;
- fouls;
- cards;
- penalties.

### Principle

Context changes situations rather than player base ratings.

Examples:

```text
Strong wind
→ long passes and crosses become harder to execute consistently.
```

```text
Strict referee
+ aggressive tackling
→ greater foul/card risk.
```

---

# Phase 5.9 — Output & Playback

Expose one simulated match through multiple viewing modes.

### Event Stream

The engine should emit structured events such as:

```text
18:42 DRIBBLE
18:46 CROSS
18:48 SHOT
18:49 GOAL
```

### 2D viewer

A simple debug viewer should show:

- player positions;
- ball position;
- movement;
- team shapes;
- possession;
- match clock.

The first version may be visually crude.

### Text commentary

The same Event Stream can generate detailed commentary.

Example:

```text
15' Ferreyra commits a foul in midfield.
19' GOAL! Molina attacks the space and finishes across the goalkeeper.
27' Silva recovers possession on the left.
```

Commentary should be dense enough to make the match feel active.

Possible commentary densities:

- highlights only;
- normal;
- detailed.

### Playback modes

- x1;
- x2;
- x4;
- instant result.

All must produce the same simulated match for the same snapshot and seed.

### Possible combined view

Future UI can support:

```text
2D pitch + text commentary
```

simultaneously.

---

# Phase 5.10 — Calibration & Statistical Validation

After the engine can simulate complete matches, run large batches of simulations.

### Validate

- goals per match;
- shot counts;
- shots on target;
- xG distributions;
- possession;
- pass completion;
- dribbles;
- crosses;
- tackles;
- fouls;
- cards;
- home advantage;
- tactical effects;
- stronger vs weaker teams;
- upset frequency;
- extreme or impossible behaviours.

### Tactical validation examples

Run the same matchup hundreds or thousands of times while changing only one variable.

Example:

```text
protect_centre = LOW
vs
protect_centre = VERY_HIGH
```

Expected trend:

```text
VERY_HIGH
→ fewer central attacks conceded
→ more attacks through wide areas
→ more crosses conceded
```

Not necessarily more victories.

Another example:

```text
high defensive line
vs
low defensive line
```

against fast forwards.

Expected trend:

```text
High line
→ more advanced recoveries
→ more space attacked behind the defence
```

---

# Technical architecture target

```text
MatchSnapshot
      │
      ▼
MatchEngine
      │
      ├── MatchClock
      ├── RandomGenerator
      ├── SpatialState
      │     ├── 22 PlayerAgents
      │     └── BallState
      │
      ├── TacticalPositioning
      ├── PerceptionSystem
      ├── DecisionEngine
      ├── ActionResolver
      ├── ChanceEngine
      ├── xGEngine
      └── EventStream
              │
              ▼
          MatchResult
```

Later:

```text
MatchResult
    ↓
WorldUpdater
```

---

# Development rule

Every sub-phase must have observable and automated validation before moving to the next one.

Examples:

```text
5.0
→ 22 players placed correctly.

5.1
→ tactical width measurably changes player spacing.

5.3
→ coherent pass sequences and possession changes occur.

5.6
→ simulated attacks can produce shots, xG and goals.

5.7
→ full 90-minute matches complete successfully.

5.10
→ large-scale simulation produces plausible statistical distributions.
```

The objective is not merely to generate believable scorelines.

The objective is to generate believable football processes that naturally produce those scorelines.
