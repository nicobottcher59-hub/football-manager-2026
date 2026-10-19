# Current Status

## Current development state

Phases 1-4, legacy spatial Phases 5.0-5.9, calibration infrastructure 5.10A-C, Fast Simulator Phases 5.11A-E, the disposable Phase 6.0 development UI, contextual player assignment Phase 6.0b, the generic Phase 6.1 Competition Framework, Phase 6.2 Round-Robin League, Phase 6.3 Knockout Competitions and Phase 6.4 Multi-Stage Competitions, Phase 6.5 Calendar & Scheduling and Phase 6.5a fictional EFL date-slot integration and combined Phases 6.5b + 6.6 English domestic cups / persistent world competition results, and Phase 6.6a + 6.6b UEFA/EFL Trophy integration and physical/calendar fixes, plus Phase 6.7 multi-season English DEV integration, are implemented. The Fast Simulator is the current critical-path match resolver; the legacy 2D path is frozen.

## Completed

- Python project structure.
- Player identity.
- Technical, mental and physical attributes.
- Optional goalkeeper-specific attributes.
- PlayerState separated from base ability.
- Positional familiarity.
- Original and current primary positions.
- JSON player loader.
- Sample outfield and goalkeeper data.
- Club domain model.
- Squad membership and lookup.
- Formation representation using named slots.
- Starting XI and bench representation.
- Club/squad/lineup validation.
- Team tactical presets.
- Full team instructions split by phase of play.
- Independent in-possession and out-of-possession line widths and inter-line gaps.
- Centre-protection and cross-tolerance defensive instructions.
- Exactly five base roles for every current Position.
- Individual role defaults and player-instruction overrides.
- Position/player/role tactical targets.
- Role suitability foundation based on existing player attributes.
- Separate tactical and role familiarity state.
- Behavioral role-similarity foundation for future adaptation.
- Tactical style analyzer based on effective instructions.
- Tactical style metrics for attacking width, defensive width, compactness and central protection.
- Immutable MatchSnapshot boundary.
- Frozen home/away lineups, attributes, current player state and familiarity data.
- Frozen team tactics, roles and effective player instructions.
- Match date/time context with timezone-aware kickoff.
- Competition table / cup aggregate context snapshots.
- Generic CompetitionDefinition / CompetitionEdition / CompetitionStage / CompetitionFixture domain.
- Configurable qualification routes for continental places, promotion, relegation and playoffs.
- Double round-robin league generation and validation, including 20-club 38-round / 380-fixture structure.
- Phase 6.5a: Championship, League One and League Two 2026/27 published matchweek kickoff slots, 46 rounds / 552 each, mapped only to fictional 24-club double round-robin pairings marked GENERATED.
- DEV-only tier-separated strength indices and table/fixture inspectors; no real EFL club/player imports.
- Phase 6.5b: two independent English domestic cup season structures (FA Cup and Carabao Cup), published round dates, staggered entries, fictional draws and entrants, correct single/two-leg final-stage behavior. FA early qualifying round dates are recorded but not simulated.
- Phase 6.6: one canonical `WorldSeasonRunner` for all four domestic leagues and both cups, deterministic cheap background result generation, managed FastSim result registration, winner-driven cup progression, conflict-aware rescheduling, exact draw history and JSON save/load.
- DEV sandbox `Continue` now advances world fixtures chronologically without playing the managed club's upcoming fixture, plus a real FA Cup / Carabao bracket inspector and world-results save/load buttons.
- Seeded first-season vs generated later-season fixture provenance and reusable round/venue templates.
- League results, partial/full standings, points and configurable tie-breaker ordering.
- Standings bridge into immutable match competition context.
- Knockout round definitions with single-leg or two-legged ties.
- Seeded external cup draws and generated in-world cup draws.
- Aggregate tie resolution without away-goals rules.
- Deciding-leg extra-time/penalty context wired to the existing Fast Simulator competition boundary.
- Automatic advancement of knockout winners into the next round.
- Stadium, pitch, weather and referee context snapshots.
- Home/away kit-selection snapshots.
- Deterministic simulation seed stored with each MatchSnapshot.
- Spatial Match Engine package.
- 2D pitch dimensions sourced from the frozen stadium snapshot.
- 22 active PlayerAgentState objects with X/Y position, velocity and facing.
- BallState with spatial position/velocity foundation.
- Fixed 0.25-second MatchClock timestep.
- Match-owned deterministic random source.
- Deterministic kickoff side and initial possession metadata.
- Home/away spatial orientation and mirrored starting shapes.
- Fixed-step movement integration for players and ball.
- Playback-chunk independence foundation for future x1/x2/x4/instant viewing.
- Tactical target positions derived from possession phase and formation.
- Independent tactical widths for defence, midfield and attack are consumed spatially.
- In/out-of-possession inter-line gaps, block height and compactness are consumed spatially.
- Protect-centre and cross-tolerance settings narrow defensive targets instead of applying stat bonuses.
- Role/individual positional instructions influence spatial targets.
- Possession changes trigger smooth transitions between team shapes without teleporting players.
- Tactical/role/position familiarity influences bounded repositioning speed without changing Overall.
- Team-shape metrics expose measurable line widths and inter-line distances.
- ASCII tactical debug renderer and Phase 5.1 visual review demo.
- Player perception system with attribute-influenced awareness radius.
- Spatial pressure and local-space evaluation.
- Goal direction/distance perception for both attacking orientations.
- Passing-lane analysis with lane openness, forward progress and receiver space.
- Explicit synchronized controlled ball ownership for decision evaluation.
- Context-valid possession action candidates: hold, short/progressive/long pass, carry, dribble, cross, shot and clearance.
- Action utility split into tactical fit, spatial value, player capability, decision quality and risk.
- Effective team and individual tactical instructions consumed by decision preferences.
- Seeded probabilistic action choice separated from later execution success.
- Phase 5.2 perception/decision debug report with normal and heavy-pressure scenarios.
- Phase 5.3 pass execution system for short, progressive and long passes.
- Ball trajectories travel through fixed simulation ticks instead of teleporting between players.
- Pass execution quality is separate from decision quality and consumes relevant attributes, distance and pressure.
- Tactical pass-speed instructions alter actual ball velocity/travel time.
- Moving receivers can be led using their current spatial velocity.
- Spatial pass interceptions can transfer possession to an opponent before arrival.
- Reception has a separate first-touch resolution with completed, intercepted, misplaced and bad-control outcomes.
- Completed passes can chain into controlled multi-pass possession sequences.
- Phase 5.3 passing/possession debug demo with open play, interception and bad-control scenarios.
- Phase 5.4 active spatial pressing plans around the controlled ball carrier.
- Team pressing intensity changes engagement radius, committed presser count and real closing movement.
- Pressing schemes and force-direction instructions alter pressure commitment/approach geometry.
- Individual pressing intensity and pressing targets affect player-specific pressing behaviour.
- Defensive coverage blends tactical shape with zonal/mixed/man marking behaviour.
- Explicit individual marking targets and defensive tracking are consumed by coverage movement.
- Defensive duel profiles separate tackle willingness from tackle execution quality.
- Tackles consume tackling, anticipation, positioning, decisions, physical strength/balance/acceleration and attacker resistance attributes.
- Defensive support and goal-side spatial position affect duel probability.
- Duel outcomes support defender control, attacker retention and genuine loose balls.
- Basic broken-press detection exposes when the carrier escapes the primary pressure.
- Phase 5.4 pressing/defensive-duel debug demo.
- Phase 5.5 controlled carries through real fixed-step spatial movement.
- Carry targets consume open space, individual `attack_space`, positional behaviour and team central focus.
- Phase 5.5 off-ball run plans with forward, overlap, underlap, inside and wide run types.
- Individual `forward_runs`, `attack_space` and roaming influence real run targets/priority without modifying attributes.
- Team overlap frequency is consumed by full-back overlap/underlap movement.
- One-on-one dribbles separate attacker/defender execution quality and support attacker-wins, defender-wins and loose-ball outcomes.
- Successful dribbles create an escape carry rather than teleporting the attacker beyond the defender.
- Progressive passes lead real forward-moving receivers more aggressively than short passes.
- Crosses and cutbacks travel through the same 2D ball state with execution error, speed and height.
- Existing cross types (`EARLY`, `BYLINE`, `LOW`, `HIGH`, `CUTBACK`, `MIXED`) are consumed by progression execution.
- Cross paths can be intercepted and receptions can finish as completed, intercepted, misplaced or bad-control outcomes.
- Phase 5.5 ball-progression debug demo.
- Phase 5.6 contextual xG model based on distance, angle, pressure, blockers, body part, chance origin and goalkeeper position.
- Finishing ability is separated from pre-shot xG and instead affects shot execution/placement.
- Foot shots and headers use distinct execution and ball-speed profiles.
- Shots travel through the fixed-step 2D ball state with explicit height and physical goal-plane targets.
- Defenders can physically block shot paths and create loose rebounds.
- Goalkeepers receive real reaction targets and movement during active shots.
- Dedicated goalkeeper attributes drive save/handling behaviour when available, with a backwards-compatible fallback for old fixtures.
- Goalkeeper ability is separated from goalkeeper positional disadvantage in the chance model.
- Shot outcomes now include goal, saved, parried, blocked, off-target and woodwork.
- Saves transfer controlled possession to the goalkeeper; parries/blocks/woodwork create real loose rebounds.
- Ball height is included in deterministic MatchState signatures.
- Phase 5.6 shooting/goalkeeper debug demo.
- Phase 5.7 autonomous `MatchFlowController` orchestrating existing decision/action systems.
- Competition-derived match decider metadata for draws, extra time + penalties, or penalties directly after regulation.
- First-half/second-half lifecycle with period-aware official time display and bounded added time.
- Extra-time halves and deterministic penalty shootouts when a tied competition context requires a winner.
- Current match score, aggregate score resolution and final `MatchResult`.
- Goal results now update the score and trigger kickoff for the conceding team.
- Basic kickoff, throw-in, goal-kick, corner and free-kick restart handling.
- Touchline/goal-line restart detection using last-touch side.
- Basic foul-to-free-kick match-flow path.
- Bounded loose-ball recovery so autonomous play cannot remain permanently ownerless.
- Structured match-flow event stream ready for later text commentary and 2D presentation.
- Complete autonomous matches can finish without manual debug action calls.
- Phase 5.7 match-flow debug demo.
- Phase 5.8 live player fitness/fatigue state initialized from the immutable MatchSnapshot.
- Exertion, stamina, natural fitness, temperature, humidity, pitch condition and surface now affect live fatigue cost.
- Current fatigue/fitness and environmental conditions affect real movement speed without changing base physical attributes.
- Pitch/surface conditions affect ground-ball speed; strong wind and severe weather increase long/aerial execution uncertainty.
- Rain/pitch/fatigue affect technical execution and first-touch context rather than rewriting technical attributes.
- Fog/heavy weather reduce useful perception radius.
- Home context is a small situational pressure-resilience effect, not an Overall/stat bonus.
- Referee strictness, contact tolerance, card tendency, penalty tendency and advantage tendency are consumed by foul decisions.
- Yellow, second-yellow-red and direct-red discipline outcomes are implemented.
- Dismissed players remain in the match record but are removed from active spatial participation.
- Penalty-area detection works for both attacking directions and can trigger in-match penalty events.
- MatchResult exposes final runtime player condition and discipline for a future WorldUpdater.
- Phase 5.8 match-context debug demo.
- Phase 5.9 presentation package separated from simulation logic.
- `MatchPlaybackSession` exposes x1/x2/x4 as fixed-tick consumption multipliers and instant result through the exact same MatchFlowController.
- Playback batching is tested to preserve event sequence, result and statistics for identical snapshot/seed.
- Live possession and event-derived match statistics: passes, shots, shots on target, xG, goals, saves, tackles, recoveries, dribbles, crosses, fouls, cards and corners.
- Shot events expose contextual xG metadata to presentation without recomputing or changing the shooting model.
- Deterministic Spanish commentary formatter with highlights, normal and detailed densities.
- Functional tkinter debug frontend with score/time, 2D pitch, live ball/player positions, commentary feed, live stats, play/pause, x1/x2/x4, instant result, same-seed restart and new-seed simulation.
- Phase 5.9 integrated-match stabilization after the first visual review: human-scale action cadence, ball-following tactical blocks, moving pass receivers, spatially audited events and reduced foul/card frequency.
- Phase 5.9 organic movement overhaul after the second visual review: every active off-ball player now owns a persistent live intention rather than being dragged directly toward a formation coordinate.
- Formation/tactical coordinates are structural anchors rather than rails. Full-backs can overlap/underlap/invert, pivots can drop between centre-backs, centre-backs can step into space, interiors can support or attack beyond the ball, wingers can hold width/come inside/drop/run behind and forwards can drop/connect/attack depth.
- Coordinated relationships now influence movement: a dropping pivot fans centre-backs, a full-back rotation changes the winger's available behaviour, the opposite full-back normally balances an attacking full-back, a dropping striker opens depth for wide/interior runners and midfield runners balance one another.
- Off-ball movement persists for several simulated seconds with acceleration/deceleration instead of reselecting a formation destination every 0.25-second tick.
- Long passes have a real aerial arc and live runs increase the spatial value of progressive/long passing options. Action-family selection no longer lets many pass targets mechanically outvote carry/dribble/cross/shoot families.
- Defensive coverage now blends with the player's existing movement instead of replacing it completely, so tracking/cover responsibilities coexist with the defensive line and recovery movement.
- Viewer target overlay displays live movement intentions; team-shape overlay displays actual line relationships rather than a misleading convex hull.
- x1 playback is presentation-compressed to approximately nine real minutes for a regulation match; x2/x4 only consume the same fixed 0.25-second ticks faster.
- Open-play crosses now require plausible advanced wide origins and target attacking/midfield runners instead of falling back to centre-backs.
- Added-time display is clamped to the officially announced amount; high added time remains possible but is no longer systemic in the reference simulation.
- In-match substitutions can be requested during live play and are applied at the next natural stoppage.
- Live tactical management can change formation (slot-preserving runtime variants), team instructions, roles and selected individual instructions without mutating MatchSnapshot.
- Same snapshot + seed + manager actions at the same simulation ticks remains deterministic.
- Viewer modes for 2D only, text only or combined 2D + commentary.
- Debug overlays for tactical targets, press assignments, defensive coverage, passing lanes, team shape and coordinates.
- Automated tests.

