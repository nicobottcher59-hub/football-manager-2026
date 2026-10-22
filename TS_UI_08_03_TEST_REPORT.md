# TS-UI-08.03 — Squad identity regression & player-club chrome

Base: apply this incremental patch after **TS-UI-08.02**. Does not alter game save schema, simulation engine, or other approved UI layouts.

## Corrected

- Squad iframe: fixed shared identity fetch to absolute `/portable/data/club-identities.json`; maintains Squad's existing `view.identities` fallback. This restores Sunderland AFC name, crest, stadium hero, primary team red, home jersey, and correctly reads future ID-keyed resource overrides.
- Scouting: player club crest shown in the roster row, recommendations, and player detail header. Inspector uses the player's own club colour independently of manager's navigation colour.
- Transfers: selling/current club crests in player-search listings, open deals, and negotiation header; negotiator hero uses the current player/seller club colour by stable club ID.
- Shared identity: safe CSS colour, existing explicit palette first; if imported crest has no configured colour, sample local image predominant saturated colour. Safe fallback for missing/unreadable/cross-origin image.
- Scouting and Medical Centre: global left sidebar and active navigation use the manager club palette and visually match Squad.
- Staff/Training/Medical data loads refresh shell manager club identity from Python payload.

## Regression results (Oct 22, 2026)

- `PYTHONPATH=src python -m pytest -q tests/test_ts_ui_08_03_club_chrome.py tests/test_ts_ui_08_02_scouting_assets.py tests/test_ts_ui_08_scouting_hub.py -x` => **12 passed**.
- `node --check` => **pass** for 6 affected JS files.
- Browser: real HTML/CSS/JS + Python read model, transport mocked only because Chromium blocks localhost. Restored Squad name Sunderland AFC, crest, stadium banner, red-and-white kit asset and `#c72838` theme, no JS exceptions.
- Browser: selected Alderwick FC (separate player club) with an imported GREEN test crest and no explicit palette: both Scouting inspector and Transfers negotiation coloured `#16a545` with their actual team crest. Global Sunderland theme stayed `#c72838`, Scouting/Medical sidebars used same gradient as Squad, no JS exceptions.
- **Limitation:** Chromium-to-Python localhost end-to-end browser test is blocked by host (`ERR_BLOCKED_BY_ADMINISTRATOR`); Python read models and browser rendering were checked separately. The user's actual Windows career remains untested. Long historical simulations not rerun.

## Install

Stop Python, back up saved career, unpack archive into repository root `football-manager-2026`, preserve folder structure, replace files, restart Python, refresh browser with Ctrl+F5. This patch assumes TS-UI-08.02 is already applied.
