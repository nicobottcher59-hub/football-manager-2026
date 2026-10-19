"""TS-15: full manager save/load, identity and continuation, safety and HTTP."""
from __future__ import annotations

from dataclasses import replace
from datetime import date
import json
import sqlite3
from threading import Thread
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from football_manager.dev_ui.session import DevelopmentSession
from football_manager.persistence import (
    SQLiteSaveRepository, SaveConflictError, SaveIntegrityError, SaveSection,
    UnsupportedSaveVersionError, load_manager_career, save_manager_career,
    load_world_results, save_world_results, manager_career_document,
)
from football_manager.persistence.session_codec import capture_manager_graph, restore_manager_graph
from football_manager.ui_shell.models import UIRosterAdmin
from football_manager.ui_shell.progression import simulate_until
from football_manager.ui_shell.server import create_server, default_save_path


def _repo(tmp_path):
    return SQLiteSaveRepository(tmp_path / 'career.sqlite3')


def _save(repo, session=None, **kwargs):
    return save_manager_career(repo, slot_id=kwargs.pop('slot_id', 'career-1'),
                               display_name=kwargs.pop('display_name', 'Mi Carrera'),
                               expected_revision=kwargs.pop('expected_revision', 0),
                               session=session or DevelopmentSession(), **kwargs)


def _player_by_id(club, pid):
    return next(player for player in club.squad.players if player.id == pid)


def test_complete_manager_state_roundtrip_preserves_shared_references_and_admin(tmp_path):
    session = DevelopmentSession()
    session.set_formation(next(fid for fid, name in session.available_formations
                               if '4-4-2' in name))
    session.dev_favorable_mode = True
    player = session.home_lineup.starting_players[0]
    player.state.morale = 44.0
    admin = UIRosterAdmin(numbers={player.id: 9}, transfer_statuses={player.id: 'untouchable'})
    repo = _repo(tmp_path)
    meta = _save(repo, session, admin=admin)
    assert meta.kind == 'manager_career'

    loaded = load_manager_career(repo, 'career-1')
    restored = loaded.session
    assert loaded.admin == admin
    assert restored.home_lineup.formation.formation_id == session.home_lineup.formation.formation_id
    assert restored.dev_favorable_mode is True
    assert restored.current_date == session.current_date
    assert restored._seed == session._seed and restored._next_seed == session._next_seed
    assert restored._career.current is restored._world
    assert restored.home_lineup.starting_players[0] is _player_by_id(restored.home_club, player.id)
    assert restored.home_lineup.starting_players[0].state.morale == 44.0
    assert restored._world.to_dict() == session._world.to_dict()
    assert {section.name for section in repo.load('career-1').document.sections} == {
        'manager_state', 'ui_metadata',
    }


def test_career_can_continue_after_loading_with_identical_results_and_player_state(tmp_path):
    session = DevelopmentSession()
    simulate_until(session, date(2026, 8, 25))
    repo = _repo(tmp_path)
    _save(repo, session)
    recovered = load_manager_career(repo, 'career-1').session
    target = date(2026, 9, 3)
    original_outcome = simulate_until(session, target)
    loaded_outcome = simulate_until(recovered, target)
    assert original_outcome['managed_matches'] == loaded_outcome['managed_matches']
    assert recovered._world.to_dict() == session._world.to_dict()
    assert recovered.current_date == session.current_date == target
    assert recovered._seed == session._seed
    assert [p.state for p in recovered.home_club.squad.players] == [p.state for p in session.home_club.squad.players]
    assert [p.positional_familiarity for p in recovered.home_club.squad.players] == [
        p.positional_familiarity for p in session.home_club.squad.players]


def test_manager_slots_are_revisioned_and_old_revisions_cannot_overwrite(tmp_path):
    repo = _repo(tmp_path)
    session = DevelopmentSession()
    first = _save(repo, session)
    second = _save(repo, session, expected_revision=first.revision)
    assert first.revision == 1 and second.revision == 2
    with pytest.raises(SaveConflictError):
        _save(repo, session, expected_revision=1)
    assert load_manager_career(repo, 'career-1').metadata.revision == 2