- Phase 6.1 stable competition definitions separated from season-specific editions.
- Ordered competition stages with generic round-robin, knockout, group, league-phase and playoff stage kinds.
- Sporting fixtures represented independently from kickoff scheduling; Phase 6.5 now maps them into the unified `SeasonCalendar` without changing sporting identity.
- Competition regulations expose substitution limits and stage-specific match deciders to existing MatchContext snapshots.
- Configurable qualification rules can map league positions to continental berths, promotion, relegation or playoffs.
- Cup-winner/title-holder qualification sources and next-eligible-league-position fallback are represented for later cross-competition allocation.
- Competition definitions, editions, stages, fixtures and qualification rules support lightweight dict round-tripping for future persistence/data loading.


- Phase 5.10A calibration harness with deterministic batch scenarios and CSV/Markdown reports.
- Phase 5.10B isolated RNG streams and auditable shot/event integrity.
- Phase 5.10C controlled strength curves and tactical ablation experiments.
- Phase 5.11A derived player `OVR` based on weighted underlying attributes rather than a simple average.
- Phase 5.11A separate contextual `ACT` rating that can move above or below OVR without rewriting player ability.
- Contextual 0-100 performance scales use 65 as neutral: values above 65 can help and values below 65 can hurt, with a deliberately soft middle rather than linear punishment.
- Positive ACT modifiers are individually small; a large upside is reserved for multiplicative total-context excellence, so one strong factor cannot inflate ACT by itself.
- Position, role and tactical familiarity are ACT inputs rather than alternate per-role Overall ratings; completely alien positions are deliberately much harsher than unfamiliar roles or tactics.
- `adaptability` is an explicit mental attribute that softens unfamiliarity while learning without granting a free performance bonus.
- Confidence is a first-class player-state input with bounded update helpers; normal low-confidence states have moderate impact, while values below 5 can become exceptionally damaging.
- Physical condition is one-sided for ACT: 75-100 is penalty-free, while values below 75 progressively reduce effective performance.
- Fatigue is not double-counted in ACT; existing workload mechanics already reduce fitness/condition.
- MatchSnapshot now freezes both `overall_rating` and lineup-context `current_rating` for every player.
- Phase 5.11B Fast Match Simulator MVP consumes MatchSnapshot without importing or instantiating the spatial 2D engine.
- Fast simulation uses separate deterministic RNG streams, compact team profiles, probabilistic possession/chance/shot/discipline processes and actual XI player attribution.
- FastMatchResult exposes score, aggregate/tiebreak outcome, goals/scorers/assists, cards, team statistics, individual statistics and post-match condition estimates.
- Fast simulation supports draw-allowed fixtures, extra time + penalties, penalties after 90 and existing cup aggregate context.
- Equal-team MVP batches are guarded around football-like totals.
- Phase 5.11C adds a dedicated neutral 70-v-70 benchmark instead of calibrating against presentation-demo artifacts.
- Phase 5.11C calibrates neutral totals, volatility, quality/ACT curves, meaningful tactical execution, one-variable tactical ablations, opponent-dependent tactical matchup/counter effects, an explicit coach-vs-squad-quality benchmark, mixed realistic batches and a synthetic league.
- Fast-simulation chance quality, card frequency and moderate home advantage received their first explicit calibrated tuning pass.
- Reference neutral batches keep goals close to xG while preserving roughly 25 shots, 9 shots on target, 22-23 fouls, 3-4 yellows and about 10 corners per match.
- Strength and ACT curves are monotonic in the reference run while draws and underdog wins survive even at large gaps.
- The Fast Simulator remains capable of processing hundreds of matches per second and the calibration package has no dependency on the legacy spatial engine.
- Phase 5.11D refines knockout resolution without changing the calibrated 90-minute model.
- Extra time is simulated as two lower-paced 15-minute periods with condition/stamina-driven energy effects rather than a full-speed extra third of a match.
- Competition `extra_time_additional_substitutions` is consumed by the Fast Simulator; extra-time substitutions consider freshness plus positional/role/tactical familiarity and reconcile player minutes.
- FastMatchResult separates regulation goals, extra-time goals and shootout score and exposes extra-time substitutions and individual penalty-kick events.
- Penalty shootouts are resolved kick by kick using penalty skill, finishing, composure, confidence, condition, goalkeeper quality and escalating pressure; shootout kicks never count as match goals/xG/shots.
- Same snapshot + seed reproduces the complete knockout path including substitutions and every shootout kick.
- Phase 5.11E replaces the temporary low-impact condition model with meaningful match depletion and calendar recovery.
- Neutral outfield starters now finish 90 minutes around the mid-50s condition on average, with a deliberately wide stamina spread; neutral 120-minute long-runners can range from near depletion to the 40s depending on stamina and workload.
- Stamina strongly controls in-match resistance and also contributes to between-match recovery; natural fitness remains the primary recovery attribute.
- Tactical workload affects physical cost by position: high pressing taxes the first line/midfield more, while deep defending increases defensive-unit workload.
- FastPlayerStatistics now exposes both `condition_after` and `fatigue_after` for future world/calendar persistence.
- Recovery services can persist post-match state and recover players across calendar days without making the Fast Simulator mutate world objects.
- Condition below 75 now has a meaningful one-sided ACT cost so congested schedules can make a fresh substitute a better current option than a tired superior player.
- Phase 6.0 adds a disposable Tkinter development UI without moving football logic into presentation code.
- The development UI exposes Home, Squad, Tactics, Calendar and Competitions screens.
- Squad view exposes OVR, contextual ACT, condition, fatigue, confidence, form and sharpness, plus a basic XI/bench swap for testing position-context consequences.
- Tactics view treats presets as starting points and can manually change formation, compatible slot roles and every editable enum/bool team instruction from the real tactic domain model.
- The disposable tactics board renders the XI on formation slots and supports starter-to-starter drag-and-drop swaps, including intentionally absurd out-of-position assignments; roles remain attached to the tactical slots and ACT/familiarity are recalculated from the real domain state.
- The Tactics screen exposes XI/squad tactical familiarity, XI chemistry, XI condition and squad/XI morale as collective decision-support metrics. Familiarity responds to plan/role/position changes; chemistry is fed into the real ACT chemistry adjustment for the submitted XI.
- Phase 6.0 chemistry uses explicit development-sandbox cohesion inputs until the later relationship/cohesion system becomes persistent world state; it is not a UI-only bonus.
- Quick Sim builds a real MatchSnapshot, invokes FastMatchSimulator and persists returned post-match condition/fatigue through the existing world-facing condition service.
- Competitions inspects the Phase 6.2 development league, Phase 6.3 knockout bracket and a Phase 6.4 multi-stage competition. From Phase 6.5, the managed DEV chronology is backed by the same `SeasonCalendar` domain used by real schedules; Continue reads the next scheduled fixture from that calendar and played fixtures transition to `PLAYED`.
- Phase 6.5 separates sporting fixtures from scheduled fixtures, supports timezone-aware kickoffs, scheduled/played/postponed/cancelled states with validated transitions, original-date preservation, rescheduling, cross-competition calendar merging and same-day-conflict/rest detection.
- Competition `SchedulingWindow` rules and slot search can locate/reassign a fixture to the earliest valid date while respecting club rest requirements.
- Future league dates are generated from a new season policy plus blackout periods; they are not created by copying prior-season dates or adding 365 days.
- The official Premier League 2026/27 fixture snapshot is packaged as data and validated as 380 matches / 20 clubs / 38 rounds / complete double round-robin. It is visible in a separate sandbox Calendar tab and is not attached to the fictional Northbridge world.
- Resetting the sandbox advances the development seed so repeated visual simulations do not replay the same random stream; deterministic engine behavior remains available when a fixed MatchSnapshot seed is supplied.

