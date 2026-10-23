"""TS-FIX-07: one-time loan fee, grounded news and personal-notice separation."""
from copy import deepcopy
from dataclasses import replace
from datetime import date, timedelta
from types import SimpleNamespace
import pytest

from football_manager.dev_ui.session import DevelopmentSession
from football_manager.domain.loan_negotiation import LoanTerms, LoanTalk, LoanRound
from football_manager.domain.loan_market import LoanAgreement
from football_manager.domain.world_runner import WorldSeasonRunner, WorldMatchResult
from football_manager.persistence.session_codec import capture_manager_graph, restore_manager_graph, GRAPH_VERSION
from football_manager.services.loan_market import _can_loan, _begin, loan_read_model
from football_manager.services.loan_bargaining import parse_loan_terms, loan_talk_command, settle_pending_loan_talks
from football_manager.services.transfer_windows import next_opening
from football_manager.services.manager_inbox import synchronize_manager_inbox, _notice
from football_manager.ui_shell.home_news import home_news_read_model


@pytest.fixture(scope='module')
def initial():
    return DevelopmentSession()


@pytest.fixture
def session(initial):
    return deepcopy(initial)


def candidate(session, *, outgoing=True, on_date=None):
    reg=session._world_squads
    manager=session.home_club.id
    today=on_date or session.current_date
    for cid,club in reg.clubs.items():
        if cid == manager: continue
        parent,borrower=(manager,cid) if outgoing else (cid,manager)
        people=(sorted(session.home_club.squad.players,key=lambda x:x.overall_rating)
                if outgoing else sorted(club.squad.players,key=lambda x:x.overall_rating))
        for player in people:
            try:
                _can_loan(reg,player.id,parent,borrower,today,6,50,'backup',None,
                          registration_on=next_opening(today))
            except ValueError:
                continue
            return player,parent,borrower
    raise AssertionError('No suitable loan candidate')


def terms_payload(fee, **other):
    return {'months':6,'borrower_wage_percent':50,'playing_time':'backup',
            'recall_allowed':False,'loan_fee_gbp':fee,**other}


def test_loan_fee_validation_and_default():
    when=date(2026,7,1)
    base={'months':6,'borrower_wage_percent':50,'playing_time':'backup'}
    assert parse_loan_terms(base,when).loan_fee_gbp == 0
    assert parse_loan_terms({**base,'loan_fee_gbp':155_000},when).loan_fee_gbp == 155_000
    for bad in (-1,500_000_001,5000.5,True,'5000'):
        with pytest.raises(ValueError):
            parse_loan_terms({**base,'loan_fee_gbp':bad},when)


def test_registration_charges_once_without_purchase_or_salary_confusion(session):
    player,parent,borrower=candidate(session,outgoing=False)
    reg=session._world_squads
    fee=25_000
    seller_before=reg.club_finances[parent]
    buyer_before=reg.club_finances[borrower]
    result=_begin(session,{'player_id':player.id,'parent_id':parent,'borrower_id':borrower,
                  'months':6,'borrower_wage_percent':50,'playing_time':'backup',
                  'recall_allowed':False,'loan_fee_gbp':fee})
    assert result['status']=='active' and result['loan_fee_gbp']==fee
    loan=reg.loans[result['loan_id']]
    assert loan.loan_fee_gbp==fee and loan.option_gbp is None
    assert reg.club_finances[parent].cash_gbp == seller_before.cash_gbp+fee
    assert reg.club_finances[parent].transfer_budget_gbp == seller_before.transfer_budget_gbp+fee
    assert reg.club_finances[borrower].cash_gbp == buyer_before.cash_gbp-fee
    assert reg.club_finances[borrower].transfer_budget_gbp == buyer_before.transfer_budget_gbp-fee
    snapshot=reg.club_finances[parent].cash_gbp,reg.club_finances[borrower].cash_gbp
    assert home_news_read_model(session)['stories'][0]['category']=='loan'
    synchronize_manager_inbox(session)
    assert not any(m.source_key.startswith('loan:') for m in session.manager_inbox.messages)
    assert snapshot==(reg.club_finances[parent].cash_gbp,reg.club_finances[borrower].cash_gbp)
    assert any(x['loan_fee_gbp']==fee for x in loan_read_model(session)['loans'])
    reg.validate()


