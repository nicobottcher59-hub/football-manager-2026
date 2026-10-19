# Phase 3.1 - Tactical Shapes by Phase

## Goal

Extend the Phase 3 tactical model so a team can use a different spatial structure with the ball and without the ball.

This update does not simulate those movements yet. It only makes the tactical intent explicit so MatchSnapshot and the future Match Engine can consume it.

## Independent shapes

The team can now describe line width and inter-line distance separately for each phase.

### In possession

Already supported and retained:

- defensive-line width;
- midfield width;
- attacking-line width;
- defense-to-midfield gap;
- midfield-to-attack gap.

This allows concepts such as opening the centre-backs and full-backs during build-up while keeping the attacking line at a different width.

### Out of possession

Phase 3.1 adds explicit controls for:

- defensive-line width;
- midfield width;
- attacking/first-press line width;
- defense-to-midfield gap;
- midfield-to-attack gap;
- centre protection;
- tolerance for conceding crosses.

The existing block height, defensive-line height, horizontal compactness and vertical compactness remain available.

## Example

A manager can now represent this plan directly:

- with the ball: open the defensive line to help short build-up;
- without the ball: narrow the defensive and midfield lines;
- defend in a low, vertically compact block;
- protect central areas and the box;
- accept more access to wide areas and more crossing opportunities.

The in-possession settings are not overwritten when the out-of-possession shape changes, and vice versa.

## Tactical style analysis

The analyzer now exposes additional descriptive metrics:

- in-possession width;
- out-of-possession width;
- defensive compactness;
- central protection;
- cross tolerance.

It can also recognize a configuration such as a wide build-up shape that collapses into a narrow defensive block and label it:

`Salida ancha + bloque defensivo compacto`

As before, style labels are descriptive only. They do not grant bonuses.

## Presets

Deep-defence presets such as Catenaccio and Low Block now explicitly encode:

- narrow defensive-line width;
- narrow midfield width;
- short distances between lines;
- very high centre protection;
- very high tolerance for conceding crosses.

Presets remain editable starting points.

## Deliberately deferred

This phase still does not implement:

- player coordinates or movement during a match;
- actual crossing frequency caused by conceding the flanks;
- defensive clearances;
- matchup effects;
- drag-and-drop UI behavior;
- match simulation.

Those systems will consume this tactical intent later.