## Tests

Current expected result:

```text
570 tests collected after 6.6a/b. Run independent groups if the monolithic suite exceeds the environment time budget.
```

Run with:

```powershell
python -m pytest
```

## Important current design decisions

- Attribute scale: `1-100`.
- No single Overall rating should drive match simulation.
- Match actions will combine the attributes relevant to each specific action.
- Player ability and current state are separate concepts.
- Position familiarity is dynamic.
- Tactical familiarity and role familiarity are separate from player ability.
- Role suitability describes attribute fit and never rewrites player attributes.
- Real/display names must remain decoupled from internal IDs.
- Formation slots are separate from positions so repeated positions are supported.
- Submitted lineups are immutable; in-match state is mutable and separate.
- Roles are behavior presets, not locked behavior and not hidden stat bonuses.
- Individual instructions override role defaults.
- Tactical presets are editable starting points, not engine bonuses.
- The Match Engine uses effective tactical instructions, not preset labels.
- Tactical style names are inferred from configuration and are descriptive only.
- In-possession and out-of-possession team shapes are independent.
- Every meaningful tactical control must eventually have an explicit Match Engine consumer or be removed/simplified.
- MatchSnapshot is an immutable kickoff boundary: later world changes cannot alter an already-started match.
- Kits are presentation data; weather, pitch, referee and tactical context are prepared as simulation inputs.
- Competition rules are not user-configurable match settings.
- Same snapshot + same seed + same engine version must produce a reproducible simulation.
- The Match Engine owns its random source; simulation code must not use uncontrolled global randomness.
- Match simulation uses a fixed internal timestep. x1/x2/x4/instant are playback/consumption modes, not different simulation precisions.
- Home attacks toward positive X and away toward negative X in the global pitch coordinate system.
- PlayerAgentState is mutable in-match state and references immutable PlayerMatchSnapshot data.
- The Match Engine never mutates persistent Player/Club/Tactic world objects directly.
- Match results will not be predetermined.

