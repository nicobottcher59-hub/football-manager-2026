"""TS-FIX-02: public knowledge, package negotiation, debt ledger and interventions.

Private valuation helpers are used ONLY to construct controlled test fixtures;
the browser/read model must never receive those values without knowledge.
"""
from copy import deepcopy
from dataclasses import replace
from datetime import date, timedelta
import json
import pytest
from football_manager.dev_ui.session import DevelopmentSession
from football_manager.domain.transfer_negotiation import TransferTerms, TransferBonus
from football_manager.domain.club_support import ProfessionalScoutReport
from football_manager.services.transfer_negotiation import (
    negotiate, transfer_read_model, _create_offer, _quote, _terms_from_data, assess_terms)
from football_manager.services.transfer_installments import (
    schedule, paid_deferred, settle_due_installments, finance_summary,
    deferred_capacity, validate_financing)
from football_manager.services.transfer_bargaining import seller_reply, public_tolerance
from football_manager.services.transfer_knowledge import player_knowledge
from football_manager.services.transfer_personal import agent_demand
from football_manager.services.transfer_market_activity import create_incoming_interest, advance_transfer_activity
from football_manager.ui_shell.progression import simulate_until, pending_transfer_decisions, progression_read_model
from football_manager.persistence.session_codec import capture_manager_graph, restore_manager_graph, GRAPH_VERSION


@pytest.fixture(scope='module')
def base():
    return DevelopmentSession()


@pytest.fixture
def s(base):
    return deepcopy(base)


def target(session, cheap=False):
    r = session._world_squads
    for cid, club in r.clubs.items():
        if cid == session.home_club.id: continue
        for p in club.squad.players:
            if p.id not in r.contracts or r.contracts[p.id].kind != 'professional': continue
            if p.overall_rating >= 85 or p.id in r.club_support[session.home_club.id].scouting_reports: continue
            if cheap and not (50 < p.overall_rating < 65 and p.age_on(session.current_date) >= 20
                              and _quote(r, p).value_gbp < 500_000): continue
            return cid, p
    raise AssertionError('No controlled target found')


def submit(s, terms=None):
    cid, p = target(s)
    answer = negotiate(s, {'action':'submit','seller_id':cid,'player_id':p.id,
                          'terms':terms or {'fixed_gbp':0}})
    return s._world_squads.transfer_offers[answer['deal_id']]


def complete(s, terms=None):
    r=s._world_squads;cid,p=target(s,cheap=True)
    t=terms or TransferTerms(100_000, installments_gbp=600_003, installment_count=4, installment_interval_months=6)
    deal=_create_offer(r,p.id,cid,s.home_club.id,s.current_date,t,s.home_club.id)
    deal=replace(deal,status='agreed');r.transfer_offers[deal.deal_id]=deal
    q=agent_demand(r,p,cid,s.home_club.id,s.current_date)
    assert q['interested']
    result=negotiate(s,{'action':'personal_offer','deal_id':deal.deal_id,'terms':{
        'weekly_wage_gbp':q['weekly_wage_gbp'],'years':q['years'],'role':q['role'],'signing_bonus_gbp':0}})
    assert result['status']=='completed'
    return r.transfer_offers[deal.deal_id]


@pytest.mark.parametrize('count',[2,4,6])
@pytest.mark.parametrize('interval',[6,12,18])
@pytest.mark.parametrize('when',[date(2026,8,31),date(2028,2,29)])
def test_exact_installment_schedule_all_combinations(count,interval,when):
    t=TransferTerms(0,installments_gbp=1_000_003,installment_count=count,installment_interval_months=interval)
    t.validate();payments=schedule(t,when)
    assert len(payments)==count and sum(x[1] for x in payments)==1_000_003
    assert payments[0][0]>when and all(a[0]<b[0] for a,b in zip(payments,payments[1:]))
    assert (payments[-1][0].year-when.year)*12+payments[-1][0].month-when.month==count*interval
    assert payments[-1][1]>=payments[0][1]


