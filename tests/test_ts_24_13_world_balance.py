"""TS-24.13: natural goalkeeper pipeline and autonomous squad depth."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from datetime import date

import pytest

from football_manager.dev_ui.session import DevelopmentSession
from football_manager.domain.enums import Position
from football_manager.services.youth_academy import _academy_promotions, MAX_U15
from football_manager.services.world_squads import _refresh_inactive_club_recovery
from football_manager.persistence import session_codec
from football_manager.persistence.models import SaveIntegrityError


@pytest.fixture(scope='module')
def baseline():
    return DevelopmentSession(world_seed=6606)


def test_fresh_academy_intake_replenishes_real_keeper_prospects(baseline):
    reg = deepcopy(baseline._world_squads)
    club_id = reg.youth.managed_club_id
    academy = reg.youth.academies[club_id]
    existing = list(academy.u15.values())
    # Model a partly-graduated academy whose remaining U15 players include no GK.
    academy.u15 = {p.player_id: p for p in existing if p.position is not Position.GK}
    # Leave enough new intake places for both goalkeeper prospects.
    assert len(academy.u15) == MAX_U15 - 2
    existing_ids = set(academy.u15)
    senior_ids = {p.id for p in reg.clubs[club_id].squad.players}
    _academy_promotions(reg, academy, date(2027, 7, 1), managed_club_id=club_id)
    assert len(academy.u15) == MAX_U15
    new_ids = set(academy.u15) - existing_ids
    # The academy also releases its existing 16-year-old graduates at rollover:
    # enough new U15 entrants are created to restore the 20-place cohort.
    new_keepers = [academy.u15[pid] for pid in new_ids if academy.u15[pid].position is Position.GK]
    assert len(new_keepers) == 2
    assert all(p.age_on(date(2027, 7, 1)) == 14 for p in new_keepers)
    assert len(new_ids) >= 2
    outfield_roles = {academy.u15[pid].position for pid in new_ids if academy.u15[pid].position is not Position.GK}
    assert len(outfield_roles) >= 4
    assert {p.id for p in reg.clubs[club_id].squad.players} == senior_ids
    # Same academy dates/seed are reproducible without copying existing people.
    repeat = deepcopy(baseline._world_squads)
    repeat_a = repeat.youth.academies[club_id]
    repeat_a.u15 = {p.player_id: p for p in list(repeat_a.u15.values())
                    if p.position is not Position.GK}
    _academy_promotions(repeat, repeat_a, date(2027, 7, 1), managed_club_id=club_id)
    assert set(repeat_a.u15) == set(academy.u15)


def test_real_u21_goalkeeper_can_become_third_keeper_without_ghost_players(baseline):
    reg = deepcopy(baseline._world_squads)
    manager = reg.youth.managed_club_id
    candidates = [cid for cid in sorted(reg.clubs)
                  if cid != manager and reg.identities[cid].tier == 4]
    cid = next(cid for cid in candidates if any(
        p.primary_position is Position.GK and p.age_on(date(2028,7,1)) >= 20
        and p.overall_rating >= 25
        for p in reg.youth.academies[cid].u21.values()))
    academy = reg.youth.academies[cid]
    before = {p.id for p in reg.clubs[cid].squad.players}
    youth_ids = set(academy.u21)
    counts = _academy_promotions(reg, academy, date(2028, 7, 1), managed_club_id=manager)
    after = {p.id for p in reg.clubs[cid].squad.players}
    added = after - before
    assert added <= youth_ids
    assert counts['u21_to_first'] == len(added)
    assert len([p for p in reg.clubs[cid].squad.players if p.primary_position is Position.GK]) >= 3
    assert not (set(academy.u21) & added)


def test_debt_does_not_block_genuine_academy_keeper(baseline):
    # A club may be in the red and still give its own developed youth a
    # contract; it receives no additional cash and no fictitious player IDs.
    reg = deepcopy(baseline._world_squads)
    manager = reg.youth.managed_club_id
    cid = next(cid for cid in sorted(reg.clubs) if cid != manager and
               reg.identities[cid].tier == 4 and
               any(p.primary_position is Position.GK and p.age_on(date(2028,7,1)) >= 20
                   and p.overall_rating >= 25 for p in reg.youth.academies[cid].u21.values()))
    before = {p.id for p in reg.clubs[cid].squad.players}
    youth_ids = set(reg.youth.academies[cid].u21)
    reg.club_finances[cid] = replace(reg.club_finances[cid], cash_gbp=-10_000_000)
    _academy_promotions(reg, reg.youth.academies[cid], date(2028,7,1), managed_club_id=manager)
    added = {p.id for p in reg.clubs[cid].squad.players} - before
    assert added <= youth_ids
    assert sum(p.primary_position is Position.GK for p in reg.clubs[cid].squad.players) == 3
    assert reg.club_finances[cid].cash_gbp == -10_000_000


def test_new_keeper_cohort_reaches_u21_before_professional_team(baseline):
    """An annual 14-year-old goalkeeper is real youth, not an emergency XI."""
    reg = deepcopy(baseline._world_squads)
    manager = reg.youth.managed_club_id
    cid = next(cid for cid in sorted(reg.clubs)
               if cid != manager and reg.identities[cid].tier == 4)
    club = reg.clubs[cid]
    academy = reg.youth.academies[cid]
    initial_professionals = {p.id for p in club.squad.players}
    _academy_promotions(reg, academy, date(2027, 7, 1), managed_club_id=manager)
    new_keeper_ids = {pid for pid, p in academy.u15.items()
                      if p.position is Position.GK and p.age_on(date(2027, 7, 1)) == 14}
    assert len(new_keeper_ids) == 2
    assert not (new_keeper_ids & initial_professionals)
    for year in range(2028, 2032):
        _academy_promotions(reg, academy, date(year, 7, 1), managed_club_id=manager)
    # These actual U15 players progressed through the youth pathway; no
    # substitution of identity was made to force a senior goalkeeper.
    assert new_keeper_ids <= set(academy.u21)
    assert not (new_keeper_ids & {p.id for p in club.squad.players})
    assert all(academy.u21[pid].primary_position is Position.GK for pid in new_keeper_ids)


def test_ai_does_not_stockpile_fourth_goalkeeper(baseline):
    reg = deepcopy(baseline._world_squads)
    manager = reg.youth.managed_club_id
    cid = next(cid for cid in sorted(reg.clubs) if cid != manager and
               reg.identities[cid].tier == 4 and
               any(p.primary_position is Position.GK and p.age_on(date(2028, 7, 1)) >= 20
                   and p.overall_rating >= 25 for p in reg.youth.academies[cid].u21.values()))
    academy = reg.youth.academies[cid]
    _academy_promotions(reg, academy, date(2028, 7, 1), managed_club_id=manager)
    _academy_promotions(reg, academy, date(2029, 7, 1), managed_club_id=manager)
    assert sum(p.primary_position is Position.GK for p in reg.clubs[cid].squad.players) == 3


def test_nonleague_club_clock_catches_up_before_youth_graduations(baseline):
    reg = deepcopy(baseline._world_squads)
    cid = next(cid for cid in sorted(reg.clubs) if cid != reg.youth.managed_club_id)
    other = next(other for other in reg.clubs if other != cid)
    unchanged = reg.last_recovery[other]
    reg.identities[cid].tier = 0  # spent many years in non-league
    reg.last_recovery[cid] = date(2026, 7, 1)
    player = next(iter(reg.clubs[cid].squad.players))
    player.state.fitness, player.state.fatigue = 45, 80
    _refresh_inactive_club_recovery(reg, date(2045, 7, 1))
    assert reg.last_recovery[cid] == date(2045, 7, 1)
    assert reg.last_recovery[other] == unchanged
    assert player.state.fitness >= 99
    assert player.state.fatigue <= 1
    # Genuine youth born during non-league years may be registered without a
    # false 'player was born after club registration' exception.
    assert date(2030, 1, 1) <= reg.last_recovery[cid]
    _refresh_inactive_club_recovery(reg, date(2045, 7, 1))  # idempotent


def test_save_graph_capacity_remains_bounded(baseline, monkeypatch):
    assert session_codec.MAX_NODES >= 285_944
    # Security guard stays active for a damaged/oversized input rather than
    # accepting an unbounded arbitrary graph.
    monkeypatch.setattr(session_codec, 'MAX_NODES', 3)
    with pytest.raises(SaveIntegrityError, match='node count'):
        session_codec.restore_manager_graph({
            'version': session_codec.GRAPH_VERSION,
            'root': {'$ref': 0},
            'nodes': [{}, {}, {}, {}],
        })


def test_lightweight_stress_scoring_advances_club_registration_clock():
    """Fast multi-year audits must not leave professional clocks back in 2026."""
    import sys
    from pathlib import Path

    tools_dir = str(Path(__file__).resolve().parents[1] / 'tools')
    if tools_dir not in sys.path:
        sys.path.insert(0, tools_dir)
    from stress_ts248_long_horizon import background_score_only

    session = DevelopmentSession(world_seed=6606)
    registry = session._world_squads
    world = session._world
    fixture = next(
        f for f in sorted(world.fixtures.values(), key=lambda item: item.match_date or date.max)
        if f.match_date is not None and f.home_club_id in registry.clubs
        and f.away_club_id in registry.clubs
        and any(registry.last_recovery[cid] < f.match_date
                for cid in (f.home_club_id, f.away_club_id))
    )
    participants = (fixture.home_club_id, fixture.away_club_id)
    assert any(registry.last_recovery[cid] < fixture.match_date for cid in participants)
    with background_score_only():
        result = world.simulate_fixture(fixture.fixture_id)
    assert result.resolver == 'background'
    assert all(registry.last_recovery[cid] == fixture.match_date for cid in participants)
    assert fixture.fixture_id in world.results


def test_lightweight_fixture_cannot_rewind_existing_club_recovery_date():
    """Competition fixture order may differ from last physical calendar tick."""
    import sys
    from datetime import timedelta
    from pathlib import Path

    tools_dir = str(Path(__file__).resolve().parents[1] / 'tools')
    if tools_dir not in sys.path:
        sys.path.insert(0, tools_dir)
    from stress_ts248_long_horizon import background_score_only

    session = DevelopmentSession(world_seed=6606)
    registry = session._world_squads
    world = session._world
    fixture = next(
        f for f in sorted(world.fixtures.values(), key=lambda x: x.match_date or date.max)
        if f.fixture_id not in world.results and f.match_date is not None
        and f.home_club_id in registry.clubs and f.away_club_id in registry.clubs
    )
    later = fixture.match_date + timedelta(days=1)
    registry.last_recovery[fixture.home_club_id] = later
    with background_score_only():
        result = world.simulate_fixture(fixture.fixture_id)
    assert result.resolver == 'background'
    assert registry.last_recovery[fixture.home_club_id] == later
    assert registry.last_recovery[fixture.away_club_id] >= fixture.match_date
