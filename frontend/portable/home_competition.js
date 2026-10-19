/* TS-22: Home tabs are local card selection, never navigation side effects. */
window.FMHomeCompetition=(()=>{
 'use strict';
 let selected=null,serial=0;
 const h=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
 const club=(id,name)=>`<button type="button" class="ts22-club-link" data-club-id="${h(id)}">${h(name)}</button>`;
 function table(rows){
  const me=rows.findIndex(r=>r.managed);let start=me<6?0:Math.max(0,me-3);
  const indices=new Set([...Array(Math.min(2,rows.length)).keys(),...rows.map((_,i)=>i).slice(start,start+7)]);
  let previous=-1;
  return '<div class="league-row league-header"><span>POS</span><span>TEAM</span><span>P</span><span>W</span><span>D</span><span>L</span><span>GD</span><span>PTS</span></div>'+[...indices].sort((a,b)=>a-b).map(i=>{
   const r=rows[i],gap=i>previous+1?'<div class="league-ellipsis">...</div>':'';previous=i;
   return `${gap}<div class="league-row ${r.managed?'is-managed':''}"><span>${r.position}</span><span class="row-club">${club(r.club_id,r.club)}</span><span>${r.played}</span><span>${r.won}</span><span>${r.drawn}</span><span>${r.lost}</span><span>${r.gd}</span><strong>${r.points}</strong></div>`;
  }).join('');
 }
 function tie(t){
  if(!t)return '';
  return `<section class="ts22-home-tie"><small>${h(t.round)}</small><div class="ts22-tie-teams">${club(t.club_a_id,t.club_a)}<b>${t.aggregate?`${t.aggregate.a} - ${t.aggregate.b}`:'VS'}</b>${club(t.club_b_id,t.club_b)}</div>${t.legs.map(m=>`<div class="ts22-leg"><span>${h(m.date||'Date pending')} ${t.legs.length>1?'Leg '+m.leg:''}</span><span>${m.score?`${m.score.home} - ${m.score.away}`:'Scheduled'}${m.penalties?` (pens ${m.penalties.home}-${m.penalties.away})`:''}</span><small>${club(m.home_id,m.home)} (H)</small></div>`).join('')}${t.legs.length>1?'<small>Aggregate above; each leg shown separately.</small>':''}</section>`;
 }
 async function refresh(){
  const card=document.querySelector('.league-card');if(!card)return;
  const mine=++serial,panel=card.querySelector('#competition-panel');
  try{
   const response=await fetch('/api/home-competition'+(selected?'?id='+encodeURIComponent(selected):''),{cache:'no-store'});
   if(!response.ok){if(response.status===404&&selected){selected=null;return refresh();}throw Error('Competition summary unavailable');}
   const data=await response.json();if(mine!==serial)return;
   selected=data.id;
   card.querySelector('#league-title').textContent=data.mode==='table'?'League Table':'Cup Progress';
   card.querySelector('.card-kicker').textContent=data.phase||data.name;
   card.querySelector('.competition-tabs').innerHTML=data.options.map(c=>`<button type="button" role="tab" id="home-tab-${h(c.id)}" class="competition-tab ${c.id===selected?'selected':''}" aria-controls="competition-panel" aria-selected="${c.id===selected}" data-home-competition="${h(c.id)}">${h(c.name)}</button>`).join('');
   panel.setAttribute('aria-labelledby','home-tab-'+selected);
   panel.innerHTML=data.mode==='table'?table(data.table)+(data.status?`<p class="ts22-home-status">${h(data.status)}</p>`:''):`<div class="ts22-home-cup"><strong>${h(data.status||'Competition progress')}</strong>${tie(data.tie)}${data.next_tie?'<h4>Next opponent comes from</h4>'+tie(data.next_tie):data.next_status?`<p class="ts22-home-status">${h(data.next_status)}</p>`:''}</div>`;
   panel.insertAdjacentHTML('beforeend',`<div class="table-note"><button type="button" class="ts22-club-link" data-home-full="${h(selected)}">View competition \u2192</button></div>`);
  }catch(err){if(mine===serial)panel.innerHTML=`<p class="ts22-home-status">${h(err.message)}. <button type="button" data-home-retry>Retry</button></p>`;}
 }
 document.addEventListener('click',e=>{
  const tab=e.target.closest('[data-home-competition]');if(tab){selected=tab.dataset.homeCompetition;refresh();return;}
  const full=e.target.closest('[data-home-full]');if(full){window.FMNavigation?.competition(full.dataset.homeFull);return;}
  if(e.target.closest('[data-home-retry]'))refresh();
 });
 return {refresh,reset:()=>{selected=null;serial++;},selected:()=>selected};
})();
