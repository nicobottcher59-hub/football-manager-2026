# UI-3.4.1 — Calendar day selection, past-day contrast & live results screen

## Approved interaction

- **Every calendar date is selectable**, including a day without any fixture. Clicking anywhere in a day cell or using Enter/Space while the cell is focused selects the target. Dates in the past remain available for inspection but cannot be used to rewind the world.
- Past days are rendered with a darker, desaturated tile. Played-fixture result strokes and W/D/L labels remain readable; today has a bright outline and future dates keep normal contrast.
- `Simulate to this date` opens an in-game confirmation. Once accepted it shows the full-screen simulation screen using genuine Python results. **Only managed-club matches** are listed; other world fixtures still resolve. Competition, home/away, score and penalty shootouts derive from `WorldSeasonRunner`.
- The display has 1x/3x/12x/Instant *presentation* speeds. **These do not change match results or the simulation RNG**. Fast display simply consumes already reported results more quickly.
- When processing succeeds, the overlay remains open with a completion summary until the user clicks `Return to calendar`. At that point Calendar, Home and other panels refresh from the newly committed Python session.
- Normal header Continue remains one day, and stops on a managed match with `Go to Match`. The actual separate match tab is explicitly deferred to the next design increment.

## Engine/API design

No new match simulator and no new fixture scheduler. `simulate_until(session, target, on_day=...)` takes an optional callback. Per-day callbacks describe only fixture results newly registered in the world ledger (not historic results seeded before the starting day). Result dates and pairings come from the canonical scheduled fixtures. The callback is never needed for normal UI-3.4 calls.

`UIRuntime` now supports **one in-flight async simulation job**. Starting a job deep-copies the live DevelopmentSession. The worker processes each day using the same existing methods as UI-3.4 and collects actual result events in order. The HTTP API exposes:

- `POST /api/progression/jobs` with `{"action":"simulate_until","date":"YYYY-MM-DD"}`: start a job, return an opaque job ID. Dates are validated before the job is created.
- `GET /api/progression/jobs/<id>?after=N&limit=100`: status, authoritative world date, days completed, percent, paginated actual result events, completion result or failure reason.

The underlying simulation can complete faster than the visible result-by-result playback. Percent/days show **actual backend progress**, while `YOUR MATCHES SHOWN` counts only rendered managed-club matches, not all background fixtures. No placeholder scores or artificial world dates are generated. The feed retains its last seven managed-club results on-screen; the frontend still paginates through every Python result event, filtering on the canonical `managed` flag without altering the background simulation or backend API.

**Transactionality:** while a job runs, writes to the squad, the old progression command, and new job starts return 409. Reads continue to show the prior committed session. Only after the working copy successfully simulates through the target date is the session pointer swapped; on an exception, the live session is unchanged and the job reports failed. Do not claim on-disk atomic save; this remains an ephemeral DEV session.

## Validations

- `tests/test_ui341_calendar_progress.py`: matching results/IDs against canonical ledger; chronological day callback; paginated HTTP events; managed club FastSim; atomic rollback on injected worker error; simultaneous mutation rejection; invalid dates/job IDs; UI resource checks.
- Old UI-3.4 Continue regression tests still pass, including full season and Go to Match hold.
- Playwright browser inspection through the Python API bridge (required by Chromium loopback restrictions in this environment): clicking an **empty Sep 23 calendar cell**, beginning the job, displaying >300 registered match results, selecting Instant display, completing, and refreshing Home/Calendar to Sep 23. Screenshots checked; no JavaScript exceptions.

## Still not implemented

- Separate pre-match/match tab: user decides its UI next. `Go to Match` remains a safe notice.
- Complete persistent save/load across restarts and season transition through 2027/28.
- A real manager-decision/event queue; the auto-sim can only stop for decisions after that domain system exists.
- Multi-year fast-forward or imported/licensed real clubs and crests.

### Windows

Install the **incremental UI-3.4.1 patch** over UI-3.4 in a new branch, preserving repository-relative paths. Close the old Python server with Ctrl+C, restart via `INICIAR_INTERFAZ_WINDOWS.bat`, and refresh Chrome using Ctrl+Shift+R. No Node/npm required.


## UI-3.4.1 hotfix — October 2026

1. **Club-only result feed:** every fixture in the world continues to simulate and enters the engine ledger, but the progress screen queues/displays only results with `managed: true`. The backend job protocol, RNG, cursor paging and transactional commit are unchanged. The UI exposes club matches played and days processed, not a long list of unrelated teams. A range without a managed fixture shows a meaningful empty state.
2. **In-game confirmation:** replaces the browser-native `window.confirm` with a themed modal showing inclusive target date, days to process and number of *currently known* club fixtures. Unknown future cup draws are explicitly not counted. Start alone begins the job; Cancel, Escape or backdrop click do not mutate the Python session. Keyboard focus returns to the invoking control.
3. **Verification:** `tests/test_ui3411_calendar_club_results_modal.py` checks the engine's managed flag against actual fixture participation and the frontend contract; a separate Playwright/Chromium test confirmed that two managed matches show while two unrelated world results do not, and that cancel/escape never creates a job. Previous tests of chronological progression and transactionality remain applicable.

Patch directly over UI-3.4.1. The separate match-tab experience, mandatory decision engine and complete save/load are still future work.
