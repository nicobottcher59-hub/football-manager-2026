"""TS-24.6 controlled contract/loan/unsigned-player integration regressions."""
from __future__ import annotations
from copy import deepcopy
from dataclasses import replace
from datetime import date
from pathlib import Path

import pytest

from football_manager.dev_ui.session import DevelopmentSession
from football_manager.services.loan_market import (
    _can_loan, loan_command, loan_read_model, active_loan,
    loan_monthly_adjustments, loan_payroll,
)
from football_manager.services.club_economy import review_finances, weekly_payroll, _date_plus_months
from football_manager.persistence.session_codec import GRAPH_VERSION, capture_manager_graph, restore_manager_graph
from football_manager.services.ai_squad_planning import can_spare
from football_manager.ui_shell.application import GameApplication
from football_manager.ui_shell.match import prematch_read_model


@pytest.fixture(scope='module')
def initial():
    return DevelopmentSession()


def loan_candidate(s, *, outgoing=True, months=6, option=None):
    r=s._world_squads
    manager=s.home_club.id
    if outgoing:
        for p in sorted(s.home_club.squad.players,key=lambda p:p.overall_rating):
            for cid in r.clubs:
                if cid==manager:continue
                try:
                    _can_loan(r,p.id,manager,cid,s.current_date,months,50,'rotation',option)
                except ValueError:continue
                return p,manager,cid
    else:
        for cid,c in r.clubs.items():
            if cid==manager:continue
            for p in sorted(c.squad.players,key=lambda p:p.overall_rating):
                try:_can_loan(r,p.id,cid,manager,s.current_date,months,100,'backup',option)
                except ValueError:continue
                return p,cid,manager
    raise AssertionError('No eligible loan in a 92-club world')


def proposal(p,parent,borrower,months=6,share=50,playing='rotation',option=None):
    return {'action':'loan_offer','player_id':p.id,'parent_id':parent,'borrower_id':borrower,
            'months':months,'borrower_wage_percent':share,
            'playing_time':playing,'option_gbp':option}


def test_new_career_has_no_loans_or_free_players(initial):
    r=initial._world_squads
    assert GRAPH_VERSION==17
    assert r.loans=={} and r.free_agents=={} and r.loan_next_id==1
    assert len(r.contracts)>5000
    before=(len(r.contracts),dict(r.club_finances),dict(r.loans))
    a=loan_read_model(initial)
    b=loan_read_model(initial)
    assert a==b and len(a['outgoing'])>=20
    assert before==(len(r.contracts),r.club_finances,r.loans)
    r.validate()


@pytest.mark.parametrize('months', [6,12,24])
def test_loan_duration_contract_identity_and_budget_split(initial,months):
    s=deepcopy(initial); r=s._world_squads
    p,parent,borrower=loan_candidate(s,months=months)
    initial_wages={cid:weekly_payroll(r,cid) for cid in (parent,borrower)}
    contract=r.contracts[p.id]
    result=loan_command(s,proposal(p,parent,borrower,months))
    agreement=r.loans[result['loan_id']]
    assert agreement.ends_on==_date_plus_months(s.current_date,months)
    assert agreement.status=='active'
    assert not r.clubs[parent].squad.contains(p.id)
    assert r.clubs[borrower].squad.get(p.id) is p
    assert r.contracts[p.id] is contract and contract.club_id==parent
    half=round(contract.weekly_wage_gbp*.5)
    assert weekly_payroll(r,parent)==initial_wages[parent]-half
    assert weekly_payroll(r,borrower)==initial_wages[borrower]+half
    overview=loan_read_model(s)['loans'][0]
    assert overview['ends_on']==result['ends_on']
    assert overview['minutes']==0 and overview['target_minutes']==0
    assert len(s.home_lineup.starting_players)==11
    r.validate()


