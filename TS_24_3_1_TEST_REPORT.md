# TS-24.3.1 - Scouting and dedicated negotiations

## Scope

Replaces the crowded TS-24.3 Transfers page with a Scouting recruitment hub and a separate full-width club negotiation route. Club-profile player details now offer a functional Make transfer offer action. Offers received, negotiation history and counteroffer replies are accessible from Scouting.

The form starts with ONLY the guaranteed upfront fee. Optional performance bonuses, sell-on percentages and buyback options are added explicitly; absent or removed clauses do not participate in validation. This addresses the native browser error about a 10,000 GBP minimum for a bonus selected as "No bonus".

Existing TS-24.3 economics, dates, budgets, fixed payment policies and pending-player-consent semantics remain unchanged. The backend read model now exposes an events-derived chronological history with the author club, date, note and agreed/proposed terms. No hidden acceptance thresholds or PA information is exposed.

## Market-price display audit

The market was individually valued. The old UI sorted players by their closeness to 38% of the user's available transfer budget, creating a long sequence of values near GBP 4.4M. A fresh TS-24.3 development career contained **2,002 potential rival professionals and 286 distinct quote amounts**. These prices came from separate player market quotes; the repeated display was primarily caused by the sorting policy. The new list prioritizes players affordable with the current budget, then orders by GRL, with age/position/GRL filters and a name/club search. No valuation formula or quotes are changed.

## Compatibility and security

- Full save graph: **version 14 unchanged**.
- Existing TS-24.3 deals and events are read directly; no synthetic conversation history or save migration.
- The HTTP endpoint remains `/api/transfers`; removing a navigation item does not change server routes.
- Transfer target is still validated by the Python domain on submission. Incomplete personal terms still prevent player movement and payment.
- Legacy `#page/Transfers` routes map to Scouting.

## Validation executed

- Six new tests passed: quote diversity, persisted conversation events, navigation and removal of sidebar Transfers, player-profile entry point, clauses-off-by-default contract, and unchanged valuation/save schema.
- All **23 TS-24.3 historical negotiation tests passed** in a full module run, covering conditional valuations, offers/counteroffers, HTTP GET/POST, migration and full SQLite negotiation persistence. This does not imply that the entire repository test suite passed.
- JavaScript syntax was checked successfully with Node in the development environment. **Node is not required on Windows to install or run the game.**
- A JavaScript VM smoke test passed: Scouting search, direct negotiation route, empty bonuses, Back navigation, historical counteroffers and counter form rendering. The smoke uses simulated DOM/model data and does not replace a real browser test.
- A Chromium browser was attempted but local navigation was blocked by the environment's administrative URL policy (`ERR_BLOCKED_BY_ADMINISTRATOR`). **No full browser click-through or native Windows visual test is claimed for this patch.**

## Deliberate limitations

- Personal player contracts, agent requests, completed player transfers and settlement of deferred clauses remain for TS-24.4 and later.
- Professional scout assignment and scouting reports are not yet implemented. Scouting in this patch is the recruitment search and negotiation hub, not an observation engine.
- The immersive screen is a dedicated in-game route in the same tab, not a browser tab or a separate application.
