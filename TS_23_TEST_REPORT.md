# TS-23 — Test report

Base: TS-21.4/21.5, Python-only installation.

- Initial world: 92 academies, 1,840 U15 preview records, 1,656 U17 and 1,656 U21 player records; 4,072 youth fixtures scheduled.
- First full live season smoke: 51 managed fixtures, 3,394 finished youth fixtures, then promoted into 2027/28. Season and identity validation succeeded.
- **Focused TS-23 suite: 10 passed.** Python directed youth testing covers roster integrity, country-specific quarterly report creation, scouting/academy promotion, historical graph migration (v9->10), actual loopback HTTP commands, yearly U15 intake, and SQLite save/load.
- TS-21/TS-22 directed regressions: 6 passed.
- Python compileall / JavaScript syntax checks passed; user install requires no Node.
- Headless Chromium browser navigation blocked by environment policy (`ERR_BLOCKED_BY_ADMINISTRATOR`). Not a passing UI E2E.
- Extensive historical regression and native Windows execution were not completed here.

For the verified final test count, refer to the linked delivery report and the actual pytest output (never infer a result from a timed-out run).