@pytest.mark.parametrize('raw',[
    {'fixed_gbp':-1},{'fixed_gbp':True},{'fixed_gbp':2.5},{'fixed_gbp':500_000_001},
    {'fixed_gbp':0,'installments_gbp':True},
    {'fixed_gbp':0,'installments_gbp':100,'installment_count':3,'installment_interval_months':6},
    {'fixed_gbp':0,'installments_gbp':100,'installment_count':2,'installment_interval_months':3},
    {'fixed_gbp':0,'installments_gbp':3,'installment_count':6,'installment_interval_months':6},
    {'fixed_gbp':0,'installment_count':2,'installment_interval_months':6},
    {'fixed_gbp':500_000_000,'installments_gbp':10,'installment_count':2,'installment_interval_months':6},
    {'fixed_gbp':0,'installments_gbp':100,'installment_count':2.0,'installment_interval_months':6},
    {'fixed_gbp':0,'installments_gbp':100,'installment_count':2,'installment_interval_months':True},
])
def test_reject_invalid_technical_terms(raw):
    with pytest.raises((ValueError,TypeError)):_terms_from_data(raw,date(2026,8,1),100)


@pytest.mark.parametrize('fee',[0,1,4999,5000,1234567,500000000])
def test_no_price_related_minimum_or_step(fee):
    assert _terms_from_data({'fixed_gbp':fee},date(2026,8,1),100).fixed_gbp==fee


def test_read_model_is_readonly_and_hides_unobserved_values(s):
    r=s._world_squads;before=(r.transfer_next_id,dict(r.transfer_offers),dict(r.club_finances),r.transfer_interest_review_on)
    a=transfer_read_model(s);b=transfer_read_model(s)
    assert a==b
    unknown=[p for p in a['targets'] if p['knowledge_source']=='unknown']
    assert unknown and all(p['ovr'] is None and p['value_gbp'] is None for p in unknown)
    assert before==(r.transfer_next_id,dict(r.transfer_offers),dict(r.club_finances),r.transfer_interest_review_on)
    assert not any('potential' in p or 'current_rating' in p for p in a['targets'])


def test_own_ovr_is_general_not_temporary_rating(s):
    p=s.home_club.squad.players[0]
    k=player_knowledge(s,s.home_club.id,p)
    assert k['ovr']==round(p.overall_rating,1) and k['value_gbp']>0
    assert k['knowledge_source']=='own_club'


def test_completed_report_is_snapshot_not_hidden_live_value(s):
    cid,p=target(s);sup=s._world_squads.club_support[s.home_club.id]
    sup.scouting_reports[p.id]=ProfessionalScoutReport(p.id,'test-scout',s.current_date-timedelta(days=20),
        p.full_name,s._world_squads.clubs[cid].name,p.primary_position.value,61.2,p.age_on(s.current_date),
        123456,('Passing',),'Controlled report snapshot')
    k=player_knowledge(s,cid,p)
    assert k['ovr']==61.2 and k['value_gbp']==123456 and k['knowledge_source']=='scout_report'


def test_public_high_profile_players_keep_public_general_information(s):
    r=s._world_squads
    cid,p=next((cid,p) for cid,c in r.clubs.items() for p in c.squad.players if cid!=s.home_club.id and p.overall_rating>=85)
    k=player_knowledge(s,cid,p)
    assert k['ovr']==round(p.overall_rating,1) and k['value_gbp']>0 and k['knowledge_source']=='public'


def test_preview_only_describes_own_package_and_cannot_spend_patience(s):
    cid,p=target(s);r=s._world_squads;before=deepcopy(r.transfer_offers);seq=r.transfer_next_id
    a=negotiate(s,{'action':'preview','seller_id':cid,'player_id':p.id,'terms':{'fixed_gbp':0}})
    assert a['valuation']['guaranteed_gbp']==0
    assert 'risk_adjusted_gbp' not in json.dumps(a) and 'probability' not in json.dumps(a)
    assert r.transfer_next_id==seq and r.transfer_offers==before


def test_zero_bid_receives_counter_not_an_immediate_rupture(s):
    d=submit(s)
    assert d.events[0].terms.fixed_gbp==0 and d.status=='manager_turn'
    assert 0<d.tolerance_remaining<100
    row=next(o for o in transfer_read_model(s)['offers'] if o['id']==d.deal_id)
    assert row['market_value_gbp'] is None and row['player_profile']['ovr'] is None
    assert 'risk_adjusted_gbp' not in json.dumps(row) and 'probability_pct' not in json.dumps(row)
    assert row['history'][0]['terms']['fixed_gbp']==0


