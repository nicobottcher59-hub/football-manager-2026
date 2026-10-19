"""TS-24.12 audit contracts: do not convert imperfect AI decisions into fabricated fixes."""
from __future__ import annotations
from copy import deepcopy
from datetime import date
from pathlib import Path
import sys
import pytest

TOOLS=Path(__file__).resolve().parents[1]/'tools'
sys.path.insert(0,str(TOOLS))
from run_ts2412_validation import (
    classify_checkpoint, manager_promote_real_academy_players,
    choose_manager_promotion, audit_world,
)
from football_manager.dev_ui.session import DevelopmentSession
from football_manager.persistence import SQLiteSaveRepository, save_manager_career, load_manager_career
from football_manager.persistence.manager_career import MANAGER_STATE_VERSION, _REQUIRED_FIELDS
from football_manager.services.loan_market import process_ai_loans

@pytest.fixture(scope='module')
def baseline():
    return DevelopmentSession(world_seed=6606)


def test_incomplete_squad_and_cash_loss_are_not_invented_technical_failures():
    snap={'hard_issues':['2 active clubs cannot cover all XI starter positions',
                         '9 clubs have fewer than two natural goalkeepers',
                         'at least one club has fewer than 18 first-team players'],
          'fixtures':800,'completed_fixtures':800,
          'cash_min_gbp':-350_000,'first_team_players_over_45':0}
    result=classify_checkpoint(snap)
    assert result['structural_failures']==[]
    assert len(result['sporting_risks'])==2
    assert len(result['squad_warnings'])==1
    assert result['financial_risks']==[]


def test_repeat_bankruptcy_is_surfaced_as_risk_not_hidden():
    snap={'hard_issues':[],'fixtures':100,'completed_fixtures':100,
          'cash_min_gbp':-250_000_000,'first_team_players_over_45':2}
    result=classify_checkpoint(snap)
    assert not result['structural_failures']
    assert result['financial_risks'] and 'below GBP -100m' in result['financial_risks'][0]
    assert result['squad_warnings']


def test_widespread_missing_second_keeper_is_sporting_risk_not_a_fabricated_fix():
    snap={'hard_issues':['13 clubs have fewer than two natural goalkeepers'],
          'fixtures':800,'completed_fixtures':800,'clubs_below_two_goalkeepers':13,
          'cash_min_gbp':0,'first_team_players_over_45':0}
    classified=classify_checkpoint(snap)
    assert not classified['structural_failures']
    assert classified['squad_warnings']
    assert any('widespread depth' in finding for finding in classified['sporting_risks'])


def test_duplication_and_unfinished_competition_are_technical_failures():
    snap={'hard_issues':['a player is registered by more than one first team'],
          'fixtures':120,'completed_fixtures':119,
          'cash_min_gbp':0,'first_team_players_over_45':0}
    result=classify_checkpoint(snap)
    assert len(result['structural_failures'])==2


def test_existing_youth_are_promoted_by_explicit_test_manager_action(baseline):
    session=deepcopy(baseline)
    candidate=choose_manager_promotion(session)
    assert candidate is not None
    cid=session.home_club.id
    ai_before={c:tuple(p.id for p in team.squad.players)
               for c,team in session._world_squads.clubs.items() if c!=cid}
    original_first={p.id for p in session.home_club.squad.players}
    count=len(original_first)
    records=manager_promote_real_academy_players(session,target_size=count+1,max_per_year=1)
    assert len(records)==1
    assert records[0]['player_id']==candidate.id
    assert records[0]['via']=='explicit_youth_command'
    assert session.home_club.squad.get(candidate.id) is candidate
    assert {p.id for p in session.home_club.squad.players}==original_first|{candidate.id}
    assert ai_before=={c:tuple(p.id for p in team.squad.players)
                       for c,team in session._world_squads.clubs.items() if c!=cid}
    session._world_squads.validate()


def test_empty_academy_does_not_generate_emergency_players(baseline):
    session=deepcopy(baseline)
    academy=session._world_squads.youth.academies[session.home_club.id]
    academy.u21.clear()
    academy.u17.clear()
    prior={p.id for p in session.home_club.squad.players}
    records=manager_promote_real_academy_players(session,target_size=len(prior)+4)
    assert records==[]
    assert {p.id for p in session.home_club.squad.players}==prior


