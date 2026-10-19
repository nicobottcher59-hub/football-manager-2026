# UI-3.5 — Pre-match and post-match screen (2026-10-09)

## Scope and architecture

New sidebar-free `/portable/match.html` opens **in a second browser tab** when the daily Continue control changes to **Go to Match**. The same Python `DevelopmentSession` / `WorldSeasonRunner` / `FastMatchSimulator` drives all data. No game simulator, scheduling engine or 2D match engine has been added.

- `GET /api/match`: match preview for the pending managed fixture on the current world date; or the last manually completed match's report on that same day. No match on that day produces a truthful empty state.
- `POST /api/match` with an exact `fixture_id`: actions `match_tactic` (wraps the existing `apply_squad_command`), `reset_match_tactics`, `match_kits` (cosmetic only) and `quick_sim`.
- `quick_sim` runs `DevelopmentSession.quick_simulate()` on a deep copy, commits all resulting world/player changes only on success, and publishes a serializable report with **real** goals, assists, cards, substitutions, penalty-shootout kicks and real FastMatchSimulator team statistics. The second attempt to play the same fixture is rejected.
- `Continue` on the post-match report advances one calendar day through the existing endpoint and returns focus to the main game. On a second own fixture on the same date, it instead loads that pending match.
- Calendar auto-simulation is **unchanged** and can still auto-play the player's matches without visiting the separate pre-match tab.

## Match-only tactics

Temporary commands are stored in `UIRuntime.match_commands`, bound to a single fixture ID. For every read, a preview copy of the current session is modified using existing Python formation/role/team/player instruction/lineup methods. The main session and its habitual tactic remain untouched until the user plays the fixture. At play time, commands are revalidated and applied to a fresh deep copy; the **match snapshot** consumes that edited formation, XI, roles and team plan. After the result is committed, the original formation and lineup and the habitual tactic are restored in the clone, keeping fatigue, positional experience, morale, fixture result and world progression. No side-effectful tactical editing of the manager's permanent setup occurs in this tab. Unavailable players cannot start.

If an automatic Calendar simulation is started while the match tab is open, the current fixture may be resolved there first. The old match tab must then be refreshed; stale fixture IDs are rejected on writes. HTTP handler lock rejects match writes during active async calendar jobs.

## Cosmetic metadata and limitations

- Both eleven-player pitches, bench and unavailable list are built from the real registered teams/lineups and player state. The numbered shirts use existing DEV-assigned roster numbers when present; otherwise they have **provisional stable local DEV numbers** derived from roster order. No real kits or licensed artwork.
- The match snapshot contains a fixed DEV weather/ground/referee placeholder. The new screen labels `Cloudy · 18°C` for presentation only; it does **not** alter FastMatchSimulator. A stable hash of the fixture ID chooses a fictional English referee from six names per tier; English domestic cups use a combined pool; UEFA uses eight additional fictional referees. This assignment is likewise presentation-only, not an engine discipline input.
- Opponent roster is synthetic DEV data produced by the same existing opponent generator. There is no manager/personnel domain, so the screen says `AI manager` rather than inventing the name of an existing coach.
- Goal, assist, card, substitution and penalty-shootout data are emitted from `FastMatchResult` exclusively. The timeline adds only predictable half-time / full-time separators. No made-up injury, tactical foul, or penalty miss during open play.
- Stats supported: possession, expected goals, shots/on target, passes attempted/completed, pass accuracy, fouls, corners and disciplinary totals. **Tackles aren't captured in FastMatchSimulator**; do not show a fake tackle count.
- Injured/suspended players are identified before the match from PlayerState. FastMatchSimulator does not currently produce **in-match injury events**; the Injuries tab truthfully indicates that limitation. The event taxonomy is ready to add them once a real match-event source exists.
- `Immersive Match` stays explicitly disabled. Stadium capacities, attendance, a real staff directory, in-play penalties, and full persistent careers remain future features.
- The DEV world lives in server memory. Closing the server **does not save** the season.

## User verification

Install the incremental archive on top of UI-3.4.1 with the club-results/custom-confirm hotfix. Restart the Python launcher. On an own match day, click **Go to Match**; confirm a new browser tab without the main sidebar and with the real teams. In **Match Tactics**, make a one-off formation/role/instruction change and optionally a substitution, then return to pre-match. Set a temporary kit color. Click **Quick Sim** and inspect the large final score and the filterable chronological timeline. Check that the permanent formation/lineup in the main game is unchanged, while the fixture and player state have progressed. Click the top-right **Continue** to return to the main UI on the next day.

Regression scripts: `tests/test_ui35_matchday.py`, existing UI-3.4 progression tests, and historical Competition/Calendar/Squad suites. Browser smoke test verified the three screens in Chromium with payloads exported from the real Python simulator. A full repository-wide test run is not yet certified.

## UI-3.5.1 interface refinement

See `PHASE_UI_3_5_1_MATCHDAY_REFINEMENT.md` for the corrected kit previews, tactical drag-and-drop, result-event alignment and verification. This changes only the browser interface and docs/tests; match-state API semantics remain unchanged.
