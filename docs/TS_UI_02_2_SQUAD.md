# TS-UI-02.2 — Squad: split-view, reusable club theme

## Scope

The read-only roster UI now uses a compact list and a persistent player inspector. Tactics still uses the original board and instructions. The four inspector tabs use actual Python read-model fields:

- **Profile / Attributes:** registered positional familiarity and attributes; radar visualizations retrieved from the existing player profile API.
- **Season statistics:** season/competition selectors, default **All competitions**, supported metrics and data coverage. Backend `player_statistics` performs the aggregation. Unsupported metrics such as xA and tackles are not fabricated.
- **Status & development:** condition, sharpness, fatigue, morale, form, availability, and the existing development focus selector. Happiness is shown as unknown if not recorded.
- **Contract & actions:** contract terms separate from the actions card. Wages and expiry come from the registered contract; changing a squad number or DEV transfer flag sends the existing `/api/squad` action, while contracts, talks, training, tactics and medical screens are accessed through their existing routes.

The list and inspector have independent scroll areas, preserved across rerenders, with a stacked layout on smaller widths.

## Club identity / scalable portraits

Club themes come from `frontend/portable/data/club-identities.json`, keyed by canonical `club_id`. Other clubs without an identity use a neutral fallback; they do not inherit Sunderland's colors. The header references the club's optional crest, banner, primary and accent colors. Semantic indicators (injury, fatigue, fitness, OVR) remain universal.

`frontend/public/squad/data/player-portraits.json` maps **immutable player IDs** to optional pictures under `frontend/public/squad/assets/`. For example, after adding a file at `frontend/public/squad/assets/players/northbridge-p0001.webp`, use:

```json
{
  "schema_version": 1,
  "portraits": {
    "northbridge-p0001": "assets/players/northbridge-p0001.webp"
  }
}
```

This is an **example**; use the actual ID of your player as returned by the Python read model. Supported formats: `.png`, `.jpg`, `.jpeg`, `.webp`. Missing/invalid images fall back to the existing deterministic cartoon portrait, including if an image fails to load. No player photos are included in this patch. Club IDs and athlete IDs are not inferred from displayed names.

## Operational limits

- The transfer list flag and squad number are existing DEV metadata, not actual executed transfers or a new squad-registration simulation.
- Contract negotiations and conversations remain owned by their existing modules; the Squad inspector does not invent new domain actions.
- Data for prior seasons reflects recorded coverage; incomplete history is labeled as such.
- Visual browser tests are isolated from saved careers. Live Windows validation and a full multi-season regression are not claimed.
