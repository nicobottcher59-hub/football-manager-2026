"""TS-UI-02.8 presentation regression contracts (no simulator changes)."""
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]
UI = ROOT / 'frontend/public/squad'
JS = (UI / 'squad_ui02.js').read_text(encoding='utf-8')
CSS = (UI / 'squad_ui028.css').read_text(encoding='utf-8')
EMBED = (UI / 'embed.html').read_text(encoding='utf-8')
CATALOGUE = json.loads((ROOT / 'frontend/portable/data/club-identities.json').read_text(encoding='utf-8'))


def test_new_visual_module_loads_after_all_prior_versions():
    assert EMBED.index('squad_ui026.css') < EMBED.index('squad_ui027.css') < EMBED.index('squad_ui028.css')
    assert 'squad_ui02.js' in EMBED


def test_directory_is_a_selectable_player_card_not_a_table():
    part = JS.split('function rosterRow(p,data)', 1)[1].split('function rosterContents(data)', 1)[0]
    for token in ('s28-player-card', 's28-row-face', 's28-row-identity', 's28-morale',
                  's28-row-condition', 's28-row-overall', 's28-row-arrow', 'role="row"',
                  'aria-selected=', 'captainBadge(p,data)', 'p.number==null'):
        assert token in part
    assert '<table' not in part
    assert 's28-profile-link' in part and 'data-open-career-player=' in part
    assert 'data-roster-expand=' in part


def test_hero_uses_live_player_data_and_modular_club_assets():
    part = JS.split('function playerHeader(p,data)', 1)[1].split('const pitchPoints=', 1)[0]
    for token in ('s28-hero', 's28-bio', 's28-kit-stage', 's28-kit-holder', 's28-metrics',
                  's28-dorsal-metric', 's28-current-metric', 's28-base-metric',
                  'captainBadge(p,data,true)', 'kitGraphic(p,data)',
                  'view.identities[data.club_id]', 'safeAsset(identity.crest)',
                  'badge(p.act)', 'badge(p.base_ovr)', "p.number==null?'—':html(p.number)"):
        assert token in part
    assert 'sunderland' not in JS.lower()
    assert 'sunderland' not in CSS.lower()


def test_clean_kit_is_supplied_by_identity_catalogue_and_is_not_a_hardcoded_shirt():
    entry = CATALOGUE['clubs']['northbridge']
    assert entry['kit_image'] == 'assets/clubs/sunderland/home_kit_clean.webp'
    assert entry['crest'] == 'assets/clubs/sunderland/crest.png'
    asset = ROOT / 'frontend/portable' / entry['kit_image']
    assert asset.is_file() and asset.stat().st_size > 25000
    assert asset.read_bytes()[:4] == b'RIFF'
    assert asset.read_bytes()[8:12] == b'WEBP'
    assert 'safeAsset(identity.kit_image)' in JS
    assert 's28-kit-holder .s2-shirt-image' in CSS and 'object-fit:contain' in CSS


def test_dedicated_watermark_follows_theme_and_refreshes_after_catalogue_load():
    assert "watermark.style.setProperty('--s28-watermark'" in JS
    assert 'background-image:var(--s28-watermark,none)' in CSS
    assert '--s2-club-primary' in CSS and '--s2-club-rgb' in CSS
    assert 'mix-blend-mode:screen' in CSS
    assert 'clubLabel.textContent=entry.display_name' in JS
    assert 'holder.innerHTML=kitGraphic(active,view.data)' in JS


def test_header_metrics_fit_in_a_height_limited_hero():
    assert '.s28-hero{' in CSS and 'grid-template-rows:minmax(0,1fr)' in CSS
    assert '.s28-kit-holder .s2-shirt-image' in CSS
    assert 'max-height:232px!important' in CSS
    assert '.s28-metrics{' in CSS and 'grid-template-rows:minmax(0,.95fr)' in CSS
    assert '@media(max-width:1500px)' in CSS and '@media(max-width:1000px)' in CSS


def test_position_map_role_comparison_and_every_attribute_remain_available():
    assert 'function profileTab(p,data)' in JS
    assert 'function groupedAttributes(p)' in JS
    assert 'Object.entries(p.attributes?.[group]||{})' in JS
    assert 'data-s2-focus-position=' in JS
    assert 's24-comparison-card' in JS
    assert 's24-attribute-groups' in JS
    assert '.s24-profile-top' in CSS
    assert '.s24-profile-top>.s24-positions-card' in CSS


def test_tab_changes_preserve_header_and_roster_dom():
    segment = JS.split('function switchInspectorTab(tab)', 1)[1].split('function focusPosition(pos)', 1)[0]
    assert 'panel.innerHTML=' in segment
    assert 'tablist.querySelectorAll' in segment
    assert 'current.replaceWith' not in segment
    assert 'window.location.href' not in segment
    assert '@media(prefers-reduced-motion:reduce)' in CSS


def test_actions_and_scope_are_not_modified_by_the_rebuild():
    assert "action:'squad_number'" in JS
    assert "action:'transfer_status'" in JS
    assert 'data-open-finances' in JS
    assert 'state.competition=' in JS
    assert 'All competitions' in JS
