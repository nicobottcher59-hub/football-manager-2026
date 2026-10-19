"""TS-24.7: end-to-end season-rollover regression and diagnostic contracts."""
from __future__ import annotations

from datetime import date
from copy import deepcopy

import pytest

from football_manager.dev_ui.session import DevelopmentSession
from football_manager.domain.world_runner import WorldSeasonRunner
from football_manager.services.player_development import catch_up_unsigned_player
from tools.stress_ts247_long_horizon import (
    _median, _pct, background_score_only, snapshot, run,
)


def test_long_horizon_percentiles_and_arguments(tmp_path):
    assert _median([7, 1, 4]) == 4
    assert _median([]) == 0
    assert _pct([10, 20, 30], 95) == 29
    assert _pct([], 95) == 0
    with pytest.raises(ValueError, match='season count'):
        run(0, output=tmp_path / 'must-not-exist.json')
    with pytest.raises(ValueError, match='checkpoints'):
        run(1, output=tmp_path / 'must-not-exist.json', milestones=(0,))


def test_accelerated_resolver_is_strictly_diagnostic_and_restored():
    original = WorldSeasonRunner.simulate_fixture
    with background_score_only():
        assert WorldSeasonRunner.simulate_fixture is not original
        with pytest.raises(RuntimeError, match='forced'):
            raise RuntimeError('forced')
    assert WorldSeasonRunner.simulate_fixture is original
    with pytest.raises(RuntimeError, match='forced again'):
        with background_score_only():
            raise RuntimeError('forced again')
    assert WorldSeasonRunner.simulate_fixture is original


@pytest.fixture(scope='module')
def initial():
    return DevelopmentSession()


def test_baseline_snapshot_is_read_only_and_92_clubs(initial):
    registry = initial._world_squads
    before = (len(registry.contracts), len(registry.club_finances),
              len(registry.transfer_offers), registry.market_review_on)
    metrics = snapshot(initial, 0)
    assert metrics['active_clubs'] == 92
    assert metrics['first_team_players'] == 2024
    assert metrics['uncovered_starter_slots'] == 0
    assert metrics['clubs_below_two_goalkeepers'] == 0
    assert metrics['hard_issues'] == []
    assert before == (len(registry.contracts), len(registry.club_finances),
                      len(registry.transfer_offers), registry.market_review_on)


def test_first_annual_rollover_bootstraps_promoted_clubs_without_backdated_cash():
    """Historical TS-24.6 defect: missing financial account on annual rollover.

    Fast season results are intentional: the regression is for the *real*
    calendar/monthly ledger and club bootstrap, not a FastMatchSimulator test.
    """
    s = DevelopmentSession()
    initial_ids = set(s._world_squads.clubs)
    try:
        with background_score_only():
            progress = s._world.advance_until(date(2027, 6, 30))
            assert progress.matches_played > 2000
            assert s.season_finished
            assert len(s._world.results) == len(s._world.fixtures)
            s.begin_next_season()
        r = s._world_squads
        # The summer transition must actually progress U21 academy footballers.
        assert sum(len(a.graduates) for a in r.youth.academies.values()) > 0
        entrants = sorted(set(r.clubs) - initial_ids)
        assert len(entrants) == 2
        assert len({c for c, identity in r.identities.items() if identity.tier > 0}) == 92
        assert set(r.club_finances) == set(r.clubs)
        for cid in entrants:
            # Before TS-24.7 renewal raised KeyError, and an early bootstrap
            # would have backdated July recurring income to these new clubs.
            account = r.club_finances[cid]
            assert account.cash_gbp > 0
            assert not account.history
            assert all(contract.signed_on >= date(2027, 7, 1)
                       for contract in r.contracts.values() if contract.club_id == cid)
        r.validate()
    finally:
        assert WorldSeasonRunner.simulate_fixture.__name__ == 'simulate_fixture'


def test_long_unsigned_player_resumes_monthly_clock_without_phantom_minutes(initial):
    player = deepcopy(initial.home_club.squad.players[9])
    opening_minutes = player.development.exposure.minutes
    start_age = player.aging.last_review
    steps = catch_up_unsigned_player(player, date(2029, 3, 22))
    assert steps >= 25  # An unsigned player can return after years away.
    assert player.development.last_review == date(2029, 3, 1)
    assert player.aging.last_review == date(2029, 3, 1)
    assert player.development.exposure.minutes == opening_minutes
    assert player.aging.last_review > start_age
    assert catch_up_unsigned_player(player, date(2029, 3, 31)) == 0


def test_unsigned_catchup_is_world_transaction_rollback_safe(initial):
    player = deepcopy(initial.home_club.squad.players[9])
    old = (player.attributes, player.development, player.aging)
    with pytest.raises(RuntimeError, match='undo'):
        with initial._world.transaction():
            assert catch_up_unsigned_player(player, date(2028, 4, 1), world=initial._world) > 1
            raise RuntimeError('undo')
    assert (player.attributes, player.development, player.aging) == old


def test_retirement_is_not_blocked_by_tactical_starter_coverage(initial):
    from dataclasses import replace
    from football_manager.services.player_aging import finalize_season_retirements
    s=deepcopy(initial)
    club=s.home_club
    slot=s.home_lineup.starters[0]
    candidate=club.squad.get(slot.player.id)
    candidate.aging=replace(candidate.aging,retirement_status='requested',
                            retirement_requested_on=s.current_date)
    departed=finalize_season_retirements(s._world,date(2026,9,1))
    assert candidate.id in departed
    assert not club.squad.contains(candidate.id)
    assert candidate.id in s._world_squads.retired_players


def test_ai_academies_retain_u23s_when_squad_is_full_of_veterans(initial):
    """A 25-player AI squad must not release every eligible U21 graduate."""
    from football_manager.services.youth_academy import _academy_promotions
    s = deepcopy(initial)
    r = s._world_squads
    summer = date(2027, 7, 1)
    cid = next(cid for cid, club in r.clubs.items()
        if cid != s.home_club.id and
        sum(p.age_on(summer) < 23 for p in club.squad.players) < 4 and
        sum(p.age_on(summer) >= 21 for p in r.youth.academies[cid].u21.values()) >= 2)
    club = r.clubs[cid]
    # Increase the squad to 25 with already registered older professionals.
    donor = next(c for other, c in r.clubs.items() if other != cid and other != s.home_club.id)
    additions = [p for p in donor.squad.players if p.age_on(summer) >= 25][:3]
    assert len(additions) == 3
    for player in additions:
        donor.squad._players.pop(player.id)
        club.squad.add(player)
    assert len(club.squad) == 25
    before = sum(p.age_on(summer) < 23 for p in club.squad.players)
    assert before < 4
    result = _academy_promotions(r, r.youth.academies[cid], summer,
                                 managed_club_id=s.home_club.id)
    after = sum(p.age_on(summer) < 23 for p in club.squad.players)
    assert result['u21_to_first'] == min(4 - before, 29 - 25)
    assert after == 4
    assert len(club.squad) <= 29
    assert len(r.youth.academies[cid].graduates) == result['u21_to_first']