## Current milestone

The Fast Match Simulator is now the critical-path match resolver for future competition, calendar and season systems. Phase 6.0 adds a disposable development UI so those systems can be inspected as they are added instead of being developed only through console output.

The legacy 2D engine remains frozen as an experimental path and no longer blocks core game development. MatchSnapshot, OVR/ACT, the calibrated fast-simulation path and the disposable UI shell now provide the foundation needed to build the wider management game.

## Next development step

Phase 6.7 - full season lifecycle: champion/qualification rules, promotions/relegations and creating 2027/28. Full career saves, squad-based background simulation, regionalised early Carabao draw rules, and real clubs are still future work.

The competition and calendar domains can now define sporting fixtures, assign authoritative dates, import a real first-season schedule and generate future-season dates. The competition runner now advances and persists 2026/27 league/cup results across the domestic DEV world. The next critical step is a repeatable *season lifecycle* with accurate outcome rules and promotion/relegation paths.

## Phase 6.6a + 6.6b - UEFA, EFL Trophy and balance fixes

Done: canonical Champions/Europa/Conference league phases (36 clubs, 8/8/6 matches), top-8 direct qualification, 9-24 knockout playoff, full knockout to champions; 64-entry EFL Trophy (48 L1/L2 seniors + 16 invited U21), 16 groups, group shootout points and regional knockout. All fictitious matchups are GENERATED against official 2026/27 round windows. No real-club/draw importer or full UEFA pot/country restrictions yet.