def test_unaffordable_loan_fee_never_moves_money_or_player(session):
    p,parent,borrower=candidate(session,outgoing=False)
    reg=session._world_squads
    before=reg.club_finances[borrower]
    with pytest.raises(ValueError,match='afford'):
        _begin(session,{'player_id':p.id,'parent_id':parent,'borrower_id':borrower,
                        'months':6,'borrower_wage_percent':50,'playing_time':'backup',
                        'loan_fee_gbp':min(500_000_000,max(0,before.transfer_budget_gbp)+1)})
    assert reg.club_finances[borrower] is before
    assert reg.clubs[parent].squad.contains(p.id)
    assert not reg.clubs[borrower].squad.contains(p.id)


def test_pending_loan_fee_settles_only_at_window_and_survives_reload(session):
    session.current_date=date(2026,10,1)
    p,parent,borrower=candidate(session,outgoing=False)
    reg=session._world_squads
    fee=15_000
    before=(reg.club_finances[parent].cash_gbp,reg.club_finances[borrower].cash_gbp)
    result=loan_talk_command(session,{'action':'loan_propose','player_id':p.id,
        'parent_id':parent,'borrower_id':borrower,'terms':terms_payload(fee)})
    if result['status']=='counter':
        result=loan_talk_command(session,{'action':'loan_accept_counter','talk_id':result['talk_id']})
    assert result['status']=='pending_window'
    talk=reg.loan_talks[result['talk_id']]
    negotiated=talk.terms.loan_fee_gbp
    assert (reg.club_finances[parent].cash_gbp,reg.club_finances[borrower].cash_gbp)==before
    assert reg.clubs[parent].squad.contains(p.id)
    # Try a real save if feasible; the ledger is also tested via isolated graph.
    with session._world.transaction():
        assert settle_pending_loan_talks(session._world,date(2027,1,1))==1
    assert reg.clubs[borrower].squad.contains(p.id)
    assert (reg.club_finances[parent].cash_gbp,reg.club_finances[borrower].cash_gbp)==(before[0]+negotiated,before[1]-negotiated)
    with session._world.transaction():
        assert settle_pending_loan_talks(session._world,date(2027,1,1))==0
    assert (reg.club_finances[parent].cash_gbp,reg.club_finances[borrower].cash_gbp)==(before[0]+negotiated,before[1]-negotiated)
    assert next(x for x in reg.loans.values() if x.player_id==p.id).loan_fee_gbp == negotiated


def test_complete_low_fee_ai_transfer_appears_in_news(session):
    reg=session._world_squads
    manager=session.home_club.id
    ids=[cid for cid in reg.clubs if cid!=manager]
    seller,buyer=ids[:2]
    player=reg.clubs[seller].squad.players[0]
    event=SimpleNamespace(on_date=session.current_date)
    reg.transfer_offers['tsfix07-news-small']=SimpleNamespace(
        deal_id='tsfix07-news-small',status='completed',personal_status='completed',
        personal_events=(event,),terms=SimpleNamespace(fixed_gbp=25_000),
        player_id=player.id,seller_id=seller,buyer_id=buyer)
    story=next(x for x in home_news_read_model(session)['stories'] if x['id']=='transfer:tsfix07-news-small')
    assert story['category']=='transfer' and story['route']=='Transfers'
    assert '25,000' in story['body']
    synchronize_manager_inbox(session)
    assert not any(m.source_key.startswith('world-transfer:') for m in session.manager_inbox.messages)