def test_sqlite_v16_preserves_ai_loans_and_real_parent_employer(baseline,tmp_path):
    session=deepcopy(baseline)
    session.current_date=date(2026,9,1)
    with session._world.transaction():
        deals=process_ai_loans(session._world,session.current_date)
    assert deals
    # Refresh ephemeral next-opponent preview after market operations before saving.
    session._prepare_development_opponent()
    assert set(vars(session))==_REQUIRED_FIELDS and MANAGER_STATE_VERSION==17
    repo=SQLiteSaveRepository(tmp_path/'ts2412.sqlite3')
    save_manager_career(repo,slot_id='audit',display_name='Audit only',
                        expected_revision=0,session=session)
    loaded=load_manager_career(repo,'audit').session
    assert set(vars(loaded))==_REQUIRED_FIELDS
    for deal in deals:
        loan=loaded._world_squads.loans[deal['loan_id']]
        assert loan.status=='active'
        assert loaded._world_squads.contracts[loan.player_id].club_id==loan.parent_id
        assert loaded._world_squads.clubs[loan.borrower_id].squad.contains(loan.player_id)
        assert not loaded._world_squads.clubs[loan.parent_id].squad.contains(loan.player_id)
    loaded._world_squads.validate()


def test_audit_rejects_invalid_seed_and_horizon_before_expensive_world_build(tmp_path):
    with pytest.raises(ValueError,match='world_seed'):
        audit_world(world_seed=0,seasons=5,output=tmp_path/'bad.json')
    with pytest.raises(ValueError,match='seasons'):
        audit_world(world_seed=42,seasons=21,output=tmp_path/'bad.json')


def test_unplayable_ai_opponent_forfeits_without_resurrecting_players_or_minutes(baseline):
    """A scheduled human-vs-AI match must not crash on an AI with no goalkeeper."""
    from football_manager.domain.enums import Position
    session = deepcopy(baseline)
    original = session._active_match.fixture.fixture_id
    fixture = session._world.fixtures[original]
    opponent_id = (fixture.away_club_id if fixture.home_club_id == session.home_club.id
                   else fixture.home_club_id)
    opponent = session._world_squads.clubs[opponent_id]
    previous_players = tuple(p.id for p in opponent.squad.players)
    previous_usage = dict(session._world_squads.usage)
    for player in opponent.squad.players:
        if player.primary_position is Position.GK:
            player.state.suspended_matches = 50
    session._prepare_development_opponent()
    record = session._world.results[original]
    assert record.resolver == 'administrative'
    assert record.home_goals == 3 and record.away_goals == 0
    assert original not in session._world_squads.processed_fixtures
    assert tuple(p.id for p in opponent.squad.players) == previous_players
    assert session._active_match is None or session._active_match.fixture.fixture_id != original
    for pid in previous_usage:
        # A default must not invent minutes for the affected players.
        if pid in previous_players:
            assert session._world_squads.usage.get(pid) == previous_usage[pid]
    session._world.validate_integrity()
    session._world_squads.validate()
    assert set(vars(session)) == _REQUIRED_FIELDS


def test_unplayable_ai_opponent_does_not_override_manager_squad_responsibility(baseline):
    from football_manager.domain.enums import Position
    session = deepcopy(baseline)
    fixture_id = session._active_match.fixture.fixture_id
    fixture = session._world.fixtures[fixture_id]
    opponent_id = (fixture.away_club_id if fixture.home_club_id == session.home_club.id
                   else fixture.home_club_id)
    for player in session._world_squads.clubs[opponent_id].squad.players:
        if player.primary_position is Position.GK:
            player.state.suspended_matches = 50
    for player in session.home_club.squad.players:
        if player.primary_position is Position.GK:
            player.state.suspended_matches = 50
    with pytest.raises(ValueError, match='Managed club cannot field'):
        session._prepare_development_opponent()
    assert fixture_id not in session._world.results


def test_unexpected_opponent_selection_failure_is_not_silenced(baseline, monkeypatch):
    import football_manager.services.world_matches as matches
    session = deepcopy(baseline)
    original = session._active_match.fixture.fixture_id
    def broken(*args, **kwargs):
        raise ValueError('bad tactic serialization')
    monkeypatch.setattr(matches, 'opponent_side', broken)
    with pytest.raises(ValueError, match='bad tactic serialization'):
        session._prepare_development_opponent()
    assert original not in session._world.results
