# Phase 1 implementation notes

## Scope completed

This first code iteration implements the beginning of Roadmap Phase 1: the player domain model.

Implemented:

- stable player IDs;
- player identity;
- dominant foot;
- technical, mental and physical attributes;
- player current state;
- positional familiarity;
- original and current primary position;
- conservative primary-position recalculation;
- JSON player loading;
- sample dataset;
- automated tests.

## Provisional technical decisions

### Attribute scale

The prototype currently uses a **1–100** scale for player attributes and a **0–100** scale for dynamic state and familiarity.

This is deliberately isolated in the domain model so it can be changed later if the project decides to use another internal scale.

### No overall rating

The domain does not store a single overall player rating. `PlayerAttributes.average()` exists only as a diagnostic helper for development and must not become the Match Engine's definition of player quality.

### Position changes

`Player.recalculate_primary_position()` does not teach a position. It only interprets accumulated familiarity. The future adaptation system will decide how familiarity grows based on minutes, performance, training, age and tactical intelligence.

## Explicitly not implemented yet

- clubs;
- lineups;
- roles;
- tactical familiarity;
- player relationships / chemistry;
- match simulation;
- injuries as a full system;
- player development;
- persistence/database.

Those belong to later roadmap phases.
