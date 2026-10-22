# TS-UI-08.02 + TS-CORE asset registry - validation

**Incremental baseline:** TS-UI-08.01. No database or save migrations.

## Changes

- Scouting: visible salary and contract expiry, market-value display, and
  Asc/Desc sorting for name, age, height, GRL, value and scouting progress.
  Unknown metrics stay last in either direction.
- Elite players (GRL >= 85): public GRL, market value and attributes; hidden
  potential is never sent as exact latent PA. Unscouted ordinary professionals
  still receive no GRL/value/attribute fields.
- Scouting can launch the pre-existing Transfers negotiation without a report.
  The transfer engine remains unchanged.
- Unified optional ID-based photo/crest/competition/kit lookup and importer.
- Calendar, Competitions, Medical and Match Centre no longer special-case the
  identity of the managed club. Existing graphics are retained as fallback.
- Real attributes and scouting estimates use the domain's 1-100 scale.

## Executed checks

1. `PYTHONPATH=src pytest -q tests/test_ts_ui_08_02_scouting_assets.py`
   -> **4 passed**.
2. `PYTHONPATH=src pytest -q tests/test_ts_ui_08_scouting_hub.py -k
   'world_search_is_unrestricted or shortlist_add_priority_remove or
   scout_destination_is_real_staff'` -> **3 passed**.
3. `PYTHONPATH=src pytest -q tests/test_ts_ui_08_scouting_hub.py -k
   'reports_unlock_only_estimates_and_inbox'` -> **1 passed**.
4. Node VM smoke of actual `assets_registry.js` + `club_identity.js`: imported
   club name, palette, crest, photo, kit and competition logo; missing-club
   fallback and rejection of invalid paths -> **passed**.
5. `node --check` on all changed JavaScript and `py_compile` for Python and
   importer -> **passed**.
6. PNG fixture import: verified ID-keyed source copy and manifest outputs in
   automated Python tests -> **passed**.

## Not asserted

- No fresh full-browser end-to-end test was completed for this recovered code;
  legacy wide regressions also were not run to completion.
- The football DB itself and real club/player/competition asset packs are not
  included. This patch prepares the ID-based integration only.
- Height remains unavailable in the current player domain, so sorting by
  height is valid but those records are tied/unknown.
- Legacy Transfers screens still have an independently designed player
  knowledge view; the new masking rules govern the Scouting Hub.

**Compatibility:** overlay on 08.01. Preserve a backup of the career save.
