# Phase 6.1 — Competition Framework

## Goal

Create the generic competition domain that later league, cup, multi-stage, calendar and season systems can reuse without coupling competition rules to the Fast Match Simulator or to the disposable development UI.

## Core separation

Phase 6.1 deliberately separates four concepts:

1. **Competition definition** — stable identity and metadata such as name, scope and broad format.
2. **Competition edition** — one specific season with its participants, stages, regulations and qualification rules.
3. **Sporting fixture** — the pairing/round/leg that has to be played.
4. **Calendar schedule** — deliberately not implemented in Phase 6.1. Phase 6.5 now assigns kickoff dates/times to those stable fixture IDs through `ScheduledFixture` / `SeasonCalendar`.

This avoids treating a fixture and a date as the same object and keeps future rescheduling/postponement logic out of the competition generator.

## Domain objects

### `CompetitionDefinition`

Stable fields:

- `competition_id`
- name / short name
- scope: domestic, continental or international
- broad format: league, knockout or multi-stage
- optional country

### `CompetitionEdition`

Season-specific fields:

- stable `edition_id`
- season label
- participant club IDs
- ordered stages
- regulations
- qualification rules
- current lifecycle status
- unscheduled sporting fixtures

### `CompetitionStage`

A stage has a stable ID, order, stage kind, optional explicit participant subset and the competition-derived `MatchDecider` used by match snapshots.

Supported generic stage kinds are:

- round robin
- knockout
- group stage
- league phase
- playoff

The framework does **not** yet generate standings or brackets. Those belong to Phases 6.2-6.4.

### `CompetitionFixture`

Contains only sporting structure:

- fixture ID
- edition ID
- stage ID
- home/away club IDs
- optional round number
- leg number

There is intentionally no kickoff timestamp.

## Qualification / European places

League positions and downstream competition access are data, not league-engine code.

`QualificationRule` can describe:

- continental qualification
- promotion
- relegation
- playoffs

Sources can be:

- standing position
- cup winner
- cup runner-up
- title holder

A standing rule can therefore express concepts such as:

```text
positions 1-4 -> continental competition A / stage X
position 5    -> continental competition B / stage Y
positions 18-20 -> second domestic tier
```

The exact English/UEFA allocation for a specific season will be loaded as competition data later. Phase 6.1 intentionally does not hardcode a permanent "top four = Champions" rule because access lists can change and cup winners can alter final allocations.

Cup-derived routes can declare `NEXT_ELIGIBLE_STANDING_POSITION` as fallback. Actual cross-competition allocation/deduplication will be resolved once league tables and persistent competition results exist.

## Match integration

`CompetitionEdition.context_snapshot(stage_id)` converts competition/stage regulations into the existing immutable `CompetitionContextSnapshot` used by `MatchSnapshot` and `FastMatchSimulator`.

This keeps the match engine unaware of league tables, bracket generation and scheduling while still receiving the correct draw/extra-time/penalty and substitution rules.

## Serialization

Definitions, editions, stages, fixtures, regulations and qualification rules support lightweight `to_dict()` / `from_dict()` round trips. This is not the final save-game persistence layer; it is the data boundary needed for later loaders and `WorldState` persistence.

## Not implemented in 6.1

- round-robin fixture generation
- standings / points / tiebreakers
- knockout bracket advancement
- multi-stage advancement
- dates or kickoff scheduling
- persistent competition results
- full-season runner
- final English/UEFA competition data

Those remain the responsibilities of Phases 6.2-6.7.
