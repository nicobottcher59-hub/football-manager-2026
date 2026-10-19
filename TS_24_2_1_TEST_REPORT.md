# TS-24.2.1 — Squad contracts and collapsible player details

## Scope

This is a presentation-only hotfix on top of **TS-24.2**.

- Added a **Contract** column immediately after **Market value** on **Squad > General**. It reads the signed weekly wage and contract expiry from the current Python read model (`contract_details`) and can be sorted by weekly wage. Unavailable data is displayed as unknown; expired contracts are labeled distinctly.
- Converted the small `+` in each player row into an explicit **expand/collapse toggle**, using `+` when closed and `−` when open.
- Added a visible **Close details** button in the expanded profile and separated **Player management** from the expand/collapse action.
- Kept the profile detail cards, attributes, season statistics, and management actions intact.

## Validation

- JavaScript syntax: `node --check` passed in the build environment. Node/npm is **not** needed by the game or by the Windows installer.
- Chromium smoke test with a test read model: column and salary/date rendering, expired and missing contracts, opening/closing via player row and `+`/`−` button, the **Close details** control, management expand/collapse, and numeric sorting all passed.
- Four focused Python source-contract tests were added to keep these behavior contracts explicit.
- Package includes a SHA-256 verifier; no save data is included.

## Compatibility and limitations

- No Python backend, contracts, salaries, finances, or save serialization code changed.
- Save graph version remains **13**, the same as TS-24.2. Existing careers continue working.
- Tests in a Linux Chromium environment are not a native Windows end-to-end run.