def test_bad_repeated_bids_warn_before_breaking_and_cannot_reset_tolerance(s):
    d=submit(s);critical=False;values=[d.tolerance_remaining]
    for _ in range(15):
        if d.status=='rejected':break
        critical |= public_tolerance(d)['level']=='Critical'
        result=negotiate(s,{'action':'counter','deal_id':d.deal_id,'terms':{'fixed_gbp':0}})
        d=s._world_squads.transfer_offers[result['deal_id']];values.append(d.tolerance_remaining)
    assert critical and d.status=='rejected' and d.tolerance_remaining==0
    assert values==sorted(values,reverse=True)
    with pytest.raises(ValueError,match='reopen'):submit(s)
    with pytest.raises(ValueError,match='no longer active'):
        negotiate(s,{'action':'counter','deal_id':d.deal_id,'terms':{'fixed_gbp':1000}})


def test_unaffordable_counter_does_not_consume_patience(s):
    d=submit(s);before=deepcopy(s._world_squads.transfer_offers)
    with pytest.raises(ValueError,match='budget'):
        negotiate(s,{'action':'counter','deal_id':d.deal_id,'terms':{'fixed_gbp':500000000}})
    assert s._world_squads.transfer_offers==before


def test_counter_can_change_installment_schedule_and_other_terms(s):
    d=submit(s,{'fixed_gbp':1000,'installments_gbp':100000,'installment_count':6,'installment_interval_months':18})
    assert d.status=='manager_turn' and d.terms.installments_gbp>0
    assert d.terms.installment_count in (2,4) and d.terms.installment_interval_months in (6,12)
    assert d.terms!=d.events[0].terms


def test_young_nonurgent_seller_can_add_bonus_or_sell_on(s):
    r=s._world_squads;cid,p=target(s)
    # A real young player with a liquid seller gives a deterministic package case.
    cid,p=next((cid,p) for cid,c in r.clubs.items() for p in c.squad.players
               if cid!=s.home_club.id and p.id in r.contracts and p.age_on(s.current_date)<=25)
    a=r.club_finances[cid];r.club_finances[cid]=replace(a,cash_gbp=1_000_000_000)
    d=_create_offer(r,p.id,cid,s.home_club.id,s.current_date,TransferTerms(0),s.home_club.id)
    reply=seller_reply(r,d,p,1_000_000,s.current_date)
    assert reply.status=='manager_turn' and (reply.terms.bonuses or reply.terms.sell_on_percent)


def test_deferred_money_is_guaranteed_but_has_lower_present_value(s):
    cid,p=target(s);r=s._world_squads
    cash=assess_terms(r,p,s.home_club.id,TransferTerms(1_000_000),s.current_date)
    short=assess_terms(r,p,s.home_club.id,TransferTerms(0,installments_gbp=1_000_000,installment_count=2,installment_interval_months=6),s.current_date)
    long=assess_terms(r,p,s.home_club.id,TransferTerms(0,installments_gbp=1_000_000,installment_count=6,installment_interval_months=18),s.current_date)
    assert cash['guaranteed_gbp']==short['guaranteed_gbp']==long['guaranteed_gbp']
    assert cash['risk_adjusted_gbp']>short['risk_adjusted_gbp']>long['risk_adjusted_gbp']


def test_real_transfer_only_pays_initial_cash_then_exact_due_installments(s):
    r=s._world_squads;manager=s.home_club.id;before=r.club_finances[manager].cash_gbp
    d=complete(s)
    assert r.club_finances[manager].cash_gbp==before-100000
    assert r.contracts[d.player_id].club_id==manager
    assert d.settled_on==s.current_date and d.installments_paid==0
    dates=schedule(d.terms,d.settled_on)
    for i,(due,amount) in enumerate(dates):
        old=r.club_finances[manager].cash_gbp;total=sum(a.cash_gbp for a in r.club_finances.values())
        with s._world.transaction():
            assert settle_due_installments(s._world,due-timedelta(days=1))==0
            assert settle_due_installments(s._world,due)==1
            assert settle_due_installments(s._world,due)==0
        assert r.club_finances[manager].cash_gbp==old-amount
        assert sum(a.cash_gbp for a in r.club_finances.values())==total
        assert r.transfer_offers[d.deal_id].installments_paid==i+1
    assert paid_deferred(r.transfer_offers[d.deal_id])==600003
    assert finance_summary(r,manager,dates[-1][0])['outstanding_payable_gbp']==0
    r.validate()


