# Phase 2 - Clubs, Squads and Lineups

## Goal

Build the domain layer that groups players into clubs and represents a valid pre-match selection without introducing tactical behavior or match simulation yet.

## Implemented domain objects

### Club

A club has a stable internal ID, display name, short name, country and a squad.

Visible club names remain separate from IDs so data packs can replace real/display data later without changing engine logic.

### Squad

`Squad` owns the current set of players registered with a club for this prototype.

It provides:

- add player;
- remove player;
- lookup by stable player ID;
- duplicate-ID protection;
- immutable tuple view of current players.

Transfer, registration-window and contract rules are deliberately out of scope for this phase.

### Formation and FormationSlot

A formation is represented by 11 named slots.

Each slot has:

- a unique `slot_id`;
- a football `Position`.

The slot ID is separate from the position. This is important because a formation may contain repeated positions, for example two centre-backs or two strikers.

A valid formation currently requires:

- exactly 11 slots;
- unique slot IDs;
- exactly one goalkeeper slot.

### MatchLineup

A submitted lineup contains:

- club ID;
- formation;
- exactly 11 starters assigned to formation slots;
- zero or more bench players.

Validation currently prevents:

- missing or unknown formation slots;
- duplicate slot assignments;
- selecting the same player twice;
- selecting an unavailable player;
- using a lineup for the wrong club;
- selecting players who are outside that club's squad.

`MatchLineup` is immutable. Future substitutions will belong to in-match state rather than rewriting the submitted starting lineup.

## Deliberately not implemented yet

- tactical instructions;
- player roles;
- chemistry;
- substitutions;
- competition-specific bench limits;
- registration rules;
- contracts and transfers;
- match simulation.

These belong to later phases.

## Architectural reason

This phase gives the future Match Engine a clean answer to three independent questions:

1. Which club does a player belong to?
2. Which players were selected for the match?
3. In which positional slot does each starter begin?

Tactical instructions can later be layered on top without overloading the player, club or formation entities.