def test_no_double_loans_no_keeper_exploit_and_contract_length(initial):
    s=deepcopy(initial);r=s._world_squads
    p,parent,borrower=loan_candidate(s)
    loan_command(s,proposal(p,parent,borrower))
    with pytest.raises(ValueError,match='already has an active loan'):
        loan_command(s,proposal(p,parent,borrower))
    with pytest.raises(ValueError,match='6, 12 or 24'):
        loan_command(s,proposal(p,parent,borrower,months=18))
    assert r.loan_next_id==2
    others=[p for p in s.home_club.squad.players if p.primary_position.value=='GK']
    keeper=others[0]
    with pytest.raises(ValueError):
        loan_command(s,proposal(keeper,parent,borrower))
    r.validate()


def test_wage_shares_prorate_and_monthly_rolls_back(initial):
    s=deepcopy(initial);r=s._world_squads
    p,parent,borrower=loan_candidate(s)
    loan_command(s,proposal(p,parent,borrower))
    snapshot=(dict(r.club_finances),r.finance_review_on)
    adjustment=loan_monthly_adjustments(r,date(2026,8,21),date(2026,8,31))
    assert adjustment[parent]==-adjustment[borrower]
    with pytest.raises(RuntimeError,match='rollback'):
        with s._world.transaction():
            review_finances(s._world,date(2026,9,1))
            raise RuntimeError('rollback')
    assert snapshot==(r.club_finances,r.finance_review_on)
    with s._world.transaction():
        review_finances(s._world,date(2026,9,1))
    assert r.finance_review_on==date(2026,9,1)
    r.validate()


def test_recall_after_30_days_and_return_identity(initial):
    s=deepcopy(initial);r=s._world_squads
    p,parent,borrower=loan_candidate(s)
    info=loan_command(s,proposal(p,parent,borrower))
    with pytest.raises(ValueError,match='30 days'):
        loan_command(s,{'action':'loan_recall','loan_id':info['loan_id']})
    s.current_date=date(2026,10,5)
    returned=loan_command(s,{'action':'loan_recall','loan_id':info['loan_id']})
    assert returned['status']=='returned'
    assert r.clubs[parent].squad.get(p.id) is p
    assert not r.clubs[borrower].squad.contains(p.id)
    assert r.contracts[p.id].club_id==parent
    assert active_loan(r,p.id) is None
    r.validate()


def test_purchase_option_completes_permanent_transfer(initial):
    s=deepcopy(initial);r=s._world_squads
    p,parent,borrower=loan_candidate(s,outgoing=False)
    start_buyer=r.club_finances[borrower]
    start_seller=r.club_finances[parent]
    from football_manager.services.transfer_negotiation import _seller_target
    fee=max(5_000,round(_seller_target(r,parent,borrower,p,r.contracts[p.id],s.current_date)*.84/5000)*5000)
    info=loan_command(s,proposal(p,parent,borrower,share=100,playing='backup',option=fee))
    with pytest.raises(ValueError,match='final 90 days'):
        loan_command(s,{'action':'loan_buy_option','loan_id':info['loan_id']})
    s.current_date=date(2027,1,15)
    done=loan_command(s,{'action':'loan_buy_option','loan_id':info['loan_id']})
    assert done['status']=='purchased'
    assert r.loans[info['loan_id']].status=='purchased'
    assert r.clubs[borrower].squad.get(p.id) is p
    assert r.contracts[p.id].club_id==borrower
    assert r.club_finances[borrower].transfer_budget_gbp==start_buyer.transfer_budget_gbp-fee
    assert r.club_finances[parent].transfer_budget_gbp==start_seller.transfer_budget_gbp+fee
    assert any(d.status=='completed' and d.player_id==p.id for d in r.transfer_offers.values())
    with pytest.raises(ValueError,match='No exercisable'):
        loan_command(s,{'action':'loan_buy_option','loan_id':info['loan_id']})
    r.validate()


