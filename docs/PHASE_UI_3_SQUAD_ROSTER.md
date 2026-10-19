# UI-3 — Squad roster, tactical navigation and rating consistency

**Status:** implementation ready for Windows acceptance (not yet committed).  
**Suggested branch:** `phase-ui-3-squad-roster-tactics-polish`  
**Starting point:** committed UI-2 with the UI-2 404-assets hotfix applied (and both UI-1 patches already present).

## Approved user experience

The app now separates **Squad** and **Tactics** as genuine navigation destinations, while preserving the same Python development session and the shared portable iframe:

- **Squad:** a spreadsheet-style full roster table with three views (General, Attributes, Season Stats), a frozen player-name column, scrollable columns, fixed table headings, position/status filters, search, ascending/descending sorting per column, and a contextual expanded player row. Full technical, mental, physical and goalkeeper attributes (when present) remain queryable via the Attributes group filter.
- **Expanded player:** current OVR/ACT, condition, morale, match sharpness, identity, current status, **dynamic positional familiarity** for primary, secondary and explicitly learned positions. Includes effective score, stored/peak familiarity and observed minutes; these are **read directly from `Player.positional_familiarity`**, not hardcoded to the interface.
- **Player actions:** shirt number assignment (unique 1–99), and one of available/transfer-listed/loan-listed/untouchable, are **UI-development-only metadata in `UIRosterAdmin`**. They survive navigation and change during this local server process, but have **no effect on transfer negotiations, domain persistence or actual match registration**. Contract negotiation, training-focus assignment and player chats are visibly disabled. There is no implied missing engine feature.
- **Tactics:** the existing XI/formation with swaps, individual player roles and **all 15 instructions**, and the editor for **all 44 team instructions** remain under **Tactics**. In Tactics the single possession-phase selector controls the lineup positions or schematic discs; the Edit Team Tactics button swaps to the collective editor, and Back to Lineup returns without changing navigation section. No duplicate in/out possession miniature selector.
- **Scale:** the existing card/field layout is preserved while card dimensions, pitch height, text and control sizes grow at standard desktop widths. The goal is to eliminate the previous "miniaturized" appearance without changing the approved composition.
- **Rating convention:** OVR/ACT and other ratings shown by the UI use one decimal, with a comma (`88,5`). Sorting uses raw numbers and is not lexicographic. Attributes (1–100 ints), shirt numbers, match counts and calendar dates are not necessarily ratings and retain their native units.

## Source-of-truth / unavailable features

UI-3 reads roster membership, identity, primary/secondary positions, contextual and base ratings, positional familiarity, attributes and physical state through `squad_read_model(DevelopmentSession)`.

**Do not invent data.** The current `Player` domain has no persistent transfer value, contracts, independent happiness model, or roster shirt numbers. The FastMatchSimulator produces per-match statistics including xG, but the DEV session lacks a **player-by-season ledger**, and xA is not computed. Season Stats therefore contains the desired sortable columns (appearances, starts, minutes, goals, assists, clean sheets, xG, xA, pass %, shots, discipline, average match rating) populated with `null`/"—" and a clear warning. Nothing is populated with invented zeros. The dedicated season-stat aggregation is a separate future development task.

UI-2 limitations remain: DEV in-memory only; Home still uses labeled UI-1 demonstration values; Continue does not advance the Python world; set-piece taker assignments are not implemented; no genuine player portraits have been imported. The legacy spatial 2D engine is not reintroduced.

## Implementation and assets

- `frontend/public/squad/roster.js` / `roster.css` — new sortable roster table and player expansion (plain browser JavaScript with no npm requirement).
- `frontend/public/squad/squad.js` / `squad.css` — existing tactical code reused, with the three tactical interactions grouped under Tactics and desktop sizing adjustments.
- `src/football_manager/ui_shell/models.py` — richer typed-shaped roster read model; validated UI-only admin commands; original domain commands unchanged.
- `src/football_manager/ui_shell/server.py` — server-local admin state, separate from career/roster domain.
- `frontend/portable/portable.js` and the existing React Dashboard — navigation and single-decimal presentation updates. React still embeds the **same** shared development surface: no second conflicting tactical implementation.

## Installation and tests

Create branch from the already committed UI-2 hotfix state, extract the incremental patch **over the repository root**, and launch `INICIAR_INTERFAZ_WINDOWS.bat` with the game's installed Python. The local app opens at `http://127.0.0.1:8765/portable/`. A server window must remain open. Node/npm, network, Electron and build tooling are not needed on Windows for this user testing phase.

Suggested validations:

```powershell
python -m pytest -q tests/test_ui3_roster.py
python -m pytest -q tests/test_ui_shell_squad.py
python -m pytest -q tests/test_phase6_0_development_ui.py tests/test_tactics.py tests/test_phase6_0b_role_ovr_familiarity.py
```

Optional (only on an environment with Node): `node tests/ui/test_board.cjs`.

The tests check source-of-truth ratings, dynamic familiarity updates, no fake season data, unique shirt numbers, valid development-only transfer statuses, original UI-2 tactics and server/static assets. Portable-browser visual/manual verification is still necessary on the user's Windows PC.

## Pending later phases

Player-season stats aggregation (incl. definition of xA), persistent manager saves, real player imports/photos, real contract/transfer/training/conversation systems, set-piece assignments and one-day WorldCareer Continue. These should be implemented in their own future increments after domain planning, not faked in the UI.
