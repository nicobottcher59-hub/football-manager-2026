"""UI-3.1: Home and Squad/Tactics must share one truthful DEV session.

These tests require only Python's stdlib and the existing game test dependencies,
not Node.js, npm or a graphical browser.
"""
from __future__ import annotations

import json
from pathlib import Path
from threading import Thread
from urllib.request import Request, urlopen

from football_manager.dev_ui.session import DevelopmentSession
from football_manager.ui_shell.server import create_server

ROOT = Path(__file__).resolve().parents[1]


def test_live_home_assets_exist_and_reference_shared_python_state():
    index = (ROOT / 'frontend/portable/index.html').read_text(encoding='utf-8')
    shell = (ROOT / 'frontend/portable/portable.js').read_text(encoding='utf-8')
    roster = (ROOT / 'frontend/public/squad/roster.js').read_text(encoding='utf-8')
    tactics = (ROOT / 'frontend/public/squad/squad.js').read_text(encoding='utf-8')
    for asset in ('polish.css', '../public/squad/portraits.js', '../public/squad/board.js'):
        assert asset in index
    for asset in ('roster.css', 'polish.css', 'portraits.js'):
        assert asset in (ROOT / 'frontend/public/squad/embed.html').read_text(encoding='utf-8')
    assert 'updateHomeFromPython' in shell
    assert "fetch('/api/squad',{cache:'no-store'})" in shell
    assert 'data.squad_status[statuses[i]]' in shell
    assert 'window.FMTacticalBoard?.place' in shell
    assert 'window.FMPortraits' in roster and 'window.FMPortraits' in tactics
    assert 'fm-squad-state' in shell and 'fm-squad-state' in tactics
    assert "submitProgression('advance_day')" in shell
    assert 'window.FMProgression' in shell


def test_player_change_must_be_visible_through_same_http_read_model():
    session = DevelopmentSession()
    server = create_server(port=0, session=session)
    runner = Thread(target=server.serve_forever, daemon=True)
    runner.start()
    base = f'http://127.0.0.1:{server.server_port}'
    try:
        with urlopen(base+'/api/squad', timeout=5) as response:
            first = json.load(response)
        assert len(first['starters']) == 11
        assert first['club'] == session.home_club.name
        assert first['formation']['id'] == session.home_lineup.formation.formation_id
        assert first['squad_status']['morale'] == round(session.tactical_team_state().xi_morale, 1)
        assert first['squad_status']['condition'] == round(session.tactical_team_state().xi_condition, 1)
        assert first['squad_status']['chemistry'] == round(session.tactical_team_state().xi_chemistry, 1)
        assert first['date'] == session.current_date.isoformat()
        replaced = first['starters'][-1]
        inserted = first['bench'][0]
        payload = json.dumps({'action':'swap_bench','starter_id':replaced['id'],'bench_id':inserted['id']}).encode()
        request = Request(base+'/api/squad', data=payload, headers={'Content-Type':'application/json'}, method='POST')
        with urlopen(request, timeout=5) as response:
            changed = json.load(response)
        assert inserted['id'] in {p['id'] for p in changed['starters']}
        assert replaced['id'] not in {p['id'] for p in changed['starters']}
        with urlopen(base+'/api/squad',timeout=5) as response:
            fresh = json.load(response)
        assert fresh['starters'] == changed['starters']
        assert fresh['squad_status'] == changed['squad_status']
        for src in ('/portable/polish.css','/public/squad/portraits.js','/public/squad/polish.css','/public/squad/board.js'):
            with urlopen(base+src,timeout=5) as response:
                assert response.status==200
                assert response.read()
    finally:
        server.shutdown()
        server.server_close()
        runner.join(timeout=5)


def test_unchanged_rating_and_familiarity_sources():
    session = DevelopmentSession()
    from football_manager.ui_shell.models import squad_read_model
    view = squad_read_model(session)
    assert view['roster_capabilities']['market_values'] is True
    # TS-22 connects the genuine player-season ledger; rating formulas stay unchanged.
    assert view['roster_capabilities']['season_player_ledger'] is True
    assert all(p['market_value_gbp'] > 0 and p['contract'] is not None for p in view['roster'])
    for player in view['starters']:
        row = next(r for r in session.squad_rows() if r.player_id == player['id'])
        assert player['ovr'] == round(row.overall, 1)
        assert player['act'] == round(row.current, 1)
        assert player['familiarities']
