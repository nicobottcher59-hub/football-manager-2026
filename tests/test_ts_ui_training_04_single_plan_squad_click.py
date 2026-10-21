"""TS-UI-03.03: removed legacy training systems, persistent shared plan and Squad selection."""
from copy import deepcopy
from dataclasses import fields
from pathlib import Path

import pytest

from football_manager.dev_ui.session import DevelopmentSession
from football_manager.domain.club_support import TrainingPolicy
from football_manager.persistence.session_codec import (GRAPH_VERSION, capture_manager_graph,
                                                        restore_manager_graph)
from football_manager.services.club_support import (effective_intensity, recover_managed_players,
                                                     training_command, training_read_model)


@pytest.fixture(scope='module')
def baseline():
    return DevelopmentSession()


def test_one_global_automatic_plan_not_three_old_systems(baseline):
    policy = baseline._world_squads.club_support[baseline.home_club.id].training
    assert {f.name for f in fields(TrainingPolicy)} == {
        'performance_max', 'performance_focus', 'energy_max', 'energy_focus',
        'individual_intensities'}
    model = training_read_model(baseline)
    assert len(model['players']) == len(baseline.home_club.squad.players)
    assert not set(model).intersection({'policy', 'protection', 'low_condition', 'medium_condition'})
    assert all(not set(player).intersection({'group', 'protected', 'protection_effect'})
               for player in model['players'])
    assert policy.validate() is None
    assert effective_intensity(policy, 45., 5., None, sharpness=40.) == 'light'
    assert effective_intensity(policy, 95., 5., None, sharpness=40.) == 'intense'


def test_personal_plan_override_reset_and_daily_simulation(baseline):
    automatic, personal = deepcopy(baseline), deepcopy(baseline)
    player = automatic.home_club.squad.players[0]
    other = personal.home_club.squad.get(player.id)
    for s in (automatic, personal):
        p = s.home_club.squad.get(player.id)
        p.state.fitness = 95.
        p.state.fatigue = 0.
    training_command(personal, {'action':'individual','player_id':player.id,'intensity':'intense'})
    policy = personal._world_squads.club_support[personal.home_club.id].training
    assert effective_intensity(policy, 45., 10., 0, player_id=player.id, sharpness=95.) == 'intense'
    assert effective_intensity(policy, 45., 10., 0, player_id='another', sharpness=95.) == 'light'
    assert training_read_model(personal)['individual_override_count'] == 1
    recover_managed_players(automatic, days=1)
    recover_managed_players(personal, days=1)
    original = automatic._world_squads.club_support[automatic.home_club.id].training_days[player.id]
    custom = personal._world_squads.club_support[personal.home_club.id].training_days[player.id]
    assert custom[0] > original[0] and custom[1] == original[1] == 1
    training_command(personal, {'action':'individual','player_id':player.id,'intensity':'default'})
    assert training_read_model(personal)['individual_override_count'] == 0
    assert player.id not in personal._world_squads.club_support[personal.home_club.id].training.individual_intensities


def test_four_linked_thresholds_are_atomic_and_old_commands_rejected(baseline):
    s = deepcopy(baseline)
    policy = s._world_squads.club_support[s.home_club.id].training
    result = training_command(s, {'action':'configure','auto_thresholds':{'energy_max':87},'changed_field':'energy_max'})
    assert (result['auto_thresholds']['energy_max'], result['auto_thresholds']['energy_focus']) == (87,88)
    saved = deepcopy(s._world_squads.club_support[s.home_club.id].training)
    for legacy in ({'action':'configure','group':'starters','intensity':'intense'},
                   {'action':'configure','protection':False},
                   {'action':'configure','low_condition':30,'medium_condition':95},
                   {'action':'configure','apply_auto_all':True},
                   {'action':'individual','player_id':s.home_club.squad.players[0].id,'intensity':'group'}):
        with pytest.raises(ValueError):training_command(s,legacy)
    assert s._world_squads.club_support[s.home_club.id].training == saved


def test_v23_career_migrates_without_legacy_group_or_protection_fields(baseline):
    s=deepcopy(baseline)
    ident=s.home_club.squad.players[0].id
    training_command(s, {'action':'individual','player_id':ident,'intensity':'light'})
    training_command(s, {'action':'configure','auto_thresholds':{'performance_max':78},'changed_field':'performance_max'})
    assert GRAPH_VERSION == 24
    graph = capture_manager_graph(s)
    assert graph['version'] == 24
    found = 0
    for node in graph['nodes']:
        if node.get('class') == 'football_manager.domain.club_support:TrainingPolicy':
            node['fields'].update(starters='intense',bench='light',rest='balanced',
                                  protection=False,low_condition=62,medium_condition=90)
            found += 1
    graph['version'] = 23
    assert found
    loaded = restore_manager_graph(graph)
    dept = loaded._world_squads.club_support[loaded.home_club.id]
    assert dept.training.individual_intensities[ident] == 'light'
    assert (dept.training.performance_max,dept.training.performance_focus)==(78,79)
    assert not hasattr(dept.training, 'protection')
    assert not hasattr(dept.training, 'starters')
    dept.validate()
    roundtrip = capture_manager_graph(loaded)
    for node in roundtrip['nodes']:
        if node.get('class') == 'football_manager.domain.club_support:TrainingPolicy':
            assert not set(node['fields']).intersection({'starters','bench','rest','protection','low_condition','medium_condition'})
    # Unsupported legacy field injection into a CURRENT v24 save is rejected.
    for node in roundtrip['nodes']:
        if node.get('class') == 'football_manager.domain.club_support:TrainingPolicy':
            node['fields']['starters'] = 'intense'
            break
    with pytest.raises(Exception): restore_manager_graph(roundtrip)


def test_v22_career_fills_adaptive_defaults_and_discards_old_settings(baseline):
    old = capture_manager_graph(deepcopy(baseline))
    for node in old['nodes']:
        if node.get('class') == 'football_manager.domain.club_support:TrainingPolicy':
            for k in ('performance_max','performance_focus','energy_max','energy_focus','individual_intensities'):
                node['fields'].pop(k)
            node['fields'].update(starters='light',bench='balanced',rest='intense',
                                  protection=True,low_condition=70,medium_condition=85)
    old['version'] = 22
    loaded = restore_manager_graph(old)
    policy = loaded._world_squads.club_support[loaded.home_club.id].training
    assert (policy.performance_max,policy.performance_focus,policy.energy_max,policy.energy_focus) == (50,60,50,60)
    assert policy.individual_intensities == {}
    loaded._world_squads.validate()


def test_squad_rows_send_real_dom_nodes_to_selection_handler():
    root = Path(__file__).resolve().parents[1]
    js = (root/'frontend/public/squad/squad.js').read_text()
    assert 'window.FMRoster.onClick(row,refreshKeepingTable)' in js
    assert 'window.FMRoster.onClick(card,refreshKeepingTable)' in js
    assert 'onClick({dataset:{rosterExpand:' not in js
    assert 'if(button.dataset.rosterExpand)' in (root/'frontend/public/squad/squad_ui02.js').read_text()
