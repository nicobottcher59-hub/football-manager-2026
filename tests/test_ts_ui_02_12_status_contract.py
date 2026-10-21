"""TS-UI-02.12: redesign only status/development and contract/actions.

Guard the canonical data flows, valid actions, and untouched approved tabs.
"""
from pathlib import Path
import hashlib

ROOT = Path(__file__).resolve().parents[1]
SQUAD = ROOT / 'frontend/public/squad'
JS = (SQUAD / 'squad_ui02.js').read_text(encoding='utf-8')
PRESENTATION = (SQUAD / 'presentation.js').read_text(encoding='utf-8')
CSS = (SQUAD / 'squad_ui029.css').read_text(encoding='utf-8')
HTML = (SQUAD / 'embed.html').read_text(encoding='utf-8')
STATUS = JS.split('function statusTab(p,data){', 1)[1].split('function contractDaysRemaining', 1)[0]
CONTRACT = JS.split('function contractTab(p,data){', 1)[1].split('function inspector(p,data){', 1)[0]
COMPACT = PRESENTATION.split('function developmentPanelCompact(d,readonly){', 1)[1].split('async function hydrate(', 1)[0]


def test_season_stats_markup_is_byte_identical_to_approved_0211():
    # Frozen source checksum from TS-UI-02.11; no absolute paths or prior ZIP
    # required when the user runs this test inside their own repository.
    season = JS.split('function seasonTab(p,data){', 1)[1].split('function statusTab(p,data){', 1)[0].split('// TS-UI-02.12', 1)[0]
    # TS-UI-02.14 explicitly supersedes the earlier season-layout freeze.
    # Keep the original checksum requirement for the older versions.
    if 's214-season-dashboard' in season:
        assert 's214-kpi-grid' in season
        assert 's214-season-groups' in season
        assert 'supported=new Set(opt.supported||[])' in season
    else:
        assert hashlib.sha256(season.encode('utf-8')).hexdigest() == 'c1a79a16e000c51a5bc008a22c5353a7d379b84e0c5cf44999e41086398c98d0' 


def test_no_extra_css_layer_or_changes_to_player_hero():
    assert 'squad_ui0212.css' not in HTML
    assert HTML.index('squad_ui028.css') < HTML.index('squad_ui029.css')
    assert 's212-status-dashboard' in STATUS
    assert 's212-management' in CONTRACT
    assert 'TS-UI-02.12' in CSS
    assert 'function playerHeader(p,data)' in JS


def test_status_cards_come_from_python_state():
    for field in ('p.condition', 'p.sharpness', 'p.fatigue', 'p.form', 'p.morale', 'p.happiness', 'p.available', 'p.injury', 'p.suspension'):
        assert field in STATUS
    assert 's212-ring' in STATUS
    assert 's212-form-progress' in STATUS
    assert 's212-morale-content' in STATUS
    assert 'data-player-graphics=' in STATUS
    assert 'data-graphics-mode="development"' in STATUS
    assert 'Last 5 matches' not in STATUS


def test_development_comparison_only_uses_actual_history():
    assert 'mode===\'development\'?developmentPanelCompact' in PRESENTATION
    assert 'Array.isArray(d.history)?d.history:[]' in COMPACT
    assert 'history.length>=2' in COMPACT
    assert 'reference_ovr' in COMPACT
    assert 'd.reference_ovr_delta' in COMPACT
    assert 'd.period_minutes' in COMPACT
    assert 'd.tracking_since' in COMPACT and 'd.next_review' in COMPACT
    assert 'Reference OVR · not potential' in COMPACT
    assert 'd.potential' not in COMPACT
    assert 'Exact potential' not in COMPACT
    assert 'No completed review' not in COMPACT  # actual pending state is explicit


def test_training_focus_still_posts_to_python_and_can_be_read_only():
    assert 'data-development-focus' in COMPACT
    assert "readonly?'disabled':''" in COMPACT
    assert 'data-development-status' in COMPACT
    assert "fetch('/api/development/focus'" in PRESENTATION
    assert 'answer.effective_review' in PRESENTATION
    assert 'focus.value=g.evolution.focus' in PRESENTATION


def test_contract_displays_only_recorded_data_and_actual_expiry():
    for field in ('c.weekly_wage','c.expires_on','p.market_value','p.number','c.status','data.date'):
        assert field in CONTRACT
    assert 'contractDaysRemaining(c.expires_on,data.date)' in CONTRACT
    assert 'Contract end date passed' in JS
    assert 'Unsupported clauses and bonuses are not invented.' in CONTRACT
    assert 'estimated percentage' not in CONTRACT


def test_all_existing_managed_actions_retained():
    for name in ('rt-player-number','rt-transfer-status','data-open-finances',
                 'Dressing Room','Training','Tactics','Medical Centre'):
        assert name in CONTRACT
    assert 'data-open-transfer-offer' in CONTRACT
    assert "data.readonly?" in CONTRACT
    assert "action:'squad_number'" in JS
    assert "action:'transfer_status'" in JS
    assert 'data-loan-status' not in CONTRACT


def test_animations_scoped_to_new_tabs_respect_reduced_motion():
    assert '@keyframes s212-reveal' in CSS
    assert '@keyframes s212-fill' in CSS
    assert '@media(prefers-reduced-motion:reduce)' in CSS
    assert 'transition:none!important' in CSS
    assert '.s212-status-dashboard' in CSS and '.s212-management' in CSS
    assert '.s212-trend' in CSS
    assert '.s212-quick-actions' in CSS


def test_layout_scales_to_narrow_inspector():
    for breakpoint in ('@media(max-width:1500px)', '@media(max-width:1250px)',
                       '@media(max-width:1000px)', '@media(max-width:730px)'):
        assert breakpoint in CSS
    assert 'grid-template-columns:1fr' in CSS
    assert 'min-width:0' in CSS
    assert 's212-contract-grid' in CSS


def test_select_player_and_tab_switches_still_keep_directory_and_header():
    switch=JS.split('function switchInspectorTab(tab)',1)[1].split('function focusPosition(pos)',1)[0]
    assert 'panel.innerHTML=' in switch and 'tablist.querySelectorAll' in switch
    assert 'current.replaceWith' not in switch
    assert 'panel.scrollTop=0' in switch
    assert 'window.FMPlayerPresentation?.hydrate' in switch
