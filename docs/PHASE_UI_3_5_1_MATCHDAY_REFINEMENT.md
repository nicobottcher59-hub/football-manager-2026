# UI-3.5.1 — Matchday polish & drag-and-drop

## Scope

An incremental UI-only patch over **UI-3.5**. Keeps the standalone pre-match tab, full-match result, and Python FastMatchSimulator. The regular main-screen sidebar and its state handling are untouched. No sport simulation values are invented.

## Kit Settings

- Large shirt designs rendered locally using the existing SVG and CSS, with separate team-color previews, colour swatches and shirt/shorts/socks samples. No downloaded image assets or new dependencies.
- Choose Home/Away independently from the *existing server-supported kit choices*. Choices are previewed locally until **Save for this match** sends the existing `match_kits` command. **Reset to default** only resets the pending preview; cancel/back does not save.
- A simple visual-colour-distance hint shows whether shirt colours are very similar; it is **not** a match rule or referee check.
- As before, shirt colors, temperature and referee names are presentation data. The pre-match UI no longer prints a technical disclaimer beside the referee, per the accepted design; the underlying semantics remain unchanged.

## Match Tactics

- The eleven shirts are focusable/drop targets. Drag starter to starter to call `swap_starters(first=<slot>, second=<slot>)`. Drag bench player onto starter (or reverse) to call `swap_bench(starter_id=<id>, bench_id=<id>)`. All requests use the existing `POST /api/match` `match_tactic` command and fixture ID.
- The seven substitutes are explicitly shown directly below the field, with shirt number, short name, primary position and condition percentage.
- Alternative input: click a bench player then click the starter to replace. The former two-dropdown swap control stays behind an accessible disclosure. Clicking a starter without a bench player selected opens its role and instructions.
- Formation, all existing roles and instructions remain exposed in the right panel. Full match-only replay/isolation semantics are unchanged; permanent lineup and tactics are not overwritten.

## Post-match chronology

- Grid has left/home event content, center minute, right/away event content. Icon is **inside the same content element** as player/action and assist or booking detail, with placement on the appropriate side. Half/full-time markers remain neutral. Events are still generated only by FastMatchSimulator.

## Verification

- `node --check frontend/portable/match.js` (validation only; game continues to require no Node)
- `PYTHONPATH=src python -m pytest -q tests/test_ui351_matchday_refinements.py tests/test_ui35_matchday.py`
- Chromium browser QA with real API bridge: open kit screen, choose home shirt, save, open Match Tactics, drag bench→pitch, click bench→pitch, drag starter→starter, quick simulate and check event alignment. No JavaScript errors observed.
- Install by copying only the files inside the incremental ZIP over an already-updated UI-3.5 repository. Restart `INICIAR_INTERFAZ_WINDOWS.bat` and force-refresh browser.

## Existing limitations retained

The development game-state is still in-memory. In-match injuries, tackles and in-play missed penalties remain unavailable if they are not emitted by Python; immersive match mode remains disabled. Fictional referees and cosmetic weather have no gameplay influence. Technical checkpoint and complete save/load remain pending.
