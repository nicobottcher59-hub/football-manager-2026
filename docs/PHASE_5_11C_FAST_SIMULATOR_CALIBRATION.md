# Phase 5.11C - Fast Simulator Calibration & Balance

## Objective

Calibrate the Fast Match Simulator before competition/calendar/season integration.

This phase validates the non-spatial simulator across large deterministic samples without importing or executing the legacy 2D engine.

The goals are to verify that:

- neutral matches produce football-like aggregate distributions;
- goals remain anchored to generated xG;
- quality matters without predetermining results;
- ACT/current performance matters, but less aggressively than changing underlying player quality by the same amount;
- tactical instructions alter the football process they are meant to control;
- tactical familiarity/execution changes how strongly a plan is expressed;
- meaningful randomness and upsets survive across strength gaps;
- mixed-quality/mixed-state/mixed-tactic batches remain coherent;
- season-scale workloads are fast enough for future competition simulation.

## Dedicated neutral benchmark

Phase 5.11C no longer uses the presentation demo fixture as the statistical reference fixture.

The demo fixture intentionally contains real tactical presets and incomplete familiarity data, so it is useful for demonstrations but is not a clean calibration baseline.

The new neutral benchmark freezes both teams at:

```text
OVR / ACT: 70
outfield attributes: 70
GK specialist attributes: 70
state inputs: neutral
position / role / tactic execution: 65
balanced tactical instructions
```

This removes unrelated fixture artifacts from calibration.

## Neutral reference bands

Reference bands are deliberately ranges rather than universal football constants.

The current neutral checks cover:

- goals;
- total shots;
- shots on target;
- xG;
- goals minus xG;
- pass completion;
- fouls;
- yellow cards;
- corners;
- home wins;
- draws;
- away wins.

The calibration harness also reports volatility metrics without forcing them into a single exact target:

- 0-0 frequency;
- both-teams-score frequency;
- 4+ goal matches;
- 3+ goal winning margins;
- 10+ shot differentials;
- 1.0+ xG differentials;
- 60%+ possession matches.

## First calibrated simulator constants

Phase 5.11C makes small explicit tuning changes to the Fast Simulator:

```text
home_advantage_rating = 3.1
home_shot_advantage   = 1.10
chance_quality_scale  = 0.96
base_card_probability = 0.158
```

These constants shape probability distributions only.

They do not choose a winner and do not bypass the event/chance process.

The chance-quality reduction moves aggregate goals/xG closer to the desired central range while preserving shot volume. The card adjustment moves yellow-card frequency closer to the target range. Home advantage remains moderate rather than decisive.

## Reference neutral run

A 200-match reference run after calibration produced approximately:

```text
Goals:       2.83
Shots:      25.16
SOT:         9.29
xG:          2.79
Goals - xG: +0.04
Pass %:     82.8%
Fouls:      22.27
Yellow:      3.35
Corners:    10.02
H/D/A:      38.5 / 27.0 / 34.5
```

All neutral target bands passed in this reference run.

The result is not expected to reproduce these exact values on every seed window. Calibration checks ranges and distributions, not fixed outcomes.

## Mixed realistic batch

The harness also creates deterministic mixed fixtures where both sides can differ in:

- underlying quality;
- ACT/current performance;
- tactical style;
- tactical execution/familiarity.

This is separate from the neutral baseline on purpose.

A 200-match mixed reference batch produced approximately:

```text
Goals:  2.96
Shots: 25.12
SOT:    9.45
xG:     2.84
H/D/A: 45.5 / 23.0 / 31.5
```

Mixed fixtures naturally create somewhat more xG/result spread than the identical-team benchmark.

## Strength curve

The quality curve shifts underlying attributes, OVR and ACT together for the home team while preserving the same seeds across points.

Reference 200-match samples per point:

```text
Gap    PPG    GD     xGD    H/D/A       underdog win
-20    0.64  -1.38  -1.10   16/14/69      16.5%
-10    0.93  -0.58  -0.44   24/20/56      24.5%
 -5    1.19  -0.17  -0.11   31/26/44      31.0%
  0    1.43  +0.17  +0.21   38/27/34       -
 +5    1.75  +0.62  +0.56   50/27/24      23.5%
+10    2.02  +0.97  +0.88   60/22/18      17.5%
+20    2.43  +1.73  +1.55   76/15/9        9.0%
```

The reference curve has:

```text
PPG slope / +10 quality: +0.472
xGD slope / +10 quality: +0.662
PPG monotonic violations: 0
xGD monotonic violations: 0
```

Quality therefore has a strong and orderly signal without eliminating draws or upsets.

## ACT/current-performance curve

ACT is tested independently from underlying attributes/OVR.

Reference 200-match samples per point:

```text
ACT delta   PPG    GD     xGD    H/D/A
-20         0.91  -0.63  -0.50   23/22/56
-10         1.17  -0.17  -0.14   30/27/43
  0         1.43  +0.17  +0.21   38/27/34
+10         1.78  +0.62  +0.58   51/25/24
+20         2.01  +0.99  +0.93   60/22/18
```

Reference PPG slope / +10 ACT is approximately `+0.282`, lower than the full-quality slope.

This preserves the intended distinction:

```text
underlying football quality
!=
current ability to express that quality
```

A hot/adapted/confident player matters, but a temporary ACT swing is not identical to rewriting every underlying attribute.

## Tactical execution / familiarity

