'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const portable = path.resolve(__dirname,'../frontend/portable');
const catalog = JSON.parse(fs.readFileSync(path.join(portable,'data/honour-competitions.json'),'utf8'));
const context={window:{},fetch:async (url)=>({ok:true,json:async()=>catalog})};
vm.createContext(context);
vm.runInContext(fs.readFileSync(path.join(portable,'club_honours.js'),'utf8'),context);
const h=context.window.FMClubHonours;
(async()=>{
 await h.load();
 const d={institution:{country:'England'},trophies:[
  {id:'dev-premier',name:'Premier League',season:'2027/28'},
  {id:'dev-championship',name:'Championship',season:'2028/29'},
  {id:'fa-cup',name:'FA Cup',season:'2028/29'},
  {id:'champions-league',name:'UEFA Champions League',season:'2031/32'},
  {id:'intercontinental-cup',name:'Intercontinental Cup',season:'2032/33'},
 ],live:{competitions:[{id:'dev-premier',name:'Premier League'}]}};
 const seed={country:'England',honours:[
  {competition_id:'dev-premier',competition:'Premier League',total:2,seasons:['1901','1923']},
  {competition_id:'dev-league-one',competition:'League One',seasons:['1968']},
  {competition_id:'europa-league',competition:'Europa League',total:1},
 ]};
 const rows=h.summarise(d,seed,catalog);
 const get=id=>rows.find(x=>x.id===id)?.count;
 assert.equal(get('eng-leagues-all'),5,'Premier + Championship + League One + history');
 assert.equal(get('eng-lower'),2,'lower division subset of English leagues');
 assert.equal(get('eng-fa-cup'),1);
 assert.equal(get('uefa-champions'),1);
 assert.equal(get('uefa-europa'),1);
 assert.equal(get('club-world-titles'),1);
 assert.equal(get('eng-carabao'),0);
 assert.ok(h.render(d,seed).includes('/portable/assets/trophies/fa-cup.png'));
 assert.ok(h.render(d,seed).includes('data-ci-trophy-scroll'));
 assert.ok(h.render(d,seed).includes('data-ci-trophy-direction'));
 const spanish={institution:{country:'Spain'},live:{competitions:[{id:'la-liga',name:'La Liga'}]},trophies:[{id:'copa-del-rey',name:'Copa del Rey',season:'2028/29'}]};
 const sp=h.summarise(spanish,{},catalog);
 assert.ok(!sp.some(x=>x.id==='eng-fa-cup'),'foreign club must not see England-specific awards');
 assert.ok(sp.some(x=>x.label==='La Liga'),'unknown domestic league populated from live data');
 assert.equal(sp.find(x=>x.label==='Copa del Rey').count,1,'foreign cup is not dropped');
 assert.ok(sp.some(x=>x.id==='uefa-champions'),'UEFA competition included for Spain');
 const argentina={institution:{country:'Argentina'},live:{competitions:[{id:'arg-primera',name:'Liga Profesional'}]},trophies:[{id:'arg-primera',name:'Liga Profesional',season:'2032/33'}]};
 const ar=h.summarise(argentina,{},catalog);
 assert.equal(ar.find(x=>x.label==='Liga Profesional').count,1);
 assert.ok(!ar.some(x=>x.id==='uefa-champions'),'non-European club must not display UEFA catalogue');
 const empty=h.summarise({institution:{country:'England'},trophies:[]},{},catalog);
 assert.equal(empty.find(x=>x.id==='eng-leagues-all').count,0);
 const unknown=h.summarise({institution:{country:'England'},trophies:[{id:'new-domestic-cup',name:'Future National Cup',season:'2027/28'}]}, {}, catalog);
 assert.equal(unknown.find(x=>x.label==='Future National Cup').count,1);
 const duplicate=h.summarise({institution:{country:'England'},trophies:[
  {id:'dev-premier',name:'Premier League',season:'2027/28'},
  {id:'dev-premier',name:'Premier League',season:'2027/28'}]}, {},catalog);
 assert.equal(duplicate.find(x=>x.id==='eng-leagues-all').count,1,'duplicate ledger rows not double-counted');
 console.log('PASS 16 assertions for TS-UI-10.01 (catalogue, historic and career counts, world titles, countries, unknown competitions, duplicates, scrolling)');
})().catch(e=>{console.error(e);process.exitCode=1});
