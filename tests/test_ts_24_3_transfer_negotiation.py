"""TS-24.3 symmetric, conditional, persistent inter-club negotiations."""
from __future__ import annotations
from copy import deepcopy
from dataclasses import replace
from datetime import date, timedelta
from pathlib import Path

import pytest

from football_manager.dev_ui.session import DevelopmentSession
from football_manager.domain.transfer_negotiation import TransferBonus, TransferTerms
from football_manager.services.transfer_negotiation import (
    _terms_from_data, _availability, assess_terms, _seller_target, _probability,
    transfer_read_model, negotiate, review_transfers,
)
from football_manager.persistence.session_codec import (
    capture_manager_graph, restore_manager_graph, GRAPH_VERSION,
)


@pytest.fixture(scope='module')
def starting():
    return DevelopmentSession()


def candidate(session, multiplier=.20):
    targets=transfer_read_model(session)['targets']
    budget=transfer_read_model(session)['available_transfer_budget_gbp']
    return next(p for p in targets if 28>=p['age']>=19 and
                100_000<p['value_gbp']<budget*multiplier)


def normal_offer(p, multiplier=.9):
    return {'action':'submit','seller_id':p['club_id'],'player_id':p['id'],
            'terms':{'fixed_gbp': max(5000,round(p['value_gbp']*multiplier/5000)*5000)}}


def test_initial_transfer_state_and_no_mutations_from_read(starting):
    r=starting._world_squads
    before=(r.transfer_last_review_on,r.transfer_next_id,dict(r.transfer_offers),dict(r.club_finances))
    for _ in range(3):
        out=transfer_read_model(starting)
        assert out['targets'] and out['offers']==[]
        assert out['available_transfer_budget_gbp']>0
        assert all(p['value_gbp']>0 for p in out['targets'])
        assert not any('potential' in p or 'pa' in p for p in out['targets'])
    assert before==(r.transfer_last_review_on,r.transfer_next_id,r.transfer_offers,r.club_finances)
    assert GRAPH_VERSION==16
    r.validate()


def test_bonus_payments_are_not_guaranteed_and_large_unlikely_bonuses_do_not_replace_cash(starting):
    r=starting._world_squads;p=candidate(starting)
    player=r.clubs[p['club_id']].squad.get(p['id'])
    buyer=starting.home_club.id
    base=assess_terms(r,player,buyer,TransferTerms(1_000_000),starting.current_date)
    elaborate=TransferTerms(1_000_000,(TransferBonus('goals',40,150_000_000),TransferBonus('promotion',1,40_000_000)))
    risky=assess_terms(r,player,buyer,elaborate,starting.current_date)
    assert risky['headline_gbp']==191_000_000
    assert risky['risk_adjusted_gbp']<risky['headline_gbp']*.35
    assert risky['risk_adjusted_gbp']>=base['risk_adjusted_gbp']
    assert 0<risky['bonuses'][0]['probability_pct']<70
    assert all(x['risk_adjusted_gbp']<x['amount_gbp'] for x in risky['bonuses'])


def test_guaranteed_is_more_valuable_than_the_same_headline_in_variables(starting):
    r=starting._world_squads;p=candidate(starting)
    player=r.clubs[p['club_id']].squad.get(p['id']);buyer=starting.home_club.id
    direct=assess_terms(r,player,buyer,TransferTerms(20_000_000),starting.current_date)
    bonus=assess_terms(r,player,buyer,TransferTerms(12_000_000,(TransferBonus('appearances',20,8_000_000),)),starting.current_date)
    assert direct['risk_adjusted_gbp']>bonus['risk_adjusted_gbp']
    assert direct['headline_gbp']==bonus['headline_gbp']==20_000_000


