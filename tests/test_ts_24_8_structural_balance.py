"""TS-24.8: no phantom talent, credible youth opportunity and solvent planning."""
from __future__ import annotations

from copy import deepcopy
from datetime import date

import pytest

from football_manager.dev_ui.session import DevelopmentSession
from football_manager.domain.enums import Position
from football_manager.services.ai_squad_planning import can_spare, squad_plan
from football_manager.services.club_economy import (
    _operating_overhead, rebase_finances_for_new_season, weekly_payroll,
)
from football_manager.services.world_matches import opponent_side
from football_manager.services.youth_academy import _academy_promotions


@pytest.fixture(scope='module')
def opening():
    return DevelopmentSession()


def test_baseline_tactics_and_salaries_still_fully_registered(opening):
    r=opening._world_squads
    assert len(r.clubs)==92
    for cid,club in r.clubs.items():
        report=squad_plan(club,r.identities[cid].primary)
        assert report['starters_covered']==11
        assert report['backups_covered']==11
        assert len({row['player_id'] for row in report['assignments']})==len(report['assignments'])
        assert weekly_payroll(r,cid) <= r.club_finances[cid].wage_budget_weekly_gbp


def test_selling_one_deputy_does_not_permit_exporting_the_next_one(opening):
    cid=next(cid for cid in opening._world_squads.clubs if cid!=opening.home_club.id)
    r=opening._world_squads
    club=deepcopy(r.clubs[cid]);tactic=r.identities[cid].primary
    old=squad_plan(club,tactic)
    assert old['backups_covered']==11
    backups=[entry for entry in old['assignments'] if entry['layer']==2]
    first=next(entry for entry in backups if club.squad.get(entry['player_id']).primary_position is not Position.GK)
    club.squad.remove(first['player_id'])
    plan=squad_plan(club,tactic)
    assert plan['starters_covered']==11 and plan['backups_covered']==10
    attempts=[]
    for entry in plan['assignments']:
        pid=entry['player_id']
        after=squad_plan(club,tactic,excluded_id=pid)
        if after['starters_covered']==11 and after['backups_covered']<10:
            attempts.append(pid)
    assert attempts
    assert all(not can_spare(club,tactic,pid) for pid in attempts)


def _find_rotation_fixture(session):
    w=session._world
    for fid,f in w.fixtures.items():
        cid=f.home_club_id
        if cid==session.home_club.id or cid not in session._world_squads.clubs or f.match_date is None:
            continue
        club,lineup,_=opponent_side(w,cid,fixture_id=fid)
        _,standard,_=opponent_side(w,cid)
        incoming={p.id for p in lineup.starters_players if p.id not in {q.id for q in standard.starters_players}} if hasattr(lineup,'starters_players') else (
            {e.player.id for e in lineup.starters}-{e.player.id for e in standard.starters})
        if incoming:
            return fid,cid,incoming
    raise AssertionError('No genuine U23 rotation candidate in sample fixtures')


def test_development_rotation_is_earned_deterministic_and_match_valid(opening):
    fid,cid,incoming=_find_rotation_fixture(opening)
    w=opening._world
    club,rotated,tactic=opponent_side(w,cid,fixture_id=fid)
    _,repeated,_=opponent_side(w,cid,fixture_id=fid)
    assert {e.player.id for e in rotated.starters}=={e.player.id for e in repeated.starters}
    assert len(incoming)==1
    assert all(club.squad.get(pid).age_on(w.fixtures[fid].match_date)<23 for pid in incoming)
    assert len(rotated.starters)==11
    assert len(rotated.bench)==7
    club.validate_lineup(rotated)
    _,manager_lineup,_=opponent_side(w,opening.home_club.id,fixture_id=fid)
    _,manager_default,_=opponent_side(w,opening.home_club.id)
    assert {e.player.id for e in manager_lineup.starters} == {e.player.id for e in manager_default.starters}


def test_real_match_awards_minutes_only_when_fixture_plays(opening):
    s=deepcopy(opening)
    fid,cid,incoming=_find_rotation_fixture(s)
    registry=s._world_squads
    assert not any(pid in registry.usage for pid in incoming)
    s._world.simulate_fixture(fid)
    assert all(registry.usage[pid].minutes > 0 for pid in incoming)
    assert fid in s._world.results
    registry.validate()


def test_academy_promotions_are_canonical_and_do_not_clone(opening):
    s=deepcopy(opening)
    r=s._world_squads
    cid=next(cid for cid,academy in r.youth.academies.items()
             if cid!=s.home_club.id and any(p.age_on(date(2027,7,1))>=21 for p in academy.u21.values()))
    academy=r.youth.academies[cid]
    first_team=r.clubs[cid].squad
    opening_ids={p.id for p in first_team.players}
    youth_ids=set(academy.u21)
    result=_academy_promotions(r,academy,date(2027,7,1),managed_club_id=s.home_club.id)
    promoted=set(academy.graduates)-opening_ids
    assert len(promoted)==result['u21_to_first']
    assert promoted <= youth_ids
    assert promoted <= {p.id for p in first_team.players}
    assert not promoted & set(academy.u21)
    assert len(first_team)<=29


def test_managed_academy_never_auto_signs_senior_players(opening):
    s=deepcopy(opening)
    r=s._world_squads
    cid=s.home_club.id
    original={p.id for p in r.clubs[cid].squad.players}
    _academy_promotions(r,r.youth.academies[cid],date(2027,7,1),managed_club_id=cid)
    assert original=={p.id for p in r.clubs[cid].squad.players}


def test_promotion_relegation_revenues_are_independent_of_payroll(opening):
    s=deepcopy(opening)
    r=s._world_squads
    cid=next(cid for cid,ident in r.identities.items() if ident.tier==1 and cid!=s.home_club.id)
    old=r.club_finances[cid]
    old_cash=old.cash_gbp
    r.identities[cid].tier=4
    rebase_finances_for_new_season(r,date(2027,7,1))
    after=r.club_finances[cid]
    assert after.cash_gbp==old_cash
    assert after.recurring_income_gbp < old.recurring_income_gbp
    assert after.wage_budget_weekly_gbp >= weekly_payroll(r,cid)
    # Regardless of how expensive the retained contracts are, division
    # revenue is based on division and club stature, not weekly payroll.
    from football_manager.services.club_economy import DIVISION_BASE_MONTHLY_INCOME,_unit
    stature=.78+.5*_unit(r.seed,cid,'club-stature')
    assert after.recurring_income_gbp==int(DIVISION_BASE_MONTHLY_INCOME[4]*stature)


def test_non_player_cost_ratios_reflect_divisional_footprint(opening):
    r=deepcopy(opening)._world_squads
    cid=next(cid for cid,ident in r.identities.items() if ident.tier==1)
    r.identities[cid].tier=1
    premium=_operating_overhead(r,cid,1_000_000)
    r.identities[cid].tier=4
    small=_operating_overhead(r,cid,1_000_000)
    assert 350_000 <= premium <= 450_000
    assert 140_000 <= small <= 240_000
    assert premium>small


def test_transfers_keep_the_user_in_control(opening):
    from football_manager.services.ai_transfer_market import MAX_AI_TRANSFERS_PER_MONTH
    assert MAX_AI_TRANSFERS_PER_MONTH<=36
    assert opening._world_squads.youth.managed_club_id==opening.home_club.id
