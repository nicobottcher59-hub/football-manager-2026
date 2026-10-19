# TC-E1.1 — Initial 2026/27 FIFA window reflow

## Scope

The standalone portable UI starts in an ephemeral fictional English 2026/27
career, on 15 August 2026. TC-E1 introduced the recurring international calendar
but only reprogrammed generated **future** seasons. This left the first season
with league and EFL Trophy fixtures inside the September/October, November and
March FIFA club breaks.

TC-E1.1 applies the same master to this initial DEV season:

1. Generate the normal Premier and published-date-slot EFL sporting fixture lists
   without international restrictions.
2. Reflow the Premier's affected matchweeks *as entire rounds* with the TC-E1
   ordered-round planner. This may move adjacent non-FIFA matchweeks so that
   the normal matchweek sequence remains chronological and keeps at least
   three days between matchweek anchor dates. Individual league fixtures may
   subsequently move when cup/UEFA priority requires a postponement. IDs,
   opponents, venue and round numbers are unchanged.
3. Reflow **only** unplayed EFL fixtures that occupy a FIFA club break. Preserve
   the individual EFL kickoff slots of unaffected matches. Some rescheduled EFL
   matches may be played out of round-number order, as with a real postponement.
4. Register domestic cups, UEFA and EFL Trophy against the same calendar. If a
   tournament's normal nearby window is fully inside a FIFA break, expand the
   search for a legal replacement while preserving its published source date.
5. Show the resulting dates in the existing Calendar UI. The small FIFA globe
   remains purely a visual marker. The fixture, score, knockout advancement and
   matchday navigation always read from the **same WorldSeasonRunner ledger**.

The international master distinguishes `club_break` (no club matches) from
`release_only` (competitions can run; player absence requires real call-up data,
not implemented yet). The 2026/27 fictional kickoff does **not** rewrite the
separate, packaged real Premier League fixtures or imported EFL slot data.

## Validation and known limits

- Initial fixture count: 2,620; FIFA violations: 0; 48-hour club conflicts: 0.
- Initial managed club date: 15 August 2026, unchanged.
- Northbridge's Premier round 7 is no longer scheduled for 26 September 2026.
  The original kickoff is retained and is visible as `original_date` in the API.
- Full synthetic league/cup/UEFA season simulation: 2,959 fixtures and results,
  without remaining FIFA or 48-hour conflicts (Linux test environment).
- A played fixture is never moved. Reflow of individual EFL fixtures fails
  without mutating the source calendar if no valid replacement date exists.
- We still lack actual senior national-team fixtures, selection of called-up
  players, and the full manager-save persistence system. Older saved result-only
  worlds are not retroactively migrated; they retain their historical dates.
- TC-E2 will address the separate staged-registration rollback problem.

## Tests

```powershell
python -m pytest -q tests/test_tc_e1_1_initial_season_fifa_reflow.py -ra
python -m pytest -q tests/test_tc_e1_international_calendar.py -ra
```

Windows acceptance: restart `INICIAR_INTERFAZ_WINDOWS.bat`, reload browser using
`Ctrl+Shift+R`, and inspect September 2026. The 26 September Premier match
should now be on a non-FIFA day. The FIFA globes remain small and informational.
