"""Optional Chromium interaction checks for TS-19 placement and heatmap.

Uses real local CSS/JS and the Python application with an in-process transport
bridge. No Node or build step. HTTP transport is tested separately by pytest.
Requires the optional Python playwright package and a Chromium executable.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import json
from pathlib import Path
import re
import shutil
import sys
from tempfile import TemporaryDirectory

try:
    from playwright.sync_api import sync_playwright
except ImportError as exc:
    raise SystemExit('Optional browser check needs Python playwright; the game and pytest do not.') from exc

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from football_manager.dev_ui.session import DevelopmentSession
from football_manager.domain.tactical_geometry import phase_points
from football_manager.persistence import SQLiteSaveRepository
from football_manager.ui_shell.application import GameApplication
from football_manager.ui_shell.match import prematch_read_model
from football_manager.ui_shell.models import squad_read_model
from football_manager.ui_shell.runtime import UIRuntime


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=Path('reports/ts19_placement/browser'))
    parser.add_argument('--executable',default=shutil.which('chromium') or shutil.which('google-chrome'))
    args=parser.parse_args()
    args.output.mkdir(parents=True,exist_ok=True)
    checks=[]
    def check(name,condition):
        assert condition,name
        checks.append(name)
        print('PASS',name,flush=True)
    with TemporaryDirectory() as tmp:
        runtime=UIRuntime(DevelopmentSession(),SQLiteSaveRepository(Path(tmp)/'test.sqlite3'))
        application=GameApplication(runtime,prematch_builder=prematch_read_model)
        calls=[];rejections=[];errors=[];fail_next=[False]
        social_before=deepcopy(getattr(runtime.session,'dressing_room',None))
        def bridge(url,method,body):
            try:
                if method=='GET' and url=='/api/squad':
                    result=squad_read_model(runtime.session,runtime.admin)
                elif method=='POST' and url=='/api/squad':
                    command=json.loads(body);calls.append(command)
                    if fail_next[0]:
                        fail_next[0]=False
                        raise ValueError('controlled transport rejection')
                    result=application.command('squad.command',command)
                else:raise ValueError('unexpected endpoint '+url)
                return dict(status=200,data=result)
            except (ValueError,TypeError,KeyError) as exc:
                rejections.append(str(exc))
                return dict(status=400,data={'error':str(exc)})
        html=(ROOT/'frontend/public/squad/embed.html').read_text(encoding='utf-8')
        html=re.sub(r'<link[^>]+>|<script[^>]*>.*?</script>','',html,flags=re.S)
        with sync_playwright() as p:
            browser=p.chromium.launch(executable_path=args.executable,headless=True,args=['--no-sandbox','--disable-dev-shm-usage'])
            page=browser.new_page(viewport={'width':1550,'height':1050},device_scale_factor=1)
            page.set_default_timeout(15000)
            page.on('pageerror',lambda exc:errors.append(str(exc)))
            page.goto('about:blank?view=tactics')
            page.set_content(html)
            page.expose_function('fmBackend',bridge)
            page.evaluate('''() => {window.fetch=async(url,opt={})=>{const r=await window.fmBackend(String(url),opt.method||'GET',opt.body||'');return {ok:r.status<300,status:r.status,json:async()=>r.data};};}''')
            for name in ('squad','roster','polish','studio'):page.add_style_tag(path=ROOT/f'frontend/public/squad/{name}.css')
            for name in ('board','formation_layout','portraits','roster','studio','squad'):page.add_script_tag(path=ROOT/f'frontend/public/squad/{name}.js')
            page.wait_for_selector('[data-tactic-mode="editor"]')
            def settle():page.wait_for_timeout(180)
            def click(selector):page.click(selector);settle()
            def shape(phase='in_possession'):return phase_points(runtime.session.home_tactic,phase)
            def options():return page.locator('.ts-placement-options [data-position]').evaluate_all('(els)=>els.map(e=>e.dataset.position)')
            def drag(slot,x,y,release=True):
                token=page.locator(f'[data-studio-slot="{slot}"]');token.scroll_into_view_if_needed()
                rect=token.bounding_box();field=page.locator('.fm-pitch').bounding_box()
                page.mouse.move(rect['x']+rect['width']/2,rect['y']+rect['height']/2);page.mouse.down()
                page.mouse.move(field['x']+field['width']*x,field['y']+field['height']*y,steps=12)
                settle()
                if release:page.mouse.up();settle()
            click('[data-tactic-mode="editor"]')
            check('eleven accessible studio markers',page.locator('[data-studio-slot]').count()==11)
            click('[data-mode="coverage"]')
            check('text legend identifies red yellow green and estimate',all(w in page.locator('[data-studio-summary]').inner_text() for w in ('Low (red)','Medium (yellow)','High (green)','Geometric estimate')))
            colors=page.locator('.ts-overlay').evaluate('''canvas=>{const a=canvas.getContext('2d').getImageData(0,0,canvas.width,canvas.height).data;const n={red:0,yellow:0,green:0};for(let i=0;i<a.length;i+=128){const r=a[i],g=a[i+1],b=a[i+2];if(r>g+60)n.red++;if(r>180&&g>140&&b<70)n.yellow++;if(g>r+35)n.green++;}return n;}''')
            check('rendered heatmap actually contains red yellow and green pixels',all(v>0 for v in colors.values()))
            check('heatmap remains a single canvas',page.locator('.ts-overlay').count()==1)
            page.screenshot(path=str(args.output/'coverage.png'),full_page=True)
            original=squad_read_model(runtime.session)
            initial_bitmap=page.locator('.ts-overlay').evaluate('(c)=>c.toDataURL()')
            n=len(calls)
            drag('lb',.50,.29,release=False)
            check('drag preview redraws heatmap without posting',len(calls)==n and page.locator('.ts-overlay').evaluate('(c)=>c.toDataURL()')!=initial_bitmap)
            page.mouse.up();settle()
            check('release opens zonal choices without modifying Python',len(calls)==n and squad_read_model(runtime.session)==original)
            check('central attacking drop offers only ST SS AM',set(options())=={'ST','SS','AM'})
            check('no defender or goalkeeper can be selected upstairs',not set(options())&{'LB','RB','CB','DM','GK'})
            page.screenshot(path=str(args.output/'choose_position.png'),full_page=True)
            click('[data-studio="cancel-placement"]:last-child')
            check('cancel restores original marker and complete tactic',squad_read_model(runtime.session)==original and page.locator('.ts-placement-dialog').count()==0)
            drag('lb',.50,.29)
            page.keyboard.press('Escape');settle()
            check('Escape also cancels without mutation',squad_read_model(runtime.session)==original and len(calls)==n)
            drag('lb',.5,.29)
            click('[data-position="AM"]')
            check('one confirmed command commits both position and location',len(calls)==n+1 and calls[-1]['action']=='studio_place' and runtime.session.home_tactic.formation.slot('lb').position.value=='AM' and shape()['lb']==(.5,.29))
            check('the applied token displays the selected football position',page.locator('[data-studio-slot="lb"] .ts-token-core').inner_text()=='AM')
            click('[data-studio-slot="lb"]')
            offered=page.locator('[data-studio-position="lb"] option:not([disabled])').evaluate_all('(els)=>els.map(e=>e.value)')
            check('role panel is filtered to the same zone',set(offered)=={'ST','SS','AM'})
            page.select_option('[data-studio-position="lb"]','SS');settle()
            check('role panel sends the active phase for backend validation',calls[-1]['phase']=='in_possession' and runtime.session.home_tactic.formation.slot('lb').position.value=='SS')
            click('[data-action="close-player"]')
            on=shape();click('[data-phase="out_of_possession"]')
            drag('lb',.35,.63)
            check('defensive midfield range offers adjacent positions',set(options())=={'LCM','CM','DM'})
            click('[data-position="DM"]')
            check('defending phase edit does not move attacking phase',shape()==on and shape('out_of_possession')['lb']==(.35,.63))
            click('[data-phase="in_possession"]')
            old_st=shape()['st'];n=len(calls)
            token=page.locator('[data-studio-slot="st"]');token.focus();page.keyboard.press('ArrowRight');page.keyboard.press('Enter');settle()
            check('keyboard placement uses the same confirmation',page.locator('.ts-placement-dialog[open]').count()==1 and len(calls)==n)
            click('[data-position="ST"]')
            check('keyboard confirmation commits the one percent step',abs(shape()['st'][0]-old_st[0]-.01)<.0001)
            click('[data-studio="undo"]')
            check('target-only undo still restores prior anchors',shape()['st']==old_st)
            n=len(calls);token=page.locator('[data-studio-slot="st"]');token.focus();page.keyboard.press('ArrowRight');page.keyboard.press('Escape');settle()
            check('Escape cancels keyboard draft before chooser',len(calls)==n and shape()['st']==old_st)
            before=squad_read_model(runtime.session);fail_next[0]=True
            drag('st',.55,.21);click('[data-position="ST"]')
            check('rejected confirmed placement restores Python truth',squad_read_model(runtime.session)==before and 'Change not applied' in page.locator('#squad-notice').inner_text())
            # TS-19 hotfix: LM/RM are visible midway down each flank while
            # the tactical engine keeps its existing LW/RW position codes.
            drag('lb',.16,.45)
            labels=page.locator('.ts-placement-options b').all_inner_texts()
            check('left midfield release offers LM, not a right-side role',
                  'LM' in labels and 'RM' not in labels and 'LW' not in labels)
            page.screenshot(path=str(args.output/'LM-chooser.png'),full_page=True)
            click('[data-position="LW"]')
            check('left midfield choice persists as LM on board without new domain code',
                  page.locator('[data-studio-slot="lb"] .ts-token-core').inner_text()=='LM'
                  and runtime.session.home_tactic.formation.slot('lb').position.value=='LW')
            drag('rw',.84,.45)
            labels=page.locator('.ts-placement-options b').all_inner_texts()
            check('right midfield release offers RM, not a left-side role',
                  'RM' in labels and 'LM' not in labels and 'RW' not in labels)
            page.screenshot(path=str(args.output/'RM-chooser.png'),full_page=True)
            click('[data-position="RW"]')
            check('right midfield choice persists as RM on board without new domain code',
                  page.locator('[data-studio-slot="rw"] .ts-token-core').inner_text()=='RM'
                  and runtime.session.home_tactic.formation.slot('rw').position.value=='RW')
            drag('rw',.9,.22)
            check('right wing drop cannot choose a left sided position',options()==['RW'])
            click('[data-position="RW"]')
            keeper_before=shape()['gk'];n=len(calls)
            drag('gk',.5,.8)
            check('keeper mouse drag is completely ignored in the editor',
                  runtime.session.home_tactic.formation.slot('gk').position.value=='GK'
                  and shape()['gk']==keeper_before and len(calls)==n
                  and page.locator('.ts-placement-dialog').count()==0)
            token=page.locator('[data-studio-slot="gk"]');token.focus()
            page.keyboard.press('ArrowUp');page.keyboard.press('ArrowRight');page.keyboard.press('Enter');settle()
            check('keeper cannot move with keyboard either',shape()['gk']==keeper_before and len(calls)==n)
            page.on('dialog',lambda dialog:dialog.accept())
            other_keeper=shape('out_of_possession')['gk']
            click('[data-studio="copy-phase"]')
            check('copy phase omits goalkeeper and still completes',
                  len(calls)==n+1 and calls[-1]['action']=='studio_shape'
                  and all(point['slot_id']!='gk' for point in calls[-1]['points'])
                  and shape()['gk']==keeper_before and shape('out_of_possession')['gk']==other_keeper)
            click('[data-mode="vulnerabilities"]')
            check('vulnerability mode still paints same pitch',page.locator('.ts-overlay').count()==1 and 'Static spacing warning' in page.locator('[data-studio-summary]').inner_text())
            click('[data-mode="laboratory"]')
            check('laboratory retains its inline opponent control',page.locator('[data-studio-opponent] option').count()==29 and len(browser.contexts[0].pages)==1)
            click('[data-mode="coverage"]')
            for width in (1100,1550,1920):
                page.set_viewport_size({'width':width,'height':1050});settle();drag('st',.50,.28)
                box=page.locator('.ts-placement-dialog').bounding_box()
                check(f'chooser fits viewport {width}',box['x']>=0 and box['y']>=0 and box['x']+box['width']<=width and box['y']+box['height']<=1050)
                page.keyboard.press('Escape');settle()
            check('TS-20 social data is untouched',getattr(runtime.session,'dressing_room',None)==social_before)
            click('[data-tactic-mode="lineup"]')
            check('lineup still has eleven cards and no studio overlay',page.locator('[data-player-slot]').count()==11 and page.locator('.ts-overlay').count()==0)
            check('lineup cards retain a uniform size',page.locator('[data-player-slot]').evaluate_all('(els)=>new Set(els.map(e=>{const r=e.getBoundingClientRect();return Math.round(r.width)+":"+Math.round(r.height)})).size')==1)
            check('no JavaScript runtime errors',not errors)
            (args.output/'results.json').write_text(json.dumps(dict(count=len(checks),checks=checks,commands=len(calls),expected_rejections=rejections,runtime_errors=errors,heatmap_pixels=colors),indent=2),encoding='utf-8')
            browser.close()


if __name__=='__main__':main()
