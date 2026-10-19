# Phase 6.3 - Knockout Competitions

## Objective

Add a generic elimination-round domain on top of the Phase 6.1 competition framework without coupling cup logic to dates, the development UI or the Fast Match Simulator implementation.

## Implemented

- `KnockoutRoundDefinition` with ordered rounds and single-leg / two-legged formats.
- `KnockoutDrawSource` with `SEEDED` and `GENERATED` provenance.
- `seed_knockout_round()` for externally supplied real-world pairings.
- `generate_knockout_round()` for deterministic in-world draws from a seed.
- `KnockoutTie` grouping one or two sporting fixtures.
- `KnockoutMatchResult` with optional penalty-shootout score.
- aggregate tie resolution and automatic winner/loser derivation.
- no away-goals rule.
- automatic advancement of actual winners into the next round.
- knockout match-context bridge for the existing Fast Match Simulator.

## Match resolution boundary

The knockout engine does not simulate football actions. It supplies competition semantics to the existing match resolver.

For a single-leg tie, the match is decisive immediately. For a two-legged tie, leg one uses `DRAW_ALLOWED`; leg two receives a `CupTieContextSnapshot` containing the correctly reoriented aggregate before kickoff and uses the round's decisive resolver. The Fast Match Simulator therefore handles extra time and penalties using its existing Phase 5.11D path rather than cup code duplicating those systems.

A shootout is attached to the decisive fixture result. In a two-legged tie this can happen even when the second-leg score itself is not level, because the aggregate can still be tied.

## First real season vs later seasons

The cup layer supports the same philosophy already established for the league:

- first-season real draws that are known/imported can be represented as `SEEDED` pairings exactly as published;
- later rounds whose participants differ from reality, or future seasons, can use `GENERATED` draws from the clubs that actually qualified in the simulated world.

Dates are intentionally absent from both modes. Phase 6.5 now places sporting fixtures on the unified `SeasonCalendar`.

## Disposable sandbox

The development UI exposes a fictional eight-club `Development Cup` only to inspect the engine:

- quarter-finals: single leg;
- semi-finals: two legs;
- final: single leg.

A DEV-only button resolves the current cup round and advances the bracket. This is not the final cup UI and is not calendar integration.

FA Cup and EFL Cup remain named placeholders for future real competition data/rules. The generic knockout engine is ready for them, but their entry rounds, real 2026/27 draws, calendar dates and other season-specific rules are intentionally not hardcoded in Phase 6.3.

## Explicitly deferred

- real FA Cup / EFL Cup 2026/27 data imports;
- round-entry rules and competition-specific exemptions/byes;
- unified dates, postponements and congestion;
- cross-competition season runner and persistence;
- cup-winner continental berth allocation across completed competitions;
- final production UI.

Those belong to later competition/calendar/world phases.
