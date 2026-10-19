"""Optional TS-22 browser regression on a temporary career, never a user's save.

Requires Python Playwright and a Chromium browser ONLY on the test machine.
It is not needed to install, play or run the mandatory pytest suite. No npm,
project compilation, remote service or GitHub Actions job is used.
"""
from __future__ import annotations
import argparse
from copy import deepcopy
from dataclasses import replace
from datetime import date
import json
from pathlib import Path
import sys
import tempfile
from threading import Thread

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--browser', help='Optional Chromium executable path')
    parser.add_argument('--port', type=int, default=0)
    parser.add_argument('--output',type=Path,default=Path('ts22-browser-results.json'))
    args=parser.parse_args()
    try:
        from playwright.sync_api import sync_playwright, expect
    except ImportError:
        parser.error('Optional browser test dependency missing: Python playwright. Required pytest tests do not need it.')
    from football_manager.dev_ui.session import DevelopmentSession
    from football_manager.persistence import SQLiteSaveRepository
    from football_manager.ui_shell.server import create_server
    from football_manager.ui_shell.progression import simulate_until
    from football_manager.persistence.session_codec import capture_manager_graph
    results=[];js_errors=[];failed_requests=[]
    def check(value,name):
        results.append({'check':name,'passed':bool(value)})
        if not value:raise AssertionError(name)
    with tempfile.TemporaryDirectory(prefix='fm-ts22-browser-') as directory:
        server=create_server(port=args.port,save_repository=SQLiteSaveRepository(Path(directory)/'career.sqlite3'),frontend_root=ROOT/'frontend')
        runtime=server.RequestHandlerClass.runtime
        initial=deepcopy(runtime.session)
        thread=Thread(target=server.serve_forever,daemon=True);thread.start()
        base=f'http://127.0.0.1:{server.server_port}'
        try:
            with sync_playwright() as playwright:
                options={'headless':True}
                if args.browser:options['executable_path']=args.browser
                browser=playwright.chromium.launch(**options)
                page=browser.new_page(viewport={'width':1600,'height':1050});page.set_default_timeout(20000)
                page.on('pageerror',lambda e:js_errors.append(str(e)))
                page.on('response',lambda r:failed_requests.append([r.url,r.status]) if r.status>=400 and '/favicon' not in r.url else None)
                def json_api(path):
                    response=page.request.get(base+path);check(response.ok,'GET '+path)
                    return response.json()
                def main_frame():
                    return page.frame_locator('.fm-squad-frame')
                page.goto(base+'/portable/');page.locator('[data-home-competition="fa-cup"]').wait_for()
                card=page.locator('.league-card')
                check(page.locator('[data-home-competition="dev-premier"]').get_attribute('aria-selected')=='true','Home defaults to next-match competition')
                page.locator('[data-home-competition="fa-cup"]').click()
                card.get_by_text('Cup Progress',exact=True).wait_for()
                check('/#page/Competitions' not in page.url,'Home cup tab stays in Home')
                check('pending' in card.inner_text().lower(),'Unknown FA draw remains pending, not a made-up bracket')
                page.evaluate('window.FMHomeCompetition.refresh()');page.wait_for_timeout(250)
                check(page.locator('[data-home-competition="fa-cup"]').get_attribute('aria-selected')=='true','Home refresh keeps selected competition')
                page.locator('[data-home-competition="champions-league"]').click();page.wait_for_timeout(250)
                check(card.locator('.league-row').count()>1,'Champions league phase is a compact table')
                page.locator('[data-home-full]').click();page.locator('.cmp-table').wait_for()
                check('Competitions' in page.url,'Explicit View competition opens full centre')
                page.locator('.cmp-table [data-club-id]').first.click()
                cf=page.frame_locator('#fm-club-frame')
                cf.locator('[data-roster-expand]').first.wait_for() if cf.locator('[data-roster-expand]').count() else page.wait_for_timeout(450)
                # UEFA includes external clubs; choose a registered league club for full profile assertions.
                page.evaluate("window.FMNavigation.club('riverside')")
                cf.locator('[data-roster-expand]').first.wait_for()
                check(cf.locator('.rt-player-row').count()==22,'Generic rival Squad has 22 real players')
                cf.locator('[data-roster-expand]').first.click();cf.locator('.ts22-radar').first.wait_for()
                check(cf.locator('.ts22-radar').count()==2,'Both general and role radars render')
                check(cf.locator('.rt-admin-panel').count()==0,'Player-name click does not open management controls')
                first_more=cf.locator('[data-roster-more]').first;first_more.click()
                check(cf.locator('button:disabled').count()>0,'Rival contextual actions are explicitly disabled')
                check(cf.locator('#rt-player-number').count()==0,'Rival shirt numbers cannot be edited')
                role=cf.locator('[data-chart-role]'); before=deepcopy(runtime.session.home_tactic)
                role_options=role.locator('option').count()
                if role_options>1:
                    role.select_option(index=1);page.wait_for_timeout(300)
                    check(runtime.session.home_tactic==before,'Inspecting a role does not alter the managed tactic')
                check('Not recorded' in cf.locator('body').inner_text(),'Missing stadium/capacity not invented')
                page.get_by_role('button',name='Squad',exact=True).click();sf=main_frame()
                sf.locator('[data-roster-expand]').first.wait_for()
                sf.locator('[data-roster-tab="season"]').click()
                check(sf.locator('#rt-season').count()==1 and sf.locator('#rt-competition').count()==1,'Season and competition filters available')
                check(sf.locator('th button[data-roster-sort="xa"]').count()==0,'Untracked xA is not a fake statistic')
                check(sf.locator('th button[data-roster-sort="average_match_rating"]').count()==1,'Match rating separate from current GRL')
                sf.locator('#rt-competition').select_option('fa-cup');page.wait_for_timeout(250)
                check('FA Cup' in sf.locator('#rt-competition').inner_text(),'Unplayed competition can be selected')
                page.get_by_role('button',name='Tactics',exact=True).click()
                tf=page.locator('.fm-squad-frame').content_frame
                tf.locator('.fm-player-ovr').first.wait_for()
                check(all('GRL' in s for s in tf.locator('.fm-player-ovr').all_inner_texts()),'Tactics highlights current GRL')
                page.locator('.continue-button').click();mf=page.frame_locator('#fm-match-frame')
                mf.locator('#fm-quick').wait_for()
                check(len(page.context.pages)==1,'Match Center uses one browser tab')
                check(not page.locator('.sidebar').is_visible(),'Match occupies full application screen')
                check(mf.locator('.fm-player-metrics').count()==36,'22 starters and 14 bench players show GRL and condition')
                payload=json_api('/api/match')
                fixture=payload['match']['fixture_id']
                check(mf.locator('.fm-player-metrics').first.inner_text().startswith(str(payload['home']['starters'][0]['act'])),'Displayed match rating matches Python')
                mf.locator('#fm-tactics').click();mf.locator('#fm-formation').select_option('dev-4-2-3-1')
                page.wait_for_function("document.querySelector('#fm-match-frame').contentDocument.querySelector('#fm-formation')?.value === 'dev-4-2-3-1'")
                mf.locator('#fm-tactics-back').click();mf.locator('#fm-quick').wait_for()
                before_ids=[p['id'] for p in json_api('/api/match')['managed']['starters']]
                mf.locator('.fm-team-identity [data-profile-club]').last.click();cf.locator('[data-roster-expand]').first.wait_for()
                page.go_back();mf.locator('#fm-quick').wait_for()
                check(json_api('/api/match')['managed']['formation_id']=='dev-4-2-3-1','Returning from a club keeps match-only formation')
                page.reload();mf=page.frame_locator('#fm-match-frame');mf.locator('#fm-quick').wait_for()
                check(json_api('/api/match')['managed']['formation_id']=='dev-4-2-3-1','Refresh keeps match preparation within the running session')
                check([p['id'] for p in json_api('/api/match')['managed']['starters']]==before_ids,'Refresh keeps intended players')
                mf.locator('#fm-quick').click();mf.locator('#fm-result-continue').wait_for()
                ledger=deepcopy(runtime.session._world_squads.statistics)
                response=page.request.post(base+'/api/match',data={'action':'quick_sim','fixture_id':fixture})
                check(response.ok and runtime.session._world_squads.statistics==ledger,'Quick Sim retry does not duplicate statistics')
                check(runtime.session.home_lineup.formation.formation_id==initial.home_lineup.formation.formation_id,'Match-only tactic does not replace usual formation')
                page.reload();mf=page.frame_locator('#fm-match-frame');mf.locator('#fm-result-continue').wait_for()
                check(runtime.session._world_squads.statistics==ledger,'Refreshing result is read-only')
                mf.locator('#fm-result-continue').click();page.wait_for_url('**/#page/Home')
                check(page.locator('.sidebar').is_visible(),'Result Continue returns to career shell')
                page.get_by_role('button',name='Squad',exact=True).click();sf=main_frame();sf.locator('[data-roster-tab="season"]').click()
                own=json_api('/api/squad')
                check(sum(p['season_stats']['appearances'] for p in own['roster'])>=11,'Played match appears in season totals')
                check(sf.locator('.rt-stats-note').inner_text().startswith('Recorded season statistics.'),'Old DEV stats-unavailable banner removed')
                row=sf.locator('.rt-player-row').filter(has=sf.locator('[data-roster-expand="northbridge-10"]'))
                check(row.count()==1,'Actual player row present in updated season stats')
                sf.locator('[data-roster-sort="minutes"]').click()
                check(sf.locator('[data-roster-sort="minutes"]').get_attribute('title') is not None,'Stats sorting remains available')
                page.get_by_role('button',name='Home',exact=True).click();page.locator('[data-home-competition]').first.wait_for()
                next_cid=json_api('/api/home-competition')['default_id']
                expect(page.locator('[data-home-competition="'+next_cid+'"]')).to_have_attribute('aria-selected','true')
                check(True,'Re-entering Home defaults to the actual next competition')
                page.get_by_role('button',name='Calendar',exact=True).click();page.locator('[data-cal-club]').first.wait_for()
                cid=page.locator('[data-cal-club]').first.get_attribute('data-cal-club')
                page.locator('[data-cal-club]').first.click();page.wait_for_url('**/#club/'+cid)
                check(True,'Calendar opponent link opens the correct club')
                # Responsive profile read-only table and native SVG still work.
                page.set_viewport_size({'width':1100,'height':850})
                cf=page.frame_locator('#fm-club-frame');cf.locator('[data-roster-expand]').first.wait_for();cf.locator('[data-roster-expand]').first.click();cf.locator('.ts22-radar').first.wait_for()
                check(cf.locator('.ts22-radar').count()==2,'Profile radars work at a smaller viewport')
                check(not js_errors,'No browser JavaScript exceptions')
                check(not failed_requests,'No failing application HTTP requests')
                browser.close()
        finally:
            server.shutdown();server.server_close();thread.join(timeout=5)
            args.output.parent.mkdir(parents=True,exist_ok=True)
            args.output.write_text(json.dumps({'checks':results,'passed':sum(r['passed'] for r in results),'javascript_errors':js_errors,'failed_requests':failed_requests},indent=2),encoding='utf-8')
    print(f"{len(results)} browser checks passed")


if __name__=='__main__':
    main()
