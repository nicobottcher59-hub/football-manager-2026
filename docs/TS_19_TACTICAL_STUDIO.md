# TS-19 - Tactical Studio 2.0

## Scope and baseline

This is a functional expansion on TS-19.1.1, not another stabilization-only patch.
The validated baseline is the supplied project plus TS-18.5 REVISADO, the unified
TS-18.6, TS-19.1 and TS-19.1.1. The original 28 formations, roster controls,
role definitions and rating formulas remain available.

Implemented together: the portable Edit Tactics interface, phase-specific manual
targets, explicit football-position editing, a per-career tactic library, A/B/C
plans, scheduled in-match changes, previously missing fast-engine instruction
consumers, persistence migrations and tests. Player personality, dressing-room
relationships, long-term aging/newgens and Squad radar charts are NOT part of TS-19.

## Editing workflow

Open Tactics, then Edit team tactics. Lineup still selects/swaps actual players.
The tactical editor moves position markers; it does not replace the roster editor.

- Drag a marker to preview a target in the displayed phase. Releasing an outfield
  marker now opens a compact position chooser limited to that area. One atomic
  command is sent only after choosing; Cancel/Escape changes nothing. The keeper
  retains its unique position and can move without an outfield chooser.
- Alternatively focus a marker, use arrow keys (Shift for five-percent steps),
  Enter to open the same chooser or Escape to cancel. Target-only undo retains
  up to 20 moves that keep the actual position; explicit position/role changes
  and intervening unrelated commands clear the chain.
- Click a marker to use the existing role/individual-instruction panel. Its
  Position in this zone control offers the same nearby positions for the active
  phase. Incompatible roles use the existing default compatible role.
- In possession and Out of possession store independent targets. Copy other phase,
  Reset targets and Reset this phase target make that distinction explicit.
- Manual targets override automatic positional instructions for that marker only.
  Other instruction effects remain active. A formation change clears incompatible
  targets; a style preset preserves manually placed targets.

Dragging a LB into midfield does NOT silently pick DM or another position.
The user chooses from the compatible neighbouring positions before anything is
applied. For example, a central attacking drop offers ST/SS/AM, not centre-backs.
The football assignment is shared by both phases; only the dropped phase target
moves, and the other phase location is preserved when the role family changes.
Existing positional familiarity, compatible roles and OVR/ACT assess the choice.
No additional hidden position penalty is added. Existing templates and automatic
role movements are not retroactively reclassified by these editor-only ranges.
The current Position enum is retained, including the existing RW/LW representation
of the deeper RM/LM catalogue markers; no new position family is invented here.

## One pitch, three analytical layers

Coverage, Vulnerabilities and Laboratory are small controls below the same pitch.
They toggle canvas layers, not new pages, windows or tabs. The base view can be
restored with the close-layer button.

Coverage is a bounded geometric estimate from the ten outfield markers. The
kernel has widths 0.16 (across the pitch) and 0.13 (along it); coverage is
`1 - exp(-sum(kernel))`. The refinement renders this unchanged value on a fixed
red -> orange -> yellow -> lime -> green scale (low to high coverage), using a
smoothed raster instead of turquoise cell opacity. The numeric scale and kernels
are unchanged and do not normalize independently for each formation.
Vulnerability estimates the cover remaining behind the
ball across left, central and right channels. A channel below 0.55 is flagged.
Advancing both fullbacks therefore removes their contribution behind the ball.

Laboratory compares the selected phase against the current opponent's opposite
phase, mirrored into the same reference frame. The inline opponent selector can
instead use one of the 28 hypothetical catalogue structures. Blue and amber show
relative occupation, not a predicted score or a guarantee that a player wins a duel.

These are static tactical estimates, NOT recorded match heatmaps. Colors themselves
never apply a penalty. The fast simulator consumes the underlying geometry and
instructions separately, while abilities and roles remain relevant in its existing
calculations. Keeper positioning is excluded from collective outfield coverage;
explicitly advancing the keeper has bounded support AND exposure effects in the engine.

## Shared model and integration

`SlotPoint` and `PhaseShape` are immutable. Coordinates use a manager-facing pitch:
x=0 is the left touchline, x=1 the right; y=0 is the opposition goal, y=1 the own goal.
Targets must be finite and within 0.04..0.96. Duplicate phases/slots, unknown slots,
invalid types and goalkeeper-to-outfielder conversions are rejected atomically.

`Tactic.phase_shapes` is frozen into `TacticMatchSnapshot`. The shared catalogue
moved into `domain/tactical_catalogue.py`; `dev_ui/formations.py` re-exports its
original public functions, retaining import compatibility.

`domain/tactical_geometry.py` and portable `board.js` use matching automatic phase
geometry. Tests compare all 28 formations in three presets and both phases, plus
custom-target/position cases: 170 complete pitch mappings, with eleven slots each.
The spatial legacy engine also receives explicit phase anchors with a single
side/orientation transform. That does not unfreeze or redesign the legacy 2D engine.

The fast engine consumes shape summaries (connection, support, central/flank
cover and defensive screens), actual roles/attributes and the instruction features.
New adjustments are bounded: possession control +/-2; expected shot opportunity
adjustment +/-1.7; chance-quality adjustment +/-0.018; pass-completion adjustment
+/-0.035. These are documented game-design coefficients, not fits to real-world
tracking data. They can change match outputs without editing OVR/ACT formulas.

## Previously missing instruction consumers

The audited schema still has 59 controls: 52 with match effects, 3 score-dependent
management controls, and 4 whose established effect is player workload/conditioning.
The previous 22 not-modelled controls and one description-only width now have
explicit consumers. This is a schema inventory, not a claim that every setting
changes every match or every phase regardless of context.

