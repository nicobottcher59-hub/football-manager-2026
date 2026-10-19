"""Exercise the real portable editor in Chromium against the Python application.
A local in-process bridge replaces only network transport (not frontend logic).
"""
from pathlib import Path
from tempfile import TemporaryDirectory
import json, re, time
import argparse, shutil
try:
    from playwright.sync_api import sync_playwright
except ImportError as exc:
    raise SystemExit("Optional browser check: requires the Python playwright package. Standard pytest does not require it.") from exc
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from football_manager.dev_ui.session import DevelopmentSession
from football_manager.ui_shell.runtime import UIRuntime
from football_manager.ui_shell.application import GameApplication
from football_manager.ui_shell.models import squad_read_model
from football_manager.ui_shell.match import prematch_read_model
from football_manager.persistence import SQLiteSaveRepository
from football_manager.domain.tactical_geometry import phase_points

ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--output',type=Path,default=Path('reports/ts19/browser'))
parser.add_argument('--executable',default=shutil.which('chromium') or shutil.which('google-chrome'))
args=parser.parse_args()
OUT=args.output
OUT.mkdir(parents=True,exist_ok=True)
checks=[]
def check(name, condition):
    assert condition, name
    checks.append(name)
    print('PASS',name,flush=True)
with TemporaryDirectory() as tmp:
    runtime=UIRuntime(DevelopmentSession(),SQLiteSaveRepository(Path(tmp)/'test.sqlite3'))
    application=GameApplication(runtime,prematch_builder=prematch_read_model)
    calls=[]
    failures=[]
    fail_next=[False]
    def bridge(url, method, body):
        try:
            if method=='GET' and url=='/api/squad':
                value=squad_read_model(runtime.session,runtime.admin)
            elif method=='GET' and url=='/api/match':
                value=prematch_read_model(runtime.session,runtime.admin,runtime._match_commands_for_current_fixture())
                value['kits']=dict(runtime.match_kits)
            elif method=='POST' and url=='/api/match':
                command=json.loads(body);calls.append(command)
                value=application.command('match.command',command)
            elif method=='POST' and url=='/api/squad':
                command=json.loads(body);calls.append(command)
                if fail_next[0]:
                    fail_next[0]=False
                    raise ValueError('controlled transport rejection')
                value=application.command('squad.command',command)
            else: raise ValueError('unexpected endpoint '+url)
            return {'status':200,'data':value}
        except (ValueError,TypeError,KeyError) as exc:
            failures.append(str(exc))
            return {'status':400,'data':{'error':str(exc)}}
    html=(ROOT/'frontend/public/squad/embed.html').read_text()
    html=re.sub(r'<link[^>]+>|<script[^>]*>.*?</script>','',html,flags=re.S)
    with sync_playwright() as p:
        browser=p.chromium.launch(executable_path=args.executable,headless=True,args=['--no-sandbox','--disable-dev-shm-usage'])
        page=browser.new_page(viewport={'width':1550,'height':1020},device_scale_factor=1)
        errors=[]
        page.on('pageerror',lambda exc: errors.append(str(exc)))
        page.goto('about:blank?view=tactics')
        page.set_content(html)
        page.expose_function('fmBackend',bridge)
        page.evaluate('''() => {window.__responses=0;window.fetch=async(url,opt={})=>{const r=await window.fmBackend(String(url),opt.method||'GET',opt.body||'');window.__responses++;return {ok:r.status<300,status:r.status,json:async()=>r.data};};}''')
        for name in ['squad','roster','polish','studio']:
            page.add_style_tag(path=ROOT/f'frontend/public/squad/{name}.css')
        for name in ['board','formation_layout','portraits','roster','studio','squad']:
            page.add_script_tag(path=ROOT/f'frontend/public/squad/{name}.js')
        page.wait_for_selector('[data-tactic-mode="editor"]')
        def settle(): page.wait_for_timeout(150)
        def click(selector): page.click(selector); settle()
        def confirmed(selector): page.once('dialog',lambda d:d.accept());click(selector)
        def targets(phase='in_possession'):
            return phase_points(runtime.session.home_tactic,phase)
        def anchor(slot,phase='in_possession'):
            return next((p for s in runtime.session.home_tactic.phase_shapes if s.phase==phase for p in s.points if p.slot_id==slot),None)
        def drag(slot,x,y,before_release=None,position=None):
            token=page.locator(f'[data-studio-slot="{slot}"]')
            token.scroll_into_view_if_needed()
            b=page.locator('.fm-pitch').bounding_box(); t=token.bounding_box()
            page.mouse.move(t['x']+t['width']/2,t['y']+t['height']/2);page.mouse.down()
            page.mouse.move(b['x']+b['width']*x,b['y']+b['height']*y,steps=8)
            if before_release: before_release()
            page.mouse.up();settle()
            if page.locator('.ts-placement-dialog[open]').count():
                available=page.locator('.ts-placement-options [data-position]').evaluate_all('(els)=>els.map(e=>e.dataset.position)')
                current=runtime.session.home_tactic.formation.slot(slot).position.value
                chosen=position or (current if current in available else available[0])
                click(f'[data-position="{chosen}"]')
        baseline={q['id']:(q['ovr'],q['act']) for q in squad_read_model(runtime.session)['starters']}
        check('lineup keeps eleven cards, no draggable studio markers',page.locator('[data-player-slot]').count()==11 and page.locator('[data-studio-slot]').count()==0)
        click('[data-tactic-mode="editor"]')
        check('editor has eleven named, keyboard-accessible markers',page.locator('[data-studio-slot]').count()==11 and page.locator('.ts-token-name').count()==11)
        click('[data-studio="mode"][data-mode="coverage"]')
        check('coverage paints the existing canvas',page.locator('.ts-overlay').count()==1 and page.locator('[data-studio-summary]').inner_text().find('Geometric estimate')>=0)
        click('[data-studio="mode"][data-mode="vulnerabilities"]')
        before_calls=len(calls)
        def preview_check():
            check('drag preview does not post partial moves',len(calls)==before_calls)
        drag('lb',.14,.24,preview_check)
        check('drag commits normalized target once',len(calls)==before_calls+1 and abs(anchor('lb').y-.24)<.002)
        drag('rb',.86,.24)
        check('advancing fullbacks flags both exterior channels',all(s in page.locator('[data-studio-summary]').inner_text() for s in ['Left channel','Right channel']))
        check('confirmed drops apply zonal positions without replacing players',runtime.session.home_tactic.formation.slot('lb').position.value=='LW' and runtime.session.home_tactic.formation.slot('rb').position.value=='RW' and set(baseline)=={q['id'] for q in squad_read_model(runtime.session)['starters']})
        before=len(calls)
        token=page.locator('[data-studio-slot="lb"]');token.focus();page.keyboard.press('ArrowRight');page.keyboard.press('Escape');settle()
        check('Escape cancels keyboard draft without mutating',len(calls)==before)
        token=page.locator('[data-studio-slot="lb"]');token.focus();page.keyboard.press('ArrowRight');page.keyboard.press('Enter');settle();click('[data-position="LW"]')
        check('keyboard Enter applies a one-percent step',abs(anchor('lb').x-.15)<.002 and len(calls)==before+1)
        click('[data-studio="undo"]')
        check('position undo restores previous anchors',abs(anchor('lb').x-.14)<.002)
        click('[data-phase="out_of_possession"]')
        check('the other phase is independent',anchor('lb','out_of_possession') is None and targets('out_of_possession')['lb'][1]>.5)
        confirmed('[data-studio="copy-phase"]')
        check('phase copying stores eleven independent anchors',sum(len(s.points) for s in runtime.session.home_tactic.phase_shapes if s.phase=='out_of_possession')==11)
        confirmed('[data-studio="reset-phase"]')
        check('phase reset preserves the other phase',anchor('lb','out_of_possession') is None and anchor('lb') is not None)
        click('[data-phase="in_possession"]')
        drag('lb',.36,.61,position='LCM')
        click('[data-studio-slot="lb"]')
        check('click opens existing role editor with explicit position control',page.locator('[data-studio-position="lb"]').count()==1)
        page.select_option('[data-studio-position="lb"]','DM');settle()
        check('explicit position changes real position and valid role',runtime.session.home_tactic.formation.slot('lb').position.value=='DM')
        click('[data-action="close-player"]')
        click('[data-studio="toggle-library"]')
        page.fill('#ts-tactic-name','Primary asymmetry');click('[data-studio="save-new"]')
        primary=runtime.session.tactical_studio.active_id
        check('library stores a named template',runtime.session.tactical_studio.library[primary].name=='Primary asymmetry')
        page.select_option('[data-studio-plan="A"]',primary);settle()
        check('plan A references saved template',runtime.session.tactical_studio.plans['A']==primary)
        drag('st',.65,.20)
        page.fill('#ts-tactic-name','Second shape');click('[data-studio="save-new"]')
        second=runtime.session.tactical_studio.active_id
        page.select_option('[data-studio-plan="B"]',second);settle()
        check('second template is independent from original',len(runtime.session.tactical_studio.library)==2 and runtime.session.tactical_studio.library[primary].tactic.phase_shapes!=runtime.session.tactical_studio.library[second].tactic.phase_shapes)
        page.fill('#ts-tactic-name','Second shape');click('[data-studio="save-new"]')
        check('duplicate name rejects without corrupting the library',len(runtime.session.tactical_studio.library)==2 and 'already exists' in page.locator('#squad-notice').inner_text())
        page.select_option('#ts-library-select',primary);settle()
        page.once('dialog',lambda d:d.accept('Primary copy'));click('[data-studio="duplicate"]')
        copy_id=next(e.entry_id for e in runtime.session.tactical_studio.library.values() if e.name=='Primary copy')
        page.select_option('#ts-library-select',copy_id);settle()
        page.once('dialog',lambda d:d.accept('Renamed copy'));click('[data-studio="rename"]')
        check('duplicate and rename preserve the original',runtime.session.tactical_studio.library[copy_id].name=='Renamed copy' and runtime.session.tactical_studio.library[primary].name=='Primary asymmetry')
        confirmed('[data-studio="delete"]')
        check('delete removes only selected template',copy_id not in runtime.session.tactical_studio.library and len(runtime.session.tactical_studio.library)==2)
        drag('st',.70,.25)
        page.select_option('#ts-library-select',primary);settle()
        before=len(calls)
        page.once('dialog',lambda d:d.dismiss());click('[data-studio="load"]')
        check('cancel load keeps unsaved working shape',len(calls)==before and abs(anchor('st').x-.70)<.002)
        confirmed('[data-studio="load"]')
        check('accepted load applies the selected saved template',runtime.session.tactical_studio.active_id==primary and anchor('st') is None)
        click('[data-studio="toggle-schedule"]')
        click('[data-studio="add-rule"]')
        page.select_option('[data-rule-plan]','B');page.fill('[data-rule-minute]','60');page.select_option('[data-rule-condition]','trailing');click('[data-studio="save-rules"]')
        check('minute and score plan schedule reaches Python',len(runtime.session.tactical_studio.rules)==1 and runtime.session.tactical_studio.rules[0].plan=='B' and runtime.session.tactical_studio.rules[0].condition=='trailing')
        click('[data-studio="toggle-library"]');click('[data-studio="toggle-schedule"]')
        click('[data-studio="mode"][data-mode="laboratory"]')
        check('laboratory compares actual rival inside same pitch',page.locator('[data-studio-opponent] option').count()==29 and len(browser.contexts[0].pages)==1)
        page.select_option('[data-studio-opponent]','dev-5-2-2-1');settle()
        check('catalogue opponent updates hypothetical analysis','Hypothetical catalogue' in page.locator('[data-studio-summary]').inner_text())
        page.screenshot(path=str(OUT/'studio_laboratory.png'),full_page=True)
        click('[data-studio="mode"][data-mode="vulnerabilities"]')
        page.screenshot(path=str(OUT/'studio_vulnerabilities.png'),full_page=True)
        for width in (1100,1550,1920):
            page.set_viewport_size({'width':width,'height':1050});settle()
            check(f'no horizontal page overflow at width {width}',page.evaluate('document.body.scrollWidth<=window.innerWidth+1'))
        fail_next[0]=True;old=targets()['rb'];drag('rb',.75,.32)
        check('rejected edit restores backend truth',targets()['rb']==old and 'Change not applied' in page.locator('#squad-notice').inner_text())
        check('no unexpected JavaScript runtime errors',not errors)
        click('[data-tactic-mode="lineup"]')
        check('lineup remains lineup with eleven cards',page.locator('[data-player-slot]').count()==11 and page.locator('.ts-overlay').count()==0 and page.locator('[data-studio-slot]').count()==0)
        check('lineup cards remain equal sized',page.locator('[data-player-slot]').evaluate_all('(els)=>new Set(els.map(e=>{const r=e.getBoundingClientRect();return Math.round(r.width)+":"+Math.round(r.height)})).size')==1)
        # Verify the real matchday frontend, not only the editor command API.
        from copy import deepcopy
        from football_manager.ui_shell.progression import pending_managed_match,advance_day
        while runtime.session.current_date<pending_managed_match(runtime.session).match_date:
            advance_day(runtime.session)
        usual_studio=deepcopy(runtime.session.tactical_studio)
        page.close()
        page=browser.new_page(viewport={'width':1550,'height':1050},device_scale_factor=1)
        page.on('pageerror',lambda exc:errors.append(str(exc)))
        page.goto('about:blank')
        match_html=(ROOT/'frontend/portable/match.html').read_text()
        page.set_content(re.sub(r'<link[^>]+>|<script[^>]*>.*?</script>','',match_html,flags=re.S))
        page.expose_function('fmBackend',bridge)
        page.evaluate("""() => {window.fetch=async(url,opt={})=>{const r=await window.fmBackend(String(url),opt.method||'GET',opt.body||'');return {ok:r.status<300,status:r.status,json:async()=>r.data};};}""")
        page.add_style_tag(path=ROOT/'frontend/portable/match.css')
        page.add_script_tag(path=ROOT/'frontend/portable/match.js')
        page.wait_for_selector('#fm-quick')
        check('matchday renders saved plan choices',page.locator('[data-match-plan]:not([disabled])').count()==2)
        click('[data-match-plan="B"]')
        check('kickoff plan is a match-only edit',runtime.session.tactical_studio==usual_studio and len(runtime.match_commands)==1)
        click('.fm-match-schedule summary')
        page.select_option('[data-match-rule-plan]','A')
        page.fill('[data-match-rule-minute]','60')
        page.select_option('[data-match-rule-condition]','always')
        click('#fm-save-match-rules')
        check('matchday schedule posts through the real application',len(runtime.match_commands)==2)
        page.screenshot(path=str(OUT/'studio_match_plans.png'),full_page=True)
        click('#fm-quick')
        page.wait_for_selector('.fm-result-scene')
        check('quick sim completes and renders the real plan event',page.locator('.fm-event-tactical_plan').count()==1 and 'Plan A applied' in page.locator('.fm-event-tactical_plan').inner_text())
        check('match-only plan edits do not replace the career setup',runtime.session.tactical_studio==usual_studio)
        check('matchday browser has no runtime errors',not errors)
        page.screenshot(path=str(OUT/'studio_match_result.png'),full_page=True)
        (OUT/'browser_interactions.json').write_text(json.dumps({'checks':checks,'count':len(checks),'runtime_errors':errors,'expected_rejections':failures,'commands':len(calls)},indent=2))
        browser.close()