Done: more meaningful ACT penalty for low physical condition; moderate morale mean reversion; V/E/D including penalty shootout wins; no stale fixed conditional calendar entries; managed Northbridge Champions fixtures; sandbox inspectors for all four staged tournaments. 2,942 world fixtures on a full DEV season simulation. Current WorldSeasonRunner schema is v2, carrying staged progression. This is still a partial results-only save.

The next phase is 6.7 full season integration and rollover, not additional fixture inspectors.

## Phase 6.7 — Implemented: full multi-season English DEV competitions

`WorldCareer` archives independent 2026/27, 2027/28, etc. worlds; `SeasonReport` validates champions, completed results, playoff winners and UEFA participants. EFL promotion playoffs are canonical competitions: Championship 6 clubs / 7 games, League One and Two 4 clubs / 5 games each. The transition preserves 92 unique professional club IDs per season and creates two outside arrivals at the League Two/National League boundary. Annual schedules and cup windows after 2026/27 are **GENERATED**, including new round-robin pairings. The 2026/27 world now finishes with **2,959 fixtures** including 17 playoffs. World runner schema v3 stores playoff configuration.

The sandbox adds a default-enabled but reversible **weaker-opponents DEV mode**, a **Simulate entire season** button (FastMatchSimulator for Northbridge, background resolver elsewhere), a **Start next season** button, updated playoff inspectors and result-archive JSON save/load. This is a deliberately disposable UI. It is **not** a persistent save for players' physical/tactical state or full squad/world management; those systems remain future work. Multiple seasons can be simulated and archived at competition level.