def test_expired_manager_professional_becomes_free_and_can_return(initial):
    s=deepcopy(initial);r=s._world_squads
    cid=s.home_club.id
    p=next(p for p in s.home_club.squad.players if p.primary_position.value!='GK'
           and can_spare(s.home_club,r.identities[cid].primary,p.id))
    old=r.contracts[p.id]
    r.contracts[p.id]=replace(old,expires_on=date(2026,8,31))
    with s._world.transaction():
        review_finances(s._world,date(2026,9,1))
    assert p.id in r.free_agents and p.id not in r.contracts
    assert not s.home_club.squad.contains(p.id)
    reg=r.free_agents[p.id]
    assert reg.player is p and reg.previous_club_id==cid
    # Free agents negotiate their own weekly salary; no transfer fee.
    from football_manager.services.loan_market import _free_demand
    q=_free_demand(r,reg,cid,date(2026,9,1))
    s.current_date=date(2026,9,1)
    wage=q['minimum_weekly_gbp']
    if weekly_payroll(r,cid)+wage > r.club_finances[cid].wage_budget_weekly_gbp:
        account=r.club_finances[cid]
        r.club_finances[cid]=replace(account,wage_budget_weekly_gbp=weekly_payroll(r,cid)+wage+1000)
    result=loan_command(s,{'action':'sign_free_agent','player_id':p.id,
                           'weekly_wage_gbp':wage,'years':2,'role':q['role']})
    assert result['status']=='signed' and s.home_club.squad.get(p.id) is p
    assert p.id not in r.free_agents and r.contracts[p.id].club_id==cid
    r.validate()


def test_migrate_v15_graph_with_explicit_defaults(initial):
    # Legacy version-15 saves have no loan or free-agent graph fields.
    graph=capture_manager_graph(initial)
    graph['version']=15
    changed=0
    for node in graph['nodes']:
        if node.get('type')=='object' and node.get('class')=='football_manager.domain.football_world:FootballWorld':
            for key in ('loan_next_id','loans','free_agents'):
                node['fields'].pop(key)
            changed+=1
    assert changed==1
    restored=restore_manager_graph(graph)
    r=restored._world_squads
    assert r.loans=={} and r.free_agents=={} and r.loan_next_id==1
    r.validate()


def test_frontend_and_endpoint_contracts():
    root=Path(__file__).resolve().parents[1]
    js=(root/'frontend/portable/transfers.js').read_text()
    server=(root/'src/football_manager/ui_shell/server.py').read_text()
    for item in ('6 months','1 year','2 years','Loans & free agents','data-tr-loan-buy','/api/loans'):
        assert item in (js+server)
    assert 'loan_read_model' in server


def test_automatic_six_month_return_and_two_year_loan_ledger(initial):
    for months,ending in ((6,date(2027,3,1)),(24,date(2028,9,1))):
        s=deepcopy(initial);r=s._world_squads
        p,parent,borrower=loan_candidate(s,months=months)
        result=loan_command(s,proposal(p,parent,borrower,months))
        with s._world.transaction():
            review_finances(s._world,ending)
        entry=r.loans[result['loan_id']]
        assert entry.status=='returned' and entry.completed_on==ending
        assert r.clubs[parent].squad.get(p.id) is p
        assert not r.clubs[borrower].squad.contains(p.id)
        assert r.contracts[p.id].club_id==parent
        before=dict(r.loans)
        with s._world.transaction():
            assert review_finances(s._world,ending)==0
        assert r.loans==before
        r.validate()


def test_agent_rejects_absurd_future_option(initial):
    s=deepcopy(initial);r=s._world_squads
    p,parent,borrower=loan_candidate(s,outgoing=False)
    before=dict(r.loans)
    with pytest.raises(ValueError,match='undervalued future purchase option'):
        loan_command(s,proposal(p,parent,borrower,share=100,playing='backup',option=5_000))
    assert r.loans==before