def test_unsaved_or_invalid_world_state_cannot_overwrite_existing_slot(tmp_path):
    repo = _repo(tmp_path)
    session = DevelopmentSession()
    _save(repo, session)
    first = session.home_lineup.starting_players[0]
    clone = type(first)(**{f.name: getattr(first, f.name) for f in __import__('dataclasses').fields(first)})
    session.home_lineup = replace(
        session.home_lineup, starters=(replace(session.home_lineup.starters[0], player=clone),
                                       *session.home_lineup.starters[1:]))
    with pytest.raises(SaveIntegrityError, match='canonical'):
        _save(repo, session, expected_revision=1)
    assert load_manager_career(repo, 'career-1').metadata.revision == 1


def test_slot_load_rejects_results_only_and_does_not_upgrade_legacy_formats(tmp_path):
    repo = _repo(tmp_path)
    session = DevelopmentSession()
    save_world_results(repo, slot_id='legacy', display_name='Resultados',
                       career=session._career, expected_revision=0)
    with pytest.raises(SaveIntegrityError, match='complete manager'):
        load_manager_career(repo, 'legacy')
    assert load_world_results(repo, 'legacy')[1].to_dict() == session._career.to_dict()
    assert not any(entry.kind == 'manager_career' for entry in repo.list_slots())


def test_load_detects_checksum_corruption_without_modifying_slot(tmp_path):
    repo = _repo(tmp_path)
    _save(repo)
    with sqlite3.connect(repo.path) as connection:
        connection.execute("UPDATE save_sections SET payload_json='{}' "
                           "WHERE slot_id='career-1' AND section_name='manager_state'")
    with pytest.raises(SaveIntegrityError, match='checksum'):
        load_manager_career(repo, 'career-1')


def test_load_rejects_corrupted_entity_index_even_with_valid_checksums(tmp_path):
    repo = _repo(tmp_path)
    _save(repo)
    with sqlite3.connect(repo.path) as connection:
        connection.execute("DELETE FROM save_links WHERE slot_id='career-1' AND relation='registered_with'")
        connection.execute("DELETE FROM save_entities WHERE slot_id='career-1' AND kind='player'")
    with pytest.raises(SaveIntegrityError, match='entity index'):
        load_manager_career(repo, 'career-1')


def test_rejects_future_manager_state_version_without_reinterpreting_it(tmp_path):
    repo = _repo(tmp_path)
    _save(repo)
    with sqlite3.connect(repo.path) as conn:
        conn.execute("UPDATE save_sections SET section_version=100 WHERE section_name='manager_state'")
    with pytest.raises(UnsupportedSaveVersionError):
        load_manager_career(repo, 'career-1')


def test_untrusted_graph_must_not_import_arbitrary_python_class():
    graph = capture_manager_graph(DevelopmentSession())
    first_object = next(node for node in graph['nodes'] if node.get('type') == 'object')
    first_object['class'] = 'os:system'
    with pytest.raises(SaveIntegrityError, match='not permitted'):
        restore_manager_graph(graph)


def test_graph_rejects_dangling_references_and_wrong_version():
    graph = capture_manager_graph(DevelopmentSession())
    with pytest.raises(SaveIntegrityError, match='dangling'):
        restore_manager_graph({**graph, 'root': {'$ref': 999999}})
    with pytest.raises(UnsupportedSaveVersionError):
        restore_manager_graph({**graph, 'version': 100})


