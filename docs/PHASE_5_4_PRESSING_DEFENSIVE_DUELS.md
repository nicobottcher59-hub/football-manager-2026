> **LEGACY 2D DOCUMENT — HISTORICAL / EXPERIMENTAL**
>
> This document describes the original spatial 2D implementation built in Phase 5.0-5.9. That engine is now frozen and is **not** the critical-path match resolver. Core game systems use `FastMatchSimulator`. Do not extend this phase as the basis for new management features. A future 2D mode will be rebuilt incrementally; see `FUTURE_2D_REBUILD.md`.

# Phase 5.4 — Pressing & Defensive Duels

## Objective

Phase 5.4 makes the defending team actively affect the spatial match instead of only waiting for a pass to cross an interception radius.

The engine now separates three defensive concepts:

```text
pressing intent / movement
        ↓
defensive coverage
        ↓
physical duel resolution
```

A team asking for aggressive pressing therefore moves players differently, but it does not receive an artificial defensive-stat bonus.

---

## Active pressing

When one player has controlled possession, the defending side builds a spatial pressing plan around the real ball carrier.

The plan can contain:

- a primary presser;
- additional supporting pressers;
- defensive coverage assignments behind/around the press.

The number, radius and speed of active pressers consume the actual tactical configuration.

### Team pressing intensity

`pressing_intensity` changes real defensive behaviour.

Higher settings can produce:

- a larger engagement radius;
- more simultaneous pressers;
- faster closing movement.

Lower settings preserve more of the base defensive shape and normally commit fewer players.

This is spatial behaviour, not `+X defending`.

### Pressing schemes

The first implementation consumes the existing schemes as behavioural modifiers.

Examples:

- `STANDARD` — normal pressure selection;
- `ZONAL` — more conservative commitment;
- `CONSTANT` — wider/more numerous pressure commitment;
- `TRAP_INSIDE` — pressure angle attempts to shepherd the carrier inside;
- `TRAP_OUTSIDE` — pressure angle attempts to shepherd the carrier outside;
- `MAN_ORIENTED` — gives more weight to direct player-oriented pressure.

These can be refined further during calibration without changing the public tactical model.

### Individual pressing instructions

Effective player instructions are also consumed.

`pressing_intensity` influences that player's pressing priority and closing speed.

A specific `pressing_target` can increase priority when the current ball carrier matches the requested:

- player;
- position;
- role.

---

## Force direction

Pressure is no longer always a straight chase toward the exact centre of the ball carrier.

The engine generates an approach point around the carrier.

Current behaviours include:

- neutral;
- force inside;
- force outside;
- weak-foot orientation foundation.

For example:

```text
Force outside
→ presser approaches from the central side
→ carrier is spatially encouraged toward the touchline
```

This does not guarantee what the attacker will do. Future carry/dribble decisions still decide whether the attacker obeys, resists or beats the pressure.

---

## Defensive coverage

Players not selected as active pressers can receive coverage targets.

Coverage currently consumes:

- team marking style;
- individual defensive tracking;
- explicit marking targets;
- current opponent locations;
- the defender's existing tactical target.

The final target blends the base tactical shape with a goal-side marking point.

### Marking styles

Current relative behaviour:

```text
ZONAL
→ stays closer to tactical zone

MIXED
→ stronger blend toward opponent

MAN
→ tracks opponent more tightly
```

An explicit individual marking target receives stronger player-oriented coverage.

Coverage never changes the player's marking attribute.

---

## Defensive movement

Pressing and coverage modify real `PlayerAgentState.velocity` values.

During each normal fixed simulation tick:

```text
base tactical positioning
        ↓
pressing / coverage overrides where required
        ↓
normal 0.25 s spatial movement integration
```

There is no teleportation.

Manual debug velocity overrides remain respected.

When a player is no longer selected to press or cover, normal tactical positioning naturally pulls him back toward the team shape. This is the first recovery-behaviour foundation.

---

## Defensive duels

Tackle resolution is separate from the desire to press.

A defender must first be physically close enough to a controlled opposing ball carrier.

The duel profile currently evaluates relevant inputs including:

