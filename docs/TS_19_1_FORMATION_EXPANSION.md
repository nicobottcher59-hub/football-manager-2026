# TS-19.1 — Formation Expansion

## Goal and exact scope

Add 24 selectable preconfigured formation templates to the existing four (28
in total), using current positional roles, ACT/OVR/familiarity, team tactical
instructions and match engines. Make the expanded catalogue available **in the
same patch** on the Python development interface and the live HTML interface
that uses `/api/squad`.

This patch does **not** implement free dragging of positional anchors, new role
types, new tactical coefficients, expanded AI or a tactics library. Those are
separate later TS-19 stages.

## Catalogue

Retained, same IDs and positions:

- `dev-4-3-3`: 4-3-3 DM Wide
- `dev-4-2-3-1`: 4-2-3-1 Wide
- `dev-4-4-2`: 4-4-2
- `dev-3-4-2-1`: 3-4-2-1

New four-back formations:

- `dev-4-1-4-1` — 4-1-4-1
- `dev-4-3-1-2` — 4-3-1-2 (three CM)
- `dev-4-4-2-diamond` — 4-4-2 Diamond (one DM, two CM, one AM)
- `dev-4-2-2-2` — 4-2-2-2 (two DM, two AM)
- `dev-4-2-3-1-narrow` — 4-2-3-1 Narrow (three central AM)
- `dev-4-3-2-1` — 4-3-2-1 Christmas Tree
- `dev-4-4-1-1` — 4-4-1-1
- `dev-4-2-4` — 4-2-4 (explicit user request)
- `dev-4-5-1` — 4-5-1 Flat
- `dev-4-1-3-2` — 4-1-3-2

New three-back formations:

- `dev-3-5-2` — 3-5-2
- `dev-3-4-3` — 3-4-3
- `dev-3-4-1-2` — 3-4-1-2 (two CM)
- `dev-3-1-4-2` — 3-1-4-2
- `dev-3-4-1-2-dm` — 3-4-1-2 (two DM)

New five-back formations:

- `dev-5-3-2` — 5-3-2
- `dev-5-2-3` — 5-2-3
- `dev-5-4-1` — 5-4-1
- `dev-5-2-1-2` — 5-2-1-2
- `dev-5-3-1-1` — 5-3-1-1

Additional user-requested variations:

- `dev-4-3-3-double-dm` — 4-3-3 with **two DM and one CM**
- `dev-4-4-2-double-dm` — 4-4-2 with **two DM**
- `dev-4-5-1-am-duo` — 4-5-1 with **one CM, two central AM, wide RM/LM**
- `dev-5-2-2-1` — 5-2-2-1 with **two central AM**, not wide attackers

The separately requested 4-2-4 is already listed above; it is not duplicated.
The earlier candidate “4-3-3 with one DM” is already the original `dev-4-3-3`
and is likewise not duplicated.

## Integration

- `src/football_manager/dev_ui/formations.py`: authoritative catalogue of
  formation slots and normalized pitch coordinates.
- `src/football_manager/dev_ui/session.py`: the existing formation selector and
  lineup reassignment now use the expanded catalogue, preserving the initial
  four formation IDs and initial default. Existing assignment/familiarity logic
  remains unmodified.
- `src/football_manager/dev_ui/app.py`: Tkinter tactical board consumes the
  same catalogue and can represent all 28 formations immediately.
- `src/football_manager/ui_shell/models.py`: live JSON `/api/squad` includes
  the authoritative starting coordinates and optional display label for each
  tactical slot. Existing keys and commands are kept.
- `frontend/public/squad/board.js`: portable frontend reads these coordinates
  and still supports the fallback for old demo payloads. Tactical displacement
  logic and role instructions remain unchanged.
- `frontend/public/squad/squad.js` and `squad.css`: live selector automatically
  receives all 28 formations; the pitch uses compact cards where required for
  crowded midfield shapes.

### Wide midfield representation (existing game limitation)

The domain's `Position` enumeration does not yet have standalone RM/LM codes.
To avoid changing player ratings, role compatibility or familiarity formulas,
wide midfielders are modelled with existing RW/LW positions **placed deeper** on
the tactical board. They are labelled RM/LM in the live lineup for clarity.
This is a presentation/shape expansion and not the implementation of distinct
RM/LM attribute/familiarity rules. A future positional architecture may revisit
this explicitly. Do not interpret the diagram as the separate experimental 2D
match engine.

### Saving

Existing career graph serialization carries complete Formation/Tactic objects,
so these new formation definitions can be saved with the current manager state.
TS-19.3 remains the planned independent reusable multi-tactic library.

## Tests

`python -m pytest -ra tests/test_ts_19_1_formation_expansion.py`

The targeted tests cover: 28 catalogue entries, preserved original IDs and
slots, complete role assignments, selecting all formations, backend output,
actual FastMatchSimulator runs, both schematic frontend tactical phases via
Node.js (when present), persistence graph round-trip and HTTP server commands.

`node tests/ui/test_board.cjs` verifies the existing tactical sliders still
change coordinates and only one phase toggle exists.

To confirm the actual UI on Windows, launch `INICIAR_INTERFAZ_WINDOWS.bat`, open
**Tactics → Formation**, and verify that the 28 names appear, that selecting a
new shape rearranges all 11 player cards, and that both In/Out of possession
views remain usable. This real-browser Windows acceptance check cannot be
replaced by running unit tests.

## Deliberate exclusions

No alterations to `domain/enums.py`, `domain/roles.py`, `domain/tactics.py`,
fast/spatial simulation engines, OVR/ACT, tactical coefficient weights,
fatigue, player state evolution, rival AI, existing presets or transfer UI.
