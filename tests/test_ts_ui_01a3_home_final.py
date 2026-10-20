"""TS-UI-01A.3: scalable club palette, compact competition icons and fixed Home heights."""
from pathlib import Path

from PIL import Image

FRONT=Path(__file__).resolve().parents[1]/'frontend'/'portable'


def test_palette_is_club_id_based_and_theme_is_loaded():
    html=(FRONT/'index.html').read_text(encoding='utf-8')
    assert html.count('club_theme.css') == 1
    assert 'club_identity.js' in html
    js=(FRONT/'club_identity.js').read_text(encoding='utf-8')
    assert 'applyTheme' in js and 'theme(id,name)' in js
    assert 'data/club-identities.json' in js
    assert 'Sunderland' not in js
    assert 'safeColor' in js
    css=(FRONT/'club_theme.css').read_text(encoding='utf-8')
    assert '--ui-club-rgb' in css and '.nav-item.is-active' in css
    assert '.tsui-hero' in css
    assert '--ci-accent:' not in css, 'Club palette must not override competition palette'


def test_competition_icons_use_uploaded_art_and_tab_colours():
    branding=(FRONT/'competition_branding.js').read_text(encoding='utf-8')
    styles=(FRONT/'competition_branding.css').read_text(encoding='utf-8')
    for filename in ('premier-league-icon.png','fa-cup-icon.png','champions-league-icon.png'):
        asset=FRONT/'assets'/'competitions'/filename
        assert asset.stat().st_size > 1000
        with Image.open(asset) as icon:
            assert icon.size == (160,160)
            assert icon.getchannel('A').getextrema()==(0,255)
        assert filename in branding
    assert "'carabao-cup'" in branding
    assert 'var(--ci-rgb)' in styles
    assert '.selected' in styles
    assert 'ci-fixture-logo' in styles
    assert 'ci-selector-logo' in styles


def test_inbox_does_not_control_card_height():
    css=(FRONT/'ui_home.css').read_text(encoding='utf-8')
    script=(FRONT/'ui_home.js').read_text(encoding='utf-8')
    assert '.tsui-home-widgets>.tsui-home-card' in css
    assert 'height:clamp(' in css
    assert '.tsui-inbox-card .tsui-updates' in css
    assert 'overflow-y:auto' in css
    assert 'tabindex="0"' in script
    assert 'previousActivity!==state.activity' in script
    assert script.count('tsui-home-card tsui-') == 4
