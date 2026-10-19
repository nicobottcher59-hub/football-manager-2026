# UI-3.3.1 — Competition Bracket Refinement

## Why this patch exists

The accepted UI-3.3 bracket looked like a horizontal list of cup rounds. This refinement makes the cup presentation a **two-sided bracket with a final in the middle**, closely following the approved zoom sequence. The right-hand matchday/round list remains visible at all times, including in cup knockout views.

## Competition selector: controlled club only

`GET /api/competitions` returns:

- `competitions`: only competitions the managed club **participates in**, including cups where the club is a *later-round entrant* before its first tie has been drawn.
- `other_competitions`: all other competitions registered in the existing Python world, reserved for a separate World / Other Leagues screen later. This list is not rendered as tabs in Competitions.

For the unmodified Northbridge 2026/27 DEV session, the four visible tabs are **Premier League, FA Cup, Carabao Cup and UEFA Champions League**. Northbridge joins FA Cup in Round Three, so it remains visible even though the earlier rounds have drawn fixtures and Northbridge's own opponent is not yet known.

Other league API endpoints remain available internally and are not deleted. No competition simulation or qualification is changed by this UI filtering.

## Cup bracket geometry and zoom

- Symmetric left and right wings representing **both sides of the current competition's drawn tie sets**, with **Final** at the center.
- Current actual ties are distributed between the wings. When a finished tie feeds a specific tie that is **already drawn in the next round**, layout grouping keeps these on the same wing and a solid line depicts **only that proven advancement**.
- **Undrawn rounds have explicitly labelled pending placeholders** on both wings and in the middle. They are not projected matchups or pairings, and are not joined by fake progression connectors. Short dashed line stubs are decorative unresolved endpoints, never bracket predictions.
- Four progressively changing zoom levels: **Tie detail** (initial, closer to Northbridge if its tie has been drawn) → **Section** → **Both sides** → **Whole bracket** (fit overview). Use `−` to reveal more of the bracket and `+` to inspect a match. Zoom changes density of visible detail, not just font size.
- `My path` recenters and highlights a **known** Northbridge tie; `Full bracket` opens the complete two-sided overview. For FA Cup before Northbridge's own draw, My path is correctly unavailable while its announced entry round is visible in the explanatory note.
- Scrollbars and background drag allow panning while zoomed in. Clicking a match tile selects that round in the **right-side full fixtures panel**.

These are **presentation-only** mechanisms: the current cup engines rely on draws, so a fixed FIFA World Cup-style future elimination tree **cannot honestly be computed until actual pairings exist**. Each drawing is built solely from registered Python results and draws. The screenshot references are therefore a visual metaphor, not a pretext to generate fictional future opponents.

UEFA competitions retain the League Phase/Knockout toggle. The knockout stage uses the same bilateral structure but initially displays draw-pending placeholders. Every league and cup still shows **all fixtures for the selected matchday/round** in the sidebar, not just club fixtures.

## Files and non-goals

- `src/football_manager/ui_shell/competitions.py`: read-only club-participation detection, including late cup entrants. No WorldRunner mutation.
- `frontend/portable/competitions.js` and `.css`: bilateral bracket, semantically progressive zoom, scroll/drag panning, club-only selector.
- `frontend/portable/portable.js` and `frontend/portable/index.html`: updated Competition page description/version, no change to other screens.
- Tests, docs and the Windows patch instructions.

**No changes** to FastMatchSimulator, draw algorithms, match results, season scheduling, save format, or Continue. The existing Python `.bat` launcher remains usable with no Node.js/npm installation.

## Validation

- `PYTHONPATH=src python -m pytest -q tests/test_ui33_competitions.py` — club-only options, FA Cup later registration, result provenance, HTTP endpoint, code-safety assertions.
- Headless Chromium smoke test (uses **actual Python model snapshots**, not invented fixtures) — all four tabs, FA Cup pending club entry, Carabao bilateral zoom four steps and matchday sidebar, Champions League undrawn knockout view. No page errors.
- Other UI and competition-engine regressions executed in smaller blocks when resource limits allow.

## Installing and accepting

1. Start from an accepted **UI-3.3** branch containing the prior patch.
2. Make branch `phase-ui-3-3-1-competitions-refinement`.
3. Copy **the contents** of the incremental ZIP into the repository root, preserving its folder structure. Replace only files in the patch.
4. Shut down the old Python `.bat` window, then open `INICIAR_INTERFAZ_WINDOWS.bat`; refresh browser with `Ctrl+Shift+R`.
5. Inspect Cup close-up, press `−` repeatedly to see both sides and Final, press `+` to inspect matches, click Full bracket/My path, switch competition, verify right-side fixtures.
6. Do not commit until approved in Windows.
