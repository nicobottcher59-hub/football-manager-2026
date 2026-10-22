"""TS-UI-06.02 — dynamic club banner and approved visuals regression."""
from pathlib import Path
from PIL import Image

from football_manager.dev_ui import DevelopmentSession
from football_manager.ui_shell.dressing_room import dressing_room_read_model

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / 'frontend/portable/dressing_room.js'
CSS = ROOT / 'frontend/portable/dressing_room.css'
PORTABLE = ROOT / 'frontend/portable/portable.js'
ASSET = ROOT / 'frontend/portable/assets/dressing-room/locker-room-team-talk.webp'


def test_python_read_model_exposes_club_identity_without_new_saved_fields():
    data=dressing_room_read_model(DevelopmentSession())
    assert data['club_id'] and data['club']
    assert data['source']=='python-dressing-room'
    assert sum(t['count'] for t in data['tiers'])==len(data['members'])


def test_header_uses_live_club_name_crest_and_palette():
    js=JS.read_text()
    assert 'window.FMClubIdentity?.resolve?.(model.club_id,model.club)' in js
    assert 'window.FMClubIdentity?.applyTheme?.(model.club_id,model.club)' in js
    assert '${esc(club.name)} · FIRST TEAM' in js
    assert '${esc(club.crest)}' in js
    assert "${summary('hero')}" in js
    assert '${summary()}' in js
    assert 'model.members.filter(p => p.tier === t.id)' in js
    assert "FMNavigation?.navigate('Inbox'" in js


def test_photo_is_external_and_original_screen_is_not_baked_in():
    assert ASSET.is_file()
    with Image.open(ASSET) as image:
        assert image.format=='WEBP'
        assert image.width>=1200 and image.height>=200
    css=CSS.read_text()
    assert "url('assets/dressing-room/locker-room-team-talk.webp')" in css
    assert 'var(--ui-club-rgb' in css
    assert 'var(--ui-club-highlight-rgb' in css
    assert 'body.tsui-dressing-active' in css
    assert "document.body.classList.toggle('tsui-dressing-active',dressingRoom);" in PORTABLE.read_text()


def test_no_gameplay_changes_or_team_hardcodes():
    js=JS.read_text()
    assert "fetch('/api/dressing-room'" in js
    assert 'method: "POST"' not in js and "method:'POST'" not in js
    for name in ('sunderland','brighton','northbridge'):
        assert name not in (js+CSS.read_text()).lower()
