# TS-24.6 — Loans, free agents and buyback exercise

## Implemented

- Temporary player registrations for **6, 12 and 24 months**, preserving the underlying player identity and lender's professional contract. The borrower is the club for match selection until the loan ends.
- Agreed **borrower wage share (0–100%)**, enforced wage budget, prorated actual loan days, one-time monthly settlement and rollback-safe world transactions. No installment transfer payments.
- **Playing-time expectations** (`starter`, `rotation`, `backup`) validated for credible squad opportunities, with actual/indicative target minutes visible in Scouting; no automatic breach sanctions in this release.
- Optional purchase price. Buying converts the existing loan registration into a permanent, player-consented transfer with a new contract and the full agreed fee, and is restricted to the final 90 days and a transfer window. Unreasonable options demanded of AI lenders are rejected.
- Loan recalls from 30 days by the managing parent club; automatic returns at monthly review after the expiry date, including multi-season 24-month agreements. Squad and lineup repair included.
- Professional contracts may expire and suitable players enter a persistent **free-agent registry**. Signing is governed by player interest, wage demands, wage budget and roster size. AI clubs can sign free players to cover tactical gaps.
- Exercise previous TS-24.3 contractual buyback options within their validity period, with consent, full payment and a new permanent contract.
- Persist loans, free agents and salary obligations in graph and complete SQLite manager career saves. **Version 16** with explicit legacy migration from v15.
- `Scouting > Loans & free agents` provides the loan list, outgoing/incoming shortlists, free agents, buyback rights and optional purchase clause editor. No additional Transfers sidebar is introduced.

## Tested

- Sixteen TS-24.6 focused test cases (including parameterized 6/12/24-month loans) passed in isolated groups: loan validity, budget and role safeguards, payroll proration/rollback, recall, purchase option, free-agent signings, v15 migration, automatic loan returns at 6/24 months, buybacks, full graph/SQLite roundtrip and real HTTP GET/POST `/api/loans`.
- TS-24.5 autonomous market's **8 tests passed** after the changes; version-sensitive historical assertions updated without changing legacy graph fixtures.
- A manual domain simulation of seven month-ends returned a six-month loan in March; a separate 24-month financial simulation returned the player after two years while preserving the same player and parental contract. Both were validated for no repeat return.
- JavaScript `node --check frontend/portable/transfers.js` passed in the build environment. **End users do not need Node/npm**.
- Python source compilation passed. A new-career read-model check showed a live shortlist of loan candidates, zero loans/unsigned players initially and valid Finances data.
- The full historical test suite, native Windows UI interaction, and 5–20 full football seasons were **not** run. Some combined long-running test groups exceed the execution time limit; individual SQLite and HTTP tests passed separately.

## Design limitations / balance monitoring

- AI-to-AI loan negotiations are not yet autonomous; AI clubs may sign appropriate free agents.
- No mandatory purchase obligation. Buybacks are only available where a prior permanent transfer included a valid clause.
- Players on academy U17/U21 lists must be promoted to the senior squad to become eligible for professional loans.
- A promised playing-time role is a monitored expectation, not yet a disciplinary/compensation clause. Manual recall remains available for eligible outgoing loans.
- A club does not automatically lose its last functional XI or second goalkeeper when an expiring contract is released. Where safe release is not possible, interim paid retention remains until a later monthly review.