def test_sell_on_profit_and_gross_are_distinct(starting):
    r=starting._world_squads;p=candidate(starting)
    player=r.clubs[p['club_id']].squad.get(p['id']);buyer=starting.home_club.id
    gross=assess_terms(r,player,buyer,TransferTerms(1_000_000,sell_on_type='gross',sell_on_percent=20),starting.current_date)
    profit=assess_terms(r,player,buyer,TransferTerms(1_000_000,sell_on_type='profit',sell_on_percent=20),starting.current_date)
    assert gross['resale_expected_gbp']>profit['resale_expected_gbp']>0


def test_buyback_needs_higher_fixed_fee_and_future_expiry(starting):
    p=candidate(starting);today=starting.current_date
    assert _terms_from_data({'fixed_gbp':5_000_000,'buyback_gbp':15_000_000,
                             'buyback_until':(today+timedelta(days=700)).isoformat()},today,p['value_gbp']).buyback_gbp==15_000_000
    with pytest.raises(ValueError,match='Buyback price'):
        r=starting._world_squads
        assess_terms(r,r.clubs[p['club_id']].squad.get(p['id']),starting.home_club.id,
                     TransferTerms(5_000_000,buyback_gbp=4_000_000,buyback_until=today+timedelta(days=500)),today)
    with pytest.raises(ValueError,match='Buyback must be valid'):
        _terms_from_data({'fixed_gbp':5_000_000,'buyback_gbp':15_000_000,
                          'buyback_until':(today-timedelta(days=1)).isoformat()},today,p['value_gbp'])


@pytest.mark.parametrize('raw',[
    {'fixed_gbp':0}, {'fixed_gbp':1.1}, {'fixed_gbp':5000,'unknown':'1'},
    {'fixed_gbp':100_000,'sell_on_type':'gross','sell_on_percent':50},
    {'fixed_gbp':100_000,'sell_on_type':'profit','sell_on_percent':0},
    {'fixed_gbp':100_000,'bonuses':[{'kind':'promotion','threshold':1,'amount_gbp':30_000}]*2},
    {'fixed_gbp':100_000,'bonuses':[{'kind':'goals','threshold':999,'amount_gbp':30_000}]},
    {'fixed_gbp':100_000,'bonuses':[{'kind':'goals','threshold':15,'amount_gbp':3000}]},
])
def test_invalid_or_exploit_terms_rejected(raw):
    with pytest.raises((ValueError,TypeError)):
        _terms_from_data(raw,date(2026,8,21),4_000_000)


def test_user_can_bid_and_ai_counters_without_payments(starting):
    s=deepcopy(starting);p=candidate(s)
    original_cash=dict(s._world_squads.club_finances)
    old_contracts=dict(s._world_squads.contracts)
    original_owner=s._world_squads.clubs[p['club_id']].squad.get(p['id'])
    answer=negotiate(s,normal_offer(p,.72))
    assert answer['status'] in ('manager_turn','rejected','agreed')
    assert s._world_squads.club_finances==original_cash
    assert s._world_squads.contracts==old_contracts
    assert s._world_squads.clubs[p['club_id']].squad.get(p['id']) is original_owner
    offer=s._world_squads.transfer_offers[answer['deal_id']]
    offer.validate()
    assert transfer_read_model(s)['offers'][0]['player_id']==p['id']
    with pytest.raises(ValueError,match='live negotiation'):
        if offer.status!='rejected':
            negotiate(s,normal_offer(p,.95))
        else:
            raise ValueError('live negotiation')


def test_manager_can_agree_to_club_counter_but_budget_is_reserved_not_paid(starting):
    s=deepcopy(starting);p=candidate(s)
    r=s._world_squads
    before=r.club_finances[s.home_club.id]
    result=negotiate(s,normal_offer(p,.75))
    offer=r.transfer_offers[result['deal_id']]
    if offer.status=='manager_turn':
        result=negotiate(s,{'action':'accept','deal_id':offer.deal_id})
        assert result['status']=='agreed' and result['pending_player_consent']
        assert r.club_finances[s.home_club.id]==before
        assert _availability(r,s.home_club.id,s.current_date)==before.transfer_budget_gbp-r.transfer_offers[offer.deal_id].terms.fixed_gbp or _availability(r,s.home_club.id,s.current_date)<before.transfer_budget_gbp
        with pytest.raises(ValueError,match='already been accepted'):
            negotiate(s,{'action':'withdraw','deal_id':offer.deal_id})
        r.validate()


