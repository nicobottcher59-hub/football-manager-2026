"""TS-UI-02.5 regression contracts: presentation-only club/player visuals."""
import json
from pathlib import Path

from PIL import Image

ROOT=Path(__file__).resolve().parents[1]

def source(rel):
    return (ROOT/rel).read_text(encoding='utf-8')

JS=source('frontend/public/squad/squad_ui02.js')
CSS=source('frontend/public/squad/squad_ui025.css')
HTML=source('frontend/public/squad/embed.html')


def test_style_loaded_last():
    assert HTML.index('squad_ui023.css') < HTML.index('squad_ui024.css') < HTML.index('squad_ui025.css')
    assert HTML.index('squad_ui02.js') < HTML.index('squad.js')


def test_captain_comes_from_actual_python_lineup_not_ovr_or_name():
    assert "data?.set_pieces?.roles?.find(entry=>entry.role==='captain')" in JS
    assert 'captain.effective_id===player.id' in JS
    assert "!!captain?.effective_id" in JS
    assert 'captainBadge(p,data,true)' in JS
    assert 'captainBadge(p,data)' in JS
    assert 'Captain of the current XI' in JS
    assert 'const captain=data?.set_pieces' in JS


def test_large_dorsal_shows_real_number_or_dash():
    assert "p.number==null?'—':html(p.number)" in JS
    assert 's25-dorsal' in JS
    assert 'No shirt no.' not in JS
    assert 's25-captain' in CSS


def test_full_shirt_has_image_fit_no_fixed_club_asset_name():
    assert 'safeAsset(identity.kit_image)' in JS
    assert 'kitGraphic(p,data)' in JS
    assert '.s25-player-hero .s2-shirt-image' in CSS
    assert 'object-fit:contain' in CSS
    assert 'sunderland' not in JS.lower()
    catalogue=json.loads(source('frontend/portable/data/club-identities.json'))
    image=ROOT/'frontend/portable'/catalogue['clubs']['northbridge']['kit_image']
    with Image.open(image) as im:
        assert im.mode=='RGBA'
        assert im.getchannel('A').getextrema()==(0,255)
        assert im.getchannel('A').getbbox()[0] <= 10  # prepared tight crop


def test_crest_stays_data_driven_and_late_assets_repaint():
    assert 'view.identities[data.club_id]' in JS
    assert 'safeAsset(theme.crest)' in JS
    assert "playerHero.style.setProperty('--s25-hero-photo'" in JS
    assert 's2-hero-club-watermark' in JS
    assert 'rgba(var(--s2-club-rgb)' in CSS


def test_player_list_only_shows_verified_fields():
    assert 'p.primary_position' in JS and 'p.age' in JS and 'p.nationality' in JS
    assert 'p.morale' in JS and 'p.condition' in JS and 'p.act' in JS
    assert 'data-s2-search' in JS and 'data-s2-sort' in JS
    assert 's25-player-card' in JS


def test_sort_and_search_update_list_only_without_reloading_player():
    segment=JS.split('function updateRosterList(resetScroll=false)',1)[1].split('function activateLoadedArt()',1)[0]
    assert 'list.innerHTML=rosterContents(view.data)' in segment
    assert 'view.query=input.value' in segment
    assert 'render()' not in segment
    assert 'document.querySelector(\'.s2-inspector\').innerHTML' not in segment
    assert "if(input.matches('[data-s2-sort]')){view.order=input.value;updateRosterList(true)" in JS


def test_player_card_vs_full_profile_navigation_remain_distinct():
    assert 'data-s2-row=' in JS
    assert 'data-open-career-player="${html(p.id)}"' in JS
    assert 'data-roster-expand="${html(p.id)}"' in JS
    controller=source('frontend/public/squad/squad.js')
    assert "event.target.closest('[data-s2-row]')" in controller
    assert "if(button.hasAttribute('data-open-career-player'))" in controller


def test_previous_profile_features_preserved():
    for code in ('function switchInspectorTab(tab)','function focusPosition(pos)',
                 'function groupedAttributes(p)','data-s2-focus-position=','data-graphics-mode="comparison"'):
        assert code in JS
    assert 'switchInspectorTab(button.dataset.s2Tab)' in JS


def test_accessibility_and_motion():
    assert '@media(prefers-reduced-motion:reduce)' in CSS
    assert 'aria-label="Sort players"' in JS
    assert 'aria-label="Search players"' in JS
    assert 'aria-selected="${selected}"' in JS
    assert 'aria-label="Captain of the current XI"' in JS


def test_no_engine_or_data_migrations():
    assert 'DROP TABLE' not in JS
    assert 'ALTER TABLE' not in JS
    assert (ROOT/'src/football_manager/ui_shell/models.py').exists()
