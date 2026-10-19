/* An explicit maintenance operation, never a silent save/load migration. */
window.FMOpeningBalance=(()=>{
 'use strict';
 let pending=false;
 async function mount(root,reload){
  if(pending)return;
  try{
   const r=await fetch('/api/balance',{cache:'no-store'});if(!r.ok)return;const p=await r.json();
   root.querySelector('.ts22-balance')?.remove();if(!p.eligible||p.applied)return;
   const el=document.createElement('div');el.className='ts22-balance';
   const text=document.createElement('span');text.textContent=`Optional Northbridge opening balance: ${p.count} unchanged original players. Existing results, transfers and fatigue are preserved.`;
   const button=document.createElement('button');button.type='button';button.textContent='Review and apply';el.append(text,button);root.prepend(el);
   button.addEventListener('click',async()=>{
    if(pending||!confirm(`${p.description}\n\nPlayers: ${p.players.map(x=>x.name).join(', ')}\n\nApply this one-time change to this session? Keep a backup save first.`))return;
    pending=true;button.disabled=true;
    try{
     const res=await fetch('/api/balance',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({confirmation:p.id})});const result=await res.json();if(!res.ok)throw Error(result.error);
     await reload();alert('Opening balance applied. Save your career to retain it.');
    }catch(err){text.textContent='Not applied: '+err.message;button.disabled=false;}
    finally{pending=false;}
   });
  }catch(_){/* Optional balance notice must not block roster navigation. */}
 }
 return {mount};
})();
