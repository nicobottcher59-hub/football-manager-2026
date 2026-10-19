"""Portable assets and real HTTP tests; only syntax check optionally uses Node."""
from __future__ import annotations
from copy import deepcopy
import json
from pathlib import Path
import re
import shutil
import subprocess
from threading import Thread
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from football_manager.dev_ui import DevelopmentSession
from football_manager.persistence import SQLiteSaveRepository
from football_manager.ui_shell.server import create_server

ROOT=Path(__file__).resolve().parents[1]


def test_new_screen_is_in_sidebar_without_replacing_squad_or_tactics():
    html=(ROOT/'frontend/portable/index.html').read_text(encoding='utf-8')
    assert '<span>Dressing Room</span>' in html
    assert '<span>Squad</span>' in html and '<span>Tactics</span>' in html
    scripts=re.findall(r'<script[^>]+src="([^"]+)"',html)
    assert scripts.index('dressing_room.js')<scripts.index('portable.js')
    assert 'dressing_room.css' in html
    for path in scripts:
        assert '://' not in path
        assert (ROOT/'frontend/portable'/path).resolve().is_file()
    source=(ROOT/'frontend/portable/dressing_room.js').read_text(encoding='utf-8')
    assert '/api/dressing-room' in source
    assert "method:'POST'" not in source and 'localStorage' not in source
    assert 'aria-pressed' in source and 'tabindex="0"' in source
    assert 'No decisions required' in source


@pytest.mark.skipif(shutil.which('node') is None,reason='Optional Node syntax verification; Python and the browser run TS-20 without Node')
def test_javascript_syntax():
    for name in ('dressing_room.js','portable.js'):
        subprocess.run([shutil.which('node'),'--check',str(ROOT/'frontend/portable'/name)],check=True,capture_output=True,timeout=10)


def test_live_http_read_only_payload_assets_and_no_manual_social_endpoint(tmp_path):
    session=DevelopmentSession()
    server=create_server(port=0,session=session,save_repository=SQLiteSaveRepository(tmp_path/'http.sqlite3'))
    thread=Thread(target=server.serve_forever,daemon=True);thread.start()
    base=f'http://127.0.0.1:{server.server_port}'
    try:
        before=deepcopy(session.dressing_room)
        states=[deepcopy(p.state) for p in session.home_club.squad.players]
        payload=None
        for _ in range(3):
            with urlopen(base+'/api/dressing-room',timeout=15) as response:
                data=json.loads(response.read())
            assert data['source']=='python-dressing-room'
            if payload is not None:
                assert data==payload
            payload=data
        assert session.dressing_room==before
        assert [p.state for p in session.home_club.squad.players]==states
        for asset in ('dressing_room.js','dressing_room.css','index.html'):
            with urlopen(base+'/portable/'+asset,timeout=15) as response:
                assert response.status==200 and response.read()
        req=Request(base+'/api/dressing-room',data=b'{"action":"assign_friend"}',headers={'Content-Type':'application/json'},method='POST')
        with pytest.raises(HTTPError) as error:
            urlopen(req,timeout=15)
        assert error.value.code==403
        assert session.dressing_room==before
    finally:
        server.shutdown();server.server_close();thread.join(timeout=5)
