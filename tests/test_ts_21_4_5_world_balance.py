"""TS-21.4+21.5 universal club training and honest, read-only balance audits.

No Node, personal saves, networking or UI browser required.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from datetime import date
import gzip
import json
from pathlib import Path

import pytest

from football_manager.calibration.world_balance import (
    population_metrics, world_balance_snapshot, compare_world_snapshots, balance_warnings,
)
from football_manager.dev_ui.session import DevelopmentSession
from football_manager.domain.player_development import (
    DevelopmentEnvironment, current_ability, next_month,
)
from football_manager.domain.world_runner import WorldMatchResult
from football_manager.persistence.session_codec import capture_manager_graph, restore_manager_graph, GRAPH_VERSION
from football_manager.persistence.manager_career import validate_manager_session
from football_manager.services.player_development import advance_world_development
from football_manager.services.world_training import (
    PROXY_SOURCE, NEUTRAL_SOURCE, estimated_training_environment,
    initialize_club_training, month_club_fixtures, effective_training_environment,
)


@pytest.fixture(scope='module')
def current():
    return DevelopmentSession()


def test_global_training_environments_are_one_time_estimates_not_made_up_staff(current):
    world = current._world_squads
    assert len(world.clubs) == 92
    assert len({p.id for club in world.clubs.values() for p in club.squad.players}) == 2024
    assert len(set(world.development_environments.values())) > 10
    assert all(env.source == PROXY_SOURCE for env in world.development_environments.values())
    assert all(44 <= env.training_quality <= 76 and 44 <= env.coaching_quality <= 76
               for env in world.development_environments.values())
    assert initialize_club_training(world) == 0


def test_stable_club_derived_not_tier_multiplier_and_not_squad_recalculated(current):
    r = deepcopy(current._world_squads)
    cid = sorted(r.clubs)[0]
    saved = r.development_environments[cid]
    # Imported verified data never gets replaced by a provisional estimate.
    r.development_environments[cid] = DevelopmentEnvironment(91, 84, source='imported-facilities')
    assert initialize_club_training(r, upgrade_neutral=True) == 0
    assert r.development_environments[cid].source == 'imported-facilities'
    r.development_environments[cid] = saved
    first = estimated_training_environment(r, cid)
    p = r.clubs[cid].squad.players[0]
    p.attributes = replace(p.attributes, physical=replace(p.attributes.physical, pace=1))
    assert r.development_environments[cid] == saved  # Sticky initial estimate.
    # Fresh estimated value would change, but the stored fixture context does not.
    assert r.development_environments[cid].source == PROXY_SOURCE
    assert first == saved


def test_five_or_more_fixtures_decrease_training_opportunity():
    env = DevelopmentEnvironment(65, 75, 'verified')
    assert effective_training_environment(env, 0) is env
    assert effective_training_environment(env, 4) is env
    moderately_busy = effective_training_environment(env, 6)
    very_busy = effective_training_environment(env, 12)
    assert 44 <= very_busy.training_quality < moderately_busy.training_quality < env.training_quality
    assert very_busy.coaching_quality == env.coaching_quality
    assert env.training_quality == 65  # No mutation of stored facilities/coaching.
    with pytest.raises(ValueError): effective_training_environment(env, -1)
    with pytest.raises(ValueError): effective_training_environment(env, True)


def test_completed_fixture_counter_uses_only_previous_month_and_registered_clubs(current):
    s = deepcopy(current)
    w = s._world
    fixture = next(f for f in w.fixtures.values()
                   if f.home_club_id in s._world_squads.clubs and f.away_club_id in s._world_squads.clubs)
    w.results[fixture.fixture_id] = WorldMatchResult(fixture.fixture_id, 1, 1)
    boundary = next_month(fixture.match_date.replace(day=1))
    counts = month_club_fixtures(w, boundary)
    assert counts[fixture.home_club_id] == 1 and counts[fixture.away_club_id] == 1
    assert not month_club_fixtures(w, next_month(boundary))



def test_busy_registered_club_gets_training_penalty_not_other_clubs(current, monkeypatch):
    from types import SimpleNamespace
    import football_manager.services.player_development as service
    s = deepcopy(current)
    world = s._world
    club_ids = sorted(s._world_squads.clubs)
    busy, rival, quiet = club_ids[:3]
    base = s._world_squads.development_environments
    # Hypothetical match dates for a focused test; no external simulation required.
    for i in range(7):
        key = f'test-month-load-{i}'
        world.fixtures[key] = SimpleNamespace(match_date=date(2026, 8, 20),
            home_club_id=busy, away_club_id=rival)
        world.results[key] = WorldMatchResult(key, 1, 0)
    visited = {}
    real_review = service.review_career
    def traced(player, boundary, environment, **kwargs):
        if player.id in (s._world_squads.clubs[busy].squad.players[0].id,
                         s._world_squads.clubs[quiet].squad.players[0].id):
            visited[player.id] = environment
        return real_review(player, boundary, environment, **kwargs)
    monkeypatch.setattr(service, 'review_career', traced)
    assert advance_world_development(world, date(2026, 9, 1)) == 2024
    busy_id = s._world_squads.clubs[busy].squad.players[0].id
    quiet_id = s._world_squads.clubs[quiet].squad.players[0].id
    assert visited[busy_id].training_quality < base[busy].training_quality
    assert visited[quiet_id] is base[quiet]
    assert base[busy].source == base[quiet].source == PROXY_SOURCE

def test_month_review_idempotent_through_scheduled_fixture_processing(current):
    s = deepcopy(current)
    boundary = next_month(s.current_date.replace(day=1))
    before_attrs = {p.id: p.attributes for c in s._world_squads.clubs.values() for p in c.squad.players}
    advance_world_development(s._world, boundary)
    assert s._world_squads.development_next_review == next_month(boundary)
    after_attrs = {p.id: p.attributes for c in s._world_squads.clubs.values() for p in c.squad.players}
    assert len(after_attrs) == len(before_attrs)
    assert advance_world_development(s._world, boundary) == 0
    assert {p.id: p.attributes for c in s._world_squads.clubs.values() for p in c.squad.players} == after_attrs


def test_readonly_metrics_and_no_fake_elite_creation(current):
    registry = current._world_squads
    before = capture_manager_graph(current)
    report = world_balance_snapshot(registry, current.current_date)
    assert report['active']['players'] == 2024
    assert sum(report['active']['bins'].values()) == 2024
    assert sum(data['players'] for data in report['by_tier'].values()) == 2024
    assert report['academy_intake_enabled'] is False
    assert report['active']['reference_90_plus'] <= report['active']['players']
    assert compare_world_snapshots(report, report)['active_population_delta'] == 0
    assert not balance_warnings(report, report)
    assert capture_manager_graph(current) == before


def test_balance_alarms_do_not_change_player_attributes(current):
    first = world_balance_snapshot(current._world_squads,current.current_date)
    altered = deepcopy(first)
    altered['active']['players'] = int(first['active']['players']*.5)
    altered['active']['under_21'] = 0
    altered['active']['reference_ovr_mean'] += 4
    warnings = balance_warnings(first, altered)
    assert any('youth intake' in line.lower() or 'Newgens' in line for line in warnings)
    assert any('drift' in line for line in warnings)


def test_zero_player_metrics_avoid_division_errors():
    x = population_metrics([],date(2046,1,1))
    assert x['players'] == 0 and x['reference_ovr_mean'] is None
    assert sum(x['bins'].values()) == 0


def test_actual_previous_v8_save_migration_preserves_all_original_players():
    fixtures=Path(__file__).resolve().parent/'fixtures'
    with gzip.open(fixtures/'ts2145_manager_v8.json.gz','rt',encoding='utf-8') as stream:
        graph=json.load(stream)
    with gzip.open(fixtures/'ts2145_manager_v8_facts.json.gz','rt',encoding='utf-8') as stream:
        facts=json.load(stream)
    assert graph['version']==8 and GRAPH_VERSION == 16
    restored = restore_manager_graph(graph)
    validate_manager_session(restored)
    registry = restored._world_squads
    assert len(registry.clubs) == 92
    from football_manager.domain.player_development import attribute_values
    for cid, club in registry.clubs.items():
        for p in club.squad.players:
            old=facts['players'][p.id]
            assert old['attributes']==attribute_values(p.attributes)
            assert old['birth']==p.identity.birth_date.isoformat()
            assert old['potential']==p.development.potential
            assert old['club_id']==cid
        assert registry.development_environments[cid].source == PROXY_SOURCE
    assert capture_manager_graph(restored)['version'] == 16
    assert restore_manager_graph(capture_manager_graph(restored))._world_squads == restored._world_squads


def test_projections_are_hypothetical_and_never_modify_world(current):
    from tools.validate_ts2145_world_balance import run
    snapshot = capture_manager_graph(current)
    outcome=run('cohort', 20, 20)
    rows=outcome['annual_projection']
    assert outcome['sample_initial_players'] == 20
    assert 1 <= len(rows) <= 20
    assert all(rows[i]['players'] <= (20 if i==0 else rows[i-1]['players']) for i in range(len(rows)))
    assert rows[-1]['players'] < rows[0]['players']
    assert 'hypothetical' in outcome['limitations'][0].lower()
    assert capture_manager_graph(current) == snapshot
