# TS-18.1 - Player State & Learning

## Purpose

Repair the missing post-match connection for already modelled player context:
form, confidence, match sharpness, role familiarity and tactical familiarity.
The existing base attributes, OVR/ACT equations, result-based morale update,
physical recovery and position-learning rules are unchanged.

## Behaviour

- Only players credited with minutes in `FastMatchResult.player_statistics`
  receive progression. Actual match rating drives short-term form/confidence.
- Changes are **deliberately gradual**. In a 90-minute appearance, an extreme
  rating can change form by at most **2 points** and confidence by at most
  **1.25 points**, up or down. The allowance is proportional to playing time;
  120 minutes receives up to 1.25 times the 90-minute allowance.
- One poor game cannot empty confidence; successive poor performances can
  gradually reduce it, and good games can restore it.
- Match sharpness grows slowly with minutes; no new injury/fatigue or morale
  mechanics were introduced.
- Role learning uses the role actually assigned in the starting XI. Bench
  players may learn the team tactic but are not assigned an imagined role.
- Familiarity progress depends on minutes, actual match rating, adaptability,
  tactical intelligence and current confidence; it is small and bounded by 100.
- Tactical familiarity earned in a match is retained in the existing trained
  plan baseline, avoiding its accidental erasure when editing the tactic.
- Any failed match commit rolls back player state, familiarities and both plan
  baselines along with the world result. Save/load continuity is maintained.

## Out of scope

No changed ACT/OVR formulas, role/position definitions, UI controls, global
balance calibration, new training mechanics or opponent-manager behaviour.
The existing result-driven morale path is deliberately left intact.

## Verification

Focused tests cover real session integration, an excellent/poor performance,
short appearances, eight bad games followed by good ones, one-game bounds,
role learning, non-participation, unchanged OVR and attributes, rollbacks and
SQLite save/load with deterministic continuation.

Windows, after applying TS-18.1 on top of TS-17.4:

```powershell
python -m pytest -ra tests/test_ts_18_1_player_state_learning.py
python -m pytest -ra
```

The second command is the full project regression and may take several minutes.
Node.js is not required for these Python tests.
