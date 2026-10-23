# Club historical imports (TS-UI-10)

Create one JSON document named `<stable club ID>.json` for each club that has verified pre-career history. The UI fetches only the selected club.

Example **schema only** (not an actual football record):

```json
{
  "schema_version": 1,
  "club_id": "sample-club-id",
  "record": {
    "country": "Example country",
    "founded": 1900,
    "biography": "Verified institutional description",
    "honours": [{"competition_id": "league-code", "competition": "League", "total": 2, "seasons": ["1911/12", "1925/26"]}],
    "timeline": [{"date": "1900", "text": "Founding verified by official archive"}],
    "records": [{"label": "Most appearances", "value": 650, "holder": "Recorded player", "season": "2000/01"}],
    "philosophy": [{"title": "Club philosophy", "detail": "Source-backed description"}]
  }
}
```

Use the exact same club ID as the career roster and asset registry. Import only records from BEFORE the career starts; the game adds titles, movements, seasons and milestones from its own verified results. Unknown fields stay unpopulated. This directory must not be filled with invented history or screenshots.
