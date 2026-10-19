# Phase 6.2 — Round-Robin League

## Goal

Build the first real league competition behavior on top of the generic Phase 6.1 competition framework without mixing league logic into match simulation or calendar scheduling.

## Implemented

### Double round-robin sporting structure

`generate_double_round_robin()` creates an unscheduled home/away league plan using the circle method.

For a 20-club competition this produces:

- 38 sporting rounds;
- 10 fixtures per round;
- 380 fixtures total;
- every club exactly once per round;
- every pair of clubs exactly twice;
- one home and one away meeting per pair.

Kickoff dates are deliberately absent from the league domain. Phase 6.5 now owns calendar placement through `SeasonCalendar`.

### Seeded first season vs generated later seasons

Phase 6.2 explicitly distinguishes fixture provenance:

- `FixturePlanSource.SEEDED` — an externally supplied sporting fixture list, intended for the real first-season fixture order;
- `FixturePlanSource.GENERATED` — an internally generated round-robin plan for later seasons or development data.

`RoundRobinFixturePlan` validates either route and exposes a reusable `RoundRobinTemplate`.

A seeded first-season fixture list can therefore become a template of round/venue slots. Future seasons can instantiate that template with a new participant set and a different seed. This supports promoted/relegated clubs without copying literal dates or adding 365 days to the previous season.

The actual 2026/27 Premier League fixture data is intentionally not bundled in this phase. It belongs to the later real-data/calendar import layer.

### Results and league table

`LeagueResult` records a final result against a `CompetitionFixture`.

`build_league_table()` derives the table from fixtures + final results. It supports:

- played;
- wins/draws/losses;
- goals for/against;
- goal difference;
- configurable win/draw/loss points;
- configurable tie-breaker order;
- partial-season tables;
- deterministic ordering fallback when sporting criteria remain tied.

The current generic default tie-break sequence is:

1. points;
2. goal difference;
3. goals scored;
4. wins;
5. stable club ID only as a deterministic fallback.

Competition-specific edge-case tie breakers can be added as competition data when real rules are loaded; they are not hardcoded into the generic league engine.

### Match context integration

League standings can be converted to the existing immutable `StandingRowSnapshot` objects and supplied through `CompetitionEdition.context_snapshot()`.

The Fast Match Simulator remains responsible only for resolving the match. The league layer consumes final scores and updates standings.

### Disposable development UI

The sandbox now exposes the minimum inspection surface for Phase 6.2:

- a fictional 20-club development league;
- 38 rounds / 380 sporting fixtures;
- the current league table;
- development-only qualification/relegation route labels;
- current-round fixtures;
- the Northbridge Quick Sim writes its result into the league table;
- after that match, a DEV-only Continue action resolves the other nine fixtures in the round, applies seven days of existing condition recovery and loads Northbridge's next league fixture with its real home/away orientation.

These fictional clubs and qualification labels are test data, not real Premier League content. The sandbox remains disposable and does not define the final UI. Phase 6.5 replaces the original seven-day DEV-only chronology with `SeasonCalendar` and adds a separate official 2026/27 schedule inspector.

## Deliberately deferred

- real Premier League 2026/27 fixture import;
- kickoff dates and fixture rescheduling;
- cross-competition calendar congestion;
- persistent multi-match competition runners;
- season advancement;
- exact real-season European berth allocations;
- league-specific rare tie-break procedures requiring special resolution/playoffs;
- promotion/relegation participant rollover;
- cup and multi-stage competition behavior.

## Next

Phase 6.3 — Knockout Competitions.
