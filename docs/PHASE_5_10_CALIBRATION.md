# Phase 5.10 - Calibration & Statistical Validation

## 5.10A - Calibration Harness & Benchmarking

Phase 5.10A adds measurement infrastructure only. It does **not** tune Match Engine
probabilities or movement.

### Controlled benchmark scenarios

The first harness uses three intentionally simple strength profiles around the 70-point
demo reference side:

- `equal`: 70 vs 70;
- `home_weaker_10`: 60 vs 70;
- `home_stronger_10`: 80 vs 70.

Every attribute is shifted together in these scenarios. That is useful as a sensitivity
probe, not as a realistic squad model. Heterogeneous benchmark squads belong in later
5.10 work.

The same seed set is reused across scenarios so A/B comparisons change strength while
holding the starting random stream constant.

### Harness

Run from the repository root:

```powershell
python tools/calibrate.py --matches 8 --workers 4 --scenarios equal home_weaker_10 home_stronger_10
```

`--matches` is per scenario. Full 90-minute simulations are intentionally used unless
`--smoke` is passed.

For a fast plumbing check only:

```powershell
python tools/calibrate.py --matches 1 --workers 1 --scenarios equal --smoke
```

Smoke-mode numbers are not calibration data because the periods are shortened.

### Outputs

Each run writes three files under `reports/calibration/` by default:

- `<timestamp>_<commit>_matches.csv`: one row per simulated match;
- `<timestamp>_<commit>_summary.csv`: one row per scenario;
- `<timestamp>_<commit>.md`: human-readable summary and target deviations.

Reports record the current Git commit and whether the working tree is dirty.

### Metrics

The Phase 5.10A report includes:

- goals;
- shots and shots on target;
- xG;
- goals minus xG and goals/xG ratio;
- pass completion;
- possession;
- fouls;
- yellow/red cards;
- corners;
- home/draw/away rates;
- home points per match;
- home xG differential;
- wall-clock seconds per simulated match.

The neutral target table uses broad initial bands. They are diagnostic references, not
universal football constants. Outcome percentages should not be interpreted strongly
with very small sample sizes.

### Phase boundary

5.10A observes the existing event/statistics stream as-is. It deliberately does not fix
its current fragility. RNG separation and stronger typed event/statistics plumbing are
5.10B work; strength-curve and tactical ablation analysis are 5.10C work.

## 5.10B - RNG Isolation & Event Integrity

Phase 5.10B hardens reproducibility and the statistics event pipeline. It still does
**not** tune football probabilities.

### Deterministic RNG substreams

A match keeps one root seed, but random draws are isolated by subsystem:

- `initialization`;
- `decisions`;
- `passing`;
- `defending`;
- `progression`;
- `shooting`;
- `flow/duels`;
- `flow/penalties`;
- `flow/tiebreak`.

Substream seeds are derived with BLAKE2 rather than Python's process-randomized `hash`,
so they remain stable across worker processes and operating systems. Consuming an extra
random draw in passing no longer advances shooting or penalty randomness.

`MatchRandom.keyed_random(...)` is also available for future semantic draws such as
`(tick, agent, purpose)` without advancing any stream.

**Important:** splitting the historical shared RNG intentionally changes the exact match
produced by an old seed. Reproducibility is defined within Phase 5.10B and later; the
same 5.10B seed remains deterministic, but it is not expected to reproduce the 5.9
scoreline event-for-event.

### Typed event metadata

`MatchEvent.data` remains available so Phase 5.9 presentation code stays compatible.
Every event also exposes `MatchEvent.details`, a typed representation of the known
metadata fields (xG, probability, booleans, card type, outcome, coordinates, etc.).

`MatchStatisticsTracker` consumes this typed view rather than reparsing metadata strings
for every statistic.

### Shot lifecycle integrity

Every open-play `SHOT` now receives a deterministic `shot_id`. Its terminal event
(`GOAL`, `SAVE`, `BLOCK`, `WOODWORK` or `OFF_TARGET`) carries the same ID. This makes
shot -> outcome -> statistic traceable.

A pre-existing event gap was also closed: goalkeeper parries already produced a genuine
loose rebound in the simulation, but Match Flow did not emit their terminal event.
Parries now emit `SAVE` with outcome `parried`, so shots on target and goalkeeper saves
remain observable.

