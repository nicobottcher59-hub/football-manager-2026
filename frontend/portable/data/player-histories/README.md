# Optional player archives (TS-UI-11)

To import verified historical data before a career, place a JSON document named
`<stable-player-ID>.json` in this directory. Player IDs must contain only letters,
numbers, `_` or `-` (maximum 128 characters).

Example: `player-103.json`:

```json
{
  "schema_version": 1,
  "player_id": "player-103",
  "record": {
    "seasons": [{"season": "2025/26", "clubs": [{"id": "club-1", "name": "Example FC"}], "statistics": {"appearances": 17, "goals": 3, "assists": 1, "average_match_rating": 6.8}, "coverage": {"complete_season": true}}],
    "honours": [{"season": "2025/26", "competition_id": "fa-cup", "competition": "FA Cup", "club_id": "club-1", "club": "Example FC"}],
    "awards": []
  }
}
```

These are examples of **format only**, not shipped player history. No actual
pre-career records are imported with TS-UI-11. The UI merges archive entries by
stable IDs and season, preferring verified career ledger entries on conflicts.
All users are responsible for the provenance and accuracy of imported archives.
