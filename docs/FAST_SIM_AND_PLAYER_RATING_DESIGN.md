# Fast Match Simulator + Player Rating System

## 1. Match simulation strategy

The game will use two match-resolution paths:

### Fast Match Simulator
Primary simulator for:
- all matches not controlled by the user;
- the user's own match when choosing **Quick Sim**;
- league, cup and season progression.

It must be very fast and probabilistic, but still based on football logic.

It must **not** simply compare team ratings and give the win to the stronger team.

The result should emerge from:
- player quality;
- lineup and availability;
- tactics;
- tactical execution;
- player state;
- positional and role familiarity;
- chemistry;
- home advantage;
- opponent matchup;
- match context;
- controlled randomness.

The stronger team should normally have better probabilities, but upsets, draws and bad performances must remain possible.

Randomness must act **inside football events**, not directly choose a winner.

### 2D Match Engine
Future major upgrade/add-on.

Used only for the user's own match when choosing the immersive mode.

It will allow:
- watching the match in 2D;
- live tactical changes;
- substitutions and in-match decisions.

The 2D engine must not block development of leagues, seasons, transfers, scouting, contracts, finances or the rest of the game.

---

## 2. Overall vs Current Rating

Every player will show two separate ratings.

### ◆ OVR — Overall
Represents the player's underlying football quality.

It is derived from the player's attributes, using position-appropriate weighting rather than a simple average.

OVR:
- does not change because the player is used out of position;
- does not change because a role is unfamiliar;
- should change slowly over months/seasons;
- can rise or fall through long-term development or decline.

A winger rated 84 remains an **84 OVR** even if used as a striker or centre-back.

### ◇ ACT — Current / Effective Rating
Represents how well that player is currently able to express his ability in the present context.

ACT is influenced by:
- positional familiarity;
- role familiarity;
- tactical familiarity;
- form;
- confidence;
- physical condition;
- match sharpness;
- chemistry / footballing understanding;
- current context.

Example:

```text
◆ 86 OVR
◇ 74 ACT
```

The player is still an 86-quality footballer, but is currently performing well below that level.

The opposite is also possible:

```text
◆ 78 OVR
◇ 82 ACT
```

A lower-quality player can temporarily perform above his structural level because he is confident, in form, fully adapted and well suited to the current system.

---

## 3. No rating by role

There will be no separate permanent Overall such as:

```text
Advanced Forward 87
Pressing Forward 89
Target Forward 73
```

The player's OVR remains the same.

What changes is how effectively he performs in the current:
- position;
- role;
- tactical system.

The distinction is:

```text
player quality
!=
ability to execute the current function
```

---

## 4. Position, role and tactical adaptation

Players can learn new positions and roles over time.

Adaptation must not be automatic just because minutes are accumulated.

Conceptually, progress depends on:

```text
minutes played
× adaptability
× tactical intelligence
× training quality
× positional similarity
× performance quality
× confidence
```

A player who adapts well and performs well can learn faster.

A player who repeatedly performs badly may:
- adapt very slowly;
- stagnate;
- lose confidence;
- lose form;
- fail to fully learn the position or role.

Some players may never become fully comfortable in a new function.

---

## 5. Bad signings and failed development

The game must avoid guaranteed progression.

Playing many matches does **not** automatically make a player better.

A young signing can fail.

Example:

```text
21 years old
82 OVR
high potential
40 matches played

→ poor performances
→ low confidence
→ poor adaptation
→ development stalls
→ future OVR may decline
```

Long-term poor usage or poor performance can eventually affect:
- development;
- attributes;
- OVR;
- confidence;
- form;
- career trajectory.

This makes failed transfers and failed positional experiments possible.

---

## 6. Time horizons

Different variables should move at different speeds.

### Short term — match to match
- form;
- confidence;
- condition;
- fatigue debt / recovery load.

### Medium term — weeks / months
- positional familiarity;
- role familiarity;
- tactical familiarity;
- chemistry;
- match sharpness.

