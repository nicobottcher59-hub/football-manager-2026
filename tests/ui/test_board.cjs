/* Test without Node modules or frontend dependencies: node board.test.cjs */
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const scope={module:{exports:{}},window:{}};
vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../../frontend/public/squad/board.js'),'utf8'),scope);
const {place}=scope.module.exports;
const formation=[
 ['gk','GK'],['rb','RB'],['rcb','RCB'],['lcb','LCB'],['lb','LB'],['dm','DM'],['rcm','RCM'],['lcm','LCM'],['rw','RW'],['st','ST'],['lw','LW']
];
const levels=['very_low','low','normal','high','very_high'];
function data(){
 return {slots:formation.map(([slot_id,position])=>({slot_id,position,individual:[]})),tactics:{fields:[
 ...['in_possession','out_of_possession'].flatMap(group=>['defensive_line_width','midfield_width','attacking_line_width','defense_midfield_gap','midfield_attack_gap'].map(field=>({group,field,value:'normal'}))),
 ...['block_height','defensive_line_height','pressing_intensity','horizontal_compactness','vertical_compactness'].map(field=>({group:'out_of_possession',field,value:'normal'}))
 ]}};
}
let state=data();
const original=place(state,'in_possession');
const wide=state.tactics.fields.find(x=>x.group==='in_possession'&&x.field==='attacking_line_width');
wide.value='very_high';
const open=place(state,'in_possession');
assert(open.lw.x<original.lw.x,'left winger opens wider when width increases');
assert(open.rw.x>original.rw.x,'right winger opens wider when width increases');
assert.equal(Object.keys(original).length,11);
const oppBefore=place(state,'out_of_possession');
state.tactics.fields.find(x=>x.group==='out_of_possession'&&x.field==='block_height').value='very_high';
const oppAfter=place(state,'out_of_possession');
assert(oppAfter.lcm.y<oppBefore.lcm.y,'out of possession shape moves when block height increases');
assert.deepEqual(original.gk,open.gk,'width setting does not move goalkeeper');
for(const p of Object.values(oppAfter)){assert(p.x>=5&&p.x<=95&&p.y>=5&&p.y<=95);}
const html=fs.readFileSync(path.join(__dirname,'../../frontend/public/squad/embed.html'),'utf8');
assert.equal((html.match(/data-phase=/g)||[]).length,0,'phase toggle exists only in the mounted toolbar');
const js=fs.readFileSync(path.join(__dirname,'../../frontend/public/squad/squad.js'),'utf8');
assert.equal((js.match(/fm-segment/g)||[]).length,1,'only one possessive-phase toggle markup');
console.log('Board tests: width, defensive block, no duplicate phase toggle, boundaries: OK');
