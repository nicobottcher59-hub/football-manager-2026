# UI-3.3.2 — Separate Competition Screens & Country Filter Hotfix

## User-approved navigation

- **Competitions** (left sidebar): UNCHANGED UI-3.3.1 presentation. A row of club-only competition tabs, full table or bilateral cup bracket, four semantic zoom levels, and the right panel with every match of the selected round/matchday. Northbridge's registered FA Cup entry remains selectable before the club has a confirmed third-round draw.
- **Other Leagues** (its own left-sidebar button, next to Competitions): a separate view for all the other tournaments already loaded in the Python world. The previous My competitions / Other leagues tab switch *inside* Competitions was a mistake and has been removed.

The two routes intentionally **reuse the same read-only competition renderer**, selected by `window.FMCompetitions.mount(node, 'mine'|'other')`. This does not merge the two user-facing sections. Each route remembers its selected tournament during the local session; entering a route re-reads the Python index.

## Other Leagues filtering

1. Participants: Clubs / National teams (future; explicitly unavailable).
2. Scope: all, national, international.
3. **Continent: ALWAYS visible**, including domestic competitions. Six continents supported as discovery options.
4. **Country:** visible for all/national scope, filtered to the chosen continent; includes selectable future countries (Spain, Italy, Germany, Argentina, Brazil, etc.) even if no current tournament exists there.
5. Competition type: league, domestic cup, continental tournament (where applicable).
6. Division: first through fourth division (only for national/all scope and league/all types).
7. Competition picker: **only the matches from `competition_options()` that exist in Python**.

The current DEV world implements domestic competitions only for **England**, and UEFA events in Europe. Selecting Spain, Argentina or an unavailable continent does not produce fictitious leagues; a clear empty-state message appears. Country choices are discoverability/expansion placeholders, not claims that those competitions are simulated.

The original UI-3.3.2 picker only derived its options from existing competition entries (England), which made it appear unusable to browse other countries. The hotfix makes the selectors function with empty states, while preserving the Python index as the exclusive source of results/standings.

## Constraints

- No changes to FastMatchSimulator, WorldSeasonRunner, match scheduling, results, cup draws, player models or persistence.
- No changes to the bilateral bracket, zoom levels, round detail, progress connectors or competition API semantics.
- Continue is still disabled; the portable Windows `.bat` launcher needs no Node.js/npm.
- No new real-world clubs, imports, competitions or match results added.

## Tests and acceptance checks

- `PYTHONPATH=src python -m pytest -q tests/test_ui33_competitions.py tests/test_ui332_competition_explorer.py`.
- Chromium: clicking *Competitions* shows four tabs including FA Cup and no directory filters. Clicking *Other Leagues* shows Continent even with scope All; selecting **Europe / National / Spain** produces an empty state, then **England / third division** opens League One. **South America / Argentina** remains empty; switching to **Europe / International** exposes Europa League / Conference League. Going back to Competitions preserves the last selected cup and bilateral zoom works.
- Verify no JavaScript runtime errors; smoke-test the ZIP after layering onto the exact UI-3.3.2 files.

## Installation

Apply **UI-3.3.2 HOTFIX** on top of the previous UI-3.3.2 patch (not onto UI-3.3.1). Stay on `phase-ui-3-3-2-competition-explorer` if not committed. Stop the existing server, extract the patch into the repository root, replace modified files, rerun `INICIAR_INTERFAZ_WINDOWS.bat` and hard-refresh Chrome with `Ctrl+Shift+R`. Do not commit until user approval.

## Hotfix 2 (index mismatch: 10 / 0)

The UI-3.3.2.1 repair includes the Python competition index module again, even though it was already supplied in the original UI-3.3.2 patch. An installation with only frontend patches can otherwise keep the old Python API: it returns all ten competitions in `competitions`, does not expose `other_competitions`, and has no continent/country metadata. This exactly explains the report of ten club tabs and zero Other Leagues results.

The backend now tags the partitioned index with `schema_version: 2`. The portable frontend checks this contract and refuses to render incorrectly grouped competitions when talking to a stale Python server. The Windows launcher remains unchanged. Close all old server windows before applying the patch, so the new code is imported.

Verified default DEV collection: club Premier League, FA Cup (registered, no tie drawn yet), Carabao Cup, UEFA Champions League; others Championship, League One, League Two, UEFA Europa League, UEFA Conference League, EFL Trophy. Filtering England / third division displays League One and international / Europe displays Europa and Conference. No other game mechanics change.
