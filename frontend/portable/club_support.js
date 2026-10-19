'use strict';
/* TS-26: live staff, group training and medical choices; no daily task list. */
(() => {
  const esc=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const pay=n=>'£'+Number(n||0).toLocaleString('en-GB');
  const roleNames={coach:'Coaches',medic:'Medical staff',fitness:'Fitness coaches'};
  const modes={auto:'Automatic',light:'Light',balanced:'Balanced',intense:'Intense'};
  const groups={starters:'Starters',bench:'Substitutes',rest:'Rest of the squad'};
  const preference={aggressive:'Wants a quicker return',conservative:'Prefers a cautious recovery',neutral:'No strong preference'};
  let host=null,screen='staff',state=null,busy=false,serial=0;
  const api={staff:'/api/staff',training:'/api/training',medical:'/api/medical'};
  const panel=(heading,inner,extra='')=>`<section class="cs-panel ${extra}"><h3>${heading}</h3>${inner}</section>`;
  const banner=(title,detail)=>`<header class="cs-heading"><div><span class="cs-eyebrow">CAREER OPERATIONS · TS-26</span><h2>${title}</h2><p>${detail}</p></div></header>`;
  const optionList=(current)=>Object.entries(modes).map(([value,title])=>`<option value="${value}" ${current===value?'selected':''}>${title}</option>`).join('');
  function staff(){
    const data=state;
    const summary=`<div class="cs-metrics"><div><span>Weekly staff wages</span><strong>${pay(data.weekly_payroll_gbp)}</strong></div>${Object.entries(roleNames).map(([role,label])=>`<div><span>${label}</span><strong>${data.members.filter(m=>m.role===role).length} / ${data.capacity[role]}</strong></div>`).join('')}</div>`;
    const sections=Object.entries(roleNames).map(([role,label])=>{
      const members=data.members.filter(m=>m.role===role);
      const vacant=data.capacity[role]-members.length;
      return panel(`${label} <small>· ${members.length}/${data.capacity[role]} places</small>`,
        `<div class="cs-row-list">${members.map(m=>`<div class="cs-row"><div><strong>${esc(m.name)}</strong><small>Quality ${m.quality}/100 · ${pay(m.wage_weekly_gbp)} / week · Contract to ${esc(m.until)}</small></div><div class="cs-actions"><button type="button" data-cs-action="renew" data-id="${esc(m.id)}">Extend</button><button type="button" class="cs-danger" data-cs-action="release" data-id="${esc(m.id)}">Release</button></div></div>`).join('')||'<p class="cs-muted">No active staff contracts.</p>'}</div>
        ${vacant>0?`<div class="cs-market"><h4>Available candidates</h4>${data.market[role].map(m=>`<div class="cs-row"><div><strong>${esc(m.name)}</strong><small>Quality ${m.quality}/100 · ${pay(m.wage_weekly_gbp)} / week</small></div><button type="button" class="cs-primary" data-cs-action="hire" data-id="${esc(m.id)}">Hire</button></div>`).join('')||'<p class="cs-muted">No candidates left this year.</p>'}</div>`:'<p class="cs-muted">Department is full. Future facilities can expand its capacity.</p>'}`);
    }).join('');
    host.innerHTML=banner('Coaching & staff','Employ a few specialists. Their effects are deliberately modest.')+summary+sections+`<p class="cs-footer">${esc(data.note)} Releasing active staff incurs a two-week settlement. Hiring is limited by the club cash balance.</p>`;
  }
  function training(){
    const d=state;
    const table=d.players.map(p=>`<tr><td><strong>${esc(p.name)}</strong>${p.injured?'<small class="cs-alert">Injured — no training</small>':''}</td><td>${esc(groups[p.group])}</td><td>${p.condition.toFixed(1)}%</td><td>${esc(modes[p.effective])}</td><td>${esc(p.individual_focus)}</td></tr>`).join('');
    host.innerHTML=banner('Training centre','Set the three squad groups once, then let physical protection work automatically.')+
      panel('Training by squad group',`<div class="cs-controls">${Object.entries(groups).map(([group,label])=>`<label>${label}<select data-cs-group="${group}">${optionList(d.policy[group])}</select></label>`).join('')}</div>
        <p class="cs-muted">Squad groups reflect the current starting XI and bench. Individual development focuses remain in player profiles.</p>`)+
      panel('Automatic physical protection',`<label class="cs-toggle"><input type="checkbox" id="cs-protect" ${d.protection?'checked':''}> Automatically lower training intensity for fatigued players</label>
        <div class="cs-controls cs-threshold"><label>Below this condition: light training<input type="number" id="cs-low" min="40" max="95" value="${d.low_condition}"></label><label>Below this condition: no intense training<input type="number" id="cs-medium" min="41" max="98" value="${d.medium_condition}"></label><button type="button" class="cs-primary" data-cs-action="thresholds">Save thresholds</button></div>
        <p class="cs-muted">Ranges only reduce intensity. They never raise the workload above your chosen group setting. ${d.next_match_days===null?'':'Next match in '+d.next_match_days+' day(s).'}</p>`)+
      panel('Squad training today',`<div class="cs-table-scroll"><table><thead><tr><th>Player</th><th>Group</th><th>Condition</th><th>Effective</th><th>Development focus</th></tr></thead><tbody>${table}</tbody></table></div>`)+
      `<p class="cs-footer">${esc(d.note)} Changes affect future days only; opening this page does not advance time.</p>`;
  }
  function medical(){
    const d=state;
    const cards=d.cases.length?d.cases.map(p=>panel(esc(p.name),
      `<div class="cs-med-details"><span>${esc(p.injury)}</span><strong>${p.days_left===null?'Recovery date not recorded':p.days_left+' days remaining'}</strong><small>Estimated return: ${esc(p.return_on||'Unknown')}</small></div>
       ${p.treatment?`<p class="cs-note">${esc(p.treatment)} treatment selected · ${esc(p.treatment_status)}</p>`:''}
       ${p.treatment_available?`<div class="cs-med-choice"><p>Player opinion: <strong>${esc(preference[p.preference])}</strong>. You can make one decision for this injury.</p><div class="cs-actions"><button type="button" data-cs-action="conservative" data-player="${esc(p.id)}">Conservative · standard return, no added risk</button><button type="button" class="cs-danger" data-cs-action="aggressive" data-player="${esc(p.id)}">Aggressive · earlier, ~${p.estimated_aggressive_risk_pct}% setback risk</button></div></div>`:''}`,'cs-med-case')).join(''):
      panel('No active injuries','<p class="cs-muted">Your first-team squad currently has no recorded medical absences.</p>');
    host.innerHTML=banner('Medical centre','Monitor actual injuries and intervene only when a major treatment decision is useful.')+
      `<div class="cs-med-overview"><span>${d.cases.length} players currently unavailable</span><span>Doctors available: ${d.medical_staff_count}</span></div>`+cards+
      `<p class="cs-footer">${esc(d.note)} Players may react to the choice through the existing Inbox and trust systems.</p>`;
  }
  function render(){if(!host||!state)return;if(screen==='staff')staff();else if(screen==='training')training();else medical();host.setAttribute('aria-busy',String(busy));}
  async function refresh(){
    if(!host)return;
    const tick=++serial;
    try{const response=await fetch(api[screen],{cache:'no-store'});const payload=await response.json();if(!response.ok)throw Error(payload.error||`HTTP ${response.status}`);
      if(tick!==serial)return;state=payload;render();}
    catch(error){if(tick===serial)host.innerHTML=`<div class="cs-panel"><h3>Unable to load ${esc(screen)}</h3><p>${esc(error.message)}</p><button type="button" data-cs-action="refresh">Retry</button></div>`;}
  }
  async function send(payload){
    if(busy)return;
    busy=true;host?.setAttribute('aria-busy','true');
    try{const r=await fetch(api[screen],{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
      const result=await r.json();if(!r.ok)throw Error(result.error||`HTTP ${r.status}`);
      await refresh();if(screen==='medical')window.FMInbox?.refresh();if(screen==='staff')window.FMFinances?.refresh();
    }catch(error){window.alert(error.message||String(error));}finally{busy=false;host?.setAttribute('aria-busy','false');}
  }
  function mount(element,route){host=element;screen=route;state=null;host.innerHTML='<section class="cs-panel">Loading club information...</section>';refresh();}
  document.addEventListener('click',event=>{
    const button=event.target.closest('[data-cs-action]');if(!button||!host||!host.contains(button))return;
    const action=button.dataset.csAction;
    if(action==='refresh'){refresh();return;}
    if(screen==='training' && action==='thresholds'){
      const low=Number(host.querySelector('#cs-low').value),medium=Number(host.querySelector('#cs-medium').value);
      if(!Number.isInteger(low)||!Number.isInteger(medium)){window.alert('Enter whole numbers.');return;}
      send({action:'configure',low_condition:low,medium_condition:medium});return;
    }
    if(screen==='staff' && ['hire','release','renew'].includes(action)){
      if(!window.confirm(action==='release'?'Release this employee? A small settlement is charged.':action==='hire'?'Sign this employee on a two-year contract?':'Extend this contract by one year?'))return;
      send({action,member_id:button.dataset.id});return;
    }
    if(screen==='medical' && ['aggressive','conservative'].includes(action)){
      const description=action==='aggressive'?'An early return may result in a new setback.':'This keeps the normal recovery estimate without the extra relapse risk.';
      if(!window.confirm(`Choose ${action} treatment? ${description} This decision cannot be reversed.`))return;
      send({action:'treat',method:action,player_id:button.dataset.player});
    }
  });
  document.addEventListener('change',event=>{
    if(!host||!host.contains(event.target)||screen!=='training')return;
    const el=event.target;
    if(el.dataset.csGroup)send({action:'configure',group:el.dataset.csGroup,intensity:el.value});
    if(el.id==='cs-protect')send({action:'configure',protection:el.checked});
  });
  window.FMSupport=Object.freeze({mount,refresh});
})();
