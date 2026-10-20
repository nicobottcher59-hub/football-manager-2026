# TS-UI-02.6 — Squad directory and player hero rebuild

## Base

Incremental update on **TS-UI-02.5**. No complete game distribution; existing Sunderland assets are reused via `club-identities.json`.

## Implementation

- Rebuilt the **left player directory**: single title/search/sort toolbar; compact cards featuring existing portrait, name, real position/age/nationality, effective captain flag, registered morale, condition meter, current GRL, and a separate full-profile shortcut.
- Rebuilt the **right player hero** as a four-zone grid: replaceable portrait, player identity, full club-specific kit plus clearly visible crest watermark, and real dorsal/ACT/OVR. No fabricated numbers, roles, rating changes, or badges.
- Improved dynamic club identity: delayed catalogue loading also updates the **Squad banner name** (previously could remain the fictional world label).
- Scoped styles in a new `squad_ui026.css` layer, loaded after earlier Squad layers; this allows preserving the existing game engine and other tab implementations.
- Retained **persistent internal tabs** introduced in TS-UI-02.4; clicking a tab redraws its body only. List/hero persist.
- Preserved current management entry points and per-player navigation, with the row itself used strictly for selection.
- Added accessible names for morale, condition and captain; `prefers-reduced-motion` disables entrance effects.

## Source and scalability

- Club name, colors, crest, background and kit: `/portable/data/club-identities.json`, looked up using immutable `club_id`.
- Player images: optional player-ID keyed catalogue, with existing temporary illustrated avatar fallback.
- Position, GRL, morale, physical condition, dorsal, nationality, effective captain: active Python-backed Squad read model.
- Missing numbers remain `—`; missing club kit shows existing generic illustrated shirt.

## Installation

Close the game, back up your project, then overlay the contents of the patch ZIP at the project root, replacing matching files. Install on top of **TS-UI-02.5** (and its required earlier patches). Restart the UI and use Ctrl+F5 if a stale cached stylesheet remains.

## Validation limits

Chromium isolated layout and regression checks passed at 1680×980, 1366×860 and 980×800. The browser fixture deliberately contains test players; no claim is made that these are the live Windows career's players or that this verifies the native Windows shell. Final acceptance must compare the user's Windows screenshot against the approved reference at the same viewport.
