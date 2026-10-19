> **LEGACY 2D DOCUMENT — HISTORICAL / EXPERIMENTAL**
>
> This document describes the original spatial 2D implementation built in Phase 5.0-5.9. That engine is now frozen and is **not** the critical-path match resolver. Core game systems use `FastMatchSimulator`. Do not extend this phase as the basis for new management features. A future 2D mode will be rebuilt incrementally; see `FUTURE_2D_REBUILD.md`.

# Phase 5.3 — Passing & Possession

## Objective

Phase 5.3 connects the Phase 5.2 decision layer to real ball movement.

A player deciding to pass no longer means that possession is transferred instantly. The pass is now executed through the 2D spatial world and can succeed, be intercepted, miss its target, or reach a teammate who then fails to control it.

The central rule remains:

```text
decision != execution
```

A good decision can be executed badly, and a technically good passer can still fail under pressure or when attempting a difficult ball.

---

## Implemented

### Pass execution

The passing system currently executes:

- short passes;
- progressive passes;
- long passes.

Crosses remain a separate attacking action for Phase 5.5.

### Real ball travel

A pass has:

- origin;
- intended receiver;
- intended target point;
- actual target point;
- ball speed;
- expected travel time;
- execution error.

The ball moves through normal fixed 0.25-second simulation ticks. It does not teleport from passer to receiver.

### Execution quality

Pass execution quality currently consumes relevant player/context inputs such as:

- passing;
- technique;
- composure;
- vision;
- decisions;
- first touch as a small technical contribution;
- passer pressure;
- pass distance;
- pass type;
- frozen fitness/fatigue state.

This does not rewrite any player attribute or Overall value.

### Tactical pass speed

The team's effective `pass_speed` instruction changes actual ball velocity and therefore travel time.

Other passing preferences such as pass length, verticality and passing risk remain primarily decision-layer inputs from Phase 5.2: they change which passes the player wants to attempt rather than granting an execution bonus.

### Receiver lead

The target point can lead a moving receiver using the receiver's current spatial velocity. The first version is intentionally conservative and can be refined when off-ball runs become richer.

### Interceptions

Opponents physically close enough to the ball trajectory can attempt to intercept it before it reaches the target.

Interception currently considers spatial proximity and attributes including:

- anticipation;
- positioning;
- concentration;
- marking;
- agility;
- acceleration.

A successful interception immediately transfers controlled possession to the opponent.

This is only pass interception. Full pressing, tackling and defensive-duel behaviour belongs to Phase 5.4.

### First touch

Arrival and reception are separate from pass accuracy.

First-touch control currently considers:

- first touch;
- technique;
- composure;
- anticipation;
- balance;
- receiver pressure;
- incoming ball speed;
- pass execution quality.

Possible pass outcomes are:

```text
COMPLETED
INTERCEPTED
MISPLACED
BAD_CONTROL
```

A bad first touch leaves a loose ball instead of pretending the receiver automatically owns it.

### Possession state

During a pass:

```text
team possession = passer's team
individual owner = none
```

After resolution:

- completed pass -> receiving teammate controls the ball;
- interception -> opponent controls the ball;
- misplaced pass -> loose ball, no team has controlled possession;
- bad control -> loose ball after the receiver's failed touch.

### Multi-pass sequences

Completed passes can be chained into real possession sequences. Each new ball owner can perceive the new spatial state, choose another action, and attempt another pass.

---

## Determinism

Pass execution uses the match-owned seeded random source.

Therefore:

```text
same MatchSnapshot
+ same seed
+ same sequence of actions
= same pass profiles and outcomes
```

Playback chunking continues to use the same fixed-step simulation path.

---

## Debug review

Run:

```powershell
$env:PYTHONPATH = "src"
python examples/demo_passing_possession.py
```

The demo contains three intentionally simple scenarios:

1. an open two-pass possession sequence;
2. a progressive pass through a defender that can be intercepted in flight;
3. an extreme poor-first-touch case proving that reception can fail.

The demo is a diagnostic tool, not the final match viewer.

---

## Automated validation

Phase 5.3 adds tests for:

- ownership release while the ball is travelling;
- physical ball travel over multiple ticks;
- successful possession transfer;
- deterministic pass execution;
- pressure reducing execution quality;
- tactical pass speed changing real ball speed;
- receiver movement leading the pass target;
- spatial interceptions;
- possession flipping after interception;
- misplaced passes;
- failed first touches;
- first-touch probability exposure;
- different execution profiles for short/long passes;
- invalid pass execution requests;
- multi-pass possession sequences;
- fixed-timestep playback chunk independence during passes.

Expected complete test result after Phase 5.3:

```text
129 passed
```

---

## Deliberately not implemented yet

Phase 5.3 does **not** yet attempt to solve:

- pressing behaviour;
- tackles and physical defensive duels;
- advanced loose-ball battles;
- carries and dribbles;
- crosses/cutbacks;
- shooting;
- xG;
- goalkeeping actions;
- full match restarts;
- final Event Stream/commentary.

Those remain later Phase 5 responsibilities.

---

## Next step

Phase 5.4 — Pressing & Defensive Duels.

The next layer will make defenders actively influence possession through pressing, coverage, anticipation, tackles, physical duels and recovery rather than only reacting to a ball that passes through their interception radius.
