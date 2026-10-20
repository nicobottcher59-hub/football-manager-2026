# TS-UI-02.3 — Validation report

## Passing results

1. JavaScript syntax (`squad.js`, `squad_ui02.js`) and JSON validation (club identities).
2. **29 focused pytest tests** across the TS-UI-02.3 structural contracts, existing TS-UI-02.2 split-view tests, legacy contract tests and four Python roster-model tests. Server-hosted asset test intentionally excluded from this selection (local HTTP restrictions in the environment).
3. Isolated Chromium screenshots/checks: **1680, 1366, 980 px** — player cards, split layout, four tabs, stats overall vs competition, change of transfer status, development and attribute chart hydration, independent scrolling, no JS errors and no horizontal document overflow.
4. Framed Chromium checks: **1680 and 1366 px** — clicking name selects the player without opening history; clicking separate icon posts `fm-open-history` without changing selection; keyboard Enter selection; late club identity updates hero logo and generic shirt without resetting the inspector; all four tabs and server-backed mutation mocks. No JavaScript errors.
5. Reduced-motion checks: `prefers-reduced-motion` prevents hero ambient animation. Alternate-club theme test switches to blue from a different ID and retains the generic shirt without hard-coded club colors.
6. Separate physical pointer tests in Chromium confirm the **actual mouse click** selects on player name and the arrow is a separate target, not merely a programmatic event.

## Explicit limits

- Browser tests use an isolated fake Python roster response to validate UI wiring; generated demo player names are not added to the actual game world.
- Tests do not claim verification of the user's local Windows launcher or a full end-to-end season save.
- Native Windows validation and the long-horizon 20-season regression remain pending.
- Existing club images are referenced from the existing identity catalog; no new real player pictures are supplied.
