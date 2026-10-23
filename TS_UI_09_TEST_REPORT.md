# TS-UI-09 — Transfer Centre UX: integration and test report

## Baseline and scope

- Apply this incremental ZIP **directly on TS-FIX-06** (all earlier patches remain installed).
- UI integration only, without changing Python match, negotiation, accounting, or save models.
- Save graph remains **version 30**. No migration is needed.
- Existing permanent-transfer, personal-contract and loan negotiation engines are reused rather than duplicated.

## Implemented interface

1. Dedicated **Transfers** item in sidebar and `#page/Transfers` route. Old bookmarks to Transfers now open the actual Hub instead of redirecting to Scouting.
2. Header includes a **club-neutral football/transfer-document image**, scoped inside the identity/finance card. Club name, crest and theme derive dynamically from the manager club ID and shared asset catalog; no club names are hard-coded.
3. **Received Offers** and **Sent Offers** are the primary equal-width panels. They aggregate transfer discussions and loan talks; all offer types appear by default and the optional offer-type filter selects transfers/loans. Each row has status, date, club identity and an actionable link to the relevant negotiation.
4. The **Shortlist** now lives in Transfers, reads persisted scouting priorities from `/api/scouting/hub`, and offers search/priority filters, remove action and access to negotiation. Unknown OVR or valuation is not fabricated; market value only appears if it was published or genuinely reported.
5. The existing Scouting shortlist tab and its overview module were removed; Scouting retains player search, scout management, report reviews and "Add to shortlist". Its former shortlist panel is replaced by recruitment intelligence using real scout/report/recommendation counts and a link to Transfers.
6. Other widgets: transfer-window status from Python, transfer and wage budgets from Finances, recent **completed** world transfers from the game ledger, and a cross-type negotiation history.
7. A Transfer/Loan selector on the existing permanent negotiation screen switches to the existing TS-FIX-06 loan negotiation builder, and vice versa, without converting any persisted discussion into another deal type. Direct "Start loan negotiation" is provided in the Hub.
8. Responsive styles for desktop, tablet and narrow screens; shell navigation retains your club colours. All club images have dynamic ID-based lookups and explicit visual fallbacks.

## Verification

- 6 **new automated Python tests passed**: routing, shortlist move, mixed offer types/history, generic scalable image identity, linked transfer/loan routes, and authoritative API-model compatibility (real DevelopmentSession). The last test also confirms save graph 30 and verifies scouting player data do not contain raw hidden OVR or market values.
- 7 existing tests passed from `test_ts_ui_08_02_scouting_assets.py` plus `test_ts_ui_08_04_scouting_identity_ranges.py`, in a separate regression invocation.
- 10 checks passed in a combined smoke/regression invocation of the new tests plus 08.02 assets tests.
- `node --check` passed for every changed/new JS module.
- Chromium frontend tests used **the actual shipped JS/HTML/CSS**, supplied with controlled data shaped from live Python read-model responses because local browser navigation is restricted by the test environment. Assertions exercised navigation, source-of-truth shortlist link, transfer/loan filtering, a shortlist player opening transfer talks and switching to an editable loan discussion, and the independent Loan entry point. No JavaScript page errors were observed.
- Layout inspected at **1672px, 1024px and 390px**; page overflow was **0px** at all three sizes. Visual captures are provided separately for desktop, mobile and loan negotiation.
- ZIP installed over an isolated copy of the actual TS-FIX-06 base and every packaged file matched the source SHA-256. No original unaffected file is in the incremental archive.

## Limits / follow-up

- The browser visual run used controlled sample offers and player priorities on top of real API response shapes; these are **not** supplied as in-game data and no save files are changed.
- Browser navigation to the actual local HTTP server was blocked by this environment; therefore **a complete native live-server browser run on the user's Windows installation has not been certified**. The Python APIs were queried separately from the real development server and the UI was tested with actual loaded JS in a controlled DOM.
- A full-season simulation was not repeated, as this patch only changes presentation/navigation. Previous loan engine and financial tests from TS-FIX-06 were not rerun as a full historical suite.
- Real crests and portraits appear only when provided by the ID-based asset catalog; placeholders are deliberate and will resolve automatically when future BD assets arrive.
- TS-FIX-07 remains responsible for News/Inbox routing of match results and completed transfers.
