# Phase 5.11E - Condition, Stamina & Recovery

## Objective

Make physical condition matter across matches without coupling core game development to the legacy 2D engine.

Phase 5.11E turns `condition` into a meaningful, persistent match-readiness variable:

```text
pre-match condition
→ match workload
→ post-match condition + fatigue debt
→ calendar recovery
→ next-match condition
```

The Fast Match Simulator remains pure: it returns post-match physical state but does not mutate persistent Player objects. World/calendar systems can apply those outputs through the condition service.

## Condition vs fatigue

The system keeps two physical concepts separate:

```text
condition
= current readiness / freshness (0-100)

fatigue
= slower-recovering accumulated physical debt (0-100)
```

Condition is the value that affects current performance. Fatigue is not a second direct ACT penalty; it exists to make heavy workloads recover more slowly.

This avoids double-counting the same physical problem.

## In-match stamina

`stamina` is the main resistance attribute during a match.

For the same workload:

- high stamina loses less condition;
- low stamina loses more condition;
- high stamina accumulates less fatigue debt;
- low stamina accumulates more fatigue debt.

A neutral player starting at `100 condition`, with `65 stamina`, is calibrated approximately to:

```text
90 minutes  → 54 condition
120 minutes → 26 condition
```

The curve is deliberately non-linear after 90 minutes. Extra time is more expensive than simply adding one linear third of a normal match.

Reference neutral workload, always starting from `100 condition`:

```text
stamina 40 → 90m 44 | 120m 10
stamina 65 → 90m 54 | 120m 26
stamina 90 → 90m 64 | 120m 43
stamina 97 → 90m 67 | 120m 48
```

The wider spread is intentional. `stamina` must create a visible physical difference between players exposed to the same assignment rather than compressing everybody into nearly the same post-match condition.

These are calibration anchors, not fixed outcomes.

## Tactical and positional workload

Players do not all consume condition at the same rate.

Fast-sim workload considers:

- position;
- team tempo;
- team pressing;
- defensive depth;
- directness;
- individual pressing;
- defensive tracking;
- forward runs;
- roaming;
- work rate.

Examples:

```text
high pressing
→ larger physical cost for forwards, wingers and midfielders

low defensive block
→ larger sustained workload for defenders / defensive midfield

high tempo / direct transitions
→ more physical cost, especially for sprint-heavy positions
```

The tactical plan therefore has a physical price instead of only changing xG, possession or chance creation.

## Current rating and rotation

Freshness does not create a bonus above normal ability.

```text
condition 75-100
→ no direct ACT bonus
```

Below 75, condition now creates a meaningful one-sided ACT penalty.

The intended selection consequence is:

```text
better player + very low condition
can be a worse current option
than
slightly weaker player + full condition
```

This gives squad rotation a football reason rather than making substitutions/rotation cosmetic.

The fully dynamic minute-by-minute ACT model is reserved for the future 2D rebuild. Phase 5.11E only establishes the physical state and the pre-match/current-rating consequence needed by the Fast Simulator and future calendar systems.

## Recovery between matches

`natural_fitness` is the primary between-match recovery attribute.

`stamina` also contributes materially to recovery. Its strongest effect remains resistance during the match, while natural fitness has roughly twice its weight in the between-match recovery rate. This keeps the attributes distinct without making stamina irrelevant once the final whistle goes.

Recovery happens across calendar days and clears both condition deficit and fatigue debt.

Reference player (`stamina 65`, `natural_fitness 65`):

```text
After a normal 90m match:
post-match: condition 54 / fatigue 39
+1 day:     condition 62
+3 days:    condition 78
+4 days:    condition 86
+7 days:    condition 100
```

After 120 minutes:

```text
post-match: condition 26 / fatigue 63
+1 day:     condition 39
+3 days:    condition 59
+4 days:    condition 67
+7 days:    condition 90
```

A full week therefore clears a normal 90-minute workload, while 120 minutes still leaves a small but meaningful recovery scar for an average player.

This creates the intended scheduling pressure:

- one match per week normally allows full recovery;
- a midweek match after a normal 90 minutes creates a selection decision;
- a midweek match after 120 minutes can force meaningful rotation.

## Natural fitness differences

After the same neutral 90-minute post-match state and four recovery days, the reference model produces approximately:

```text
natural_fitness 40 → condition 80
natural_fitness 65 → condition 86
natural_fitness 90 → condition 92
```

Stamina also affects recovery from the same starting state:

```text
stamina 40 → condition 83
stamina 65 → condition 86
stamina 90 → condition 89
stamina 97 → condition 89
```

Natural fitness remains the stronger recovery attribute, while stamina has a secondary but visible effect. In end-to-end play stamina matters even more because it also determines how depleted the player becomes before recovery starts.

## Persistence contract

`FastPlayerStatistics` now returns both:

```text
condition_after
fatigue_after
```

The simulator still does not mutate world players.

`football_manager.services.player_condition` provides:

```text
set_post_match_condition(...)
recover_player_between_matches(...)
```

Future competition/calendar code can therefore:

1. simulate the fixture;
2. persist each participant's post-match condition/fatigue;
3. advance recovery as calendar days pass;
4. build the next MatchSnapshot from the recovered state.

## 2D boundary

This phase does not resume development of the spatial 2D engine.

A future 2D rebuild may consume the same condition model minute by minute so that substitutions react to live physical decline. That is intentionally outside the current critical path.

## Validation

Run:

```powershell
$env:PYTHONPATH = "src"
python tools/calibrate_condition.py --matches 200
```

The benchmark reports:

- 90/120-minute condition by stamina;
- recovery across 1/3/4/7 days;
- natural-fitness and stamina recovery differences;
- tactical workload examples;
- integrated Fast Simulator post-match condition/fatigue.

Phase 5.11E adds regression tests for match depletion, extra-time depletion, stamina, tactical workload, recovery, ACT cost and persistence services.
