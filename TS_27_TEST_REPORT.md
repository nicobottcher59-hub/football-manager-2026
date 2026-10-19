# TS-27: Match preparation, set-piece priorities, contextual AI coaches

## Delivery scope

This is a single release combining the agreed TS-27.1 and TS-27.2 work.
The fast match simulator is preserved. No interactive match intervention, no attribute masking, and no scouting replacement were introduced.

### Pre-match preparation (read-only report)
- The existing Tactics screen shows the actual scheduled opponent, current projected formation and tactic, indicators calculated from its tactical style, and up to three players from the opponent's selected XI.
- Recent results are included only if matching fixtures have already been completed in the world ledger. No fictitious statistics or guaranteed tactical weaknesses are generated.
- The quick-match pre-match screen includes a compact version of the same data.

### Captain and set pieces
- The manager can save an ordered primary/secondary/tertiary captain, penalty, free-kick, left-corner and right-corner selection through the existing squad command endpoint.
- Selections persist in SQLite and in the complete manager session graph; version 20 migrates older saves, including v19.
- Players on the bench, unavailable players and departed players never enter the match just because they were preferred: an available player on the pitch replaces them automatically.
- Explicit goalkeeper selections are permitted, including captain and penalty taker.
- The quick simulator uses penalty priority in penalty shootouts. For a small subset of already-generated chances it also applies named free-kick/corner takers and a bounded captain leadership modifier; it never manufactures extra goals.
- **Known limitation:** the current fast simulator does not have a separate in-play penalty-award event, so the new penalty order cannot be used for penalties in regular or extra time. Its actual effect is on penalty shootouts.

### Opponent AI coaches
- Coach approach is inferred from the opponent's existing tactical preset with deterministic, club-specific variety (attacking, cautious, balanced, pragmatic).
- Coach judgement and match variation are deterministic for a given world seed, club and fixture, with bounded numerical effects.
- Coaches alter only existing urgency-when-trailing, risk-when-leading and time-wasting levers of the instant simulator. No direct attack/defense/OVR bonuses and no access to hidden player-manager tactical choices.
- The background AI-versus-AI fixture resolver uses the same mechanism. The manager-controlled team is never silently overridden.

## Validation performed

- TS-27: **13/13 tests pass in small groups**: 7 pre-match/simulation/graph tests, 5 migration/edge-case/atomic tests, and 1 local-HTTP endpoint test. A larger combined run timed out in this container; this is NOT recorded as a successful complete-suite run.
- TS-26: **9/9 specific tests** passed across 2 groups.
- TS-26.1: **12/12 specific tests** passed across 3 groups.
- TS-25: **4 targeted tests** passed for conversations, Inbox, and saving.
- Existing world/background fast-simulation tests: **2 selected tests** passed (world match deterministic simulation and background/managed shared engine).
- Python package compile and JS syntax: passed.
- Existing v19 SQLite manager save loads in v20 with all current squad members intact and default set-piece orders; save/restore of configured orders also passes.
- Real loopback HTTP GET /api/squad, POST /api/squad and GET /api/match integration passes.

## Not yet validated

- End-user visual and playable behavior on Windows.
- Full test suite (several historical tests still hardcode legacy save version 17).
- A complete 20-season career endurance run.
- Long-term economy and sporting balance specifically after TS-27 AI profile adjustments.

## Installation

Install the incremental TS-27 patch on top of TS-26.1. Copy patch files over the project root, preserving folders, and accept replacements. Do not copy over saved games or .git.
