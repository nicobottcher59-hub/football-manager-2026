# TS-24.3 — Inter-club transfer negotiation foundation

## Contract of behavior

This release implements **club-to-club negotiations only**, continuing the explicit TS-24 roadmap. The same `assess_terms` and seller-price policy apply whether a human or AI club initiates an offer. There is **no favorable manager-side buying or selling multiplier**.

The offer carries a guaranteed fixed amount payable **in full at settlement** (never in installments), plus an optional maximum of three separate achievement-trigger bonuses; a future-sale percentage based on **gross resale OR resale profit**; and/or a seller **buyback right** with fixed exercise price and expiry. These are stored as immutable, validated dataclasses on the saved FootballWorld registry.

AI pricing computes a **risk-adjusted economic value**, not the theoretical headline total. Appearance, goals, assists and promotion triggers have different probabilities conditioned on sporting role/position, quality and buying division. Probable extras are further risk-discounted, and non-cash clauses cannot replace an implausibly low guaranteed payment. An unreasonable bid is rejected; sensible bids may be countered. Repeated lowball proposals can close talks. Contracts, squad importance and competitive rivalry affect seller reservation pricing; buyer affordability and value affect counteroffer acceptance. The same finance account provides a spending cap to both sides.

**Provisional agreements do not buy footballers.** This release does not simulate an agent agreeing to personal terms, register players, debit cash, activate bonuses, or exercise rescission/buyback. After both clubs accept terms, the guaranteed fee is earmarked against available transfer budget until the 45-day expiration or until future transfer completion support exists. No money changes hands and player/contract IDs do not move in this release. User can reject/counter incoming offers; AI clubs may submit incoming bids during quarterly market interest reviews. Club-to-club talks are not yet an all-league AI trading engine (planned for TS-24.5).

## Data integrity and compatibility

- Current full manager-state version **14**, migrated explicitly from prior saved versions including v13. No historical fees or offers are invented for migrated careers.
- Prior TS-24.1 price snapshots, TS-24.2 signed wages, budgets and SQLite support are preserved. Finances now differentiates board transfer allocation from amount available after club agreements.
- All read-model GET operations are mutation-free; backend POST requests operate on cloned sessions and commit only on complete validation. Monthly interest/expiry processing participates in the world journal and can roll back.
- Interface uses vanilla JavaScript and CSS integrated into the existing dark navigation; no npm/Node runtime required.

## Verified in this build

- **23 new TS-24.3 tests passed together**, including realistic/implausible variable pricing, gross vs profit sell-ons, buyback validation, budget and auth restrictions, static wiring, v13 graph migration, world journal rollback, full SQLite round-trip, and real HTTP GET/POST/GET transfer endpoints.
- **29 TS-24.2 focused economic regression tests passed** (excluding two separately run integration cases).
- **40 TS-24.1 focused valuation regression tests passed** (excluding the four heavy full-world/monthly/save cases).
- TS-24.2 SQLite round-trip and local HTTP contract flow were each run separately and passed.
- JavaScript syntax passed for the new and routing scripts (`node --check` used in development only).
- Headless Chromium verified target search, positional filters, clause form, risk preview, tab switching, basic responsiveness and no page JavaScript errors; visual browser check is isolated, not a native Windows client run.
- A separate economic audit sampled ~2,000 rival first-team contracts and found a median seller-asking/market-value ratio of about **1.16** in the initial fictional world (not a general sporting market constant).

## Boundaries / future work

- **TS-24.4:** Player-agent contract negotiation, player preferences, club consent, transfer settlement and registration.
- **TS-24.5:** Active AI-AI trading, realistic windows, multiple bidders and player competition.
- **TS-24.6:** Actual contingent-clause payouts, buyback/sell-on execution and loans.
- Youth player international transfers, external-league markets, free agents and installment payments are not enabled. `transfer_offers` currently references registered first-team professionals.
- Not a complete historic regression run, a 20-season AI market balance validation, or a native Windows check.
