"""TS-UI-11 player-ID read model, real season totals and award certificates."""
from types import SimpleNamespace

from football_manager.dev_ui.session import DevelopmentSession
from football_manager.domain.season_statistics import SeasonPlayerStatistics
from football_manager.services.career_recognition import award_season
from football_manager.ui_shell.career_history import player_career_read_model


def test_player_history_has_stable_identity_and_no_invented_results():
    session=DevelopmentSession()
    player=session.home_club.squad.players[0]
    result=player_career_read_model(session, player.id)
    assert result['id']==player.id
    assert result['age']==player.age_on(session.current_date)
    assert result['preferred_foot']==player.identity.dominant_foot.value
    assert result['overall_rating'] == round(player.overall_rating,1)
    assert result['current_club_id']==session.home_club.id
    assert not result['honours'] and not result['awards']
    assert all(isinstance(season['competitions'],list) for season in result['seasons'])
    assert result==player_career_read_model(session, player.id)


def test_certified_world_awards_are_recorded_and_idempotent_without_puskas():
    season='2026/27'
    def person(pid,age):
        return SimpleNamespace(id=pid,age_on=lambda on_date: age,
            primary_position=SimpleNamespace(value='ST'))
    a=person('forward-young',20)
    b=person('forward-senior',29)
    ledger=SimpleNamespace(
        complete_seasons={season:True},
        seasons={season:{'dev-premier':{
            a.id:SeasonPlayerStatistics(appearances=5,starts=5,minutes=450,goals=8,assists=1,rating_total=39),
            b.id:SeasonPlayerStatistics(appearances=5,starts=5,minutes=450,goals=5,assists=2,rating_total=40)
        }}}
    )
    registry=SimpleNamespace(
        clubs={'a':SimpleNamespace(squad=SimpleNamespace(players=[a,b]))},
        free_agents={},retired_players={},statistics=ledger,
        individual_awards={},player_season_clubs={season:{a.id:('a',),b.id:('a',)}},
        identities={'a':SimpleNamespace(tier=1)})
    world=SimpleNamespace(leagues={'dev-premier':SimpleNamespace(participant_club_ids=['a'])},staged={})
    report=SimpleNamespace(season_label=season)
    from datetime import date
    count=award_season(registry,world,report,as_of=date(2027,6,30))
    cats={x.category for x in registry.individual_awards[season]}
    assert count>0
    assert {'world_player','world_young','golden_shoe','player','goals'}.issubset(cats)
    assert 'puskas' not in cats
    assert award_season(registry,world,report,as_of=date(2027,6,30))==0
    assert len(registry.individual_awards[season])==count



def test_recorded_competition_breakdown_uses_stable_ids_and_real_ledger():
    # Isolated ledger fixture: no whole-season simulation or fabricated UI
    # history is required to prove the read model wiring.
    session=DevelopmentSession()
    reg=session._world_squads
    season=reg.season_label
    player=session.home_club.squad.players[0]
    reg.statistics.seasons.setdefault(season,{})['dev-premier']={
        player.id: SeasonPlayerStatistics(appearances=2, starts=2, minutes=180,
                                          goals=1, assists=1, rating_total=14)}
    reg.player_season_clubs.setdefault(season,{})[player.id]=(session.home_club.id,)
    result=player_career_read_model(session,player.id)
    record=next(r for r in result['seasons'] if r['season']==season)
    assert record['clubs'][0]['id']==session.home_club.id
    assert len(record['competitions'])==1
    breakdown=record['competitions'][0]
    assert breakdown['competition_id']=='dev-premier'
    assert breakdown['statistics']['appearances']==2
    assert breakdown['statistics']['goals']==1
