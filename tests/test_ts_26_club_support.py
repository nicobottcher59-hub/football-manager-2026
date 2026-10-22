"""TS-26: staff, training, medical and persistence regression checks."""
from __future__ import annotations

from copy import deepcopy
from datetime import timedelta

import pytest

from football_manager.dev_ui.session import DevelopmentSession
from football_manager.domain.club_support import ROLES
from football_manager.persistence.manager_career import validate_manager_session
from football_manager.persistence.session_codec import capture_manager_graph, restore_manager_graph
from football_manager.services.club_support import (
    staff_command, staff_read_model, training_command, training_read_model,
    medical_command, medical_read_model, recover_managed_players,
)
from football_manager.services.player_aging import register_medical_absence, recover_medical_absences
from football_manager.services.club_economy import review_finances
from football_manager.services.manager_inbox import synchronize_manager_inbox


@pytest.fixture(scope='module')
def starting():
    return DevelopmentSession()


def fresh(starting):
    return deepcopy(starting)


def test_initialized_departments_are_bounded_and_saveable(starting):
    registry = starting._world_squads
    assert set(registry.club_support) == set(registry.clubs)
    for support in registry.club_support.values():
        support.validate()
        assert {m.role for m in support.members.values()} == set(ROLES)
        assert all(support.capacity[r] >= 1 for r in ROLES)
    assert staff_read_model(starting)['capacity_source'].startswith('provisional')
    validate_manager_session(starting)


def test_hiring_releasing_and_capacity_are_real(starting):
    session = fresh(starting)
    dept = session._world_squads.club_support[session.home_club.id]
    data = staff_read_model(session)
    role = next(role for role in ROLES if data['capacity'][role] > 1)
    first = data['market'][role][0]['id']
    demanded = data['market'][role][0]['wage_demand_weekly_gbp']
    hired = staff_command(session, {'action':'offer','member_id':first,'weekly_wage_gbp':min(50000,demanded+750),'years':2,'signing_bonus_gbp':0})
    assert hired['accepted'] and hired['member_id'] == first
    assert len([m for m in staff_read_model(session)['members'] if m['role'] == role]) == 2
    assert first not in {m['id'] for m in staff_read_model(session)['market'][role]}
    while len([m for m in staff_read_model(session)['members'] if m['role'] == role]) < dept.capacity[role]:
        ident = next(m['id'] for m in staff_read_model(session)['market'][role] if m['id'] not in dept.members)
        terms=next(m for m in staff_read_model(session)['market'][role] if m['id']==ident)
        assert staff_command(session, {'action':'offer','member_id':ident,'weekly_wage_gbp':min(50000,terms['wage_demand_weekly_gbp']+750),'years':2,'signing_bonus_gbp':0})['accepted']
    next_ident = next((m['id'] for m in staff_read_model(session)['market'][role] if m['id'] not in dept.members), None)
    if next_ident:
        with pytest.raises(ValueError,match='places'):
            staff_command(session, {'action':'offer','member_id':next_ident,'weekly_wage_gbp':10000,'years':2,'signing_bonus_gbp':0})
    balance = session._world_squads.club_finances[session.home_club.id].cash_gbp
    released = staff_command(session, {'action':'release','member_id':first})
    assert released['settlement_gbp'] > 0
    assert session._world_squads.club_finances[session.home_club.id].cash_gbp == balance-released['settlement_gbp']
    session._world_squads.validate()


def test_unified_auto_training_and_personal_override(starting):
    session=fresh(starting)
    target=session.home_lineup.starters[0].player
    target.state.fitness=45.;target.state.fatigue=40.
    info=next(p for p in training_read_model(session)['players'] if p['id']==target.id)
    assert info['effective']=='light' and info['intensity_source']=='automatic'
    automatic=deepcopy(session);personal=deepcopy(session)
    training_command(personal,{'action':'individual','player_id':target.id,'intensity':'intense'})
    recover_managed_players(automatic,days=1);recover_managed_players(personal,days=1)
    assert (personal._world_squads.club_support[session.home_club.id].training_days[target.id][0]
            > automatic._world_squads.club_support[session.home_club.id].training_days[target.id][0])
    with pytest.raises(ValueError):training_command(session,{'action':'configure','group':'starters','intensity':'intense'})


def injured_session(starting, episode_id='ts26-test-episode'):
    session = fresh(starting)
    player = session.home_club.squad.players[0]
    register_medical_absence(session._world, session.home_club.id, player.id,
                             session.current_date, episode_id=episode_id,
                             duration_days=28, label='Muscle strain')
    return session, player


