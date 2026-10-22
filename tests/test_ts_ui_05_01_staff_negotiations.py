"""TS-UI-05.01: negotiated staff employment, club finances, identity and persistence."""
from copy import deepcopy
from datetime import timedelta
from pathlib import Path

import pytest

from football_manager.dev_ui.session import DevelopmentSession
from football_manager.persistence.session_codec import capture_manager_graph, restore_manager_graph
from football_manager.services.club_support import staff_read_model, staff_command
from football_manager.services.club_economy import finances_read_model, review_finances


@pytest.fixture(scope='module')
def starting():
    return DevelopmentSession()


def offer(member, *, wage=None, bonus=0, years=2):
    return {'action':'offer', 'member_id':member['id'],
            'weekly_wage_gbp':wage if wage is not None else min(50000, member['wage_demand_weekly_gbp']+600),
            'years':years, 'signing_bonus_gbp':bonus}


def test_market_and_club_identity_are_real_and_stable(starting):
    before = staff_read_model(starting)
    assert before['club_id'] == starting.home_club.id
    assert before['club'] == starting.home_club.name
    assert before['weekly_payroll_gbp'] == finances_read_model(starting)['staff_weekly_wages_gbp']
    assert len(before['market']['medic']) == 8
    assert len({m['name'] for m in before['market']['medic']}) == 8
    assert before == staff_read_model(starting)


def test_lowball_is_declined_with_counter_and_no_side_effects(starting):
    session = deepcopy(starting)
    candidate = staff_read_model(session)['market']['medic'][0]
    dept = session._world_squads.club_support[session.home_club.id]
    account = session._world_squads.club_finances[session.home_club.id]
    snapshot = set(dept.members), account
    result = staff_command(session, offer(candidate, wage=100))
    assert not result['accepted']
    assert result['counter_wage_weekly_gbp'] >= 100
    assert (set(dept.members), session._world_squads.club_finances[session.home_club.id]) == snapshot
    assert staff_command(session, offer(candidate, wage=100)) == result
    with pytest.raises(ValueError, match='require a negotiated'):
        staff_command(session, {'action':'hire','member_id':candidate['id']})


def test_hiring_changes_real_payroll_deducts_bonus_and_survives_save(starting):
    session = deepcopy(starting)
    cid = session.home_club.id
    candidate = staff_read_model(session)['market']['scout'][0]
    before = staff_read_model(session)['weekly_payroll_gbp']
    cash = session._world_squads.club_finances[cid].cash_gbp
    result = staff_command(session, offer(candidate, bonus=1000, years=3))
    assert result['accepted'] and result['kind'] == 'appointment'
    wage = result['weekly_wage_gbp']
    assert staff_read_model(session)['weekly_payroll_gbp'] == before + wage
    assert finances_read_model(session)['staff_weekly_wages_gbp'] == before + wage
    assert session._world_squads.club_finances[cid].cash_gbp == cash - 1000
    staff = session._world_squads.club_support[cid].members[candidate['id']]
    assert (staff.contract_until-session.current_date).days == 365*3
    assert staff.wage_weekly_gbp == wage
    restored = restore_manager_graph(capture_manager_graph(session))
    assert restored._world_squads.club_support[cid].members[candidate['id']] == staff
    assert restored._world_squads.club_finances[cid].cash_gbp == cash - 1000
    assert candidate['id'] not in {item['id'] for item in staff_read_model(session)['market']['scout']}


def test_existing_staff_extension_requires_negotiated_terms(starting):
    session = deepcopy(starting)
    cid = session.home_club.id
    employee = staff_read_model(session)['members'][0]
    prior = session._world_squads.club_support[cid].members[employee['id']]
    rejected = staff_command(session, offer(employee, wage=100))
    assert rejected['accepted'] is False
    assert session._world_squads.club_support[cid].members[employee['id']] == prior
    accepted = staff_command(session, offer(employee, years=1, bonus=0))
    assert accepted['accepted']
    assert accepted['kind'] == 'extension'
    revised = session._world_squads.club_support[cid].members[employee['id']]
    assert revised.contract_until == prior.contract_until + timedelta(days=365)
    assert revised.wage_weekly_gbp == accepted['weekly_wage_gbp']
    with pytest.raises(ValueError, match='require a negotiated'):
        staff_command(session, {'action':'renew','member_id':employee['id']})


