# TS-28.2 | Career History and Linked Profiles

## Scope and provenance

This update extends TS-28.1. Historical facts are read from the existing manager-career world, match records, season statistics, completed negotiations, loans, retirement archive and season reports. No separately maintained fabricated football history is introduced.

### Delivered

- `/api/history/player/{id}`: player year-by-year statistics, verified match-season clubs, completed transfers, loans, titles recorded at confirmed season rollover, retirement information.
- `/api/history/club/{id}`: club seasons, actual league positions, promotions/relegations, trophies, results with pagination, completed transfer ledger and recorded retirees.
- `/api/history/competition/{id}`: archived editions, confirmed champions, standings and results (paginated).
- `Career History` screen within the portable UI: deep links, clickable player/club/competition names, and back navigation.
- Entry points from squad profiles, rival club profiles, Scouting, competitions, news, Inbox, Training, Medical Centre and Dressing Room.
- `Club Info` now displays a club's verified sporting history; institution/facilities UI remains future TS-28.4 work.
- The existing retirement archive remains accessible. This change does not replay or delete retired players.
- New `player_season_clubs` ledger records the clubs a player **actually appeared for** in verified match statistics. Multiple clubs per season are supported.
- New `player_honours` ledger captures season-end champion registrations at a completed transition, without retroactively attributing trophies.
- Save graph and manager_state version **21**, with explicit migration for v20 and earlier graphs.
- Verified Home news articles link to their known subjects where IDs exist.

### Strict limitations

- Past player appearances and goal totals retained by older versions remain visible, but past season **club attribution** is not inferred when no original participation record exists.
- Trophy winners for previous seasons come from existing SeasonReports. **Player trophies** are first recorded when the career completes a season using TS-28.2.
- Transfer dates use the **player agreement date**, because the exact registration date is not stored.
- Transfers are listed only when the negotiation and player consent are both completed. Unsupported data (e.g. retroactive full awards) is not manufactured.
- History is a read-only screen and does not alter progress or football results on navigation.
- For closed seasons, league tables show confirmed positions. Historical points are not manufactured if absent from reports.
- No new club institutions, facilities, coaches, awards, nations, real clubs, or competitions were invented.

## Tests (executed)

| Suite / flow | Confirmed result |
|---|---|
| TS-28.2 new tests (`tests/test_ts_28_2_career_history.py`) | 6/6 passed |
| TS-28.1 verified news regression | 7/7 passed |
| TS-27 match preparation and AI regression | 13/13 passed |
| TS-26 club support regression | 9/9 passed |
| TS-26.1 professional scouting regression | 11 original cases passed, one final case passed after aligning obsolete hardcoded save-version expectation; 12/12 cases covered |
| TS-25.2 conversations regression | 10/10 passed |
| Syntax checks | `python -m compileall` and `node --check` for changed JS passed |
| Real match | Fresh career, played managed match, club and player appearances recorded correctly |
| Save graph roundtrip | v21 roundtrip preserves verified links, stats, and career records |
| Legacy graph | Synthetic v20 graph with no new fields loaded with empty new ledgers and validated |
| Legacy SQLite v20 | **Real TS-28.1** sqlite career slot written with old code, loaded with TS-28.2, saved as v21 and loaded again; validated |
| HTTP requests | All three profile endpoints returned validated JSON; missing profiles and negative offsets rejected; assets served |

The full historical regression collection in one invocation and a 20-season run were **not** completed. Visual and interactive play testing on Windows is also **pending**. Do not treat this as a certified release in those areas.

## Compatibility / installation

Apply **only on top of TS-28.1**. Back up existing saves before using a new schema version. Copy the patch contents into the game root, preserving paths, and accept replacement. Do not delete `.git`, existing user saves, or the executable launcher. No existing files need removal.

## GitHub Desktop

Branch: `feat/ts-28-2-career-history`

Summary: `feat: TS-28.2 persistent career histories and linked profiles`

Description: `Introduce verified player, club and competition histories with retired-player profiles, archived seasons, transfers, trophy records and cross-linked navigation. Persist match-verified player-club affiliations and confirmed season-end honours, migrate SQLite careers to v21, and extend Club Info without fabricating historical facts. Includes targeted regressions and API tests.`
