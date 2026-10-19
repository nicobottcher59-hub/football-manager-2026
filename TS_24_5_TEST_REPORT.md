# TS-24.5 - Autonomous 92-Club Market & Formation-Aware Squad Planning

## Scope

This is an incremental enhancement of the TS-24.4 professional market; it
uses existing player valuations, agent interest, professional contracts,
club accounts, persistent transfer records, and the tactical formations
already registered for England's 92 league clubs.

### Squad planning

- A club's **primary tactical formation** determines two sets of 11 roles,
  plus a desirable third goalkeeper: 23 target assignments in total.
- A bipartite assignment solves those jobs using **player familiarity** and
  overall rating. A dual-position player may cover only one job at a time.
- The planner distinguishes *uncovered starters*, *uncovered reserves*,
  *extra keeper*, and discretionary upgrades. It never describes an injured
  contracted professional as a permanent positional vacancy.
- Sellers must retain starting positional coverage. A low-depth GK cannot
  be sold when that leaves a club with fewer than two true keepers.
- Clubs may strengthen weak positions only after examining their roster's
  actual coverage, wage ceiling, available cash and asking price.

### Autonomous inter-club market

- At calendar month boundaries, the AI reviews the window that just ended;
  the first supported open months are **January, July, August**.
- The same pre-existing valuation, asking-band, player-consent and salary
  calculations are used by all clubs. No money or players are invented.
- Between rival AI-owned clubs, transfers settle atomically, updating player
  ownership, professional contract, budgets, transfer history and any
  already-existing sell-on payable. The world transaction undo journal
  reverses the operation if a later step fails.
- Teams can make at most two purchases per market review, and the world
  processes at most 28 completed AI transfers in a window month. A second
  recruitment pass lets earlier sellers try to restore newly vacant backups.
- The manager's club is never moved or paid on behalf of the user. Rivals
  may submit actionable pending offers for its players; those bids reserve
  the AI buyer's funds until their expiration.
- Scouting shows recent AI-to-AI transfer history, and disables new offer
  submission outside supported transfer windows (ongoing talks remain viewable),
  while Other Leagues club detail pages expose squad-planning coverage.
- Cached previews for managed upcoming opponents rebuild if the rival sells
  a player included in that preview, avoiding invalid match selections.

## Save compatibility

Unchanged complete-career and SQLite schema version **15**. No migration and
no new persistent dataclass fields. Deals use the established transfer event
records and contracts. Loading a TS-24.4 game remains supported.

## Verified in development environment

- 8 focused squad-planning/market tests, including all 92 lineups, shortage
  detection, no duplicate assignment, window restrictions, journal rollback,
  accurate money/contracts, pending manager-bid budget reservation, closed
  market months, stale opponent lineup repair, and frontend contracts.
- Existing TS-24.4 and TS-24.3 tests: 42 cases passed in a combined run
  prior to the final lineup safety change; the new targeted lineup test
  passed after that change.
- Full integrated daily progression from **2026-08-21 to 2026-09-02**:
  three managed and 141 background matches simulated, **16 completed rival
  transfers**, and complete in-memory career graph save/restore (190,015
  nodes) with unchanged transfer history and valid club registries.
- Full SQLite save/load of that progressed career with completed AI trades:
  verified the same transfer records and valid registered players.
- Eight earlier daily/calendar progression tests passed after the cached
  lineup-repair change (excluding the separate entire-season stress test).
- Market/economy **30-month** dry stress (no league games or season changes):
  **142 completed transfers**, 0 uncovered starter spots across the 92
  clubs, 5 uncovered reserve slots in total, every team retaining at least
  two genuine goalkeepers, and roster sizes between 21 and 23. It is NOT
  evidence of a complete 30-month sporting simulation.
- Python syntax and frontend JavaScript syntax validated. Full installation
  verification is provided by a standard-library SHA-256 package checker.

## Explicit limitations

- No native Windows gameplay test was run here.
- No complete 5/10/20-year multi-season competition/promotions simulation
  has been run for this patch. That sporting/economic calibration remains
  important before treating the balance as final.
- Player-agent negotiations between AI clubs are evaluated by the existing
  interest and demand functions, rather than through an interactive agent UI.
- No auto-leases/loans, player swaps, unsigned professionals, January
  precontracts, or legally detailed division-specific transfer deadlines.
- Clubs initially have two true keepers; the third-keeper objective may
  remain unfilled without eligible sellers or academy graduates. The
  model does not generate artificial keepers to fill a target.
