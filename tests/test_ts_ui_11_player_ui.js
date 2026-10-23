'use strict';
const assert=require('assert');const fs=require('fs');const vm=require('vm');const path=require('path');
const root=path.resolve(__dirname,'..','frontend','portable');
const fake = {
  schema_version:1,
  categories:[
    {id:'league-player',category:'player',label:'League Player of the Season',image:'league-player-season.png',group_by_scope:false},
    {id:'league-scorer',category:'goals',label:'League Top Scorer',image:'league-top-scorer.png',group_by_scope:false},
    {id:'ballon-dor',category:'world_player',label:"Ballon d'Or",image:'ballon-dor.png'},
    {id:'puskas',category:'puskas',label:'Puskas Award',image:'puskas.png'}
  ]
};
const honours=JSON.parse(fs.readFileSync(path.join(root,'data/honour-competitions.json'),'utf8'));
const api={
 FMClubIdentity:{resolve:(id,name)=>({display_name:name,short_name:'FC',crest:null,primary_color:'#a22255'}),theme:()=>({primary:'#a22255',highlight:'#ce5577'}),fallbackColour:()=> '#223344'},
 FMEntityAssets:{getPhoto:()=>null,url:()=>null},
 FMPortraits:{portrait:()=>'<span class="portrait">Photo</span>'},
 FMNationFlags:{render:()=>'<span>Flag</span>'}
};
const sandbox={window:api,console,fetch:async u=>({ok:true,json:async()=>u.includes('individual-awards')?fake:honours})};
vm.createContext(sandbox);vm.runInContext(fs.readFileSync(path.join(root,'player_career.js'),'utf8'),sandbox);
const fm=api.FMPlayerCareer;
const base={id:'p1',name:'Test Player',position:'ST',age:27,nationality:'England',birth_date:'1999-01-01',preferred_foot:'right',current_club_id:'club-a',current_club:'Club A',status:'active',progression:[{overall:78,date:'2026-07-01',season:'2026/27',indicators:{}}],
 seasons:[{season:'2026/27',clubs:[{id:'club-a',name:'Club A'}],statistics:{appearances:7,goals:3,assists:2,average_match_rating:7.2},coverage:{complete_season:true},competitions:[]}],
 honours:[],awards:[],transfers:[],loans:[]};
(async()=>{
 await fm.load();
 const blank=fm.render(base);
 assert(blank.includes('No team honours earned yet.'));
 assert(blank.includes('No individual awards earned yet.'));
 assert(!blank.includes('Ballon d\'Or</span>'));
 const played={...base,honours:[{season:'2026/27',competition_id:'fa-cup',competition:'FA Cup',club_id:'club-a',club:'Club A'}],
  awards:[{season:'2026/27',category:'goals',competition_id:'dev-premier',competition:'Premier League'}]};
 const filled=fm.render(played);
 assert(filled.includes('fa-cup.png'));
 assert(filled.includes('league-top-scorer.png'));
 assert(!filled.includes('community-shield.png'));
 assert(!filled.includes('Ballon d\'Or</span>'));
 const foreign={...base,honours:[{season:'2026/27',competition_id:'la-liga',competition:'La Liga',club_id:'club-a',club:'Club A'}]};
 assert(fm.render(foreign).includes('La Liga'));
 const seeded={honours:[...played.honours],awards:[...played.awards]};
 assert.equal(fm.overlay(played,seeded).honours.length,1);
 assert.equal(fm.overlay(played,seeded).awards.length,1);
 assert(fm.render({...base,name:'<img src=x onerror=alert(1)>',honours:[]}).includes('&lt;img'));
 assert(fm.categoryFor('fa-cup').image==='fa-cup.png');
 assert(fm.categoryFor('community-shield').image==='community-shield.png');
 assert(fm.categoryFor('efl-trophy').image==='efl-trophy.png');
 assert(fm.render({...base,awards:[{season:'2027/28',category:'puskas',competition_id:'world'}]}).includes('puskas.png'));
 console.log('TS-UI-11 frontend: 11 assertions passed');
})().catch(err=>{console.error(err);process.exit(1)});
