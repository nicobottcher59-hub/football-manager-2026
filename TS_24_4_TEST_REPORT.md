# TS-24.4 — Player Consent, Agents & Completed Transfers

## What changed

- A provisional interclub agreement now leads to **personal terms**: weekly wage, years, squad role and optional signing-on bonus. Agent demands depend on wage expectations, the player's current pay, role prospects and club division.
- Players may decline a major sporting downgrade even if offered much more money. Ambition and loyalty affect sporting eligibility; unreasonable offers can provoke agent counters or terminate talks.
- Acceptance **completes a real transfer**: moves the same player object between clubs, closes the existing contract, signs a new professional contract, debits the buyer's cash/transfer budget, credits the seller and reconciles previously owed wages. The purchasing club must have both the fee and sufficient wage headroom.
- The existing application command operates on a **deep-copied session**, publishing a transaction only if all checks pass. This prevents partial cash/ownership changes on failure.
- Managed first XI, substitutes and dressing-room memberships are repaired when a player leaves; medical followups and club ownership also follow the transferred player.
- In the Scouting negotiation view, the personal agreement is integrated in the existing full-page flow, including counteroffers, refusals and completed transfer status. For incoming AI bids to the manager, a player/AI buyer consent resolution action is available.
- Existing conditional bonuses are now **obligations** that pay out on actual appearances, goals, assists or promotion, once per achievement, rather than treating the maximum headline as guaranteed cash. A subsequent resale settles the original club's future-sale share on **gross or actual profit**. Unpaid hypothetical bonuses are not counted as past acquisition costs.
- Completed transfer history remains readable after a player's second sale.

## Persistence and compatibility

- Full manager-save graph and SQLite career section versions: **15**.
- Compatible v14 saves migrate the additional personal offer/status, history and settlement fields while keeping their original transfer offers and players.
- No automatic overwriting on load. Back up the SQLite career before saving in the new version.
- The original TS-24.1 and TS-24.2 price and salary scales remain in effect. Agreed club prices still use risk-adjusted conditional values, not headline maxima.

## Verification in this environment

- The **13 new targeted test cases** passed in directed groups: real purchase/sale, contracts/wages, transfer budgets, agent counter, prestige refusal, rollback on errors, lineup repair, bonus settlement/idempotence, repeated-resale gross/profit sell-on, full graph v14 migration, SQLite completed-transfer roundtrip, HTTP endpoint and presentation contract checks.
- Existing tests passed in directed groups: **21 TS-24.3 cases**, **8 additional TS-24.3/TS-24.3.1 cases**, and **TS-24.1/TS-24.2 valuation-finance tests** (old persistence assertions were updated to version 15 and failing legacy fixture cases were rerun after correction).
- Python source was compiled and browser JavaScript passed a syntax check in the build environment.
- A standalone Chromium render using real frontend source and mocked game API data showed the agent form and stored conversation; no JS errors were recorded. **The native live localhost browser URL was blocked by an environment policy**, so this is not a full end-to-end browser or Windows test.
- A clean application of the incremental ZIP and verification/checks is documented at build time.

## Deliberate limits

- The full AI-to-AI transfer economy, competing bids at transfer windows and transfer window restrictions await TS-24.5.
- Loan deals, free agents and buyback **exercise** await subsequent versions. A buyback option agreed in a deal is retained in its record but cannot yet be exercised.
- Contract dialogue uses deterministic economic and personality/ambition criteria, not a complete agent relationship system.
- The full historical multi-season regression suite was not completed in a single uninterrupted run. This release should be further tested on Windows against a backup career.
