# Phase 5.11B - Fast Match Simulator MVP

## Objective

Introduce an instant match-resolution path that can simulate league/cup fixtures without creating 2D agents, spatial state or fixed simulation ticks.

The Fast Match Simulator is now the critical-path match engine for future competition and season systems.

The existing 2D engine remains available as legacy/experimental code, but Phase 5.11B does not import or execute it.

## Architectural boundary

The simulator consumes the existing immutable:

```text
MatchSnapshot
```

and produces a compact fast-simulation result:

```text
FastMatchResult
```

The implementation lives under:

```text
football_manager.fast_simulation
```

That package has no dependency on:

```text
football_manager.simulation
SpatialMatchEngine
MatchFlowController
```

This lets future calendar/competition code resolve large numbers of fixtures without depending on 2D internals.

A shared outer match-result contract can be extracted later when the rebuilt 2D path returns to active development. Phase 5.11B deliberately avoids refactoring the frozen 2D engine just to force both implementations into the same concrete class today.

## Core philosophy

The Fast Match Simulator must never perform:

```text
team rating comparison
-> choose winner
-> invent statistics afterwards
```

Instead, quality and context define probability distributions.

The result emerges from compact football processes:

```text
team/player quality
+ current effective performance
+ tactical execution
+ tactical interaction
+ home context
+ possession/control
+ chance volume
+ chance quality
+ finishing
+ goalkeeping
+ discipline
+ controlled randomness
```

An inferior team therefore remains capable of winning because randomness is applied inside football events rather than as an explicit "upset roll".

## Team profile

Each starting XI is converted into a compact `FastTeamProfile`.

The profile includes:

- average OVR;
- average ACT/current rating;
- attack;
- midfield/control;
- defense;
- goalkeeping;
- set pieces;
- discipline;
- tactical execution;
- possession style;
- pressing;
- directness;
- defensive depth;
- tempo;
- width;
- risk;
- defensive compactness;
- cross tolerance;
- crossing frequency;
- defensive aggression.

Unit strengths are not calculated from OVR alone.

They combine the player's frozen `current_rating` with the attributes relevant to that football function. Positional weighting determines how strongly each starter contributes to attack, control and defense.

## OVR and ACT use

`OVR` remains the stable summary of underlying player quality.

`ACT` remains the contextual expression of that quality at kickoff.

The Fast Match Simulator primarily consumes the frozen lineup-context `current_rating` together with action-specific attributes.

This preserves the design rule:

```text
better footballer
!=
automatically better performance in every current context
```

## Tactical influence

Tactics alter specific match processes rather than providing a universal hidden bonus.

Examples in the MVP:

- possession orientation affects expected possession and passing volume;
- directness and tempo affect passing/chance volume;
- pressing interacts with opposing possession style;
- directness interacts with opposing defensive depth;
- width interacts with defensive compactness;
- crossing frequency influences corner volume;
- defensive aggression/pressing influence foul volume.

Tactical effects are scaled by tactical execution/familiarity, so instructions that a team barely understands are not expressed at full strength.

This is intentionally an MVP interaction layer. Phase 5.11C will calibrate magnitude and future phases can add richer matchup consumers.

## Chance and goal process

The simulator does not sample a final score directly.

For each team it first generates chance volume from a probability distribution.

Each shot then receives:

- a shooter selected from the actual XI;
- an xG/chance-quality value;
- an on-target outcome;
- a goal outcome.

Goal probability is based primarily on chance quality, with bounded finishing and goalkeeper modifiers.

This preserves the separation between:

```text
chance creation
finishing
goalkeeping
```

and keeps aggregate goals anchored near aggregate xG instead of using a fixed conversion rate.

## Randomness

`FastMatchRandom` owns all fast-simulation randomness.

It supports deterministic named substreams.

Examples:

```text
possession
home/shots/regulation
away/shots/regulation
home/non_shot
away/non_shot
penalty_shootout
player ratings
```

Therefore:

```text
same MatchSnapshot + same seed + same Fast Simulator version
= same result
```

Adding an unrelated random call to one namespace should not reorder every other subsystem.

## Generated result

`FastMatchResult` currently exposes:

- score;
- aggregate score;
- winning club when applicable;
- regulation/draw/extra-time/penalty decision;
- penalty-shootout score;
- goal events;
- scorer;
- assist;
- shot xG for each goal;
- card events;
- team statistics;
- individual player statistics.

Team statistics include:

- possession;
- passes attempted/completed;
- shots;
- shots on target;
- xG;
- goals;
- saves;
- fouls;
- yellow cards;
- red cards;
- corners.

Starter statistics include:

- minutes;
- goals;
- assists;
- shots;
- shots on target;
- xG;
- passes attempted/completed;
- fouls;
- cards;
- match rating;
- estimated post-match condition.

## Competition resolution

The MVP respects the competition `MatchDecider` already frozen in `MatchSnapshot`.

Supported paths:

```text
DRAW_ALLOWED
EXTRA_TIME_AND_PENALTIES
PENALTIES_AFTER_90
```

Extra-time goals are generated through the same shot process at reduced period length.

Penalty shootouts resolve individual kicks from penalty/composure quality against goalkeeper quality. The simulator never performs a direct random "choose winner" operation.

Existing cup aggregate context is also respected.

## Performance

The simulator does not create spatial agents and does not step through 0.25-second ticks.

The Phase 5.11B demo includes a 1000-match batch benchmark. On the development environment the MVP processes hundreds of complete matches per second.

Exact performance budgets will be formalized after integration with competitions and season simulation.

## Initial distribution sanity check

Phase 5.11B uses broad guardrails only. It is not the final calibration phase.

The reference equal-team batch is currently around:

```text
goals      ~2.9 per match
shots      ~25 total
SOT        ~9 total
xG         ~2.9 total
fouls      ~23 total
yellows    ~3.4 total
corners    ~9-10 total
```

These values are intentionally validated with wide automated ranges.

Phase 5.11C will perform the real large-sample calibration of:

- H/D/A distribution and home advantage;
- goal/xG relationship;
- shot and chance distributions;
- strength curves;
- upset frequency;
- tactical effect magnitude;
- disciplinary distributions;
- individual-stat distributions;
- speed at season-scale workloads.

## Deferred from this MVP

Not yet implemented in the Fast Simulator:

- substitutions;
- injuries;
- detailed in-match state changes;
- minute-by-minute tactical changes;
- persistent post-match world mutation;
- chemistry system beyond the ACT snapshot input;
- advanced tactical matchup library;
- full individual action/event log.

These should be added only when required by the wider game loop.

## Tests

Phase 5.11B adds tests for:

- same-seed determinism;
- different-seed variability;
- score/statistical invariants;
- team/player-stat reconciliation;
- valid scorers and assists;
- immutable MatchSnapshot behavior;
- no dependency on the spatial 2D engine;
- broad football-like batch distributions;
- stronger-team advantage with surviving upsets/draws;
- measurable tactical possession effects;
- penalty-decider support.

Expected complete suite after this phase:

```text
350 passed
```

## Next step

Phase 5.11C - Fast Simulator Calibration.

The next phase should run large deterministic batches against explicit target distributions and tune the simulator without reintroducing the 2D engine into the critical path.