### Long term — months / seasons
- attributes;
- OVR;
- realized potential;
- physical decline;
- long-term development.

A few bad matches should not destroy OVR.

A poor season or several poor seasons can.

---

## 7. Confidence

Confidence is a core player-state attribute.

It should influence current performance and adaptation.

Confidence can be affected by:
- recent performances;
- goals / assists / mistakes;
- missed chances;
- playing time;
- positional comfort;
- tactical fit;
- team results;
- manager decisions;
- losing a starting place;
- successful adaptation.

Confidence is one of the main inputs to **ACT**, not a direct rewrite of OVR.

---

## 8. Fast Simulator philosophy

The Fast Simulator should use player OVR as a quick indicator of structural quality, but must not resolve matches only from OVR.

A match should approximately emerge from:

```text
player quality
+
tactics
+
tactical execution
+
current state
+
positional / role familiarity
+
chemistry
+
opponent interaction
+
context
+
controlled randomness
```

The stronger team should usually be favoured, but never guaranteed to win.

The simulator should generate the result through probabilistic football events and distributions rather than first deciding the winner.

It should eventually return:
- score;
- goalscorers;
- assists;
- shots;
- shots on target;
- xG;
- possession;
- passes;
- fouls;
- cards;
- corners;
- injuries;
- substitutions;
- player ratings;
- minutes;
- condition and post-match fatigue/recovery effects;
- individual statistics.

---

## 9. Condition, stamina and recovery

Physical state is split deliberately:

```text
condition
= current freshness/readiness (0-100)

fatigue
= accumulated physical debt that slows recovery
```

Only `condition` is a direct physical input to ACT. `fatigue` must not be counted as a second direct ACT penalty; it affects future condition through workload and recovery.

`condition` is one-sided for current performance:

```text
75-100 → no direct ACT bonus
below 75 → progressively worse effective performance
```

Within matches, `stamina` is the main resistance attribute. High stamina means less condition loss and less fatigue accumulation for the same workload. Tactical choices and player duties change that workload.

Between matches, `natural_fitness` is the main recovery attribute and `stamina` contributes secondarily. A normal 90-minute match can be fully recovered from over a clean week for an average player; 120 minutes should leave a small recovery scar even after a week.

The persistent loop is:

```text
pre-match condition
→ match workload
→ condition_after + fatigue_after
→ calendar recovery
→ next-match condition
```

This is intended to make fixture congestion and squad rotation real management problems rather than cosmetic systems.

---

## 10. Coach quality must matter

The Fast Simulator must not become a squad-quality calculator.

A stronger squad should normally be favoured, but a weaker side can compensate through:

- better player selection;
- correct positions and roles;
- high tactical familiarity/execution;
- a plan that exploits the opponent;
- appropriate physical management.

The tactical system must therefore distinguish:

```text
execution quality
!=
matchup quality
```

High execution of the wrong plan must not receive a hidden universal bonus. A well-executed counter-plan can, however, turn a moderate structural-quality deficit into an even or favourable matchup through shots/xG/control rather than through an artificial upset roll.

---

## 11. Future 2D dynamic rating

The current Fast Simulator mainly consumes the frozen pre-match/current `ACT` from MatchSnapshot and returns post-match physical state.

A future 2D rebuild may maintain an internal minute-by-minute effective-performance value:

```text
pre-match ACT
+ live condition
+ live match context
= internal in-match effectiveness
```

That value does not need to be shown directly in the UI. Its purpose is to make substitutions, pressing intensity and physical mismatches matter dynamically while preserving the player's underlying OVR.

---

## 12. Core design principle

The central distinction is:

```text
◆ OVR
How good is this footballer?

◇ ACT
How well is he performing in this team, role and moment?
```

A great player can perform badly.

A worse player can currently perform better.

A player can fail to adapt.

A signing can fail.

A tactical experiment can hurt a player's confidence and long-term development.

The game should generate these outcomes from systems rather than guarantee progression.
