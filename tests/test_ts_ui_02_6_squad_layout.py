"""TS-UI-02.6 contracts: Squad directory and header are real reusable components."""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
JS = (ROOT / 'frontend/public/squad/squad_ui02.js').read_text(encoding='utf-8')
CSS = (ROOT / 'frontend/public/squad/squad_ui028.css').read_text(encoding='utf-8')
EMBED = (ROOT / 'frontend/public/squad/embed.html').read_text(encoding='utf-8')


def test_final_styles_are_loaded_last():
    assert EMBED.index('squad_ui025.css') < EMBED.index('squad_ui026.css')
    assert EMBED.index('squad_ui026.css') < EMBED.index('squad_ui02.js')


def test_directory_has_single_toolbar_and_no_table_columns():
    part = JS.split('function roster(data)', 1)[1].split('function kitGraphic', 1)[0]
    for key in ('s28-directory-head', 's28-tools', 's28-search', 's28-sort', 's28-list-scroll'):
        assert key in part
    assert 's2-colheads' not in part
    assert 's28-screen-reader' in part


def test_list_renders_only_verified_player_fields():
    part = JS.split('function rosterRow(p,data)', 1)[1].split('function rosterContents', 1)[0]
    for key in ('p.id', 'p.name', 'p.primary_position', 'p.age',
                'p.act', 'p.condition', 'p.morale', 'nation(p)', 'captainBadge(p,data)'):
        assert key in part
    assert 's28-morale' in part and 's28-row-condition' in part
    assert 's28-row-overall' in part and 's28-profile-link' in part


def test_captain_comes_from_effective_captain_only():
    assert "data?.set_pieces?.roles?.find(entry=>entry.role==='captain')" in JS
    assert 'captain.effective_id===player.id' in JS
    assert 'captainBadge(p,data,true)' in JS
    assert 'captainBadge(p,data)' in JS


def test_dorsal_and_ability_not_fabricated():
    part = JS.split('function playerHeader(p,data)', 1)[1].split('const pitchPoints=', 1)[0]
    assert "p.number==null?'—':html(p.number)" in part
    assert 'badge(p.act)' in part and 'badge(p.base_ovr)' in part
    assert '▲ +1.2' not in JS


def test_header_uses_theme_assets_without_hardcoded_club():
    part = JS.split('function playerHeader(p,data)', 1)[1].split('const pitchPoints=', 1)[0]
    assert 'view.identities[data.club_id]' in part
    assert 'safeAsset(identity.crest)' in part and 'entry.hero_image' in JS
    assert 'kitGraphic(p,data)' in part
    assert 's28-kit-holder' in part and 's28-metrics' in part
    assert 'sunderland' not in part.lower()


def test_crest_and_kit_fit_preserves_image_fallback():
    assert '.s28-kit-holder .s2-shirt-image' in CSS
    assert 'object-fit:contain' in CSS
    assert 's28-kit-stage' in CSS and 's28-crest-watermark' in CSS
    assert 'kitGraphic(player,view.data,true)' in JS
    assert "img.addEventListener('error',fallback" in JS


def test_async_catalogue_updates_name_as_well_as_art():
    assert 'data-s26-club-name' in JS
    assert "const clubLabel=$('[data-s26-club-name]')" in JS
    assert 'clubLabel.textContent=entry.display_name' in JS
    assert 'view.identities[id]' in JS


def test_player_selection_vs_open_profile_are_disjoint():
    assert 'data-roster-expand="${html(p.id)}"' in JS
    assert 'data-open-career-player="${html(p.id)}"' in JS
    controller = (ROOT / 'frontend/public/squad/squad.js').read_text(encoding='utf-8')
    first = controller.index("if(button.hasAttribute('data-open-career-player'))")
    later = controller.index("if(screen==='squad' && window.FMRoster.onClick(button")
    assert first < later
    assert "event.target.closest('[data-s2-row]')" in controller


def test_persistent_tabs_and_responsive_reduced_motion():
    segment=JS.split('function switchInspectorTab(tab)',1)[1].split('function focusPosition(pos)',1)[0]
    assert 'panel.innerHTML=' in segment and 'current.replaceWith' not in segment
    assert '@media(max-width:1500px)' in CSS
    assert '@media(max-width:1000px)' in CSS
    assert '@media(prefers-reduced-motion:reduce)' in CSS
    assert 'window.location.href' not in segment


def test_no_local_asset_or_gameplay_migrations():
    assert not re.search(r'(CREATE TABLE|DROP TABLE|ALTER TABLE|UPDATE players SET)', JS)
    assert 'sunderland' not in JS.lower()
    assert '#c72838' not in CSS.lower()
