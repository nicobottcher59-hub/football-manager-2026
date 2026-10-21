"""TS-UI-03.03: automatic bands, personalized daily training, saves."""
from copy import deepcopy
import pytest
from football_manager.dev_ui.session import DevelopmentSession
from football_manager.domain.club_support import TrainingPolicy
from football_manager.persistence.session_codec import GRAPH_VERSION,capture_manager_graph,restore_manager_graph
from football_manager.services.club_support import effective_intensity,training_command,training_read_model,recover_managed_players
from football_manager.services.player_development import set_development_focus

@pytest.fixture(scope='module')
def career():return DevelopmentSession()

def test_automatic_bands_prioritize_energy():
    p=TrainingPolicy()
    assert effective_intensity(p,95,0,None,sharpness=40)=='intense'
    assert effective_intensity(p,95,0,None,sharpness=55)=='balanced'
    assert effective_intensity(p,45,0,None,sharpness=40)=='light'
    assert effective_intensity(p,55,0,None,sharpness=40)=='balanced'
    assert effective_intensity(p,95,0,1,sharpness=40)=='balanced' or effective_intensity(p,95,0,1,sharpness=40)=='light'

def test_linked_thresholds_push_the_neighbour(career):
    s=deepcopy(career)
    r=training_command(s,{'action':'configure','auto_thresholds':{'performance_max':88},'changed_field':'performance_max'})
    assert (r['auto_thresholds']['performance_max'],r['auto_thresholds']['performance_focus'])==(88,89)
    r=training_command(s,{'action':'configure','auto_thresholds':{'energy_focus':21},'changed_field':'energy_focus'})
    assert (r['auto_thresholds']['energy_max'],r['auto_thresholds']['energy_focus'])==(20,21)
    r=training_command(s,{'action':'configure','auto_thresholds':{'performance_max':100},'changed_field':'performance_max'})
    assert (r['auto_thresholds']['performance_max'],r['auto_thresholds']['performance_focus'])==(99,100)

def test_individual_exceptions_survive_lineup_changes(career):
    s=deepcopy(career);player=s.home_club.squad.players[0]
    training_command(s,{'action':'individual','player_id':player.id,'intensity':'intense'})
    p=s._world_squads.club_support[s.home_club.id].training
    assert effective_intensity(p,95,0,None,player_id=player.id,sharpness=80)=='intense'
    assert effective_intensity(p,55,0,None,player_id=player.id,sharpness=80)=='intense'
    assert next(x for x in training_read_model(s)['players'] if x['id']==player.id)['intensity_source']=='individual'
    training_command(s,{'action':'individual','player_id':player.id,'intensity':'default'})
    assert player.id not in p.individual_intensities or player.id not in s._world_squads.club_support[s.home_club.id].training.individual_intensities
    with pytest.raises(ValueError): training_command(s,{'action':'individual','player_id':'other:club','intensity':'intense'})

def test_removed_group_and_physical_protection_commands_are_rejected(career):
    s=deepcopy(career);dept=s._world_squads.club_support[s.home_club.id]
    before=deepcopy(dept.training)
    for legacy in ({'action':'configure','group':'bench','intensity':'intense'},
                   {'action':'configure','protection':False},
                   {'action':'configure','apply_auto_all':True},
                   {'action':'configure','low_condition':75,'medium_condition':85}):
        with pytest.raises(ValueError): training_command(s,legacy)
    assert dept.training==before

def test_manual_workload_changes_actual_daily_training(career):
    a=deepcopy(career);b=deepcopy(career);player=a.home_club.squad.players[0]
    training_command(a,{'action':'individual','player_id':player.id,'intensity':'intense'})
    recover_managed_players(a,days=1);recover_managed_players(b,days=1)
    assert a._world_squads.club_support[a.home_club.id].training_days[player.id][0] > b._world_squads.club_support[b.home_club.id].training_days[player.id][0]

def test_player_development_focus_remains_shared_with_squad(career):
    s=deepcopy(career);p=s.home_club.squad.players[0]
    set_development_focus(s,p.id,'mental')
    row=next(x for x in training_read_model(s)['players'] if x['id']==p.id)
    assert row['individual_focus']=='mental' and 'mental' in training_read_model(s)['focus_options']

def test_v23_to_v24_save_migration_preserves_personal_training(career):
    assert GRAPH_VERSION==24
    s=deepcopy(career);p=s.home_club.squad.players[0]
    training_command(s,{'action':'individual','player_id':p.id,'intensity':'intense'})
    g=capture_manager_graph(s)
    for node in g['nodes']:
        if node.get('class')=='football_manager.domain.club_support:TrainingPolicy':
            node['fields'].update(starters='light',bench='balanced',rest='intense',protection=True,low_condition=70,medium_condition=85)
    g['version']=23
    loaded=restore_manager_graph(g)
    restored=loaded._world_squads.club_support[loaded.home_club.id].training
    assert restored.individual_intensities[p.id]=='intense'
    assert not hasattr(restored,'starters')
    loaded._world_squads.validate()

def test_v24_save_roundtrip_keeps_individual_overrides(career):
    s=deepcopy(career);p=s.home_club.squad.players[1]
    training_command(s,{'action':'configure','auto_thresholds':{'energy_max':61},'changed_field':'energy_max'})
    training_command(s,{'action':'individual','player_id':p.id,'intensity':'light'})
    graph=capture_manager_graph(s);assert graph['version']==24
    loaded=restore_manager_graph(graph)
    policy=loaded._world_squads.club_support[loaded.home_club.id].training
    assert policy.individual_intensities[p.id]=='light'
    assert (policy.energy_max,policy.energy_focus)==(61,62)
    assert len(training_read_model(loaded)['players'])==len(career.home_club.squad.players)
