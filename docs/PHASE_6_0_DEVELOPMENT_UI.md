# Phase 6.0 - Disposable Development UI

## Status

Implemented.

This phase adds a deliberately disposable graphical shell so the management game can be inspected and exercised while the persistent world, competitions and calendar are still under construction.

It is **not** the final game UI and must not constrain the eventual UX architecture.

---

## Purpose

The project now contains enough real football systems that console-only outputs make product decisions harder to reason about.

The development UI exists to make those systems tangible early:

- inspect the current squad;
- compare `OVR` and contextual `ACT`;
- inspect condition, fatigue, confidence, form and sharpness;
- inspect the submitted XI, slots and roles on a tactical pitch;
- swap a starter with a bench player and immediately observe contextual ACT consequences;
- use tactical presets only as starting points;
- manually change formation, compatible slot roles and team instructions;
- drag starting players between tactical slots, including deliberately extreme out-of-position assignments;
- inspect tactical familiarity, chemistry, condition and morale as collective decision-support metrics;
- run the real `FastMatchSimulator` through a Quick Sim action;
- inspect the result and post-match physical state;
- reserve visible places for Calendar and Competitions before those systems exist.

The UI is intentionally simple. Its value is development feedback, not visual polish.

---

## Launch

From the project root in PowerShell:

```powershell
$env:PYTHONPATH = "src"
python -m football_manager.dev_ui
```

Tkinter is part of the standard CPython distribution on normal Windows Python installations. No new third-party UI dependency is required.

---

## Architecture boundary

The Tkinter layer does not own football logic.

```text
Tkinter widgets
    |
    v
DevelopmentSession
    |
    +--> domain models / OVR-ACT
    +--> lineup + tactic objects
    +--> MatchSnapshot builder
    +--> FastMatchSimulator
    +--> post-match condition service
```

`football_manager.dev_ui.app` only renders state and forwards user actions.

`football_manager.dev_ui.session.DevelopmentSession` is the temporary application-facing adapter used by the sandbox. Simulation formulas, player ratings, tactical calculations and physical-state formulas remain in their existing domain/simulation modules.

This separation allows the entire Phase 6.0 UI to be deleted or replaced later without rewriting game logic.

---

## Pages

### Home

Shows:

- current development club and date;
- next match placeholder;
- current tactical plan;
- Quick Sim;
- latest Fast Simulator result;
- disabled `Continue` placeholder for the future persistent-world loop.

Quick Sim uses the real Fast Match Simulator. After the match, returned `condition_after` and `fatigue_after` values are persisted onto the sandbox players through the existing condition service.

Because Phase 6.0 has no world calendar yet, the sandbox allows one match per reset. This prevents repeated clicks from silently creating several matches on the same date.

### Squad

Shows:

- XI / bench state;
- player;
- natural position;
- assigned slot;
- assigned role;
- `OVR`;
- contextual `ACT`;
- condition;
- fatigue;
- confidence;
- form;
- match sharpness.

A simple XI/bench swap control is included. It deliberately permits out-of-position selections so the user can see the existing position/role/tactical familiarity model affect ACT.

### Tactics

Shows and edits the real tactical plan. Presets are only starting points. After applying one, the user can manually change:

- formation (`4-3-3 DM Wide`, `4-2-3-1 Wide`, `4-4-2`, `3-4-2-1` in the current sandbox);
- the role assigned to each slot, restricted to roles supported by that slot position;
- all enum/bool team instructions currently present in the domain model across in-possession, transition, out-of-possession and game-management groups.

Manual edits mark the tactic origin as `CUSTOM`. Formation changes rebuild a valid XI over the new slots while preserving the selected team instructions. Role and instruction changes operate on the real `Tactic` object; Tkinter owns no tactical formula.

The starting XI is rendered on a simple tactical pitch. Player cards can be dragged onto another occupied slot to swap the two assigned players. The tactical slot keeps its own position and role; only the players move. This intentionally allows extreme experiments such as assigning a striker to centre-back or a defender to striker so the real position familiarity, role familiarity, ACT and tactical-execution consequences can be inspected. The board does not invent a separate penalty formula.

The screen also exposes four collective diagnostics:

- **Tactical familiarity**: the XI value uses the same position/role/tactic familiarity weighting used by Fast Simulator tactical execution; a squad value is also shown. Manual changes can lower the score rather than receiving free familiarity.
- **Chemistry**: Phase 6.0 uses explicit per-player sandbox cohesion inputs and averages the selected XI. Those values are passed into the existing ACT chemistry adjustment when the MatchSnapshot is built, so the number is not decorative. The final chemistry source will later be replaced by the real relationship/cohesion system.
- **Condition**: XI average plus counts below 75 and 60. Individual condition already affects ACT and post-match physical state.
- **Morale**: squad average plus the XI average. Morale is an existing player-state input to ACT. A future long-term happiness/satisfaction system remains a separate concern.

This is still not the final tactical UX. The Phase 6.0 drag-and-drop pitch is only a development control for swapping players between predefined formation slots; freeform spatial positioning, final information hierarchy, production navigation and polished interaction design belong to the eventual final interface.

### Calendar

Currently a clearly marked placeholder.

It exists so Phase 6.1+ can replace mock rows with real fixtures without inventing the screen later.

The intended future calendar will combine:

- domestic league;
- FA Cup;
- EFL Cup;
- UEFA competitions;
- postponements/reprogramming;
- international breaks;
- condition/recovery consequences from real gaps between fixtures.

### Competitions

Currently a clearly marked placeholder for:

- Premier League;
- FA Cup;
- EFL Cup;
- Champions League.

These rows are not competition implementations and do not hardcode competition rules into the UI.

---

## Development data

Phase 6.0 uses fictional English clubs and players created specifically for the sandbox.

They exist only to expose the current systems with varied:

- quality;
- positions;
- stamina;
- natural fitness;
- confidence;
- form;
- tactical context.

The initial sandbox seed is reset to the same value when `Reset sandbox` is used. This makes quick A/B comparisons useful: change one lineup/tactical choice, reset, and rerun with the same underlying random stream.

Real databases, real competition participants and imported real-season schedules are separate future data concerns.

---

## What Phase 6.0 intentionally does not implement

- persistent WorldState;
- real Competition domain objects;
- real Fixture/Schedule domain objects;
- standings;
- knockout brackets;
- season progression;
- real calendar import;
- advancing days;
- recovery through the calendar;
- save/load;
- final UI design;
- final navigation model;
- responsive production layout;
- branding/assets;
- persistent relationship/chemistry graph;
- long-term player happiness/satisfaction model.

The placeholder pages must not be mistaken for implementations of those systems.

---

## Next phase

**Phase 6.1 - Competition Framework**.

The framework should be generic from the start rather than hardcoded to one league:

```text
Competition
    -> Edition / Season
        -> Stages
            -> Participants
            -> Fixtures
            -> Rules
            -> Standings / Bracket state
```

England is the preferred first integrated test environment because one club can naturally need to coexist across a domestic league, two domestic cups and a UEFA competition.

The first real season may later import actual competition calendars. Future seasons should be generated from calendar templates/windows derived from the original competition structure rather than by simply adding 365 days to imported dates.
