# Phase 1.1 - Expanded Player Attributes

## Objective

Complete the first usable version of the player attribute model before moving on to clubs and lineups.

This phase expands the initial attribute groups so the future Match Engine can evaluate specific football actions instead of resolving gameplay from a single overall rating.

## Attribute scale

All attributes use a `1-100` scale.

The scale is a representation of ability, not a direct percentage of success. A player with `finishing = 90` does not score 90% of his shots.

## Technical attributes

- `passing`
- `technique`
- `finishing`
- `first_touch`
- `dribbling`
- `crossing`
- `tackling`
- `heading`
- `long_shots`
- `shot_power`
- `marking`
- `set_pieces`
- `penalties`

## Mental attributes

- `vision`
- `decisions`
- `anticipation`
- `concentration`
- `composure`
- `positioning`
- `off_the_ball`
- `teamwork`
- `work_rate`
- `aggression`
- `bravery`
- `creativity`
- `tactical_intelligence`
- `adaptability`

## Physical attributes

- `pace`
- `acceleration`
- `strength`
- `stamina`
- `agility`
- `balance`
- `jumping_reach`
- `natural_fitness`

## Goalkeeping attributes

Goalkeeper-specific attributes are optional for an outfield player and present for goalkeepers.

- `reflexes`
- `handling`
- `one_on_ones`
- `aerial_reach`
- `command_of_area`
- `kicking`
- `throwing`
- `goalkeeper_positioning`

## Important design decision: Overall is a summary, not an action resolver

Players will have a derived `Overall` (`OVR`) rating representing their general underlying football quality.

`OVR` is not an independent ability and must not replace the player's attributes.

It is calculated from the player's underlying attributes using appropriate weighting rather than a simple arithmetic average.

The purpose of `OVR` is to provide a compact summary of player quality for systems such as:

- squad evaluation;
- scouting;
- transfer-market evaluation;
- AI squad selection;
- team-strength estimation;
- Fast Match Simulator inputs;
- user-interface presentation.

A player's `OVR` represents the quality of the footballer himself.

It does **not** decrease simply because the player is being used:

- out of position;
- in an unfamiliar role;
- in an unfamiliar tactical system;
- while out of form;
- while lacking confidence.

Those factors affect how effectively the player performs in the current context, but they do not redefine his underlying quality.

For example:

```text
Player
OVR: 84

Natural position familiarity: 95
Current position familiarity: 20
Role familiarity: 15
Confidence: 40
Form: 45
```

The player remains an `84 OVR` footballer even if his current effective performance is substantially lower.

The game will therefore distinguish between:

```text
OVR
=
underlying football quality
```

and:

```text
current / effective rating
=
how much of that quality the player is currently able to express
```

The current/effective rating will eventually consider contextual factors such as:

- positional familiarity;
- role familiarity;
- tactical familiarity;
- form;
- confidence;
- physical condition;
- match sharpness;
- chemistry / footballing understanding;
- current context.

`fatigue` is intentionally not applied as a second direct current-rating penalty. It represents accumulated workload/recovery debt and influences performance through the player's resulting physical `condition`.

This current/effective rating must remain separate from `OVR`.

`OVR` itself may evolve over the long term as the player's real attributes develop or decline across months and seasons.

Repeated poor performances, failed development, aging, injuries or long-term negative career trajectories may eventually reduce attributes and therefore reduce `OVR`.

Likewise, development may increase attributes and therefore increase `OVR`.

However, short-term form or confidence changes must not directly rewrite the player's underlying `OVR`.

`PlayerAttributes.outfield_average()` remains a development/debugging diagnostic.

It must not automatically be treated as the player's final `OVR`, because the real `OVR` calculation may use weighted attributes rather than a simple average.

Most importantly, neither the Match Engine nor the Fast Match Simulator should resolve specific football actions using `OVR` alone.

Examples:

```text
Shot from inside the box
→ finishing + composure + technique + context
```

```text
Attack the space behind a high defensive line
→ acceleration + pace + off_the_ball + anticipation
```

```text
Defend an aerial cross
→ jumping_reach + heading + positioning + strength + context
```

```text
Goalkeeper one-on-one
→ one_on_ones + reflexes + goalkeeper_positioning + composure + context
```

`OVR` may help establish the player's general level, but specific football actions must continue to depend on the relevant attributes and context.

The exact `OVR`, current/effective rating and Match Engine formulas are deliberately not defined in this phase.

## Player attributes vs player statistics

Attributes describe what a player is capable of doing:

```text
finishing = 84
dribbling = 76
vision = 74
```

Statistics describe what the player actually did in matches:

```text
matches = 21
goals = 8
assists = 5
xG = 7.3
```

Match statistics are intentionally not implemented yet because they will be produced by the Match Engine in later phases.

## Data loading

The JSON player loader now supports an optional `goalkeeping` attribute group.

Outfield players can omit it.

## Sample data

The sample dataset now contains:

- one striker;
- one winger;
- one goalkeeper.

This allows both outfield and goalkeeper profiles to be tested.
