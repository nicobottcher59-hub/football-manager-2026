> **LEGACY 2D DOCUMENT — HISTORICAL / EXPERIMENTAL**
>
> This document describes the original spatial 2D implementation built in Phase 5.0-5.9. That engine is now frozen and is **not** the critical-path match resolver. Core game systems use `FastMatchSimulator`. Do not extend this phase as the basis for new management features. A future 2D mode will be rebuilt incrementally; see `FUTURE_2D_REBUILD.md`.

# Phase 5.8 — Match Context

## Objective

Phase 5.8 connects the frozen pre-match context in `MatchSnapshot` to live match behaviour.

Weather, pitch, current fatigue, home context and referee tendencies now affect concrete situations without rewriting player base attributes or Overall.

The central rule remains:

```text
context changes the situation
!=
context changes the player
```

A player with Passing 70 remains a Passing 70 player. A waterlogged pitch, strong wind, pressure or fatigue can make a specific 30-metre pass harder to execute, but the underlying attribute is unchanged.

---

## Runtime player condition

`PlayerMatchSnapshot.state` remains immutable.

Each `PlayerAgentState` now keeps live match values for:

- `current_fitness`;
- `current_fatigue`;
- yellow-card count;
- dismissal state.

The live condition starts from the frozen pre-match snapshot and evolves only inside the simulation.

Fatigue cost consumes:

- current movement/exertion;
- stamina;
- natural fitness;
- temperature;
- humidity;
- pitch condition;
- playing surface.

A moving player therefore tires faster than a stationary player, and demanding environmental conditions increase the physical cost.

`MatchResult` exposes final condition and discipline data so a future `WorldUpdater` can decide how to persist post-match consequences.

---

## Weather, pitch and surface

Context is consumed by the systems that need it rather than by one global rating modifier.

### Player movement

Movement can be affected by:

- wet/heavy/waterlogged pitches;
- rain, storms and snow;
- surface type;
- accumulated fatigue;
- remaining fitness.

### Ball behaviour

Ground-ball speed reacts to pitch/surface conditions.

Examples:

```text
wet pitch
-> ball can skid slightly faster
```

```text
heavy / waterlogged pitch
-> ball loses more speed
```

Long or aerial actions receive additional uncertainty in strong wind.

The current snapshot stores wind speed but not wind direction. Phase 5.8 therefore models wind as increased long/aerial uncertainty instead of inventing a directional drift that the source data does not contain.

### Technical execution

Rain, pitch condition, wind and fatigue can affect the execution context for passes, crosses and shots.

First-touch difficulty also reacts to wet/heavy conditions and fatigue.

### Perception

Severe visibility conditions such as fog, storms or heavy rain reduce the useful awareness radius used by the perception layer.

---

## Home context

Home advantage is intentionally small and situational.

It does **not** modify:

- Overall;
- technical attributes;
- mental attributes;
- physical attributes.

The current model gives the home side a small pressure-resilience effect only when executing under pressure.

There is no unconditional home rating bonus and no guarantee of better results.

The exact strength remains provisional until Phase 5.10 calibration.

---

## Referee model

`RefereeSnapshot` tendencies are now consumed during live foul decisions:

- `strictness`;
- `contact_tolerance`;
- `card_tendency`;
- `penalty_tendency`;
- `advantage_tendency`.

Foul assessment also consumes football context such as:

- defender aggression;
- team defensive aggression;
- tackling quality;
- defender fatigue;
- distance to the opponent;
- attacking progress;
- penalty-area location.

The result is a contextual foul assessment rather than a guaranteed foul from a tackle attempt.

---

## Cards and dismissals

Supported discipline outcomes:

- yellow card;
- second yellow + red;
- direct red.

A dismissed player is not deleted from the match record. Their `PlayerAgentState` remains available for identity/statistics/history, but `is_active` becomes false.

Inactive/dismissed players are excluded from live participation including:

- tactical positioning;
- perception;
- pressing and defensive coverage;
- passing/receiving;
- ball progression;
- shooting;
- loose-ball collection.

This means a red card has a real spatial consequence: the team continues with fewer active players.

---

## Advantage

The referee can allow advantage when the attacking context supports it.

Advantage probability depends on referee tendency and attacking progress.

Advantage is disabled for:

- penalty-area fouls;
- direct-red situations;
- second-yellow dismissals.

---

## In-match penalties

A foul assessment detects whether the foul location lies inside the attacking penalty area for either pitch orientation.

A penalty-area foul can emit:

```text
FOUL
-> PENALTY_AWARDED
-> PENALTY_KICK
-> GOAL or SAVE
```

Penalty award and penalty conversion are separate decisions.

A referee's `penalty_tendency` influences the foul-call bias in the area; it does not alter the taker's attributes.

---

## Integration with existing systems

Phase 5.8 context is shared by the existing Match Engine systems.

```text
MatchSnapshot context
        |
        v
MatchContextSystem
        |
        +--> Tactical positioning / movement
        +--> Perception
        +--> Passing / first touch
        +--> Pressing / defending
        +--> Carries / dribbles / crosses
        +--> Shooting / goalkeeper movement
        +--> Match flow / fouls / cards / penalties
```

The Match Engine continues to use one deterministic random source and one fixed internal timestep.

---

## Validation

Phase 5.8 automated tests cover, among other cases:

- live fatigue vs frozen snapshot condition;
- moving vs stationary fatigue cost;
- hot/humid/heavy-pitch fatigue;
- pitch effects on player and ball speed;
- wind effects on long/aerial uncertainty;
- fog effects on awareness;
- first-touch context;
- situational home pressure resilience;
- referee strictness/contact tolerance;
- card tendency;
- advantage tendency;
- penalty-area detection in both attacking directions;
- penalty tendency;
- second-yellow dismissal;
- direct-red removal from active perception;
- in-match penalty events;
- final condition/discipline data in `MatchResult`;
- deterministic runtime context progression.

Current full-suite result after Phase 5.8:

```text
256 passed
```

---

## Calibration note

The architecture and causal direction are part of Phase 5.8.

The exact numerical strengths are **not** considered final yet.

Examples that remain calibration targets for Phase 5.10:

- fatigue rates;
- weather penalties;
- wind sensitivity;
- home-context strength;
- foul rates;
- yellow/red-card rates;
- penalty frequency;
- advantage frequency.

Those values must later be evaluated across large batches of complete matches rather than tuned from one isolated example.
