"""TS-24.9: reproducible seed, credible successors and balance protection."""
from copy import deepcopy
from dataclasses import replace
from datetime import date

import pytest

from football_manager.dev_ui.session import DevelopmentSession
from football_manager.domain.enums import Position
from football_manager.services.ai_squad_planning import imminent_succession_needs, squad_plan
from football_manager.services.club_economy import auto_renew_ai_contracts, weekly_payroll
from football_manager.services.player_aging import finalize_season_retirements


@pytest.fixture(scope='module')
def opening():
    return DevelopmentSession()


def test_default_world_seed_keeps_previous_career_reproducible(opening):
    assert opening._world.seed == 6606
    assert opening._world_squads.seed == 6606
    assert opening._world_squads.validate() is None


def test_seed_is_transient_and_preserves_sqlite_session_field_contract():
    # v16 save format rejects undeclared session fields. The seed must live
    # in the world ledger and never add fields to a loaded manager session.
    from football_manager.persistence.manager_career import _REQUIRED_FIELDS
    s=DevelopmentSession(world_seed=7707)
    assert set(vars(s)) == _REQUIRED_FIELDS
    s.reset()
    assert set(vars(s)) == _REQUIRED_FIELDS
    assert s._world.seed == s._world_squads.seed == 7707


def test_independent_seed_changes_players_and_world_without_changing_leagues(opening):
    alt=DevelopmentSession(world_seed=7707)
    assert alt._world.seed == alt._world_squads.seed == 7707
    assert set(alt._world_squads.clubs) == set(opening._world_squads.clubs)
    first=next(cid for cid in alt._world_squads.clubs if cid != alt.home_club.id)
    a=tuple((p.id,round(p.overall_rating,2)) for p in alt._world_squads.clubs[first].squad.players)
    b=tuple((p.id,round(p.overall_rating,2)) for p in opening._world_squads.clubs[first].squad.players)
    assert a != b


def test_reject_invalid_world_seed():
    for seed in (0, -1, 1.1, 'not-a-seed', True, 2_147_483_648):
        with pytest.raises(ValueError):
            DevelopmentSession(world_seed=seed)


def test_imminent_replacement_only_when_retirement_would_create_genuine_gap(opening):
    reg=opening._world_squads
    cid=next(cid for cid in reg.clubs if cid!=opening.home_club.id)
    club=deepcopy(reg.clubs[cid])
    tactic=reg.identities[cid].primary
    plan=squad_plan(club,tactic)
    assert imminent_succession_needs(club,tactic,opening.current_date,plan)==[]
    older=next(slot for slot in plan['assignments'] if slot['layer']==2 and slot['position']!='GK')
    player=club.squad.get(older['player_id'])
    player.identity=replace(player.identity,birth_date=date(1986,1,1))
    player.aging=replace(player.aging,retirement_status='requested',
                         retirement_requested_on=opening.current_date)
    needs=imminent_succession_needs(club,tactic,opening.current_date)
    assert needs
    assert all(i['succession'] and i['retiring_id']==player.id for i in needs)
    assert all(i['layer']<=2 for i in needs)
    # No phantom vacancies: deleting an actual covered player leaves a hole.
    after=squad_plan(club,tactic,excluded_id=player.id)
    assert after['starters_covered']+after['backups_covered'] < 22


def test_retirement_is_independent_of_keeper_depth_and_starter_coverage(opening):
    s=deepcopy(opening)
    reg=s._world_squads
    cid=next(cid for cid in reg.clubs if cid!=s.home_club.id)
    club=reg.clubs[cid]
    keeper=next(p for p in club.squad.players if p.primary_position is Position.GK)
    keeper.aging=replace(keeper.aging,retirement_status='requested',
                         retirement_requested_on=s.current_date)
    was=squad_plan(club,reg.identities[cid].primary)
    retired=finalize_season_retirements(s._world,date(2026,9,1))
    assert keeper.id in retired
    assert not club.squad.contains(keeper.id)
    assert keeper.id in reg.retired_players
    now=squad_plan(club,reg.identities[cid].primary)
    assert now['starters_covered'] <= was['starters_covered']


def test_renewal_not_granted_when_cash_runway_inadequate(opening):
    session=deepcopy(opening)
    reg=session._world_squads
    cid=next(cid for cid in reg.clubs if cid!=session.home_club.id)
    player=next(p for p in reg.clubs[cid].squad.players if p.age_on(session.current_date)<30)
    contract=reg.contracts[player.id]
    reg.contracts[player.id]=replace(contract,expires_on=date(2026,11,1))
    account=reg.club_finances[cid]
    reg.club_finances[cid]=replace(account,cash_gbp=0,recurring_income_gbp=1,
                                   recurring_operations_gbp=account.recurring_operations_gbp,
                                   wage_budget_weekly_gbp=max(50_000_000,weekly_payroll(reg,cid)*3))
    with session._world.transaction():
        auto_renew_ai_contracts(session._world,date(2026,9,1),managed_club_id=session.home_club.id)
    assert reg.contracts[player.id].expires_on == date(2026,11,1)
    # Honour the binding old wage; no retroactive contract write-off.
    assert reg.contracts[player.id].weekly_wage_gbp==contract.weekly_wage_gbp
