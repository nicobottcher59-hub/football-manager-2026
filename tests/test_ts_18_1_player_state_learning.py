"""TS-18.1: existing ACT inputs must actually progress after played matches."""
from __future__ import annotations

from copy import deepcopy

import pytest

from football_manager.dev_ui import DevelopmentSession
from football_manager.domain import CurrentRatingContext
from football_manager.persistence import SQLiteSaveRepository, load_manager_career, save_manager_career
from football_manager.services.player_match_progression import apply_player_match_progression


def _starter(session: DevelopmentSession):
    return session.home_lineup.starters[0]


def test_existing_form_confidence_and_sharpness_move_with_real_played_minutes():
    session = DevelopmentSession()
    before = {p.id: (p.state.form, p.state.confidence, p.state.match_sharpness)
              for p in session.home_club.squad.players}
    result = session.quick_simulate()
    played = {x.player_id for x in result.player_statistics
              if x.club_id == session.home_club.id and x.minutes > 0}
    assert played
    assert any((p.state.form, p.state.confidence) != before[p.id][:2]
               for p in session.home_club.squad.players if p.id in played)
    assert any(p.state.match_sharpness > before[p.id][2]
               for p in session.home_club.squad.players if p.id in played)
    assert all((p.state.form, p.state.confidence, p.state.match_sharpness) == before[p.id]
               for p in session.home_club.squad.players if p.id not in played)


def test_match_learning_uses_ratings_not_just_minutes_and_does_not_rewrite_ovr():
    positive = DevelopmentSession().home_lineup.starters[0].player
    negative = deepcopy(positive)
    original_ovr = positive.overall_rating
    context = CurrentRatingContext(assigned_position=positive.primary_position)
    original_act = positive.current_rating(context).current
    apply_player_match_progression(positive, minutes=90, match_rating=9.0)
    apply_player_match_progression(negative, minutes=90, match_rating=4.0)
    assert positive.state.form > negative.state.form
    assert positive.state.confidence > negative.state.confidence
    assert positive.overall_rating == pytest.approx(original_ovr)
    assert positive.current_rating(context).current > original_act
    assert negative.current_rating(context).current < original_act


def test_role_and_tactic_learning_persist_after_tactical_recalculation():
    session = DevelopmentSession()
    entry = _starter(session)
    player = entry.player
    role_id = session.home_tactic.role_for_slot(entry.slot_id).role_id
    tactic_id = session.home_tactic.tactic_id
    old_role = player.tactical_familiarity.role_score(role_id)
    old_tactic = player.tactical_familiarity.tactic_score(tactic_id)
    session.quick_simulate()
    assert player.tactical_familiarity.role_score(role_id) > old_role
    assert player.tactical_familiarity.tactic_score(tactic_id) > old_tactic
    learned = player.tactical_familiarity.tactic_score(tactic_id)
    session._sync_effective_tactic_familiarity(home=True)
    assert player.tactical_familiarity.tactic_score(tactic_id) >= learned - 1e-6


def test_unplayed_player_gets_no_learning_and_poor_play_does_not_guarantee_role_growth():
    player = _starter(DevelopmentSession()).player
    role_id = 'advanced_forward'
    initial = deepcopy(player)
    apply_player_match_progression(player, minutes=0, match_rating=9.0,
                                   role_id=role_id, tactic_id='test-tactic')
    assert player.state == initial.state
    assert player.tactical_familiarity == initial.tactical_familiarity
    apply_player_match_progression(player, minutes=90, match_rating=3.0,
                                   role_id=role_id, tactic_id='test-tactic')
    assert player.tactical_familiarity.role_score(role_id) == initial.tactical_familiarity.role_score(role_id)
    assert player.tactical_familiarity.tactic_score('test-tactic') == 0.0
    assert player.state.form < initial.state.form


def test_failed_commit_restores_form_confidence_learning_and_baseline(monkeypatch):
    session = DevelopmentSession()
    players_before = [(p, deepcopy(p.state), deepcopy(p.tactical_familiarity))
                      for p in session.home_club.squad.players]
    baseline = dict(session._home_base_tactic_familiarity)
    original = session._record_active_match_result

    def broken(result):
        original(result)
        raise RuntimeError('injected failure after learning')

    monkeypatch.setattr(session, '_record_active_match_result', broken)
    with pytest.raises(RuntimeError, match='after learning'):
        session.quick_simulate()
    assert not session.match_played
    assert session._home_base_tactic_familiarity == baseline
    for player, state, familiarity in players_before:
        assert player.state == state
        assert player.tactical_familiarity == familiarity


def test_save_load_preserves_progression_and_future_match_determinism(tmp_path):
    one = DevelopmentSession()
    one.quick_simulate()
    repo = SQLiteSaveRepository(tmp_path / 'player-state.sqlite3')
    save_manager_career(repo, slot_id='one', display_name='One', expected_revision=0, session=one)
    two = load_manager_career(repo, 'one').session
    assert [(p.state.form, p.state.confidence, p.tactical_familiarity)
            for p in one.home_club.squad.players] == [
                (p.state.form, p.state.confidence, p.tactical_familiarity)
                for p in two.home_club.squad.players]
    one.continue_to_next_match()
    two.continue_to_next_match()
    result1 = one.quick_simulate()
    result2 = two.quick_simulate()
    assert result1 == result2
    assert [(p.state, p.tactical_familiarity) for p in one.home_club.squad.players] == [
        (p.state, p.tactical_familiarity) for p in two.home_club.squad.players]


