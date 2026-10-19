# Phase 6.5b + 6.6 — FA Cup, Carabao Cup & Persistent English World Runner

## Goal

Close the two missing major domestic cups and immediately run all six English competitions together in the same canonical result ledger, using **fictional clubs**. Phase 6.7 will handle final league outcomes and season transitions.

## Official source windows / modeled behavior

- [The FA — Emirates FA Cup round dates, 2026/27](https://www.thefa.com/competitions/thefacup/round-dates): qualifying round dates through 17 October 2026; first/second/third/fourth/fifth round proper; quarter-final, semi-final and 22 May 2027 final. **Only fourth qualifying onward is simulated** (64 fictional non-league clubs competing for 32 spots). Earlier rounds are in `FA_EARLY_QUALIFYING_DATES` as reference-only dates. Clubs from fictitious League One and Two enter round proper 1; fictitious Championship/Premier clubs enter round proper 3. All ties are generated, not imported real-world draws.
- [EFL — Carabao 2026/27 key dates](https://www.efl.com/competitions/key-dates/) and [2026/27 preliminary structure](https://www.efl.com/news/2026/july/29/carabao-cup-preliminary-round--all-you-need-to-know/): 92 professional fictitious clubs, preliminary 4→2, round one 70→35, round two 46→23, round three 32→16, round four 16→8, round five 8→4, two-legged semi-finals and 21 March 2027 final. Nine fictitiously designated Premier European entrants join in round three; this is **not** actual UEFA qualification data.

Actual cup knockout pairing data is **not** labeled OFFICIAL: generated draws use the clubs that survived *this simulated world*. The published dates are round scheduling windows, rather than claims about real kickoff assignments for imaginary teams. Early Carabao rounds are not yet northern/southern regionalised because invented clubs lack location data. The specific preliminary-club designation is also a DEV simplification.

## Sporting domain

- `DomesticCupRound`: unique ID, label, round date windows, new entries, number of legs and match decider (penalties-after-90 for Carabao single legs; extra time/penalties when appropriate).
- `DomesticCupSeason`: generated plan history, deterministic seeded draws, current round, champion. May progress only if every tie has a winner. Winners and staggered entrants form next-round participant set.
- Reuses Phase 6.3 `KnockoutRoundPlan`, aggregate-score rules and no away-goals tiebreak.

## Canonical runner

- `WorldSeasonRunner`: registers four domestic round-robin leagues plus FA Cup and Carabao; owns `ScheduledFixture` calendar states and unique `WorldMatchResult` records.
- Background fixtures use a deterministic, seed+fixture-ID strength-adjusted DEV goal resolver; the managed club still uses FastMatchSimulator and `MatchSnapshot` with real cup deciding-match contexts.
- `advance_until(date, protected_club_id=...)`: iterates in chronological order and stops before a fixture containing the protected club, so manual decisions and FastSim aren't skipped.
- Registering a deciding cup result can generate a new round, with new fixture dates; conflicts with fictitious league fixtures are repaired with rescheduling and ≥48h club rest. `SeasonCalendar` remains the canonical time/state source.
- Four league standings are **derived** from the ledger; no parallel conflicting score lists. Re-simulating an already played fixture is rejected.
- Atomic JSON save/load stores schema, full world calendar, competition edition definitions, result ledger, club strength inputs and exact cup bracket draw history. Validates IDs, fixture participant/stage integrity, duplicate records and state consistency on load.

## Sandbox

- Northbridge's `Calendar` and `Quick Sim / Continue` now include Premier DEV, FA Cup and Carabao Cup. `Continue` also progresses the three fictional EFL leagues.
- `Competitions → FA Cup / Carabao`: selectable bracket inspector for both cups with each known round, score, penalty details and kickoff/status.
- The old `Development Cup` bracket is **not part of the season**; it remains available as a legacy inspection-only tab. `Development Continental` remains an independent DEV harness, not yet covered by the English domestic Runner.
- Sidebar `Save world results (JSON)` and `Load world results (JSON)` persist/recover **competition results and draw history only**. This does NOT save player condition, tactics, familiarity, roster, or the FastSim RNG state and does not implement a full career save. Do not present it as such.

## Verification

- Four leagues: 380 + 552 + 552 + 552 = 2036 league matches.
- FA Cup simulated path: 32 + 40 + 20 + 32 + 16 + 8 + 4 + 2 + 1 = 155 matches.
- Carabao simulated path: 2 + 35 + 23 + 16 + 8 + 4 + 4 + 1 = 93 matches.
- Full domestic world = **2,284 matches**, one result each when the season is complete, zero calendar rest conflicts in the DEV reference seed. Two champions, no skipped managed matches.
- Full round trip `WorldSeasonRunner.to_dict/from_dict` and JSON atomic save/load tested; separate targeted UI rendering smoke in a headless X display.

## Deliberate exclusions

Real clubs and squads; club locations/region-constrained cup draws; earlier non-league qualification simulation; real first-season cup draws; real European competitions; full persistent player/career state; full season transition; real club-strength calibration beyond DEV tier bands.