### Calibration audit

`audit_match_events(...)` checks each calibration match for:

- shot attempts without a terminal outcome;
- terminal shot outcomes without a matching shot;
- duplicate terminal outcomes;
- invalid/missing open-play xG;
- disagreement between final score and emitted goal events.

The calibration CLI adds an `evt!` column and writes aggregate event-integrity counts to
the CSV/Markdown reports. A healthy run should report `evt! = 0`.

### Phase boundary

5.10B makes A/B experiments trustworthy and statistics traceable. It does not correct
low shot volume, high goal/xG conversion, low foul/card/corner counts, strength-curve
sensitivity or tactical effect size. Those remain calibration work for 5.10C and later simulator-specific calibration.

## 5.10C - Strength Curve & Tactical Ablation

Phase 5.10C measures two different questions before any coefficient tuning:

1. **How sensitive is the engine to team quality?**
2. **Do tactical instructions actually reach the simulation and create observable effects?**

It still does **not** tune finishing, passing, fouls, cards, corners or movement.

### Strength curve

The strength experiment replaces the all-70-vs-all-80 probe with mirrored,
deterministically heterogeneous squads. Matching slots have matching player profiles at
gap 0, but individual technical/mental/physical values vary around the reference level.
The controlled team delta is then applied over that profile.

Default points:

- `-20`, `-10`, `-5`, `0`, `+5`, `+10`, `+20` home strength gap.

The same seeds are reused at every point. The report measures:

- home points per match;
- goal differential;
- xG differential;
- home xG share;
- home/draw/away rates;
- underdog-win rate (batacazos);
- favorite non-win rate;
- slope per +10 attribute points;
- monotonicity violations and abrupt adjacent jumps.

Run a first usable curve with:

```powershell
python tools/strength_curve.py --matches 4 --workers 4
```

For plumbing only:

```powershell
python tools/strength_curve.py --matches 1 --workers 1 --scenarios home_weaker_5_heterogeneous home_stronger_5_heterogeneous --smoke
```

Small-N win rates remain noisy. A serious calibration decision should use a larger N
once performance work makes that practical.

### Tactical ablation

Ablation runs paired control/treatment matches with identical teams and seeds. Each
experiment changes **one team-instruction field only**:

- `tempo`: LOW -> VERY_HIGH;
- `pressing_intensity`: LOW -> VERY_HIGH;
- `build_from_back`: VERY_LOW -> VERY_HIGH;
- `crossing_frequency`: VERY_LOW -> VERY_HIGH;
- `pass_length`: VERY_SHORT -> VERY_LONG.

The paired report measures deltas in:

- points;
- possession;
- pass attempts and pass completion;
- shots and xG;
- crosses;
- tackles;
- recoveries;
- fouls;
- opponent pass completion;
- percentage of paired seeds with at least one material observable change.

Run:

```powershell
python tools/ablate_tactics.py --matches 4 --workers 4
```

Or isolate one instruction:

```powershell
python tools/ablate_tactics.py --matches 4 --workers 4 --ablations pressing_intensity
```

A repeated near-zero effect is a **wiring-review signal**, not an instruction to inflate
a coefficient blindly. The purpose of 5.10C is to identify which controls are too weak,
too strong, disconnected, or hypersensitive before any later engine-specific tuning.

### Report version metadata

Git metadata now has a fallback that reads `.git/HEAD` directly when the `git`
executable is not available on PATH (a common GitHub Desktop setup). This avoids
`unknown` commit IDs in most local reports. Dirty-state detection still requires the
Git executable; the fallback conservatively marks the tree dirty.

### Phase boundary

5.10A-C remain valuable diagnostic infrastructure, especially for any future 2D rebuild.

The originally planned Phase 5.10D was **deferred/superseded** when the project moved the Fast Match Simulator onto the critical path instead of continuing to tune the legacy spatial engine.

Fast-simulator baseline calibration, strength/ACT curves, tactical execution and opponent-dependent tactical matchups are handled in Phase 5.11C. The legacy 2D engine remains frozen until the future layered rebuild described in `FUTURE_2D_REBUILD.md`.
