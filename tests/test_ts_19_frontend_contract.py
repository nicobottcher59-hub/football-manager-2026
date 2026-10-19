"""Portable integration contracts; Node is OPTIONAL, never required by the game."""
from __future__ import annotations
import json
from pathlib import Path
import random
import re
import shutil
import subprocess
from threading import Thread
from urllib.error import HTTPError
from urllib.request import Request, urlopen
import pytest
from football_manager.dev_ui.session import DevelopmentSession
from football_manager.dev_ui.formations import development_formations
from football_manager.domain.tactical_geometry import occupation, phase_points, rest_cover
from football_manager.ui_shell.models import squad_read_model
from football_manager.ui_shell.server import create_server
from football_manager.ui_shell.transactions import apply_squad_command_atomically
from football_manager.persistence import SQLiteSaveRepository

ROOT=Path(__file__).resolve().parents[1]
NODE=shutil.which('node')
node_only=pytest.mark.skipif(NODE is None,reason='Optional Node.js frontend verification; not required to run the portable game')

def test_studio_assets_are_local_ordered_and_leave_lineup_entrypoint_intact():
    html=(ROOT/'frontend/public/squad/embed.html').read_text(encoding='utf-8')
    scripts=re.findall(r'<script[^>]+src="([^"]+)"',html)
    assert scripts.index('board.js')<scripts.index('studio.js')<scripts.index('squad.js')
    assert 'studio.css' in html
    assert all('://' not in s for s in scripts)
    for asset in scripts:
        assert (ROOT/'frontend/public/squad'/asset).is_file()
    source=(ROOT/'frontend/public/squad/squad.js').read_text(encoding='utf-8')
    assert "tacticMode==='editor'" in source
    assert 'data-player-slot' in source and 'swap_starters' in source

@node_only
def test_browser_and_python_phase_geometry_agree_for_every_formation():
    session=DevelopmentSession()
    cases=[]
    for formation in development_formations():
        session.set_formation(formation.formation_id)
        for style in ('balanced','wide_attack','constant_press'):
            session.set_tactical_preset(style)
            data=squad_read_model(session)
            for phase in ('in_possession','out_of_possession'):
                cases.append({'data':data,'phase':phase,'expected':{key:{'x':x*100,'y':y*100} for key,(x,y) in phase_points(session.home_tactic,phase).items()}})
    apply_squad_command_atomically(session,{'action':'studio_point','slot_id':'lb','phase':'in_possession','x':42,'y':28},None)
    apply_squad_command_atomically(session,{'action':'studio_position','slot_id':'lb','position':'AM'},None)
    for phase in ('in_possession','out_of_possession'):
        cases.append({'data':squad_read_model(session),'phase':phase,'expected':{key:{'x':x*100,'y':y*100} for key,(x,y) in phase_points(session.home_tactic,phase).items()}})
    js="""const fs=require('fs');const vm=require('vm');const scope={};vm.runInNewContext(fs.readFileSync('./frontend/public/squad/board.js','utf8'),scope);const board=scope.FMTacticalBoard;
    const cases=JSON.parse(fs.readFileSync(0,'utf8'));console.log(JSON.stringify(cases.map(c=>board.place(c.data,c.phase))));"""
    output=subprocess.run([NODE,'-e',js],cwd=ROOT,input=json.dumps(cases),text=True,capture_output=True,check=True,timeout=30)
    for case,actual in zip(cases,json.loads(output.stdout),strict=True):
        assert set(actual)==set(case['expected'])
        for key,point in actual.items():
            assert point==pytest.approx(case['expected'][key]),(case['data']['formation']['id'],case['phase'],key)

@node_only
def test_overlay_math_matches_backend_and_names_are_escaped():
    rng=random.Random(19)
    points=[(rng.uniform(.04,.96),rng.uniform(.04,.96)) for _ in range(10)]
    cells=[(x/10,y/10) for x in range(1,10) for y in range(1,10)]
    data={'points':[{'x':x,'y':y} for x,y in points],'cells':cells}
    js="""const fs=require('fs');const vm=require('vm');const scope={};vm.runInNewContext(fs.readFileSync('./frontend/public/squad/studio.js','utf8'),scope);const s=scope.FMStudio;const d=JSON.parse(fs.readFileSync(0,'utf8'));
    console.log(JSON.stringify({coverage:d.cells.map(([x,y])=>s.coverage(d.points,x,y)),rest:[.16,.5,.84].map(x=>s.restCover(d.points,x)),marker:s.marker({position:'ST',slot_id:'st'},{short_name:'<script>',name:'<svg onload=bad>',role:'Test',act:80},{x:50,y:14},false)}));"""
    output=subprocess.run([NODE,'-e',js],cwd=ROOT,input=json.dumps(data),text=True,capture_output=True,check=True,timeout=10)
    got=json.loads(output.stdout)
    assert got['coverage']==pytest.approx([occupation(points,x,y) for x,y in cells])
    assert got['rest']==pytest.approx([rest_cover(points,x) for x in (.16,.5,.84)])
    assert '<script>' not in got['marker'] and '<svg' not in got['marker']
    assert '&lt;script&gt;' in got['marker'] and 'aria-label=' in got['marker']

def test_live_http_serves_studio_and_atomically_validates_revision(tmp_path):
    session=DevelopmentSession()
    server=create_server(port=0,session=session,save_repository=SQLiteSaveRepository(tmp_path/'http.sqlite3'))
    thread=Thread(target=server.serve_forever,daemon=True);thread.start()
    base=f'http://127.0.0.1:{server.server_port}'
    def get():
        with urlopen(base+'/api/squad',timeout=10) as r:return json.loads(r.read())
    def post(data):
        req=Request(base+'/api/squad',data=json.dumps(data).encode(),headers={'Content-Type':'application/json'},method='POST')
        with urlopen(req,timeout=10) as r:return json.loads(r.read())
    try:
        for asset in ('studio.js','studio.css','embed.html'):
            with urlopen(base+'/squad/'+asset,timeout=10) as r:
                assert r.status==200 and r.read()
        before=get()
        rev=before['studio']['revision']
        edited=post({'action':'studio_point','slot_id':'lb','phase':'in_possession','x':30,'y':40,'expected_revision':rev})
        assert edited['studio']['revision']==rev+1
        assert edited['studio']['anchors']['in_possession']['lb']=={'x':30,'y':40}
        with pytest.raises(HTTPError) as error:
            post({'action':'studio_save','name':'Stale view','expected_revision':rev})
        assert error.value.code==400
        assert get()==edited
        saved=post({'action':'studio_save','name':'HTTP tactic','expected_revision':rev+1})
        assert saved['studio']['library'][0]['name']=='HTTP tactic'
    finally:
        server.shutdown();server.server_close();thread.join(timeout=5)
