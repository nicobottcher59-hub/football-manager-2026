"""TS-24.2 salary/contract and real monthly club-ledger assertions."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from datetime import date, timedelta
from pathlib import Path

import pytest

from football_manager.dev_ui.session import DevelopmentSession
from football_manager.domain.club_economy import PlayerContract, WagePeriod
from football_manager.persistence.session_codec import GRAPH_VERSION, capture_manager_graph, restore_manager_graph
from football_manager.persistence.manager_career import validate_manager_session
from football_manager.services.club_economy import (
    WAGE_ANCHORS, _wage_base, _month_wage, _date_plus_months, _role_for_rank,
    initialize_finances, sync_financial_rosters, quote_renewal, renew_contract,
    finances_read_model, weekly_payroll, auto_renew_ai_contracts,
)
from football_manager.services.player_development import advance_world_development
from football_manager.services.youth_academy import youth_command
from football_manager.ui_shell.models import squad_read_model
from football_manager.ui_shell.world_squads import club_squad_read_model
from football_manager.ui_shell.club_profiles import club_profile_read_model


@pytest.fixture(scope='module')
def starting():
    return DevelopmentSession()


@pytest.mark.parametrize('ovr,wage', WAGE_ANCHORS)
def test_reference_salary_band(ovr,wage):
    assert _wage_base(ovr)==pytest.approx(wage)


def test_wages_progress_non_linearly():
    assert all(_wage_base(v)<_wage_base(v+1) for v in range(36,98))
    assert _wage_base(85)-_wage_base(80)>_wage_base(65)-_wage_base(60)


def test_all_clubs_pro_and_youth_registered_once(starting):
    r=starting._world_squads
    assert len(r.clubs)==92 and len(r.club_finances)==92
    pro=sum(len(c.squad) for c in r.clubs.values())
    youth=sum(len(a.u17)+len(a.u21) for a in r.youth.academies.values())
    assert len(r.contracts)==pro+youth
    assert len(r.contracts)==len(set(r.contracts))
    assert all(x.weekly_wage_gbp>0 for x in r.contracts.values())
    assert r.finance_review_on.day==1 and r.finance_started_on<=starting.current_date
    for cid,account in r.club_finances.items():
        account.validate()
        assert weekly_payroll(r,cid)<=account.wage_budget_weekly_gbp
        assert account.transfer_budget_gbp<=account.cash_gbp
        assert account.recurring_income_gbp>0
    r.validate()


def test_weekly_wages_not_linked_to_temporary_condition_or_ovr(starting):
    s=deepcopy(starting);r=s._world_squads
    p=s.home_club.squad.players[0];old=r.contracts[p.id]
    p.state.fitness=40;p.state.fatigue=75
    assert r.contracts[p.id] is old and r.contracts[p.id].weekly_wage_gbp==old.weekly_wage_gbp
    assert 'minimum_weekly_gbp' in quote_renewal(r,p,old,s.current_date,2)
    assert r.contracts[p.id] is old


def test_pure_read_model_no_hidden_cash_mutations(starting):
    s=deepcopy(starting);r=s._world_squads
    balances=dict(r.club_finances);terms=dict(r.contracts)
    view=finances_read_model(s)
    assert view['managed'] and view['weekly_payroll_gbp']<=view['wage_budget_weekly_gbp']
    assert view['contracts'] and all(c['weekly_wage_gbp'] for c in view['contracts'])
    assert not view['history']
    assert all(p['contract'] and p['contract_details']['weekly_wage_gbp']>0 for p in squad_read_model(s)['roster'])
    other=next(cid for cid in r.clubs if cid!=s.home_club.id)
    assert all(row['contract'] for row in club_profile_read_model(s,other)['roster'])
    assert all(row['contract_details'] for row in club_squad_read_model(s,other)['players'])
    assert r.club_finances==balances and r.contracts==terms


def test_successful_renewal_changes_only_signed_contract(starting):
    s=deepcopy(starting);r=s._world_squads
    row=next(c for c in finances_read_model(s)['contracts'] if c['renewal'] and c['renewal']['minimum_weekly_gbp']>c['weekly_wage_gbp'])
    pid=row['player_id'];old=r.contracts[pid]
    before_attributes=s.home_club.squad.get(pid).attributes
    before_potential=s.home_club.squad.get(pid).development.potential
    quote=quote_renewal(r,s.home_club.squad.get(pid),old,s.current_date,2)
    original_cash=r.club_finances[s.home_club.id].cash_gbp
    result=renew_contract(s,{'action':'renew','player_id':pid,'weekly_wage_gbp':quote['minimum_weekly_gbp'],'years':2})
    new=r.contracts[pid]
    assert result['renewed'] and new.player_id==pid and new.weekly_wage_gbp==quote['minimum_weekly_gbp']
    assert new.expires_on==_date_plus_months(s.current_date,24) and new.renewed_on==s.current_date
    assert new.history[-1].weekly_gbp==old.weekly_wage_gbp
    assert r.club_finances[s.home_club.id].cash_gbp==original_cash
    assert s.home_club.squad.get(pid).attributes==before_attributes
    assert s.home_club.squad.get(pid).development.potential==before_potential
    r.validate()
    with pytest.raises(ValueError,match='recently'):
        renew_contract(s,{'player_id':pid,'weekly_wage_gbp':quote['minimum_weekly_gbp'],'years':2})


def test_underbid_and_unaffordable_renewals_rejected_without_mutation(starting):
    s=deepcopy(starting);r=s._world_squads
    row=next(c for c in finances_read_model(s)['contracts'] if c['renewal'])
    current=r.contracts[row['player_id']]
    offer=row['renewal']['minimum_weekly_gbp']
    with pytest.raises(ValueError,match='below the current expectation'):
        renew_contract(s,{'player_id':row['player_id'],'weekly_wage_gbp':offer-100,'years':2})
    account=r.club_finances[s.home_club.id]
    r.club_finances[s.home_club.id]=replace(account,wage_budget_weekly_gbp=weekly_payroll(r,s.home_club.id))
    with pytest.raises(ValueError,match='board wage budget'):
        renew_contract(s,{'player_id':row['player_id'],'weekly_wage_gbp':max(offer,current.weekly_wage_gbp+100),'years':2})
    assert r.contracts[row['player_id']]==current


def test_no_unauthorized_renewals_and_invalid_types(starting):
    s=deepcopy(starting);p=s.home_club.squad.players[0]
    with pytest.raises(ValueError):renew_contract(s,{'player_id':p.id,'years':2,'weekly_wage_gbp':float('nan')})
    with pytest.raises(ValueError):renew_contract(s,{'player_id':'missing','years':2,'weekly_wage_gbp':1000})
    other=next(c for c in s._world_squads.clubs.values() if c.id!=s.home_club.id)
    with pytest.raises(ValueError,match='not in your'):
        renew_contract(s,{'player_id':other.squad.players[0].id,'weekly_wage_gbp':10000,'years':2})
    with pytest.raises(ValueError,match='duration'):
        renew_contract(s,{'player_id':p.id,'weekly_wage_gbp':100000,'years':8})


def test_month_close_once_and_pro_rated_on_migration_month(starting):
    s=deepcopy(starting);r=s._world_squads;world=s._world
    club_id=s.home_club.id
    before=r.club_finances[club_id]
    first=r.finance_review_on
    next_month=_date_plus_months(first,1)
    # isolate world progression from routine match changes
    advance_world_development(world,next_month)
    after=r.club_finances[club_id]
    assert r.finance_review_on==next_month and len(after.history)==1
    statement=after.history[0]
    assert statement.period_start==first
    assert after.cash_gbp==before.cash_gbp+statement.income_gbp-statement.wages_gbp-statement.operations_gbp
    # Opening half-month is paid only for the days already in the economy.
    assert statement.income_gbp<before.recurring_income_gbp
    assert statement.wages_gbp<round(weekly_payroll(r,club_id)*52/12)
    assert len(r.contracts)>=5000
    advance_world_development(world,next_month)
    assert r.club_finances[club_id]==after
    r.validate()


def test_history_preserves_old_wage_before_renewal():
    c=PlayerContract('p','a',date(2026,8,1),date(2027,8,1),1000,'regular',
        'professional',(WagePeriod(date(2026,8,1),date(2026,8,14),1000),),date(2026,8,15))
    c=replace(c,signed_on=date(2026,8,15),weekly_wage_gbp=3000)
    assert _month_wage(c,date(2026,8,1),date(2026,8,31))==round(1000*14/7)+round(3000*17/7)


def test_monthly_transaction_rolls_back_finances_and_contracts(starting):
    s=deepcopy(starting);r=s._world_squads;world=s._world
    before_money=dict(r.club_finances);before_contracts=dict(r.contracts);clock=r.finance_review_on
    with pytest.raises(RuntimeError,match='rollback marker'):
        with world.transaction():
            from football_manager.services.club_economy import review_finances
            review_finances(world,_date_plus_months(clock,1))
            raise RuntimeError('rollback marker')
    assert r.club_finances==before_money and r.contracts==before_contracts and r.finance_review_on==clock


def test_ai_demand_uses_same_rules_as_manager(starting):
    s=deepcopy(starting);r=s._world_squads;world=s._world
    other=next(cid for cid in r.clubs if cid!=s.home_club.id)
    p=r.clubs[other].squad.players[0];contract=r.contracts[p.id]
    cap=r.club_finances[other]
    # Same demand function for every club; then apply AI renewal at expiry.
    r.contracts[p.id]=replace(contract,expires_on=s.current_date+timedelta(days=12))
    request=quote_renewal(r,p,r.contracts[p.id],s.current_date,2)
    r.club_finances[other]=replace(cap,wage_budget_weekly_gbp=max(cap.wage_budget_weekly_gbp,weekly_payroll(r,other)+request['minimum_weekly_gbp']))
    with world.transaction():
        changed=auto_renew_ai_contracts(world,s.current_date,managed_club_id=s.home_club.id)
    assert changed>=1 and r.contracts[p.id].expires_on>s.current_date+timedelta(days=365)
    own=s.home_club.squad.players[0]
    old=r.contracts[own.id]
    r.contracts[own.id]=replace(old,expires_on=s.current_date+timedelta(days=1))
    with world.transaction():
        auto_renew_ai_contracts(world,s.current_date,managed_club_id=s.home_club.id)
    assert r.contracts[own.id].expires_on==s.current_date+timedelta(days=1)


def test_pro_stipend_upgrades_once_on_promotion(starting):
    s=deepcopy(starting);r=s._world_squads;cid=s.home_club.id
    pid=next(iter(r.youth.academies[cid].u17))
    old=r.contracts[pid]
    assert old.kind=='academy'
    youth_command(s,{'action':'move','player_id':pid,'target':'first'})
    new=r.contracts[pid]
    assert s.home_club.squad.contains(pid) and new.player_id==pid
    assert new.kind=='professional' and new.weekly_wage_gbp>=old.weekly_wage_gbp
    assert sum(1 for c in r.contracts.values() if c.player_id==pid)==1
    r.validate()


def test_expired_deal_visible_and_still_paid_during_interim_retention(starting):
    s=deepcopy(starting);r=s._world_squads
    pid=s.home_club.squad.players[0].id
    old=r.contracts[pid]
    r.contracts[pid]=replace(old,expires_on=date(2026,8,1))
    view=finances_read_model(s)
    row=next(p for p in view['contracts'] if p['player_id']==pid)
    assert row['status']=='out_of_contract_retained'
    assert weekly_payroll(r,s.home_club.id)>=old.weekly_wage_gbp


def test_migration_v12_creates_ledger_without_mutating_original_world(starting):
    graph=capture_manager_graph(starting)
    assert graph['version']==GRAPH_VERSION==17
    before_market=dict(starting._world_squads.market_values)
    # Simulate the v12 schema: all four new fields were absent.
    graph['version']=12
    for n in graph['nodes']:
        if n.get('class')=='football_manager.domain.football_world:FootballWorld':
            for name in ('finance_review_on','finance_started_on','contracts','club_finances'):
                n['fields'].pop(name)
    restored=restore_manager_graph(graph)
    validate_manager_session(restored)
    assert restored._world_squads.market_values==before_market
    assert len(restored._world_squads.contracts)==len(starting._world_squads.contracts)
    assert restored._world_squads.finance_started_on==restored.current_date


def test_frontend_and_api_routes_are_wired():
    root=Path(__file__).resolve().parents[1]
    html=(root/'frontend/portable/index.html').read_text()
    js=(root/'frontend/portable/portable.js').read_text()
    screen=(root/'frontend/portable/finances.js').read_text()
    server=(root/'src/football_manager/ui_shell/server.py').read_text()
    assert 'finances.css' in html and 'finances.js' in html
    assert "page === 'Finances'" in js
    assert '/api/finances' in screen and '/api/finances' in server
    assert 'data-open-finances' in (root/'frontend/public/squad/roster.js').read_text()


def test_sqlite_roundtrip_preserves_contracts_and_accounts(starting,tmp_path):
    from football_manager.persistence import SQLiteSaveRepository
    from football_manager.persistence.manager_career import save_manager_career, load_manager_career
    s=deepcopy(starting)
    row=next(r for r in finances_read_model(s)['contracts'] if r['renewal'] and
             r['renewal']['minimum_weekly_gbp']>r['weekly_wage_gbp'])
    renew_contract(s,{'action':'renew','player_id':row['player_id'],
                      'weekly_wage_gbp':row['renewal']['minimum_weekly_gbp'],'years':2})
    repo=SQLiteSaveRepository(tmp_path/'ts24_2.sqlite3')
    save_manager_career(repo,slot_id='economy',display_name='Contracts',session=s,expected_revision=0)
    loaded=load_manager_career(repo,'economy').session
    assert loaded._world_squads.contracts==s._world_squads.contracts
    assert loaded._world_squads.club_finances==s._world_squads.club_finances
    assert loaded._world_squads.finance_review_on==s._world_squads.finance_review_on
    assert loaded._world_squads.finance_started_on==s._world_squads.finance_started_on
    assert capture_manager_graph(loaded)['version']==17
    validate_manager_session(loaded)


def test_live_finances_http_get_and_post(starting):
    import json
    from threading import Thread
    from urllib.request import Request,urlopen
    from football_manager.ui_shell.server import create_server
    server=create_server(port=0,session=deepcopy(starting))
    thread=Thread(target=server.serve_forever,daemon=True)
    thread.start()
    host=f'http://127.0.0.1:{server.server_port}'
    try:
        with urlopen(host+'/api/finances',timeout=30) as response:
            before=json.load(response)
        assert before['club_id']==starting.home_club.id and before['contracts']
        candidate=next(row for row in before['contracts'] if row['renewal'] and
                       row['renewal']['minimum_weekly_gbp']>row['weekly_wage_gbp'])
        request=Request(host+'/api/finances',method='POST',headers={'Content-Type':'application/json'},
            data=json.dumps({'action':'renew','player_id':candidate['player_id'],
            'weekly_wage_gbp':candidate['renewal']['minimum_weekly_gbp'],'years':2}).encode())
        with urlopen(request,timeout=50) as response:
            result=json.load(response)
        assert result['renewed']
        with urlopen(host+'/api/finances',timeout=30) as response:
            after=json.load(response)
        amended=next(p for p in after['contracts'] if p['player_id']==candidate['player_id'])
        assert amended['weekly_wage_gbp']==result['wage_weekly_gbp']
        assert amended['expires_on']==result['expires_on']
        assert after['weekly_payroll_gbp']>=before['weekly_payroll_gbp']
        with urlopen(host+'/portable/finances.js',timeout=30) as response:
            assert b'FMFinances' in response.read()
    finally:
        server.shutdown();server.server_close();thread.join(timeout=5)