def test_settlement_transaction_rollback_and_reapply(s):
    d=complete(s);r=s._world_squads;before=deepcopy(r.club_finances)
    with pytest.raises(RuntimeError,match='abort'):
        with s._world.transaction():
            settle_due_installments(s._world,schedule(d.terms,d.settled_on)[0][0]);raise RuntimeError('abort')
    assert r.club_finances==before and r.transfer_offers[d.deal_id]==d
    with s._world.transaction():assert settle_due_installments(s._world,schedule(d.terms,d.settled_on)[0][0])==1


def test_installment_commitments_survive_reload_and_resale(s):
    d=complete(s);r=s._world_squads
    buyer=next(c for c in r.clubs if c not in (d.buyer_id,d.seller_id) and r.identities[c].tier==1)
    p=r.clubs[d.buyer_id].squad.remove(d.player_id)
    # The real transfer is covered separately. Move the canonical object to
    # exercise an existing liability after a subsequent registration change.
    p=p or s.home_club.squad._players.get(d.player_id)
    if p is None:
        raise AssertionError('Squad.remove must return player for this fixture')
    r.clubs[buyer].squad.add(p);r.contracts[p.id]=replace(r.contracts[p.id],club_id=buyer)
    with s._world.transaction():assert settle_due_installments(s._world,schedule(d.terms,d.settled_on)[0][0])==1
    assert r.transfer_offers[d.deal_id].installments_paid==1


def test_roundtrip_preserves_debt_and_tolerance(s):
    d=complete(s);talk=submit(s)
    with s._world.transaction():settle_due_installments(s._world,schedule(d.terms,d.settled_on)[0][0])
    graph=capture_manager_graph(s);assert graph['version']==GRAPH_VERSION==29
    loaded=restore_manager_graph(graph)
    assert loaded._world_squads.transfer_offers==s._world_squads.transfer_offers
    with loaded._world.transaction():assert settle_due_installments(loaded._world,schedule(d.terms,d.settled_on)[0][0])==0
    loaded._world_squads.validate()


def test_v26_migration_initializes_new_fields_without_resetting_old_data(s):
    d=submit(s);graph=capture_manager_graph(s);graph['version']=26
    names={'football_manager.domain.transfer_negotiation:TransferTerms':('installments_gbp','installment_count','installment_interval_months'),
        'football_manager.domain.transfer_negotiation:TransferNegotiation':('tolerance_remaining','settled_on','installments_paid'),
        'football_manager.domain.football_world:FootballWorld':('transfer_interest_review_on',)}
    for n in graph['nodes']:
        for key in names.get(n.get('class'),()):n['fields'].pop(key,None)
    loaded=restore_manager_graph(graph);d2=loaded._world_squads.transfer_offers[d.deal_id]
    assert d2.tolerance_remaining==100 and d2.terms.installments_gbp==0
    assert d2.events==d.events and loaded.current_date==s.current_date
    assert loaded.home_club.squad.get(s.home_club.squad.players[0].id).state==s.home_club.squad.players[0].state
    loaded._world_squads.validate()


def test_credit_counts_existing_guaranteed_commitments(s):
    r=s._world_squads;mid=s.home_club.id;before=deferred_capacity(r,mid,s.current_date);d=complete(s)
    assert deferred_capacity(r,mid,s.current_date)==before-d.terms.installments_gbp
    t=TransferTerms(0,installments_gbp=before,installment_count=2,installment_interval_months=6)
    with pytest.raises(ValueError,match='credit'):validate_financing(r,mid,t,s.current_date)


def test_calendar_skips_decisions_without_selling_players(s):
    d=submit(s);today=s.current_date;target_day=today+timedelta(days=10);events=[]
    result=simulate_until(s,target_day,on_day=lambda day,rows:events.append((day,rows)))
    assert not result['stopped_for_decision'] and s.current_date==target_day
    assert result['managed_matches']==0 and any(x['deal_id']==d.deal_id for x in result['decisions'])
    assert events and events[-1][0]==target_day
    assert progression_read_model(s)['resume_target'] is None
    negotiate(s,{'action':'withdraw','deal_id':d.deal_id})
    assert not any(x['deal_id']==d.deal_id for x in pending_transfer_decisions(s))


