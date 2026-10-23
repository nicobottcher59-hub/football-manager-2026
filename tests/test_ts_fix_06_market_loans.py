"""TS-FIX-06: realistic manager offers and stateful loan negotiations."""
from __future__ import annotations
from copy import deepcopy
from datetime import date, timedelta
from dataclasses import replace
import pytest
from football_manager.dev_ui.session import DevelopmentSession
from football_manager.domain.loan_negotiation import LoanTerms, LoanRound, LoanTalk
from football_manager.domain.transfer_negotiation import TransferTerms
from football_manager.services.loan_market import _can_loan, loan_command, loan_read_model
from football_manager.services.loan_bargaining import parse_loan_terms, public_loan_talk
from football_manager.services.club_economy import _date_plus_months
from football_manager.persistence.session_codec import GRAPH_VERSION, capture_manager_graph, restore_manager_graph
from football_manager.services.transfer_negotiation import _seller_target
from football_manager.services.transfer_windows import next_opening
from football_manager.ui_shell.progression import _settle_scheduled_registrations


@pytest.fixture(scope='module')
def initial():return DevelopmentSession()


@pytest.fixture
def s(initial):return deepcopy(initial)


def candidate(s, outgoing=True, months=6, option=None):
    reg=s._world_squads
    manager=s.home_club.id
    for cid,club in reg.clubs.items():
        if cid==manager:continue
        people=(sorted(s.home_club.squad.players,key=lambda p:p.overall_rating)
                if outgoing else sorted(club.squad.players,key=lambda p:p.overall_rating))
        for player in people:
            parent,borrower=(manager,cid) if outgoing else (cid,manager)
            share,role=(50,'rotation') if outgoing else (100,'backup')
            try:_can_loan(reg,player.id,parent,borrower,s.current_date,months,share,role,option,registration_on=next_opening(s.current_date))
            except ValueError:continue
            return player,parent,borrower
    raise AssertionError('No attainable professional loan candidate')


def propose(s,p,parent,borrower,share=100,role='rotation',months=6,**extras):
    return loan_command(s,{'action':'loan_propose','player_id':p.id,'parent_id':parent,'borrower_id':borrower,
                           'terms':{'months':months,'borrower_wage_percent':share,
                                    'playing_time':role,'recall_allowed':False,**extras}})


def test_loan_builder_rejects_invalid_clauses_and_accepts_complex_option():
    with pytest.raises(ValueError):parse_loan_terms({'months':3,'borrower_wage_percent':50,'playing_time':'backup'},date(2026,7,1))
    with pytest.raises(ValueError):parse_loan_terms({'months':12,'borrower_wage_percent':50,'playing_time':'backup','purchase':{'fixed_gbp':0}},date(2026,7,1))
    terms=parse_loan_terms({'months':12,'borrower_wage_percent':45,'playing_time':'rotation','recall_allowed':True,
       'purchase':{'fixed_gbp':500_000,'installments_gbp':250_000,'installment_count':2,'installment_interval_months':6,
                   'bonuses':[{'kind':'appearances','threshold':20,'amount_gbp':15000}],
                   'sell_on_type':'profit','sell_on_percent':15,'buyback_gbp':1_000_000,'buyback_until':'2029-08-01'}},date(2026,7,1))
    assert terms.purchase.guaranteed_gbp==750_000
    terms.validate()


def test_ai_counter_salary_and_actual_loan_registration(s):
    p,parent,borrower=candidate(s)
    before=s._world_squads.contracts[p.id]
    out=propose(s,p,parent,borrower)
    assert out['status']=='counter'
    assert out['patience']<100
    assert 0<=out['terms']['borrower_wage_percent']<100
    data=loan_read_model(s)
    assert len(data['negotiations'])==1
    assert data['negotiations'][0]['history'][-1]['by_club_id']==borrower
    result=loan_command(s,{'action':'loan_accept_counter','talk_id':out['talk_id']})
    assert result['status']=='active'
    registry=s._world_squads
    assert registry.loans[result['loan_id']].borrower_wage_percent==out['terms']['borrower_wage_percent']
    assert registry.contracts[p.id] is before
    assert registry.clubs[borrower].squad.contains(p.id) and not registry.clubs[parent].squad.contains(p.id)
    assert registry.loans[result['loan_id']].recall_allowed is False
    with pytest.raises(ValueError,match='no negotiated recall right'):
        loan_command(s,{'action':'loan_recall','loan_id':result['loan_id']})
    registry.validate()


