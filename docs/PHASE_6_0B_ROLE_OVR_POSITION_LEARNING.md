# Phase 6.0b - Contextual role OVR and position learning

## Goal

Phase 6.0b separates two questions that were previously mixed together:

1. **OVR**: how good is this player for the exact position/role assignment?
2. **ACT**: how much of that assignment-specific quality can the player express right now?

The change makes attributes the primary driver of positional adaptation. A centre-back with the right defensive/passing profile can therefore be a credible defensive full-back or anchor, while the same player can be a poor winger even if the raw position distance is similar.

## Contextual OVR

Contextual OVR starts from the attribute weights already defined by each `RoleDefinition`.

The calculation is conceptually:

```text
attribute fit for role
+ bounded positional-familiarity adjustment
+ small side / dominant-foot adjustment
= contextual OVR
```

The attribute fit is deliberately dominant. Positional familiarity can make an unfamiliar job harder, but it cannot make a player with the wrong footballing profile good at the role. Likewise, a player with excellent role attributes can remain useful while learning a new position.

The side/foot modifier is intentionally small. Mirrored wide positions such as LW/RW are close, not identical. Inverted roles reverse the preferred-foot logic where appropriate.

## ACT remains the execution layer

The existing ACT model remains in place above contextual OVR. It continues to apply current state and execution context such as:

- form;
- confidence;
- morale;
- condition;
- match sharpness;
- role familiarity;
- tactic familiarity;
- chemistry;
- exceptional total-context alignment.

Positional familiarity is not applied as a second direct ACT penalty because it already modifies contextual OVR.

## Position transfer

When a player has no explicit familiarity value for a target position, conservative transfer floors can be inferred from nearby football positions.

Examples:

- RCB <-> CB and RCM <-> CM transfer strongly;
- LW <-> RW transfer strongly but not perfectly;
- centre-back <-> full-back transfers partially;
- full-back <-> wing-back transfers strongly;
- centre-back <-> defensive midfield transfers partially;
- goalkeeper remains isolated from outfield positions.

These transfer values represent spatial familiarity only. They do **not** determine role quality; the role's attribute profile does that.

## Dynamic familiarity

`Player.record_position_minutes(...)` is the persistent domain entry point for positional development.

Playing minutes in a position:

- creates an explicit familiarity record when needed;
- starts from any valid transferable familiarity;
- improves quickly at low familiarity and more slowly near mastery;
- uses the player's adaptability to influence learning speed;
- accumulates real minutes for the position;
- slowly decays other explicit positions after a grace period;
- preserves a long-term memory floor based on historical peak familiarity and transferable knowledge.

This means a player does not instantly forget an old position, but several seasons in another role can materially change his positional identity.

## Primary and secondary positions

Primary and secondary positions are interpreted from accumulated familiarity instead of being permanently static labels.

A secondary position requires both:

- sufficient explicit familiarity; and
- meaningful real match minutes.

A new primary position requires sustained conversion. By default it must:

- reach at least 82 familiarity;
- accumulate at least 1,350 minutes;
- exceed the current primary by at least 5 familiarity points.

This inertia prevents emergency appearances from rewriting a player's main position. Once a conversion is genuinely established, the new position becomes primary automatically and the previous primary can remain as a secondary while it slowly decays.

`original_position` is retained separately as historical data.

## Match integration

Starter MatchSnapshots now carry OVR for the actual tactical assignment. The development UI, Fast Match Simulator and 2D runtime therefore consume the same contextual OVR.

Substitutes and live tactical reassignment also recalculate assignment OVR instead of falling back to the player's natural-position rating.

The Phase 6.0 sandbox persists starter position minutes after Quick Sim. It does not yet have a multi-fixture calendar or exact substitution-position history, so long-term conversions are exercised at domain level until the calendar/world layer is implemented.

## Development UI diagnostics

The Squad/Tactics views now expose additional diagnostics:

- main position;
- learned secondary positions;
- role attribute fit;
- assigned-position familiarity;
- contextual OVR;
- ACT.

These values make it possible to distinguish **"bad attributes for the role"** from **"good profile, but still learning the position"**.

## Regression coverage

Phase 6.0b adds regression tests for:

- defensive profiles fitting defensive full-back/anchor better than winger;
- stat-rich wingers remaining viable when retrained as full-backs;
- different roles at the same position producing different OVRs;
- mirrored winger positions being close but not identical;
- contextual OVR becoming the base for ACT without a duplicate positional penalty;
- UI and MatchSnapshot agreement;
- match minutes beginning positional learning;
- conservative automatic primary-position conversion.

Current suite: **415 tests**.