Remaining work after 6.x: real-club integration, accurate future UEFA access lists/association coefficients, complete youth and non-league structures, long-term club/player state, full manager savegames, player transfers/contracts/scouting/finances and later production UI. The old spatial 2D engine is still frozen.

Details: `docs/PHASE_6_7_FULL_SEASON_INTEGRATION.md`.

## UI-1 status — Dashboard shell (after completed Phase 6.7)

A React + TypeScript + Vite dashboard is now available under `frontend/` for visual review, containing the agreed club overview, next match, competition tabs (league tables / cup statuses), compact squad metrics, a tactical pitch with eleven **OVR** badges, Inbox/Club News and a prominent Continue control. All displayed data are **explicitly fictional demo data**. Continue changes only the rendered demo date by one day and announces that the Python world has not advanced. Non-Home destinations are placeholders. This is a frontend shell, **not a running game**, not a full manager save, and not yet an Electron/Tauri desktop package.

FastMatchSimulator, WorldCareer, result persistence and all existing Tkinter UI paths remain untouched. Next tasks: add typed Python application read models, then a genuine safe daily-advance command, finally a desktop host. See `docs/PHASE_UI_1_DASHBOARD_SHELL.md`.


## UI-2 status — Squad / player detail / team tactics (DEV only)

Implemented: Python-local read/write adapter with 11 real DEV starters, 7 real bench members, contextual OVR/ACT, 4 status indicators, player selection, formation changes, role catalog, all 15 individual overrides including target types, 44 team fields, 11 presets, swapping starters/substitutes. One phase selector drives the schematic disc board and the relevant in/out-of-possession controls; Transition and Match Management remain available. The current DEV roster has no outside-matchday players. Set-piece taker assignment is NOT implemented. The Home dashboard/Continue remain demonstration-only; Squad and Tactics edits are ephemeral and are not complete career saves. See `docs/PHASE_UI_2_SQUAD_TACTICS.md`.


