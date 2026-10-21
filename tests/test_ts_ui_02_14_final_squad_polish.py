"""TS-UI-02.14: signed-off Squad tabs: symmetrical stats, real training areas,
custom dark transfer controls and restored contract spacing. No gameplay edits.
"""
from pathlib import Path
import hashlib

BASE=Path(__file__).resolve().parents[1]
UI=BASE/'frontend/public/squad'
JS=(UI/'squad_ui02.js').read_text(encoding='utf-8')
PRESENT=(UI/'presentation.js').read_text(encoding='utf-8')
CSS=(UI/'squad_ui029.css').read_text(encoding='utf-8')
EMBED=(UI/'embed.html').read_text(encoding='utf-8')
SEASON=JS.split('function seasonTab(p,data){',1)[1].split('// TS-UI-02.12:',1)[0]
STATUS=JS.split('function statusTab(p,data){',1)[1].split('function contractDaysRemaining(',1)[0]
MANAGEMENT=JS.split('function contractTab(p,data){',1)[1].split('function inspector(p,data){',1)[0]
FOCUS=PRESENT.split('function areaSnapshot(player, focus){',1)[1].split('async function hydrate(',1)[0]


def test_season_dashboard_has_six_equal_kpis_and_three_equal_groups():
    assert 's214-season-dashboard' in SEASON
    assert 's214-kpi-grid' in SEASON and 's214-season-groups' in SEASON
    for key in ('appearances','starts','minutes','goals','assists','average_match_rating'):
        assert key in SEASON
    assert "section('Shooting'" in SEASON
    assert "section('Passing'" in SEASON
    assert "section('Defence & discipline'" in SEASON
    assert 'grid-template-columns:repeat(6,minmax(0,1fr))' in CSS
    assert 'grid-template-columns:repeat(3,minmax(0,1fr))' in CSS


def test_no_fabricated_season_statistics_or_history():
    assert "supported=new Set(opt.supported||[])" in SEASON
    assert "if(!supported.has(key)||!numeric(stats[key]))return '—'" in SEASON
    assert 'stats=p.season_stats||{}' in SEASON
    for field in ('coverage.complete_season','coverage.recorded_appearances','coverage.from','opt.clean_sheet_definition'):
        assert field in SEASON
    assert 'data-s2-season' in SEASON and 'data-s2-competition' in SEASON
    assert 'Trend' not in SEASON and 'key_passes' not in SEASON


def test_training_bars_reflect_recorded_skills_not_projected_growth():
    assert 'source=player?.attributes||{}' in FOCUS
    assert "mean('technical',['finishing'" in FOCUS
    assert "mean('technical',['tackling'" in FOCUS
    assert "mean('physical')" in FOCUS
    assert "mean('mental')" in FOCUS
    assert "mean('goalkeeping')" in FOCUS
    assert 'Current abilities' in FOCUS
    assert 'not growth' in FOCUS
    assert 's214-training-areas' in FOCUS
    assert 's214-training-areas' in CSS
    assert "d.focus" in FOCUS
    assert 'data-development-focus' in FOCUS
    assert "fetch('/api/development/focus'" in PRESENT
    assert 'd.potential' not in FOCUS


def test_dark_custom_picker_keeps_existing_write_commands():
    assert 'function managerPicker(id,label,options,current)' in JS
    assert 'data-s214-picker-toggle' in JS
    assert 'data-s214-picker-option' in JS
    assert 'role="listbox"' in JS
    assert 'closeManagerPickers()' in JS
    assert "new Event('change',{bubbles:true})" in JS
    assert "action:'transfer_status'" in JS
    assert "action:'squad_number'" in JS
    assert "managerPicker('rt-player-number'" in MANAGEMENT
    assert "managerPicker('rt-transfer-status'" in MANAGEMENT
    assert 'data-open-finances' in MANAGEMENT
    assert 'data-s2-navigate="Tactics"' in MANAGEMENT
    assert '.s214-picker-menu[hidden]' in CSS
    assert '.s214-drop-up .s214-picker-menu' in CSS
    assert 'background:#092236' in CSS


def test_club_independent_and_responsive_without_adding_stylesheets():
    css=CSS.split('TS-UI-02.14',1)[1]
    assert 'sunderland' not in css.lower()
    assert 'brighton' not in css.lower()
    assert 'var(--s2-club-accent)' in css
    assert 'rgba(var(--s2-club-rgb)' in css
    assert '@media(max-width:730px)' in css
    assert '@media(prefers-reduced-motion:reduce)' in css
    assert 'squad_ui0214.css' not in EMBED
    assert EMBED.count('squad_ui029.css')==1


def test_approved_roster_hero_and_profile_are_byte_identical_to_0213():
    # Frozen baselines from TS-UI-02.13; no other ZIP is needed by the user.
    blocks=[
        ('function rosterRow(p,data){','function rosterContents(data){',
         'f706c3bb9a6192aac1275c20a02f982e2b9720d838663b4d814241b7983b2394'),
        ('function playerHeader(p,data){','const pitchPoints=',
         'fed85f041c97510ecacd906fef3dfae1452ac8e212d71312b980c3a038701bf0'),
        ('function profileTab(p,data){','// TS-UI-02.14:',
         '40fac17f3b3d3c7bf008c6b24a80367ad340c50504511ec6fb13f4ad9814d706'),
    ]
    for begin,end,checksum in blocks:
        block=JS.split(begin,1)[1].split(end,1)[0]
        assert hashlib.sha256(block.encode('utf-8')).hexdigest()==checksum
