"""TS-UI-08: public-only search, persisted shortlist and scout territories."""
from __future__ import annotations

from copy import deepcopy
from datetime import timedelta

import pytest

from football_manager.dev_ui.session import DevelopmentSession
from football_manager.persistence.session_codec import capture_manager_graph, restore_manager_graph, GRAPH_VERSION
from football_manager.services.manager_inbox import inbox_read_model
from football_manager.services.professional_scouting import (
    scouting_hub_read_model, scouting_command, advance_professional_scouting,
)


@pytest.fixture(scope='module')
def seed():
    return DevelopmentSession()


def test_world_search_is_unrestricted_but_hides_confidential_information(seed):
    session = deepcopy(seed)
    first = scouting_hub_read_model(session)
    assert first['club_id'] == session.home_club.id
    assert len(first['players']) > 100
    assert first['scouts']
    assert first['capacity'] >= len(first['scouts'])
    assert first['clubs']
    assert first['countries']
    for player in first['players']:
        assert player['id'] and player['name'] and player['club_id']
        assert player['age'] > 0 and player['position'] in player['positions']
        assert player['height_cm'] is None and player['weight_kg'] is None
        assert player.get('report') is None
        assert all(k not in player for k in ('ovr', 'value_gbp', 'potential', 'overall_rating', 'true_value'))
    assert first == scouting_hub_read_model(session)  # GET is pure and deterministic


def test_shortlist_add_priority_remove_stays_independent_from_scouts(seed):
    s = deepcopy(seed)
    pid = scouting_hub_read_model(s)['players'][0]['id']
    dept = s._world_squads.club_support[s.home_club.id]
    assert scouting_command(s, {'action':'shortlist_add','player_id':pid,'priority':'top'})['shortlist_priority'] == 'top'
    assert scouting_hub_read_model(s)['shortlisted'] == 1
    assert dept.scouting_assignments == {}
    scouting_command(s, {'action':'shortlist_priority','player_id':pid,'priority':'future'})
    assert dept.scouting_shortlist[pid] == 'future'
    for bad in ('other','',None):
        with pytest.raises(ValueError):
            scouting_command(s, {'action':'shortlist_add','player_id':pid,'priority':bad})
    for bad in ('not-a-player',s.home_club.squad.players[0].id):
        with pytest.raises(ValueError):
            scouting_command(s, {'action':'shortlist_add','player_id':bad})
    scouting_command(s, {'action':'shortlist_remove','player_id':pid})
    assert scouting_hub_read_model(s)['shortlisted'] == 0


def test_scout_destination_is_real_staff_and_saved(seed):
    s=deepcopy(seed)
    current=scouting_hub_read_model(s)
    mid=current['scouts'][0]['id']
    league=current['leagues'][0]
    scouting_command(s, {'action':'destination','scout_id':mid,'destination':'league:'+league})
    assert scouting_hub_read_model(s)['scouts'][0]['destination'] == 'league:'+league
    assert all(r['destination']=='league:'+league for r in scouting_hub_read_model(s)['recommendations'] if r['scout_id']==mid)
    for bad in ('continent:Mars','league:fake'):
        with pytest.raises(ValueError):
            scouting_command(s, {'action':'destination','scout_id':mid,'destination':bad})
    with pytest.raises(ValueError):
        scouting_command(s, {'action':'destination','scout_id':'missing','destination':'all'})
    assert capture_manager_graph(s)['version'] == GRAPH_VERSION
    restored=restore_manager_graph(capture_manager_graph(s))
    assert restored._world_squads.club_support[restored.home_club.id].scouting_destinations[mid] == 'league:'+league
    restored._world_squads.club_support[restored.home_club.id].validate()


def test_reports_unlock_only_estimates_and_inbox(seed):
    s=deepcopy(seed)
    pid=scouting_hub_read_model(s)['players'][0]['id']
    scouting_command(s, {'action':'shortlist_add','player_id':pid,'priority':'monitor'})
    scouting_command(s, {'action':'assign','player_id':pid})
    current=next(p for p in scouting_hub_read_model(s)['players'] if p['id']==pid)
    assert 'report' not in current
    assert current['scouting']['progress'] == 0
    assert current['priority'] == 'monitor'
    for _ in range(20):
        s.current_date += timedelta(days=1)
        advance_professional_scouting(s,s.current_date)
    current=next(p for p in scouting_hub_read_model(s)['players'] if p['id']==pid)
    assert 'report' in current and 'scouting' not in current
    report=current['report']
    assert len(report['overall_range'])==2 and report['overall_range'][0]<=report['overall_range'][1]
    assert len(report['potential_range'])==2 and report['potential_range'][0]<=report['potential_range'][1]
    assert len(report['value_range_gbp'])==2
    assert report['confidence']<=94
    assert report['attributes'] and all(len(a['range'])==2 for a in report['attributes'])
    assert 'potential' not in current and 'ovr' not in current and 'value_gbp' not in current
    assert current['priority'] == 'monitor'
    notices=inbox_read_model(s)['messages']
    assert any(n['source_key'].startswith('professional-scout:report:') and pid in n['source_key'] for n in notices)
    restored=restore_manager_graph(capture_manager_graph(s))
    again=next(p for p in scouting_hub_read_model(restored)['players'] if p['id']==pid)
    assert again['report']==report and again['priority']=='monitor'
