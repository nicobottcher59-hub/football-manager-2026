"""TS-24.11: real loan registration, evidence-based commitments, fixture defaults."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from datetime import date

import pytest

from football_manager.dev_ui.session import DevelopmentSession
from football_manager.domain.enums import Position
from football_manager.domain.football_world import PlayerSeasonUsage
from football_manager.persistence.session_codec import capture_manager_graph, restore_manager_graph
from football_manager.services.loan_market import (
    active_loan, process_ai_loans, loan_promise_review,
    review_loan_month, _finish_loan,
)
from football_manager.services.club_economy import _date_plus_months, weekly_payroll


@pytest.fixture(scope='module')
def original():
    return DevelopmentSession()


def make_loans(initial):
    s=deepcopy(initial)
    with s._world.transaction():
        deals=process_ai_loans(s._world,date(2026,9,1))
    assert deals
    return s,deals


def test_ai_loans_are_consent_based_and_only_between_ai_clubs(original):
    s,deals=make_loans(original)
    r=s._world_squads
    assert 1 <= len(deals) <= 10
    assert len({d['player_id'] for d in deals})==len(deals)
    assert len({d['parent_id'] for d in deals})==len(deals)
    assert all(s.home_club.id not in (d['parent_id'],d['borrower_id']) for d in deals)
    for d in deals:
        loan=r.loans[d['loan_id']]
        assert loan.started_on==date(2026,9,1)
        assert loan.ends_on==_date_plus_months(loan.started_on,d['months'])
        assert loan.playing_time in ('starter','rotation')
        assert 0 <= loan.borrower_wage_percent <= 100
        assert r.clubs[loan.borrower_id].squad.contains(loan.player_id)
        assert not r.clubs[loan.parent_id].squad.contains(loan.player_id)
        assert r.contracts[loan.player_id].club_id==loan.parent_id
        assert active_loan(r,loan.player_id) is loan
    r.validate()


def test_ai_loan_replay_is_deterministic_and_closed_window_is_inert(original):
    s1,d1=make_loans(original)
    s2,d2=make_loans(original)
    assert d1==d2
    with s1._world.transaction():
        assert process_ai_loans(s1._world,date(2026,10,1)) == []
    assert len(s1._world_squads.loans)==len(d1)


def test_ai_loans_wages_are_split_and_restored(original):
    s=deepcopy(original);r=s._world_squads
    original_wages={cid:weekly_payroll(r,cid) for cid in r.clubs}
    with s._world.transaction():
        deals=process_ai_loans(s._world,date(2026,9,1))
    loan=r.loans[deals[0]['loan_id']]
    wage=r.contracts[loan.player_id].weekly_wage_gbp
    subsidy=round(wage*loan.borrower_wage_percent/100)
    assert weekly_payroll(r,loan.parent_id)==original_wages[loan.parent_id]-subsidy
    assert weekly_payroll(r,loan.borrower_id)>=original_wages[loan.borrower_id]+subsidy
    with s._world.transaction():
        _finish_loan(r,loan,date(2027,3,1),world=s._world)
    assert r.clubs[loan.parent_id].squad.contains(loan.player_id)
    assert r.loans[loan.loan_id].status=='returned'
    assert active_loan(r,loan.player_id) is None
    r.validate()


def test_ai_loan_journal_rolls_back_graph_and_id(original):
    s=deepcopy(original);r=s._world_squads
    start=r.loan_next_id
    with pytest.raises(RuntimeError,match='abort'):
        with s._world.transaction():
            loans=process_ai_loans(s._world,date(2026,9,1))
            assert loans
            raise RuntimeError('abort')
    assert not r.loans and r.loan_next_id==start
    for c in r.clubs.values():
        for p in c.squad.players:
            contract=r.contracts.get(p.id)
            assert contract is not None and contract.club_id==c.id
    r.validate()


def test_future_registration_requires_adequate_parent_contract(original):
    s=deepcopy(original);r=s._world_squads
    with s._world.transaction():
        deals=process_ai_loans(s._world,date(2026,9,1))
    assert all(r.contracts[d['player_id']].expires_on >=r.loans[d['loan_id']].ends_on for d in deals)


def test_evidence_gate_does_not_punish_synthetic_zero_minute_seasons(original):
    s,deals=make_loans(original);r=s._world_squads
    loan=r.loans[deals[0]['loan_id']]
    assessment=loan_promise_review(s._world,loan,date(2027,3,1))
    assert assessment['matches']==0 and not assessment['assessable']
    pl=r.clubs[loan.borrower_id].squad.get(loan.player_id)
    initial_morale=pl.state.morale
    with s._world.transaction():
        _finish_loan(r,loan,date(2027,3,1),world=s._world)
    assert pl.state.morale==initial_morale


def test_default_for_ai_missing_keeper_does_not_create_players_or_minutes(original):
    s=deepcopy(original);w=s._world;r=s._world_squads
    fid,fixture=next((fid,f) for fid,f in w.fixtures.items()
                     if f.home_club_id in r.clubs and f.away_club_id in r.clubs and
                     s.home_club.id not in (f.home_club_id,f.away_club_id))
    missing=r.clubs[fixture.home_club_id]
    for player in missing.squad.players:
        if player.primary_position is Position.GK:
            player.state.suspended_matches=50
    before={cid:len(r.clubs[cid].squad) for cid in (fixture.home_club_id,fixture.away_club_id)}
    before_usage=dict(r.usage)
    result=w.simulate_fixture(fid)
    assert result.resolver=='administrative'
    assert result.home_goals==0 and result.away_goals>=3
    assert fid not in r.processed_fixtures
    assert r.usage==before_usage
    assert before=={cid:len(r.clubs[cid].squad) for cid in before}
    restored=restore_manager_graph(capture_manager_graph(s))
    assert restored._world.results[fid].resolver=='administrative'
    r.validate()


def test_manager_missing_keeper_remains_user_decision(original):
    s=deepcopy(original);w=s._world
    fixture=next((fid,f) for fid,f in w.fixtures.items() if s.home_club.id in (f.home_club_id,f.away_club_id))
    for p in s.home_club.squad.players:
        if p.primary_position is Position.GK:p.state.suspended_matches=50
    with pytest.raises(ValueError,match='Managed club cannot field'):
        w.simulate_fixture(fixture[0])
    assert fixture[0] not in w.results


def test_end_of_loan_without_documented_matches_leaves_morale_intact(original):
    s,deals=make_loans(original);r=s._world_squads
    target=r.loans[deals[0]['loan_id']]
    morale=r.clubs[target.borrower_id].squad.get(target.player_id).state.morale
    with s._world.transaction():
        summary=review_loan_month(s._world,date(2027,9,1))
    assert summary['returned']>=1
    assert r.clubs[target.parent_id].squad.get(target.player_id).state.morale==morale
    r.validate()


def test_borrower_never_renews_the_parent_employment_contract(original):
    from football_manager.services.club_economy import auto_renew_ai_contracts
    s,deals=make_loans(original);r=s._world_squads
    target=next((r.loans[d['loan_id']] for d in deals if d['months']==12),None)
    assert target is not None
    old=r.contracts[target.player_id]
    r.contracts[target.player_id]=replace(old,expires_on=target.ends_on)
    with s._world.transaction():
        auto_renew_ai_contracts(s._world,date(2027,7,1),managed_club_id=s.home_club.id)
    assert r.contracts[target.player_id].club_id==target.parent_id
    assert r.contracts[target.player_id].expires_on==target.ends_on
    r.validate()


def test_recorded_games_provide_real_loan_minute_evidence(original):
    s,deals=make_loans(original);w=s._world;r=s._world_squads
    loan=r.loans[deals[0]['loan_id']]
    fixtures=sorted((f for f in w.fixtures.values() if
                     f.match_date is not None and f.match_date>=loan.started_on and
                     loan.borrower_id in (f.home_club_id,f.away_club_id)),
                    key=lambda f:(f.match_date,f.fixture_id))
    assert len(fixtures)>=6
    for f in fixtures[:6]:
        result=w.simulate_fixture(f.fixture_id)
        assert result.resolver=='background'
    reviewed=loan_promise_review(w,loan,date(2026,12,1))
    assert reviewed['matches']==6
    assert reviewed['assessable']
    assert reviewed['minutes']>0
    assert reviewed['ratio']>=.4


def test_material_promise_breach_triggers_ai_parent_recall_and_morale(original,monkeypatch):
    from football_manager.services import loan_market
    s,deals=make_loans(original);r=s._world_squads
    target=next(r.loans[d['loan_id']] for d in deals if d['months']==12)
    player=r.clubs[target.borrower_id].squad.get(target.player_id)
    initial=player.state.morale
    monkeypatch.setattr(loan_market,'loan_promise_review',
                        lambda world,loan,when: {'assessable':loan.loan_id==target.loan_id,
                                                'ratio':0.05,'matches':9,'minutes':40,'target':900})
    with s._world.transaction():
        report=review_loan_month(s._world,date(2027,3,1))
    assert report['breach_recalls']==1
    assert r.loans[target.loan_id].status=='returned'
    assert r.loans[target.loan_id].completed_on<target.ends_on
    assert r.clubs[target.parent_id].squad.get(target.player_id) is player
    assert player.state.morale<initial
    r.validate()


def test_low_minutes_are_not_automatically_punished_before_review_threshold(original,monkeypatch):
    from football_manager.services import loan_market
    s,deals=make_loans(original);r=s._world_squads
    target=next(r.loans[d['loan_id']] for d in deals if d['months']==12)
    player=r.clubs[target.borrower_id].squad.get(target.player_id)
    before=player.state.morale
    monkeypatch.setattr(loan_market,'loan_promise_review',
                        lambda world,loan,when: {'assessable':False,'ratio':0.,'matches':0,'minutes':0,'target':900})
    with s._world.transaction():
        review_loan_month(s._world,date(2027,3,1))
    assert r.loans[target.loan_id].status=='active'
    assert player.state.morale==before
    r.validate()


def test_ai_loan_persists_with_original_contract_and_v16_graph(original):
    from football_manager.persistence.manager_career import _REQUIRED_FIELDS
    s,deals=make_loans(original)
    s.current_date=date(2026,9,1)
    assert set(vars(s))==_REQUIRED_FIELDS
    fresh=restore_manager_graph(capture_manager_graph(s))
    r=fresh._world_squads
    for deal in deals:
        loan=r.loans[deal['loan_id']]
        assert loan.status=='active'
        assert r.contracts[loan.player_id].club_id==loan.parent_id
        assert not r.clubs[loan.parent_id].squad.contains(loan.player_id)
        assert r.clubs[loan.borrower_id].squad.contains(loan.player_id)
    r.validate()