## UI-3 checkpoint — Squad roster and unified Tactics (pending Windows acceptance)

The entire Squad section is now a sortable/fixed-name roster table with General, Attributes and Season Stats tabs, search, filters and a contextual player-expanded management row. Tactics owns the lineup, individual role editor, and the 44-field team-tactics editor with animated schematic discs and a single in/out possession toggle. Player positional familiarity is a live Python read, not a mockup; OVR and ACT appear with a decimal. Existing career/competition simulation remains unchanged. The new shirt-number/availability switches are session-only UI metadata; market values, happiness, contracts, chats, training, season player aggregates and xA are still not implemented. See `docs/PHASE_UI_3_SQUAD_ROSTER.md`.

## UI-3.1 — Visual polish + Home connected to Python DEV

UI-3.1 keeps the UI-3 layout and scale, enhances depth/color and adds consistent deterministic illustrated player portraits in **Home, Squad and Tactics**, including nationality in roster and player details. Squad's expanded row now separates profile, current state, positional familiarity, attribute highlights and player-management actions. The Home starting XI, formation, dynamic status metrics, current date and opponent read **the same local Python DEV session** used by Squad/Tactics; returning to Home after changing a starter shows the changed team. OVR/ACT use one decimal.

Start in Windows with `INICIAR_INTERFAZ_WINDOWS.bat` (no npm). **This is still a temporary DEV session**: no persistence, no daily Continue, no contracts/market/training/player conversations/season ledger. The league table, news, manager/club story content and several club card fields remain labeled visual demo data; Python calendar match metadata is only partially available. See `docs/PHASE_UI_3_1_VISUAL_POLISH.md`.

## UI-3.2 — Monthly managed Calendar + position sort

`Calendar` is now an operational **read-only** monthly presentation of Northbridge's known generated 2026/27 fixtures from the Python season, with per-competition filtering, date navigation, H/A, stable provisional crests, and genuine results including shootouts and knockout aggregates when present. No unknown fixtures, standings, scores, weather or referees are invented. Home's next-match shortcut opens Calendar. The full world day-by-day `Continue` command and persistent squad/tactics game saves are still **pending**. Squad position sorting now follows football positions, not alphabetical text. See `docs/PHASE_UI_3_2_CALENDAR.md`.

## UI-3.3 — Live Competitions centre (for Windows acceptance)

The portable UI now has Competition selection for **10 registered world competitions**: Premier League, Championship, League One, League Two, FA Cup, Carabao Cup, Champions League, Europa League, Conference League and EFL Trophy. Every selected stage displays a dominant **league/group table or knockout bracket** and a secondary panel containing **all fixtures in the selected matchday/round** with navigation. Cup brackets show actual confirmed draw history; zoom and pan work, and no future opponents, links or predictions are fabricated. UEFA uses its 36-team league tables and existing knockout plan metadata; the EFL Trophy has 16 selectable four-team groups. Match scores, penalties and aggregate qualifiers are kept distinct.

No full-save persistence, world/day Continue, transfers, xG aggregation, imported club assets or financial data were added. Northbridge, rivals, and participants remain generated/fictional; the English/UEFA competition algorithms were not rewritten. Windows user acceptance is pending. Details: `docs/PHASE_UI_3_3_COMPETITIONS.md`.


## UI-3.3.1 — Competitions bracket refinements (Windows acceptance pending)

Controlled club tabs only, FA Cup late entrant detection, two-sided cup bracket with central Final, four semantic zoom levels, drag/scroll and pending draws without predicted pairings. Right round fixture panel unchanged. Tests/screenshots completed locally; user Windows acceptance outstanding. No Continue, persistence or match-engine changes.

## UI-3.3.2 — Competition Explorer (Windows acceptance pending)

UI-3.3.2 hotfix: the user-facing `Competitions` route retains UI-3.3.1 club-only horizontal tabs and includes FA Cup for a late-entering club. `Other Leagues` is a **separate sidebar destination**, not a tab inside Competitions. Its hierarchical directory has always-visible Continent, national Country, type and division controls. Country options include future regions (e.g. Spain, Argentina) that show explicit empty states until the world has those leagues; only the ten real registered DEV-world competitions are clickable. Brackets, their zoom and the full fixture side panel are unchanged. Python and Windows `.bat` remain Node-free; Continue/savegame remain pending. Tests and visual browser checks are documented in `docs/PHASE_UI_3_3_2_COMPETITION_EXPLORER.md`.


