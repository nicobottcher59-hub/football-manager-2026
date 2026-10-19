# TS-19.1 — Verified test report

- Test environment: Linux, Python 3.13, Node.js present.
- Baseline: provided source ZIP (TS-18.4) + reviewed TS-18.5 ZIP + unified TS-18.6 ZIP + TS-19.1 patch.
- **Full regression: 1100 tests passed, zero failures (352.50s).**
- New TS-19.1 tests: **7 passed** (Python catalogue, live UI JSON, full formation selection, 28 match runs, HTTP selection, career graph roundtrip and portable JS pitch for all formations). The Node.js-dependent test runs when Node.js is installed.
- Existing Node board test: `node tests/ui/test_board.cjs` — passed.
- JavaScript syntax check: `node --check frontend/public/squad/squad.js` — passed.
- Manual tests: live web UI is verified via its API and JavaScript computation, **but could not be rendered interactively in this container because the browser execution was blocked by administrator settings**. Real Windows browser acceptance is still required after installation.
- No football match engine, coefficient, state progression or OVR/ACT code was modified in TS-19.1.

Integration test workspace only: previous TS-18.5/TS-18.6 patches were applied so the regression covers the intended installation base; these prior patches are **not duplicated** in TS-19.1 ZIP.

## Coverage limits

The domain currently has no separate RM/LM enum entries. Wide midfield is
represented by RW/LW slots shown deeper on the board, with RM/LM display labels;
that limitation is documented in `docs/TS_19_1_FORMATION_EXPANSION.md`.
The fast simulator is position/profile-driven, so visually different shapes
with the same position-role combination can share some underlying match
contributions. This patch does not invent new tactical coefficients or change
existing formulas to force differences between templates. Additional positional
freedom and tactical expression remain scheduled for TS-19.2 / TS-19.4.
