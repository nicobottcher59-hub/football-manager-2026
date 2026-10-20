/* TS-22: read-only profile charts. Native SVG, no build, npm or chart library. */
(() => {
 'use strict';
 const h=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
 const fmt=v=>typeof v==='number'&&Number.isFinite(v)?v.toFixed(1):'\u2014';

 const choices=new Map();
 const pendingRequests=new WeakMap();
 function radar(axes,label){
  const n=axes.length,cx=160,cy=138,r=83;
  if(n<3)return '<p>No chart for this role.</p>';
  const point=(i,k)=>{const a=-Math.PI/2+2*Math.PI*i/n;return [cx+Math.cos(a)*r*k,cy+Math.sin(a)*r*k];};
  const points=k=>axes.map((_,i)=>point(i,k).join(',')).join(' ');
  const grid=[.25,.5,.75,1].map(k=>`<polygon points="${points(k)}" class="ts22-radar-grid"/>`).join('');
  const valid=axes.every(a=>typeof a.value==='number'&&Number.isFinite(a.value));
  const polygon=valid?`<polygon points="${axes.map((a,i)=>point(i,Math.max(0,Math.min(100,a.value))/100).join(',')).join(' ')}" class="ts22-radar-area"/>`:'';
  return `<svg class="ts22-radar" viewBox="0 0 320 286" role="img" aria-label="${h(label)}"><title>${h(label)}: ${h(axes.map(a=>a.label+' '+fmt(a.value)).join(', '))}. Scale 0 to 100.</title>${grid}${axes.map((a,i)=>{const [x,y]=point(i,1),[lx,ly]=point(i,1.32);return `<path d="M${cx},${cy} L${x},${y}" class="ts22-radar-grid"/><text x="${lx}" y="${ly-3}" text-anchor="middle">${h(a.label)}</text><text x="${lx}" y="${ly+12}" text-anchor="middle" class="ts22-radar-value">${fmt(a.value)}</text>`;}).join('')}${polygon}</svg>`;
 }
 // TS-UI-02.4: both polygons use the same six engine role axes.
 // Cyan shows the player's recorded 0-100 attributes; coral shows normalized
 // relative role weights. Weight is NOT a minimum rating or hidden potential.
 function roleComparison(graphics, position, positions, chosen){
  const role=graphics.role||{},axes=(role.axes||[]).filter(a=>a.attribute&&a.weight!=null);
  const maxWeight=Math.max(0,...axes.map(a=>Number(a.weight)||0));
  const options=graphics.role_options||[];
  const toolbar=`<div class="s24-comparison-tools"><div><span class="s24-comparison-eyebrow">ROLE ANALYSIS</span><h4>${h(role.name||'Selected role')}</h4></div><div class="s24-comparison-selects"><label>Position <select data-chart-position>${positions.map(v=>`<option value="${h(v)}" ${v===chosen.position?'selected':''}>${h(v)}</option>`).join('')}</select></label><label>Role <select data-chart-role>${options.map(r=>`<option value="${h(r.id)}" ${r.id===role.id?'selected':''}>${h(r.name)}</option>`).join('')}</select></label></div></div>`;
  if(axes.length<3 || !maxWeight)return `${toolbar}<div class="s24-chart-empty">Comparison unavailable for this role.</div>`;
  const cx=305,cy=178,r=117,n=axes.length;
  const point=(i,k)=>{const angle=-Math.PI/2+2*Math.PI*i/n;return [cx+Math.cos(angle)*r*k,cy+Math.sin(angle)*r*k];};
  const poly=(values)=>values.map((value,i)=>point(i,Math.max(0,Math.min(100,Number(value)||0))/100).join(',')).join(' ');
  const roleValues=axes.map(axis=>Math.max(0,(Number(axis.weight)||0)/maxWeight*100));
  const playerValues=axes.map(axis=>axis.value);
  const playerKnown=playerValues.every(v=>typeof v==='number'&&Number.isFinite(v));
  const rings=[.25,.5,.75,1].map(k=>`<polygon class="s24-radar-ring" points="${axes.map((_,i)=>point(i,k).join(',')).join(' ')}"/>`).join('');
  const rays=axes.map((axis,i)=>{
   const [x,y]=point(i,1),[lx,ly]=point(i,1.34);
   const align=lx>cx+8?'start':lx<cx-8?'end':'middle';
   const offset=align==='start'?6:align==='end'?-6:0;
   return `<path class="s24-radar-ray" d="M${cx},${cy}L${x},${y}"/><text x="${lx+offset}" y="${ly}" text-anchor="${align}" dominant-baseline="middle">${h(axis.label)}</text>`;
  }).join('');
  const roleShape=`<polygon class="s24-radar-emphasis" points="${poly(roleValues)}"/>`;
  const playerShape=playerKnown?`<polygon class="s24-radar-player" points="${poly(playerValues)}"/>${axes.map((axis,i)=>{const [x,y]=point(i,playerValues[i]/100);return `<circle class="s24-radar-node" cx="${x}" cy="${y}" r="3.4"/>`;}).join('')}`:'';
  const dataRows=axes.map(axis=>`<div class="s24-chart-key-row"><span>${h(axis.label)}</span><strong>${fmt(axis.value)}</strong></div>`).join('');
  return `${toolbar}<div class="s24-comparison-body"><div class="s24-chart-canvas"><svg class="s24-comparison-radar" viewBox="0 0 610 350" role="img" aria-label="Player ability and relative role weight on the same six selected attributes"><title>Ability values use the 0 to 100 player scale. Role emphasis is the relative weight of attributes in this role, normalized to 100; not a required rating.</title><g>${rings}${rays}</g>${roleShape}${playerShape}</svg></div><div class="s24-comparison-side"><div class="s24-radar-legend"><div><span class="s24-legend-player"></span>Player ability</div><div><span class="s24-legend-role"></span>Role emphasis <span class="s24-help" tabindex="0" title="Role importance is normalized from the engine's attribute weights. It is NOT a required skill level or potential.">i</span></div></div><div class="s24-chart-key-list">${dataRows}</div></div></div>`;
 }
 function developmentPanel(d,readonly){
  if(!d?.registered)return `<p class="ts22-history-note">${h(d?.message||'Development not registered.')}</p>`;
  const changes=Object.entries(d.last_changes||{});
  const delta=d.reference_ovr_delta;
  return `<section class="ts212-development"><div class="ts22-chart-head"><strong>Player development</strong><span>Born ${h(d.birth_date)} \u00b7 Age ${d.age}</span></div>
   <p>${h(d.message)}</p>${d.career?.message?`<p>${h(d.career.message)}</p>`:''}${d.career?.injury?`<p>${h(d.career.injury.description)} · Return: ${h(d.career.injury.return_on||'Unknown (legacy injury)')}</p>`:''}<div class="ts212-development-facts"><span>Tracked since <b>${h(d.tracking_since)}</b></span><span>Next review <b>${h(d.next_review)}</b></span><span>Minutes this period <b>${d.period_minutes}</b></span><span>Last reference OVR change <b>${delta==null?'Pending':(delta>0?'+':'')+fmt(delta)}</b></span></div>
   <p class="ts212-changes">${changes.length?changes.map(([k,v])=>`${h(k.replaceAll('_',' ').replace('.',' / '))} <b>${v>0?'+':''}${v}</b>`).join(' \u00b7 '):'No whole attribute changes recorded in the latest review.'}</p>
   <label>Development focus <select data-development-focus ${readonly?'disabled':''}>${d.focus_options.map(f=>`<option value="${h(f)}" ${f===d.focus?'selected':''}>${h(f.charAt(0).toUpperCase()+f.slice(1))}</option>`).join('')}</select></label><span data-development-status role="status">${readonly?'Read-only rival profile.':'Training emphasis for the next monthly review. Exact potential remains hidden.'}</span>
   ${d.history.length?`<details><summary>Recorded monthly progress</summary><table><thead><tr><th>Review</th><th>Reference OVR</th><th>Minutes</th></tr></thead><tbody>${d.history.map(r=>`<tr><td>${h(r.date)}</td><td>${fmt(r.reference_ovr)}</td><td>${r.minutes}</td></tr>`).join('')}</tbody></table></details>`:''}
   ${d.annual_history?.length?`<details><summary>Annual history</summary><table><tbody>${d.annual_history.map(r=>`<tr><td>${h(r.date)}</td><td>${fmt(r.reference_ovr)}</td></tr>`).join('')}</tbody></table></details>`:''}
   <p class="rt-fam-hint">${h(d.note)}</p></section>`;
 }
 async function hydrate(container,data){
  const el=container.querySelector('[data-player-graphics]');
  if(!el)return;
  const request=(pendingRequests.get(el)||0)+1;pendingRequests.set(el,request);
  const p=data.roster.find(p=>p.id===el.dataset.playerGraphics);if(!p)return;
  const ck=data.club_id+':'+p.id;
  const chosen=choices.get(ck)||{position:p.position||p.primary_position,role:p.role_id||''};
  // LM/RM are display aliases, not extra engine positions.
  const pos={LM:'LW',RM:'RW'}[chosen.position]||chosen.position;

  const positions=[...new Set([p.position,p.primary_position,...p.secondary_positions].filter(Boolean))];
  try{
   const q=new URLSearchParams({position:pos});if(chosen.role)q.set('role',chosen.role);
   const res=await fetch(`/api/clubs/${encodeURIComponent(data.club_id)}/players/${encodeURIComponent(p.id)}?${q}`,{cache:'no-store'});
   const result=await res.json();if(!res.ok)throw Error(result.error||'Profile unavailable');
   if(!el.isConnected||pendingRequests.get(el)!==request)return;
   const g=result.graphics;
   const mode=el.dataset.graphicsMode || 'both';
   const charts=`<div class="ts22-chart-head"><strong>Player profile</strong><label>Inspect position <select data-chart-position>${positions.map(v=>`<option value="${h(v)}" ${v===chosen.position?'selected':''}>${h(v)}</option>`).join('')}</select></label><label>Inspect role <select data-chart-role>${g.role_options.map(r=>`<option value="${h(r.id)}" ${r.id===g.role.id?'selected':''}>${h(r.name)}</option>`).join('')}</select></label></div><div class="ts22-charts"><section><h3>Footballing capabilities</h3>${radar(g.general,'General attributes')}</section><section><h3>${h(g.role.name)}</h3>${radar(g.role.axes,'Role attributes')}</section></div><p class="rt-fam-hint">${h(g.note)} Inspecting a role does not change the lineup or tactical assignment.</p><details class="ts22-chart-values"><summary>Chart definitions and attribute values</summary><div>${g.general.map(a=>`<p><b>${h(a.label)}: ${fmt(a.value)}</b><br>${h(a.attributes.join(', '))}</p>`).join('')}${g.role.axes.map(a=>`<p>${h(a.attribute)}: ${fmt(a.value)} (role weight ${a.weight})</p>`).join('')}</div></details>`;
   const evolution=developmentPanel(g.evolution,!!data.readonly);
   const comparison=mode==='comparison'?roleComparison(g,chosen.position,positions,chosen):'';
   el.innerHTML=mode==='comparison'?comparison:mode==='charts'?charts:mode==='development'?evolution:charts+evolution;
   const focus=el.querySelector('[data-development-focus]');
   if(focus&&!data.readonly)focus.addEventListener('change',async()=>{
    focus.disabled=true;const status=el.querySelector('[data-development-status]');
    try{
     const r=await fetch('/api/development/focus',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({player_id:p.id,focus:focus.value})});
     const answer=await r.json();if(!r.ok)throw Error(answer.error||'Focus could not be saved');
     g.evolution.focus=answer.focus;
     status.textContent=`Focus set for review on ${answer.effective_review}. Save your career to retain it.`;
    }catch(err){status.textContent=err.message;focus.value=g.evolution.focus;}
    finally{focus.disabled=false;}
   });
   el.querySelector('[data-chart-position]')?.addEventListener('change',e=>{choices.set(ck,{position:e.target.value,role:''});window.FMSquadUI02?.focusPosition?.(e.target.value);hydrate(container,data);});
   el.querySelector('[data-chart-role]')?.addEventListener('change',e=>{choices.set(ck,{position:chosen.position,role:e.target.value});hydrate(container,data);});
  }catch(err){if(el.isConnected&&pendingRequests.get(el)===request)el.innerHTML=`<p class="rt-muted">${h(err.message)}. Close and reopen this profile to retry.</p>`;}
 }
 function clubHeader(data){
  if(!data.readonly)return '';
  const i=data.information||{},l=i.league;
  const link=(id,name)=>`<button type="button" class="ts22-club-link" data-open-club="${h(id)}">${h(name)}</button>`;
  return `<section class="ts22-club-overview rt-card"><div class="ts22-chart-head"><strong>${h(data.club)}</strong><button type="button" class="ch-link" data-open-club-history="${h(data.club_id)}">Club history ↗</button></div><div class="ts22-club-facts"><span><small>Competition</small><b>${h(l?.name||'Outside active divisions')}</b></span><span><small>Position / points</small><b>${l?`${l.position} / ${l.points}`:'\u2014'}</b></span><span><small>Country</small><b>${h(i.country||'Not recorded')}</b></span><span><small>Location</small><b>${h(i.city||'Not recorded')}</b></span><span><small>Stadium / capacity</small><b>${h(i.stadium||'Not recorded')} / ${h(i.capacity??'\u2014')}</b></span></div><div class="ts22-club-recent"><strong>Recent results</strong>${(i.recent_results||[]).map(r=>`<span><small>${h(r.date)}</small> ${link(r.home_id,r.home)} <b>${r.home_goals} - ${r.away_goals}</b> ${link(r.away_id,r.away)}</span>`).join('')||'<span>No recorded results this season.</span>'}</div><details class="ts22-club-tactics"><summary>Tactical identity: ${h(data.primary?.formation)} / ${h(data.primary?.style)}</summary>${['primary','alternative'].map(key=>{const t=data[key];return t?`<section><h4>${key==='primary'?'Primary':'Alternative'}: ${h(t.formation)} / ${h(t.style)}</h4><div class="ts22-role-list">${t.slots.map(s=>`<span><b>${h(s.position)}</b> ${h(s.role)}</span>`).join('')}</div><details><summary>Team instructions</summary>${t.instructions.map(g=>`<p><b>${h(g.name)}</b>: ${g.rows.map(r=>h(r.name)+': '+h(r.value)).join(' / ')}</p>`).join('')}</details></section>`:'';}).join('')}</details><p class="rt-fam-hint">Physical state recorded as of ${h(i.condition_as_of)}. Displayed roles follow the primary plan, not a confirmed match lineup. Viewing a club does not advance recovery or change team selection.</p></section>`;
 }
 window.FMPlayerPresentation={hydrate,clubHeader,radar};
 document.addEventListener('click',event=>{
  const archive=event.target.closest('[data-open-club-history]');
  if(archive){event.preventDefault();event.stopPropagation();if(parent!==window)parent.postMessage({type:'fm-open-history',entity:'club',id:archive.dataset.openClubHistory},location.origin);else location.href='/portable/#history/club/'+encodeURIComponent(archive.dataset.openClubHistory);return;}
  const b=event.target.closest('[data-open-club]');if(!b)return;
  event.preventDefault();event.stopPropagation();
  if(parent!==window)parent.postMessage({type:'fm-open-club',clubId:b.dataset.openClub},location.origin);
  else location.href=`/portable/#club/${encodeURIComponent(b.dataset.openClub)}`;
 });
})();
