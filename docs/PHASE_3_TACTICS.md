# Phase 3 - Tactical Domain v1

## Goal

Represent a manager's tactical plan without simulating a match yet.

The central rule is that tactics describe requested behavior. They do not rewrite a player's base attributes or Overall rating.

## Team tactical presets

The tactical domain includes editable starting presets:

- Balanced
- Tiki-Taka
- Possession
- Constant Press
- Counterpress
- Counter Attack
- Direct Counter
- Catenaccio
- Low Block
- Direct Play
- Wide Attack
- Custom

A preset only creates an initial configuration. The Match Engine will eventually use the effective instructions after customization, not the preset name.

## Team instructions

Team behavior is separated into four groups.

### In possession

The model currently supports:

- width for defensive, midfield and attacking lines;
- distance between defense and midfield;
- distance between midfield and attack;
- tempo;
- pass speed;
- pass length;
- verticality;
- passing risk;
- build-up from the back;
- support closeness;
- switches of play;
- central focus;
- overlap frequency;
- patience;
- crossing frequency;
- long-shot frequency.

### Transition

The model currently supports:

- behavior after losing the ball;
- behavior after winning the ball;
- transition speed;
- counterattack risk;
- goalkeeper release speed.

### Out of possession

The model currently supports:

- independent defensive-line width;
- independent midfield width;
- independent attacking/first-press line width;
- distance between defense and midfield;
- distance between midfield and attack;
- block height;
- defensive line height;
- horizontal compactness;
- vertical compactness;
- pressing intensity;
- pressing scheme;
- direction used to force the opponent;
- marking style;
- offside trap;
- defensive aggression;
- box protection;
- centre protection;
- tolerance for conceding crosses.

### Game management

The foundation includes:

- time wasting;
- risk while leading;
- urgency while trailing.

The in-possession and out-of-possession shapes are independent. A team can, for example, open its defensive line during build-up and collapse into a narrow low block without the ball.

The Match Engine does not execute these instructions yet.

## Base roles by position

Every current Position has exactly five base roles.

Examples:

- full-backs: Defensive Full-Back, Balanced Full-Back, Wing-Back, Inverted Full-Back and Inverted Wing-Back;
- centre-backs: Central Defender, Stopper, Covering Defender, Ball Playing Defender and Wide Centre-Back;
- central midfielders: Central Midfielder, Box-to-Box, Central Playmaker, Mezzala and Ball-Winning Midfielder;
- wingers: Winger, Inverted Winger, Inside Forward, Wide Playmaker and Defensive Winger;
- strikers: Advanced Forward, Pressing Forward, Target Forward, Deep-Lying Forward and False Nine.

Roles are presets of player behavior, not ability modifiers.

## Individual instructions

A role supplies default instructions. The manager can override them per formation slot.

Current individual controls include:

- forward runs;
- dribbling frequency;
- crossing frequency;
- shooting frequency;
- passing risk;
- hold-up play;
- attacking space;
- pressing intensity;
- defensive tracking;
- roaming;
- in-possession movement;
- out-of-possession movement;
- cross type;
- marking target;
- pressing target.

A target can reference:

- a specific player;
- an opposition position;
- a role.

This allows future instructions such as a left-back marking the opposition right-winger or an attacker pressing a specific goalkeeper.

## Role defaults plus overrides

The role label is not the final behavior.

For example, a Defensive Full-Back can be customized to:

- make more forward runs;
- enter midfield in possession;
- attempt more dribbles;
- return to the base full-back position without the ball.

The effective instructions are the role defaults plus user overrides.

Changing those instructions does not alter the player's technical, mental or physical attributes.

## Familiarity and suitability foundations

The phase separates four concepts:

1. positional familiarity;
2. role familiarity;
3. tactic familiarity;
4. role suitability.

Role suitability is calculated from the player's existing attributes that matter to that role. It is diagnostic only and does not modify player ability.

Role familiarity and tactic familiarity are stored independently on the player.

Learning rules are deliberately deferred. Minutes, training, age, performance and behavioral similarity can later determine how fast familiarity changes.

## Role similarity

The domain can compare the behavioral defaults of two roles.

This is a foundation for later transfer of learning. A winger and an advanced forward can be more behaviorally similar than a winger and a target forward, so a future adaptation system can use that difference rather than relying only on role names.

## Tactical style analyzer

The style analyzer reads the effective team instructions and produces descriptive axes such as:

- possession;
- pressing;
- directness;
- defensive depth;
- tempo;
- width;
- in-possession width;
- out-of-possession width;
- defensive compactness;
- central protection;
- cross tolerance;
- risk.

It also generates a descriptive label, for example:

- Presion alta + posesion
- Defensa profunda + ralentizar el partido
- Defensa profunda + contraataque directo
- Ataque por bandas + amplitud
- Salida ancha + bloque defensivo compacto

The generated label is descriptive only. It grants no hidden bonus.

A manager can keep a custom tactic name such as `Nico Ball` while the game separately reports the detected tactical identity.

## Deliberately not implemented yet

- match simulation;
- tactical matchup effects;
- xG, shots or goals;
- actual pressing actions;
- automatic familiarity growth;
- tactical training;
- chemistry;
- opponent scouting;
- in-match tactical changes;
- AI tactical decision-making.

These systems will consume the tactical model in later phases.
