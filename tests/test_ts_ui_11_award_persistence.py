"""Existing save graph stores new award categories without schema changes."""
from football_manager.dev_ui.session import DevelopmentSession
from football_manager.domain.career_recognition import IndividualAward
from football_manager.persistence.session_codec import GRAPH_VERSION, capture_manager_graph, restore_manager_graph


def test_new_certified_awards_round_trip_in_existing_graph_version():
    session=DevelopmentSession()
    registry=session._world_squads
    p=session.home_club.squad.players[0]
    label=registry.season_label
    award=IndividualAward(label,'world','world_young',p.id,session.home_club.id)
    registry.individual_awards[label]=(award,)
    graph=capture_manager_graph(session)
    assert graph['version']==GRAPH_VERSION==32
    restored=restore_manager_graph(graph)
    assert restored._world_squads.individual_awards[label]==(award,)
