# TS-UI-07.01 - Youth Academy redesign, scout contract negotiations

## Patch baseline
Apply on top of TS-UI-06.02. Archive includes project-root relative paths.
Python world/senior match engine, Squad, Dressing Room and existing staff screens are not changed by this patch.

## Functional work
- Shared dynamic club identity through FMClubIdentity; generic photograph without embedded brand marks.
- Four youth views: U17, U21/Reserves, read-only U15 intake, Youth Scouts.
- Larger U17/U21 player management cards, filtered search, existing promotions and release actions.
- Academy/club scouting potential presented as approximate intervals and stars. Never send true PA as a field.
- Scouts use generic person icons without real/AI portraits.
- Youth scout appointment and renewal requires a salary/term/signing-bonus offer, acceptance or counteroffer.
- Accepted contracts persist on the existing YouthScout domain model; the separate academy recruitment allocation pays the signing bonus and monthly wages; rejected offers do not mutate game state.
- Direct hire_scout command is retired; manual watch and dismiss are retired. Reports update prospect confidence on the ongoing automatic scouting cycle.
- Prospect action is ONLY Sign to U17; U17 capacity, age and unique identity are enforced by Python.
- Resolve a preexisting persistence issue: GRAPH_VERSION was already 24 but MANAGER_STATE_VERSION was still 22. New sections follow GRAPH_VERSION. Existing records with section version 22 + valid graph 23/24 are recoverable, subject to the normal graph/index/session checks.

## Tests actually run (separate targeted runs)
- tests/test_ts_ui_07_01_youth_academy.py: 10 passed.
- tests/test_ts_ui_07_01_save_compat.py: 1 passed (accepted scout saved/loaded; historic mismatched section/graph marker recovered).
- tests/test_ts_23_2_u17_u21_layout.py and selected tests/test_ts_23_1_academy_polish.py: 9 passed (excluding slow unrelated historic scenarios).
- Selected tests/test_ts_23_youth_academy.py (initialization, read-only API, live local Python HTTP route, promotion): 4 passed.
- Selected tests/test_ts_23_youth_academy.py SQLite round trip: 1 passed after the version fix.
- Node syntax check of youth_academy.js passed; Python compilation of youth_academy.py and manager_career.py passed.
- Chromium offline browser using actual frontend JS/CSS and Python read-model data: widths 1680/1366/980/560/390; no JavaScript errors or horizontal page overflow. U17/U21/U15/scouting tabs rendered; mock transport verified low offer, counteroffer, revised offer and signing action; switched club identity to Brighton test fallback.
- Global combined historic pytest run attempted but TIME-LIMITED; NOT claimed passing.
- User Windows save and real full UI shell not tested in this environment.

## Installation
1. Back up current career save, especially if it was created with TS-UI-03.02 through TS-UI-06.02.
2. Stop Python development server.
3. Extract archive at football-manager-2026 project root preserving relative directories, overwriting existing files.
4. Restart `PYTHONPATH=src python3 -m football_manager.ui_shell`, then Ctrl+F5 in browser.
5. Verify U17/U21 move, U15 preview, Scouting -> recruit -> negotiate -> assign -> reports, Sign to U17 and save/reload.

## Notes
No new youth-save dataclass fields or new graph version are introduced. GRAPH_VERSION remains 24. The SQLite manager-section version is repaired to match graph 24, with backward compatibility for the historic mismatched wrapper.
