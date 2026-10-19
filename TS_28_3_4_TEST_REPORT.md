# TS-28.3 + TS-28.4 | Player development, verified awards and Club Info

## Scope

This is a single incremental update on top of **TS-28.2.1**. It does not replace the simulation engine, scouting, medical centre, staff model or existing archive/navigation.

### TS-28.3: progression, recognition and records

- Annual **actual** OVR and selected attribute checkpoints persist in `FootballWorld.rating_history`; read-only player profiles append the current live rating rather than pretending it is an old checkpoint. Only ten expressly labelled indicators are persisted per checkpoint, to keep multi-decade save graphs bounded.
- Certification of awards happens **once** at `DevelopmentSession.begin_next_season`, after a legitimate completed season. Ratings, minutes, assists, goals and (for goalkeepers) clean sheets are taken from the actual season statistics ledger. Ability, GRL, potential and reputation do *not* determine the awards. Tie-breaks are deterministic.
- Award scopes: the four professional league competitions, Champions League / Europa League / Conference League when their played-match data supports a winner, and one global **Golden Ball** for the simulated world. League/UEFA awards include Player, Young Player, Goalkeeper, Golden Boot, Top Assists, and a position-based XI when enough players qualify.
- Awards are withheld if detailed season coverage was explicitly marked incomplete or there are insufficient verified qualifying appearances. When one player represented more than one club in a season, an individual award can still be earned, but no **single club** is guessed.
- Persistent certificates remain visible in player/club/competition history after transfers and retirements. Home news announces only confirmed season awards; there are no invented announcement days.
- Career leaderboards aggregate actual performance over recorded seasons. Club leaderboards exclude multi-club seasons when the ledger cannot correctly split statistics; no fabricated retroactive records or unimplemented xA/tackles.

### TS-28.4: Club Info

- Show canonical club name, country, current professional tier, league, tactical identity, simulator strength (distinct from club reputation), the seven strongest **current** players, current budgets, staff counts and their provisional hiring caps.
- Show existing training-quality data with its provenance. Training/medical/youth facility upgrades remain **future TS-29** functionality. The current hiring limits are provisional and are *not* presented as verified physical installation levels.
- When a fictional club has no stored city, stadium, founding date or stadium capacity, the UI explicitly displays **Not recorded**, without generating fictional institutional facts.
- Integrates with existing trophies, seasonal positions, fixture archives, verified transfer ledgers and retired profiles from TS-28.2.

### Persistence and compatibility

- Manager state and graph format **v22**; explicit migration from **v21** injects empty award and rating ledgers and makes one factual *current* baseline rating observation. Older seasons are not backfilled. v21 games open normally through the versioned loader.
- Fresh careers capture an initial rating observation; the next observation is at the real season closure. Existing players are not snapshotted a second time at the following July opening. New players receive their own first point on entry.
- The maximum per-player rating history is 80 compact points. No separate duplication of full player attributes. All historical awards and positions are server-derived; opening pages does not modify the game.
- No files need deletion, and this patch does not contain `.git` or saved careers. Back up local save files before migrating.

## Confirmed tests

| Verification | Result |
|---|---|
| New TS-28.3/28.4 suite, including no fabricated clubs/awards, multiclub non-attribution and graph migration | 8/8 passed |
| TS-28.2.1 UI-hotfix regression | 3/3 passed |
| TS-28.2 historical archive regression | 6/6 passed |
| TS-28.1 career news regression | 7/7 passed |
| TS-27 targeted opponent/set-piece/AI/graph tests | 5/5 passed |
| TS-26.1 targeted scouts/quality/graph tests | 3/3 cases marked passed; long runner exit unconfirmed |
| Real v21 SQLite career loaded, saved as v22, then loaded again | Passed |
| Isolated Chromium rendering of actual player, club and competition profiles; chart selection | Passed; no page errors |
| JavaScript syntax (`node --check`) and Python compile | Passed |

**Not certified:** a complete 20-season run, a complete uninterrupted all-suite regression, or a visual/playable check on the user's Windows machine. An older combined test runner exceeded the local time limit, so this report distinguishes individual confirmed cases from any unconfirmed full-run exit.

## GitHub Desktop

- **Branch:** `feat/ts-28-3-4-awards-club-info`
- **Summary:** `feat: TS-28.3/28.4 career awards, progression and club info`
- **Description:** `Add persistent OVR/attribute checkpoints, verified seasonal league and continental awards, a simulated-world Golden Ball and all-time records. Complete read-only Club Info with identity, finances, leading players, staff limits and institutional data provenance. Integrate results with linked career profiles and Home news; support v21-to-v22 save migration without fabricating earlier history.`
