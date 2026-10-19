# TS-19.1.1 - Formation UI Refinement

## Scope

This is an incremental UI patch applied **after TS-19.1 Formation Expansion**.
It does not implement free-position editing (TS-19.2) and does not change football
rules, attributes, OVR, ACT, player roles or match engines.

## Problem and changes

1. TS-19.1 used `.fm-dense-shape` to shrink player cards on dense formations.
   The main pitch now uses a single width and height for every card at a given
   viewport breakpoint (106 x 100 pixels on desktop; 88 x 90 on narrow screens).
2. An isolated frontend-only layout pass places the fixed-size cards on the
   pitch, preserving formation order and adapting to available pitch dimensions.
   It prevents cards from overlapping and keeps their complete bounding boxes
   inside the pitch. It does not rewrite any coordinates stored in Python.
3. A visual formation picker replaces the plain dropdown in the tactics toolbar.
   It has search, back-three/four/five filters, 28 miniatures and a larger preview.
4. The modal works as a draft: browsing, selecting and canceling do not change
   formation. Only confirming invokes the existing `{action: 'formation', id}`
   command. The existing role-reset behavior remains unchanged.
5. The read-only `/api/squad` model includes base position coordinates and labels
   for each of the 28 formations. This avoids duplicating shape definitions in
   JavaScript. The main `formation` and `slots` fields are unchanged.

## Technical files

- `src/football_manager/ui_shell/models.py` (read-only preview data)
- `frontend/public/squad/formation_layout.js` (UI geometry; CommonJS-testable)
- `frontend/public/squad/squad.js` (modal, events, card placement)
- `frontend/public/squad/squad.css` (fixed-size card rules, modal styles)
- `frontend/public/squad/embed.html` (include layout script)
- `tests/test_ts_19_1_1_formation_ui_refinement.py`
- `tests/ui/test_formation_layout.cjs`
- `tests/ui/test_formation_picker.cjs`

## Automated checks

- Original TS-19.1 catalogue and API assertions must continue to pass.
- All 28 previews must include eleven exactly matching catalogue positions.
- Layout geometry checks cover 28 formations x 2 phases x 4 pitch sizes
  x 5 tactical scenarios = 1,120 layouts. Test conditions include default and
  mixed extreme instruction values. Cards must never intersect or clip.
- Picker lifecycle tests ensure draft selection and cancellation do not send
  a Python command, and confirming sends exactly one command.

## Manual Windows checks

1. Launch `INICIAR_INTERFAZ_WINDOWS.bat` and open **Tactics**.
2. Click **Choose formation**. Confirm 28 preview tiles, filters and search.
3. Select a tile. Confirm the large preview changes while the starting XI does not.
4. Cancel (button, backdrop, Escape). Confirm the current formation stays the same.
5. Reopen and confirm **5-2-2-1 (2 Central AM)**. Ensure its two central AM
   markers and XI cards appear in the main pitch without a separate update.
6. Change to **4-2-3-1 Narrow**, **4-5-1 Flat**, **4-2-4**, **4-3-3 DM Wide**;
   compare card sizes, the high striker and crowded midfield in both phases.
7. Check responsive window widths or reduce the parent window size; a narrow
   viewport may horizontally scroll the pitch rather than shrink selected cards.
8. Ensure player selection and starter swapping continue working after closing
   the selector, and the existing Python role-reset warning is still accurate.

## Limitations

- The tactical field remains a schematic UI; this patch does not implement
  free-position controls or alter the fast/spatial match engine.
- A GUI inspection in Chromium may be unavailable in restricted execution
  environments; automated DOM lifecycle and geometry tests do not replace
  manual visual acceptance on the user's Windows installation.
