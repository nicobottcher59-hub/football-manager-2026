"""Optional real-browser validation. No Node installation required by the game.

Uses the existing Python HTTP server when loopback navigation is allowed.
When host policy blocks it, loads the same assets with a Python read-model
bridge, reporting that limitation. HTTP contracts are tested separately.
Needs optional Python Playwright and a locally installed Chromium for validation.
"""
from __future__ import annotations
import argparse
from copy import deepcopy
from datetime import date
import json
import re
from pathlib import Path
import shutil
import sys
from tempfile import TemporaryDirectory
from threading import Thread

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
try:
    from playwright.sync_api import sync_playwright
except ImportError as exc:
    raise SystemExit('Optional browser validation requires Python Playwright on the validation machine.') from exc
from football_manager.dev_ui import DevelopmentSession
from football_manager.persistence import SQLiteSaveRepository
from football_manager.ui_shell.server import create_server
from football_manager.ui_shell.dressing_room import dressing_room_read_model
from football_manager.ui_shell.application import GameApplication
from football_manager.ui_shell.match import prematch_read_model


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=Path('reports/ts20/browser'))
    parser.add_argument('--executable',default=shutil.which('chromium') or shutil.which('google-chrome'))
    args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=True)
    checks=[];errors=[];transport="live HTTP"
    def check(name,condition):
        assert condition,name
        checks.append(name);print('PASS',name,flush=True)
    with TemporaryDirectory() as tmp:
        session=DevelopmentSession()
        server=create_server(port=0,session=session,save_repository=SQLiteSaveRepository(Path(tmp)/'browser.sqlite3'))
        runtime=server.RequestHandlerClass.runtime
        app=GameApplication(runtime,prematch_builder=prematch_read_model)
        thread=Thread(target=server.serve_forever,daemon=True);thread.start()
        url=f'http://127.0.0.1:{server.server_port}/portable/'
        try:
            with sync_playwright() as p:
                browser=p.chromium.launch(executable_path=args.executable,headless=True,args=['--no-sandbox','--disable-dev-shm-usage'])
                page=browser.new_page(viewport={'width':1640,'height':1080},device_scale_factor=1)
                page.on('pageerror',lambda e:errors.append(str(e)))
                responses=[];page.on('response',lambda r:responses.append((r.url,r.status)))
                try:
                    page.goto(url,wait_until='networkidle')
                except Exception as exc:
                    if 'ERR_BLOCKED_BY_ADMINISTRATOR' not in str(exc):
                        raise
                    # This environment blocks loopback navigation. Keep that
                    # policy intact: load our local files into about:blank and
                    # bridge fetch calls to the exact Python read/application
                    # models. HTTP itself is covered separately by pytest.
                    transport='in-process Python bridge (loopback navigation blocked)'
                    from football_manager.ui_shell.models import squad_read_model
                    from football_manager.ui_shell.progression import progression_read_model
                    from football_manager.ui_shell.calendar import calendar_read_model
                    from football_manager.ui_shell.competitions import competition_options, competition_read_model
                    def fetch_bridge(path):
                        with runtime.lock:
                            if path=='/api/dressing-room':data=dressing_room_read_model(runtime.session)
                            elif path=='/api/squad':data=squad_read_model(runtime.session,runtime.admin)
                            elif path=='/api/progression':data=progression_read_model(runtime.session)
                            elif path=='/api/calendar':data=calendar_read_model(runtime.session)
                            elif path=='/api/competitions':data=competition_options(runtime.session)
                            elif path.startswith('/api/competitions/'):data=competition_read_model(runtime.session,path.split('/')[-1])
                            else:return {'status':404,'data':{'error':'unknown test endpoint'}}
                            return {'status':200,'data':data}
                    page.close()
                    page=browser.new_page(viewport={'width':1640,'height':1080},device_scale_factor=1)
                    page.on('pageerror',lambda e:errors.append(str(e)))
                    html=(ROOT/'frontend/portable/index.html').read_text(encoding='utf-8')
                    html=re.sub(r'<link[^>]+>|<script[^>]*>.*?</script>','',html,flags=re.S)
                    page.set_content(html)
                    page.expose_function('fmTS20Fetch',fetch_bridge)
                    page.evaluate("""() => {window.__ts20Offline=false;window.fetch=async url=>{
                        const r=window.__ts20Offline && url==='/api/dressing-room' ? {status:503,data:{}} : await window.fmTS20Fetch(String(url));
                        return {ok:r.status<300,status:r.status,json:async()=>r.data};};}""")
                    for name in ('styles','polish','calendar','simulation','competitions','dressing_room'):
                        page.add_style_tag(path=ROOT/f'frontend/portable/{name}.css')
                    for file in ('frontend/portable/data/demo.js','frontend/public/squad/portraits.js','frontend/public/squad/board.js',
                                 'frontend/portable/calendar.js','frontend/portable/competitions.js','frontend/portable/simulation.js',
                                 'frontend/portable/dressing_room.js','frontend/portable/portable.js'):
                        page.add_script_tag(path=ROOT/file)
                    page.wait_for_timeout(400)
                room_before=deepcopy(session.dressing_room)
                player_states=deepcopy([q.state for q in session.home_club.squad.players])
                page.locator('.sidebar .nav-item',has_text='Dressing Room').click()
                page.wait_for_selector('.dr-player')
                check('sidebar opens the integrated Dressing Room page',page.locator('.header-left h1').inner_text()=='Dressing Room')
                check('all eighteen registered players appear in four hierarchy tiers',page.locator('.dr-player').count()==18 and page.locator('.dr-tier').count()==4)
                check('screen is non-blocking and informational',page.locator('.dr-live').inner_text()=='No decisions required' and page.locator('[role="dialog"]').count()==0)
                page.locator('.dr-player').nth(4).click()
                chosen=page.locator('.dr-player.is-selected').get_attribute('data-dr-player')
                expected=session.home_club.squad.get(chosen).full_name
                check('selecting a player shows the correct profile',page.locator('.dr-profile-heading h3').inner_text()==expected)
                check('network reflects the selected player',page.locator('.dr-node.is-selected').get_attribute('data-dr-player')==chosen)
                node=page.locator('.dr-node').nth(2);pid=node.get_attribute('data-dr-player')
                node.focus();page.keyboard.press('Enter')
                check('relationship network is keyboard accessible',page.locator('.dr-player.is-selected').get_attribute('data-dr-player')==pid)
                page.locator('[data-dr-refresh]').click();page.wait_for_timeout(250)
                check('viewing/selecting/refreshing never advances social state',session.dressing_room==room_before)
                check('UI interactions do not change player morale or state',[q.state for q in session.home_club.squad.players]==player_states)
                page.screenshot(path=str(args.output/'dressing_room_initial.png'),full_page=True)
                page.locator('.sidebar .nav-item',has_text='Squad').click()
                page.wait_for_timeout(100)
                check('existing Squad route remains available',page.locator('.header-left h1').inner_text()=='Squad')
                page.locator('.sidebar .nav-item',has_text='Tactics').click()
                if transport=='live HTTP':
                    frame=page.frame_locator('iframe')
                    frame.locator('[data-tactic-mode="editor"]').wait_for()
                    frame.locator('[data-tactic-mode="editor"]').click()
                    check('TS-19 tactical editor still has eleven markers',frame.locator('[data-studio-slot]').count()==11)
                else:
                    check('Tactics keeps its existing editor route', 'view=tactics' in page.locator('iframe').get_attribute('src'))
                page.locator('.sidebar .nav-item',has_text='Dressing Room').click();page.wait_for_selector('.dr-player')
                # Real career progression through the same application service,
                # then the same browser refresh exposed to the user.
                with runtime.lock:
                    app.command('progression.command',{'action':'simulate_until','date':'2026-09-21'})
                page.evaluate('window.FMProgression.refresh()')
                page.locator('[data-dr-refresh]').click()
                page.wait_for_function("document.querySelector('.dr-date')?.textContent === '2026-09-25'")
                model=dressing_room_read_model(runtime.session)
                check('live page follows actual dates after managed matches',model['date']=='2026-09-21' and model['revision']>0)
                check('hierarchy changes from real progression',runtime.session.dressing_room!=room_before)
                check('actual playing time is displayed',sum(m['recent_minutes'] for m in model['members'])>0)
                page.evaluate('window.scrollTo(0,0)')
                page.screenshot(path=str(args.output/'dressing_room_progressed.png'),full_page=True)
                page.screenshot(path=str(args.output/'dressing_room_preview.png'),full_page=False)
                with runtime.lock:
                    app.command('career.save',{'slot_id':'browser-ts20','display_name':'Browser TS20','expected_revision':0})
                    saved=deepcopy(model)
                    app.command('progression.command',{'action':'simulate_until','date':'2026-10-03'})
                    app.command('career.load',{'slot_id':'browser-ts20'})
                page.evaluate('window.FMProgression.refresh()')
                page.locator('[data-dr-refresh]').click();page.wait_for_timeout(300)
                check('save/load preserves visible relationships and hierarchy',dressing_room_read_model(runtime.session)==saved)
                # Render an untrusted name as text, never as HTML/event markup.
                player=runtime.session.home_club.squad.players[0]
                from dataclasses import replace
                original=player.identity
                player.identity=replace(original,first_name='<img src=x onerror="window.ts20xss=1">')
                page.locator('[data-dr-refresh]').click();page.wait_for_timeout(250)
                page.locator('.dr-player').filter(has_text=player.identity.last_name).first.click()
                check('player-controlled text is safely escaped',not page.evaluate('Boolean(window.ts20xss)') and page.locator('.dr-profile img').count()==0)
                player.identity=original
                page.locator('[data-dr-refresh]').click();page.wait_for_timeout(200)
                for width,height in [(1280,800),(1024,768),(800,900)]:
                    page.set_viewport_size({'width':width,'height':height});page.wait_for_timeout(150)
                    bounds=page.locator('.fm-dressing-room-screen').evaluate("e=>({w:e.clientWidth,scroll:e.scrollWidth})")
                    check(f'new page has no horizontal overflow at {width}px',bounds['scroll']<=bounds['w']+1)
                    page.screenshot(path=str(args.output/f'dressing_room_{width}.png'),full_page=True)
                # Controlled offline response tests fail-safe rendering.
                if transport=='live HTTP':page.route('**/api/dressing-room',lambda route:route.fulfill(status=503,body='{}',content_type='application/json'))
                else:page.evaluate('window.__ts20Offline=true')
                page.locator('[data-dr-refresh]').click();page.wait_for_selector('.dr-error')
                check('failed fetch does not present stale career data as current',page.locator('.dr-player').count()==0)
                if transport=='live HTTP':page.unroute('**/api/dressing-room')
                else:page.evaluate('window.__ts20Offline=false')
                page.locator('[data-dr-retry]').click();page.wait_for_selector('.dr-player')
                check('recoverable fetch errors have a working retry',page.locator('.dr-player').count()==18)
                check('no uncaught browser errors',not errors)
                browser.close()
        finally:
            server.shutdown();server.server_close();thread.join(timeout=5)
    (args.output/'results.json').write_text(json.dumps({'passed':len(checks),'checks':checks,'browser_errors':errors,'transport':transport},indent=2),encoding='utf-8')
    print(f'{len(checks)} browser checks passed',flush=True)

if __name__=='__main__':
    main()
