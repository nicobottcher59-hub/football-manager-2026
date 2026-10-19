# TS-23.1 - Youth Academy polish, scouting contracts and poaching

## Scope

Redesigned U15 preview pitch, bench, pathway; U17/U21 roster tables, real youth results/standings, filtering and authorized actions; scouting manager with paid hires and genuine decisions for discovered prospects. No external fonts or new JavaScript build system.

New careers have 0/3 hired scouts. Offers are deterministic per saved season and club. Initial youth recruitment allocation is £500,000, independent of the placeholder finances UI. Hiring costs a signing fee, active employees are charged wages on monthly review, contracts expire, and funds never go negative. Annual youth allocations are provisional, tier-dependent. Older saves keep existing TS-23 scouts at legacy zero costs, with no retroactive charges.

Prospects can be signed to U17, followed for improved assessment at later reports, dismissed, or signed by an AI club after sufficient time. Poaching creates the actual player in the rival academy with the *same ID and birth date*, removes him from your recruiting pool, and records the loss. Risk is stochastic and deterministic for the same saved state and calendar, not a guaranteed steal.

The estimated potential band is a noisy scout assessment. It is NOT exact PA and neither endpoint is copied from saved PA. The U15 view remains non-playable, and U17/U21 matches still simulate automatically.

## Save and compatibility

Full career graph/section version: **11**. Version 10 migrates the added finance and scout fields using explicit defaults; the historic TS-23 employees are grandfathered without wages. SQLite saves preserve scout contracts, remaining allocation, watched candidates, poaching history and academy memberships. No automatic overwriting on load. Earlier compatible save migrations remain available.

## Verified here

- Seven new Python tests (`tests/test_ts_23_1_academy_polish.py`) passed: zero hires and stable offers, paid hire/limit/termination, monthly idempotence and insufficient funds, rival poaching with actual persistent player and transaction rollback, v10 graph migration, and frontend asset contracts.
- Existing TS-23 focused Python tests passed individually or in targeted subgroups for club youth creation, fixtures, scouting missions, youth movement, migration, SQLite round-trip, and HTTP POST/GET behavior. The combined long-running historical suite was not finished and is NOT reported as passed.
- Chromium browser smoke checks of all four tabs, hire market dialog, and hired-scout display ran successfully with Python-provided read models. No page JavaScript errors were reported; the browser smoke is not a native Windows run or full in-game end-to-end UI test.
- JavaScript syntax validated in this build environment. The user does NOT require Node/npm to run or test the package.

## Limitations

- Scouting money is a self-contained youth allocation and is not deducted from real club finances because that finance subsystem does not yet exist.
- Youth transfers have simplified cross-border eligibility; detailed legal transfers/academy contracts are future work.
- Unrelated scouting and first-team interfaces remain unchanged. No visual redesign outside Youth Academy.
- 20-season global balance with these recruitment effects, and a native Windows browser test, have not yet been verified.
