"""Isolated browser smoke test of real TS-28.3/28.4 read models."""
from pathlib import Path
from playwright.sync_api import sync_playwright
from football_manager.dev_ui.session import DevelopmentSession
from football_manager.ui_shell.career_history import (club_career_read_model,
    player_career_read_model,competition_career_read_model)

ui=Path(__file__).resolve().parents[1]/'frontend/portable'
session=DevelopmentSession()
club=club_career_read_model(session,session.home_club.id)
player=player_career_read_model(session,session.home_club.squad.players[0].id)
competition=competition_career_read_model(session,'dev-premier')
with sync_playwright() as pw:
    browser=pw.chromium.launch(headless=True,executable_path='/usr/bin/chromium',
                               args=['--no-sandbox','--disable-gpu','--disable-dev-shm-usage'])
    page=browser.new_page(viewport={'width':1280,'height':850})
    errors=[]
    page.on('pageerror',lambda err:errors.append(str(err)))
    page.set_content('<!doctype html><html><head><style>body{background:#071a2b;color:#fff;margin:35px;font-family:Arial}</style></head><body><section id="history"></section></body></html>')
    page.add_style_tag(content=(ui/'history.css').read_text())
    page.evaluate('''fixtures=>{window.fixtures=fixtures;window.fetch=async url=>({ok:true,json:async()=>url.includes('/club/')?window.fixtures.club:url.includes('/competition/')?window.fixtures.competition:window.fixtures.player});window.FMNavigation={back:()=>{},club:()=>{},competition:()=>{}};}''',
                  {'club':club,'player':player,'competition':competition})
    page.add_script_tag(content=(ui/'history.js').read_text())
    host='#history'
    page.evaluate("id=>FMHistory.mount(document.querySelector('#history'),'club',id)",club['id'])
    page.get_by_text('Club identity',exact=True).wait_for(timeout=12000)
    text=page.locator(host).inner_text()
    for label in ('Club identity','Finances','Facilities and staff','Historical records','Individual awards','Current leading players'):
        assert label in text, label
    print('CLUB RENDERED:',text[:300].replace('\n',' / '))
    page.evaluate("id=>FMHistory.mount(document.querySelector('#history'),'player',id)",player['id'])
    page.get_by_text('Player development',exact=True).wait_for(timeout=12000)
    assert page.locator('.ch-graph circle').count()>=1
    page.locator('select[data-history-metric]').select_option('Pace')
    assert page.locator('select[data-history-metric]').input_value()=='Pace'
    assert page.get_by_text('Player development',exact=True).count()==1
    print('PLAYER RENDERED:',page.locator(host).inner_text()[:230].replace('\n',' / '))
    page.evaluate("id=>FMHistory.mount(document.querySelector('#history'),'competition',id)",competition['id'])
    page.get_by_text('Historical records',exact=True).wait_for(timeout=12000)
    assert page.get_by_text('Individual awards',exact=True).count()==1
    assert page.get_by_text('Past champions',exact=True).count()==1
    print('COMPETITION RENDERED:',page.locator(host).inner_text()[:190].replace('\n',' / '))
    print('JS ERRORS',errors)
    assert not errors
    browser.close()
