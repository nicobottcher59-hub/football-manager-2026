"""Training read-model regression, updated for unified TS-UI-03.03 gameplay."""
from copy import deepcopy
import pytest
from football_manager.dev_ui.session import DevelopmentSession
from football_manager.services.club_support import training_command, training_read_model, recover_managed_players

@pytest.fixture(scope='module')
def baseline():return DevelopmentSession()

def test_training_model_exposes_shared_identity_and_real_current_values(baseline):
    model=training_read_model(baseline)
    assert model['club_id']==baseline.home_club.id
    assert model['club']==baseline.home_club.name
    assert len(model['players'])==len(baseline.home_club.squad.players)
    for player in baseline.home_club.squad.players:
        row=next(x for x in model['players'] if x['id']==player.id)
        assert row['name']==player.full_name
        assert row['position']==player.primary_position.value
        assert row['condition']==round(player.state.condition,1)
        assert row['sharpness']==round(player.state.match_sharpness,1)
        assert row['individual_focus']==(player.development.focus if player.development else 'balanced')
        assert row['intensity_source']=='automatic'
        assert 'group' not in row and 'protected' not in row

def test_training_read_model_is_pure(baseline):
    s=deepcopy(baseline)
    before=[(p.id,p.state.condition,p.state.match_sharpness,p.state.fatigue) for p in s.home_club.squad.players]
    policy=deepcopy(s._world_squads.club_support[s.home_club.id].training)
    training_read_model(s);training_read_model(s)
    assert [(p.id,p.state.condition,p.state.match_sharpness,p.state.fatigue) for p in s.home_club.squad.players]==before
    assert s._world_squads.club_support[s.home_club.id].training==policy

def test_automatic_energy_rule_and_individual_override(baseline):
    s=deepcopy(baseline); player=s.home_club.squad.players[0]
    player.state.fitness=46.;player.state.fatigue=10.;player.state.match_sharpness=40.
    before=next(p for p in training_read_model(s)['players'] if p['id']==player.id)
    assert before['effective']=='light'
    training_command(s,{'action':'individual','player_id':player.id,'intensity':'intense'})
    after=next(p for p in training_read_model(s)['players'] if p['id']==player.id)
    assert after['effective']=='intense' and after['intensity_source']=='individual'
    training_command(s,{'action':'individual','player_id':player.id,'intensity':'default'})
    assert next(p for p in training_read_model(s)['players'] if p['id']==player.id)['effective']=='light'

def test_injuries_skip_workouts_even_with_manual_intensity(baseline):
    s=deepcopy(baseline);player=s.home_club.squad.players[0]
    training_command(s,{'action':'individual','player_id':player.id,'intensity':'intense'})
    player.state.injury='Muscle strain'
    recover_managed_players(s,days=1)
    assert player.id not in s._world_squads.club_support[s.home_club.id].training_days
    assert next(p for p in training_read_model(s)['players'] if p['id']==player.id)['injured']

def test_current_player_ids_not_group_membership(baseline):
    model=training_read_model(baseline)
    ids={p.id for p in baseline.home_club.squad.players}
    assert {p['id'] for p in model['players']}==ids
    assert model['individual_override_count']==0
    assert 'policy' not in model and 'protection' not in model
