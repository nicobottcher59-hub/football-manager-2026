# Phase 6.7 — Full Season Integration (English DEV world)

## Purpose

Connect the independently working English leagues, domestic cups, UEFA
competitions, and EFL Trophy across **multiple seasons**. The result is an
inspectable *competition career*, not yet a complete football manager savegame.

All participants remain fictional. The 2026/27 base season retains its
existing provenance; **2027/28 and later fixture opponents and dates are
GENERATED**, not claimed to be published EFL, PL, FA or UEFA fixtures.

## English promotion and relegation

The 92 professional-club pyramid is maintained at **20 / 24 / 24 / 24**.

| Tier | Promoted | Relegated | Playoff field |
|---|---|---|---|
| Premier | Not applicable | Bottom three | None |
| Championship | First two + playoff winner | Bottom three | **3rd–8th (six teams)** starting in 2026/27 |
| League One | First two + playoff winner | Bottom four | 3rd–6th |
| League Two | First three + playoff winner | Bottom two | 4th–7th |

Championship 2026/27: fifth hosts eighth and sixth hosts seventh in **one-leg
eliminators**; their winners meet third and fourth in two-legged semifinals,
where **third faces the lowest-ranked remaining team**. Third and fourth host
the *second* legs. Winners meet in one final. Seven games total. League One and
Two each play two home-and-away semifinals and one final (five matches).

**Official rule reference:**
https://www.efl.com/news/2026/march/05/efl-statement--sky-bet-championship-play-off-format/

**Dates limitation:** the playoff kickoffs here are generated DEV windows after
the last league match, **not official 2026/27 fixture dates**. They are
scheduled through `WorldSeasonRunner` and the generic `DomesticCupSeason` /
knockout engine, so they generate 17 extra fixtures and can be persisted.
No away-goals rule is used.

League Two is a boundary of the simulated pyramid: its bottom two leave the
92 professional clubs and two newly generated clubs are promoted from an
**external National League interface**. No National League table or season is
fabricated; promotion of those two outsiders is a DEV assumption.

## European qualification

`EuropeanAccessPolicy` is configurable:

- Four default Premier Champions League league spots.
- Optional European performance spot; **off by default** because it is not a
  confirmed fixture-independent entitlement for an arbitrary season.
- One league Europa League route.
- FA Cup winner to Europa League, with fallback to next unallocated Premier
  club if already qualified.
- Carabao winner to Conference, with fallback to next eligible Premier club.
- UEFA Champions and Europa titleholder routes to Champions, and Conference
  titleholder route to Europa, when the winner is an English club.
- A club is allocated to at most **one** UEFA tournament.

Future real-country associations, complete 2027/28 UEFA access lists, UEFA
association coefficients, cup-specific exceptions and full pot/country draw
restrictions remain **explicitly deferred**. Foreign opponents remain fictional.
This is a configurable DEV allocation, **not a claim of a fully accurate
2027/28 UEFA access list**.

## New competition career domain

- `domain/season_cycle.py`: postseason validation, EFL playoffs,
  `SeasonReport`, `EuropeanAccessPolicy`, promotions/relegations, UEFA places.
- `domain/career.py`: `WorldCareer` (season worlds + immutable reports),
  `next_season_world`, JSON archive with atomic write and validation.
- `data/future_seasons.py`: independently generated home/away round robins,
  next-season date policies and cup round windows.
- `domain/world_runner.py`: opt-in EFL playoff creation only after each
  division has completed all 46 matchweeks; one canonical results ledger.
- `domain/domestic_cups.py`: configurable promotion-playoff seeding, preserved
  through serialization, in addition to existing generated draws.

Year transitions create new league and cup editions and unique fixture IDs;
clubs retain stable IDs. Strengths follow division changes without suddenly
turning a promoted club into the strongest team in the higher category.
The start of the next season carries the Northbridge squad and tactical
settings in the **live** DEV session, with offseason recovery. This is **not**
a fully serialized persistent squad lifecycle for all clubs.

`WorldCareer` requires all fixtures to be resolved before transition; it will
not silently invent playoff results. The 2026/27 world becomes an archived
edition, not an overwritten record.

## Sandbox: fast manual season testing

Launch from the repository root:

```powershell
$env:PYTHONPATH = "src"
python -m football_manager.dev_ui
```

On `Home`:

1. **DEV advantage: weaker rivals (no scripted wins)** is checked by default
   when you launch the normal Tkinter sandbox. Uncheck it for neutral testing.
   It lowers the **generated playable opposing squads** for Northbridge only,
   and does not alter permanent strengths, Fast Simulator calculations,
   competition allocations, or background match results. Even in DEV mode,
   upsets and elimination remain possible.
2. **Simulate entire season (DEV)** plays all remaining Northbridge fixtures
   through the **real FastMatchSimulator** and advances other results through
   the World Runner. Newly drawn rounds are included. The UI uses a worker
   thread, disables concurrent controls, and displays live managed-match count.
   It may take some time depending on the computer.
3. Inspect the tables, FA Cup, Carabao, UEFA and EFL Trophy, plus the generated
   Championship/League One/League Two promotion playoff brackets.
4. **Start next season** becomes available only after the full world is done.
   The managed club stays in the correct tier, even if it changes division.

The **Calendar** still shows V/E/D from Northbridge's point of view, with
shootout winners counted as victories, and only actual drawn fixtures (no
fixed `TBD` phantom entries). The generic EFL inspector and managed league
table follow the newly generated world edition.

## Result archives are not complete game saves

`Save current season results` / `Load current season results` use the single
`WorldSeasonRunner` JSON. `Save career results` / `Load career results` save
**all the world seasons and transition reports** via `WorldCareer`.
These contain competition data, calendars, results, draws, selected names
and strengths; they **do not restore all player condition, tactics, lineups,
injuries, finances, contracts or manager decisions**. When loading an archived
result timeline, the user should not mistake that for restoring a full manager
career. A complete save format is future work.

## Tests / acceptance

- Six-/four-team playoff seeding, aggregate legs and finals.
- Season cannot close with missing fixtures or missing winners.
- PL/Championship/League One/League Two promotion flow retains 20/24/24/24
  unique club IDs; two generated arrivals from the National League boundary.
- UEFA qualifiers unique with league/cup-winner fallback.
- New annual dates and fixtures, distinct from previous-year IDs.
- Completion of 2,959 world fixtures including the 17 EFL playoff fixtures.
- At least three consecutive world transitions without rest conflicts.
- JSON archive roundtrip, validation against corrupt timelines.
- DEV advantage only lowers playable opposition; real Fast Simulator still
  records every managed Northbridge result.
- Tkinter smoke: all five pages, worker completion, next season button.

The 2D spatial engine remains legacy/frozen. Real playable clubs and players,
foreign domestic leagues, regionalized lower-round cup draws and full squad
savegames are deliberately outside Phase 6.7.
