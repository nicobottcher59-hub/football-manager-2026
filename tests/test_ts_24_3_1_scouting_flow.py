"""TS-24.3.1 - scouting entry, historical club discussions, optional clauses."""
from copy import deepcopy
from pathlib import Path

import pytest

from football_manager.dev_ui.session import DevelopmentSession
from football_manager.services.transfer_negotiation import transfer_read_model, negotiate
from football_manager.persistence.session_codec import GRAPH_VERSION

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def world():
    return DevelopmentSession()


def affordable(world):
    model = transfer_read_model(world)
    return next(p for p in model['targets'] if 20 <= p['age'] <= 29 and
                100_000 < p['value_gbp'] < model['available_transfer_budget_gbp'] * .16)


def test_market_prices_are_per_player_not_one_display_placeholder(world):
    targets = transfer_read_model(world)['targets']
    assert len(targets) > 1900
    assert len({p['value_gbp'] for p in targets}) > 200
    assert len({p['value_gbp'] for p in targets[:80]}) > 20
    assert all(p['value_gbp'] >= 5_000 for p in targets)


def test_real_negotiation_history_is_visible_after_offer(world):
    session = deepcopy(world)
    player = affordable(session)
    answer = negotiate(session, {'action':'submit','seller_id':player['club_id'],
        'player_id':player['id'],'terms':{'fixed_gbp':100_000}})
    view = transfer_read_model(session)
    discussion = next(row for row in view['offers'] if row['id'] == answer['deal_id'])
    assert discussion['events'] == len(discussion['history']) >= 1
    assert discussion['history'][0]['by_manager'] is True
    assert discussion['history'][0]['by_club'] == session.home_club.name
    assert discussion['history'][0]['terms']['fixed_gbp'] == 100_000
    assert discussion['history'][-1]['terms'] == discussion['terms']
    assert all('seller_minimum' not in event for event in discussion['history'])
    assert session._world_squads.clubs[player['club_id']].squad.contains(player['id'])
    assert GRAPH_VERSION == 16


def test_navigation_is_scouting_and_fullscreen_not_transfers_sidebar():
    html = (ROOT/'frontend/portable/index.html').read_text()
    portable = (ROOT/'frontend/portable/portable.js').read_text()
    css = (ROOT/'frontend/portable/transfers.css').read_text()
    assert '<span>Scouting</span>' in html
    assert '<span>Transfers</span>' not in html
    assert "page === 'Scouting' || negotiationPage" in portable
    assert "page==='Negotiation'" in portable
    assert 'tr-negotiation-open' in portable and 'tr-negotiation-open' in css
    assert "parts[0]==='negotiation'" in portable
    assert "parts[1]==='Transfers'?'Scouting'" in portable


def test_club_profile_offer_button_sends_navigation_event():
    roster = (ROOT/'frontend/public/squad/roster.js').read_text()
    squad = (ROOT/'frontend/public/squad/squad.js').read_text()
    portable = (ROOT/'frontend/portable/portable.js').read_text()
    assert 'data-open-transfer-offer' in roster
    assert 'fm-open-transfer-offer' in squad
    assert 'fm-open-transfer-offer' in portable
    assert 'event.source===clubFrame.contentWindow' in portable


def test_optional_bonus_and_clause_presentation_is_empty_by_default():
    js = (ROOT/'frontend/portable/transfers.js').read_text()
    assert 'No performance bonuses selected.' in js
    assert "const bs=t?.bonuses||[]" in js
    assert "bs.map((b,i)=>rowBonus(i,b))" in js
    assert 'data-tr-add-bonus' in js and 'data-tr-remove-bonus' in js
    assert 'data-tr-toggle-sell' in js and 'data-tr-toggle-buy' in js
    assert 'form.reportValidity()' in js
    assert "for(const row of form.querySelectorAll('[data-tr-bonus-row]'))" in js
    assert 'Math.abs(a.value_gbp-model.available_transfer_budget_gbp*.38)' not in js
    assert 'value_gbp<=model.available_transfer_budget_gbp' in js


def test_existing_transfer_economics_and_save_schema_unchanged():
    from football_manager.domain.transfer_negotiation import TransferTerms
    from football_manager.services.transfer_negotiation import assess_terms
    session = DevelopmentSession()
    item = affordable(session)
    player = session._world_squads.clubs[item['club_id']].squad.get(item['id'])
    val = assess_terms(session._world_squads,player,session.home_club.id,
                       TransferTerms(1_000_000),session.current_date)
    assert val['risk_adjusted_gbp'] == val['fixed_gbp'] == val['headline_gbp'] == 1_000_000
    assert GRAPH_VERSION == 16
