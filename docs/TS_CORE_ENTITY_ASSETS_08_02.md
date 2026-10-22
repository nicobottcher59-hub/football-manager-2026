# TS-CORE 08.02 - Universal visual identity and imported assets

This is a presentation layer. Game IDs, clubs, fixtures, finance, player data,
contract records, simulation and save schemas remain authoritative in Python.

## ID resolution

- Club ID -> public display/short name, palette, crest, home/away/goalkeeper
  shirt images and optional hero/medical photographs.
- Player ID -> optional imported photograph; the shared deterministic illustration
  remains underneath when no photograph exists.
- Competition ID -> optional official logo, falling back to the existing branding
  or a neutral mark. Never substitute an unrelated team's crest.
- Missing image -> fallback. A missing player height or weight stays blank.
- Staff cards are intentionally icon-only, as approved.

`FMEntityAssets` loads `/portable/data/entity-assets.json`. `FMClubIdentity`
merges its contents over the previously approved club catalog. Imported assets
are stored by ID and can be used from portable, the Squad iframe and Match.
All paths are relative to `frontend/portable/` and validated.

## Import from a future database's assets folder

Organize image files by **stable world ID**, not display name:

```
image-source/
  players/PLAYER_ID.png
  clubs/CLUB_ID/crest.png
  clubs/CLUB_ID/home.png
  clubs/CLUB_ID/away.png
  clubs/CLUB_ID/goalkeeper.png
  clubs/CLUB_ID/hero.jpg
  clubs/CLUB_ID/medical.jpg
  competitions/COMPETITION_ID.png
```

Optional `club-metadata.json`:

```
{"clubs":{"CLUB_ID":{"display_name":"Club Name","short_name":"Club",
"primary_color":"#224466","secondary_color":"#ffffff","accent_color":"#ccaa66"}}}
```

Run from the repository root:

```
python tools/import_entity_assets.py --source image-source --metadata club-metadata.json
```

The script validates each image, copies it into `frontend/portable/assets/imported`
and writes the manifest in `frontend/portable/data/entity-assets.json`.
Use `--dry-run` to validate without writing. It **does not scrape/download
licensed photos, resize images or import football/player records**.

## Dependencies and limitations

- Club and player identifiers in an eventual imported DB must match those sent
  by the Python world. This patch does not implement the football DB importer.
- Existing world identity records take priority as simulation entities. New
  public names/colours are *presentation overlays*, not new teams.
- Fallback player drawings use the club palette where the club identity is
  available. Official kit graphics still require actual files in the manifest.
- For hundreds of thousands of players, server-side filtering/pagination and
  image size optimization are a separate performance task; Scouting still
  transfers its current full player directory on page load.
- Existing legacy Transfers views have their own knowledge presentation;
  confidential-data visibility must be audited there independently before a
  future large real-world database release.

## Visual touchpoints updated

Squad and shared player portraits; Scouting; Youth Academy; Staff/Training/
Medical; Dressing Room through shared portraits; Home through identity/catalog;
Calendar/Competitions through club and competition IDs; Match Centre crests,
team names and optional kits; World Squads' displayed team names.

These changes do not alter sporting identities, transfers or save migrations.
