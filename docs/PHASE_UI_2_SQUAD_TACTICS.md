# UI-2 — Squad, player role editor and team tactics (Python DEV integration)

**Status:** Implemented for developer validation on Windows; user acceptance pending.
**Prerequisite:** original Phase 6.7 repository + BOTH previous UI-1 incremental patches (React Dashboard and Portable SIN NODE).
**Branch suggestion:** `phase-ui-2-squad-tactics-python` (from the branch already containing UI-1).

## Approved screens / interactions

1. **Squad Overview** — dominant pitch with the current real Northbridge starting XI, contextual **OVR** and execution **ACT**, physical-condition bar, formation switch in place, one **In possession / Out of possession** switch. To the right: compact Morale/Condition/Chemistry/Form metrics, real bench, future Set Pieces panel. Under the pitch: players not called up (currently EMPTY with only 11 starters + 7 subs).
2. **Player Selected** — click a starting player; the right-hand panels are replaced with their real position, nationality, age, preferred foot, OVR/ACT, condition, positional familiarity, role fit, all compatible Python roles, **all 15 existing individual instructions**, and actual player attributes. Overrides can be inherited from the role or explicitly modified. Marking/pressing targets can be set using current domain `TacticalTarget` types. This is a real Python change within the DEV session.
3. **Team Tactics** — click **Edit tactics**. The pitch displays 11 unlabeled tactical discs instead of portraits/names/numbers. A **single** shared phase switch determines the pitch shape and the relevant set of settings; no duplicated mini phase previews or toggles. The 44 real Python team instruction fields are available across In Possession (18), Out of Possession (18), Transitions (5) and Match Management (3), with 11 presets and Custom. Tactical style scores are computed in Python.

Formation and starter/substitution updates go through `DevelopmentSession.set_formation`, `swap_starting_slots` and `swap_lineup`. Team instructions and presets use `DevelopmentSession.set_team_instruction` / `set_tactical_preset`; roles use `set_role`. Individual overrides use existing `Tactic.set_player_overrides`, `PlayerInstructionOverrides` and domain enum/target classes. No tactical rules, rating, fatigue calculation or simulation are duplicated in JavaScript.

## Schematic pitch preview — important limits

`frontend/public/squad/board.js` is a **UI-only visual function**: positions respond with CSS transitions to the phase, line widths/gaps, height, defensive compactness, selected individual positioning and other reasonable shape cues. Nonspatial commands still visibly indicate the change; **the image is NOT a prediction of the FastMatchSimulator's exact on-field positions**. The legacy spatial 2D system stays frozen. Python holds the authoritative instructions. Not all 44 controls currently have distinct consumers in FastMatchSimulator; merely changing a selector does not certify a measurable simulation effect. The adapter intentionally does not claim otherwise.

## Windows: no Node, npm, packages or internet needed

Double-click `INICIAR_INTERFAZ_WINDOWS.bat` from the repository root. It uses the Python already needed by the game and opens `http://127.0.0.1:8765/` in the default browser. Keep the terminal window open and use Ctrl+C to stop. Requires the same Python environment as the Tkinter sandbox; does not install new dependencies.

For debugging, from repository root:

```powershell
$env:PYTHONPATH = 'src'
python -m football_manager.ui_shell
```

**UI-2 static-resource route hotfix:** The launch URL `/` redirects to `/portable/` rather than serving the same document at `/`. This preserves the existing relative asset URLs in `frontend/portable/index.html` for both HTTP and local file use; they resolve to `/portable/styles.css`, `/portable/data/demo.js`, `/portable/portable.js`, etc., instead of 404 at the website root. `tests/test_ui_shell_squad.py` validates the redirect and the assets.

The Python stdlib `ThreadingHTTPServer` binds to **127.0.0.1 only**, checks Host and Origin, and serves UI-1's existing Dashboard from `frontend/portable/` and the new shared Squad/Tactics iframe from `frontend/public/squad/`. `GET /api/squad` retrieves a typed-shaped JSON view; `POST /api/squad` supports formation, preset, team instruction, individual role/override and swaps. Requests are validated by domain commands. Browser changes update only the in-memory instance of `DevelopmentSession` for this local process.

If the desired port is occupied, stop the other instance or close the process. **Do not open `frontend/portable/index.html` directly for UI-2**: file:// cannot access the Python API. The HTTP launcher is required.

### React/TypeScript compatibility

The original React + TypeScript Dashboard and sidebar remain in `frontend/src/`. Its Squad and Tactics routes now embed **the exact same portable Squad/Tactics implementation** as the Windows launcher, served by `frontend/public/squad/`. This is an interim shared web UI to avoid two diverging implementations while Windows can't install Node. If testing Vite with installed npm, run the Python local server first, then Vite; its proxy maps `/api` to `127.0.0.1:8765`. This is **not** an Electron package and the inner editor is plain JS/CSS, not yet a React-native component.

## Explicitly pending / not simulated

- **Home** is still labeled fictional UI-1 demo data. Continue only changes the Home displayed date (one day) and is **disabled** while inside Squad/Tactics; it does not advance `WorldCareer`, run scheduled matches or save anything.
- **Set Pieces:** UI panel deliberately says not yet supported. No assigned takers/captains are invented. Player attributes for set-piece-related skills exist, but their manual assignments do not.
- **Full manager saves:** roster/tactics, health and modifications are **in memory only** and **are lost when the local server exits**. `WorldCareer` results JSON does not persist a full manager save. This increment does NOT replace it or introduce fake persistence.
- **Real club/player photos:** not included. The development roster remains fictional, and player cards use compact illustrated shirt icons, not generated celebrity portraits.
- **Full daily progression, injuries event inbox, youth/regens/real database, commercial management:** out of scope.
- **Windows visual acceptance:** still needed; Chromium screenshots could not complete in the authoring environment, but API/domain and JS tests were run.

## Validation

```powershell
python -m pytest -q tests/test_ui_shell_squad.py
node tests/ui/test_board.cjs                 # optional for developers who HAVE Node
python -m pytest -q tests/test_phase6_0_development_ui.py tests/test_tactics.py tests/test_phase6_0b_role_ovr_familiarity.py
```

`node` test is for CI/author verification, **not required for Windows use**. The `INICIAR_INTERFAZ_WINDOWS.bat` script uses Python exclusively.

## Next

- User validates spacing, scroll behavior, tactical shapes, role/individual controls, swapping and formation changes on Windows.
- UI-2B or next approved update: persistent manager/session read models beyond the DEV sandbox, Home/Calendar real data and a safe one-day Continue command (must gate manager fixtures and avoid duplicate fixture simulation). Retain the same user-approved three-view model.
