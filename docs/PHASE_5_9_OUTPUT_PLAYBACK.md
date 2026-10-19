> **LEGACY 2D DOCUMENT — HISTORICAL / EXPERIMENTAL**
>
> This document describes the original spatial 2D implementation built in Phase 5.0-5.9. That engine is now frozen and is **not** the critical-path match resolver. Core game systems use `FastMatchSimulator`. Do not extend this phase as the basis for new management features. A future 2D mode will be rebuilt incrementally; see `FUTURE_2D_REBUILD.md`.

# Phase 5.9 — Output & Playback

## Objective

Phase 5.9 exposes the same simulated match through presentation layers without changing Match Engine behaviour.

The goal is not to build the final game frontend. The goal is to create a functional debugging viewer that makes the spatial Match Engine inspectable before Phase 5.10 calibration.

The same `MatchFlowController` and fixed 0.25-second simulation timestep are used by every viewing mode.

```text
MatchSnapshot
      ↓
MatchFlowController
      ↓
MatchState + Event Stream
      ↓
PlaybackSession
      ├── 2D debug pitch
      ├── text commentary
      ├── statistics
      └── x1 / x2 / x4 / instant
```

## Core invariant

```text
Same MatchSnapshot
+ Same seed
+ Same engine version
+ Same manager interventions at the same simulation ticks
= Same match
```

Playback speed changes only how many fixed simulation ticks are consumed between presentation refreshes.

It does not change:

- the simulation timestep;
- random-number order;
- decisions;
- execution;
- events;
- score;
- statistics.

Instant result does not use a simplified result generator. It consumes the same Match Engine without waiting for presentation frames.

## MatchPlaybackSession

`football_manager.presentation.MatchPlaybackSession` wraps the existing match-flow controller for presentation use.

Supported relative speeds:

- `x1`;
- `x2`;
- `x4`.

The debug viewer uses x1 as its baseline presentation rate. x2 and x4 consume two/four times as many fixed ticks per UI pulse.

After visual review, x1 is intentionally presentation-compressed: one fixed 0.25-second simulation tick is normally consumed every 25 ms of UI time. A regulation match therefore takes roughly nine real minutes at x1, about half that at x2 and roughly a quarter at x4. This changes presentation throughput only; the engine still simulates every 0.25-second tick.

`run_instant()` repeatedly consumes the same fixed-step simulation as quickly as possible.

## Statistics

`MatchStatisticsTracker` derives live statistics from the same state/event stream.

Current presentation statistics include:

- possession;
- passes attempted/completed;
- shots;
- shots on target;
- xG;
- goals;
- saves;
- tackles;
- recoveries;
- dribbles;
- crosses;
- fouls;
- yellow/red cards;
- corners.

Statistics are output-only. They never feed values back into the Match Engine.

Shot-start events now expose contextual xG metadata so the presentation layer can accumulate xG without reconstructing or changing shot logic.

Penalty-shootout kicks are deliberately excluded from normal match shot/xG statistics.

## Text commentary

Structured match events are translated into deterministic Spanish commentary.

Available densities:

- `Solo destacados`;
- `Normal`;
- `Detallado`.

Important events are surfaced directly:

- goals;
- shots;
- saves;
- blocks;
- woodwork;
- cards;
- penalties;
- match-period transitions.

Routine possession events are deterministically sampled according to the selected density so the feed stays active without printing every single engine event.

Commentary can include:

- completed/intercepted/misplaced passes;
- recoveries;
- carries;
- dribbles;
- crosses;
- tackles;
- fouls;
- corners/free kicks;
- goals and shot outcomes.

Commentary wording is derived from actual structured events. It does not invent football actions that were not simulated.

## 2D debug viewer

Run:

```powershell
$env:PYTHONPATH = "src"
python examples/demo_match_viewer.py
```

The viewer provides:

- live score;
- official match time;
- 2D pitch;
- player positions;
- ball position/height;
- possession highlight;
- text commentary;
- live statistics;
- play/pause;
- x1/x2/x4;
- instant result;
- restart using the same snapshot/seed;
- start a new deterministic simulation with a new seed;
- substitutions and live tactical adjustments;
- `2D`, `Texto` or `Ambas` viewing modes;
- commentary-density selector.

The GUI uses Python's standard `tkinter` package, so no new project dependency is required.


## Headless playback check

A short non-GUI demo is also available:

```powershell
$env:PYTHONPATH = "src"
python examples/demo_output_playback.py
```

It compares x1/x2/x4/instant output for the same snapshot/seed and prints a commentary/statistics sample. Its periods are intentionally shortened for quick orchestration checks; it is not a statistical realism demo.

## Debug overlays

The viewer can inspect internal spatial behaviour with optional overlays:

- tactical targets;
- active pressers and approach targets;
- defensive coverage targets;
- best perceived passing lanes;
- team-shape convex hulls;
- player coordinates.

These overlays are presentation-only and have no effect on simulation.

They exist specifically to find issues such as:

- full-backs moving to incorrect tactical spaces;
- excessive team width/compactness;
- pressers approaching from the wrong side;
- coverage leaving impossible gaps;
- passing lanes not matching spatial reality;
- players jumping/teleporting between states.

