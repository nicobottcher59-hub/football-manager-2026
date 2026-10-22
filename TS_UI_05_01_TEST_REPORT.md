# TS-UI-05.01 — Staff management and negotiations

## Scope

Incremental patch on TS-UI-04.01. No modification of Squad files or mechanics, Training plan, Medical treatments, player contracts, academy, calendar or match simulation.

### Interface

- Four role-specific Staff panels, active member badges, contract dates, quality, positions and actual wage totals.
- Cinematic generic tactics-room background (`frontend/portable/assets/staff/football-analysis-room.webp`), no baked-in club crest/text; `FMClubIdentity.resolve` supplies the current crest/name and the shell club palette supplies the colors.
- Recruitment subview: eight stable candidates per role, quality/wage sort, name search, salary offer, term, optional signing bonus, counteroffer and accepted offer feedback.
- Active employee **Open negotiations** and **Dismiss**, not instant Extend or Hire.
- Existing Training/Medical panes untouched; Staff link from Medical unchanged.

### Gameplay

- `staff.command` now accepts `action: offer` with exact fields `member_id`, `weekly_wage_gbp`, `years`, `signing_bonus_gbp`; validates bounds and staff capacity and ensures enough cash.
- For hires, signed staff join the same `ClubSupport.members` used by training/medical/scouting calculations; for renewals, contract term extends and salary is renegotiated.
- Deterministic response based on staff expectations, term and signing bonus: underbids are rejected and receive a minimum counteroffer. Rejected offers do not mutate the career. No claim of probabilistic negotiations or unsupported specialties.
- Accepted salaries are charged by the existing real monthly finance routine; signing bonuses immediately reduce club cash and liquid transfer budget. Current and projected wage figures use live Staff read model.
- Dismissal retains the old two-week salary settlement and affects the staff headcount.
- Original direct `hire` and `renew` actions now reject, avoiding bypass of negotiation.
- Saved contracts use the existing v24 StaffMember fields. No schema increment or save migration.

## Verification actually performed

- **9/9** focused tests passed: `tests/test_ts_ui_05_01_staff_negotiations.py` (stable candidate market, rejected underbid and counter, accepted hire and finances, save graph roundtrip, renewal, validations, monthly wages, cross-screen staff changes, application command dispatch, asset/identity contract).
- **5/5** selected historic and cross-screen tests passed in separate runs: hiring/release/capacity, scouting staff capacity and reassignment, Medical/Training staff counts.
- JavaScript syntax checks: `node --check` on edited `club_support.js` and `portable.js`. Python `compileall` passed.
- Chromium visual checks using the actual Staff HTML generator, production Staff CSS/JS and Python read-model data with a deterministic transport stub: overview, recruit, rejected offer, counter acceptance, extension view. No JS page errors.
- Desktop widths 1680,1366,980,560: panel fits available width; at mocked 390px desktop sidebar, *mock full page* overflows horizontally by 43px, but Staff panel itself has no horizontal overflow. This isolated harness does not reproduce the application's adaptive sidebar.
- The production server `http://127.0.0.1` is browser-blocked in this environment, so **no claim of full end-to-end game-browser validation**. The real Python application dispatch was exercised via test, and browser rendering was exercised with mocked transport.
- The full global regression suite was **not completed**: a combined test run exceeded the execution window. This is not claimed to pass. Validation against the user's actual Windows career remains pending.

## Installation

Stop the Python UI and back up the current save. Extract the ZIP at the repository root onto TS-UI-04.01 preserving paths, then restart Python and force-refresh the browser (`Ctrl+F5`). Saved careers remain version 24.
