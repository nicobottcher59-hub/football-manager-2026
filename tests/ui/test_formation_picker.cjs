/* Headless DOM-independent test of the formation-picker lifecycle.
 * Uses the real Python squad JSON, mocked browser events and API responses.
 */
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const path=require('node:path');
const snapshots=JSON.parse(fs.readFileSync(process.argv[2],'utf8'));
const byId=new Map(snapshots.map(view=>[view.formation.id,view]));
let live=snapshots[0],commands=[];
const listeners={}, windowListeners={};
const classList={add(){},remove(){},toggle(){}};
let redrawHtml='';
const fakeDialog={set outerHTML(value){redrawHtml=value;}};
const root={innerHTML:'',classList,addEventListener(name,handler){listeners[name]=handler;},
 querySelector(q){return q==='#fm-formation-dialog'?fakeDialog:null;},querySelectorAll(){return [];}};
const notice={textContent:'',classList};
const document={getElementById(id){return id==='squad-root'?root:notice;},activeElement:null};
const location={search:'?view=tactics',origin:'http://local.invalid',href:'http://local.invalid/?view=tactics'};
const window={location,FMRoster:{format:x=>Number(x).toFixed(1)},FMTacticalBoard:{place:(view)=>Object.fromEntries(view.slots.map(s=>[s.slot_id,{x:s.base_x,y:s.base_y}]))},
 FMPortraits:{portrait:()=>'<span>portrait</span>'},addEventListener(name,cb){windowListeners[name]=cb;}};
const scope={window,parent:window,document,location,history:{replaceState(){}},URL,URLSearchParams,
 requestAnimationFrame(){},setTimeout(){return 1;},clearTimeout(){},fetch:async(url,options)=>{
   if(options?.method==='POST'){
     const payload=JSON.parse(options.body);commands.push(payload);
     assert.equal(payload.action,'formation');
     live=byId.get(payload.id);
     assert(live,'chosen formation must exist in Python');
   }
   return {ok:true,json:async()=>live};
 }};
vm.runInNewContext(fs.readFileSync(path.resolve(__dirname,'../../frontend/public/squad/squad.js'),'utf8'),scope);
function click(dataset){return listeners.click({target:{closest:q=>q==='button'?{dataset}:null}});}
function ticks(){return new Promise(resolve=>setImmediate(resolve));}
(async()=>{
 await ticks();
 assert(root.innerHTML.includes('Choose formation'),'new picker trigger renders');
 assert(!root.innerHTML.includes('data-change="formation"'),'legacy dropdown removed');
 click({action:'open-formations'});
 assert(root.innerHTML.includes('role="dialog"'),'modal opens');
 assert.equal((root.innerHTML.match(/data-formation-pick=/g)||[]).length,28,'28 selectable previews');
 assert.equal(commands.length,0,'opening must not change game');
 click({formationPick:'dev-5-2-2-1'});
 assert(redrawHtml.includes('5-2-2-1 (2 Central AM)'),'candidate details update in dialog');
 assert.equal(commands.length,0,'choosing preview must not change game');
 click({action:'close-formations'});
 assert.equal(commands.length,0,'cancel preserves game state');
 click({action:'open-formations'});
 click({formationPick:'dev-5-2-2-1'});
 await click({action:'apply-formation'});
 assert.equal(commands.length,1,'exactly one command when confirming');
 assert.equal(live.formation.id,'dev-5-2-2-1');
 assert(!root.innerHTML.includes('role="dialog"'),'picker closes after success');
 assert(root.innerHTML.includes('5-2-2-1 (2 Central AM)'));
 console.log('TS-19.1.1 picker: 28 previews, cancel without changes, confirmed-only commit: OK');
})().catch(error=>{console.error(error);process.exitCode=1;});
