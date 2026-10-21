"""TS-UI-02.9 presentation contracts; no engine, save format, or simulated values."""
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]
UI = ROOT / 'frontend/public/squad'
JS = (UI / 'squad_ui02.js').read_text(encoding='utf-8')
CSS = (UI / 'squad_ui029.css').read_text(encoding='utf-8')
EMBED = (UI / 'embed.html').read_text(encoding='utf-8')
PRESENTATION = (UI / 'presentation.js').read_text(encoding='utf-8')
CATALOG = json.loads((ROOT / 'frontend/portable/data/club-identities.json').read_text(encoding='utf-8'))


def test_new_sheet_loads_last_and_namespace_is_separate():
    assert EMBED.index('squad_ui028.css') < EMBED.index('squad_ui029.css')
    assert 's29-hero s28-hero' in JS
    assert 's29-player-card s28-player-card' in JS
    assert '.s29-directory' in CSS and '.s29-hero' in CSS


def test_rows_show_recorded_dorsal_captain_morale_fitness_and_grl():
    part = JS.split('function rosterRow(p,data)', 1)[1].split('function rosterContents', 1)[0]
    for item in ('p.number==null', 'captainBadge(p,data)', 'moodSvg', 'p.condition',
                 'badge(p.act)', 'p.age', 'nation(p)', 's29-player-card'):
        assert item in part
    assert 'data-open-career-player' in part and 'data-roster-expand' in part
    assert 'No shirt' not in part


def test_header_four_regions_and_current_career_metrics():
    section = JS.split('function playerHeader(p,data)', 1)[1].split('const pitchPoints=', 1)[0]
    for item in ('s29-portrait', 's29-bio', 's29-kit-stage', 's29-metrics',
                 'captainBadge(p,data,true)', 'kitGraphic(p,data)',
                 'badge(p.act)', 'badge(p.base_ovr)', "p.number==null?'—':html(p.number)"):
        assert item in section
    assert 'sunderland' not in JS.lower()


def test_crest_uses_two_catalogue_backed_layers_not_hardcoded_club():
    assert '--s29-crest' in JS
    assert '--s28-watermark' in JS
    assert 's29-crest-silhouette' in JS
    assert '.s28-crest-watermark.has-crest' in CSS
    assert 'var(--s2-club-primary)' in CSS and '--s2-club-rgb' in CSS
    assert 'color-mix(' in CSS
    assert '#c72838' not in CSS.lower()
    assert 'sunderland' not in CSS.lower()


def test_club_shirt_asset_is_transparent_and_falls_back():
    cfg = CATALOG['clubs']['northbridge']
    path = ROOT / 'frontend/portable' / cfg['kit_image']
    assert path.is_file() and path.stat().st_size > 25000
    assert path.read_bytes()[:4] == b'RIFF'
    assert 'object-fit:contain!important' in CSS
    assert "img.addEventListener('error',fallback" in JS


def test_tactical_profile_remains_live_and_all_attributes_are_shown():
    assert 'data-s2-focus-position' in JS
    assert 'function groupedAttributes(p)' in JS
    assert 'Object.entries(p.attributes?.[group]||{})' in JS
    assert 's24-attributes-card' in JS
    assert '.s24-profile-top' in CSS and '.s24-positions-card' in CSS


def test_radar_comparison_is_one_shared_chart_with_complete_axis_labels():
    part = PRESENTATION.split('function roleComparison(', 1)[1].split('function developmentPanel(', 1)[0]
    assert 's24-comparison-radar' in part
    assert 'roleValues' in part and 'playerValues' in part
    assert 'viewBox="62 0 486 350"' in part
    assert 'point(i,1.18)' in part
    assert 'graphics.role_options' in part


def test_tab_transitions_retain_header_and_list_without_navigation():
    part = JS.split('function switchInspectorTab(tab)', 1)[1].split('function focusPosition(pos)', 1)[0]
    assert 'panel.innerHTML=' in part
    assert 'current.replaceWith' not in part
    assert 'location.href' not in part
    assert 'tablist.querySelectorAll' in part


def test_python_management_and_scope_are_unchanged():
    for token in ("action:'squad_number'", "action:'transfer_status'",
                  'data-open-finances', 'All competitions', 'state.competition'):
        assert token in JS


def test_responsive_and_accessibility_without_requiring_external_dependencies():
    for token in ('@media(max-width:1500px)', '@media(max-width:1000px)',
                  '@media(prefers-reduced-motion:reduce)', 'aria-selected', 'aria-label'):
        assert token in CSS + JS