UI-3.3.2 hotfix 2: corrected competition-index schema synchronization between portable UI and Python. The Python module is re-delivered in the incremental hotfix to repair installations with an older index; the frontend checks `schema_version=2` and does not render stale, unpartitioned ten-competition responses. Default DEV collection is four club competitions and six other competitions.

## UI-3.4 — Daily Continue + Calendar auto-simulation (pending Windows acceptance)

The Python portable UI now has authoritative daily progression. The global Continue advances one day and becomes **Go to Match** on a day with an unplayed managed fixture; the match screen is not built yet. Calendar supports selecting any future/current day and **auto-simulating through that date, including the managed club's own fixtures** via FastMatchSimulator, with other world fixtures via WorldSeasonRunner. Home's league table and recent match form now come from the same world. Calendar and Competitions update from registered results; active session changes commit in memory only when the whole command succeeds. Results, tactical/player changes and date remain **temporary DEV session state** until complete career persistence is implemented; the UI does not yet start a new season. Required-intervention event logic also does not yet exist. See `docs/PHASE_UI_3_4_DAILY_CONTINUE.md`.

## UI-3.4.1 — Calendar progress (local implementation; awaiting Windows validation)

Added whole-cell date selection on days with or without club fixtures, an explicit past-day color hierarchy, and an asynchronous auto-simulation progress overlay displaying only canonical Python match results, one after another. The backend publishes paginated day/result status from a working session copy and commits the game session only after full success. The normal daily Continue and `Go to Match` hold remain unchanged. Complete save games, decision-blocking events and a separate pre-match match tab are still unimplemented. Details: `docs/PHASE_UI_3_4_1_CALENDAR_PROGRESS.md`.


### UI-3.4.1 hotfix — Club-only simulation feed and in-game confirmation

Calendar fast-forward still simulates **the entire world**; the visible progress list now shows **only managed-club matches**, based on the existing Python `managed` event flag. The percent measures the full world's processed days. Calendar's confirmation is now a styled, keyboard-accessible in-game modal with target date, inclusive days and the count of already scheduled managed matches. The simulation engine, REST job protocol, Continue/day semantics, transactional in-memory session and unsaved DEV limitation were not changed. Pre-match UI remains the next design milestone.

### UI-3.5 — Pre-Match and Post-Match (October 2026)

Implemented: dedicated tab via Go to Match, real two-sided XI/bench, provisional numbered kits, unavailable injury/suspension warnings, cosmetic weather and fictional referee pool, **one-fixture tactical override**, match-only kit colors, FastMatchSimulator quick match, and a large score/statistics/event-timeline screen with a top-right Continue. Team tactics revert after the match. Goals/assists, cards, substitutions and shootout kicks are sourced from real simulation events; no false missed penalties, tackles or injury events. Known limits: immersive match disabled, no in-match injury generation/reporting in FastSim, no persistent saved games, no real referee/manager domain. More at `docs/PHASE_UI_3_5_MATCHDAY.md`.

### UI-3.5.1 — Matchday appearance and bench interactions (October 2026)

Implemented on top of UI-3.5: improved CSS/SVG-based kit preview with multiple color selections and a local visual contrast check; a tactics pitch that permits starter/starter drag swaps and bench/starter drag replacements through the existing match-only API; visible seven-player bench, click-to-select replacement and dropdown fallback; removed the user-facing "decorative DEV data" weather/referee note; aligned match event icon and description in the same team lane. Verified in Chromium using the real local Python API through a browser bridge and in automated regression tests. No FastMatchSimulator, fixture, roster, health or permanent lineup algorithm changes. Known limits still include fictional cosmetics/metadata, no in-match injury generator, non-persistent DEV session and disabled immersive viewing. Documentation: `docs/PHASE_UI_3_5_1_MATCHDAY_REFINEMENT.md`.

### TC-E1 — International calendar foundation

Implemented recurring FIFA club-pause windows and national-tournament release-only reservations, with source labels and future-date projections, in `domain/international_calendar.py`. English future leagues keep their natural/generated fixture round structure before a separate FIFA scheduling pass; displaced fixtures preserve their original date. Generated future worlds and their cup/UEFA-style scheduling respect mandatory club pauses. The portable Calendar shows a subtle globe/tooltip per affected FIFA day, not an extra fixture row. An explicit call-up registry is available but is **not yet connected to national-team fixtures, lineup availability or player fatigue**. Initial 2026/27 seeded dates remain unchanged. See `docs/TECHNICAL_CHECKPOINT_INTERNATIONAL_CALENDAR.md`.
