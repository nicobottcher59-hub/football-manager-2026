# Phase 6.6a + 6.6b - Fatigue, calendar fixes, UEFA and EFL Trophy

## Scope and provenance

This phase extends Phase 6.5b + 6.6. Four English leagues, FA Cup and Carabao are **not replaced**. Four additional competitions now share `WorldSeasonRunner`, `SeasonCalendar`, one fixture ledger and JSON persistence:

| Competition | Fictional participants | Primary fixture count | Next stages |
|---|---:|---:|---|
| UEFA Champions League | 36 | 144 (8 games/team) | Top 8 R16, 9-24 playoff, 25-36 out; playoff, R16, QF, SF, final |
| UEFA Europa League | 36 | 144 (8 games/team) | Same qualification bands |
| UEFA Conference League | 36 | 108 (6 games/team) | Same qualification bands |
| EFL Trophy | 64 | 96 (16 groups of 4) | Top two per group, R32, R16, QF, SF, final |

**Official**: competition format and season 2026/27 round windows. **Generated**: club IDs/names, strengths, group assignment, draw pairings, fixture times, moved DEV dates and all match results. The actual 2026/27 official UEFA draw and team participants are **NOT** embedded as generated results. Exact dates may move to honor fixture conflicts. The engine does not yet reproduce UEFA pot/country restrictions and all fixed bracket-lane pairing restrictions; the league-phase generator supplies distinct opponents and exactly 4/4 home-away (3/3 Conference), while knockout draws follow competition progression. EFL Trophy DEV north/south groups are randomized, not authentic English geographic assignments.

UEFA reference calendars:
- https://www.uefa.com/uefachampionsleague/
- https://www.uefa.com/uefaeuropaleague/
- https://www.uefa.com/uefaconferenceleague/

EFL Trophy reference: https://www.efl.com/ (2026/27 group-stage and invited U21 announcement).

## English club selection

The English clubs entered in the continental DEV competitions are placeholders, *not* automatically determined by actual official qualifications: five initial Premier DEV IDs into Champions (including managed Northbridge), two into Europa League and one into Conference. The remaining competitors are foreign fictional clubs. No real-club database was imported. Qualification rules for future seasons remain a Phase 6.7 responsibility.

EFL Trophy uses the **existing** 24 League One and 24 League Two fictional clubs plus 16 newly generated U21 invitational sides. Penalties decide a drawn group game: 2 points to the shootout winner, 1 to the loser, 3 for a 90-minute win, 0 for a defeat. The group structure comprises 16 groups split into 8 DEV north and 8 DEV south; the bracket stays regional in R32/R16. Knockout ties resolve without extra time through SF; the final permits extra time and penalties.

## Implementation

- `domain/staged_world.py`: `StagedWorldCompetition` holds participants, sporting league/group fixtures, group standings, qualifiers, `KnockoutRoundPlan` progression and serialization.
- `data/staged_2026_27.py`: fixture generation from published round windows; deterministic balanced league-phase game allocation, EFL Trophy four-team groups.
- `domain/world_runner.py`: registers and dates primary fixtures; simulates knockout/group results with appropriate penalty rules; generates winner-dependent stages; reschedules fictional league matches when necessary; preserves stages in schema-v2 JSON. Legacy schema-v1 saves are readable by the model, but the current DEV sandbox requires matching registered competitions.
- `dev_ui/session.py`: managed Northbridge plays canonical Champions fixtures rather than the disconnected 8-team Development Continental harness. `Continue` advances both domestic and continental background fixtures and applies actual day gaps for recovery.
- `dev_ui/app.py`: Calendar V/E/D indicator (including penalties), stage-aware result rows, UEFA/EFL Trophy calendar inspector and competition inspector with table, Trophy group selector and knockout history. No fixed conditional ghost fixtures.
- `domain/player_ratings.py`: physical readiness below 75 now has a meaningful, one-sided nonlinear ACT penalty. OVR remains unchanged. The existing FastMatchSimulator sees the adjusted current rating through its MatchSnapshot; no parallel fitness score or simulation engine was created.
- `dev_ui/session.py`: morale reacts to results but mean-reverts toward 72, preventing repeated wins from pinning starters to 100 indefinitely. Chemistry and position/role learning are unchanged.

## Verification and limitations

The complete generated 2026/27 world produces **2,942 fixtures/results** if every match is simulated: 2,036 domestic league games, 155 FA Cup, 93 Carabao Cup, 492 UEFA league-phase and Trophy group games, plus 166 UEFA/Trophy knockout legs. Four staged competitions and both domestic cups can crown champions. Full-game season rollover, worldwide player states, injuries and career savegames remain OUT OF SCOPE.

The legacy 8-club Development Cup and Development Continental inspectors are retained for regression tests, but neither adds fixtures to the managed season. Unknown future knockout opponents do not create fake scheduled rows. The competition runner introduces their actual fixtures once the necessary sporting results exist.

Testing: `python -m pytest`. Development sandbox: `$env:PYTHONPATH = 'src'; python -m football_manager.dev_ui`.