def test_invalid_terms_capacity_and_insufficient_cash_do_not_mutate(starting):
    session = deepcopy(starting)
    cid = session.home_club.id
    member = staff_read_model(session)['market']['coach'][0]
    for bad in (-1, 0, 23.5, 50001):
        with pytest.raises(ValueError):
            staff_command(session, offer(member, wage=bad))
    for bad in ('2', 0, 5):
        with pytest.raises(ValueError):
            staff_command(session, offer(member, years=bad))
    with pytest.raises(ValueError):
        staff_command(session, offer(member, bonus=-1))
    account = session._world_squads.club_finances[cid]
    from dataclasses import replace
    session._world_squads.club_finances[cid] = replace(account, cash_gbp=100)
    with pytest.raises(ValueError, match='cash'):
        staff_command(session, offer(member))
    assert member['id'] not in session._world_squads.club_support[cid].members


def test_monthly_wage_charges_include_new_staff(starting):
    session = deepcopy(starting)
    candidate = staff_read_model(session)['market']['medic'][0]
    hired = staff_command(session, offer(candidate))
    assert hired['accepted']
    registry = session._world_squads
    old = registry.finance_review_on
    with session._world.transaction():
        review_finances(session._world, old + timedelta(days=32))
    wages = registry.club_finances[session.home_club.id].history[-1].wages_gbp
    assert wages >= hired['weekly_wage_gbp'] * 3


def test_staff_visual_uses_dynamic_crest_and_club_palette():
    base = Path(__file__).resolve().parents[1]
    js = (base/'frontend/portable/club_support.js').read_text()
    css = (base/'frontend/portable/club_support.css').read_text()
    assert 'FMClubIdentity?.resolve' in js
    assert 'st-club-crest' in js and 'identity.crest' in js
    assert 'st-hero' in css and 'var(--ui-club-rgb' in css
    image = base/'frontend/portable/assets/staff/football-analysis-room.webp'
    assert image.is_file() and image.stat().st_size > 10000


def test_staff_changes_reflected_in_training_and_medical(starting):
    from football_manager.services.club_support import training_read_model, medical_read_model
    session = deepcopy(starting)
    before_train = training_read_model(session)['training_staff']
    before_medical = medical_read_model(session)['staffing']
    coach = staff_read_model(session)['market']['coach'][0]
    medic = staff_read_model(session)['market']['medic'][0]
    assert staff_command(session, offer(coach))['accepted']
    assert staff_command(session, offer(medic))['accepted']
    assert training_read_model(session)['training_staff']['coaches'] == before_train['coaches'] + 1
    assert medical_read_model(session)['staffing']['medical'] == before_medical['medical'] + 1


def test_application_staff_command_uses_same_negotiation_and_updates_runtime(starting):
    from football_manager.ui_shell.runtime import UIRuntime
    from football_manager.ui_shell.application import GameApplication
    runtime = UIRuntime(deepcopy(starting))
    app = GameApplication(runtime, prematch_builder=lambda *_: {})
    person = staff_read_model(runtime.session)['market']['fitness'][0]
    declined = app.command('staff.command',offer(person,wage=100))
    assert declined['accepted'] is False
    assert person['id'] not in runtime.session._world_squads.club_support[runtime.session.home_club.id].members
    accepted = app.command('staff.command',offer(person))
    assert accepted['accepted'] is True
    assert person['id'] in runtime.session._world_squads.club_support[runtime.session.home_club.id].members