## Integrated-match stabilization after first visual review

The first real 2D/text review exposed integration problems that isolated subsystem tests could not show. The initial viewer could emit too many actions, keep tactical blocks pinned close to their original halves while the event layer still described attacks, over-produce fouls/cards and create excessive added time.

The Phase 5.9 stabilization pass therefore adds integration constraints instead of treating those symptoms as presentation-only issues:

- team tactical targets travel longitudinally and laterally with the live ball so both sides can cross midfield and occupy the final third;
- pass receivers physically move toward the intended receiving point while the ball is in flight;
- live actions use a human-scale decision cadence rather than allowing a new decision every fixed 0.25-second tick;
- repeated tackle attempts have recovery windows and foul checks only occur after a defender actually commits to a challenge;
- card probabilities are reduced to provisional match-scale values;
- open-play crosses require an advanced wide origin and choose attacking/midfield runners instead of defaulting to centre-backs;
- action events carry the actor's current X/Y coordinates so shots/crosses can be audited against the spatial state;
- regulation added time remains interruption-derived, with a high safety cap, while the official display never runs beyond the amount announced because of fixed-tick overrun;
- detailed commentary samples routine pass/control/recovery events rather than printing every engine micro-event;
- the debug playback baseline consumes several fixed ticks per UI refresh, making x1 watchable without changing the internal 0.25-second simulation step.

Reference-seed integration tests now guard against the regressions found in that first visual review: action density, final-third occupation, spatial shot/cross origins, added-time display, systemic red cards and inappropriate cross targets.

## Organic movement overhaul after second visual review

The second visual review showed a deeper issue: players could cross midfield, but they still behaved too much like pieces attached to formation rows. The ball owner and immediate defender were active while many other players looked passive or returned too quickly to positional targets.

Phase 5.9 therefore gained a dedicated `OrganicMovementSystem` for every active off-ball player.

The core rule is:

```text
formation / role position = structural reference
current movement intention = what the player is actually doing now
```

Current persistent intentions include:

- hold structure;
- support the ball;
- offer a passing lane;
- drop to receive;
- run in behind;
- attack the box;
- hold width;
- move inside;
- overlap / underlap;
- invert;
- drop between centre-backs;
- step into free build-up space;
- cover space;
- track a runner;
- recover shape.

Intentions normally persist for several simulated seconds. Players accelerate, turn and decelerate into those trajectories rather than being assigned a fresh full-speed vector toward a formation coordinate every tick.

Movement is also relational. Examples:

- a dropping pivot encourages the centre-backs to fan out;
- a winger moving inside increases the value of a full-back overlap;
- an attacking full-back normally encourages the opposite full-back to balance behind play;
- a dropping striker increases the value of depth runs from wingers/interiors;
- one attacking interior increases the probability that another midfielder balances the possession;
- defenders can hand over runners while preserving connection to the line.

The attacking decision layer consumes those movements. A real run can raise the spatial value of a progressive/long pass, and pass execution leads a moving receiver rather than aiming only at a static coordinate. Long passes now have visible aerial height.

The intention overlay shows these live targets/reasons in the viewer so movement can be audited directly.

## In-match manager intervention

The debug viewer can now alter the live match without rebuilding the immutable kickoff snapshot.

Supported debug controls include:

- substitutions from the bench;
- substitutions requested during live play and applied at the next natural stoppage;
- team tactical plans;
- live formation changes that preserve runtime slot IDs;
- tempo, verticality, passing-risk, pressing, block-height and defensive-line adjustments;
- role changes for a selected slot;
- individual forward-run, dribbling, crossing and passing-risk instructions.

Runtime formation/role changes recalculate position familiarity, role familiarity, tactic familiarity and role suitability from the player's existing data. They never rewrite player attributes.

The stronger determinism rule is therefore:

```text
Same MatchSnapshot
+ Same seed
+ Same manager actions at the same simulation ticks
= Same continuation
```

`Reiniciar` intentionally reuses the same seed. `Nueva seed` starts a different deterministic simulation.

## Presentation time behaviour

Half-time and final-whistle screens preserve the last official time label instead of visually jumping back to `0'`.

Examples:

```text
45+3'
90+4'
PEN
```

## Definition of done

Phase 5.9 is complete when:

- x1/x2/x4/instant produce identical matches for the same snapshot/seed;
- text commentary is generated only from real events;
- detailed commentary produces a dense match feed;
- live statistics are derived without affecting simulation;
- the 2D viewer can display a running match;
- debug overlays expose tactical/spatial internals;
- active off-ball players move from persistent football intentions rather than rigid formation rails;
- coordinated rotations can mix positional lines while keeping a coherent team structure;
- the user can switch between 2D, text and combined views;
- all automated tests remain green;
- both teams can spatially enter the opposition half/final third in integrated play;
- match-scale action density is bounded;
- substitutions and tactical changes are consumed by the live engine.

## What is intentionally not final

This viewer is not the final game interface.

Phase 5.9 does not attempt to deliver:

- final visual design;
- real club assets;
- polished kits/player models;
- stadium rendering;
- broadcast-quality animation;
- final frontend architecture;
- final Match Engine calibration.

Those would be premature before Phase 5.10 validates and calibrates match behaviour at scale.
