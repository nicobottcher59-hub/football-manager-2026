# TS-FIX-06 - Market discipline and structured loan negotiations

## Release baseline

- Source installation: original `football-manager-2026.zip`, followed by TS-FIX-01, TS-FIX-02, TS-UI-08.04, TS-FIX-03, TS-FIX-04 and TS-FIX-05.
- Installation target: the existing TS-FIX-05 installation (which already contains TS-UI-08.04).
- Incremental delivery: **16 application/test files** (11 modified, 5 added). The ZIP also contains this report, installation instructions, and SHA-256 checksums.
- Graph persistence version: **29 -> 30**. Earlier saves are migratable; saves written by this version are not readable by previous builds.
- No new third-party runtime dependencies.

## A. AI offers to the managed club

Two separate bid generation paths existed: a weekly incoming-interest service and a monthly AI transfer market. Previously the weekly path could create up to two bids per review and keep up to five active offers. Both paths now honor shared window-volume limits and recent activity.

- At most one new manager bid per market review, three per winter/summer transfer window, and one unsolicited (unlisted) bid per window.
- A separate 14-day global quiet period applies to weekly incoming offers; a 120-day buyer/player repeat-bid cooldown applies across individual target evaluations.
- Explicitly transfer-listed players are favored by interested, budget-capable buyers. Players marked untouchable are excluded from new managed-club bids. Other players may still attract rare offers if there is a credible position/quality gain.
- No player is sold or transferred merely because an AI bid is generated. An incoming bid remains a manager decision, and unattended Calendar simulation does not accept it.
- The patch does not retroactively erase already received offers from an existing save.

## B. Loan negotiation model

New persisted `LoanTerms`, `LoanRound`, and `LoanTalk` implement multiple rounds of club-to-club bargaining:

- Duration: six, twelve or twenty-four months.
- Borrower's weekly salary share: 0-100%, as a percentage of the parent's current professional contract.
- Credible playing-time commitment: starter, rotation or backup. The AI compares the player's position and ability with the receiving squad rather than promising unrealistic guaranteed starts.
- Optional parent-club recall right (after a minimum of 30 days).
- Optional **full permanent purchase package**, reusing the existing transfer terms model: cash upfront, 2/4/6 installments at 6/12/18-month intervals, up to three performance bonuses, percentage on a future sale, and seller buyback clauses.
- AI counterpart evaluates salary coverage, feasibility of playing-time promises, duration, recall, and the expected economic value of an option to buy. Replies can counter more than one dimension at once.
- Each discussion stores sender, terms, explanation, date, and remaining patience. Ended conversations cannot be restarted immediately (14 days after walking away, 60 after an exhausted negotiation).
- Unknown outside-player OVR and weekly wage are not disclosed in the loan search UI.

## C. Execution and accounting

- Loan proposals can be agreed outside a registration window. The player remains with the parent and the borrowing club owes no loan wages until a valid window activates the loan.
- At activation, the original professional contract stays with the parent. The receiving club registers the same Player object, while existing payroll accounting allocates the salary cost between both clubs.
- Only the borrowing manager can activate a purchased option from the loan interface; the chosen full purchase package is immutable after agreement. Any registration-window delay postpones the transfer and the upfront fee.
- A deferred option exercise is recorded as a pending transfer agreement. The loan registration is returned to the parent at expiry/window before the permanent transfer settles. Cash, permanent contract and installments settle only on actual registration.
- The transfer pipeline validates upfront cash and deferred credit separately; an authorized financed total no longer fails simply because the guaranteed total exceeds the immediate budget.
- Purchase-activated installments retain their normal dated, one-time financial ledger.

## D. UI

- New loan discussion builder inside Transfers > Loans (the full Transfers Hub remains TS-UI-09).
- Player and both club identities use existing scalable asset resolvers with safe placeholders.
- Two-column negotiation layout, counterpart terms and discussion history, patience indicator and inline feedback.
- Installment count and payment frequency are separate **three-position sliders**, consistent with the prior approved transfer negotiation pattern.
- Loan/option/recall and legacy free-agent actions use in-page confirmation instead of browser-native `confirm` dialogues.
- All amounts use GBP currency symbols and separators.

## E. Verification

- **13 new Python tests passed** in separately bounded runs: club response and counterterms, salary-share settlement, realistic playing time, discussion persistence and cooldown, agreement out of window, future purchase terms, graph 29->30 migration, unknown data, deferred option settlement with no duplicated registration or immediate fee, deferred-financing option, and monthly/weekly offer-volume safety.
- Syntax compilation for the changed Python modules and `node --check` on the changed JavaScript modules passed.
- Chromium standalone UI smoke test passed for the actual loan-form code, purchase option toggle, amount parsing, 2/4/6 installment count, 6/12/18-month frequencies, and hiding unknown OVR. No JavaScript exceptions. Tested 1440px desktop and 390px mobile (0px horizontal overflow).
- Existing TS-FIX-05 tactical tests produced ten assertion passes and one outdated graph-version-29 expectation under graph version 30. An earlier TS-24.6 legacy test expects graph version 17. These version assertions are not failures of new loan logic; the entire historical battery was not certified in this release.
- The 13 new tests were run in groups because an all-at-once invocation exceeded the execution limit after its first twelve successful cases. Individual final cases passed in separate processes.
- Reconstructed-base ZIP application is verified using SHA-256 comparison of every changed/new application file. No untouched file is included for replacement.

## F. Known limits / follow-up

- Do not interpret isolated DOM smoke tests as a full live browser walkthrough or a complete season simulation. Those remain for the user's local game.
- In this release, the user can activate purchase options when managing the **borrowing** club. Automated activation by an AI borrowing club on an outgoing manager loan is not implemented here; such options are negotiated and recorded but AI exercise behavior should be considered a separate enhancement.
- Existing nonloan free-agent workflows retain older mechanics. Full Transfers Hub organization is deliberately reserved for TS-UI-09.
- The national window calendar still uses English fallback rules for countries without defined local transfer windows.

## Suggested manual validation

1. Back up the career and apply TS-FIX-06 over TS-FIX-05.
2. In Transfers > Loans, negotiate both an inbound and an outbound loan. Observe salary, squad fit, duration and recall counteroffers.
3. Add a buy option with cash plus four installments every twelve months, and a conditional bonus. Check the right-side conversation summary.
4. Reopen the discussion and reload the save; verify patience and terms are unchanged.
5. Negotiate in October and advance unattended to January. Verify registration only when the window opens.
6. Activate a purchase option while a window is closed; inspect the pending status and check that cash changes only on registration.
7. Advance across several transfer-market reviews; compare unsolicited offers and make sure no players transfer without an approved decision.
