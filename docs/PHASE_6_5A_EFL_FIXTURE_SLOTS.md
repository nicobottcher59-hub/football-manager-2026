# Phase 6.5a — EFL 2026/27 kickoff slots + fictional English tiers

## Product decision / scope

The 2026/27 Premier League *real-club* fixture is already imported in Phase 6.5.
For Championship, League One and League Two, **the user explicitly does not want
real playable clubs yet**. This phase therefore imports the published 2026/27
**kickoff-date/time slots per matchweek**, but generates all sporting pairings
for 24 **fictional** clubs per division.

This difference is fundamental and must be visible in UI and saved metadata:

- **Source-derived:** 46 matchweeks × 12 kickoff slots per EFL division, including
  midweek matches, rescheduled/outlier matches, opening and final dates.
- **Generated:** club identities, home/away pairings, strength values and simulated
  match results. All new `ScheduledFixture.source` values are `GENERATED`, **never
  `OFFICIAL`**, because the original real-world club matchup was not preserved.
- **Already official as a complete pairing fixture:** Phase 6.5 Premier League
  snapshot, still inspected separately and not attached to fictional Northbridge.

## Source provenance / dates

- EFL fixture release (25 June 2026):
  https://www.efl.com/news/2026/june/25/the-2026-27-efl-fixtures-are-here/
- Individual matchweek UTC kickoff distributions captured from:
  - Championship: https://fixturedownload.com/results/championship-2026
  - League One: https://fixturedownload.com/results/efl-league-one-2026
  - League Two: https://fixturedownload.com/results/efl-league-two-2026
- Snapshot basis: 8 October 2026; real fixture changes are not automatically
  synchronized. Kickoffs are stored as UTC-aware timestamps. The data does **not**
  import real-world results.

Bundled source-controlled assets:

```
src/football_manager/data/official/england/efl_slots/
    championship_2026_27.slots
    league_one_2026_27.slots
    league_two_2026_27.slots
```

`MMDD-HHMMxN` is a run-length encoding of UTC kickoff timestamps for a given
round. Each row must expand to 12 timestamps. File round numbers are 1..46,
not chronological event order (a rearranged match may be played after the next
round); `SeasonCalendar` remains the chronological source of truth.

## Domain / loading

`football_manager.data.efl_2026_27` exposes:

- `load_efl_2026_27_slots(key)` — strict parsing/validation of the date template;
- `build_development_efl_2026_27(key, seed=6510)` — generated 24-team
  double round-robin with 552 fixtures and no duplicate home/away pairing;
- `build_all_development_efl_2026_27()` — three independent divisions;
- `DevelopmentEflDivision` — immutable edition/calendar/spec/club names/strengths;
- `tier_strength(tier, club_index)` — sandbox-only relative quality.

Each of the 24 fictional clubs plays 46 matches, facing each other club twice,
once home and once away. The generated pairing-to-date mapping is deterministic,
uses exactly the source-date multiset for every round and rejects same-club
schedule conflicts. Any officially rescheduled/outlier slot belongs to its
original matchweek number, even if its actual calendar date is later.

## Relative fictional team strength

The test-world team-quality index uses distinct bands with internal variation:

| Tier | Division | Nominal strength | Actual DEV range |
|---|---|---:|---:|
| 1 | Premier League | 80 | 76–84 |
| 2 | Championship | 65 | 61–69 |
| 3 | League One | 50 | 46–54 |
| 4 | League Two | 35 | 31–39 |

Tier 1's values are reserved for future cross-tier tests; existing Premier
FastSim/league calibration is **not retroactively changed**. Lower-tier background
simulation uses the generated strength to influence expected goals, not
real-world club ratings. None of these clubs represents a real 2026/27 team.

## Sandbox coverage

- `Calendar -> EFL 2026/27 — fictional clubs`: choose Championship / League One /
  League Two; view all 552 generated pairings with the published kickoff slots.
- `Competitions -> EFL leagues (DEV)`: inspect full 24-team table, strength index,
  any of 46 rounds, its dates, and simulate next round for testing. Results are
  kept separate per division; the current managed Premier season is unaffected.
- The existing `Calendar -> Premier League 2026/27 — Official data`, managed
  Northbridge flow, Development Cup and Development Continental remain intact.

The EFL spectator button is deliberately a **development inspector**, not a
persistent background world runner. It can simulate matchweeks without moving
managed club time. Phase 6.6 will add full chronological unattended world
execution, and Phase 6.7 will handle true season transitions.

## Explicitly deferred

- Real EFL club identities, real rosters, player attributes and a playable club
  selector across the 92 clubs (do not import them prematurely);
- Real EFL 2026/27 club pairings attached to actual club records;
- FA Cup + Carabao Cup independent real competition integration (Phase 6.5b);
- Cross-league promotions/relegations and playoffs after a full season (6.7);
- Database persistence and automatic non-managed fixture resolution (6.6);
- UEFA real-season scheduling and detailed future TV fixture adjustments.

## Regression expectations

Check both properties: (a) full 552 kickoff-slot multiset per division and (b)
all 552 generated fixtures have valid round-robin pairings with `GENERATED`
provenance; never infer the latter is a real English Football League draw.
The test suite also checks deterministic generation, 24-hour clash-free calendar,
quality bands, simulated standings and 46-round completion.
