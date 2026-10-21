"""TS-UI-02.7 presentation contracts; no gameplay or migration changes."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = (ROOT / 'frontend/public/squad/squad_ui02.js').read_text(encoding='utf-8')
CSS = (ROOT / 'frontend/public/squad/squad_ui028.css').read_text(encoding='utf-8')
EMBED = (ROOT / 'frontend/public/squad/embed.html').read_text(encoding='utf-8')


def test_final_stylesheet_loaded_after_existing_versions():
    assert EMBED.index('squad_ui025.css') < EMBED.index('squad_ui026.css') < EMBED.index('squad_ui027.css')


def test_real_player_card_has_dorsal_captain_morale_condition_and_rating():
    part = JS.split('function rosterRow(p,data)', 1)[1].split('function rosterContents', 1)[0]
    for piece in ('s28-player-card', 's28-jersey-number', 'p.number==null',
                  'captainBadge(p,data)', 's28-morale', 's28-row-condition',
                  'badge(p.act)', 'data-roster-expand=', 'data-open-career-player='):
        assert piece in part
    assert 'No shirt no' not in part


def test_hero_has_four_real_data_zones_and_themed_art():
    part = JS.split('function playerHeader(p,data)', 1)[1].split('const pitchPoints=', 1)[0]
    for piece in ('s28-portrait-frame', 's28-bio', 's28-kit-stage',
                  's28-metrics', 'kitGraphic(p,data)', 'captainBadge(p,data,true)',
                  "p.number==null?'—':html(p.number)", 'badge(p.act)',
                  'badge(p.base_ovr)', 'safeAsset(identity.crest)'):
        assert piece in part
    assert '▲ +1.2' not in part
    assert "Contextual rating difference; not a permanent ability change" in part


def test_mask_supports_dynamic_club_identity_and_late_catalogue_loading():
    assert '--s28-watermark' in JS and '--s28-watermark' in CSS
    assert "watermark.style.setProperty('--s28-watermark'" in JS
    assert 'var(--s2-club-primary)' in CSS
    assert 'background-image:var(--s28-watermark,none)' in CSS
    assert 'sunderland' not in JS.lower()
    assert 'sunderland' not in CSS.lower()


def test_pitch_radar_kept_side_by_side_and_all_attributes_still_render():
    assert 's24-profile-top' in CSS
    assert '@media(min-width:1110px)' in CSS
    assert 'grid-template-columns:minmax(0,.93fr) minmax(0,1.17fr)' in CSS
    assert 'function groupedAttributes(p)' in JS
    assert 'Object.entries(p.attributes?.[group]||{})' in JS
    assert 's24-attribute-groups' in JS
    assert 'data-s2-focus-position=' in JS


def test_tabs_stay_local_and_styles_respect_reduced_motion():
    segment = JS.split('function switchInspectorTab(tab)', 1)[1].split('function focusPosition(pos)', 1)[0]
    assert 'panel.innerHTML=' in segment
    assert 'current.replaceWith' not in segment
    assert '@media(prefers-reduced-motion:reduce)' in CSS
    assert 'window.location.href' not in segment