def test_buyback_uses_player_consent_and_full_fee(initial):
    from football_manager.services.transfer_negotiation import _create_offer,negotiate
    from football_manager.domain.transfer_negotiation import TransferTerms
    from football_manager.services.transfer_personal import agent_demand
    from football_manager.services.club_economy import weekly_payroll
    s=deepcopy(initial);r=s._world_squads;m=s.home_club.id
    selected=None
    for p in sorted(s.home_club.squad.players,key=lambda p:p.overall_rating):
        if not can_spare(s.home_club,r.identities[m].primary,p.id):continue
        for cid in r.clubs:
            if cid==m or r.identities[cid].tier!=1:continue
            demand=agent_demand(r,p,m,cid,s.current_date)
            account=r.club_finances[cid]
            if demand['interested'] and weekly_payroll(r,cid)+demand['weekly_wage_gbp']<=account.wage_budget_weekly_gbp and account.transfer_budget_gbp>100_000:
                selected=(p,cid);break
        if selected:break
    assert selected
    p,buyer=selected
    term=TransferTerms(100_000,buyback_gbp=150_000,buyback_until=date(2027,8,1))
    d=_create_offer(r,p.id,m,buyer,s.current_date,term,buyer)
    r.transfer_offers[d.deal_id]=replace(d,status='agreed')
    assert negotiate(s,{'action':'personal_resolve','deal_id':d.deal_id})['status']=='completed'
    assert r.clubs[buyer].squad.contains(p.id)
    result=loan_command(s,{'action':'buyback','deal_id':d.deal_id})
    assert result['status']=='completed' and result['transfer']['fixed_gbp']==150_000
    assert s.home_club.squad.get(p.id) is p
    with pytest.raises(ValueError):
        loan_command(s,{'action':'buyback','deal_id':d.deal_id})
    r.validate()


def test_complete_loan_save_graph_and_sqlite(initial,tmp_path):
    from football_manager.persistence import SQLiteSaveRepository
    from football_manager.persistence.manager_career import save_manager_career,load_manager_career
    s=deepcopy(initial)
    p,parent,borrower=loan_candidate(s,months=24)
    result=loan_command(s,proposal(p,parent,borrower,months=24))
    again=restore_manager_graph(capture_manager_graph(s))
    loan=again._world_squads.loans[result['loan_id']]
    assert loan.ends_on==date(2028,8,21) and loan.status=='active'
    assert again._world_squads.clubs[borrower].squad.get(p.id) is again._world_squads.clubs[borrower].squad._players[p.id]
    assert again._world_squads.contracts[p.id].club_id==parent
    repo=SQLiteSaveRepository(tmp_path/'ts246.sqlite3')
    save_manager_career(repo,slot_id='ts246',display_name='Two-year loan',session=s,expected_revision=0)
    loaded=load_manager_career(repo,'ts246')
    restored=loaded.session._world_squads
    assert restored.loans[result['loan_id']]==s._world_squads.loans[result['loan_id']]
    assert restored.clubs[borrower].squad.contains(p.id)
    assert restored.contracts[p.id].club_id==parent
    restored.validate()


def test_real_http_loan_get_and_post(initial):
    import json
    from urllib.request import Request,urlopen
    from threading import Thread
    from football_manager.ui_shell.server import create_server
    s=deepcopy(initial)
    p,parent,borrower=loan_candidate(s)
    server=create_server(port=0,session=s)
    thread=Thread(target=server.serve_forever,daemon=True)
    thread.start()
    base='http://127.0.0.1:'+str(server.server_port)
    try:
        with urlopen(base+'/api/loans',timeout=30) as response:
            data=json.load(response)
        assert data['manager_club_id']==parent
        cmd=proposal(p,parent,borrower)
        req=Request(base+'/api/loans',method='POST',data=json.dumps(cmd).encode(),
                    headers={'Content-Type':'application/json'})
        with urlopen(req,timeout=30) as response:
            done=json.load(response)
        assert done['status']=='active'
        with urlopen(base+'/api/loans',timeout=30) as response:
            after=json.load(response)
        assert after['loans'][0]['id']==done['loan_id']
        actual=server.RequestHandlerClass.runtime.session
        assert actual._world_squads.clubs[borrower].squad.contains(p.id)
        actual._world_squads.validate()
    finally:
        server.shutdown();thread.join(timeout=5);server.server_close()
