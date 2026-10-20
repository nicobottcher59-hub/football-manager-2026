# TS-UI-02.2 — targeted validation report

## Passed

- JavaScript syntax validation: `squad.js`, `squad_ui02.js`, `presentation.js`.
- Python syntax check: `src/football_manager/ui_shell/models.py`.
- 10 standalone structural tests: new CSS/JS wiring, independent tabs/contract and actions, season scopes, existing operation IDs, club identities, player picture fallback, scroll support, navigation, scheduled competition selection.
- 6 existing Python tests: UI-3 player season statistics and DEV administration (2), historical TS-24.2.1 contract/roster interface tests (4).
- Isolated headless Chromium: viewports **1680, 1366, 980 px**, with synthetic roster fixture and intercepted API responses. Assertions: 25 rows, 4 inspector tabs, original horizontal table removed, responsive placement/no page overflow, portfolio of old placeholder avatars, semantic club theming, season **all** vs selected competition vs **all**, transfer flag mutation payload, development-only and charts-only graphics, JavaScript error count zero.
- Additional browser interaction: selecting a row after list scroll and changing tabs preserves the roster scroll position.

## Not performed

- Live end-to-end run in the user's Windows environment.
- A full 20-season or complete system regression suite.
- Visual inspection of external real-player images (not supplied).

## Scope/safety

No changes to core match simulation, transfer economics, database schema or player ability equations. Read model exposes only the current club's scheduled competitions as selector metadata.
