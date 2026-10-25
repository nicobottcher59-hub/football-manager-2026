const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const assert=require('node:assert/strict');
const brandScript=fs.readFileSync(path.join(__dirname,'../../frontend/portable/competition_branding.js'),'utf8');
const context={window:Object.create(null)};
vm.createContext(context);
vm.runInContext(brandScript,context);
const b=context.window.FMCompetitionBranding;
const known={
  'dev-premier':'#c18bf6',
  'fa-cup':'#f46a78',
  'carabao-cup':'#35d49d',
  'champions-league':'#638eff',
  'dev-championship':'#77b8ed',
  'dev-league-one':'#e8ab70',
  'dev-league-two':'#76d4b7',
  'efl-trophy':'#dd90cd',
  'europa-league':'#f4a455',
  'conference-league':'#8ad97b',
};
for(const [id,hex] of Object.entries(known)){
  assert.equal(b.resolve(id).accent,hex);
  assert.match(b.vars(id),new RegExp('^--ci-accent:'+hex+';','i'));
}
assert.equal(new Set(Object.keys(known).map(id=>b.resolve(id).accent)).size,10);
assert.match(b.badge('dev-championship','ci-title-logo ci-full-logo'),/ci-generic-logo/);
context.window.FMEntityAssets={
  getCompetitionTheme:id=>id==='dev-championship'?{
    logo:'assets/imported/competitions/dev-championship.png',primary_color:'#1a83bd',secondary_color:'#1f3555'}:null,
  getCompetition:id=>id==='dev-championship'?'assets/imported/competitions/dev-championship.png':null,
  url:path=>'/portable/'+path,
};
const rec=b.resolve('dev-championship');
assert.equal(rec.accent,'#1a83bd');
assert.equal(rec.shade,'#1f3555');
assert.match(b.badge('dev-championship','ci-title-logo ci-full-logo'),/dev-championship\.png/);
assert.match(b.badge('dev-championship','ci-title-logo ci-full-logo'),/ci-full-logo/);
context.window.FMEntityAssets.getCompetitionTheme=()=>({primary_color:'red\');alert(1);',secondary_color:'url(evil)'});
context.window.FMEntityAssets.getCompetition=()=>null;
assert.equal(b.resolve('dev-championship').accent,'#77b8ed');
assert.equal(b.resolve('dev-championship').shade,'#14344e');
assert.doesNotMatch(b.vars('dev-championship'),/evil|alert/);
assert.equal(b.resolve('unrecognized-new-league').key,'neutral');
console.log('TS-UI-14: ten ID palettes, future PNG, import colour, fallback and injection controls passed');