def test_backup_can_recover_original_career_after_database_corruption(tmp_path):
    repo = _repo(tmp_path)
    _save(repo)
    destination = tmp_path / 'backup.sqlite3'
    assert repo.backup_to(destination) == destination
    with sqlite3.connect(repo.path) as db:
        db.execute("UPDATE save_sections SET payload_json='{}' WHERE slot_id='career-1'")
    with pytest.raises(SaveIntegrityError):
        load_manager_career(repo, 'career-1')
    recovered = load_manager_career(SQLiteSaveRepository(destination), 'career-1')
    assert recovered.session.current_date == date(2026, 8, 21)


def test_backup_must_not_overwrite_original_db(tmp_path):
    repo = _repo(tmp_path)
    _save(repo)
    with pytest.raises(ValueError, match='must differ'):
        repo.backup_to(repo.path)
    assert load_manager_career(repo, 'career-1').metadata.revision == 1


def test_repeated_backup_replaces_old_backup_only_after_full_copy(tmp_path):
    repo = _repo(tmp_path)
    session = DevelopmentSession()
    _save(repo, session)
    backup = tmp_path / 'backups' / 'copy.sqlite3'
    repo.backup_to(backup)
    _save(repo, session, expected_revision=1)
    assert load_manager_career(SQLiteSaveRepository(backup), 'career-1').metadata.revision == 1
    repo.backup_to(backup)
    assert load_manager_career(SQLiteSaveRepository(backup), 'career-1').metadata.revision == 2


def test_invalid_ui_metadata_does_not_commit_partial_save(tmp_path):
    repo = _repo(tmp_path)
    session = DevelopmentSession()
    _save(repo, session)
    with pytest.raises(SaveIntegrityError, match='shirt number'):
        _save(repo, session, expected_revision=1,
              admin=UIRosterAdmin(numbers={'unknown': 8}))
    assert load_manager_career(repo, 'career-1').metadata.revision == 1


def test_default_location_can_be_configured_without_changing_repository(monkeypatch, tmp_path):
    target = tmp_path / 'override.sqlite3'
    monkeypatch.setenv('FM_SAVE_DATABASE', str(target))
    assert default_save_path() == target
    assert not target.exists()


def test_http_save_list_load_and_atomic_restore(tmp_path):
    server = create_server(port=0, save_repository=_repo(tmp_path))
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f'http://127.0.0.1:{server.server_port}'

    def request(path, payload=None):
        if payload is None:
            with urlopen(base + path, timeout=30) as response:
                return json.load(response)
        req = Request(base + path, data=json.dumps(payload).encode('utf-8'),
                      method='POST', headers={'Content-Type': 'application/json'})
        with urlopen(req, timeout=30) as response:
            return json.load(response)

    try:
        runtime = server.RequestHandlerClass.runtime
        player = runtime.session.home_club.squad.players[0]
        runtime.admin.numbers[player.id] = 17
        runtime.session.dev_favorable_mode = True
        saved = request('/api/career/save', {'slot_id': 'example', 'display_name': 'Prueba', 'expected_revision': 0})
        assert saved['saved'] and saved['slot']['revision'] == 1
        listed = request('/api/career/saves')
        assert [s['slot_id'] for s in listed['slots']] == ['example']
        original = runtime.session
        runtime.session = DevelopmentSession()
        runtime.admin.numbers.clear()
        runtime.session.dev_favorable_mode = False
        restored = request('/api/career/load', {'slot_id': 'example'})
        assert restored['loaded'] and restored['date'] == '2026-08-21'
        assert runtime.session is not original
        assert runtime.session.dev_favorable_mode is True
        assert runtime.admin.numbers[player.id] == 17
        assert request('/api/progression')['date'] == '2026-08-21'
    finally:
        server.shutdown(); server.server_close(); thread.join(timeout=5)


