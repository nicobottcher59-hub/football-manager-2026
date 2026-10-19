"""TS-11: permanent squad edits and temporary match commands are atomic."""
from __future__ import annotations

from copy import deepcopy
from threading import Thread
from urllib.error import HTTPError
from urllib.request import Request, urlopen
import json

import pytest

from football_manager.dev_ui.session import DevelopmentSession
from football_manager.ui_shell import models, server as api
from football_manager.ui_shell.models import squad_read_model
from football_manager.ui_shell.server import FootballUIHandler, UIRuntime, create_server


def _post(base: str, path: str, body: dict):
    payload = json.dumps(body).encode('utf-8')
    req = Request(base + path, data=payload, method='POST',
                  headers={'Content-Type': 'application/json'})
    try:
        with urlopen(req, timeout=20) as response:
            return response.status, json.load(response)
    except HTTPError as exc:
        return exc.code, json.loads(exc.read())


def _server(session: DevelopmentSession):
    instance = create_server(port=0, session=session)
    thread = Thread(target=instance.serve_forever, daemon=True)
    thread.start()
    return instance, thread, f'http://127.0.0.1:{instance.server_port}'


def _close(instance, thread):
    instance.shutdown()
    instance.server_close()
    thread.join(timeout=5)


def _familiarities(session):
    return {p.id: deepcopy(p.tactical_familiarity) for p in session.home_club.squad.players}


def _direct_handler():
    handler = object.__new__(FootballUIHandler)
    handler.runtime = UIRuntime()
    fixture_id = handler.runtime.session._active_match.fixture.fixture_id
    return handler, fixture_id


def test_squad_failed_read_model_rolls_back_tactic_and_preserves_references(monkeypatch):
    session = DevelopmentSession()
    initial_tactic = session.home_tactic
    initial_lineup = session.home_lineup
    before = deepcopy(session.home_tactic)
    familiarities = _familiarities(session)
    world = session._world
    instance, thread, base = _server(session)
    original = models.squad_read_model

    def fail_after_update(current, admin=None):
        if current.home_tactic.preset_origin.value == 'tiki_taka':
            raise ValueError('injected view failure')
        return original(current, admin)

    monkeypatch.setattr(models, 'squad_read_model', fail_after_update)
    try:
        status, body = _post(base, '/api/squad', {'action': 'preset', 'id': 'tiki_taka'})
        assert status == 400 and 'injected' in body['error']
        assert instance.RequestHandlerClass.runtime.session is session
        assert session.home_tactic is initial_tactic
        assert session.home_lineup is initial_lineup
        assert session.home_tactic == before
        assert session._world is world
        assert _familiarities(session) == familiarities
    finally:
        _close(instance, thread)


def test_squad_failed_formation_sync_rolls_back_player_familiarity(monkeypatch):
    session = DevelopmentSession()
    original_lineup, original_tactic = session.home_lineup, session.home_tactic
    before = _familiarities(session)
    sync = DevelopmentSession._sync_effective_tactic_familiarity

    def fail_after_sync(self, *, home):
        sync(self, home=home)
        if home and self.home_lineup.formation != original_lineup.formation:
            raise RuntimeError('injected tactical sync failure')

    monkeypatch.setattr(DevelopmentSession, '_sync_effective_tactic_familiarity', fail_after_sync)
    target = next(k for k, _ in session.available_formations if k != original_lineup.formation.formation_id)
    instance, thread, base = _server(session)
    try:
        status, body = _post(base, '/api/squad', {'action': 'formation', 'id': target})
        assert status == 409 and 'injected' in body['error']
        assert session.home_lineup is original_lineup
        assert session.home_tactic is original_tactic
        assert _familiarities(session) == before
    finally:
        _close(instance, thread)


def test_ui_admin_update_failed_read_model_leaves_no_partial_number(monkeypatch):
    session = DevelopmentSession()
    player_id = session.home_club.squad.players[0].id
    instance, thread, base = _server(session)
    runtime = instance.RequestHandlerClass.runtime

    def fail_read_model(*args, **kwargs):
        raise ValueError('injected administrative view failure')

    monkeypatch.setattr(models, 'squad_read_model', fail_read_model)
    try:
        status, body = _post(base, '/api/squad', {'action': 'squad_number',
                                                 'player_id': player_id, 'number': 17})
        assert status == 400 and 'injected' in body['error']
        assert runtime.admin.numbers == {}
    finally:
        _close(instance, thread)


