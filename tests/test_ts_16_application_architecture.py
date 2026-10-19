"""TS-16: application layer, transport compatibility, and distributable assets."""
from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
from threading import Thread
from urllib.error import HTTPError
from urllib.request import Request, urlopen
import json

import pytest

from football_manager.dev_ui.session import DevelopmentSession
from football_manager.persistence import SQLiteSaveRepository
from football_manager.ui_shell.application import GameApplication
from football_manager.ui_shell.match import prematch_read_model
from football_manager.ui_shell.progression import simulate_until
from football_manager.ui_shell.runtime import UIRuntime
from football_manager.ui_shell.server import create_server, UIRuntime as PublicRuntime
from football_manager.ui_shell.static_assets import find_frontend_root, resolve_static_asset


FRONTEND = Path(__file__).resolve().parents[1] / 'frontend'


def application(tmp_path):
    runtime = UIRuntime(
        session=DevelopmentSession(),
        save_repository=SQLiteSaveRepository(tmp_path / 'career.db'),
    )
    return runtime, GameApplication(runtime, prematch_builder=prematch_read_model)


def test_runtime_is_shared_by_http_and_application_without_import_cycle(tmp_path):
    runtime, app = application(tmp_path)
    assert PublicRuntime is UIRuntime
    assert app.runtime is runtime
    assert runtime.frontend_root == FRONTEND.resolve()


def test_direct_application_commands_preserve_http_result_contract(tmp_path):
    runtime, app = application(tmp_path)
    before = runtime.session.current_date
    simulate_until(runtime.session, before)  # First day is a managed match.
    with runtime.lock:
        view = app.command('squad.command', {'action': 'preset', 'id': 'tiki_taka'})
        assert view['tactics']['preset'] == 'tiki_taka'
        assert runtime.session.home_tactic.preset_origin.value == 'tiki_taka'
        step = app.command('progression.command', {'action': 'advance_day'})
    assert step['from_date'] == before.isoformat()
    assert step['to_date'] == (before + timedelta(days=1)).isoformat()
    assert runtime.session.current_date == before + timedelta(days=1)


def test_direct_application_career_save_load_preserves_atomic_publishing(tmp_path):
    runtime, app = application(tmp_path)
    saved_session = runtime.session
    saved_date = saved_session.current_date.isoformat()
    with runtime.lock:
        saved = app.command('career.save', {
            'slot_id': 'ts16-test', 'display_name': 'Testing', 'expected_revision': 0,
        })
    assert saved['saved'] is True
    assert saved['slot']['revision'] == 1
    assert [s['slot_id'] for s in app.list_saves()['slots']] == ['ts16-test']
    runtime.session.current_date = date(2026, 9, 1)
    runtime.match_commands = [{'action': 'ignored'}]
    runtime.match_kits = {'home': 'blue', 'away': 'red'}
    with runtime.lock:
        loaded = app.command('career.load', {'slot_id': 'ts16-test'})
    assert loaded['loaded'] is True
    assert loaded['date'] == saved_date
    assert runtime.session is not saved_session
    assert runtime.match_commands == []
    assert runtime.match_kits == {'home': 'default', 'away': 'default'}


def test_unknown_command_and_bad_date_leave_runtime_unchanged(tmp_path):
    runtime, app = application(tmp_path)
    original = runtime.session
    with pytest.raises(ValueError, match='unsupported'):
        app.command('unknown.command', {'action': 'advance_day'})
    with pytest.raises(ValueError, match='YYYY-MM-DD'):
        app.command('progression.command', {'action': 'simulate_until', 'date': 'not-a-date'})
    assert runtime.session is original


def test_frontend_root_selection_and_invalid_override(tmp_path, monkeypatch):
    fake = tmp_path / 'static files'
    (fake / 'portable').mkdir(parents=True)
    (fake / 'public' / 'squad').mkdir(parents=True)
    (fake / 'portable' / 'index.html').write_text('<h1>local override</h1>', encoding='utf-8')
    (fake / 'public' / 'squad' / 'embed.html').write_text('local board', encoding='utf-8')
    monkeypatch.setenv('FM_FRONTEND_DIR', str(fake))
    assert find_frontend_root() == fake.resolve()
    assert find_frontend_root(FRONTEND) == FRONTEND.resolve()  # explicit argument wins
    monkeypatch.setenv('FM_FRONTEND_DIR', str(tmp_path / 'missing'))
    with pytest.raises(FileNotFoundError, match='Frontend files'):
        find_frontend_root()


def test_static_asset_containment_blocks_escape_and_symlinks(tmp_path):
    root = find_frontend_root(FRONTEND)
    assert resolve_static_asset('/portable/', root) == root / 'portable' / 'index.html'
    assert resolve_static_asset('/squad/embed.html', root) == root / 'public' / 'squad' / 'embed.html'
    assert resolve_static_asset('/public/squad/embed.html', root) == root / 'public' / 'squad' / 'embed.html'
    assert resolve_static_asset('/portable/../../README.md', root) is None
    assert resolve_static_asset('/portable/../public/squad/embed.html', root) is None
    assert resolve_static_asset('/portable/%00', root) is None
    assert resolve_static_asset('/anything/else', root) is None
    secret = tmp_path / 'secret.txt'
    secret.write_text('secret', encoding='utf8')
    dest = tmp_path / 'static'
    (dest / 'portable').mkdir(parents=True)
    link = dest / 'portable' / 'shortcut.txt'
    try:
        link.symlink_to(secret)
    except (OSError, NotImplementedError):
        pass  # Windows without developer mode may not allow symlinks.
    else:
        assert resolve_static_asset('/portable/shortcut.txt', dest) is None


def test_http_adapter_keeps_routes_and_reads_static_override(tmp_path):
    fake = tmp_path / 'assets'
    (fake / 'portable').mkdir(parents=True)
    (fake / 'public' / 'squad').mkdir(parents=True)
    (fake / 'portable' / 'index.html').write_text('<h1>TS16 override</h1>', encoding='utf8')
    (fake / 'public' / 'squad' / 'embed.html').write_text('TS16 squad', encoding='utf8')
    server = create_server(port=0, frontend_root=fake)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f'http://127.0.0.1:{server.server_port}'
    try:
        with urlopen(base + '/', timeout=20) as result:
            assert result.url.endswith('/portable/')
            assert result.read() == b'<h1>TS16 override</h1>'
        with urlopen(base + '/squad/embed.html', timeout=20) as result:
            assert result.read() == b'TS16 squad'
        with urlopen(base + '/api/calendar', timeout=20) as result:
            assert json.load(result)['date'] == '2026-08-21'
        invalid = Request(base + '/portable/../../README.md')
        with pytest.raises(HTTPError) as err:
            urlopen(invalid, timeout=20)
        assert err.value.code == 404
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_two_server_instances_keep_isolated_runtime_and_game_state():
    first = create_server(port=0)
    second = create_server(port=0)
    try:
        a = first.RequestHandlerClass.runtime
        b = second.RequestHandlerClass.runtime
        assert a is not b
        assert a.session is not b.session
        a.match_kits['home'] = 'red'
        assert b.match_kits['home'] == 'default'
        assert a.frontend_root == b.frontend_root
    finally:
        first.server_close()
        second.server_close()