### Defender

- tackling;
- anticipation;
- decisions;
- positioning;
- bravery;
- strength;
- balance;
- acceleration.

### Ball carrier

- dribbling;
- technique;
- first touch;
- composure;
- decisions;
- agility;
- balance;
- strength.

### Spatial context

- challenge distance;
- whether the defender is goal-side / in front of the attack;
- nearby defensive support.

---

## Defensive aggression vs tackle quality

The tactical `defensive_aggression` setting influences **tackle willingness**, not the player's underlying defensive ability.

Conceptually:

```text
high defensive aggression
→ more willingness to commit

high tackling / anticipation / positioning
→ better chance of executing the duel successfully
```

This preserves the project's central rule:

```text
tactical instruction != attribute bonus
```

Automatic full-match scheduling of when to commit to a tackle will consume this willingness later as the complete match-flow loop is assembled. Phase 5.4 already exposes and tests the value separately from execution quality.

---

## Duel outcomes

A successful defensive challenge does not automatically teleport possession to the defender.

Current outcomes are:

```text
DEFENDER_CONTROL
ATTACKER_RETAINS
LOOSE_BALL
```

### Defender control

The defender wins the challenge and controls the ball.

Possession flips to the defending team.

### Attacker retains

The tackle fails and the existing ball carrier keeps control.

### Loose ball

The defender wins contact with the ball but does not cleanly control it.

The ball is placed loose near the challenge and no team has controlled possession.

This provides a foundation for later loose-ball races and second-ball situations.

---

## Broken press detection

The engine can identify a basic broken-press situation when the ball carrier gets beyond the primary presser in the attacking direction, opens sufficient distance, and is not still contained by a supporting presser.

This is diagnostic state for now. Later phases can use it when evaluating transitions, carries and attacks into exposed space.

---

## Determinism

Pressing movement itself is deterministic from the spatial/tactical state.

Physical duel resolution uses the match-owned seeded random source.

Therefore:

```text
same MatchSnapshot
+ same seed
+ same spatial setup
+ same action sequence
= same defensive-duel result
```

---

## Debug review

Run:

```powershell
$env:PYTHONPATH = "src"
python examples/demo_pressing_defensive_duels.py
```

The demo shows:

1. very-low vs very-high pressing intensity in the same spatial scenario;
2. pressure angle and defensive coverage;
3. a real tackle duel with possession transfer plus broken-press detection.

The output is intentionally diagnostic rather than presentation-ready.

---

## Automated validation

Phase 5.4 adds tests for:

- no press without a controlled opposing ball carrier;
- primary presser selection;
- team pressing intensity and number of committed pressers;
- constant-pressure scheme behaviour;
- individual pressing targets;
- individual pressing intensity and real closing speed;
- force-direction approach geometry;
- trap-outside scheme geometry;
- physical closing movement over fixed ticks;
- manual movement overrides;
- explicit marking assignments;
- zonal vs man-marking strength;
- tackle-distance validation;
- invalid teammate tackles;
- defender/attacker attribute effects on duel probability;
- nearby defensive support;
- defensive aggression vs underlying duel quality;
- seeded deterministic duel resolution;
- broken-press detection;
- defender-controlled recoveries;
- failed tackles where the attacker retains possession;
- loose-ball outcomes after a won challenge.

Expected complete test result after Phase 5.4:

```text
151 passed
```

---

## Deliberately not implemented yet

Phase 5.4 does **not** yet implement:

- full carry/dribble execution;
- attacker-vs-defender dribble resolution;
- overlaps/underlaps;
- crosses/cutbacks;
- shots/xG;
- goalkeeper shot actions;
- referee foul/card decisions;
- automatic foul outcomes from tackles;
- full-match action scheduling;
- final Event Stream/commentary.

Fouls, referee strictness and cards remain Match Context work for Phase 5.8 rather than being hidden inside a generic tackle roll now.

---

## Next step

Phase 5.5 — Ball Progression.

The next layer will let ball carriers and off-ball attackers actively progress through the defensive behaviour introduced here using carries, dribbles, runs, through balls, overlaps, underlaps and wide/crossing actions.
