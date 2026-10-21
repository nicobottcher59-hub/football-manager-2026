"""TS-UI-02.13: visual punch restricted to approved Squad 01C / 01D."""
from pathlib import Path
import hashlib

ROOT = Path(__file__).resolve().parents[1]
SQUAD = ROOT / 'frontend/public/squad'
JS = (SQUAD / 'squad_ui02.js').read_text(encoding='utf-8')
CSS = (SQUAD / 'squad_ui029.css').read_text(encoding='utf-8')
PRESENT = (SQUAD / 'presentation.js').read_text(encoding='utf-8')
HTML = (SQUAD / 'embed.html').read_text(encoding='utf-8')
STATUS = JS.split('function statusTab(p,data){', 1)[1].split('function contractDaysRemaining(', 1)[0]
CONTRACT = JS.split('function contractTab(p,data){', 1)[1].split('function inspector(p,data){', 1)[0]
COMPACT = PRESENT.split('function developmentPanelCompact(d,readonly){', 1)[1].split('async function hydrate(', 1)[0]


def test_approved_season_and_profile_remain_untouched():
    season = JS.split('function seasonTab(p,data){', 1)[1].split('function statusTab(p,data){', 1)[0].split('// TS-UI-02.12', 1)[0]
    # TS-UI-02.14 explicitly supersedes the earlier season-layout freeze.
    # Keep the original checksum requirement for the older versions.
    if 's214-season-dashboard' in season:
        assert 's214-kpi-grid' in season
        assert 's214-season-groups' in season
        assert 'supported=new Set(opt.supported||[])' in season
    else:
        assert hashlib.sha256(season.encode('utf-8')).hexdigest() == 'c1a79a16e000c51a5bc008a22c5353a7d379b84e0c5cf44999e41086398c98d0' 
    assert 'function playerHeader(p,data)' in JS
    assert 'function rosterRow(p,data)' in JS
    assert 'squad_ui0213.css' not in HTML


def test_status_facts_real_and_visually_distinct():
    for attr in ('p.condition', 'p.sharpness', 'p.fatigue', 'p.form', 'p.morale', 'p.injury', 'p.suspension', 'p.available'):
        assert attr in STATUS
    for cls in ('s213-status-dashboard', 's213-performance-tile', 's213-morale-meter', 's213-development-card'):
        assert cls in STATUS
    assert 'data-graphics-mode="development"' in STATUS
    assert 'moodGraphic' in STATUS and 'moodMouth' in STATUS
    assert 'Last 5 matches' not in STATUS


def test_development_visual_is_explicitly_not_fake_history():
    assert 'Array.isArray(d.history)?d.history:[]' in COMPACT
    assert 'history.length>=2' in COMPACT
    assert 's213-review-graphic' in COMPACT
    assert 'First review pending' in COMPACT
    assert 'Reference OVR · not potential' in COMPACT
    assert 'd.potential' not in COMPACT
    assert 'data-development-focus' in COMPACT
    assert "readonly?'disabled':''" in COMPACT
    assert "fetch('/api/development/focus'" in PRESENT


def test_contract_summary_uses_existing_recorded_values_only():
    for source in ('c.weekly_wage', 'c.expires_on', 'p.market_value', 'p.number', 'c.status', 'data.date'):
        assert source in CONTRACT
    assert 'contractDaysRemaining(c.expires_on,data.date)' in CONTRACT
    assert 's213-contract-finances' in CONTRACT
    assert 's213-contract-seal' in CONTRACT
    assert 'Unsupported clauses and bonuses are not invented.' in CONTRACT
    assert 'CLUB RECORD · READ ONLY' in CONTRACT
    assert 'contract percentage' not in CONTRACT.lower()


def test_existing_actions_and_writes_are_preserved():
    for action in ('rt-player-number', 'rt-transfer-status', 'data-open-finances', 'Dressing Room', 'Training', 'Tactics', 'Medical Centre', 'data-open-transfer-offer'):
        assert action in CONTRACT
    assert 's213-quick-actions' in CONTRACT
    assert 'data-development-status' in COMPACT
    assert "action:'squad_number'" in JS
    assert "action:'transfer_status'" in JS


def test_no_hardcoded_club_and_reduced_motion_supported():
    new_css = CSS.split('/* TS-UI-02.13 —', 1)[1]
    assert 'var(--s2-club-accent)' in new_css
    assert 'var(--s2-club-rgb)' in new_css
    assert 'sunderland' not in new_css.lower()
    assert 'brighton' not in new_css.lower()
    assert '@media(prefers-reduced-motion:reduce)' in new_css
    assert '@keyframes s213-tile-in' in new_css
    assert '@media(max-width:730px)' in new_css
    assert '.s213-action-label' in new_css


def test_old_stylesheet_still_loaded_without_adding_competing_layer():
    assert HTML.count('squad_ui029.css') == 1
    assert 'squad_ui0213.css' not in HTML
    assert 'TS-UI-02.13' in CSS
    assert 'TS-UI-02.12' in CSS
