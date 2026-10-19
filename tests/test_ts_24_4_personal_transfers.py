"""TS-24.4 player consent, contracts and real money/membership settlement."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from datetime import date
from pathlib import Path

import pytest

from football_manager.dev_ui.session import DevelopmentSession
from football_manager.domain.football_world import PlayerSeasonUsage
from football_manager.domain.transfer_negotiation import TransferTerms, TransferBonus
from football_manager.persistence.session_codec import GRAPH_VERSION, capture_manager_graph, restore_manager_graph
from football_manager.services.transfer_negotiation import (
    _create_offer, negotiate, review_transfers, transfer_read_model,
)
from football_manager.services.transfer_personal import _player_interest, agent_demand, career_player_totals


@pytest.fixture(scope='module')
def starting():
    return DevelopmentSession()


def make_agreement(s, player, seller_id, buyer_id, fee=None, terms=None):
    r=s._world_squads
    if terms is None:
        terms=TransferTerms(fee or 100_000)
    deal=_create_offer(r,player.id,seller_id,buyer_id,s.current_date,terms,buyer_id)
    agreed=replace(deal,status='agreed')
    r.transfer_offers[deal.deal_id]=agreed
    return agreed


def cheapest_target(s):
    model=transfer_read_model(s)
    return next(p for p in model['targets'] if 50<p['ovr']<67 and p['value_gbp']<
                model['available_transfer_budget_gbp']*.10 and p['age']>=20)


def offer_at_demand(s,deal):
    r=s._world_squads
    p=r.clubs[deal.seller_id].squad.get(deal.player_id)
    q=agent_demand(r,p,deal.seller_id,deal.buyer_id,s.current_date)
    assert q['interested']
    return {'weekly_wage_gbp':q['weekly_wage_gbp'],'years':q['years'],
            'role':q['role'],'signing_bonus_gbp':0}


def test_v15_market_base_and_readonly_personal_quotes(starting):
    s=deepcopy(starting);r=s._world_squads
    assert GRAPH_VERSION==16
    t=cheapest_target(s);p=r.clubs[t['club_id']].squad.get(t['id'])
    d=make_agreement(s,p,t['club_id'],s.home_club.id,100_000)
    before=deepcopy(r.transfer_offers)
    for _ in range(2):
        quote=transfer_read_model(s)['offers'][0]['personal_quote']
        assert quote['weekly_wage_gbp']>0
    assert r.transfer_offers==before
    r.validate()


def test_purchase_moves_player_money_and_contract_without_repeating(starting):
    s=deepcopy(starting);r=s._world_squads
    t=cheapest_target(s);player=r.clubs[t['club_id']].squad.get(t['id'])
    deal=make_agreement(s,player,t['club_id'],s.home_club.id,100_000)
    before_buyer=r.club_finances[s.home_club.id]
    before_seller=r.club_finances[t['club_id']]
    terms=offer_at_demand(s,deal)
    outcome=negotiate(s,{'action':'personal_offer','deal_id':deal.deal_id,'terms':terms})
    assert outcome['status']=='completed'
    assert not r.clubs[t['club_id']].squad.contains(player.id)
    assert s.home_club.squad.get(player.id) is player
    assert r.contracts[player.id].club_id==s.home_club.id
    assert r.contracts[player.id].weekly_wage_gbp==terms['weekly_wage_gbp']
    assert r.club_finances[s.home_club.id].transfer_budget_gbp==before_buyer.transfer_budget_gbp-100_000
    assert r.club_finances[t['club_id']].transfer_budget_gbp==before_seller.transfer_budget_gbp+100_000
    assert r.transfer_offers[deal.deal_id].personal_status=='completed'
    assert transfer_read_model(s)['offers'][0]['status']=='completed'
    assert len(s.home_lineup.starting_players)==11
    with pytest.raises(ValueError,match='active, agreed'):
        negotiate(s,{'action':'personal_offer','deal_id':deal.deal_id,'terms':terms})
    r.validate()


def test_agent_counter_stores_talk_and_acceptance(starting):
    s=deepcopy(starting);r=s._world_squads
    t=cheapest_target(s);p=r.clubs[t['club_id']].squad.get(t['id'])
    d=make_agreement(s,p,t['club_id'],s.home_club.id,100_000)
    q=offer_at_demand(s,d)
    q['weekly_wage_gbp']=max(75,int(q['weekly_wage_gbp']*.78//25)*25)
    result=negotiate(s,{'action':'personal_offer','deal_id':d.deal_id,'terms':q})
    assert result['status']=='counter'
    counter=r.transfer_offers[d.deal_id]
    assert counter.personal_status=='counter' and len(counter.personal_events)==2
    assert counter.personal_terms.weekly_wage_gbp>=q['weekly_wage_gbp']
    agreed=negotiate(s,{'action':'personal_accept','deal_id':d.deal_id})
    assert agreed['status']=='completed'
    assert r.contracts[p.id].weekly_wage_gbp==counter.personal_terms.weekly_wage_gbp
    r.validate()


def test_hard_sporting_rejection_even_with_money(starting):
    r=starting._world_squads
    strong=next(p for p in starting.home_club.squad.players if p.overall_rating>=78)
    small=next(c for c in r.clubs if r.identities[c].tier==4)
    allowed,reason=_player_interest(r,strong,starting.home_club.id,small,starting.current_date)
    assert not allowed and 'division' in reason.lower()
    s=deepcopy(starting);p=s.home_club.squad.get(strong.id)
    d=make_agreement(s,p,s.home_club.id,small,100_000)
    cash=dict(s._world_squads.club_finances)
    result=negotiate(s,{'action':'personal_resolve','deal_id':d.deal_id})
    assert result['status']=='failed'
    assert s.home_club.squad.contains(p.id)
    assert s._world_squads.club_finances==cash


def test_managed_sale_repairs_lineup_and_morale(starting):
    s=deepcopy(starting);r=s._world_squads
    p=next(p for p in s.home_lineup.starting_players if p.primary_position.value!='GK')
    rich=[cid for cid in r.clubs if cid!=s.home_club.id and r.identities[cid].tier==1
          and r.club_finances[cid].transfer_budget_gbp>200_000]
    buyer=rich[0]
    d=make_agreement(s,p,s.home_club.id,buyer,100_000)
    before=r.club_finances[s.home_club.id].cash_gbp
    result=negotiate(s,{'action':'personal_resolve','deal_id':d.deal_id})
    if result['status']=='completed':
        assert r.clubs[buyer].squad.contains(p.id)
        assert not s.home_club.squad.contains(p.id)
        assert p.id not in {x.id for x in s.home_lineup.selected_players}
        assert p.id not in s.dressing_room.members
        assert r.club_finances[s.home_club.id].cash_gbp>=before
    else:
        assert s.home_club.squad.contains(p.id)
    r.validate()


def test_invalid_personal_wages_and_insufficient_funds_leave_membership(starting):
    s=deepcopy(starting);r=s._world_squads
    t=cheapest_target(s);p=r.clubs[t['club_id']].squad.get(t['id'])
    d=make_agreement(s,p,t['club_id'],s.home_club.id,100_000)
    old=dict(r.club_finances)
    with pytest.raises(ValueError,match='weekly salary|Invalid personal contract terms'):
        negotiate(s,{'action':'personal_offer','deal_id':d.deal_id,'terms':{
            'weekly_wage_gbp':True,'years':3,'role':'star','signing_bonus_gbp':0}})
    q=offer_at_demand(s,d);q['signing_bonus_gbp']=50_000_000
    with pytest.raises(ValueError,match='budget'):
        negotiate(s,{'action':'personal_offer','deal_id':d.deal_id,'terms':q})
    assert r.club_finances==old and r.clubs[t['club_id']].squad.contains(p.id)
    assert r.transfer_offers[d.deal_id].status=='agreed'


def test_persist_completed_deal_and_migration_from_v14(starting):
    s=deepcopy(starting);r=s._world_squads
    t=cheapest_target(s);p=r.clubs[t['club_id']].squad.get(t['id'])
    d=make_agreement(s,p,t['club_id'],s.home_club.id,100_000)
    original=capture_manager_graph(s)
    # Legacy v14 includes the transfer record but none of its new personal fields.
    for node in original['nodes']:
        if node.get('type')=='object' and node.get('class')=='football_manager.domain.transfer_negotiation:TransferNegotiation':
            for key in ('personal_status','personal_terms','personal_events','personal_refusals',
                        'sell_on_paid_gbp','bonus_baseline','bonus_paid','buyer_tier_at_signing'):
                node['fields'].pop(key,None)
    original['version']=14
    legacy=restore_manager_graph(original)
    assert legacy._world_squads.transfer_offers[d.deal_id].personal_status=='not_started'
    legacy._world_squads.validate()
    outcome=negotiate(s,{'action':'personal_offer','deal_id':d.deal_id,'terms':offer_at_demand(s,d)})
    assert outcome['status']=='completed'
    loaded=restore_manager_graph(capture_manager_graph(s))
    assert loaded._world_squads.contracts[p.id].club_id==s.home_club.id
    assert loaded._world_squads.transfer_offers[d.deal_id]==r.transfer_offers[d.deal_id]
    loaded._world_squads.validate()


def test_bonus_pays_only_when_real_threshold_reached_once(starting):
    s=deepcopy(starting);r=s._world_squads
    t=cheapest_target(s);p=r.clubs[t['club_id']].squad.get(t['id'])
    terms=TransferTerms(100_000,(TransferBonus('appearances',10,50_000),))
    d=make_agreement(s,p,t['club_id'],s.home_club.id,terms=terms)
    negotiate(s,{'action':'personal_offer','deal_id':d.deal_id,'terms':offer_at_demand(s,d)})
    before=(r.club_finances[s.home_club.id],r.club_finances[t['club_id']])
    with s._world.transaction():
        review_transfers(s._world,date(2026,9,1))
    assert 'appearances' not in r.transfer_offers[d.deal_id].bonus_paid
    r.usage[p.id]=PlayerSeasonUsage(appearances=10,starts=10,minutes=900)
    with s._world.transaction():
        review_transfers(s._world,date(2026,10,1))
    assert r.transfer_offers[d.deal_id].bonus_paid==('appearances',)
    assert r.club_finances[s.home_club.id].cash_gbp==before[0].cash_gbp-50_000
    again=r.club_finances[s.home_club.id]
    with s._world.transaction():
        review_transfers(s._world,date(2026,11,1))
    assert r.club_finances[s.home_club.id]==again
    r.validate()


def test_frontend_and_api_contracts():
    root=Path(__file__).resolve().parents[1]
    js=(root/'frontend/portable/transfers.js').read_text()
    server=(root/'src/football_manager/ui_shell/server.py').read_text()
    app=(root/'src/football_manager/ui_shell/application.py').read_text()
    assert 'data-tr-personal-accept' in js and 'tr-personal-form' in js
    assert "action:'personal_offer'" in js
    assert "'/api/transfers': 'transfers.command'" in server
    assert "if action == 'transfers.command':" in app


def test_http_actual_player_transfer(starting):
    import json
    from threading import Thread
    from urllib.request import Request,urlopen
    from football_manager.ui_shell.server import create_server
    session=deepcopy(starting)
    t=cheapest_target(session)
    p=session._world_squads.clubs[t['club_id']].squad.get(t['id'])
    d=make_agreement(session,p,t['club_id'],session.home_club.id,100_000)
    server=create_server(port=0,session=session)
    thread=Thread(target=server.serve_forever,daemon=True)
    thread.start();url=f'http://127.0.0.1:{server.server_port}'
    try:
        with urlopen(url+'/api/transfers',timeout=30) as response:
            view=json.load(response)
        offer=view['offers'][0]
        assert offer['personal_quote']['interested']
        quote=offer['personal_quote']
        cmd={'action':'personal_offer','deal_id':d.deal_id,'terms':{
            'weekly_wage_gbp':quote['weekly_wage_gbp'],'years':quote['years'],
            'role':quote['role'],'signing_bonus_gbp':0}}
        req=Request(url+'/api/transfers',data=json.dumps(cmd).encode(),method='POST',
                    headers={'Content-Type':'application/json'})
        with urlopen(req,timeout=30) as response:result=json.load(response)
        assert result['status']=='completed'
        with urlopen(url+'/api/transfers',timeout=30) as response:after=json.load(response)
        assert after['offers'][0]['status']=='completed'
        actual=server.RequestHandlerClass.runtime.session
        assert actual.home_club.squad.contains(t['id'])
        actual._world_squads.validate()
    finally:
        server.shutdown();thread.join(timeout=5);server.server_close()


def test_second_sale_pays_original_seller_sell_on_share(starting):
    from football_manager.services.club_economy import weekly_payroll
    s=deepcopy(starting);r=s._world_squads
    t=cheapest_target(s);p=r.clubs[t['club_id']].squad.get(t['id'])
    first=make_agreement(s,p,t['club_id'],s.home_club.id,
        terms=TransferTerms(100_000,sell_on_type='gross',sell_on_percent=20))
    negotiate(s,{'action':'personal_offer','deal_id':first.deal_id,'terms':offer_at_demand(s,first)})
    buyer=next(cid for cid in sorted(r.clubs) if cid != s.home_club.id
        and r.identities[cid].tier==1 and r.club_finances[cid].transfer_budget_gbp >= 200_000
        and r.club_finances[cid].wage_budget_weekly_gbp-weekly_payroll(r,cid) >=
        agent_demand(r,p,s.home_club.id,cid,s.current_date)['weekly_wage_gbp'])
    second=make_agreement(s,p,s.home_club.id,buyer,200_000)
    old=r.club_finances[t['club_id']].cash_gbp
    result=negotiate(s,{'action':'personal_resolve','deal_id':second.deal_id})
    assert result['status']=='completed'
    assert result['sell_on_paid_gbp']==40_000
    assert r.club_finances[t['club_id']].cash_gbp==old+40_000
    assert r.clubs[buyer].squad.contains(p.id)
    history=transfer_read_model(s)['offers']
    assert {first.deal_id,second.deal_id} <= {item['id'] for item in history}
    r.validate()


def test_completed_player_transfer_survives_sqlite_save(starting,tmp_path):
    from football_manager.persistence import SQLiteSaveRepository
    from football_manager.persistence.manager_career import save_manager_career,load_manager_career
    s=deepcopy(starting);r=s._world_squads
    t=cheapest_target(s);p=r.clubs[t['club_id']].squad.get(t['id'])
    d=make_agreement(s,p,t['club_id'],s.home_club.id,100_000)
    negotiate(s,{'action':'personal_offer','deal_id':d.deal_id,'terms':offer_at_demand(s,d)})
    repo=SQLiteSaveRepository(tmp_path/'player-transfer.sqlite3')
    save_manager_career(repo,slot_id='ts244',display_name='Completed signing',session=s,expected_revision=0)
    loaded=load_manager_career(repo,'ts244').session
    assert loaded.home_club.squad.contains(p.id)
    assert loaded.home_club.squad.get(p.id) is loaded._world_squads.clubs[s.home_club.id].squad.get(p.id)
    assert not loaded._world_squads.clubs[t['club_id']].squad.contains(p.id)
    assert loaded._world_squads.transfer_offers[d.deal_id].status=='completed'
    assert loaded._world_squads.club_finances==r.club_finances
    loaded._world_squads.validate()


def test_sell_on_profit_uses_real_margin_not_gross(starting):
    """The originating club receives its negotiated share of resale profit."""
    from football_manager.services.club_economy import weekly_payroll
    s=deepcopy(starting)
    r=s._world_squads
    t=cheapest_target(s)
    p=r.clubs[t['club_id']].squad.get(t['id'])
    first=make_agreement(s,p,t['club_id'],s.home_club.id,
                         terms=TransferTerms(100_000,sell_on_type='profit',sell_on_percent=20))
    assert negotiate(s,{'action':'personal_offer','deal_id':first.deal_id,
                        'terms':offer_at_demand(s,first)})['status']=='completed'
    buyer=next(cid for cid in sorted(r.clubs) if cid != s.home_club.id
               and r.identities[cid].tier==1
               and r.club_finances[cid].transfer_budget_gbp>=200_000
               and r.club_finances[cid].wage_budget_weekly_gbp-weekly_payroll(r,cid)>=
               agent_demand(r,p,s.home_club.id,cid,s.current_date)['weekly_wage_gbp'])
    second=make_agreement(s,p,s.home_club.id,buyer,200_000)
    original=r.club_finances[t['club_id']].cash_gbp
    result=negotiate(s,{'action':'personal_resolve','deal_id':second.deal_id})
    assert result['status']=='completed'
    assert result['sell_on_paid_gbp']==20_000
    assert r.club_finances[t['club_id']].cash_gbp==original+20_000
    r.validate()