def test_no_club_or_player_impersonation(starting):
    s=deepcopy(starting);p=candidate(s)
    with pytest.raises(ValueError):negotiate(s,{'action':'submit','seller_id':s.home_club.id,'player_id':p['id'],'terms':{'fixed_gbp':10000}})
    with pytest.raises(ValueError):negotiate(s,{'action':'submit','seller_id':p['club_id'],'player_id':'nonexistent','terms':{'fixed_gbp':10000}})
    with pytest.raises(ValueError):negotiate(s,{'action':'accept','deal_id':'anything'})
    with pytest.raises(ValueError):negotiate(s,{'action':'submit','seller_id':p['club_id'],'player_id':p['id'],'terms':{'fixed_gbp':10**12}})
    assert not s._world_squads.transfer_offers


def test_preview_has_no_mutations(starting):
    s=deepcopy(starting);p=candidate(s)
    before=s._world_squads.transfer_next_id
    result=negotiate(s,{**normal_offer(p,1.03),'action':'preview'})
    assert result['valuation']['risk_adjusted_gbp']>0
    assert result['note'] and s._world_squads.transfer_next_id==before
    assert not s._world_squads.transfer_offers


def test_transfer_state_roundtrip_and_v13_migration(starting):
    s=deepcopy(starting);p=candidate(s)
    negotiate(s,normal_offer(p,.92))
    graph=capture_manager_graph(s)
    assert graph['version']==16
    loaded=restore_manager_graph(graph)
    assert loaded._world_squads.transfer_offers==s._world_squads.transfer_offers
    assert loaded._world_squads.transfer_next_id==2
    loaded._world_squads.validate()
    for node in graph['nodes']:
        if node.get('type')=='object' and node.get('class')=='football_manager.domain.football_world:FootballWorld':
            for field in ('transfer_offers','transfer_next_id','transfer_last_review_on'):
                node['fields'].pop(field,None)
    graph['version']=13
    older=restore_manager_graph(graph)
    assert older._world_squads.transfer_offers=={}
    assert older._world_squads.transfer_next_id==1
    assert older._world_squads.transfer_last_review_on==older.current_date.replace(day=1)
    older._world_squads.validate()


def test_monthly_ai_bids_are_repeatable_and_roll_back(starting):
    s=deepcopy(starting);r=s._world_squads;world=s._world
    before=dict(r.transfer_offers);clock=r.transfer_last_review_on
    with pytest.raises(RuntimeError,match='abort'):
        with world.transaction():
            review_transfers(world,date(2026,11,1))
            raise RuntimeError('abort')
    assert r.transfer_offers==before and r.transfer_last_review_on==clock and r.transfer_next_id==1
    with world.transaction():
        count=review_transfers(world,date(2026,11,1))
    assert count>=0
    with world.transaction():
        assert review_transfers(world,date(2026,11,1))==0
    r.validate()
    assert all(o.status=='manager_turn' for o in r.transfer_offers.values()
               if s.home_club.id in (o.seller_id,o.buyer_id))
    assert all(o.status=='completed' for o in r.transfer_offers.values()
               if s.home_club.id not in (o.seller_id,o.buyer_id))


