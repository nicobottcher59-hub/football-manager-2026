"""Small stdlib-only contracts for the TS-24.2.1 Squad UI hotfix.

The end-to-end browser interactions were exercised separately in Chromium.
These focused tests intentionally have no external or Node requirements.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / 'frontend/public/squad/roster.js'
CSS = ROOT / 'frontend/public/squad/roster.css'


def test_general_squad_shows_contract_next_to_market_value():
    js = JS.read_text(encoding='utf-8')
    assert "['market_value','Market value',110],['contract','Contract',170]" in js
    assert "if(key==='contract')return contractCell(p);" in js
    assert "p.contract_details?.weekly_wage_gbp??null" in js


def test_contract_cell_is_derived_from_registered_details_not_guessed():
    js = JS.read_text(encoding='utf-8')
    assert "const details=p.contract_details;" in js
    assert "if(!details)return empty(p.contract);" in js
    assert 'details.weekly_wage_gbp' in js
    assert 'details.expires_on' in js
    assert "details.status==='out_of_contract_retained'" in js


def test_plus_button_and_detail_toolbar_can_both_close_player():
    js = JS.read_text(encoding='utf-8')
    assert 'class="ts22-more" data-roster-expand=' in js
    assert 'class="rt-detail-close"' in js
    assert 'class="rt-detail-manage"' in js
    assert "state.expanded=state.expanded===button.dataset.rosterExpand?null:button.dataset.rosterExpand" in js
    assert "state.more=false" in js


def test_contract_and_toolbar_have_styles():
    css = CSS.read_text(encoding='utf-8')
    for name in ('rt-contract-cell', 'rt-detail-toolbar', 'rt-detail-close', 'rt-detail-manage'):
        assert '.' + name in css