def test_short_appearance_has_smaller_effect_than_full_match():
    full = _starter(DevelopmentSession()).player
    short = deepcopy(full)
    role_id = 'advanced_forward'
    full_gain = apply_player_match_progression(
        full, minutes=90, match_rating=8.5, role_id=role_id, tactic_id='fixture-tactic',
    )
    short_gain = apply_player_match_progression(
        short, minutes=20, match_rating=8.5, role_id=role_id, tactic_id='fixture-tactic',
    )
    assert full.state.form > short.state.form
    assert full.state.confidence > short.state.confidence
    assert full.state.match_sharpness > short.state.match_sharpness
    assert full_gain > short_gain > 0
    assert full.tactical_familiarity.role_score(role_id) > short.tactical_familiarity.role_score(role_id)


def test_player_state_is_bounded_and_does_not_change_attributes_or_morale():
    player = _starter(DevelopmentSession()).player
    attributes = player.attributes
    original_morale = player.state.morale
    for _ in range(150):
        apply_player_match_progression(player, minutes=120, match_rating=10,
                                       role_id='advanced_forward', tactic_id='test-tactic')
    assert player.attributes == attributes
    assert player.state.morale == original_morale  # Existing result-driven morale path owns this.
    assert all(0 <= value <= 100 for value in (
        player.state.form, player.state.confidence, player.state.match_sharpness,
        player.tactical_familiarity.role_score('advanced_forward'),
        player.tactical_familiarity.tactic_score('test-tactic'),
    ))
    for _ in range(150):
        apply_player_match_progression(player, minutes=90, match_rating=1,
                                       role_id='advanced_forward', tactic_id='test-tactic')
    assert all(0 <= value <= 100 for value in (
        player.state.form, player.state.confidence, player.state.match_sharpness,
    ))


def test_edited_role_learns_only_in_actual_slot_and_is_not_reset_by_tactic_sync():
    session = DevelopmentSession()
    entry = _starter(session)
    old_role = session.home_tactic.role_for_slot(entry.slot_id).role_id
    from football_manager.domain.roles import roles_for_position
    position = session.home_lineup.formation.slot(entry.slot_id).position
    replacement = next(role.role_id for role in roles_for_position(position)
                       if role.role_id != old_role)
    session.set_role(entry.slot_id, replacement)
    before = entry.player.tactical_familiarity.role_score(replacement)
    previous_old = entry.player.tactical_familiarity.role_score(old_role)
    session.quick_simulate()
    # The rating can be unfavorable, but even if so the role must not be faked.
    assert entry.player.tactical_familiarity.role_score(replacement) >= before
    assert entry.player.tactical_familiarity.role_score(old_role) == previous_old
    gained = entry.player.tactical_familiarity.tactic_score(session.home_tactic.tactic_id)
    session._sync_effective_tactic_familiarity(home=True)
    assert entry.player.tactical_familiarity.tactic_score(session.home_tactic.tactic_id) == pytest.approx(gained)


def test_failed_progression_reverts_tactical_baselines_before_retry(monkeypatch):
    session = DevelopmentSession()
    before_home = dict(session._home_base_tactic_familiarity)
    before_away = dict(session._away_base_tactic_familiarity)
    before_players = [(p, deepcopy(p.state), deepcopy(p.tactical_familiarity))
                      for team in (session.home_club, session.away_club)
                      for p in team.squad.players]
    original = session._persist_match_progression
    def fail_after_progression(*args, **kwargs):
        original(*args, **kwargs)
        raise RuntimeError('injected progress failure')
    monkeypatch.setattr(session, '_persist_match_progression', fail_after_progression)
    with pytest.raises(RuntimeError, match='injected progress failure'):
        session.quick_simulate()
    assert session._home_base_tactic_familiarity == before_home
    assert session._away_base_tactic_familiarity == before_away
    for player, state, tactic in before_players:
        assert player.state == state
        assert player.tactical_familiarity == tactic
    assert session.match_played is False
    monkeypatch.undo()
    assert session.quick_simulate().match_id


@pytest.mark.parametrize('rating', (1.0, 3.0, 4.0, 9.0, 10.0))
def test_single_match_has_small_bounded_effect_even_at_extreme_ratings(rating):
    player = _starter(DevelopmentSession()).player
    before_form, before_confidence, before_morale = (
        player.state.form, player.state.confidence, player.state.morale
    )
    apply_player_match_progression(player, minutes=90, match_rating=rating)
    assert abs(player.state.form - before_form) <= 2.0 + 1e-8
    assert abs(player.state.confidence - before_confidence) <= 1.25 + 1e-8
    # This service doesn't override the game's existing result-driven morale.
    assert player.state.morale == before_morale


def test_bad_match_streak_is_gradual_and_good_matches_can_recover_confidence():
    player = _starter(DevelopmentSession()).player
    initial_confidence = player.state.confidence
    initial_form = player.state.form
    apply_player_match_progression(player, minutes=90, match_rating=1.0)
    assert player.state.confidence >= initial_confidence - 1.25
    assert player.state.form >= initial_form - 2.0
    for _ in range(7):
        apply_player_match_progression(player, minutes=90, match_rating=1.0)
    # A prolonged run matters, but eight terrible performances do not empty the meter.
    assert initial_confidence - 10 <= player.state.confidence < initial_confidence
    assert initial_form - 16 <= player.state.form < initial_form
    after_bad_run = player.state.confidence
    for _ in range(4):
        apply_player_match_progression(player, minutes=90, match_rating=9.0)
    assert player.state.confidence > after_bad_run


def test_short_appearance_has_proportional_per_match_limits():
    player = _starter(DevelopmentSession()).player
    start_form = player.state.form
    start_confidence = player.state.confidence
    apply_player_match_progression(player, minutes=20, match_rating=1.0)
    assert start_form - player.state.form <= 2.0 * 20 / 90 + 1e-8
    assert start_confidence - player.state.confidence <= 1.25 * 20 / 90 + 1e-8
