"""TS-UI-02.7 presentation contracts; no gameplay or migration changes."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = (ROOT / 'frontend/public/squad/squad_ui02.js').read_text(encoding='utf-8')
CSS = (ROOT / 'frontend/public/squad/squad_ui027.css').read_text(encoding='utf-8')
EMBED = (ROOT / 'frontend/public/squad/embed.html').read_text(encoding='utf-8')


def test_final_stylesheet_loaded_after_existing_versions():
    assert EMBED.index('squad_ui025.css') < EMBED.index('squad_ui026.css') < EMBED.index('squad_ui027.css')


def test_real_player_card_has_dorsal_captain_morale_condition_and_rating():
    part = JS.split('function rosterRow(p,data)', 1)[1].split('function rosterContents', 1)[0]
    for piece in ('s27-player-card', 's27-row-dorsal', 'p.number==null',
                  'captainBadge(p,data)', 's26-morale', 's26-condition',
                  'badge(p.act)', 'data-roster-expand=', 'data-open-career-player='):
        assert piece in part
    assert 'No shirt no' not in part


def test_hero_has_four_real_data_zones_and_themed_art():
    part = JS.split('function playerHeader(p,data)', 1)[1].split('const pitchPoints=', 1)[0]
    for piece in ('s27-hero-portrait', 's27-hero-identity', 's27-kit-stage',
                  's27-hero-scores', 'kitGraphic(p,data)', 'captainBadge(p,data,true)',
                  "p.number==null?'—':html(p.number)", 'badge(p.act)',
                  'badge(p.base_ovr)', 'safeAsset(theme.crest)'):
        assert piece in part
    assert '▲ +1.2' not in part
    assert "title=\"Current rating relative to base overall; not a historical gain\"" in part


def test_mask_supports_dynamic_club_identity_and_late_catalogue_loading():
    assert '--s27-watermark' in JS and '--s27-watermark' in CSS
    assert "watermark.style.setProperty('--s27-watermark'" in JS
    assert 'background:var(--s2-club-primary)' in CSS
    assert 'mask-image:var(--s27-watermark)' in CSS
    assert 'sunderland' not in JS.lower()
    assert 'sunderland' not in CSS.lower()


def test_pitch_radar_kept_side_by_side_and_all_attributes_still_render():
    assert 's24-profile-top' in CSS
    assert '@media(min-width:760px)' in CSS
    assert 'grid-template-columns:minmax(0,.94fr) minmax(0,1.16fr)' in CSS
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
