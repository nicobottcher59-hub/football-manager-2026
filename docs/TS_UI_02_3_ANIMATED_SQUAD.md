# TS-UI-02.3 — Squad animated visual polish

## Goal

Squad keeps the proven **split layout** of TS-UI-02.2 but stops looking like a spreadsheet. It uses card-like roster rows, a more cinematic selected-player hero, role/attribute visualization, and restrained responsive animation, without compromising the recorded career data.

## UI structure

- **Left:** compact roster cards with existing replaceable illustrated portraits, actual GRL, age, shirt number when allocated, position, recorded condition, availability, and an icon derived only from recorded morale. It deliberately has no filter row or fifteen-column sheet.
- **Right header:** current player photo (with existing fallback), name, age, nationality and roles, a purely visual club shirt, genuine current GRL / base OVR, and a distinct **Full player profile** control. The back number is omitted if no number is registered.
- **Profile / Attributes:** positional schematic based on registered positions and the Python familiarity data, strongest actual attributes and existing authoritative radar charts.
- **Season statistics:** existing server-backed season + competition selector, including **All competitions** to show season aggregate values. Untracked fields remain unavailable. No invented ratings or results.
- **Status & development:** real morale/condition/sharpness/fatigue/form, a visual morale gauge and existing monthly development view.
- **Contract & actions:** generous, separate contract and operation blocks, without inventing bonuses, negotiations or actions unsupported by the backend.

## Interaction isolation (bug fix)

Selecting a roster row — **including its name text** — selects it in Squad. The neighboring ↗ button, the hero shortcut, and the lower profile link alone open the full player career view. The script delegates to the original `fm-open-history` navigation; no alternate route was invented. Enter/Space on a focused roster row works too, and pressing keys on a nested profile button is exempt.

The left roster's scroll location is preserved across player and tab selection, as in TS-UI-02.2.

## Motion system

Staggered content transition (~400 ms), progress-bar reveals (~700 ms), player position marker appearance, radar reveal, card hover and tab-state transitions. Hero ambient light is the only continuous effect and is very slow/low opacity. `prefers-reduced-motion: reduce` disables the animations and relevant transitions. Color semantics for injuries, condition and ratings are distinct from the club theme.

## Scalable identity and images

The existing `club-identities.json` entry keyed by immutable club ID continues to supply badge, banner and primary/secondary/accent colors. Two optional visual fields are supported:

- `kit_style: "vertical_stripes"` (otherwise a plain primary-color illustrative shirt);
- `kit_image: "assets/clubs/<id>/kit.png"` (optional image override; when present it supersedes the SVG).

The existing `frontend/public/squad/data/player-portraits.json` maps immutable player IDs to relative images beneath `frontend/public/squad/assets/`. Missing or broken images always leave the original illustrated portraits in place. No photo assets are embedded and no code branch references `Sunderland` or a player by name.

## Scope / limits

No game simulation, economic model, persistence schema, stats ledger, seasonal events, tactical calculations, or match engine is changed. `frontend/public/squad/squad_ui023.css` is loaded **after** TS-UI-02.2 CSS and is strictly scoped to `.is-squad`; Tactics remains unaffected.

UI consistency tested via isolated headless Chromium at 1680, 1366 and 980 px, plus a framed test for player navigation and slow club identity loading. Native Windows validation and the full 20-season simulation are still pending.
