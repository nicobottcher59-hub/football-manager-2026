# TS-28.3 + TS-28.4 — Technical and game-design notes

## Recognition model
- Award candidates: verified official season player statistics with >=3 appearances and >=225 minutes. No potential/GRL in winner calculations. Repeatable deterministic tie breaks.
- Scopes: domestic tier leagues and recorded European club competitions, plus a global award over recorded competitions (only within the simulated game universe, not all football worldwide).
- Categories: best player, best U23, goalkeeper, top scorer, assists leader and a formation-aware season XI where eligible players exist. The global Golden Ball is one per completed season.
- Partial statistics: no awards if explicitly marked incomplete. Zero or incomplete coverage does not synthesize winners. Awards only after certified season end and stored as immutable certificates; no silent recomputation after transfers.
- Multi-club seasons: if match attribution proves more than one club, award may be player-linked but has no guessed single club. Club career record leaderboards similarly exclude unpartitionable multi-club totals.
- Historic records begin at the first tracked season. Existing careers do not get assumed earlier awards or fabricated rating snapshots.

## Ratings and graph size
- Opening factual snapshot; actual year-end checkpoints. Current live observation added only at read time, without writing or claiming it was an end-of-year value.
- Ten indicators: technical, mental and physical mean; passing, finishing, tackling, vision, decisions, pace and stamina. This is not a recording of all 40 attributes or a replacement for the current player profile.
- Each snapshot stores one short fixed-length tuple of numeric values; fixed indicator names are in code. Maximum 80 snapshots per player to bound graph size.
- SQLite manager state and JSON graph v22; explicit migration preserves all prior graph components, including team instructions, finances, clubs and TS-25 conversations.

## Club Info provenance
- Current live identity, league and tier from registered world; roster from active club players; salaries/caps from staff registry; finance estimates from existing ClubFinances.
- Ground/city/founding facts are displayed only if present in underlying Club data; most fictional clubs have no such data.
- Provisional hiring cap is **not** the level of constructed club facilities. Facility level upgrades await TS-29.
- No separate club-history ledger; pages reuse TS-28.2 cross-links, fixtures, league reports and transfer/retirement history.

## Limitations
- No new xA/tackles statistic computation. No retroactive historical match replays.
- Awards have no additional hidden gameplay boost or potential/ability change.
- Multi-season 20-year regression, full Windows visual check and global game-balance validation remain outstanding.