def test_loan_in_ai_role_counter_must_be_credible(s):
    p,parent,borrower=candidate(s,outgoing=False)
    res=propose(s,p,parent,borrower,share=20,role='rotation')
    assert res['status']=='counter'
    result=loan_command(s,{'action':'loan_accept_counter','talk_id':res['talk_id']})
    assert result['status']=='active'
    assert s._world_squads.loans[result['loan_id']].playing_time=='backup'


def test_counter_patience_and_walk_not_reset(s):
    p,parent,borrower=candidate(s)
    one=propose(s,p,parent,borrower,share=100)
    two=loan_command(s,{'action':'loan_propose','talk_id':one['talk_id'],
          'terms':{'months':6,'borrower_wage_percent':100,'playing_time':'rotation','recall_allowed':False}})
    assert two['patience']<one['patience']
    loan_command(s,{'action':'loan_walk','talk_id':one['talk_id']})
    assert s._world_squads.loan_talks[one['talk_id']].status=='walked'
    with pytest.raises(ValueError):loan_command(s,{'action':'loan_accept_counter','talk_id':one['talk_id']})


def test_future_window_loan_agreement_uses_real_registration_date(s):
    s.current_date=date(2026,10,1)
    p,parent,borrower=candidate(s)
    reg=s._world_squads
    old_cash=reg.club_finances[borrower].cash_gbp
    reply=propose(s,p,parent,borrower,share=30,role='rotation')
    if reply['status']=='counter':
        reply=loan_command(s,{'action':'loan_accept_counter','talk_id':reply['talk_id']})
    assert reply['status']=='pending_window'
    assert reply['arrival_on']=='2027-01-01'
    assert reg.clubs[parent].squad.contains(p.id)
    assert reg.club_finances[borrower].cash_gbp==old_cash
    assert not reg.loans
    # World journal: the loan is registered on the first open month boundary.
    from football_manager.services.loan_bargaining import settle_pending_loan_talks
    with s._world.transaction():
        assert settle_pending_loan_talks(s._world,date(2027,1,1))==1
    assert reg.clubs[borrower].squad.contains(p.id)
    talk=reg.loan_talks[reply['talk_id']]
    assert talk.status=='active'
    assert reg.loans[talk.loan_id].started_on==date(2027,1,1)
    reg.validate()


def test_loan_transfers_full_future_purchase_terms(s):
    p,parent,borrower=candidate(s)
    payload={'fixed_gbp':40_000,'installments_gbp':20_000,'installment_count':2,'installment_interval_months':6,
             'bonuses':[{'kind':'appearances','threshold':20,'amount_gbp':10_000}],
             'sell_on_type':'profit','sell_on_percent':10}
    reply=propose(s,p,parent,borrower,share=50,role='rotation',purchase=payload)
    if reply['status']=='counter':
        reply=loan_command(s,{'action':'loan_accept_counter','talk_id':reply['talk_id']})
    assert reply['status']=='active'
    loan=s._world_squads.loans[reply['loan_id']]
    assert loan.purchase_terms is not None
    assert loan.option_gbp==loan.purchase_terms.guaranteed_gbp
    assert loan.purchase_terms.installment_count==2
    assert loan.purchase_terms.sell_on_percent==10
    s._world_squads.validate()


