"""UI-3.5 regression: match tab, engine-backed events and one-fixture tactics."""
from __future__ import annotations

from copy import deepcopy
from datetime import timedelta
from http.server import ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from urllib.error import HTTPError
from urllib.request import Request, urlopen
import json

from football_manager.dev_ui.session import DevelopmentSession
from football_manager.ui_shell.match import (
    ENGLISH_REFEREES, UEFA_REFEREES, _referee_for, prematch_read_model,
)
from football_manager.ui_shell.models import UIRosterAdmin
from football_manager.ui_shell.server import create_server


def test_prematch_uses_correct_fixture_starters_subs_and_referee_pool():
    session = DevelopmentSession()
    view = prematch_read_model(session, UIRosterAdmin())
    assert view['status'] == 'prematch'
    assert view['match']['fixture_id'] == session._active_match.fixture.fixture_id
    assert view['match']['date'] == session.current_date.isoformat()
    assert view['home']['name'] == 'Northbridge FC'
    assert len(view['home']['starters']) == len(view['away']['starters']) == 11
    assert len(view['home']['bench']) == 7
    assert {p['id'] for p in view['home']['starters']} == {p.id for p in session.home_lineup.starting_players}
    assert len({p['number'] for p in view['home']['starters'] + view['home']['bench']}) == 18
    assert view['match']['referee'] in ENGLISH_REFEREES['premier']
    assert _referee_for('fixture01','champions-league') in UEFA_REFEREES
    assert _referee_for('fixture01','fa-cup') in {name for group in ENGLISH_REFEREES.values() for name in group}
    assert _referee_for('fixture01','fa-cup') == _referee_for('fixture01','fa-cup')
    assert view['tactical']['slots'] and view['tactical']['tactics']['fields']


def test_no_future_match_prematch_and_no_fake_stats():
    session = DevelopmentSession()
    session.current_date = session.current_date.replace(day=14)
    assert prematch_read_model(session,UIRosterAdmin())['status'] == 'no_match'
    source = Path('src/football_manager/ui_shell/match.py').read_text(encoding='utf-8')
    assert "'tackles':None" in source
    assert "'injury_tracking_supported':True" in source
    assert "'in_match_injuries_supported':False" in source


def test_live_http_match_commands_are_temp_and_result_is_real():
    session = DevelopmentSession()
    original_formation = session.home_lineup.formation.formation_id
    original_tactic = session.home_tactic.team_instructions
    original_starters = [p.id for p in session.home_lineup.starting_players]
    before = set(session._world.results)
    server = create_server(port=0, session=session)
    thread = Thread(target=server.serve_forever,daemon=True)
    thread.start()
    host = f'127.0.0.1:{server.server_port}'

    def request(path, data=None):
        payload = json.dumps(data).encode() if data else None
        req = Request(f'http://{host}{path}', data=payload,
                      headers={'Host':host, **({'Content-Type':'application/json'} if payload else {})})
        with urlopen(req,timeout=30) as response:
            return json.load(response)
    try:
        prematch = request('/api/match')
        fixture = prematch['match']['fixture_id']
        # Changing lineup and formation is visible in the dedicated match preview.
        view = request('/api/match',{'action':'match_tactic','fixture_id':fixture,
                  'command':{'action':'formation','id':'dev-4-2-3-1'}})
        assert view['managed']['formation_id'] == 'dev-4-2-3-1'
        assert server.RequestHandlerClass.runtime.session.home_lineup.formation.formation_id == original_formation
        view = request('/api/match',{'action':'match_tactic','fixture_id':fixture,
                     'command':{'action':'swap_bench','starter_id':view['tactical']['starters'][0]['id'],
                                'bench_id':view['tactical']['bench'][0]['id']}})
        changed_ids = [p['id'] for p in view['managed']['starters']]
        assert changed_ids != original_starters
        assert [p.id for p in session.home_lineup.starting_players] == original_starters
        # Reset must discard the match-only plan entirely.
        view = request('/api/match',{'action':'reset_match_tactics','fixture_id':fixture})
        assert view['managed']['formation_id'] == original_formation
        # Reapply a change and actually play it; the permanent plan must survive.
        request('/api/match',{'action':'match_tactic','fixture_id':fixture,
                   'command':{'action':'formation','id':'dev-4-2-3-1'}})
        result = request('/api/match',{'action':'quick_sim','fixture_id':fixture})
        assert result['status'] == 'finished'
        assert server.RequestHandlerClass.runtime.session.home_lineup.formation.formation_id == original_formation
        assert [p.id for p in server.RequestHandlerClass.runtime.session.home_lineup.starting_players] == original_starters
        assert server.RequestHandlerClass.runtime.session.home_tactic.team_instructions == original_tactic
        world = server.RequestHandlerClass.runtime.session._world
        assert set(world.results) - before == {fixture} or fixture in (set(world.results) - before)
        assert (world.results[fixture].home_goals,world.results[fixture].away_goals) == (result['home']['goals'],result['away']['goals'])
        raw = server.RequestHandlerClass.runtime.session.last_result
        assert len([e for e in result['events'] if e['kind']=='goal']) == len(raw.goals)
        assert len([e for e in result['events'] if e['kind']=='card']) == len(raw.cards)
        assert len([e for e in result['events'] if e['kind']=='substitution']) == len(raw.substitutions)
        assert result['home']['statistics']['shots'] == raw.statistics_home.shots
        assert result['home']['statistics']['tackles'] is None
        assert result['injury_tracking_supported'] is True
        assert result['in_match_injuries_supported'] is False
        assert 'Post-match' in result['injury_tracking_scope']
        assert request('/api/match')['status']=='finished'
        # TS-22: a retry returns the committed summary without a second game.
        stats_before = dict(world.results)
        assert request('/api/match',{'action':'quick_sim','fixture_id':fixture}) == result
        assert world.results == stats_before
        # Calendar dates are data-driven. Continuing must advance exactly one
        # day after the actual match, not a hard-coded pre-TC-E2.1 date.
        match_day = server.RequestHandlerClass.runtime.session.current_date
        step = request('/api/progression', {'action': 'advance_day'})
        assert step['from_date'] == match_day.isoformat()
        assert step['to_date'] == (match_day + timedelta(days=1)).isoformat()
        assert server.RequestHandlerClass.runtime.session.current_date == match_day + timedelta(days=1)
        assert request('/api/match')['status']=='no_match'
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)


def test_static_match_tab_does_not_include_sidebar_and_uses_python_api():
    html=Path('frontend/portable/match.html').read_text(encoding='utf-8')
    js=Path('frontend/portable/match.js').read_text(encoding='utf-8')
    shell=Path('frontend/portable/portable.js').read_text(encoding='utf-8')
    assert 'match.js' in html and 'portable.js' not in html
    assert '/api/match' in js and 'window.open(' not in shell and 'loadFrame(matchFrame,src)' in shell
    assert 'fm-result-continue' in js and 'fm-quick' in js
    assert 'data-filter' in js and 'match_tactic' in js
