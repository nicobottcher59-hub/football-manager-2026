# TS-UI-02.5 — Squad hero and directory polish

## Base / installation

This is an incremental UI patch for **TS-UI-02.4**. Extract at project root, preserving folder paths and replacing matching files. No Python engine, DB schema, or save-file changes.

## Visual and behavior scope

- **Club-themed player hero**: four balanced areas—placeholder/photo, identity, club shirt/crest, and player ratings. The club home shirt stays inside the hero (`object-fit: contain`) and its transparent asset was tightly cropped to remove empty padding. The club crest is a more visible watermark, without making text illegible.
- **Squad number**: larger dedicated dorsal card. `—` is shown when the Python career has no number assigned; no provisional number is invented in the client.
- **Captain**: gold `C` appears in the list and the player hero only when the player's ID matches `data.set_pieces.roles[role='captain'].effective_id` (current effective on-field captain). No heuristics based on player OVR, name or role.
- **Player directory**: cleaner, tighter cards show avatar, name, main position, age, nationality, morale, OVR and condition. Removed the small repetitive `No shirt no.` label.
- **Search and sort**: simple player search and Position / GRL / Name sorting replace only the list contents. The inspector/header and its current tab remain mounted. These are presentation-only; no filter is applied to the Python roster.
- **Transitions**: additional nonintrusive kit and captain entrance, faster card hover. `prefers-reduced-motion` is respected.
- **Resource architecture**: club colors, emblem, backdrop and kit continue to resolve by immutable club ID from `frontend/portable/data/club-identities.json`. Player images resolve by player ID and keep illustrated fallbacks.

## Player context and accuracy

- `number` may be `null`, and that's displayed honestly.
- `set_pieces.roles` may be absent in rival/readonly views. In this case the captain marker is omitted.
- For a managed club, `set_piece_view` includes the actual XI `effective_id`; captain badge follows the current lineup rather than an invented permanent title.
- No fictitious player, potential, rating, contract, status or match data was introduced.

## Testing

- `pytest -q tests/test_ts_ui_02_5_squad_polish.py tests/test_ts_ui_02_4_profile.py tests/test_ts_ui_02_3_squad_visual.py tests/test_ts_ui_02_2_squad_split.py`
- Isolated Chromium checks at 1680×980, 1366×860, 980×800 confirmed no runtime exceptions or page horizontal overflow. Checked player selection, tabs, position dots, all listed attributes, shirt sizing, captain state, sorting, search without inspector rerender and unassigned dorsals.
- **Not** a native Windows or full season simulation run.