| Controls | Actual fast-engine use |
| --- | --- |
| Attacking defense/midfield and midfield/attack gaps | Phase geometry, connection, progression costs and opportunity quality |
| Switch play, central focus | Opponent width/channel coverage, possession/passing costs and shooter shares |
| Overlap frequency | Wide-back support and transition exposure; not a free bonus |
| Long-shot frequency | Shot opportunities, chance quality and long-shot construction using actual attributes |
| Goalkeeper release speed | Transition effects when counter/direct/expand is requested; passing tradeoff |
| All three defending line widths | Defensive shape, screens, route coverage and width mismatch |
| Force direction, marking style | Channel matchup or marking/mobility/technical-escape comparison |
| Individual dribble/shoot/cross frequency | Opportunities, actor selection and actual chance construction |
| Individual passing risk and hold-up play | Creator/pass shares, control and completion tradeoffs |
| Attack space | Attacking support and shooter opportunities |
| Individual in/out-of-possession positioning | Automatic phase geometry; free movement has bounded collective effects |
| Cross type | Construction branches for high/early, low, cutback and byline crosses |
| Marking and pressing targets | Pressure on present matching player IDs, positions or roles only |

Runs, individual pressing intensity, tracking and roaming keep their existing
conditioning path. This update does not invent detailed event telemetry for crosses,
dribble maps or every defensive action; the fast simulator remains non-spatial.
Rerun `python tools/audit_tactical_consumers.py` to inspect the inventory.

## Tactic library and plans

The library supports up to 64 named templates: save/overwrite, save as new, load,
rename, duplicate and delete. Names are validated as data and escaped in the UI.
Templates store formation/position assignments, role overrides, team instructions
and both phase shapes. They never store player selections. Loading reuses the
current eleven and bench rather than resurrecting an old lineup.

A, B and C reference saved templates. They can be loaded in the studio or chosen
as a temporary kickoff setup in Matchday. Up to six rules can be scheduled at
separate minutes 1..119, with Always, Leading, Level or Trailing conditions.
Each rule is evaluated ONCE, immediately before that minute, against the real
score. Extra-time rules run only if extra time actually occurs.

Rules run inside a chronological fast-simulation path, not on a prerecorded
result. Plan preparation uses isolated roster copies and canonical assignment
ratings. Actual substitutions are followed by player identity; dismissed players
remain dismissed. Role/position exposure and physical workload are accumulated
only for the minutes actually played, including extra time and substitutions.
Form/confidence progression is applied once; the existing learning budget is
split across the roles actually played.

Important: Quick Sim computes the match before displaying its report. TS-19 does
NOT add live manual intervention into that finished report. Choose plans/schedules
before simulation; the resulting plan events appear in the match timeline.
Scheduling opts into a minute-based RNG path. Determinism requires identical full
inputs, including the schedule; identical seeds across old/new engine versions or
scheduled/unscheduled paths are not an identical-result guarantee. Later plan
choices do not rewrite earlier events within the scheduled path.

Matchday overrides are temporary. The normal career tactic, library and schedule
are restored after the match; player progression and the genuine result remain.

## Persistence and error handling

Complete career saves migrate manager graph/section version 1 or 2 to version 3.
Legacy tactics acquire empty manual shapes; legacy results acquire empty tactical
events and role segments; legacy careers acquire an empty library. Migrations are
explicit and class-specific, not a fallback that accepts damaged saves.

The library is part of the COMPLETE career save. Pressing Save tactic updates the
live career/library; save the career to persist it to disk before closing. Legacy
results-only world JSON does not include the tactical library.

Save/load validation checks formation/role integrity, valid coordinates, library
references, rules and result exposure. A real v2 save fixture with a played match is
included in the tests. Returning to older code after saving v3 requires the backup
made before installing TS-19; old code is not promised to read new-version saves.

Commands use the existing atomic transaction path. Invalid or stale-revision
commands restore the prior state. Rejected optimistic UI changes reread Python
truth. Input shapes/rosters are not mutated by pure match simulation or plan preparation.

## Validation and practical limits

See `TS_19_TEST_REPORT.md` and `reports/ts19/` for actual executed results, including
the full suite, browser interactions, an additional 1000-match batch and the updated
versioned reference match. No tests are claimed complete merely because a ZIP exists.

The browser check runs actual shipped JS/CSS in Chromium. Its in-process bridge
replaces network transport with the real Python application. A separate live HTTP
test checks routes, asset serving, commands and rejected revisions. This distinction
is recorded rather than describing the bridge as a real Windows deployment.

The portable frontend uses native pointer/keyboard events, not a React migration or
a new npm build. Windows needs no Node.js to run the game. Two new JS contract checks
are optional and skip without Node; the remaining new tests are Python-only.

The synthetic regression/stress checks are not proof of final competitive balance,
15-year player longevity, or absence of every possible bug. TS-20/21 remain separate.

## TS-19 placement / heatmap refinement

See `TS_19_PLACEMENT_HEATMAP_INSTRUCTIONS.txt` and
`TS_19_PLACEMENT_HEATMAP_TEST_REPORT.md` at the repository root.
The domain table `tactical_position_zones.py` is shared through the studio read
model. These overlapping bands are UI design ranges, not new match coefficients.
The existing no-phase `studio_position` API and saved templates remain compatible;
the updated UI always sends the active phase, and `studio_place` validates the
confirmed position and coordinates together. No save-format bump or TS-20
installation is required.