def test_market_clock_is_idempotent_and_transactional(s):
    r=s._world_squads;before=(r.transfer_interest_review_on,dict(r.transfer_offers),r.transfer_next_id)
    day=s.current_date+timedelta(days=2)
    with pytest.raises(RuntimeError,match='abort'):
        with s._world.transaction():advance_transfer_activity(s._world,day);raise RuntimeError('abort')
    assert before==(r.transfer_interest_review_on,r.transfer_offers,r.transfer_next_id)
    with s._world.transaction():advance_transfer_activity(s._world,day)
    after=(r.transfer_interest_review_on,dict(r.transfer_offers),r.transfer_next_id)
    with s._world.transaction():assert advance_transfer_activity(s._world,day)==0
    assert after==(r.transfer_interest_review_on,r.transfer_offers,r.transfer_next_id)


def test_incoming_interest_is_real_and_never_auto_sells_managed_players(s):
    r=s._world_squads;mid=s.home_club.id
    # Explicitly funded buyers: the fixture has needs but finances would otherwise
    # rule some out. No arbitrary offer quota is imposed on ordinary careers.
    for cid,a in list(r.club_finances.items()):
        if cid!=mid:r.club_finances[cid]=replace(a,cash_gbp=1_000_000_000,transfer_budget_gbp=200_000_000,wage_budget_weekly_gbp=10_000_000)
    before={p.id for p in s.home_club.squad.players}
    with s._world.transaction():count=create_incoming_interest(s._world,s.current_date)
    assert count>0
    incoming=[d for d in r.transfer_offers.values() if d.seller_id==mid and d.status=='manager_turn']
    assert incoming and all(d.proposed_by==d.buyer_id for d in incoming)
    assert {p.id for p in s.home_club.squad.players}==before
    assert any(x['kind']=='incoming_offer' for x in pending_transfer_decisions(s))
    with s._world.transaction():create_incoming_interest(s._world,s.current_date)
    pairs=[(d.player_id,d.buyer_id) for d in r.transfer_offers.values() if d.seller_id==mid and d.status=='manager_turn']
    assert len(pairs)==len(set(pairs))


def test_expiry_releases_pending_offers_but_not_completed_debt(s):
    d=complete(s);talk=submit(s);through=talk.expires_on+timedelta(days=1)
    with s._world.transaction():advance_transfer_activity(s._world,through)
    assert s._world_squads.transfer_offers[talk.deal_id].status=='expired'
    assert s._world_squads.transfer_offers[d.deal_id].status=='completed'
    assert finance_summary(s._world_squads,s.home_club.id,through)['outstanding_payable_gbp']==600003


@pytest.mark.parametrize('mechanism',['gross','profit'])
def test_sell_on_settlement_uses_received_cash_and_guaranteed_acquisition_cost(s,mechanism):
    from football_manager.services.transfer_personal import _sell_on_payout
    r=s._world_squads;mid=s.home_club.id
    first=complete(s,TransferTerms(100_000,sell_on_type=mechanism,sell_on_percent=20,
        installments_gbp=600_003,installment_count=4,installment_interval_months=6))
    other=next(c for c in r.clubs if c not in (first.seller_id,mid) and r.identities[c].tier==1)
    a=r.club_finances[other];r.club_finances[other]=replace(a,cash_gbp=1_000_000_000,
        transfer_budget_gbp=100_000_000,wage_budget_weekly_gbp=10_000_000)
    second=_create_offer(r,first.player_id,mid,other,s.current_date,
        TransferTerms(200_000,installments_gbp=1_000_004,installment_count=4,installment_interval_months=6),mid)
    r.transfer_offers[second.deal_id]=replace(second,status='agreed')
    result=negotiate(s,{'action':'personal_resolve','deal_id':second.deal_id})
    assert result['status']=='completed'
    assert not s.home_club.squad.contains(first.player_id)
    second=r.transfer_offers[second.deal_id]
    assert second.sell_on_paid_gbp==(40_000 if mechanism=='gross' else 0)
    # Original installments are STILL owed even though the player has moved on.
    assert finance_summary(r,mid,s.current_date)['outstanding_payable_gbp']==600003
    for index,(day,amount) in enumerate(schedule(second.terms,second.settled_on)):
        before=sum(a.cash_gbp for a in r.club_finances.values())
        with s._world.transaction():assert settle_due_installments(s._world,day)==2
        assert sum(a.cash_gbp for a in r.club_finances.values())==before
        updated=r.transfer_offers[second.deal_id]
        proceeds=updated.terms.fixed_gbp+paid_deferred(updated)
        basis=proceeds if mechanism=='gross' else max(0,proceeds-first.terms.guaranteed_gbp)
        assert updated.sell_on_paid_gbp==round(basis*.20)
        assert _sell_on_payout(r,updated)[1]==0
    assert r.transfer_offers[first.deal_id].installments_paid==4
    r.validate()