def test_conservative_medical_is_safer_and_player_opinion_is_moderate(starting):
    session, player = injured_session(starting, 'ts26-conservative')
    original = player.aging.active_injury.return_on
    data = medical_read_model(session)['cases'][0]
    assert data['treatment_available'] and data['days_left'] == 28
    morale = player.state.morale
    decision = medical_command(session, {'action':'treat','method':'conservative','player_id':player.id})
    assert decision['return_on'] == original.isoformat()
    assert decision['estimated_risk_pct'] == 0
    assert abs(player.state.morale-morale) <= 1.
    assert not medical_read_model(session)['cases'][0]['treatment_available']
    with pytest.raises(ValueError):
        medical_command(session, {'action':'treat','method':'conservative','player_id':player.id})
    session._world_squads.validate()
    validate_manager_session(session)


def test_aggressive_medical_persists_and_deterministically_resolves(starting):
    session, player = injured_session(starting, 'ts26-aggressive')
    original = player.aging.active_injury.return_on
    decision = medical_command(session, {'action':'treat','method':'aggressive','player_id':player.id})
    assert decision['return_on'] < original.isoformat()
    graph = capture_manager_graph(session)
    loaded = restore_manager_graph(graph)
    p = loaded.home_club.squad.get(player.id)
    plan = loaded._world_squads.club_support[loaded.home_club.id].treatments[player.id]
    assert plan.relapse_risk > 0 and p.aging.active_injury.return_on == plan.planned_return
    due = plan.planned_return
    recover_medical_absences(loaded._world, due)
    if plan.will_relapse:
        assert p.aging.active_injury.return_on == due+timedelta(days=plan.relapse_days)
        assert plan.status == 'relapsed'
        loaded.current_date = due
        synchronize_manager_inbox(loaded)
        assert any(m.source_key == f'treatment:relapse:{plan.episode_id}' for m in loaded.manager_inbox.messages)
        recover_medical_absences(loaded._world, due+timedelta(days=plan.relapse_days))
    assert p.state.injury is None and plan.status == 'completed'
    loaded._world_squads.validate()


def test_staff_wages_are_real_and_overhead_not_double_charged(starting):
    session = fresh(starting)
    registry = session._world_squads
    cid = session.home_club.id
    before = registry.club_finances[cid]
    payroll = staff_read_model(session)['weekly_payroll_gbp']
    assert payroll > 0
    with session._world.transaction():
        review_finances(session._world, registry.finance_review_on + timedelta(days=32))
    after = registry.club_finances[cid]
    month = after.history[-1]
    assert month.wages_gbp > payroll*3
    assert month.operations_gbp < before.recurring_operations_gbp
    assert 0 < month.income_gbp <= before.recurring_income_gbp


def test_v17_careers_migrate_without_overwriting_existing_gameplay(starting):
    snapshot = capture_manager_graph(starting)
    snapshot['version'] = 17
    for node in snapshot['nodes']:
        if node.get('type') == 'object' and node.get('class') == 'football_manager.domain.football_world:FootballWorld':
            node['fields'].pop('club_support')
    migrated = restore_manager_graph(snapshot)
    assert len(migrated._world_squads.club_support) == len(starting._world_squads.clubs)
    assert migrated.home_club.squad.players[0].id == starting.home_club.squad.players[0].id
    validate_manager_session(migrated)


def test_forced_aggressive_relapse_really_extends_injury_and_notifies(starting):
    session, player = injured_session(starting, 'ts26-forced-relapse')
    medical_command(session, {'action': 'treat', 'method': 'aggressive', 'player_id': player.id})
    plan = session._world_squads.club_support[session.home_club.id].treatments[player.id]
    plan.will_relapse = True
    plan.relapse_days = 11
    first_due = plan.planned_return
    recover_medical_absences(session._world, first_due)
    assert plan.status == 'relapsed'
    assert player.aging.active_injury.return_on == first_due + timedelta(days=11)
    assert player.state.injury is not None
    session.current_date = first_due
    synchronize_manager_inbox(session)
    assert sum(m.source_key == f'treatment:relapse:{plan.episode_id}'
               for m in session.manager_inbox.messages) == 1
    synchronize_manager_inbox(session)
    assert sum(m.source_key == f'treatment:relapse:{plan.episode_id}'
               for m in session.manager_inbox.messages) == 1
    recover_medical_absences(session._world, first_due + timedelta(days=11))
    assert plan.status == 'completed' and player.state.injury is None
    session._world_squads.validate()


def test_ai_staff_renews_automatically_but_manager_stays_in_control(starting):
    from football_manager.services.club_support import auto_extend_ai_staff
    session = fresh(starting)
    registry = session._world_squads
    managed = session.home_club.id
    other = next(cid for cid in registry.club_support if cid != managed)
    ai_staff = next(iter(registry.club_support[other].members.values()))
    managed_staff = next(iter(registry.club_support[managed].members.values()))
    with session._world.transaction():
        updated = auto_extend_ai_staff(session._world,
            ai_staff.contract_until - timedelta(days=30), managed_club_id=managed)
    assert updated > 0
    assert registry.club_support[other].members[ai_staff.member_id].contract_until > ai_staff.contract_until
    assert registry.club_support[managed].members[managed_staff.member_id].contract_until == managed_staff.contract_until
    registry.validate()
