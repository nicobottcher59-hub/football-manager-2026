# TS-FIX-03 - Contract negotiation / agent AI / renewals

## Baseline and delivery

- Applied incrementally over TS-UI-08.04, with TS-FIX-01 and TS-FIX-02 already present.
- Changed/new project files: **22** (14 modified, 8 new), excluding patch documentation.
- Persistent save graph upgraded **27 to 28** with migration defaults for existing talks, incentive ledgers and transfer-agent patience.
- No save files and no new third-party runtime dependencies.

## Implemented functionality

1. **Shared contract negotiation experience**: player-agent editor for transfer signings and renewals; club-colored visual shell and crest/photo resolution via existing identity/fallback components. Finances retains its existing table; `Open Negotiation` opens the dedicated screen.
2. **Wages begin at GBP 0** in the proposal editor; no pre-populated acceptance threshold. The player/agent wage expectation shown is an indicative discussion interval, not the actual server-side wage floor. All visible currency inputs/amounts use GBP symbols and grouping.
3. **Agent choices** consider guaranteed weekly wage, duration, role, player age, personality, signing-on fees, attainable bonuses and remaining patience. Counters can vary wages, signing bonus, duration, role and bonus composition; insufficient bids lower patience and can end the current talks. The server does not expose the private agent acceptance computation.
4. **Renewal negotiations** use the same bargaining and personal terms as transfer signings. A ended renewal can be reopened after a 45-day cooling-off period; a signed renewal can be reopened after 90 days. Read-only page refreshes do not alter persistence or restore lost patience.
5. **Economic consequences**: new wage commitments, once-only signing-on fees and recorded performance triggers. Supported incentive triggers: appearances, goals, assists, clean sheets for GK/defenders, and promotion. Triggers come from verified career usage / detailed match statistics and are paid no more than once per signed deal. Renewals start a fresh milestone baseline.
6. **Squad-role commitments** are registered in the established inbox/promise review pathway; the app does not silently guarantee that a player will start every fixture.
7. **Career saves** preserve agent discussion histories, counteroffers, patience and bonus payment ledgers. Older v27 careers gain safe empty defaults on loading.
8. Legacy direct renewal UI forms and native confirm dialogs have been replaced within the Finances renewal flow; the broader interface redesign of Finances remains a separate UI stage.

## Verification actually performed

- **14 new contract tests passed in two targeted runs** (13 tests excluding the heavy purchase/save integration, plus the purchase/save integration separately). These include zero offers, patience decay, agent counteroffers, closed/reopened talks, budget and signing fees, bonus settlements (including GK/defender clean sheets), persistence and v27 migration.
- **Purchase end-to-end** reproduced independently in ~13 seconds with an actual transfer, agent counteroffer and acceptance, registered signing, bonus ledger, and a 199,046-node graph roundtrip (saved state reconstruction and contract validation).
- **10 selected previous-patch regression tests passed** from TS-FIX-02, TS-UI-08.04 and TS-UI-08.03 (market estimates, negotiating installments and club identity components).
- Python `compileall` on affected package code and JavaScript `node --check` for updated scripts passed.
- Isolated UI browser render checked at 1366, 1024 and 390 px: no horizontal overflow or script errors in that controlled page; the preview used mock player data.
- Zip file list, hash manifest, installation into a clean copy, and file bytes are verified during packaging and later verification.

## Limitations and outstanding checks

- **No complete browser-to-live-server E2E**: the local browser test returned `ERR_BLOCKED_BY_ADMINISTRATOR` for its `127.0.0.1` target, so the isolated screenshot is not a native gameplay verification.
- **No full regression suite pass is claimed.** The full legacy suite was not completed, and several old tests hard-code obsolete `GRAPH_VERSION` or historical fixed wage acceptance assumptions.
- No direct run on the user's specific career save or a complete new season; continue the saved career only after backing it up.
- Clean-sheet milestones only count match-recorded clean sheets, not guessed statistics from legacy data without detail.
- Contract bonus types are finite, not a fully arbitrary clause editor, and salary offers still have explicit technical and budget validation on signing.

## QA snapshot

`TS_FIX_03_Contract_Negotiation.png` is a controlled visual preview of the new UI, not a photograph of a native session. The preview contains a proposed input value typed during testing; a newly opened editor starts at GBP 0.

## Installation

See `TS_FIX_03_INSTALL.txt`. Apply the zip over the stated baseline with the folder tree preserved. A v28 save can only be rolled back with its pre-patch backup.
