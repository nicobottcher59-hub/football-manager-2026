"""TS-17.2: match UI/stat consumers cannot confuse rival-player IDs."""
from dataclasses import replace

import pytest

from football_manager.dev_ui.session import DevelopmentSession
from football_manager.ui_shell.match import result_read_model


def test_goal_name_is_scoped_by_club_not_overwritten_by_opponent_id():
    session = DevelopmentSession()
    result = session.quick_simulate()
    goal = next(g for g in result.goals if g.club_id == session.home_club.id)
    scorer = next(player for player in session.home_club.squad.players
                  if player.id == goal.scorer_player_id)
    opponent = session.away_club.squad.players[0]
    opponent.identity = replace(opponent.identity, player_id=scorer.id,
                                first_name="Wrong", last_name="Opponent")
    view = result_read_model(session, {'home_name': 'Home', 'away_name': 'Away'}, result)
    goal_view = next(event for event in view['events']
                     if event['kind'] == 'goal' and event['club_id'] == goal.club_id
                     and event['player_id'] == goal.scorer_player_id)
    assert goal_view['player'] == scorer.full_name
    assert goal_view['player'] != opponent.full_name


def test_player_stat_lookup_rejects_ambiguous_local_ids():
    result = DevelopmentSession().quick_simulate()
    a = next(item for item in result.player_statistics if item.club_id == result.home_club_id)
    b = next(item for item in result.player_statistics if item.club_id == result.away_club_id)
    duplicated = replace(b, player_id=a.player_id)
    revised = replace(result, player_statistics=(a, duplicated))
    assert revised.player_stat(a.player_id, club_id=a.club_id) is a
    assert revised.player_stat(a.player_id, club_id=b.club_id) is duplicated
    with pytest.raises(ValueError, match='ambiguous'):
        revised.player_stat(a.player_id)
    with pytest.raises(KeyError):
        revised.player_stat('missing-player', club_id=a.club_id)


def test_player_stat_keeps_single_id_lookup_for_legacy_callers():
    result = DevelopmentSession().quick_simulate()
    a = result.player_statistics[0]
    assert result.player_stat(a.player_id) == a
    assert result.player_stat(a.player_id, club_id=a.club_id) == a
