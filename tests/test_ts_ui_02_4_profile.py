"""TS-UI-02.4: presentation-only regression checks, no world simulation."""
from pathlib import Path
import json

ROOT=Path(__file__).resolve().parents[1]
SQUAD=ROOT/'frontend/public/squad'

def source(path):
    return (ROOT/path).read_text(encoding='utf-8')


def test_latest_style_layer_is_loaded_after_prior_squad_layers():
    page=source('frontend/public/squad/embed.html')
    assert page.index('squad_ui02.css') < page.index('squad_ui023.css') < page.index('squad_ui024.css')
    assert page.index('presentation.js') < page.index('squad_ui02.js') < page.index('squad.js')


def test_tabs_replace_only_details_not_root_or_inspector():
    code=source('frontend/public/squad/squad_ui02.js')
    assert 'function switchInspectorTab(tab)' in code
    segment=code.split('function switchInspectorTab(tab)',1)[1].split('function focusPosition(pos)',1)[0]
    assert 'panel.innerHTML=' in segment
    assert 'panel.scrollTop=0' in segment
    assert 'tablist.querySelectorAll' in segment
    assert 'aria-selected' in segment
    assert 'view.tab=tab' in segment
    assert 'refresh()' not in segment
    assert 'root.innerHTML' not in segment
    assert 'document.location' not in segment


def test_player_switch_does_not_reload_roster():
    code=source('frontend/public/squad/squad_ui02.js')
    assert 'function showSelectedPlayer()' in code
    assert 'current.replaceWith(holder.firstElementChild)' in code
    assert 'row.classList.toggle' in code
    assert 'if(!showSelectedPlayer())refresh()' in code


def test_map_has_svg_lines_and_clickable_positions_linked_to_bars():
    code=source('frontend/public/squad/squad_ui02.js')
    assert '<svg class="s24-pitch-lines"' in code
    assert 'const positions=knownPositions(p)' in code
    assert 'p.primary_position' in code and 'p.secondary_positions||[]' in code
    assert 'data-s2-focus-position=' in code
    assert 'aria-pressed=' in code
    assert 'window.FMSquadUI02=' in code and 'focusPosition};' in code


def test_every_recorded_attribute_is_included_without_synthetic_values():
    code=source('frontend/public/squad/squad_ui02.js')
    segment=code.split('function groupedAttributes(p)',1)[1].split('function seasonTab(p,data)',1)[0]
    assert 'Object.entries(p.attributes?.[group]||{})' in segment
    assert 'typeof value===\'number\'' in segment
    assert '.slice(0,6)' not in segment
    assert 's24-attribute-row' in segment
    assert 'groups.reduce((n,g)=>n+g.entries.length,0)' in segment


def test_comparison_uses_real_engine_role_weights_not_made_up_thresholds():
    code=source('frontend/public/squad/presentation.js')
    assert 'function roleComparison(graphics' in code
    assert 'g.role' in code or 'graphics.role' in code
    assert "role.axes" in code
    assert '(Number(axis.weight)||0)/maxWeight*100' in code
    assert 'axis.value' in code
    assert 'Player ability' in code
    assert 'Role emphasis' in code
    assert "mode==='comparison'" in code
    assert "mode==='charts'?charts" in code  # original chart still works


def test_actual_sunderland_kit_is_in_identity_catalogue_not_js():
    catalogue=json.loads(source('frontend/portable/data/club-identities.json'))
    entry=catalogue['clubs']['northbridge']
    assert entry['kit_image']=='assets/clubs/sunderland/home_kit_clean.webp'
    file=ROOT/'frontend/portable'/entry['kit_image']
    assert file.exists() and file.stat().st_size > 1000
    from PIL import Image
    im=Image.open(file)
    assert im.mode=='RGBA'
    assert im.getextrema()[3][0]==0 and im.getextrema()[3][1]==255
    code=source('frontend/public/squad/squad_ui02.js')
    assert 'kit_image' in code
    assert 'home_kit.webp' not in code
    assert 'function kitGraphic(p,data,illustrated=false)' in code
    assert "img.addEventListener('error',fallback" in code


def test_interactive_layout_has_reduced_motion_fallback_and_club_theme():
    style=source('frontend/public/squad/squad_ui024.css')
    for token in ('@media(prefers-reduced-motion:reduce)', '--s2-club-primary',
                  '--s2-club-accent','--s2-club-rgb','.s24-pitch-dot.is-active',
                  '.s24-radar-player','.s24-radar-emphasis','.s24-attribute-group',
                  '.s24-tab-content'):
        assert token in style
    assert '#c72838' not in style
