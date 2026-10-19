# TC-E2.1 — Premier League official date-slot template (DEV)

## Decision

Use the already packaged **2026/27 official Premier League kickoffs** as the
calendar-date/time **reference**, rather than creating a synthetic sequence of
Saturdays and Wednesdays. Fictional DEV club identities, fixtures, results,
qualification and cup draws remain GENERATED; official English club pairings
are **not** imported into the playable world.

Published 2026/27 source:
https://www.premierleague.com/en/news/4675097 (19 June 2026, updated snapshot in
`premier_league_2026_27.meta.json`). The published list has 380 kickoffs, 38
matchweeks, and variable match days. Kickoff times later in the season are
provisional until TV selections and other fixture adjustments are announced.

## Implementation

- `data/premier_calendar.py` loads **all ten slots per round** from the
  existing official dataset and maps them deterministically to the fictional
  20-team round-robin. The output is marked `ScheduleSource.GENERATED`.
- 2026/27 opens on **21 August 2026**, the first actual published Premier
  kickoff, rather than the old fictitious 15 August opener. The DEV session
  binds its managed match and date to the canonical world kickoff at startup.
- For 2027/28 onward the 2026/27 reference is projected to the **same weekday
  near the same week** in the relevant year. New opponent pairings are drawn
  independently; *future* kickoff dates are explicitly generated projections,
  never presented as official future schedules.
- The initial fixture is generated first, **then** the shared FIFA master
  reprograms only conflicting unplayed matches, storing their original kickoff.
  Release-only tournaments do not suspend club fixtures.
- When FA Cup, Carabao, UEFA or EFL Trophy ties become known **as the season
  progresses**, the existing WorldSeasonRunner schedules those real ties and
  moves only clashing unplayed league fixtures. It does not regenerate the
  full fixture or rewrite matches already played. Every view reads the same
  fixture IDs and dates from WorldSeasonRunner.
- EFL kickoff-slot sources and schedules are unchanged by TC-E2.1.

## Validation

- Initial Premier calendar: 380 fictional league fixtures mapped to all 380
  actual 2026/27 kickoff slots; one unique league matchup per fixture ID.
- 2027/28 carries forward the same projected per-round distribution, including
  Friday, Saturday, Sunday, Monday and selected midweek dates.
- A future FIFA overlap is fixed only by moving affected fixtures, while
  retaining `original_kickoff`.
- The complete 2026/27 fictional world simulation finished **2959/2959**
  fixtures with **0 FIFA violations, 0 duplicated results and 0 detected
  48-hour rest conflicts**; advancing to 2027/28 produced 2562 scheduled
  fixtures and 0 detected initial FIFA/rest conflicts.

## Known limitations

1. 2026/27 has a published reference; later seasons project it without
   pretending to know future broadcaster selections or actual league fixtures.
2. The game is still a fictional DEV world. Do not mistake the underlying
   Premier official dataset's club names/results for a licensed playable league.
3. A real fully implemented manager career save, contract/player national-team
   availability and cross-country calendar constraints are future work.
4. **TC-E2.2 (transactional rollback)** is still pending. Cup/staged
   registration may partially mutate the runner if date assignment fails;
   this patch does not claim that is fixed.
5. Some long-running HTTP/Matchday regression suites can exceed the test
   environment timeout; individual targeted suites pass where recorded.

## Verification

```powershell
python -m pytest -q tests/test_tc_e2_1_premier_official_slots.py -ra
python -m pytest -q tests/test_tc_e1_1_initial_season_fifa_reflow.py -ra
python -m pytest -q tests/test_phase6_5_official_premier_schedule.py -ra
```

Run `INICIAR_INTERFAZ_WINDOWS.bat` and inspect Calendar in **August 2026**:
Premier fixtures should be spread over 21–24 August, including the opening
Friday, and later matchweeks will include weekends and selected weekdays.
The small FIFA globe remains read-only and does not displace fixture cards.
