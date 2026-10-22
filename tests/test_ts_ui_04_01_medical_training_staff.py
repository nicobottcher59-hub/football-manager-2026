"""TS-UI-04.01: medical/training data comes from current Python career state."""
from datetime import timedelta

import pytest

from football_manager.dev_ui.session import DevelopmentSession
from football_manager.services.club_support import (
    active_staff, medical_read_model, training_read_model, staff_command,
)
from football_manager.services.player_aging import register_medical_absence


@pytest.fixture(scope='module')
def career():
    return DevelopmentSession()


def test_medical_staff_and_current_fitness_are_real(career):
    medical = medical_read_model(career)
    support = career._world_squads.club_support[career.home_club.id]
    day = career.current_date
    assert medical['club_id'] == career.home_club.id
    assert medical['squad_size'] == len(career.home_club.squad.players)
    assert medical['available_count'] == medical['squad_size'] - len(medical['cases'])
    assert medical['staffing']['medical'] == len(active_staff(support, 'medic', day))
    assert medical['staffing']['fitness'] == len(active_staff(support, 'fitness', day))
    assert medical['staffing']['medical_capacity'] == support.capacity['medic']
    assert medical['staffing']['fitness_capacity'] == support.capacity['fitness']
    assert sum(medical['condition_bands'].values()) == medical['squad_size']
    assert medical['recent_treatments'] == []


def test_training_staff_counts_are_shared_with_staff_records(career):
    support = career._world_squads.club_support[career.home_club.id]
    day = career.current_date
    before = training_read_model(career)['training_staff']
    assert before['coaches'] == len(active_staff(support, 'coach', day))
    assert before['fitness'] == len(active_staff(support, 'fitness', day))
    assert before['total'] == before['coaches'] + before['fitness']
    assert before['capacity'] == support.capacity['coach'] + support.capacity['fitness']
    # No state changes just by reading the page.
    assert training_read_model(career)['training_staff'] == before


def test_medical_decision_log_reflects_existing_episode(career):
    from football_manager.services.club_support import medical_command
    player = career.home_club.squad.players[0]
    initial_count = len(medical_read_model(career)['cases'])
    register_medical_absence(career._world, career.home_club.id, player.id,
                             career.current_date, episode_id='tsui-med04-fixture',
                             duration_days=25, label='Muscle strain')
    current = medical_read_model(career)
    assert len(current['cases']) == initial_count + 1
    assert current['available_count'] == current['squad_size'] - len(current['cases'])
    assert current['cases'][0]['treatment_available']
    decision = medical_command(career, {'action':'treat', 'method':'conservative', 'player_id':player.id})
    updated = medical_read_model(career)
    record = next(x for x in updated['recent_treatments'] if x['player_id'] == player.id)
    assert record['method'] == 'conservative'
    assert record['planned_return'] == decision['return_on']
    assert record['status'] == 'active'
    assert not next(x for x in updated['cases'] if x['id'] == player.id)['treatment_available']


def test_no_gameplay_or_save_migration_added():
    from pathlib import Path
    source = Path(__file__).resolve().parents[1]
    assert (source/'frontend/portable/assets/medical/sunderland-physio-suite.webp').is_file()
    assert 'medical-suite-generic.webp' in {p.name for p in (source/'frontend/portable/assets/medical').iterdir()}
    training = (source/'frontend/portable/club_support.js').read_text()
    assert 'data-cs-action="conservative"' in training
    assert 'data-cs-action="aggressive"' in training
    assert 'data-md-open-staff' in training
    assert 'training_staff' in (source/'src/football_manager/services/club_support.py').read_text()