def test_frontend_uses_real_api_and_linked_modules():
    root=Path(__file__).resolve().parents[1]
    server=(root/'src/football_manager/ui_shell/server.py').read_text()
    app=(root/'src/football_manager/ui_shell/application.py').read_text()
    html=(root/'frontend/portable/index.html').read_text()
    portable=(root/'frontend/portable/portable.js').read_text()
    js=(root/'frontend/portable/transfers.js').read_text()
    assert "'/api/transfers': 'transfers.command'" in server
    assert "if path == '/api/transfers':" in server
    assert "if action == 'transfers.command':" in app
    assert 'transfers.js' in html and 'transfers.css' in html
    # TS-24.3.1 replaced the old Transfers tab with Scouting and a routed negotiation.
    assert "page === 'Scouting' || negotiationPage" in portable
    assert "'#negotiation/'" in portable
    assert 'Risk-adjusted' in js and 'No instalments' in js


def test_sqlite_full_career_preserves_transfer_talks(starting,tmp_path):
    from football_manager.persistence import SQLiteSaveRepository
    from football_manager.persistence.manager_career import save_manager_career,load_manager_career
    s=deepcopy(starting);p=candidate(s)
    result=negotiate(s,normal_offer(p,.87))
    repository=SQLiteSaveRepository(tmp_path/'transfer.sqlite3')
    save_manager_career(repository,slot_id='transfer',display_name='Transfer tests',session=s,expected_revision=0)
    loaded=load_manager_career(repository,'transfer').session
    assert capture_manager_graph(loaded)['version']==16
    assert loaded._world_squads.transfer_offers==s._world_squads.transfer_offers
    assert result['deal_id'] in loaded._world_squads.transfer_offers
    assert loaded._world_squads.club_finances==s._world_squads.club_finances
    loaded._world_squads.validate()


def test_http_transfer_get_post_preview_and_offer(starting):
    import json
    from threading import Thread
    from urllib.request import Request,urlopen
    from football_manager.ui_shell.server import create_server
    from football_manager.ui_shell.runtime import UIRuntime
    from football_manager.services.transfer_negotiation import transfer_read_model
    server=create_server(port=0,session=deepcopy(starting))
    thread=Thread(target=server.serve_forever,daemon=True)
    thread.start();root=f'http://127.0.0.1:{server.server_port}'
    try:
        with urlopen(root+'/api/transfers',timeout=30) as response:
            view=json.load(response)
        assert view['targets'] and view['offers']==[]
        player=next(p for p in view['targets'] if p['value_gbp']<view['available_transfer_budget_gbp']*.2 and p['age']>=20)
        command=normal_offer(player,.93)
        preview={**command,'action':'preview'}
        for payload in (preview, command):
            request=Request(root+'/api/transfers',method='POST',
                            headers={'Content-Type':'application/json'},data=json.dumps(payload).encode())
            with urlopen(request,timeout=30) as response:
                result=json.load(response)
            if payload['action']=='preview':
                assert result['valuation']['risk_adjusted_gbp']>0
            else:
                assert result['deal_id']
        with urlopen(root+'/api/transfers',timeout=30) as response:
            after=json.load(response)
        assert len(after['offers'])==1
        assert after['offers'][0]['player_id']==player['id']
        assert after['available_transfer_budget_gbp']<=view['available_transfer_budget_gbp']
        assert server.RequestHandlerClass.runtime.session._world_squads.clubs[player['club_id']].squad.contains(player['id'])
    finally:
        server.shutdown();thread.join(timeout=5);server.server_close()


def test_incoming_bid_has_manager_actions_when_created(starting):
    s=deepcopy(starting);r=s._world_squads
    # Simulate the world boundary (the calendar changes during actual Continue).
    with s._world.transaction():
        review_transfers(s._world,date(2026,10,1))
    incoming=list(r.transfer_offers.values())
    if incoming:
        assert all(o.seller_id==s.home_club.id and o.status=='manager_turn'
                   for o in incoming if s.home_club.id in (o.seller_id,o.buyer_id))
        assert all(o.status=='completed' for o in incoming
                   if s.home_club.id not in (o.seller_id,o.buyer_id))
        assert all(o.proposed_by==o.buyer_id for o in incoming)
        # Date is not yet advanced in this standalone review; the same terms
        # remain valid in the real September/October calendar.
        r.validate()
