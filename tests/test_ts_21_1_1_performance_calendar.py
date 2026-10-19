"""TS-21.1.1: deterministic equivalence, bounded caches and fixture repairs.

Python-only; no timing thresholds tied to a developer's computer. Performance
measurements are collected by tools/benchmark_ts2111.py, not asserted as a race.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, replace
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from random import Random
import gzip
import json

import pytest

from football_manager.dev_ui.session import DevelopmentSession
from football_manager.domain.calendar import ScheduleSource, ScheduledFixture, ScheduledFixtureStatus
from football_manager.domain.calendar_planner import (
    FixtureIndex, repair_generated_calendar, calendar_rest_audit,
)
from football_manager.domain.enums import Position
from football_manager.domain.player_ratings import (
    CurrentRatingBatch, CurrentRatingContext, calculate_current_rating,
    _condition_adjustment, _confidence_adjustment, _bidirectional_adjustment,
)
from football_manager.domain.roles import roles_for_position
from football_manager.domain.world_runner import WorldSeasonRunner
from football_manager.domain.international_calendar import build_international_calendar
from football_manager.persistence import SQLiteSaveRepository, load_manager_career, save_manager_career
from football_manager.persistence.manager_career import validate_manager_session
from football_manager.persistence.session_codec import capture_manager_graph
from football_manager.services import world_squads, world_matches
from football_manager.services.calendar_stabilization import stabilize_session_calendar
from football_manager.ui_shell.progression import simulate_until, advance_day
from ts2111_reference import legacy_select_lineup, legacy_select_team, legacy_current_rating


@pytest.fixture(scope='module')
def initial():
    return DevelopmentSession()


def lineup_ids(lineup):
    return tuple((e.slot_id, e.player.id) for e in lineup.starters), tuple(p.id for p in lineup.bench)


@pytest.mark.parametrize('tier', [1, 2, 3, 4])
@pytest.mark.parametrize('current', [False, True])
def test_every_club_selects_identical_xi_and_bench(initial, tier, current):
    registry = initial._world_squads
    for cid, identity in registry.identities.items():
        if identity.tier != tier:
            continue
        club = registry.clubs[cid]
        for tactic in (identity.primary, identity.alternative):
            assert lineup_ids(world_squads.select_lineup(club, tactic, current=current)) == lineup_ids(
                legacy_select_lineup(club, tactic, current=current))


@pytest.mark.parametrize('tier', [1, 2, 3, 4])
def test_tactical_plan_selection_is_unchanged(initial, tier):
    registry = initial._world_squads
    for cid, identity in registry.identities.items():
        if identity.tier == tier:
            actual, at = world_squads.select_team(registry.clubs[cid], identity)
            expected, et = legacy_select_team(registry.clubs[cid], identity)
            assert at.tactic_id == et.tactic_id
            assert lineup_ids(actual) == lineup_ids(expected)


@pytest.mark.parametrize('chemistry', [0, 40, 65, 85, 100])
def test_full_rating_breakdown_matches_frozen_formula(initial, chemistry):
    # Every position and supported role, multiple player archetypes and states.
    players = deepcopy(initial.home_club.squad.players[:6])
    for number, player in enumerate(players):
        player.state.fitness = (35, 55, 74, 75, 90, 100)[number]
        player.state.confidence = (1, 4, 35, 65, 85, 100)[number]
        batch = CurrentRatingBatch()
        contexts = [CurrentRatingContext(chemistry=chemistry)]
        contexts += [CurrentRatingContext(assigned_position=position, role_id=role.role_id,
                        tactic_id='unfamiliar-plan', chemistry=chemistry)
                     for position in Position for role in roles_for_position(position)]
        for context in contexts:
            reference = legacy_current_rating(player, context)
            assert calculate_current_rating(player, context) == reference
            assert batch.rating(player, context) == reference


@pytest.mark.parametrize('condition', [1, 20, 50, 65, 74, 75, 100])
def test_cached_numeric_modifiers_are_exact_and_bounded(condition):
    assert _condition_adjustment(condition) == _condition_adjustment.__wrapped__(condition)
    assert _confidence_adjustment(condition) == _confidence_adjustment.__wrapped__(condition)
    args = dict(max_penalty=5.0, max_bonus=1.0)
    assert _bidirectional_adjustment(condition, **args) == _bidirectional_adjustment.__wrapped__(condition, **args)
    assert _condition_adjustment.cache_info().currsize <= 8192


def test_selection_cache_does_not_survive_state_attribute_or_role_changes(initial):
    club = deepcopy(initial.home_club)
    tactic = deepcopy(initial.home_tactic)
    world_squads.select_lineup(club, tactic)
    player = club.squad.players[1]
    player.state.fitness = 10
    player.state.fatigue = 95
    player.attributes = replace(player.attributes, physical=replace(player.attributes.physical, pace=5))
    player.tactical_familiarity.set_tactic_score(tactic.tactic_id, 0)
    assert lineup_ids(world_squads.select_lineup(club, tactic)) == lineup_ids(legacy_select_lineup(club, tactic))
    # Same identifiers on a different clone must not reuse an earlier rating.
    other = deepcopy(club)
    other.squad.players[1].state.fitness = 100
    assert lineup_ids(world_squads.select_lineup(other, tactic)) == lineup_ids(legacy_select_lineup(other, tactic))


def test_scoring_reuses_matrix_for_the_bench(initial, monkeypatch):
    count = 0
    original = world_squads._score
    def tracked(*args, **kwargs):
        nonlocal count
        count += 1
        return original(*args, **kwargs)
    monkeypatch.setattr(world_squads, '_score', tracked)
    world_squads.select_lineup(initial.home_club, initial.home_tactic)
    unique = {(s.position, initial.home_tactic.role_for_slot(s.slot_id).role_id)
              for s in initial.home_tactic.formation.slots}
    assert count <= len(initial.home_club.squad) * len(unique)


def test_fixed_seed_match_results_and_player_state_identical(initial, monkeypatch):
    fast, reference = deepcopy(initial._world), deepcopy(initial._world)
    ids = [f.fixture_id for f in sorted(fast.fixtures.values(), key=lambda f: (f.kickoff, f.fixture_id))
           if f.fixture_id not in fast.results and f.competition_id in fast.leagues
           and initial.home_club.id not in (f.home_club_id, f.away_club_id)][:24]
    for fid in ids:
        fast.simulate_fixture(fid)
    monkeypatch.setattr(world_matches, 'select_team', legacy_select_team)
    for fid in ids:
        reference.simulate_fixture(fid)
    assert fast.to_dict() == reference.to_dict()
    assert asdict(fast.football_world) == asdict(reference.football_world)


def fixture(fid, day, hour=19, minute=45, *, competition='dev-premier', home='A', away='B',
            source=ScheduleSource.GENERATED, status=ScheduledFixtureStatus.SCHEDULED):
    return ScheduledFixture(fid, competition, competition+'-2026-27', 'league', home, away,
        datetime(2026, 11, day, hour, minute, tzinfo=timezone.utc), source, status=status)


def small_world(*fixtures):
    world = WorldSeasonRunner(international_calendar=build_international_calendar(2026, 2027))
    world.leagues['dev-premier'] = object()  # Only fixture ownership is needed here.
    world.fixtures.update((f.fixture_id, f) for f in fixtures)
    return world


def test_wednesday_europe_friday_league_moves_to_sunday():
    europe = fixture('eu', 4, competition='champions-league', away='C')
    league = fixture('pl', 6, hour=20, minute=0)
    world = small_world(europe, league)
    report = repair_generated_calendar(world)
    assert len(report['moved']) == 1
    assert world.fixtures['pl'].match_date == date(2026, 11, 8)
    assert world.fixtures['pl'].original_kickoff == league.kickoff
    assert world.fixtures['eu'] is europe
    assert not calendar_rest_audit(world)['short_rest_pairs']


def test_thursday_europe_uses_sunday_evening_for_72_hours():
    world = small_world(fixture('eu', 5, competition='europa-league', away='C'), fixture('pl', 7))
    repair_generated_calendar(world)
    assert world.fixtures['pl'].kickoff == datetime(2026, 11, 8, 19, 45, tzinfo=timezone.utc)
    assert not calendar_rest_audit(world)['short_rest_pairs']


def test_both_clubs_and_the_next_game_are_checked():
    world = small_world(fixture('eu', 4, competition='champions-league', away='C'),
                        fixture('pl', 6), fixture('next', 10, competition='cup', home='B', away='D'))
    # No mandatory break in this synthetic test, to isolate the next opponent.
    world.international_calendar = None
    repair_generated_calendar(world)
    # Sunday would leave the opponent only 48h before Tuesday: use Saturday evening.
    assert world.fixtures['pl'].kickoff == datetime(2026, 11, 7, 19, 45, tzinfo=timezone.utc)
    assert not calendar_rest_audit(world)['short_rest_pairs']


@pytest.mark.parametrize('protected', ['official', 'played', 'today', 'past'])
def test_repairs_never_rewrite_protected_fixtures(protected):
    league = fixture('pl', 6, source=ScheduleSource.OFFICIAL if protected == 'official' else ScheduleSource.GENERATED,
                     status=ScheduledFixtureStatus.PLAYED if protected == 'played' else ScheduledFixtureStatus.SCHEDULED)
    world = small_world(fixture('eu', 4, competition='champions-league', away='C'), league)
    repair_generated_calendar(world, after_date=date(2026, 11, 6 if protected == 'today' else 7)
                              if protected in ('today', 'past') else None)
    assert world.fixtures['pl'] is league


def test_international_break_remains_blocked_and_repair_is_idempotent():
    world = small_world(fixture('eu', 4, competition='champions-league', away='C'), fixture('pl', 6))
    repair_generated_calendar(world)
    before = dict(world.fixtures)
    assert repair_generated_calendar(world)['moved'] == []
    assert world.fixtures == before
    assert not world.international_window_violations()


def test_unavoidable_fixed_date_exception_is_reported_not_hidden():
    world = small_world(fixture('one', 4, competition='cup', away='C'),
                        fixture('two', 6, competition='uefa', away='D'))
    assert repair_generated_calendar(world)['moved'] == []
    report = calendar_rest_audit(world)
    assert len(report['short_rest_pairs']) == 1
    assert report['short_rest_pairs'][0]['gap_hours'] == 48
    assert report['hard_violations'] == 0


def test_displacements_reserve_all_clubs_and_prefer_sunday():
    world = small_world(fixture('l1', 4), fixture('l2', 4, home='B', away='D'))
    anchor = fixture('cup', 4).kickoff
    with world.transaction():
        moves = world._plan_league_displacements(list(world.fixtures.values()), anchor)
    assert moves is not None
    assert moves[0][1].weekday() == 6
    assert abs((moves[0][1] - moves[1][1]).total_seconds()) >= 72*3600


def test_index_matches_full_scan_and_handles_cancel_move_and_played(initial):
    fixtures = list(initial._world.fixtures.values())
    index = FixtureIndex(fixtures)
    for f in fixtures[::29]:
        expected = {x.fixture_id for x in fixtures if x.kickoff is not None
                    and x.status in (ScheduledFixtureStatus.SCHEDULED, ScheduledFixtureStatus.PLAYED)
                    and {f.home_club_id, f.away_club_id} & {x.home_club_id, x.away_club_id}
                    and (x.match_date == f.match_date or abs((x.kickoff-f.kickoff).total_seconds()) < 72*3600)}
        assert {x.fixture_id for x in index.conflicts(f.kickoff, f.home_club_id, f.away_club_id)} == expected
    old = fixtures[0]
    cancelled = replace(old, status=ScheduledFixtureStatus.CANCELLED)
    index.put(old, cancelled)
    assert old.fixture_id not in index.by_club[old.home_club_id]
    played = replace(old, status=ScheduledFixtureStatus.PLAYED)
    index.put(cancelled, played)
    assert index.by_club[old.home_club_id][old.fixture_id] is played


def test_calendar_repair_rolls_back_every_date_on_failure(monkeypatch):
    world = small_world(fixture('eu', 4, competition='champions-league', away='C'), fixture('pl', 6))
    before = dict(world.fixtures)
    original = world._put
    def fail(mapping, key, value):
        original(mapping, key, value)
        raise RuntimeError('synthetic calendar failure')
    monkeypatch.setattr(world, '_put', fail)
    with pytest.raises(RuntimeError, match='synthetic calendar failure'):
        repair_generated_calendar(world)
    assert all(world.fixtures[fid] is f for fid, f in before.items())
    assert world._active_journal is None
    assert world._matching_conflicts(before['pl'].kickoff, 'A', 'B')


def test_opening_world_fixes_both_reported_november_weekends(initial):
    fixtures = initial._world.calendar.fixtures_for_club(initial.home_club.id)
    for day in (8, 29):
        assert any(f.competition_id == 'dev-premier' and f.match_date == date(2026, 11, day) for f in fixtures)
    assert not any(f.competition_id == 'dev-premier' and f.match_date in (date(2026,11,6),date(2026,11,27)) for f in fixtures)
    initial._world.validate_integrity()
    assert calendar_rest_audit(initial._world)['hard_violations'] == 0


def test_load_stabilization_preserves_world_players_results_and_current_match(initial):
    session = deepcopy(initial)
    # Recreate an old TS-21.1 Friday on a still-future match.
    game = next(f for f in session._world.calendar.fixtures_for_club(session.home_club.id)
                if f.competition_id == 'dev-premier' and f.match_date == date(2026, 11, 8))
    session._world.fixtures[game.fixture_id] = replace(game, kickoff=game.kickoff.replace(day=6,hour=20,minute=0))
    session._sync_world_view()
    player_state = asdict(session._world_squads)
    results = dict(session._world.results)
    active = session._active_match.fixture.fixture_id
    current = session.current_date
    report = stabilize_session_calendar(session)
    assert report['moved']
    assert session.current_date == current
    assert session._active_match.fixture.fixture_id == active
    assert session._world.results == results
    assert asdict(session._world_squads) == player_state
    validate_manager_session(session)


def test_existing_v5_database_is_repaired_in_memory_only(tmp_path):
    source = Path(__file__).with_name('fixtures') / 'ts2111_manager_v5_before.sqlite3.gz'
    path = tmp_path/'old.sqlite3'
    path.write_bytes(gzip.decompress(source.read_bytes()))
    original = path.read_bytes()
    repository = SQLiteSaveRepository(path)
    session = load_manager_career(repository, 'ts2111-before').session
    assert path.read_bytes() == original
    validate_manager_session(session)
    games = session._world.calendar.fixtures_for_club(session.home_club.id)
    assert any(f.competition_id=='dev-premier' and f.match_date==date(2026,11,8) for f in games)
    report = stabilize_session_calendar(session)
    assert report['moved'] == []
    save_manager_career(repository, slot_id='updated', display_name='Synthetic updated career',
                        expected_revision=0, session=session)
    loaded = load_manager_career(repository, 'updated').session
    assert capture_manager_graph(loaded) == capture_manager_graph(session)


def test_no_match_day_skips_rebuilding_the_world_projection(initial, monkeypatch):
    session = deepcopy(initial)
    simulate_until(session, session.current_date)
    calls = 0
    original = session._sync_world_view
    def sync():
        nonlocal calls
        calls += 1
        original()
    monkeypatch.setattr(session, '_sync_world_view', sync)
    day = session.current_date + timedelta(days=1)
    # Use the naturally quiet day after the opening weekend, with no fake results.
    while session.current_date < day:
        advance_day(session)
    assert calls <= 1
    assert session.current_date == day


def test_verifier_detects_missing_tampered_and_traversal(tmp_path):
    import hashlib
    import importlib.util
    tool = Path(__file__).resolve().parents[1]/'tools'/'verify_ts2111_performance_calendar_package.py'
    spec = importlib.util.spec_from_file_location('ts2111_verifier_test', tool)
    verifier = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(verifier)
    payload = b'synthetic package payload'
    target = tmp_path/'source.py'
    target.write_bytes(payload)
    manifest = {'package':verifier.PACKAGE, 'manifest_version':1, 'file_count':2,
                'files':[{'path':'source.py', 'bytes':len(payload),
                          'sha256':hashlib.sha256(payload).hexdigest()}]}
    manifest_path = tmp_path/verifier.MANIFEST
    manifest_path.write_text(json.dumps(manifest), encoding='utf-8')
    assert verifier.verify(tmp_path) == (1, [])
    target.write_bytes(b'changed')
    assert verifier.verify(tmp_path) == (1, ['MODIFIED: source.py'])
    target.unlink()
    assert verifier.verify(tmp_path) == (1, ['MISSING: source.py'])
    for unsafe in ('../outside.py', '/absolute.py', 'C:/outside.py', '..\\outside.py'):
        manifest['files'][0]['path'] = unsafe
        manifest_path.write_text(json.dumps(manifest), encoding='utf-8')
        with pytest.raises(ValueError):
            verifier.verify(tmp_path)