def test_match_tactic_failed_prematch_does_not_append_command(monkeypatch):
    handler, fixture_id = _direct_handler()
    cmd = {'action': 'formation', 'id': 'dev-4-2-3-1'}
    before = deepcopy(handler.runtime.match_commands)

    def fail_prematch(*args, **kwargs):
        raise RuntimeError('injected prematch render failure')

    monkeypatch.setattr(api, 'prematch_read_model', fail_prematch)
    with pytest.raises(RuntimeError, match='injected'):
        handler._match_command({'action': 'match_tactic', 'fixture_id': fixture_id,
                                'command': cmd})
    assert handler.runtime.match_commands == before
    assert handler.runtime.session.home_lineup.formation.formation_id != cmd['id']


def test_reset_match_tactics_failure_preserves_previous_commands(monkeypatch):
    handler, fixture_id = _direct_handler()
    cmd = {'action': 'formation', 'id': 'dev-4-2-3-1'}
    handler._match_command({'action': 'match_tactic', 'fixture_id': fixture_id, 'command': cmd})

    def fail_prematch(*args, **kwargs):
        raise ValueError('injected reset view failure')

    monkeypatch.setattr(api, 'prematch_read_model', fail_prematch)
    with pytest.raises(ValueError, match='injected'):
        handler._match_command({'action': 'reset_match_tactics', 'fixture_id': fixture_id})
    assert handler.runtime.match_commands == [cmd]


def test_match_kits_failed_preview_does_not_commit_kit_change(monkeypatch):
    handler, fixture_id = _direct_handler()
    original = dict(handler.runtime.match_kits)

    def fail_prematch(*args, **kwargs):
        raise RuntimeError('injected kit preview failure')

    monkeypatch.setattr(api, 'prematch_read_model', fail_prematch)
    with pytest.raises(RuntimeError, match='injected'):
        handler._match_command({'action': 'match_kits', 'fixture_id': fixture_id,
                                'home': 'red', 'away': 'blue'})
    assert handler.runtime.match_kits == original


def test_successful_edit_keeps_session_world_identity_and_roster_state():
    session = DevelopmentSession()
    instance, thread, base = _server(session)
    runtime = instance.RequestHandlerClass.runtime
    original_world = session._world
    original_squad = session.home_club.squad
    try:
        status, body = _post(base, '/api/squad', {'action': 'preset', 'id': 'tiki_taka'})
        assert status == 200
        assert body['tactics']['preset'] == 'tiki_taka'
        assert runtime.session is session
        assert session._world is original_world
        assert session.home_club.squad is original_squad
        assert squad_read_model(session)['tactics']['preset'] == 'tiki_taka'
    finally:
        _close(instance, thread)


def test_async_completion_does_not_publish_session_before_completed_status(monkeypatch):
    from datetime import date
    from threading import Event, Thread
    from football_manager.ui_shell import simulation_jobs

    runtime = UIRuntime()
    original = runtime.session
    pending = deepcopy(original)
    job = simulation_jobs.SimulationJob(pending, date(2026, 8, 22))
    runtime.active_job = job
    reached = Event()

    def fake_progress(working, target, *, on_day):
        working.current_date = target
        reached.set()
        return {'mode': 'calendar_auto_sim', 'to_date': target.isoformat()}

    monkeypatch.setattr(simulation_jobs, 'simulate_until', fake_progress)
    with job.lock:
        thread = Thread(target=job._run, args=(runtime,), daemon=True)
        thread.start()
        assert reached.wait(5)
        # The commit cannot pass its status transition while job.lock is held.
        # Earlier versions exposed the new session while still reporting running.
        from time import sleep
        sleep(0.05)
        assert runtime.session is original
        assert job.status == 'running'
    thread.join(timeout=5)
    assert not thread.is_alive()
    assert runtime.session is pending
    assert job.status == 'completed'
    assert job.snapshot()['committed']
    assert job.snapshot()['result']['to_date'] == '2026-08-22'
    assert job.session is None  # Completed jobs must not retain old world copies.
    assert runtime.active_job is None


def test_async_failure_releases_unused_private_session(monkeypatch):
    from datetime import date
    from football_manager.ui_shell import simulation_jobs

    runtime = UIRuntime()
    original = runtime.session
    working = deepcopy(original)
    job = simulation_jobs.SimulationJob(working, date(2026, 8, 22))
    runtime.active_job = job

    def fail_progress(session, target, *, on_day):
        session.current_date = target
        on_day(target, [{'type': 'result', 'id': 'not-committed'}])
        raise RuntimeError('injected background simulation failure')

    monkeypatch.setattr(simulation_jobs, 'simulate_until', fail_progress)
    job._run(runtime)
    assert runtime.session is original
    assert job.status == 'failed'
    assert job.snapshot()['events'][0]['id'] == 'not-committed'
    assert job.snapshot()['committed'] is False
    assert job.snapshot()['result'] is None
    assert job.session is None
    assert runtime.active_job is None
