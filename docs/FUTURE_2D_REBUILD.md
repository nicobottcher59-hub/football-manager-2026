# Future 2D Match Engine Rebuild

## Status

This document defines the strategy for a **future** immersive 2D match engine.

The Phase 5.0-5.9 spatial engine is preserved as historical/experimental code but is frozen. It must not block development of competitions, seasons, transfers, scouting, contracts, finances or other management systems.

The current official match resolver is `FastMatchSimulator`.

## Product role

The intended match choice for the user's team is:

```text
Quick Sim
→ FastMatchSimulator

Watch / Manage in 2D
→ future 2DMatchEngineV2
```

All other fixtures in the world continue to use the Fast Simulator.

Both paths should consume the same conceptual kickoff boundary (`MatchSnapshot`) and return compatible match consequences so competition/calendar/world systems do not depend on engine internals.

## Why rebuild instead of extending the legacy engine

The previous attempt to add many collective-intelligence systems on top of an insufficient movement foundation created undesirable behaviour such as:

- player swarming around the ball;
- loss of positional structure;
- collisions / overlap;
- frozen ball carriers while choosing actions;
- visually unclear goals and transitions;
- tactical layers fighting each other instead of producing coherent football.

The rebuild therefore follows a strict rule:

> Do not add the next tactical/intelligence layer until the current layer is visually and statistically credible.

## Layered rebuild plan

### M1 — Movement Core

Build the physical foundation first:

- continuous 22-player movement;
- acceleration/deceleration;
- facing/body orientation;
- collision avoidance and personal space;
- no ball-carrier freezing during decisions;
- physical ball movement;
- first-control/body-orientation consequences;
- deterministic fixed-step simulation.

Exit criterion: players can move around the pitch without swarming, teleporting, overlapping or visibly freezing.

### M2 — Positional Structure

Add:

- formation reference points;
- in-possession/out-of-possession shapes;
- line spacing;
- width;
- strong/weak side;
- basic support distances;
- goalkeeper starting position.

Exit criterion: both teams preserve recognizable structure while reacting to ball location.

### M3 — Basic Possession

Add only the minimum coherent possession actions:

- receive/control;
- short/progressive pass;
- carry;
- simple off-ball support;
- switches of play;
- natural ball progression.

The carrier must remain mobile while evaluating options.

### M4 — Basic Defensive Shape

Add:

- pressure on the ball;
- cover and balance;
- zonal responsibility;
- distance between presser and support;
- compactness;
- simple marking/tracking.

Avoid “everyone chases the ball” behaviour.

### M5 — Transitions

Add:

- immediate reaction to turnovers;
- counterattack / recovery runs;
- counterpress versus regroup;
- second balls and rebounds;
- goalkeeper transition involvement.

### M6 — Roles

Layer positional roles on top of stable collective behaviour.

Roles are behavioural presets, not stat bonuses. They should affect movement and action preferences while preserving team structure.

### M7 — Manager Instructions

Consume the manager's tactical instructions explicitly:

- tempo;
- directness;
- pressing;
- defensive line/block;
- width;
- buildup;
- transition behaviour;
- crossing/overlap/underlap;
- player instructions.

Match-state behaviour should primarily come from manager instructions and decisions, not hidden automatic scoreline boosts.

### M8 — Advanced Collective Intelligence

Only after M1-M7 are stable, add:

- coordinated pressing responsibilities;
- strong-side overload / weak-side coverage;
- switches and rest defence;
- synchronized runs;
- advanced cover shadows;
- coordinated offside line;
- opponent-specific collective responses.

### M9 — Final Calibration

Use the existing calibration philosophy and tools to validate:

- goals vs xG;
- shots/SOT;
- fouls/cards/corners;
- pass completion;
- strength curve;
- upset rate;
- tactical ablations;
- performance;
- reproducibility.

Future 2D distributions should eventually be compatible with the same football world represented by the Fast Simulator, but the legacy 2D engine is **not** the calibration target.

## Advanced football behaviours to preserve for later layers

The rebuild should eventually support:

- body orientation and first control;
- offside and timing of runs;
- second balls / rebounds;
- active goalkeeper sweeping and distribution;
- goalkeeper starting position as tactical context;
- physical shot/pass/cross trajectories;
- individual decisions without freezing the carrier;
- natural carrying and dribbling;
- transitions that preserve team responsibilities.

## Condition and dynamic effectiveness

The shared condition model should be usable minute by minute in the future 2D engine.

Conceptually:

```text
pre-match ACT
+ live condition
+ live tactical / match context
→ internal current effectiveness
```

This value does not need to be shown directly. It exists so that:

- tired starters lose effectiveness;
- fresh substitutes matter;
- pressing has a physical cost;
- stamina differentiates players over 90/120 minutes;
- extra time produces severe physical asymmetries.

## Development rule

The future 2D engine is an immersion upgrade, not a dependency of the management game.

Every module must pass:

1. deterministic tests;
2. visual review;
3. behavioural invariants;
4. basic statistical calibration;

before the next layer is added.
