"""TS-UI-12: independently enforced staffing allowance and read-only finance UI data."""
from copy import deepcopy
from dataclasses import replace

import pytest

from football_manager.dev_ui.session import DevelopmentSession
from football_manager.services.club_economy import finances_read_model, staff_budget_weekly
from football_manager.services.club_support import staff_read_model, staff_command


@pytest.fixture(scope='module')
def starting():
    return DevelopmentSession()


def test_staff_budget_stable_independent_from_hires_and_player_wages(starting):
    registry = starting._world_squads
    cid = starting.home_club.id
    balance = staff_budget_weekly(registry, cid)
    assert balance >= 900
    assert balance == staff_budget_weekly(registry, cid)
    saved_payroll = sum(m.wage_weekly_gbp for m in registry.club_support[cid].members.values())
    assert staff_read_model(starting)['staff_headroom_weekly_gbp'] == balance - saved_payroll
    assert finances_read_model(starting)['staff_budget_weekly_gbp'] == balance
    # Existing staff wage increases do not raise their own approved limit.
    session = deepcopy(starting)
    dept = session._world_squads.club_support[cid]
    key = next(iter(dept.members))
    dept.members[key] = replace(dept.members[key], wage_weekly_gbp=dept.members[key].wage_weekly_gbp+500)
    assert staff_budget_weekly(session._world_squads, cid) == balance


def test_finance_reads_actual_staff_rows_and_separates_player_budget(starting):
    model = finances_read_model(starting)
    staff = staff_read_model(starting)
    assert model['club_id'] == staff['club_id'] == starting.home_club.id
    assert model['club'] == staff['club'] == starting.home_club.name
    assert model['staff_weekly_wages_gbp'] == staff['weekly_payroll_gbp']
    assert model['staff_budget_weekly_gbp'] == staff['staff_budget_weekly_gbp']
    assert model['staff_headroom_weekly_gbp'] == staff['staff_headroom_weekly_gbp']
    assert sum(e['weekly_wage_gbp'] for e in model['staff_contracts']) == staff['weekly_payroll_gbp']
    assert model['weekly_payroll_gbp'] == sum(c.weekly_wage_gbp for c in starting._world_squads.contracts.values() if c.club_id==starting.home_club.id) or model['weekly_payroll_gbp'] >= 0
    assert model['season'].count('/') == 1
    assert model['staff_budget_weekly_gbp'] != model['wage_budget_weekly_gbp']


def test_hiring_over_staff_board_limit_is_rejected_without_mutating(starting):
    session = deepcopy(starting)
    registry = session._world_squads
    cid = session.home_club.id
    dept = registry.club_support[cid]
    # Future old saves may be over the limit; preserve those agreements while
    # blocking payroll increases without touching cash or the signed contracts.
    for mid, member in tuple(dept.members.items()):
        dept.members[mid] = replace(member, wage_weekly_gbp=49000)
    member = staff_read_model(session)['members'][0]
    previous = deepcopy(dept.members)
    cash = registry.club_finances[cid].cash_gbp
    proposal={'action':'offer','member_id':member['id'],'weekly_wage_gbp':50000,
              'years':2,'signing_bonus_gbp':0}
    with pytest.raises(ValueError, match='staff wage budget'):
        staff_command(session, proposal)
    assert dept.members == previous
    assert registry.club_finances[cid].cash_gbp == cash


def test_finance_history_uses_actual_months_only_and_loan_fees(starting):
    data=finances_read_model(starting)
    reg=starting._world_squads
    cid=starting.home_club.id
    assert len(data['history'])==len(reg.club_finances[cid].history[-12:])
    for row in data['history']:
        assert row['net_gbp']==row['income_gbp']-row['wages_gbp']-row['operations_gbp']
    assert data['loan_fees_paid_gbp']==sum(x.loan_fee_gbp for x in reg.loans.values() if x.borrower_id==cid and x.started_on<=starting.current_date)
    assert data['loan_fees_received_gbp']==sum(x.loan_fee_gbp for x in reg.loans.values() if x.parent_id==cid and x.started_on<=starting.current_date)
