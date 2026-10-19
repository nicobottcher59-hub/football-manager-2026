# TS-24.2 - Professional contracts and club finance

## Delivered scope

A persistent, fictional 92-club financial subsystem connected to the TS-24.1 player valuation world. Each of 2,024 senior professionals gets a fixed weekly contracted salary, term and role; every U17/U21 registered youngster has a modest academy agreement (5,336 contracts initially in total). All clubs share the same salary formula, payroll calculation, financial account model and renewal constraints. Salaries are paid from operating cash at each monthly development review, not recalculated by changing OVR, fatigue or ACT.

The new **Finances** screen displays actual simulated cash, transfer allocation (not spendable until player trading arrives), weekly wage budget, committed salary, expected monthly inflows/outflows, and monthly recorded statements. A manager can offer salary and years through the new `/api/finances` transactional endpoint. The same numeric quote model serves AI renewal decisions; each AI club still has its own constraints. The squad/player profile and rival club roster show the registered contract.

A U17/U21 promotion to the professional squad converts the youth agreement to a new pro contract, keeping the player's identity. Youth scouting staff wages are still funded from TS-23.1's separate youth recruitment allocation; they are NOT deducted a second time from this club payroll.

## Opening world salary calibration

Suggested weekly GBP anchors: OVR 50 £550, 60 £1,600, 65 £4,000, 70 £8,500, 75 £26,000, 80 £65,000, 85 £132,000, 90 £270,000, 95 £410,000. Anchors are reference demands; each signed salary varies with role, age, youth status, when it was signed and deterministic club/player context. Contracts do not change automatically after an OVR improvement.

Observed fictional opening **median wage-budget ceilings** for the initial clubs:

| Division | Clubs | Weekly median budget |
|---|---:|---:|
| Premier League | 20 | ~£746K |
| Championship | 24 | ~£150K |
| League One | 24 | ~£35K |
| League Two | 24 | ~£16K |

Budgets are calibrated to the saved fictional squads and adjusted by club-specific stature within each division. They are not claims of real current English club wage bills. Independent cash/transfer allocations, real saved salaries and ledger histories are implemented. Recurring revenue and other expenses are intentionally synthetic until match-day accounting and contracts are expanded.

## Contract handling

- Signed terms include stable player and club IDs, signed date, expiration, weekly salary, role, deal type and historical salary periods for accurate in-month proration.
- User renewal decisions accept a weekly offer in pounds and a 1-5-year term subject to age restrictions and a 90-day renegotiation cooldown.
- A salary below the player's expected figure is refused. An increase exceeding the available weekly wage ceiling is refused, as is a change to another club's player.
- AI teams use the same financial and salary quote rules. Unaffordable extensions are declined. Expired players stay on an explicitly labeled paid interim agreement until a genuine free-agent system exists; no silently free players.
- Monthly rollups debit and credit cash, are idempotent, and roll back transactionally on failed world updates.
- Loading older compatible full SQLite careers initializes the ledger only from the load date; no historical wages are charged for unregistered periods.
- Full graph and manager state version **13**. No attribute, CA, PA, injury or match engine changes.

## Verified

- 29 unit/functional TS-24.2 assertions passed together, covering salary anchors, role/payroll arithmetic, all clubs, renewals, invalid offers, monthly reviews, rollback, AI renewal fairness, academy promotion, read-only GET, old v12 migration and front-end route contracts.
- Two additional TS-24.2 integration tests passed together: actual SQLite roundtrip after a renewal, and actual local HTTP GET/POST/GET `/api/finances` renewal flow.
- Five focused historic TS-23/23.1 academy/scout movement/poaching tests passed together on this code.
- TS-24.1 valuation tests were previously run successfully before final TS-24.2 additions; historical battery has not been exhaustively completed as a whole in this release. Some graph/long save suites hit execution time limits. Do NOT assume full historical repository suite passed.
- `tools/audit_ts242_economy.py` produced the quoted medians and verified every club opened within its wage ceiling.
- Isolated Chromium UI render displayed four finance KPIs, all 22 example professional contracts and filter behavior with no JavaScript errors. Full browser navigation to the local HTTP server is blocked by the execution environment (`ERR_BLOCKED_BY_ADMINISTRATOR`), so this is NOT an end-to-end Windows UI run.
- Native Windows testing and a 20-year financial AI balance test have NOT been done.

## Known boundaries

A high wage expectation is not yet a full player-agent conversation. Completing a contract renewal is the manager agreeing to the displayed minimum weekly demand subject to board affordability, not an exhaustive negotiation simulator. A club's budget for transfers is **reserved**, not yet actionable. Future TS-24.3 and 24.4 will add genuine inter-club bids, player consent and agent negotiations. Users may need to tune wage ceilings with directorial decisions in a later expansion.
