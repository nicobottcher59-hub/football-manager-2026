# Phase 6.5 - Calendar & Scheduling

## Objective

Turn dates into a real domain concern instead of a DEV-only ordering trick, while keeping sporting competition structure independent from scheduling and proving the model against an official first-season fixture dataset.

## Fixture vs schedule

Phase 6.1-6.4 deliberately kept `CompetitionFixture` unscheduled. Phase 6.5 preserves that boundary:

```text
CompetitionFixture
= sporting identity, clubs, stage, round/leg

ScheduledFixture
= fixture_id + kickoff + status + scheduling source

SeasonCalendar
= authoritative cross-competition chronology
```

Moving a match therefore does not rewrite the league/cup draw. Sporting identity and calendar placement can evolve independently.

## Calendar model

`football_manager.domain.calendar` adds:

- `ScheduleSource`: `OFFICIAL` or `GENERATED`;
- `ScheduledFixtureStatus`: `SCHEDULED`, `PLAYED`, `POSTPONED`, `CANCELLED`;
- `ScheduledFixture`: timezone-aware calendar placement linked by stable fixture ID;
- `SeasonCalendar`: immutable calendar operations and chronological queries;
- `CalendarConflict`: same-club overlap (including two different kickoff times on one date) or insufficient-rest detection;
- `CalendarBlock`: explicit date blocks for generation rules;
- `SchedulingWindow`: allowed date range/weekdays for a competition;
- `LeagueSchedulingPolicy`: future-season league date-generation policy.

A postponed fixture preserves `original_kickoff`. A rescheduled fixture receives a new kickoff while retaining that original date for audit/history. `mark_played`, `postpone`, `reschedule` and `cancel` reject invalid status transitions rather than silently reviving a finished fixture.

## Competition windows and rescheduling

`find_available_kickoff()` searches a `SchedulingWindow` for the earliest valid slot and rejects dates that would violate the requested minimum rest around either club's other fixtures.

`reschedule_fixture_into_window()` applies that search to an existing fixture without treating the fixture being moved as a collision with itself.

This is the first scheduling-rule layer. Detailed broadcast selection, police/venue constraints, weather postponements and competition-specific priority policies can be added as data/rules later without changing the fixture/calendar boundary.

## Future seasons

`generate_league_round_dates()` takes the new season's own:

- start/end dates;
- preferred weekday/time;
- minimum gap (three days by default);
- blackout periods.

The policy can also declare midweek weekdays. Round dates are distributed across the new season's window using deterministic minimum-cost scheduling, favouring the preferred weekday while respecting blackouts and minimum gaps. When weekends alone cannot fit a 38-round league, it can place a limited number of midweek rounds; impossible windows are rejected explicitly.

It does **not** copy the previous season's dates and does not add 365 days to an old schedule. The sporting round order can come from the Phase 6.2 round-robin/template layer, while Phase 6.5 assigns dates for the new edition. A future world runner will still need to coordinate league dates with cup and European windows rather than assume one independent competition policy can settle every conflict.

## Official Premier League 2026/27 dataset

The first official schedule snapshot is packaged under:

```text
src/football_manager/data/official/england/
```

`load_premier_league_2026_27()` constructs both the real competition edition and its `SeasonCalendar`.

The loader validates:

- 20 clubs;
- 38 matchweeks;
- 10 matches and 20 unique clubs per matchweek;
- 380 total fixtures;
- 190 club pairs;
- each pair exactly twice, once at each venue;
- all schedule rows tagged `OFFICIAL`;
- fixture bounds from 21 August 2026 through 30 May 2027.

The packaged metadata records the official Premier League source article, its publication date (19 June 2026) and the fixture snapshot date (8 October 2026). Kickoffs use the published fixture information and the article's stated default kickoff rules where an individual time is not specified. Real-world fixture changes after the snapshot are not silently invented into this source-controlled dataset.

No real 2026/27 results are imported. A new save remains free to simulate its own outcomes.

## Development UI integration

The disposable sandbox now consumes `SeasonCalendar` directly.

### Managed DEV calendar

- league, Development Cup and Development Continental fixtures are registered as `GENERATED` scheduled fixtures;
- `Continue` asks the calendar for the next scheduled Northbridge match;
- Quick Sim marks the active scheduled fixture `PLAYED`;
- condition recovery uses the actual number of days to the next calendar fixture.

### Official data inspector

Calendar has a separate **Premier League 2026/27 - Official data** tab showing all 380 packaged fixtures with date, matchweek, home/away clubs, kickoff and source.

The real clubs are intentionally **not** merged into the fictional DEV world. Binding official schedules to playable real clubs belongs to the real world/club database integration, not to a UI shortcut.

## Explicitly deferred

- persistent saved WorldState and unattended world-result advancement (Phase 6.6);
- full season orchestration across the English test world (Phase 6.7);
- official Championship / League One / League Two datasets;
- official FA Cup / EFL Cup draws and evolving round participants;
- UEFA schedule import (the loader/calendar boundary is ready, but no UEFA dataset is packaged in 6.5);
- broadcast-driven fixture moves and detailed venue/policing/weather policies;
- final production calendar UI.
