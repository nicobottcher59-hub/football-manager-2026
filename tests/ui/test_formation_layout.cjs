/* node tests/ui/test_formation_layout.cjs <Python catalogue snapshot JSON>
 * Simulate 28 formations, both phases, desktop/mobile widths and tactical extremes.
 * No browser modules or match-engine changes required.
 */
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const root=path.resolve(__dirname,'../..');
function load(relative){
  const scope={module:{exports:{}},window:{}};
  vm.runInNewContext(fs.readFileSync(path.join(root,relative),'utf8'),scope);
  return scope.module.exports;
}
const {arrange}=load('frontend/public/squad/formation_layout.js');
const {place}=load('frontend/public/squad/board.js');
const fixtures=JSON.parse(fs.readFileSync(process.argv[2],'utf8'));
const sizes=[{width:620,height:670,cardWidth:106,cardHeight:100},
 {width:700,height:670,cardWidth:106,cardHeight:100},
 {width:850,height:720,cardWidth:106,cardHeight:100},
 {width:510,height:595,cardWidth:88,cardHeight:90}];
let checked=0;
function verify(entry, phase, size){
  const output=arrange(place(entry,phase),entry.slots,size);
  assert.equal(Object.keys(output).length,11,'11 positions: '+entry.formation.name);
  for(const [i,a] of entry.slots.entries()){
    const p=output[a.slot_id];
    assert(p.x>=size.cardWidth/2-1 && p.x<=size.width-size.cardWidth/2+1,'horizontal bound '+entry.formation.name+' '+a.slot_id);
    assert(p.y>=size.cardHeight/2-1 && p.y<=size.height-size.cardHeight/2+1,'vertical bound '+entry.formation.name+' '+a.slot_id);
    for(const b of entry.slots.slice(i+1)){
      const q=output[b.slot_id];
      const dx=Math.abs(p.x-q.x),dy=Math.abs(p.y-q.y);
      assert(dx>=size.cardWidth+5 || dy>=size.cardHeight+5,
        `collision in ${entry.formation.name} (${phase}, ${size.width}x${size.height}): ${a.slot_id}/${b.slot_id} distance ${dx.toFixed(1)},${dy.toFixed(1)}`);
    }
  }
  checked++;
}
const levels=['very_low','low','normal','high','very_high'];
for(const entry of fixtures){
 for(let scenario=0;scenario<5;scenario++){
  // Scenario 0 keeps the original instructions; remaining scenarios exercise
  // extremes and asymmetric mixes of existing level-based instruction fields.
  const varied=scenario===0?entry:{...entry,tactics:{...entry.tactics,fields:entry.tactics.fields.map((f,i)=>{
    const value=(f.options||[]).includes('very_high')&& (f.options||[]).includes('very_low')?
      levels[(scenario+i*3)%levels.length]:f.value;
    return {...f,value};
  })}};
  for(const phase of ['in_possession','out_of_possession'])for(const size of sizes){
    verify(varied,phase,size);
  }
 }
}
assert.equal(checked,fixtures.length*2*sizes.length*5);
console.log(`TS-19.1.1 board geometry: ${checked} pitch sizes/phases/scenarios, all ${fixtures.length} formations, no overlaps or clipping`);
