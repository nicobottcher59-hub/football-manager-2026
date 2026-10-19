# Phase 6.4 - Multi-Stage Competitions

## Objective

Compose standings-based and knockout stages into one competition flow without hardcoding a specific UEFA format, while keeping the Fast Match Simulator as the only match resolver.

## Domain model

Phase 6.4 adds `football_manager.domain.multistage`.

- `StageRouteKind`: `ADVANCE`, `PLAYOFF`, `ELIMINATED`.
- `StandingRouteRule`: season/edition data that maps one or more standing positions from a source stage to a destination stage or elimination.
- `StageRouteAssignment`: resolved club route for one final standing position.
- `StandingStageTransition`: complete transition result with helpers for destination participants and eliminated clubs.
- `resolve_standing_stage_transition()`: converts completed standings into the configured routes and rejects overlapping position rules.
- `merge_stage_participants()`: safely combines direct qualifiers with winners from an intermediate stage.
- `validate_multi_stage_edition()`: validates multi-stage format, stage references and forward-only standing transitions.

No UEFA position ranges live in the engine. A real edition will provide those bands as data.

## Development Continental proof

The disposable sandbox contains an eight-club multi-stage competition only to exercise composition:

1. seven-match single round-robin league phase;
2. positions 1-2 advance directly to the semi-final;
3. positions 3-6 enter a single-leg playoff;
4. positions 7-8 are eliminated;
5. playoff winners join the two direct qualifiers in a two-legged semi-final;
6. semi-final winners advance to a single-leg final.

This is not intended to mirror real Champions League participant counts or 2026/27 data. It proves the transition architecture that real data will later configure.

## DEV cross-competition schedule

Because every implemented competition must be testable immediately, the disposable `DevelopmentSession` now maintains an in-memory chronological schedule for the managed club:

- all 38 development league fixtures;
- known Development Cup fixtures;
- Development Continental league-phase fixtures;
- dynamically generated knockout fixtures when the club qualifies;
- conditional future knockout dates displayed as `TBD if qualified` until the sporting path is known.

`Quick Sim` records the result in the correct competition. Background DEV resolution completes the other fixtures needed for tables/brackets. `Continue` selects the next managed fixture by date across competitions and recovery uses the actual gap in days.

At the end of Phase 6.4 this was deliberately only a DEV chronology. Phase 6.5 replaces that ad-hoc scheduling layer with the real `SeasonCalendar` domain, including postponement/rescheduling and conflict/rest checks.

## Morale

The sandbox now persists a basic result-driven morale response through the real `PlayerState.adjust_morale()` API:

- wins increase morale;
- losses reduce morale;
- draws provide a small positive adjustment;
- result margin modestly scales the change;
- starters react slightly more than non-starters.

Chemistry is intentionally unchanged until the planned relationship/cohesion systems exist. Role familiarity was not changed in this phase.

## Explicitly deferred

- real Champions League 2026/27 rules, teams and fixtures;
- real Premier League / FA Cup / EFL Cup schedule import;
- full English pyramid to League Two;
- persistent unified WorldState calendar;
- postponements, rescheduling and fixture congestion rules;
- qualification allocation across completed domestic/continental competitions;
- final production competition/calendar UI.

Phase 6.5 now covers the calendar/scheduling items in this list; the remaining world-data and persistence work continues in Phase 6.6+.