The simulator already receives ACT, which includes contextual familiarity effects from the player-rating layer.

Fast simulation also models collective tactical execution directly. This is not a hidden team-strength bonus. It affects coordinated attacking, ball control, defensive coordination, pass execution and how faithfully non-neutral tactical instructions are expressed.

The execution test uses the same non-neutral plan at every point and changes only execution/familiarity.

A 200-match reference run produced approximately:

```text
Execution   PPG   Poss   Pass%   Shots   xG
20         1.14   48.9   81.8    12.52  1.31
40         1.28   50.9   82.6    13.13  1.42
65         1.50   53.3   83.5    13.92  1.57
85         1.57   54.5   84.0    14.28  1.63
100        1.67   55.4   84.4    14.50  1.69
```

Poor tactical familiarity is deliberately more damaging than perfect familiarity is beneficial. A team that barely understands its plan should lose coordination; a perfectly drilled team becomes better at executing the plan, but does not receive an artificial super-team multiplier.

Poorly learned pressing also creates more mistimed fouls/cards, while better execution makes tactical intensity more precise.

## Tactical ablation

Ablations change one tactical input at a time with paired seeds.

The current consumers behave directionally as intended:

- more possession orientation increases possession and pass completion;
- more directness lowers pass completion;
- more pressing increases foul pressure and reduces opponent pass completion;
- more tempo slightly increases shot volume;
- more width increases corner generation;
- more crossing frequency increases corner generation.

Single-variable changes deliberately do not receive a universal PPG bonus.

Tactics influence specific football processes and combinations/matchups, not a hidden `better tactic` score.

## Tactical matchup interactions

Phase 5.11C now includes paired matchup tests with equal-quality teams and the same random seeds. The home plan stays fixed while the opponent changes between a tactically difficult and tactically favorable setup.

A 200-match reference run produced approximately:

```text
Matchup                    PPG delta   xGD delta
direct vs high line          +0.35       +0.47
possession vs low press       +0.65       +0.86
high press vs possession      +0.80       +1.00
wide vs compact block         +0.25       +0.32
```

Interpretation:

- direct play attacks space behind a high line, but loses much of that edge against a deep compact block;
- possession build-up performs substantially better against passive pressure than against an organised high press;
- high pressing disrupts possession build-up, while direct play can bypass part of the press;
- attacking width can stretch a compact defensive block.

These are interaction effects. No tactic receives a flat result bonus and the same instruction can be favorable in one matchup and unfavorable in another.

## Synthetic league

The calibration suite can simulate a synthetic double round-robin league without any competition-system implementation.

For 20 teams:

```text
20 teams
380 fixtures
```

A reference run produced:

```text
Quality / points correlation: +0.892
Strongest team rank: 2
Weakest team rank: 19
Top-half mean quality delta: +5.3
Bottom-half mean quality delta: -5.3
```

The signal is strong, but the table is not predetermined: the nominally strongest team does not need to finish first and weaker sides can outperform stronger sides across a season.

## Performance

The reference calibration environment continues to process hundreds of matches per second.

Typical measurements are roughly:

```text
~300+ neutral matches/sec
~250+ synthetic-league matches/sec
```

Performance will be measured again after substitutions, injuries and richer match-state systems are added.

## Tooling

Run the complete calibration suite with:

```powershell
$env:PYTHONPATH = "src"
python tools/calibrate_fast.py --matches 200
```

`--matches` is the sample count per baseline/curve/tactical scenario.

The tool writes Markdown and CSV reports under:

```text
reports/fast_calibration/
```

Reports include:

- neutral baseline;
- mixed batch;
- strength curve;
- ACT curve;
- tactical execution;
- tactical ablations;
- tactical matchup interactions;
- synthetic-league standings.

## Architectural boundary

`football_manager.fast_calibration` does not import:

```text
football_manager.simulation
SpatialMatchEngine
MatchFlowController
```

The legacy 2D engine remains frozen and outside the critical path.

## Tests

Phase 5.11C adds automated checks for:

- clean neutral benchmark construction;
- neutral statistical target bands;
- healthy match-to-match volatility;
- monotonic strength response with surviving upsets;
- ACT sensitivity below full-quality sensitivity;
- meaningful tactical-execution scaling;
- directional tactical consumers;
- opponent-dependent tactical matchup/counter behavior;
- mixed quality/ACT/tactic batches;
- synthetic 20-team league behavior;
- no legacy 2D dependency.

Expected complete test collection after this phase:

```text
362 tests
```

## Next step

Phase 5.11D - Extra Time & Penalties Refinement.

The 90-minute Fast Simulator is now sufficiently instrumented and balanced to move on to a focused refinement of knockout resolution before competition integration.


## Coach vs squad quality benchmark

The calibration suite includes a paired home/away experiment that holds player quality fixed while changing only the weaker team's tactical plan and execution.

The stronger squad is fixed at `+10` structural quality. The benchmark compares:

- `quality_baseline`: weaker side uses a generic neutral plan;
- `better_coach`: weaker side uses a high-execution counter-plan tailored to the stronger team's possession/high-line identity;
- `wrong_plan`: weaker side has equally high execution but a tactically poor matchup.

The same paired seeds are reused across all scenarios. The test is designed to prove that a well-chosen plan can compensate for a moderate squad-quality deficit through football processes (xG, shots and results), while high tactical execution with the wrong plan does not receive a hidden universal bonus.
