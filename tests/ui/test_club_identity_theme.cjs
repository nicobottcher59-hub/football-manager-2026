const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const root=path.join(__dirname,'../../frontend/portable');
const catalog=JSON.parse(fs.readFileSync(path.join(root,'data/club-identities.json'),'utf8'));
const custom=structuredClone(catalog);
custom.clubs['blue-test']={display_name:'Blue Example',primary_color:'#123fa4',accent_color:'#ced4eb'};
custom.clubs['light-test']={display_name:'White Example',primary_color:'#ffffff',accent_color:'#e7d59a'};
custom.clubs['bad-test']={display_name:'Injected',primary_color:'red; background:evil',accent_color:'url(evil)'};
const properties=new Map();
const context={
  window:{dispatchEvent:()=>{}},
  document:{documentElement:{dataset:{},style:{setProperty:(name,value)=>properties.set(name,value)}},querySelector:()=>null},
  fetch:()=>Promise.resolve({ok:true,json:()=>Promise.resolve(custom)}),
  CustomEvent:class CustomEvent {constructor(name){this.type=name}},
  console,
};
vm.createContext(context);
vm.runInContext(fs.readFileSync(path.join(root,'club_identity.js'),'utf8'),context);
(async()=>{
  const module=context.window.FMClubIdentity;
  await module.ready;
  assert.equal(module.resolve('northbridge').display_name,'Sunderland AFC');
  module.applyShell('northbridge','Northbridge FC');
  const red=properties.get('--ui-club-rgb');
  assert.equal(red,'199,40,56');
  assert.match(properties.get('--ui-club-highlight'),/^#[0-9a-f]{6}$/);
  module.applyShell('blue-test','Other club');
  const blue=properties.get('--ui-club-rgb');
  assert.notEqual(red,blue);
  assert.equal(blue,'18,63,164');
  module.applyShell('unknown','Unknown United');
  assert.equal(module.resolve('unknown','Unknown United').display_name,'Unknown United');
  assert.equal(properties.get('--ui-club-rgb'),'20,135,216');
  module.applyShell('light-test','White Example');
  assert.equal(properties.get('--ui-club-rgb'),'255,255,255');
  module.applyShell('bad-test','Injected');
  assert.equal(properties.get('--ui-club-rgb'),'20,135,216');
  for(const val of properties.values()) assert.doesNotMatch(val,/url\(|evil|;|\{/i);
  console.log('Club themes: independent colours, safe fallback and no Sunderland hardcoding — PASS');
})().catch(e=>{console.error(e);process.exitCode=1});
