# TS-24.1 — Player market valuation foundation

## Scope

A reusable and calibrated value-of-player engine is now integrated into the persistent 92-club world, the U17/U21 academies, and the visible Squad/club profile read models. No playable professional transfer negotiation is enabled in this update.

## Valuation design

- **18 GBP anchor points** for an ordinary outfield footballer of 27 in normal form. Continuous exponential interpolation between anchors prevents OVR threshold cliffs.
- **Youth valuation premium** is sensitive to age and *perceived* development headroom. The market belief uses a deterministic bounded noisy assessment, influenced by saved PA but *never the exact PA*, and is not sent to UI responses. Future scouting can improve this approximation without modifying the existing OVR/ACT equations.
- **Age decline** reduces price as a player approaches retirement. Goalkeepers receive a distinct longevity adjustment. Position-specific demand adjustments are deliberately small (up to 6% above baseline for strikers; full-backs about 3% below baseline).
- **Form** uses the existing smoothed `PlayerState.form`, a component contributing to ACT, with a bounded maximum impact of **±12%**. It explicitly excludes `fitness` and `fatigue`, so a tiring post-match condition is not a sale-price collapse.
- **Medical history** uses previously recorded serious absences and persistent injury burden. Incidental short injuries do not carry an automatic discount. Medical reduction is capped at 32% in normal cases.
- An **extreme price guardrail of £500M** prevents improbable multi-billion valuations for rare combinations of exceptional ability and future headroom.
- **Monthly snapshots**, stored on the world calendar, prevent a quote from being recomputed after every match or every click. Snapshots are stored in the full SQLite manager save; reads have no mutations, and failed monthly steps roll back quotes atomically.
- The system is independent of English tier and user ownership, so the same player is assessed identically whether you are buying or selling.

## Selling-price scenarios

`asking_band(quote, SaleContext(...))` is an available *pure model* for future negotiations. A real transfer engine can provide remaining contract months, importance, urgency, transfer list status, demand from other bidders, buyer rivalry, player's wish to leave and available replacements. It yields a market valuation adjusted for those facts and an indicative low/high asking band. **It does not claim to be a club's actual hidden threshold and does not accept a bid.** Current footballers have no genuine player-contract register, so contract time is unknown and no years are invented in Squad.

## Calibration examples (£ GBP; illustrations are pure-model scenarios)

| Age | OVR | Perceived improvement room | Market estimate |
|---:|---:|---:|---:|
| 16 | 60 | 0 | £690K |
| 16 | 60 | 15 | £3.3M |
| 16 | 60 | 30 | £7.7M |
| 19 | 72 | 0 | £5.7M |
| 19 | 72 | 15 | £20M |
| 19 | 72 | 27 | £38.5M |
| 20 | 75 | 0 | £10M |
| 20 | 75 | 12 | £26.5M |
| 21 | 80 | 12 | £71M |
| 27 | 80 | 0 | £24M |
| 34 | 80 | 0 | £6M |
| 19 | 90 | 7 | £239M |
| 35 | 85 | 0 | £12M (outfield), approx. £22M (GK) |

The samples use ordinary form, no serious injuries and the neutral (1.0) position multiplier. Actual player results differ modestly according to position and form, as expected. `tools/audit_ts241_market.py` reports exact price anchors and the initial 92-club medians from the installed data pack.

## Financial distribution of the initial professional world

| Tier | Initial players | Median market estimate |
|---|---:|---:|
| Premier | 440 | ~£9M |
| Championship | 528 | ~£1.6M |
| League One | 528 | ~£280K |
| League Two | 528 | ~£50K |

Initial U17/U21 academies contain approximately 3,312 additional persisted players with valuations; U15 preview prospects are intentionally excluded. The opening market contains 2,024 professional players and 5,336 market snapshots overall. These are **fictional game-market values**, not the real UK transfer market or measured prices for actual footballers.

## Save and compatibility

Full manager graph and manager-state section version **12**; previous compatible v11 careers load using explicit defaults. Missing market snapshots are bootstrapped only at migration, never by changing PA, OVR or ACT. Quote policy and snapshot month are retained after save/load. Stale quotes for retired/released footballers are reclaimed during subsequent monthly review; player identities and retirement histories remain untouched.

## Validation and limitations

- Focused valuation assertions cover 18 anchor OVR prices, intermediate interpolation, young/prodigy examples, older and goalkeeper values, form/fatigue independence, medical risks, sale-context symmetry, invalid-input protection, global read-only models, monthly updates, transaction rollback, legacy graph migration and full SQLite round-trip.
- Chromium **isolated, no-network** Squad render checked that market prices and date/asking-price disclaimers appear correctly in the existing table/profile; the full local server/browser navigation was blocked by this environment's policy (`ERR_BLOCKED_BY_ADMINISTRATOR`), so it is **not** counted as a full E2E browser pass.
- Professional contract terms and budgets are not yet registered. Asking price ranges are **scenario logic only**, not an available final negotiation outcome. Agents, transfer windows, buyer interest and binding offers are subsequent TS-24 stages.
- The 20-season footballing/economic balance with an operative buying/selling AI and real-world players is NOT validated at this stage.
- No native Windows run or complete repository test suite is claimed.

## Measured results for this release

- **44 focused TS-24.1 tests passed** on the final calibrated pricing code, including exact anchor prices, varied potential and age examples, symmetric context scenarios, rollback, v11 migration and SQLite round trip.
- **266 historical regression tests passed** in the joint TS-23.1/TS-23/TS-22/TS-21.2/TS-21.3/TS-21.4/21.5 suites on the pre-final price model. One obsolete v6→v12 test assertion initially failed because it omitted the real academy players introduced after v6; it was corrected to assert that all original players remain unchanged, and the complete suite was rerun successfully. Pricing tweaks after the joint run were covered by the final focused 44-case suite, but the entire 266-case suite was **not rerun a third time**.
- `tools/audit_ts241_market.py` executed successfully with the reference prices, all four English division medians and 5,336 professional/youth quotes.
- Isolated Chromium Squad rendering showed 22 market value entries and the individual-player asking-price caveat without page JS errors. Full server browser navigation remained blocked by this environment, and Windows-native testing was not done.
