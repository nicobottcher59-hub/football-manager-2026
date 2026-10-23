"""TS-UI-09.01: one negotiation surface, cross-mode offers, no age ban."""
from copy import deepcopy
from datetime import date
from pathlib import Path
import pytest

from football_manager.dev_ui.session import DevelopmentSession
from football_manager.services.loan_market import loan_command, _can_loan, loan_read_model
from football_manager.services.loan_bargaining import public_loan_talk
from football_manager.services.transfer_negotiation import negotiate, transfer_read_model
from football_manager.services.transfer_windows import next_opening
from football_manager.persistence.session_codec import GRAPH_VERSION

ROOT=Path(__file__).resolve().parents[1]

@pytest.fixture(scope='module')
def game():
    return DevelopmentSession()

@pytest.fixture
def session(game):
    return deepcopy(game)


def _candidate(s, outgoing=False):
    reg=s._world_squads; manager=s.home_club.id
    for cid, club in reg.clubs.items():
        if cid==manager:continue
        parent,borrower=(manager,cid) if outgoing else (cid,manager)
        for player in (s.home_club.squad.players if outgoing else club.squad.players):
            try:
                _can_loan(reg,player.id,parent,borrower,s.current_date,6,0,'backup',None,
                          registration_on=next_opening(s.current_date,reg.clubs[borrower].country))
                return player,parent,borrower
            except ValueError:
                continue
    raise AssertionError('no eligible loan candidate')


def test_loan_can_turn_into_actual_transfer_counteroffer(session,monkeypatch):
    from football_manager.services import loan_bargaining
    p,parent,borrower=_candidate(session)
    manager=session.home_club.id
    money_before=tuple(x.cash_gbp for x in session._world_squads.club_finances.values())
    monkeypatch.setattr(loan_bargaining,'_prefer_permanent_sale',lambda *a: True)
    res=loan_command(session,{'action':'loan_propose','player_id':p.id,
        'parent_id':parent,'borrower_id':borrower,'terms':{
        'months':6,'borrower_wage_percent':5,'playing_time':'backup','recall_allowed':False}})
    assert res['status']=='alternate_transfer',res
    assert res['transfer_deal_id']
    talk=session._world_squads.loan_talks[res['talk_id']]
    deal=session._world_squads.transfer_offers[res['transfer_deal_id']]
    assert talk.status=='converted' and talk.linked_transfer_deal_id==deal.deal_id
    assert deal.linked_loan_talk_id==talk.talk_id
    assert deal.seller_id==parent and deal.buyer_id==borrower
    assert deal.tolerance_remaining==talk.patience<100
    assert deal.status=='manager_turn' and deal.proposed_by==parent
    assert session._world_squads.clubs[parent].squad.contains(p.id)
    assert tuple(x.cash_gbp for x in session._world_squads.club_finances.values())==money_before
    info=next(d for d in transfer_read_model(session)['offers'] if d['id']==deal.deal_id)
    assert info['prior_loan_history'] and info['prior_loan_history'][0]['mode']=='loan'
    assert info['history'][-1]['terms']['fixed_gbp']>=5000
    session._world_squads.validate()


def test_transfer_can_turn_into_actual_loan_counteroffer(session,monkeypatch):
    from football_manager.services import transfer_negotiation
    p,parent,borrower=_candidate(session)
    monkeypatch.setattr(transfer_negotiation,'_prefer_loan_instead_of_sale',lambda *a: True)
    res=negotiate(session,{'action':'submit','seller_id':parent,'player_id':p.id,
        'terms':{'fixed_gbp':0}})
    assert res['status']=='alternate_loan',res
    assert res['loan_talk_id']
    deal=session._world_squads.transfer_offers[res['deal_id']]
    talk=session._world_squads.loan_talks[res['loan_talk_id']]
    assert deal.status=='withdrawn' and talk.source_transfer_deal_id==deal.deal_id
    assert talk.status=='counter' and talk.rounds[0].by_club_id==parent
    assert talk.patience==deal.tolerance_remaining and talk.patience>0
    assert session._world_squads.clubs[parent].squad.contains(p.id)
    data=next(d for d in loan_read_model(session)['negotiations'] if d['id']==talk.talk_id)
    assert data['prior_transfer_history'] and data['prior_transfer_history'][0]['mode']=='transfer'
    session._world_squads.validate()


def test_original_loans_are_not_age_capped(session):
    from football_manager.services import loan_market
    # No per-player age maximum in the deal engine or AI-AI loan pool.
    assert 'age_on(boundary)>24' not in (Path(loan_market.__file__).read_text())
    assert 'age_on(now)>24' not in (Path(loan_market.__file__).read_text())
    assert GRAPH_VERSION==31



def test_loan_discovery_includes_veterans_without_public_rating():
    from football_manager.services.loan_market import _loan_discovery_sample
    # Without age-stratification, young players fill the first page and hide
    # the entire 27+ cohort despite being eligible for individual loans.
    people=[]
    for age, count in [(17,350),(23,200),(27,180),(31,140),(35,100)]:
        for index in range(count):
            people.append({'id':f'{age}-{index}','name':f'Player {age}-{index}',
                           'age':age,'position':'CB','club_id':f'club-{index%15}'})
    selected=_loan_discovery_sample(people,{'CB'},250)
    assert len(selected)==250
    assert len({p['id'] for p in selected})==250
    assert {p['age'] for p in selected}=={17,23,27,31,35}
    assert sum(p['age']>=27 for p in selected)>80
    assert selected==_loan_discovery_sample(list(reversed(people)),{'CB'},250)