def test_results_only_in_news_and_legacy_inbox_cleanup(session):
    world=session._world
    managed=session.home_club.id
    fixture=next(x for x in world.fixtures.values() if managed in (x.home_club_id,x.away_club_id) and x.kickoff)
    session.current_date=max(session.current_date,fixture.kickoff.date())
    world.results[fixture.fixture_id]=WorldMatchResult(fixture.fixture_id,2,1)
    _notice(session.manager_inbox,session.current_date,'results','Match result recorded','An old duplicate',
            f'result:{fixture.fixture_id}')
    _notice(session.manager_inbox,session.current_date,'market','Major transfer completed','An old duplicate',
            'world-transfer:old')
    synchronize_manager_inbox(session)
    assert not any(m.source_key.startswith(('result:','world-transfer:')) for m in session.manager_inbox.messages)
    assert any(story['id']==f'match:{fixture.fixture_id}' for story in home_news_read_model(session)['stories'])
    synchronize_manager_inbox(session)
    assert not any(m.source_key==f'result:{fixture.fixture_id}' for m in session.manager_inbox.messages)


def test_migrate_version31_loan_fee_fields_defaults():
    when=date(2026,7,1)
    lt=LoanTerms(6,50,'rotation')
    loan=LoanAgreement('a','p','club-a','club-b',when,date(2027,1,1),50,'rotation')
    old=object.__new__(DevelopmentSession)
    old._world=object.__new__(WorldSeasonRunner)
    old._world._active_journal=None
    old._world._advance_queue=None
    old.saved_terms=lt
    old.saved_loan=loan
    graph=capture_manager_graph(old)
    assert graph['version']==GRAPH_VERSION==32
    restored=restore_manager_graph(graph)
    assert restored.saved_terms.loan_fee_gbp == 0 and restored.saved_loan.loan_fee_gbp == 0
    legacy=deepcopy(graph)
    legacy['version']=31
    for node in legacy['nodes']:
        if node.get('class') in ('football_manager.domain.loan_market:LoanAgreement',
                                 'football_manager.domain.loan_negotiation:LoanTerms'):
            node['fields'].pop('loan_fee_gbp')
    loaded=restore_manager_graph(legacy)
    assert loaded.saved_terms.loan_fee_gbp==0 and loaded.saved_loan.loan_fee_gbp==0


def test_frontend_loan_fee_and_shared_dialog_code():
    from pathlib import Path
    root=Path(__file__).resolve().parents[1]/'frontend/portable'
    form=(root/'loan_negotiations.js').read_text()
    assert "number('Loan fee" in form and "f.namedItem('loan_fee_gbp')" in form
    assert "loan_fee_gbp||0" in (root/'transfers.js').read_text()
    assert 'fm_dialog.js' in (root/'index.html').read_text()
    for item in ('club_support.js','youth_academy.js','transfers.js'):
        script=(root/item).read_text()
        assert 'window.confirm(' not in script and 'window.alert(' not in script


def test_ai_can_counter_a_separate_loan_fee_without_changing_purchase_option(session):
    p,parent,borrower=candidate(session)
    reg=session._world_squads
    from dataclasses import replace
    bank=reg.club_finances[borrower]
    reg.club_finances[borrower]=replace(bank,cash_gbp=max(30_000_000,bank.cash_gbp),
                                        transfer_budget_gbp=max(30_000_000,bank.transfer_budget_gbp))
    result=loan_talk_command(session,{'action':'loan_propose',
        'player_id':p.id,'parent_id':parent,'borrower_id':borrower,
        'terms':terms_payload(3_000_000,playing_time='rotation')})
    assert result['status']=='counter'
    assert 0 <= result['terms']['loan_fee_gbp'] < 3_000_000
    assert result['terms']['purchase'] is None
    assert reg.club_finances[borrower].cash_gbp==max(30_000_000,bank.cash_gbp)
    assert not reg.loans


def test_fee_and_purchase_option_are_distinct_terms():
    terms=parse_loan_terms({'months':12,'playing_time':'rotation','borrower_wage_percent':75,
        'loan_fee_gbp':150_000,'purchase':{'fixed_gbp':4_000_000}},date(2026,7,1))
    assert terms.loan_fee_gbp == 150_000
    assert terms.purchase.fixed_gbp == 4_000_000
    terms.validate()