def test_http_rejects_stale_save_and_blocks_simultaneous_jobs(tmp_path):
    server = create_server(port=0, save_repository=_repo(tmp_path))
    worker = Thread(target=server.serve_forever, daemon=True); worker.start()
    base = f'http://127.0.0.1:{server.server_port}'

    def post(path, body):
        data = json.dumps(body).encode('utf-8')
        req = Request(base+path, data=data, method='POST',
                      headers={'Content-Type':'application/json'})
        with urlopen(req, timeout=30) as response:
            return json.load(response)
    try:
        runtime = server.RequestHandlerClass.runtime
        data = {'slot_id': 'slot', 'display_name': 'Slot', 'expected_revision': 0}
        post('/api/career/save', data)
        with pytest.raises(HTTPError) as response:
            post('/api/career/save', data)
        assert response.value.code == 409
        class BusyJob:
            status = 'running'
        runtime.active_job = BusyJob()
        with pytest.raises(HTTPError) as response:
            post('/api/career/load', {'slot_id':'slot'})
        assert response.value.code == 409
        with pytest.raises(HTTPError) as response:
            post('/api/career/save', {'slot_id':'slot', 'display_name':'Slot', 'expected_revision':1})
        assert response.value.code == 409
        runtime.active_job = None
        assert post('/api/career/load', {'slot_id':'slot'})['loaded']
    finally:
        server.shutdown(); server.server_close(); worker.join(timeout=5)


def test_http_load_failure_preserves_live_session_and_ui_metadata(tmp_path):
    repo = _repo(tmp_path)
    server = create_server(port=0, save_repository=repo)
    worker = Thread(target=server.serve_forever, daemon=True); worker.start()
    base = f'http://127.0.0.1:{server.server_port}'
    try:
        runtime = server.RequestHandlerClass.runtime
        save_manager_career(repo, slot_id='slot', display_name='One',
                            session=runtime.session, expected_revision=0)
        original = runtime.session
        with sqlite3.connect(repo.path) as conn:
            conn.execute("UPDATE save_sections SET payload_json='{}' WHERE slot_id='slot'")
        data = json.dumps({'slot_id':'slot'}).encode('utf-8')
        req = Request(base+'/api/career/load', data=data, method='POST',
                      headers={'Content-Type':'application/json'})
        with pytest.raises(HTTPError) as response:
            urlopen(req, timeout=30)
        assert response.value.code == 400
        assert runtime.session is original
    finally:
        server.shutdown(); server.server_close(); worker.join(timeout=5)


def test_completed_managed_match_preserves_detailed_result_and_resumes(tmp_path):
    session = DevelopmentSession()
    finished = session.quick_simulate()
    assert session.match_played and session.last_result is not None
    repo = _repo(tmp_path)
    _save(repo, session)
    recovered = load_manager_career(repo, 'career-1').session
    assert recovered.match_played
    assert recovered.last_result == finished
    assert recovered._world.to_dict() == session._world.to_dict()
    session.continue_to_next_match()
    recovered.continue_to_next_match()
    assert recovered.current_date == session.current_date
    assert recovered._world.to_dict() == session._world.to_dict()


def test_full_season_transition_can_be_saved_and_recovered(tmp_path):
    session = DevelopmentSession()
    assert session.simulate_remaining_season() >= 38
    session.begin_next_season()
    assert len(session.archived_season_reports) == 1
    repo = _repo(tmp_path)
    _save(repo, session)
    recovered = load_manager_career(repo, 'career-1').session
    assert recovered._world.season_label == '2027/28'
    assert recovered._career.current is recovered._world
    assert len(recovered.archived_season_reports) == 1
    assert recovered._career.to_dict() == session._career.to_dict()
    assert recovered.can_quick_sim
    result = recovered.quick_simulate()
    assert result.home_goals >= 0


def test_duplicate_jersey_numbers_are_rejected_without_overwriting(tmp_path):
    session = DevelopmentSession()
    repo = _repo(tmp_path)
    _save(repo, session)
    first, second = session.home_club.squad.players[:2]
    admin = UIRosterAdmin(numbers={first.id: 10, second.id: 10})
    with pytest.raises(SaveIntegrityError, match='duplicate saved shirt'):
        _save(repo, session, admin=admin, expected_revision=1)
    assert repo.load('career-1').metadata.revision == 1