def test_inline_mode_is_not_a_page_navigation():
    script=(ROOT/'frontend/portable/transfers.js').read_text()
    loan=(ROOT/'frontend/portable/loan_negotiations.js').read_text()
    assert 'saveDraft();dealMode=\'loan\'' in script
    assert 'embedded:true' in script and 'ln-embedded-columns' in loan
    assert "nav()?.loanPlayer?.(button.dataset.trSwitchLoan" not in script
    assert "data-tr-switch-transfer" in script and "data-tr-switch-loan" in script
    assert "reply.status==='alternate_transfer'" in script
    assert "result.status==='alternate_loan'" in script
    assert "prior_loan_history" in script


def test_manual_loan_to_permanent_keeps_patience_and_history(session):
    p,parent,borrower=_candidate(session)
    opening=loan_command(session,{'action':'loan_propose','player_id':p.id,
        'parent_id':parent,'borrower_id':borrower,'terms':{
        'months':6,'borrower_wage_percent':5,'playing_time':'backup','recall_allowed':False}})
    assert opening['status']=='counter',opening
    remaining=opening['patience']
    updated=negotiate(session,{'action':'transfer_from_loan','talk_id':opening['talk_id'],
        'terms':{'fixed_gbp':0}})
    talk=session._world_squads.loan_talks[opening['talk_id']]
    deal=session._world_squads.transfer_offers[updated['deal_id']]
    assert talk.status=='converted' and talk.linked_transfer_deal_id==deal.deal_id
    assert deal.linked_loan_talk_id==talk.talk_id
    assert deal.tolerance_remaining<=remaining
    assert session._world_squads.clubs[parent].squad.contains(p.id)
    session._world_squads.validate()


def test_manual_permanent_to_loan_keeps_patience_and_history(session):
    p,parent,borrower=_candidate(session)
    first=negotiate(session,{'action':'submit','seller_id':parent,'player_id':p.id,
        'terms':{'fixed_gbp':0}})
    deal=session._world_squads.transfer_offers[first['deal_id']]
    assert deal.status=='manager_turn'
    reply=loan_command(session,{'action':'loan_propose','player_id':p.id,
        'parent_id':parent,'borrower_id':borrower,'source_transfer_deal_id':deal.deal_id,
        'terms':{'months':6,'borrower_wage_percent':5,
                 'playing_time':'backup','recall_allowed':False}})
    talk=session._world_squads.loan_talks[reply['talk_id']]
    former=session._world_squads.transfer_offers[deal.deal_id]
    assert talk.source_transfer_deal_id==deal.deal_id
    assert former.linked_loan_talk_id==talk.talk_id and former.status=='withdrawn'
    assert talk.patience<=deal.tolerance_remaining
    assert len(public_loan_talk(talk,session._world_squads)['prior_transfer_history'])>=1
    session._world_squads.validate()


def test_graph_31_can_read_version_30_loan_and_transfer_records():
    """Small, real codec graph: confirm old deal records migrate without
    requiring a multi-thousand-player world to serialize during the test.
    """
    from football_manager.persistence.session_codec import capture_manager_graph, restore_manager_graph
    from football_manager.domain.loan_negotiation import LoanTalk, LoanTerms, LoanRound
    from football_manager.domain.transfer_negotiation import (
        TransferNegotiation, TransferTerms, NegotiationEvent,
    )
    when=date(2026,7,1)
    loan_terms=LoanTerms(12,50,'rotation',False,None)
    offer_terms=TransferTerms(1_000_000)
    loan=LoanTalk('talk-1','player-1','club-a','club-b',when,date(2026,8,1),
                  'counter',loan_terms,(LoanRound(when,'club-a',loan_terms,'Open talks'),))
    offer=TransferNegotiation('deal-1','player-1','club-a','club-b',
        when,date(2026,8,1),'manager_turn','club-a',offer_terms,
        (NegotiationEvent(when,'club-a',offer_terms,'Open terms'),))
    from football_manager.domain.world_runner import WorldSeasonRunner
    old=object.__new__(DevelopmentSession)
    old._world=object.__new__(WorldSeasonRunner)
    old._world._active_journal=None
    old._world._advance_queue=None
    old.saved_loan=loan
    old.saved_offer=offer
    graph=capture_manager_graph(old)
    assert graph['version']==31
    assert restore_manager_graph(graph).saved_loan.talk_id=='talk-1'
    legacy=deepcopy(graph)
    legacy['version']=30
    for node in legacy['nodes']:
        if node.get('class')=='football_manager.domain.loan_negotiation:LoanTalk':
            node['fields'].pop('linked_transfer_deal_id',None)
            node['fields'].pop('source_transfer_deal_id',None)
        if node.get('class')=='football_manager.domain.transfer_negotiation:TransferNegotiation':
            node['fields'].pop('linked_loan_talk_id',None)
    restored=restore_manager_graph(legacy)
    assert restored.saved_loan.linked_transfer_deal_id is None
    assert restored.saved_loan.source_transfer_deal_id is None
    assert restored.saved_offer.linked_loan_talk_id is None
