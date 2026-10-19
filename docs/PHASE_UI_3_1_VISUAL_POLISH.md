# UI-3.1 — Visual Polish, Player Portraits & Live Home (development session)

## Scope

- **Continuation of UI-3**, not UI-4. Branch: `phase-ui-3-1-visual-polish-portraits`.
- The approved layout and desktop zoom are preserved; this pass changes visual hierarchy, not the overall scale.
- Squad rows and expanded profiles display deterministic, **illustrated placeholder portraits keyed by player ID**. They are not real people. Nationality is read from `player.identity.nationality` and includes country styling where supported. Imported licensed/authorized face packs can replace the illustration source later without changing the Python model.
- Expanded profile separates **profile / OVR and ACT / condition, morale, sharpness and other recorded facts / dynamic positional familiarity / leading real attributes / actions**. The unimplemented operations remain disabled or plainly labeled, rather than faking results.
- Four-tier colors in Squad are presentation only: under 60 neutral, 60–74.9 amber, 75–84.9 teal, and 85+ green. OVR and ACT keep one decimal comma (e.g. `85,2`). Rating computations are unchanged.
- Tactics' lineup uses the same placeholder portraits and more layered panels; **collective tactical edit mode keeps anonymous discs** and a single on/off possession view toggle.
- Home no longer shows the UI-1 eleven or fictitious morale and condition. It calls the same local **`GET /api/squad`** read model as Squad/Tactics. After a lineup change and navigation back to Home, it re-reads the session so the formation, 11 portraits/names/OVR, opponent and status indicators are consistent. The shared `FMTacticalBoard` helper positions players; it is an illustrative visualization, not the deprecated 2D simulator.

## Truthfulness and limitations

- In the current Python DEV session the starting date is **2026-08-15** and Northbridge faces **Riverside Athletic**. Changes to the current development session are reflected immediately on Home; **the session is not saved on application restart**.
- Home's **League Table, club presentation metadata, inbox and editorial stories are still UI-1 demo displays**. Hero league points/rank and recent match form are shown as unavailable rather than implying the demo standings are live. Demo data is visually identified.
- Python's `next_match_label` provides the opponent, but no verified kickoff time or venue; the UI uses `TBD` rather than leaving the old 2027 details.
- **Continue does not advance the world or the date**. Clicking it explains that daily progression is pending. There is no simulated date divergence between Home and Tactics.
- Dorsal and availability flags are temporary development UI state only. Happiness, transfer negotiations, contracts, training, dialogue and accumulated season stats remain future systems.
- React/Vite source remains an earlier development prototype; the Windows `.bat` starts the maintained **portable Python-backed HTML/CSS/JS UI**. The eventual desktop packaging architecture is still a future decision.

## Runtime and integration

No npm/Node required. Open `INICIAR_INTERFAZ_WINDOWS.bat` at repository root. The stdlib loopback server (`127.0.0.1:8765`) serves static assets and the JSON read model. UI-3.1 requires `frontend/public/squad/portraits.js`, `board.js`, `frontend/public/squad/polish.css` and `frontend/portable/polish.css` to be present alongside the original UI-3 files.

`tests/test_ui31_visual_live_home.py` covers asset availability, session read consistency, starters/bench swaps and source-of-truth OVR/ACT; `tests/test_ui3_roster.py` and `tests/test_ui_shell_squad.py` provide existing UI regression coverage. The exact browser appearance should also be verified manually in Windows/Chrome at your preferred zoom.