def test_result_stream_does_not_lose_results_while_skipping_decisions(s,monkeypatch):
    import football_manager.ui_shell.progression as progression
    from types import SimpleNamespace
    r=s._world_squads
    for key,d in list(r.transfer_offers.items()):
        if s.home_club.id in (d.seller_id,d.buyer_id) and d.status in ('manager_turn','agreed'):
            r.transfer_offers[key]=replace(d,status='withdrawn')
    # Do not simulate a full world to test this control-flow boundary. A fixture
    # and a decision arriving in _move_day must both survive the next loop check.
    fid='fix02-interruption-fixture';captured=[]
    monkeypatch.setattr(progression,'_finish_day',lambda *_:0)
    def move(session):
        session.current_date+=timedelta(days=1)
        session._world.fixtures[fid]=SimpleNamespace(kickoff=None,match_date=session.current_date,
            home_club_id='test-a',away_club_id='test-b',competition_id='test-cup')
        session._world.results[fid]=SimpleNamespace(home_goals=2,away_goals=1,
            penalties_home=None,penalties_away=None,resolver='test-fixture')
        cid,p=target(session)
        _create_offer(r,p.id,cid,session.home_club.id,session.current_date,TransferTerms(100000),cid)
        return 1
    monkeypatch.setattr(progression,'_move_day',move)
    out=simulate_until(s,s.current_date+timedelta(days=4),on_day=lambda day,rows:captured.extend(rows))
    assert not out['stopped_for_decision'] and any(x['id']==fid for x in captured)
    assert len([x for x in captured if x['id']==fid])==1


def test_counter_rounds_generate_distinct_inbox_updates_without_read_side_effects(s):
    from football_manager.services.manager_inbox import synchronize_manager_inbox, inbox_read_model
    d=submit(s);synchronize_manager_inbox(s)
    first=len([m for m in s.manager_inbox.messages if m.source_key.startswith('offer:'+d.deal_id+':')])
    negotiate(s,{'action':'counter','deal_id':d.deal_id,'terms':{'fixed_gbp':0}})
    synchronize_manager_inbox(s)
    rows=[m for m in s.manager_inbox.messages if m.source_key.startswith('offer:'+d.deal_id+':')]
    assert len(rows)==first+1 and 'upfront' in rows[-1].body
    before=len(s.manager_inbox.messages)
    inbox_read_model(s);inbox_read_model(s);synchronize_manager_inbox(s)
    assert len(s.manager_inbox.messages)==before


def test_completed_calendar_target_is_valid_persistent_career_state(s,tmp_path):
    from football_manager.persistence.manager_career import validate_manager_session,save_manager_career,load_manager_career
    from football_manager.persistence import SQLiteSaveRepository
    submit(s);target_day=s.current_date+timedelta(days=10)
    simulate_until(s,target_day);validate_manager_session(s)
    repo=SQLiteSaveRepository(tmp_path/'calendar-pause.sqlite3')
    save_manager_career(repo,slot_id='pause',display_name='Pause',session=s,expected_revision=0)
    restored=load_manager_career(repo,'pause').session
    assert progression_read_model(restored)['resume_target'] is None
    assert restored.current_date==target_day
    assert pending_transfer_decisions(restored)==pending_transfer_decisions(s)
    validate_manager_session(restored)


def test_new_inbox_includes_existing_actionable_offers_without_duplicates(s):
    from football_manager.services.manager_inbox import create_manager_inbox,synchronize_manager_inbox
    d=submit(s);s.manager_inbox=create_manager_inbox(s)
    rows=[m for m in s.manager_inbox.messages if m.source_key.startswith('offer:'+d.deal_id+':')]
    assert len(rows)==1 and 'upfront' in rows[0].body
    before=len(s.manager_inbox.messages);synchronize_manager_inbox(s)
    assert len(s.manager_inbox.messages)==before