def test_graph_30_roundtrip_and_29_migration(s):
    assert GRAPH_VERSION==30
    p,parent,borrower=candidate(s)
    propose(s,p,parent,borrower)
    encoded=capture_manager_graph(s)
    loaded=restore_manager_graph(encoded)
    assert loaded._world_squads.loan_talks.keys()==s._world_squads.loan_talks.keys()
    loaded._world_squads.validate()
    # Simulate an older save by dropping new fields and using previous format.
    import json
    raw=deepcopy(encoded)
    raw['version']=29
    for node in raw['nodes']:
        if node.get('class')=='football_manager.domain.football_world:FootballWorld':
            for entry in ('loan_talks','manager_sale_posture'):
                node['fields'].pop(entry,None)
    legacy=restore_manager_graph(raw)
    assert legacy._world_squads.loan_talks=={}
    assert legacy._world_squads.manager_sale_posture=={}


def test_loan_read_does_not_reveal_unknown_ratings(s):
    data=loan_read_model(s)
    assert data['incoming']
    unknown=[p for p in data['incoming'] if p['ovr'] is None]
    assert unknown
    assert all(p['weekly_gbp'] is None for p in data['incoming'])
    assert all(p['nationality'] for p in data['incoming'])


def _active_loan_with_option(s, *, start=None, financed=False):
    from football_manager.services.transfer_installments import deferred_capacity
    reg = s._world_squads
    if start is not None:
        s.current_date = start
    player, parent, borrower = candidate(s, outgoing=False)
    target = _seller_target(reg, parent, borrower, player, reg.contracts[player.id], s.current_date)
    if financed:
        fixed = 1_000_000
        deferred = min(deferred_capacity(reg,borrower,s.current_date), 12_000_000)
        assert fixed + deferred > reg.club_finances[borrower].transfer_budget_gbp
    else:
        total = max(15_000, int(target*1.2 // 5_000 + 1)*5_000)
        fixed, deferred = total//2, total-total//2
    terms = TransferTerms(fixed_gbp=fixed,installments_gbp=deferred,
                          installment_count=2,installment_interval_months=6)
    result=loan_command(s,{'action':'loan_offer','player_id':player.id,'parent_id':parent,
          'borrower_id':borrower,'months':6,'borrower_wage_percent':40,'playing_time':'backup',
          'option_gbp':terms.guaranteed_gbp,'purchase_terms':terms,'recall_allowed':False})
    return player,parent,borrower,terms,result['loan_id']


def test_loan_purchase_schedule_no_early_fees_no_duplicate_settlement(s):
    from football_manager.services.loan_market import _finish_loan
    from football_manager.services.transfer_installments import finance_summary
    player,parent,borrower,terms,loan_id=_active_loan_with_option(s)
    reg=s._world_squads
    original_cash=reg.club_finances[borrower].cash_gbp
    s.current_date=date(2026,11,10)
    pending=loan_command(s,{'action':'loan_buy_option','loan_id':loan_id})
    assert pending['status']=='pending_window' and pending['arrival_on']=='2027-01-01'
    assert reg.clubs[borrower].squad.contains(player.id)
    assert reg.club_finances[borrower].cash_gbp==original_cash
    assert reg.loans[loan_id].option_pending_deal_id==pending['deal_id']
    with pytest.raises(ValueError,match='already been exercised'):
        loan_command(s,{'action':'loan_buy_option','loan_id':loan_id})
    # A seasonal world review returns an expiring loanee before the manager
    # settles pre-agreed permanent registrations at the next opening.
    s.current_date=date(2027,1,1)
    _finish_loan(reg,reg.loans[loan_id],s.current_date)
    assert reg.clubs[parent].squad.contains(player.id)
    assert reg.club_finances[borrower].cash_gbp==original_cash
    _settle_scheduled_registrations(s)
    deal=reg.transfer_offers[pending['deal_id']]
    assert deal.status=='completed' and deal.installments_paid==0
    assert deal.terms==terms and deal.settled_on==s.current_date
    assert reg.clubs[borrower].squad.contains(player.id)
    assert reg.loans[loan_id].status=='purchased'
    assert reg.club_finances[borrower].cash_gbp==original_cash-terms.fixed_gbp-deal.personal_terms.signing_bonus_gbp
    summary=finance_summary(reg,borrower,s.current_date)
    due=[r for r in summary['payments'] if r['deal_id']==deal.deal_id and r['direction']=='payable']
    assert len(due)==2 and all(not r['paid'] for r in due)
    assert due[0]['due_on']=='2027-07-01' and due[1]['due_on']=='2028-01-01'
    before=reg.club_finances[borrower].cash_gbp
    _settle_scheduled_registrations(s)
    assert reg.club_finances[borrower].cash_gbp==before
    restored=restore_manager_graph(capture_manager_graph(s))
    assert restored._world_squads.loans[loan_id].status=='purchased'
    assert restored._world_squads.transfer_offers[deal.deal_id].installments_paid==0
    reg.validate()


def test_fully_deferred_option_not_blocked_by_upfront_budget(s):
    from football_manager.services.transfer_installments import deferred_capacity
    player,parent,borrower,terms,loan_id=_active_loan_with_option(s,start=date(2026,7,15),financed=True)
    reg=s._world_squads
    assert terms.guaranteed_gbp>reg.club_finances[borrower].transfer_budget_gbp
    assert terms.fixed_gbp<reg.club_finances[borrower].transfer_budget_gbp
    assert terms.installments_gbp<=deferred_capacity(reg,borrower,s.current_date)
    s.current_date=date(2027,1,1)
    result=loan_command(s,{'action':'loan_buy_option','loan_id':loan_id})
    assert result['status']=='purchased'
    deal=reg.transfer_offers[result['transfer']['deal_id']]
    assert deal.terms==terms and deal.status=='completed'
    assert reg.loans[loan_id].status=='purchased'
    assert reg.clubs[borrower].squad.contains(player.id)
    reg.validate()


def test_closed_talk_cannot_reopen_next_day(s):
    p,parent,borrower=candidate(s)
    first=propose(s,p,parent,borrower)
    loan_command(s,{'action':'loan_walk','talk_id':first['talk_id']})
    with pytest.raises(ValueError,match='needs time'):
        propose(s,p,parent,borrower)
    s.current_date=s.current_date+timedelta(days=15)
    other=propose(s,p,parent,borrower)
    assert other['talk_id']!=first['talk_id']


def test_ai_incoming_bids_are_scoped_and_never_auto_sell(s):
    from football_manager.services.ai_transfer_market import process_ai_market
    reg=s._world_squads
    manager=s.home_club.id
    before_players={p.id for p in reg.clubs[manager].squad.players}
    existing={d.deal_id for d in reg.transfer_offers.values() if d.seller_id==manager}
    # A first-of-month background transfer review may buy/sell between AI clubs,
    # but must issue at most one new manager bid and no automatic human sales.
    with s._world.transaction():
        process_ai_market(s._world,date(2026,9,1))
    incoming=[d for d in reg.transfer_offers.values() if d.seller_id==manager and d.deal_id not in existing]
    assert len(incoming)<=1
    assert all(d.status=='manager_turn' for d in incoming)
    assert {p.id for p in reg.clubs[manager].squad.players}==before_players
    reg.validate()


def test_weekly_incoming_interest_uses_same_scarcity_limits(s):
    from football_manager.services.transfer_market_activity import create_incoming_interest
    reg=s._world_squads
    manager=s.home_club.id
    before={p.id for p in reg.clubs[manager].squad.players}
    with s._world.transaction():
        created=create_incoming_interest(s._world,date(2026,7,15))
    assert created<=1
    summer=[d for d in reg.transfer_offers.values() if d.seller_id==manager
            and d.started_on.year==2026 and d.started_on.month in (7,8)]
    assert len(summer)<=3
    assert sum(reg.manager_sale_posture.get(d.player_id,'normal')!='transfer_listed' for d in summer)<=1
    assert {p.id for p in reg.clubs[manager].squad.players}==before
    # 'Untouchable' is a binding target exclusion in the weekly path too.
    for player in reg.clubs[manager].squad.players:
        reg.manager_sale_posture[player.id]='untouchable'
    with s._world.transaction():
        assert create_incoming_interest(s._world,date(2026,7,29))==0
    reg.validate()
