"""UI-3.4.1: actual result-by-result progress and transactional async calendar skip."""
from __future__ import annotations

from datetime import date
from threading import Thread, Event
from time import monotonic, sleep
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from unittest.mock import patch
import json

import pytest

from football_manager.dev_ui.session import DevelopmentSession
from football_manager.ui_shell.progression import simulate_until
from football_manager.ui_shell.server import create_server


def _request(base, path, payload=None):
    data = None if payload is None else json.dumps(payload).encode()
    req = Request(base + path, data=data, method='POST' if data else 'GET',
                  headers={'Content-Type': 'application/json'} if data else {})
    with urlopen(req, timeout=40) as response:
        return json.load(response)


def _collect(base, job_id, timeout=30):
    after = 0
    collected = []
    deadline = monotonic() + timeout
    while monotonic() < deadline:
        status = _request(base, f'/api/progression/jobs/{job_id}?after={after}&limit=15')
        assert status['committed'] == (status['status'] == 'completed')
        assert status['days_completed'] <= status['total_days']
        rows = status['events']
        assert all(row['seq'] == after + i + 1 for i, row in enumerate(rows))
        collected.extend(rows)
        after = status['next_cursor']
        if status['status'] != 'running' and not status['has_more']:
            assert after == status['results_available']
            return status, collected
        sleep(.015)
    raise AssertionError('simulation job timed out')


def test_progress_callback_emits_only_new_real_world_results_in_date_order():
    game = DevelopmentSession()
    initial = set(game._world.results)
    start = game.current_date
    days = []
    progress = simulate_until(game, date(2026, 9, 30),
                              on_day=lambda day, rows: days.append((day, rows)))
    results = [row for _, rows in days for row in rows]
    assert progress['to_date'] == '2026-09-30'
    assert len(days) == (date(2026, 9, 30) - start).days + 1
    assert len(results) == len(set(game._world.results) - initial)
    assert {r['id'] for r in results} == set(game._world.results) - initial
    assert len({r['id'] for r in results}) == len(results)
    assert [d for d, _ in days] == sorted(d for d, _ in days)
    assert any(r['managed'] and r['resolver'] == 'managed' for r in results)
    for result in results:
        score = game._world.results[result['id']]
        fixture = game._world.fixtures[result['id']]
        assert (result['home_goals'], result['away_goals']) == (score.home_goals, score.away_goals)
        assert result['competition_id'] == fixture.competition_id


def test_async_progress_pagination_world_commit_and_previous_state_untouched():
    server = create_server(port=0)
    worker = Thread(target=server.serve_forever, daemon=True)
    worker.start()
    base = f'http://127.0.0.1:{server.server_port}'
    original = server.RequestHandlerClass.runtime.session
    initial_ids = set(original._world.results)
    try:
        started = _request(base, '/api/progression/jobs',
                           {'action': 'simulate_until', 'date': '2026-09-30'})
        assert started['status'] == 'running'
        final, events = _collect(base, started['job_id'])
        assert final['status'] == 'completed'
        assert final['percent'] == 100.0
        assert final['result']['state']['date'] == '2026-09-30'
        assert final['result']['managed_matches'] == sum(x['managed'] for x in events)
        assert len(events) == len(set(server.RequestHandlerClass.runtime.session._world.results) - initial_ids)
        assert server.RequestHandlerClass.runtime.session is not original
        assert original.current_date == date(2026, 8, 21)
        assert _request(base, '/api/calendar')['date'] == '2026-09-30'
        assert all(x['type'] == 'result' for x in events)
        assert any(x['managed'] for x in events)
        assert _request(base, '/api/progression')['date'] == '2026-09-30'
    finally:
        server.shutdown(); server.server_close(); worker.join(timeout=5)


def test_async_failure_does_not_commit_and_blocks_other_mutations_while_running():
    server = create_server(port=0)
    worker = Thread(target=server.serve_forever, daemon=True); worker.start()
    base = f'http://127.0.0.1:{server.server_port}'
    runtime = server.RequestHandlerClass.runtime
    previous = runtime.session
    blocked = Event()
    release = Event()

    def fail(session, target, *, on_day=None):
        session.current_date = date(2026, 8, 25)
        session._world.results.clear()
        on_day(date(2026, 8, 25), [{
            'type':'result','id':'tentative','date':'2026-08-25','home_club':'Test FC',
            'away_club':'Test Away', 'home_goals':1, 'away_goals':0,
        }])
        blocked.set()
        assert release.wait(10)
        raise RuntimeError('forced calendar scheduling failure')

    try:
        with patch('football_manager.ui_shell.simulation_jobs.simulate_until', side_effect=fail):
            job = _request(base, '/api/progression/jobs',
                           {'action': 'simulate_until', 'date': '2026-08-25'})
            assert blocked.wait(5)
            assert _request(base, '/api/progression')['date'] == '2026-08-21'
            assert _request(base, '/api/progression/jobs/' + job['job_id'])['events'][0]['id'] == 'tentative'
            for path, body in [('/api/progression', {'action':'advance_day'}),
                               ('/api/squad', {'action':'noop'}),
                               ('/api/progression/jobs', {'action':'simulate_until','date':'2026-09-01'})]:
                with pytest.raises(HTTPError) as exc:
                    _request(base, path, body)
                assert exc.value.code == 409
            release.set()
            final, entries = _collect(base, job['job_id'])
            assert final['status'] == 'failed'
            assert 'forced calendar scheduling failure' in final['error']
            assert not final['committed'] and final['result'] is None
            assert len(entries) == 1
        assert runtime.session is previous
        assert runtime.session.current_date == date(2026, 8, 21)
        assert runtime.session._world.results
        with pytest.raises(HTTPError) as exc:
            _request(base, '/api/progression/jobs/' + job['job_id'] + '?after=-1')
        assert exc.value.code == 400
    finally:
        release.set(); server.shutdown(); server.server_close(); worker.join(timeout=5)


def test_invalid_date_and_nonexistent_jobs_do_not_mutate_session():
    server = create_server(port=0)
    worker = Thread(target=server.serve_forever, daemon=True); worker.start()
    base = f'http://127.0.0.1:{server.server_port}'
    original = server.RequestHandlerClass.runtime.session
    try:
        for value in ('2026-08-14','2027-07-01','not-a-date'):
            with pytest.raises(HTTPError) as exc:
                _request(base, '/api/progression/jobs', {'action':'simulate_until','date':value})
            assert exc.value.code == 400
        with pytest.raises(HTTPError) as exc:
            _request(base, '/api/progression/jobs/not-found')
        assert exc.value.code == 404
        assert server.RequestHandlerClass.runtime.session is original
    finally:
        server.shutdown();server.server_close();worker.join(timeout=5)


def test_ui_selects_entire_calendar_cell_marks_past_and_renders_real_progress():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1] / 'frontend' / 'portable'
    calendar = (root / 'calendar.js').read_text(encoding='utf-8')
    style = (root / 'calendar.css').read_text(encoding='utf-8')
    progress = (root / 'simulation.js').read_text(encoding='utf-8')
    index = (root / 'index.html').read_text(encoding='utf-8')
    assert 'data-cal-cell' in calendar and 'cellClick' in calendar and 'cellKeydown' in calendar
    assert 'cal-past' in calendar and '.cal-day.cal-past' in style
    assert "fetch('/api/progression/jobs'" in progress
    assert 'payload.events' in progress and 'appendResult' in progress
    assert 'result.home_goals' not in progress  # field is populated from actual item, not a constant
    assert 'simulation.css' in index and 'simulation.js' in index
