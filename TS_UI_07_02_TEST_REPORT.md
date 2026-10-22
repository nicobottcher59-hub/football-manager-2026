# TS-UI-07.02 - Youth Academy identity / player-row polish

## Baseline
Incremental update to **TS-UI-07.01**, not a replacement game distribution. The three changed source files match exactly the original 07.01 ZIP before applying this update.

## Changes
- Tables: each team's visual name and any available crest comes from the shared FMClubIdentity catalogue, resolved by immutable club_id. The managed-club row is highlighted using the same club ID. No string substitution of Northbridge, Sunderland, or another specific club appears in youth JS.
- Match opponents: youth read model now includes `opponent_club_id` alongside `opponent`; the latter and the scores are not changed. This lets the same visual mapping work for next match and results.
- Hero: the club-name line is independent of the section title and supports catalogue short names and long-name wrapping. No text or crest is baked into the background photograph.
- U17/U21: player cards show existing cumulative recorded minutes, recent development delta, and the same approximate potential range. They have denser four-part stat blocks with the original squad portraits.
- Actions: blue (U17/U21), green (first-team promotion), red (release). When age makes U21->U17 illegal, the UI shows a passive "U17 age limit" indicator; Python enforcement is unchanged.
- Sidebar and right-side cards continue to inherit dynamic club palette (TS-UI-07.01), without overriding shared theme architecture.

## Verified results
- `PYTHONPATH=src pytest -q tests/test_ts_ui_07_02_identity.py tests/test_ts_ui_07_01_youth_academy.py tests/test_ts_23_2_u17_u21_layout.py`: **18 passed**.
- Five additional core academy regressions, run individually via `-k`: **5 passed**, covering academy roster formation, youth fixture round-robin, player promotions, read-only model, and the live local Python youth API.
- `node --check frontend/portable/youth_academy.js`: **passed**.
- `python -m py_compile src/football_manager/services/youth_academy.py`: **passed**.
- Offline Chromium loaded actual JS/CSS, Python read-model, shared portrait code and club catalogue at viewport widths 1680 / 1366 / 980 / 560 / 390. **No horizontal page overflow or JavaScript errors.**
- U17 and U21 own table row displays Sunderland AFC with the supplied visual crest even though internal Python ID/name is `northbridge`/`Northbridge FC`. Both rows are joined by club_id.
- Switching to a *different real academy* in the Python world also updates its own-row name correctly. A long unmapped club name at 390px wraps without page overflow.
- Browser mock-action test verified that U17 scout signing and youth-scout negotiation controls still send their intended payloads. These are not claims that the user's Windows save was tested.

## Scope and limitations
- No world/team ID rewrites, saved-session migration, competition-result mutations, or gameplay rule changes.
- Full long-horizon regression suite was not run in this 07.02 pass; directed regressions listed above were run successfully.
- The user's current local save is not accessible here and should be checked after installation.
