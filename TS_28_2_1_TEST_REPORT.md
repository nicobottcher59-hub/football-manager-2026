# TS-28.2.1 | Career History visibility hotfix and Squad access

## Root cause

The TS-28.2 portable `index.html` omitted `</script>` after the external `news.js` tag. Consequently the following `<script src="history.js" defer>` was parsed as content inside the existing script instead of as a new script tag. The career-history module was not instantiated. The router used optional chaining (`window.FMHistory?.mount`) and silently displayed an empty page for both `Career History` and `Club Info`.

This is a UI defect, **not missing historical data**. A fresh career (August 2026) legitimately has little past history, but the club's current season, current player identity and available statistics can already be displayed.

## Files changed

- `frontend/portable/index.html`: correctly close the `news.js` tag, allowing `history.js` to load as an independent deferred script.
- `frontend/portable/portable.js`: show an explanatory error instead of blank content if the history module is unavailable; show a loading state and handle failures while resolving `Club Info` from the active squad.
- `frontend/public/squad/squad.js`: include a direct `Career history` action inside the selected starter's profile (in Squad and Tactics).
- `frontend/public/squad/roster.js`: show a direct accessible per-player career-history shortcut beside the name in the full Squad table. Retain the existing full `Career history` action in the expanded player details.
- `frontend/public/squad/presentation.css`: style the shortcut in the existing design.
- `tests/test_ts_28_2_1_history_hotfix.py`: regression tests for proper script HTML structure, Squad navigation hooks and new-career data.

## Tests executed

| Check | Result |
|---|---|
| TS-28.2.1 hotfix cases | 3/3 passed |
| TS-28.2 history regression | 6/6 passed |
| TS-28.1 news regression | 7/7 passed |
| JavaScript syntax (`node --check` on changed JS and history.js) | Passed |
| Portable HTML script order and closing tags | Passed |
| Isolated Chromium rendering of actual live career-history read models | Club and player pages rendered; no JavaScript page errors |

The Chromium rendering test ran in an **isolated document** using real Python read-model responses and mocked fetch calls. A full Chromium page navigation to the local HTTP server was blocked by the environment; Windows visual interaction and long-horizon simulation remain untested in this hotfix.

## Compatibility

- Apply **over TS-28.2**, preserving relative paths.
- No save migration; manager graph / SQLite remains **v21**.
- No changes to match simulations, finances or player records.
- No removals, save files or Git metadata included.

## GitHub Desktop

**Branch:** `fix/ts-28-2-1-history-and-squad-links`

**Summary:** `fix: TS-28.2.1 restore career history and squad links`

**Description:** `Fix the malformed portable script tag that prevented Career History and Club Info from rendering. Add explicit loading/error states and accessible career-history shortcuts in the Squad roster and selected-player panel. Keep SQLite v21 and all existing history data unchanged. Add regression and isolated browser rendering checks.`
