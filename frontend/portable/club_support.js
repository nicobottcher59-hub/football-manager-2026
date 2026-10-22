'use strict';
/* TS-UI-03.03: shared automatic training, player overrides, staff and medical choices. */
(() => {
  const esc=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const pay=n=>'£'+Number(n||0).toLocaleString('en-GB');
  const roleNames={coach:'Coaches',medic:'Medical staff',fitness:'Fitness coaches',scout:'Professional scouts'};
  const modes={auto:'Automatic',light:'Light',balanced:'Balanced',intense:'Intense'};
  const preference={aggressive:'Wants a quicker return',conservative:'Prefers a cautious recovery',neutral:'No strong preference'};
  let host=null,screen='staff',state=null,busy=false,serial=0;
  const staffView={page:'overview',role:'coach',targetId:null,sort:'quality',search:'',offerWage:0,offerYears:2,offerBonus:0,feedback:null};
  const trainingView={search:'',plan:'all',focus:'all',playerId:null,lastThreshold:null};
  // The same optional ID-keyed photo catalogue read by the approved Squad screen.
  // Keep illustrated portraits as a stable fallback when a photo is absent.
  const trainingPhotoSources=new Map();
  const validSquadPhoto=s=>typeof s==='string'&&/^assets\/[a-zA-Z0-9_/-]+\.(?:png|jpg|jpeg|webp)$/.test(s);
  let trainingPhotosRequested=false;
  function ensureTrainingPhotos(){
    if(trainingPhotosRequested)return;
    trainingPhotosRequested=true;
    fetch('/public/squad/data/player-portraits.json',{cache:'no-store'})
      .then(response=>response.ok?response.json():null)
      .then(catalogue=>{
        if(catalogue?.schema_version!==1||!catalogue.portraits||typeof catalogue.portraits!=='object')return;
        for(const [id,path] of Object.entries(catalogue.portraits)){
          if(validSquadPhoto(path))trainingPhotoSources.set(id,path);
        }
        if(screen==='training'&&host)trainingRosterRows();
      }).catch(()=>{});
  }
  const api={staff:'/api/staff',training:'/api/training',medical:'/api/medical'};
  const panel=(heading,inner,extra='')=>`<section class="cs-panel ${extra}"><h3>${heading}</h3>${inner}</section>`;
  const banner=(title,detail)=>`<header class="cs-heading"><div><span class="cs-eyebrow">CAREER OPERATIONS · TS-26</span><h2>${title}</h2><p>${detail}</p></div></header>`;
  // TS-UI-05.01: Staff management and deterministic salary negotiations.
  // Photo is a neutral background; crest and colours always come from the club catalog.
  const staffRoles={
    coach:{name:'Coaches',single:'Coach',icon:'people',detail:'Support technical development and tactical familiarity.'},
    medic:{name:'Medical staff',single:'Medical specialist',icon:'heart',detail:'Help your players recover and manage recorded injuries.'},
    fitness:{name:'Fitness coaches',single:'Fitness coach',icon:'bolt',detail:'Support squad conditioning and player recovery.'},
    scout:{name:'Professional scouts',single:'Scout',icon:'search',detail:'Increase first-team scouting capacity and report speed.'},
  };
  const staffRolesOrder=['coach','medic','fitness','scout'];
  const stIcon=(name,size=18)=>trIcon(name,size);
  const staffPerson=(role,large=false)=>`<span class="st-person st-person-${esc(role)}${large?' st-person-large':''}" aria-hidden="true">${stIcon('people',large?31:23)}</span>`;
  const staffQuality=quality=>`<span class="st-quality ${quality>=80?'st-quality-high':quality>=65?'st-quality-good':quality>=55?'st-quality-mid':'st-quality-low'}" aria-label="Quality ${quality} out of 100">${quality}</span>`;
  const staffIdentity=()=>{
    const data=state||{};
    const identity=window.FMClubIdentity?.resolve?.(data.club_id,data.club)||{display_name:data.club||'Club',crest:null};
    return {name:identity.display_name||data.club||'Club',crest:identity.crest};
  };
  function staffHeader(isRecruit){
    const id=staffIdentity();
    const crest=id.crest?`<img src="${esc(id.crest)}" alt="" loading="lazy">`:stIcon('shield',34);
    return `<header class="st-hero" aria-label="Staff management"><div class="st-hero-left"><span class="st-club-crest">${crest}</span>
      <div><span class="st-overline">${esc(id.name)} · STAFF DEPARTMENT</span><h2>${isRecruit?'Recruit staff':'Coaching & staff'}</h2>
      <p>${isRecruit?'Review real candidates, negotiate their salary and improve your club’s workforce.':'Build a high-performance environment with the right people. Manage coaches, medical specialists, fitness staff and professional scouts.'}</p></div></div></header>`;
  }
  function staffStat(icon,label,value,sub,kind){
    return `<div class="st-kpi st-kpi-${kind}"><span class="st-kpi-icon">${stIcon(icon,22)}</span><span><small>${esc(label)}</small><strong>${esc(value)}</strong><em>${esc(sub)}</em></span></div>`;
  }
  function staffOverview(){
    const d=state;
    const summary=`<div class="st-kpis">${staffStat('chart','Weekly staff wages',pay(d.weekly_payroll_gbp),'Active contracts','wage')}
      ${staffRolesOrder.map(role=>{
        const n=d.members.filter(m=>m.role===role).length,capacity=d.capacity[role],details=staffRoles[role];
        return staffStat(details.icon,details.name,`${n} / ${capacity}`,`${Math.max(0,capacity-n)} positions available`,role);
      }).join('')}</div>`;
    const cards=staffRolesOrder.map(role=>{
      const info=staffRoles[role],members=d.members.filter(m=>m.role===role),max=d.capacity[role],vacant=Math.max(0,max-members.length);
      const employees=members.map(m=>`<div class="st-employed">
          ${staffPerson(role)}<div class="st-employee-name"><strong>${esc(m.name)}</strong><span>${esc(info.single)}</span>
            <small>${pay(m.wage_weekly_gbp)} / week · Contract until ${esc(m.until)}</small></div>
          ${staffQuality(m.quality)}<div class="st-employee-actions"><button type="button" class="st-action" data-st-negotiation="${esc(m.id)}" data-st-role="${role}">Open negotiations</button>
          <button type="button" class="st-action st-dismiss" data-st-dismiss="${esc(m.id)}" data-st-name="${esc(m.name)}">Dismiss</button></div>
        </div>`).join('');
      return `<section class="st-department st-department-${role}"><div class="st-department-head">
        <div class="st-title-line"><span class="st-role-symbol">${stIcon(info.icon,23)}</span><h3>${esc(info.name)}</h3><span class="st-count">${members.length} / ${max}</span></div>
        <button type="button" class="st-recruit-btn" data-st-recruit="${role}">Recruit ${esc(info.name)} ${stIcon('chevron',15)}</button>
      </div><p class="st-department-detail">${esc(info.detail)}</p>
      <div class="st-employees">${employees||'<div class="st-vacant-only">No active appointments in this department.</div>'}</div>
      <div class="st-vacancies"><span class="st-vacancy-icon">${stIcon('people',22)}</span>
        <span><strong>${vacant?`${vacant} ${vacant===1?'position':'positions'} available`:'All positions filled'}</strong><small>${vacant?'Review candidates and negotiate a contract.':'Contracts can still be renegotiated with current employees.'}</small></span>
        <button type="button" class="st-action" data-st-recruit="${role}" ${vacant?'':'disabled'}>View candidates ${stIcon('chevron',14)}</button></div>
      </section>`;
    }).join('');
    host.innerHTML=`<div class="st-shell">${staffHeader(false)}${summary}
      ${staffView.feedback?`<div class="st-feedback st-feedback-ok" role="status">${esc(staffView.feedback.message||staffView.feedback)}</div>`:''}
      <div class="st-departments">${cards}</div>
      <p class="st-footer">${esc(d.note)} Dismissing staff incurs the existing two-week settlement. Department capacities are provisional.</p></div>`;
  }
  function staffTarget(){
    const items=staffView.page==='extension'?(state?.members||[]):(state?.market?.[staffView.role]||[]);
    return items.find(item=>item.id===staffView.targetId)||null;
  }
  function selectStaffTarget(member, role, extension){
    staffView.role=role;
    staffView.page=extension?'extension':'recruit';
    staffView.targetId=member?.id||null;
    staffView.offerWage=member?.wage_demand_weekly_gbp||member?.wage_weekly_gbp||0;
    staffView.offerYears=member?.preferred_years||2;
    staffView.offerBonus=0;
    staffView.feedback=null;
    render();
  }
  function openStaffRecruit(role){
    staffView.role=staffRoles[role]?role:'coach';
    staffView.page='recruit';staffView.search='';staffView.feedback=null;
    const choices=state?.market?.[staffView.role]||[];
    const featured=[...choices].sort((a,b)=>b.quality-a.quality||a.wage_demand_weekly_gbp-b.wage_demand_weekly_gbp)[0];
    selectStaffTarget(featured,staffView.role,false);
  }
  function staffOfferSummary(){
    const previous=staffTarget();
    const after=Math.max(0,(state?.weekly_payroll_gbp||0) + staffView.offerWage - (staffView.page==='extension'?(previous?.wage_weekly_gbp||0):0));
    return `<div class="st-finance-forecast"><div><small>Current weekly staff wages</small><strong>${pay(state.weekly_payroll_gbp)}</strong></div>
      <div><small>Projected after acceptance</small><strong data-st-projected>${pay(after)}</strong></div>
      <div><small>Current club cash</small><strong>${pay(state.cash_gbp)}</strong></div></div>`;
  }
  function staffRecruit(){
    const role=staffView.role;
    const info=staffRoles[role];
    const isExtension=staffView.page==='extension';
    const target=staffTarget();
    const full=(state.members||[]).filter(m=>m.role===role).length>=Number(state.capacity?.[role]||0);
    const raw=state?.market?.[role]||[];
    const items=raw.filter(m=>m.name.toLowerCase().includes(staffView.search.toLowerCase()));
    items.sort((a,b)=>staffView.sort==='wage'?a.wage_demand_weekly_gbp-b.wage_demand_weekly_gbp||b.quality-a.quality:b.quality-a.quality||a.wage_demand_weekly_gbp-b.wage_demand_weekly_gbp);
    const candidateRows=items.map(m=>`<button class="st-candidate ${target?.id===m.id?'is-selected':''}" type="button" data-st-candidate="${esc(m.id)}">
      ${staffPerson(role)}<span class="st-candidate-name"><strong>${esc(m.name)}</strong><small>${esc(info.single)}</small></span>
      ${staffQuality(m.quality)}<span class="st-candidate-salary"><small>Wage demand</small><strong>${pay(m.wage_demand_weekly_gbp)} / wk</strong></span>
      <span class="st-candidate-term"><small>Suggested term</small><strong>${m.preferred_years} years</strong></span>${stIcon('chevron',16)}</button>`).join('');
    const negotiation=target?`<div class="st-offer-person">${staffPerson(role,true)}<span><strong>${esc(target.name)}</strong><small>${esc(info.single)} · Quality ${target.quality}/100</small></span>${staffQuality(target.quality)}</div>
      <div class="st-demand"><span>${isExtension?'Renewal wage demand':'Candidate wage demand'}</span><strong>${pay(target.wage_demand_weekly_gbp)} / week</strong></div>
      <form class="st-offer-form" data-st-offer-form><label>Weekly salary offer
        <input type="number" min="100" max="50000" step="25" name="weekly_wage_gbp" value="${staffView.offerWage}" required></label>
        <label>Contract extension / duration
          <select name="years">${[1,2,3,4].map(n=>`<option value="${n}" ${staffView.offerYears===n?'selected':''}>${n} ${n===1?'year':'years'}</option>`).join('')}</select></label>
        <label>Signing bonus (optional)
          <input type="number" min="0" max="200000" step="25" name="signing_bonus_gbp" value="${staffView.offerBonus}" required></label>
        ${full&&!isExtension?'<div class="st-feedback st-feedback-warn" role="status">Department full. Dismiss an employee before making a new appointment.</div>':''}
        <div class="st-offer-note">An offer below the expected terms can be declined. A signing bonus is paid immediately if accepted; wages are charged by the existing monthly finance system.</div>
        ${staffView.feedback?`<div class="st-feedback ${staffView.feedback.accepted?'st-feedback-ok':'st-feedback-warn'}" role="status"><strong>${esc(staffView.feedback.message)}</strong>${staffView.feedback.counter_wage_weekly_gbp?`<span>Suggested salary: ${pay(staffView.feedback.counter_wage_weekly_gbp)} / week.</span><button type="button" data-st-counter="${staffView.feedback.counter_wage_weekly_gbp}">Use counteroffer</button>`:''}</div>`:''}
        <button class="st-offer-submit" type="submit" ${busy||(full&&!isExtension)?'disabled':''}>Send ${isExtension?'renewal':'contract'} offer ${stIcon('chevron',16)}</button>
      </form>`:'<div class="st-empty">Select a candidate to negotiate a contract.</div>';
    host.innerHTML=`<div class="st-shell">${staffHeader(true)}<div class="st-recruit-menu">
      <button type="button" class="st-back" data-st-back>${stIcon('chevron',14)} Back to staff</button>
      <div class="st-recruit-tabs">${staffRolesOrder.map(r=>`<button type="button" class="${r===role?'is-active':''}" data-st-recruit="${r}">${stIcon(staffRoles[r].icon,16)} ${esc(staffRoles[r].name)}</button>`).join('')}</div>
    </div>${staffOfferSummary()}
    <div class="st-recruit-grid"><section class="st-candidate-panel"><div class="st-panel-head"><div><h3>${isExtension?'Contract extension':`${esc(info.name)} candidates`}</h3>
      <p>${isExtension?'Negotiate improved terms with an active employee.':'Compare available professionals by recorded quality and wage expectations.'}</p></div></div>
      ${isExtension?`<div class="st-extension-target">${staffPerson(role)}<strong>${esc(target?.name||'Staff member unavailable')}</strong><small>Current contract: ${pay(target?.wage_weekly_gbp||0)} / week · Until ${esc(target?.until||'—')}</small></div>`:
      `<div class="st-candidate-controls"><label>Search<input type="search" data-st-search placeholder="Search candidates" value="${esc(staffView.search)}"></label><label>Sort by<select data-st-sort><option value="quality" ${staffView.sort==='quality'?'selected':''}>Highest quality</option><option value="wage" ${staffView.sort==='wage'?'selected':''}>Lowest wage demand</option></select></label></div><div class="st-candidate-list">${candidateRows||'<p class="st-empty">No candidates match your search.</p>'}</div>
       <div class="st-candidate-footer">${items.length} visible · ${raw.length} available in ${esc(info.name)}</div>`}
    </section><section class="st-negotiation-panel"><div class="st-panel-head"><div><h3>${isExtension?'Renewal negotiation':'Negotiate contract'}</h3>
      <p>Agree salary, term and any signing bonus before an appointment becomes active.</p></div>${stIcon('people',23)}</div>
      ${negotiation}</section></div></div>`;
  }
  function staff(){
    if(!state)return;
    if(staffView.page==='overview')staffOverview();
    else staffRecruit();
  }
  function staffUpdateProjected(){
    const current=staffTarget();
    const total=Number(state?.weekly_payroll_gbp||0)+staffView.offerWage-(staffView.page==='extension'?Number(current?.wage_weekly_gbp||0):0);
    const indicator=host?.querySelector('[data-st-projected]');if(indicator)indicator.textContent=pay(total);
  }
  async function sendStaffOffer(){
    if(busy||!staffTarget()||!Number.isInteger(staffView.offerWage)||!Number.isInteger(staffView.offerBonus))return;
    const id=staffView.targetId;
    busy=true;host?.setAttribute('aria-busy','true');
    try{
      const response=await fetch('/api/staff',{method:'POST',headers:{'Content-Type':'application/json'},
        body:JSON.stringify({action:'offer',member_id:id,weekly_wage_gbp:staffView.offerWage,
          years:staffView.offerYears,signing_bonus_gbp:staffView.offerBonus})});
      const result=await response.json();if(!response.ok)throw Error(result.error||`HTTP ${response.status}`);
      if(result.accepted){
        staffView.page='overview';staffView.feedback=result;
        await refresh();window.FMFinances?.refresh?.();
      }else{staffView.feedback=result;render();}
    }catch(error){staffView.feedback={accepted:false,message:error.message||String(error)};render();}
    finally{busy=false;host?.setAttribute('aria-busy','false');}
  }
  // Training visual read model: all aggregations below use the live Python payload.
  // No historic progress, risk prediction or future match readiness is inferred.
  const trPct=v=>Math.max(0,Math.min(100,Number(v)||0));
  const trNum=v=>Number(v||0).toFixed(0);
  const trIcon=(name,size=18)=>{
    const shapes={
      shield:'<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/><path d="m9 12 2 2 4-4"/>',
      heart:'<path d="M20.5 8.5c0 5-8.5 11-8.5 11S3.5 13.5 3.5 8.5a4.5 4.5 0 0 1 8.5-2 4.5 4.5 0 0 1 8.5 2z"/>',
      people:'<circle cx="9" cy="7" r="3"/><path d="M3 21v-3a6 6 0 0 1 12 0v3M17 5a3 3 0 0 1 0 6M17 15a5 5 0 0 1 5 5v1"/>',
      bolt:'<path d="m13 2-9 12h7l-1 8 10-13h-7l0-7z"/>',
      chart:'<path d="M3 20V12M9 20V7M15 20v-4M21 20V3"/>',
      target:'<circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="5"/><circle cx="12" cy="12" r="1"/>',
      clock:'<circle cx="12" cy="12" r="9"/><path d="M12 7v5l4 2"/>',
      search:'<circle cx="11" cy="11" r="7"/><path d="m16 16 5 5"/>',
      chevron:'<path d="m9 18 6-6-6-6"/>',
      check:'<path d="m5 12 4 4L19 6"/>',
      activity:'<path d="M3 12h4l3-8 4 16 3-8h4"/>',
      layers:'<path d="m12 3 9 5-9 5-9-5 9-5ZM3 12l9 5 9-5M3 16l9 5 9-5"/>',
      calendar:'<rect x="3" y="5" width="18" height="16" rx="2"/><path d="M7 2v6M17 2v6M3 10h18"/>',
      sliders:'<path d="M4 7h16M4 17h16M9 4v6M16 14v6"/>',
    };
    return `<svg class="tr-icon" width="${size}" height="${size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.85" stroke-linejoin="round" stroke-linecap="round" aria-hidden="true">${shapes[name]||shapes.activity}</svg>`;
  };
  // Native select popups can render white on Windows despite the app dark theme.
  // Keep a genuine select as the event source; only replace its visual popup.
  function trainingPicker(attributes,options,selected,label){
    const current=options.find(x=>String(x[0])===String(selected))?.[1]||label;
    return `<div class="tr-picker" data-tr-picker>
      <select class="tr-picker-native" tabindex="-1" aria-hidden="true" ${attributes}>${options.map(([value,title])=>`<option value="${esc(value)}" ${selected===value?'selected':''}>${esc(title)}</option>`).join('')}</select>
      <button type="button" class="tr-picker-trigger" data-tr-picker-trigger aria-haspopup="listbox" aria-expanded="false" aria-label="${esc(label)}">${esc(current)}${trIcon('chevron',14)}</button>
      <div class="tr-picker-menu" role="listbox" aria-label="${esc(label)}" hidden>${options.map(([value,title])=>`<button type="button" data-tr-picker-option="${esc(value)}" role="option" aria-selected="${selected===value}">${esc(title)}${selected===value?trIcon('check',14):''}</button>`).join('')}</div>
    </div>`;
  }
  function closeTrainingPickers(except=null){
    host?.querySelectorAll('[data-tr-picker]').forEach(picker=>{
      if(picker===except)return;
      picker.querySelector('.tr-picker-menu').hidden=true;
      picker.querySelector('[data-tr-picker-trigger]').setAttribute('aria-expanded','false');
    });
  }
  function trainingPortrait(player){
    const fallback=window.FMPortraits?.portrait?.(player,'tr-player-face')||`<span class="tr-face-fallback">${esc(String(player.name||'?').slice(0,1))}</span>`;
    const photo=window.FMEntityAssets?.getPhoto?.(player.id)?null:trainingPhotoSources.get(String(player.id));
    return fallback+(photo?`<img class="tr-real-photo" src="/public/squad/${esc(photo)}" alt="" loading="lazy" decoding="async">`:'');
  }
  const autoBandFields=[
    ['performance_max','Maximum performance','Sharpness below this · intense when safe','performance'],
    ['performance_focus','Focused performance','Sharpness below this · balanced','performance'],
    ['energy_max','Maximum energy','Condition below this · light','energy'],
    ['energy_focus','Focused energy','Condition below this · balanced','energy'],
  ];
  function autoBandsMarkup(d){
    const t=d.auto_thresholds||{};
    const automaticCount=(d.players||[]).filter(p=>p.individual_intensity==null||p.individual_intensity==='auto').length;
    const channel=(key,name,icon,description)=>`<div class="tr-auto-channel tr-auto-${key}">
      <div class="tr-auto-channel-head">${trIcon(icon,19)}<div><strong>${name}</strong><small>${description}</small></div></div>
      ${autoBandFields.filter(f=>f[3]===key).map(([field,title,detail])=>`
        <div class="tr-auto-rule"><div class="tr-auto-rule-head"><span><strong>${title}</strong><small>${detail}</small></span>
          <label class="tr-auto-value"><input type="number" min="0" max="100" step="1" data-tr-auto-number="${field}" value="${t[field]??50}" aria-label="${title} threshold"><span>%</span></label></div>
          <input class="tr-auto-range" type="range" min="0" max="100" step="1" value="${t[field]??50}" data-tr-auto-range="${field}" style="--fill:${t[field]??50}%" aria-label="${title} threshold slider">
        </div>`).join('')}
      <div class="tr-auto-range-summary" data-tr-auto-summary="${key}" aria-live="polite"></div>
    </div>`;
    return `<section class="tr-section tr-auto-bands" aria-label="Automatic training plans">
      <div class="tr-section-head"><div><span class="tr-overline">01 · ADAPTIVE PLANS</span><h3>${trIcon('sliders',18)} Automatic training bands</h3></div><span class="tr-auto-active">${automaticCount} players on Automatic · Four linked thresholds</span></div>
      <p class="tr-auto-explanation">Every player follows this <b>Automatic</b> plan unless a personal intensity is selected. Energy recovery takes priority when condition and sharpness are both low.</p>
      <div class="tr-auto-grid">${channel('performance','Match performance','bolt','Based on actual match sharpness')}${channel('energy','Physical energy','heart','Based on current player condition')}</div>
      <div class="tr-auto-footer"><span>${trIcon('shield',14)} Linked boundaries cannot overlap: dragging one pushes its neighbour.</span>
        <button class="cs-primary tr-save" type="button" data-cs-action="auto_thresholds">Save automatic plans ${trIcon('chevron',14)}</button></div>
    </section>`;
  }
  function trainingThresholdValues(){
    const out={};for(const [key] of autoBandFields){const el=host?.querySelector(`[data-tr-auto-range="${key}"]`);out[key]=Number(el?.value);}
    return out;
  }
  function showThresholdBands(){
    const t=trainingThresholdValues();
    for(const [key] of autoBandFields){
      const range=host?.querySelector(`[data-tr-auto-range="${key}"]`);
      const number=host?.querySelector(`[data-tr-auto-number="${key}"]`);
      if(range){range.value=t[key];range.style.setProperty('--fill',`${t[key]}%`);}
      if(number)number.value=t[key];
    }
    for(const [channel,low,high] of [['performance','performance_max','performance_focus'],['energy','energy_max','energy_focus']]){
      const el=host?.querySelector(`[data-tr-auto-summary="${channel}"]`);
      if(el)el.textContent=`Maximum: 0–${Math.max(0,t[low]-1)} · Focused: ${t[low]}–${Math.max(t[low],t[high]-1)} · Normal auto rules from ${t[high]}`;
    }
  }
  function shiftAutoBoundary(changed,value){
    const current=trainingThresholdValues();
    const next=Math.max(0,Math.min(100,Math.round(Number(value)||0)));
    const pair=changed.startsWith('performance_')?['performance_max','performance_focus']:['energy_max','energy_focus'];
    const [lower,upper]=pair;
    current[changed]=next;
    if(current[lower]>=current[upper]){
      if(changed===lower){current[lower]=Math.min(99,current[lower]);current[upper]=current[lower]+1;}
      else{current[upper]=Math.max(1,current[upper]);current[lower]=current[upper]-1;}
    }
    for(const [key,val] of Object.entries(current)){
      const range=host?.querySelector(`[data-tr-auto-range="${key}"]`);
      if(range)range.value=val;
    }
    trainingView.lastThreshold=changed;
    showThresholdBands();
  }
  function individualTrainingMarkup(){
    const players=Array.isArray(state?.players)?state.players:[];
    if(!players.length)return '<p class="tr-empty">No managed-club players available.</p>';
    const current=players.find(p=>p.id===trainingView.playerId)||players[0];
    trainingView.playerId=current.id;
    const selectedMode=current.individual_intensity||'default';
    const modeOptions=[['default','Follow automatic plan'],['auto','Automatic (personal)'],...Object.entries(modes).filter(([key])=>key!=='auto')];
    const focuses=Array.isArray(state?.focus_options)?state.focus_options:['balanced','technical','mental','physical'];
    const overrides=players.filter(p=>p.individual_intensity);
    const summary=overrides.length?overrides.map(p=>`<div class="tr-custom-row">
      <span class="tr-custom-face">${trainingPortrait(p)}</span><span><strong>${esc(p.name)}</strong><small>${esc(modes[p.individual_intensity]||p.individual_intensity)} · effective ${esc(modes[p.effective]||p.effective)}</small></span>
      <button type="button" class="tr-custom-remove" data-tr-remove="${esc(p.id)}" aria-label="Return ${esc(p.name)} to automatic training">Use automatic ×</button>
    </div>`).join(''):'<div class="tr-custom-empty">No exceptions yet. Every player follows the automatic plan.</div>';
    return `<div class="tr-individual-select"><label class="tr-individual-label">PLAYER ${trainingPicker('data-tr-individual-player',players.map(p=>[p.id,`${p.name} · ${p.position}`]),current.id,'Choose player for individual training')}</label>
      <div class="tr-selected-identity"><span class="tr-custom-face">${trainingPortrait(current)}</span><span><strong>${esc(current.name)}</strong><small>${esc(current.position||'Player')} · Condition ${trNum(current.condition)}% · Sharpness ${trNum(current.sharpness)}%</small></span></div></div>
    <div class="tr-individual-controls"><label class="tr-individual-label">PERSONAL WORKLOAD ${trainingPicker('data-tr-individual-mode',modeOptions,selectedMode,'Personal training intensity')}</label>
      <label class="tr-individual-label">DEVELOPMENT FOCUS ${current.focus_editable?trainingPicker('data-tr-individual-focus',focuses.map(f=>[f,f.charAt(0).toUpperCase()+f.slice(1)]),String(current.individual_focus),'Individual development focus'):'<span class="tr-custom-unavailable">Development not available</span>'}</label>
      <div class="tr-individual-result"><small>EFFECTIVE TODAY</small><strong>${current.injured?'No training':esc(modes[current.effective]||current.effective)}</strong><span>${current.individual_intensity?'Personal workload replaces the automatic plan.':'Following the squad-wide automatic plan.'}</span></div></div>
    <div class="tr-individual-bottom"><div class="tr-individual-bottom-head"><strong>Individual exceptions</strong><span>${overrides.length} customized</span></div><div class="tr-custom-rows">${summary}</div></div>`;
  }
  function drawIndividualTraining(){
    const body=host?.querySelector('#tr-individual-body');if(!body)return;
    body.innerHTML=individualTrainingMarkup();
    body.querySelectorAll('img.tr-real-photo').forEach(image=>{
      image.addEventListener('error',()=>image.remove(),{once:true});
      if(image.complete&&!image.naturalWidth)image.remove();
    });
  }
  function trainingRosterRows(){
    const list=Array.isArray(state?.players)?state.players:[];
    const filter=trainingView;
    const found=list.filter(p=>(filter.plan==='all'||(filter.plan==='custom'?p.individual_intensity!=null:p.individual_intensity==null))
      &&(filter.focus==='all'||String(p.individual_focus||'balanced')===filter.focus)
      &&(!filter.search||String(p.name||'').toLocaleLowerCase().includes(filter.search.toLocaleLowerCase())
        ||String(p.position||'').toLocaleLowerCase().includes(filter.search.toLocaleLowerCase())));
    const container=host?.querySelector('#tr-roster-rows');
    if(!container)return;
    const count=host.querySelector('#tr-roster-count');if(count)count.textContent=`${found.length} / ${list.length} players`;
    container.innerHTML=found.map(p=>{
      const injured=Boolean(p.injured),status=injured?'Injured':'Training';
      const statusClass=injured?'injured':'normal';
      const focus=String(p.individual_focus||'balanced');
      return `<div class="tr-roster-row ${injured?'is-injured':''}" role="listitem">
        <button type="button" class="tr-person" data-career-type="player" data-career-id="${esc(p.id)}" aria-label="Open ${esc(p.name)} player profile">
          <span class="tr-portrait">${trainingPortrait(p)}</span>
          <span class="tr-person-words"><strong>${esc(p.name)}</strong><small>${esc(p.position||'Position not recorded')}</small></span>
        </button>
        <span class="tr-plan-label ${p.individual_intensity!=null?'is-custom':'is-automatic'}">${p.individual_intensity!=null?'Individual':'Automatic'}</span>
        <div class="tr-roster-meter" aria-label="Condition ${trNum(p.condition)} percent"><span class="tr-row-stat">${trNum(p.condition)}%</span><span class="tr-track tr-track-condition"><i style="--bar:${trPct(p.condition)}%"></i></span></div>
        <div class="tr-roster-meter" aria-label="Match sharpness ${trNum(p.sharpness)} percent"><span class="tr-row-stat">${trNum(p.sharpness)}%</span><span class="tr-track tr-track-sharpness"><i style="--bar:${trPct(p.sharpness)}%"></i></span></div>
        <span class="tr-effective tr-mode-${injured?'off':esc(p.effective)}">${injured?'No training':esc(modes[p.effective]||p.effective)}${p.individual_intensity?'<i class="tr-custom-marker" title="Individual intensity override">CUSTOM</i>':''}</span>
        <span class="tr-focus"><i class="tr-focus-dot tr-focus-${esc(focus.toLowerCase().replace(/[^a-z0-9]/g,''))}"></i>${esc(focus)}</span>
        <span class="tr-status tr-status-${statusClass}">${trIcon(injured?'activity':'check',13)}${status}</span>
        <button type="button" class="tr-row-go" data-career-type="player" data-career-id="${esc(p.id)}" aria-label="Open ${esc(p.name)} profile">${trIcon('chevron',16)}</button>
      </div>`;
    }).join('')||'<p class="tr-empty">No players match these filters. Try another search or training plan.</p>';
    // A missing optional photo must never replace its illustrated fallback with a broken image.
    container.querySelectorAll('img.tr-real-photo').forEach(image=>{
      image.addEventListener('error',()=>image.remove(),{once:true});
      if(image.complete&&!image.naturalWidth)image.remove();
    });
  }
  function training(){
    const d=state,players=Array.isArray(d.players)?d.players:[];
    const size=players.length,avg=key=>size?players.reduce((s,p)=>s+trPct(p[key]),0)/size:null;
    const customCount=players.filter(p=>p.individual_intensity!=null).length;
    const workCounts=Object.fromEntries(['light','balanced','intense'].map(v=>[v,players.filter(p=>!p.injured&&p.effective===v).length]));
    const conditionBands=[['90–100%',players.filter(p=>p.condition>=90).length],['80–89%',players.filter(p=>p.condition>=80&&p.condition<90).length],['70–79%',players.filter(p=>p.condition>=70&&p.condition<80).length],['Below 70%',players.filter(p=>p.condition<70).length]];
    const focusCounts=Object.entries(players.reduce((a,p)=>{const k=String(p.individual_focus||'balanced');a[k]=(a[k]||0)+1;return a;},{})).sort((a,b)=>b[1]-a[1]||a[0].localeCompare(b[0]));
    const maxFocus=Math.max(1,...focusCounts.map(x=>x[1]));
    const identity=window.FMClubIdentity?.resolve?.(d.club_id,d.club)||{crest:null,display_name:d.club||'Your club'};
    const crest=identity.crest?`<img src="${esc(identity.crest)}" alt="" loading="lazy">`:trIcon('shield',30);
    const kpi=(icon,label,value,foot,klass)=>`<div class="tr-kpi tr-kpi-${klass}">
      <span class="tr-kpi-icon">${trIcon(icon,19)}</span><div><strong>${value}</strong><span>${label}</span><small>${foot}</small></div>
    </div>`;
    const focusChoices=[...new Set(players.map(p=>String(p.individual_focus||'balanced')))].sort();
    const bands=conditionBands.map(([label,n],i)=>`<div class="tr-legend-item"><span class="tr-legend-color band-${i}"></span><span>${label}</span><strong>${n}</strong></div>`).join('');
    const conditionSegments=conditionBands.map(([label,n],i)=>`<span class="tr-stack-segment band-${i}" style="--segment:${size?100*n/size:0}%" title="${label}: ${n} players"></span>`).join('');
    const workBars=['light','balanced','intense'].map(k=>`<div class="tr-work-column tr-work-${k}"><div class="tr-work-vessel"><i style="--bar:${size?100*workCounts[k]/size:0}%"></i></div><strong>${workCounts[k]}</strong><span>${modes[k]}</span></div>`).join('');
    const focusBars=focusCounts.map(([key,n],i)=>`<div class="tr-focus-row"><span class="tr-focus-key"><i class="tr-focus-swatch" style="--focus-idx:${i}"></i>${esc(key)}</span><span class="tr-focus-bar"><i style="--bar:${100*n/maxFocus}%;--focus-idx:${i}"></i></span><strong>${n}</strong></div>`).join('');
    const match=d.next_match_days===null?'Next fixture date unavailable':d.next_match_days===0?'Match day today':d.next_match_days===1?'Next match tomorrow':`Next match in ${d.next_match_days} days`;
    const staff=d.training_staff;
    const staffLabel=staff?`${staff.total} active · ${staff.coaches} coach${staff.coaches===1?'':'es'} + ${staff.fitness} fitness coach${staff.fitness===1?'':'es'}`:'Training staff unavailable';
    host.classList.add('is-training');
    host.innerHTML=`<div class="tr-shell">
      <section class="tr-hero" aria-label="Training centre dashboard">
        <div class="tr-hero-identity"><span class="tr-brand-crest">${crest}</span><div><span class="tr-kicker">${esc(identity.display_name||d.club||'Club')} · FIRST TEAM</span><h2>Training centre</h2><p>Set one automatic workload plan for your whole squad and personalize players when needed. Every session uses real career data.</p><span class="tr-hero-meta"><span class="tr-next-match">${trIcon('calendar',13)}${esc(match)}</span><span class="tr-staff-chip" title="Staff numbers reflect active contracts in Staff">${trIcon('people',13)}Training staff: ${esc(staffLabel)}</span></span></div></div>
        <div class="tr-hero-kpis">
          ${kpi('heart','Average condition',avg('condition')===null?'—':trNum(avg('condition'))+'%','Current first team','condition')}
          ${kpi('bolt','Average sharpness',avg('sharpness')===null?'—':trNum(avg('sharpness'))+'%','Match sharpness','sharpness')}
          ${kpi('target','Individual plans',String(customCount),`${size-customCount} following automatic`,'custom')}
        </div>
      </section>
      ${autoBandsMarkup(d)}
      <section class="tr-section tr-individual" aria-label="Personalized individual training">
        <div class="tr-section-head"><div><span class="tr-overline">02 · INDIVIDUAL WORKLOADS</span><h3>${trIcon('target',19)} Individual player training</h3></div><span class="tr-head-note">Individual choices stay attached to player IDs across lineup changes</span></div>
        <p class="tr-explanation">Choose a player to assign a personal intensity or keep <b>Follow automatic plan</b>. Development focus shares the same setting used in Squad and applies at the monthly review.</p>
        <div class="tr-individual-body" id="tr-individual-body"></div>
      </section>
      <section class="tr-section tr-overview" aria-label="Squad training overview">
        <div class="tr-section-head"><div><span class="tr-overline">03 · CURRENT SQUAD</span><h3>Team training overview</h3></div><span class="tr-head-note">All values from the current Python session</span></div>
        <div class="tr-chart-grid">
          <div class="tr-chart"><h4>Condition distribution</h4><p>Players across fitness ranges</p><div class="tr-chart-content tr-condition-overview"><div class="tr-chart-big"><strong>${size}</strong><span>Players</span></div><div class="tr-condition-legend">${bands}</div></div><div class="tr-condition-stack" aria-label="Condition distribution">${conditionSegments}</div></div>
          <div class="tr-chart"><h4>Effective workload</h4><p>Automatic and individual workloads</p><div class="tr-work-columns">${workBars}</div></div>
          <div class="tr-chart"><h4>Individual development</h4><p>Recorded training focus distribution</p><div class="tr-focus-bars">${focusBars||'<p class="tr-empty">No focus data recorded.</p>'}</div></div>
        </div>
      </section>
      <section class="tr-section tr-roster" aria-label="Squad training today">
        <div class="tr-section-head tr-roster-top"><div><span class="tr-overline">04 · PLAYER-BY-PLAYER</span><h3>Squad training today <span id="tr-roster-count">${size} players</span></h3></div>
        <div class="tr-roster-filters"><label class="tr-roster-search">${trIcon('search',15)}<input type="search" id="tr-search" placeholder="Search players or positions…" aria-label="Search training players" data-tr-filter="search" value="${esc(trainingView.search)}"></label>
          ${trainingPicker('data-tr-filter="plan"',[['all','All plans'],['automatic','Automatic'],['custom','Individual']],trainingView.plan,'Filter by training plan')}
          ${trainingPicker('data-tr-filter="focus"',[['all','All focuses'],...focusChoices.map(key=>[key,key])],trainingView.focus,'Filter by development focus')}</div></div>
        <div class="tr-roster-labels" aria-hidden="true"><span>PLAYER</span><span>PLAN</span><span>CONDITION</span><span>SHARPNESS</span><span>TRAINING</span><span>FOCUS</span><span>STATUS</span><span></span></div>
        <div class="tr-roster-list" id="tr-roster-rows" role="list" aria-label="Current player training status" tabindex="0"></div>
      </section>
      <p class="tr-footer">${esc(d.note)} Player development focuses are set in their profiles. Opening Training never advances the career calendar.</p>
    </div>`;
    trainingRosterRows();
    drawIndividualTraining();
    showThresholdBands();
  }
  // TS-UI-04.01 — Medical dashboard. All metrics and scheduled returns are
  // read from the live Python session; no fabricated risk or future injuries.
  const mdDate=iso=>{
    if(!iso||!/^\d{4}-\d{2}-\d{2}$/.test(String(iso)))return 'Not recorded';
    const [year,month,day]=String(iso).split('-');
    return `${day}/${month}/${year}`;
  };
  const mdCount=value=>Number.isFinite(Number(value))?Math.max(0,Number(value)):0;
  const mdBand=(name,n,max,klass)=>`<div class="md-band"><span>${esc(name)}</span><div class="md-track"><i class="${klass}" style="--bar:${max?Math.min(100,100*n/max):0}%"></i></div><strong>${n}</strong></div>`;
  function medical(){
    const d=state;
    const cases=Array.isArray(d.cases)?d.cases:[];
    const size=mdCount(d.squad_size);
    const available=mdCount(d.available_count);
    const staffing=d.staffing||{};
    const medical=mdCount(staffing.medical),fitness=mdCount(staffing.fitness);
    const identity=window.FMClubIdentity?.resolve?.(d.club_id,d.club)||{display_name:d.club||'Club',crest:null};
    const crest=identity.crest?`<img src="${esc(identity.crest)}" alt="" loading="lazy">`:trIcon('shield',34);
    const medicalPhoto=window.FMEntityAssets?.safePath?.(identity.medical_image) ? window.FMEntityAssets.url(identity.medical_image) : null;
    const medicalBackground=medicalPhoto ? `style="--md-photo:url('${esc(medicalPhoto)}')"` : '';
    const kp=(icon,title,value,caption,kind)=>`<div class="md-stat md-stat-${kind}"><span class="md-stat-icon">${trIcon(icon,19)}</span><span><strong>${value}</strong><b>${title}</b><small>${esc(caption)}</small></span></div>`;
    const rosterRows=cases.map(p=>{
      const status=p.days_left===null?'Return date not recorded':`${p.days_left} days remaining`;
      const opinion=p.preference?`<p class="md-opinion">Player preference: <strong>${esc(preference[p.preference]||'No strong preference')}</strong></p>`:'';
      const controls=p.treatment_available?`<div class="md-treatment-choice"><span>Choose one treatment for this recorded injury:</span>
        <div class="md-treatment-buttons"><button type="button" data-cs-action="conservative" data-player="${esc(p.id)}">Conservative · standard return</button>
        <button type="button" class="cs-danger" data-cs-action="aggressive" data-player="${esc(p.id)}">Aggressive · earlier, ${p.estimated_aggressive_risk_pct}% estimated setback risk</button></div></div>`:'';
      return `<article class="md-injury-item"><div class="md-injury-info">
        <span class="md-injury-mark">${trIcon('activity',21)}</span><div><button type="button" class="md-player-link" data-career-type="player" data-career-id="${esc(p.id)}">${esc(p.name)} ${trIcon('chevron',14)}</button>
        <p>${esc(p.injury)}</p></div></div><div class="md-injury-return"><strong>${esc(status)}</strong><small>Estimated return: ${esc(mdDate(p.return_on))}</small></div>
        ${p.treatment?`<p class="md-treatment-saved">${trIcon('check',13)} ${esc(p.treatment)} treatment · ${esc(p.treatment_status||'recorded')}</p>`:''}${opinion}${controls}</article>`;
    }).join('');
    const empty=`<div class="md-empty"><span class="md-empty-symbol">${trIcon('shield',34)}</span><strong>No active injuries</strong><p>Your first-team squad currently has no recorded medical absences.</p>
      <div class="md-available-label">${trIcon('check',14)} All ${available} first-team players currently available</div></div>`;
    const staffRole=(icon,title,number,capacity,detail)=>`<div class="md-staff-role"><span class="md-role-icon">${trIcon(icon,20)}</span><span><strong>${esc(title)}</strong><small>${esc(detail)}</small></span><b>${number}<em> / ${mdCount(capacity)}</em></b></div>`;
    // Counts refer exclusively to recorded dated injuries. Unknown dates are
    // reported separately; they are never plotted at an invented return time.
    const returnCounts=[0,0,0,0],undated=[];
    cases.forEach(item=>{
      if(item.days_left==null){undated.push(item);return;}
      const days=Math.max(0,Number(item.days_left)||0);
      returnCounts[days<=7?0:days<=14?1:days<=28?2:3]++;
    });
    const maxReturn=Math.max(1,...returnCounts);
    const schedule=['0–7 days','8–14 days','15–28 days','29+ days'].map((label,index)=>`<div class="md-return-col"><b>${returnCounts[index]}</b><span class="md-return-track"><i style="--bar:${(100*returnCounts[index]/maxReturn)}%"></i></span><small>${label}</small></div>`).join('');
    const log=Array.isArray(d.recent_treatments)?d.recent_treatments:[];
    const history=log.length?log.map(t=>`<div class="md-history-row"><span class="md-log-icon">${trIcon('calendar',16)}</span><span><strong>${esc(t.player)}</strong><small>${esc(mdDate(t.decided_on))} · ${esc(t.method)} treatment</small></span><span class="md-log-status">${esc(t.status)}</span></div>`).join(''):
      `<div class="md-history-empty">${trIcon('calendar',25)}<strong>No treatment decisions recorded</strong><span>Decisions will appear here after a real injury is treated.</span></div>`;
    const bands=d.condition_bands||{};
    const high=mdCount(bands.high),medium=mdCount(bands.medium),low=mdCount(bands.low);
    const condition=d.average_condition==null?'—':`${Number(d.average_condition).toFixed(1)}%`;
    host.innerHTML=`<div class="md-shell">
      <section class="md-hero" ${medicalBackground} aria-label="Medical Centre">
        <div class="md-hero-main"><div class="md-club-crest">${crest}</div><div class="md-hero-copy"><span class="md-overline">${esc(identity.display_name||d.club||'Club')} · FIRST TEAM</span><h2>Medical centre</h2><p>Monitor injuries, support recovery and manage treatment decisions with your medical team.</p></div></div>
        <div class="md-hero-stats">
          ${kp('activity','Unavailable',cases.length,'Players currently sidelined','unavailable')}
          ${kp('shield','Doctors',medical,`Active / ${mdCount(staffing.medical_capacity)} places`,'doctors')}
          ${kp('people','Fitness staff',fitness,`Active / ${mdCount(staffing.fitness_capacity)} places`,'fitness')}
          ${kp('check','Squad available',available,`${size} first-team players`,'squad')}
        </div>
      </section>
      <div class="md-major-grid">
        <section class="md-panel md-injuries"><div class="md-panel-head"><div><h3>${trIcon('activity',19)} Active injuries</h3><p>Recorded absences, estimated returns and real treatment decisions</p></div><span class="md-count-pill">${cases.length} active</span></div>
          <div class="md-injury-body">${cases.length?`<div class="md-injury-list">${rosterRows}</div>`:empty}</div>
        </section>
        <div class="md-right-stack">
          <section class="md-panel md-staff"><div class="md-panel-head"><div><h3>${trIcon('people',19)} Medical &amp; fitness staff</h3><p>Active contracts in the current club</p></div><button class="md-link" type="button" data-md-open-staff>Manage staff ${trIcon('chevron',14)}</button></div>
            <div class="md-staff-rows">
              ${staffRole('shield','Medical staff',medical,staffing.medical_capacity,'Doctors and treatment decisions')}
              ${staffRole('bolt','Fitness coaches',fitness,staffing.fitness_capacity,'Recovery and physical conditioning')}
            </div>
          </section>
          <section class="md-panel md-calendar"><div class="md-panel-head"><div><h3>${trIcon('calendar',19)} Recorded returns</h3><p>When currently injured players are due back</p></div><span class="md-count-pill">${cases.filter(p=>p.days_left!==null).length} dated</span></div>
            <div class="md-return-grid">${schedule}</div><p class="md-calendar-note">${undated.length?`${undated.length} injury record(s) without a return date.`:'Only known injuries are shown; future injuries are not predicted.'}</p>
          </section>
        </div>
      </div>
      <div class="md-bottom-grid">
        <section class="md-panel md-history"><div class="md-panel-head"><div><h3>${trIcon('calendar',19)} Recent treatment decisions</h3><p>Recorded choices from your club's medical department</p></div></div><div class="md-history-rows">${history}</div></section>
        <section class="md-panel md-condition"><div class="md-panel-head"><div><h3>${trIcon('heart',19)} Squad physical snapshot</h3><p>Real current condition, not a predicted injury-risk score</p></div></div>
          <div class="md-condition-inner"><div class="md-condition-gauge" style="--level:${trPct(d.average_condition)}%"><strong>${condition}</strong><span>Avg condition</span></div>
            <div class="md-condition-bands">${mdBand('90–100%',high,size,'high')}${mdBand('75–89%',medium,size,'medium')}${mdBand('Below 75%',low,size,'low')}</div></div>
          <div class="md-condition-note">${trIcon('check',14)} ${available} of ${size} players currently available for selection</div>
        </section>
      </div>
      <p class="md-footer">${esc(d.note)} Players can respond through Inbox and the existing trust system. No changes to career simulation occur when this page opens.</p>
    </div>`;
  }
  function render(){if(!host||!state)return;host.classList.toggle('is-training',screen==='training');host.classList.toggle('is-medical',screen==='medical');host.classList.toggle('is-staff',screen==='staff');if(screen==='staff')staff();else if(screen==='training')training();else medical();host.setAttribute('aria-busy',String(busy));}
  async function refresh(){
    if(!host)return;
    const tick=++serial;
    try{const response=await fetch(api[screen],{cache:'no-store'});const payload=await response.json();if(!response.ok)throw Error(payload.error||`HTTP ${response.status}`);
      if(tick!==serial)return;state=payload;
      window.FMClubIdentity?.applyShell?.(payload.club_id,payload.club);
      render();}
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
  async function sendDevelopmentFocus(playerId,focus){
    if(busy)return;
    busy=true;host?.setAttribute('aria-busy','true');
    try{
      const r=await fetch('/api/development/focus',{method:'POST',headers:{'Content-Type':'application/json'},
        body:JSON.stringify({player_id:playerId,focus})});
      const result=await r.json();if(!r.ok)throw Error(result.error||`HTTP ${r.status}`);
      await refresh();
    }catch(error){window.alert(error.message||String(error));}
    finally{busy=false;host?.setAttribute('aria-busy','false');}
  }
  function mount(element,route){host=element;screen=route;state=null;if(route==='staff'){staffView.page='overview';staffView.role='coach';staffView.feedback=null;}if(route==='training'){trainingView.playerId=null;trainingView.lastThreshold=null;}host.innerHTML='<section class="cs-panel">Loading club information...</section>';if(route==='training')ensureTrainingPhotos();refresh();}
  document.addEventListener('click',event=>{
    if(host&&screen==='training'){
      const trigger=event.target.closest('[data-tr-picker-trigger]');
      const option=event.target.closest('[data-tr-picker-option]');
      if(trigger&&host.contains(trigger)){
        const picker=trigger.closest('[data-tr-picker]'), menu=picker.querySelector('.tr-picker-menu');
        const open=menu.hidden;
        closeTrainingPickers();
        menu.hidden=!open;trigger.setAttribute('aria-expanded',String(open));
        return;
      }
      if(option&&host.contains(option)){
        const picker=option.closest('[data-tr-picker]'), select=picker.querySelector('select');
        select.value=option.dataset.trPickerOption;
        closeTrainingPickers();
        select.dispatchEvent(new Event('change',{bubbles:true}));
        return;
      }
      closeTrainingPickers();
    }
    const staffLink=event.target.closest('[data-md-open-staff]');
    if(staffLink&&screen==='medical'&&host&&host.contains(staffLink)){
      window.FMNavigation?.navigate?.('Staff');return;
    }
    const reset=event.target.closest('[data-tr-remove]');
    if(reset&&host&&host.contains(reset)&&screen==='training'){
      send({action:'individual',player_id:reset.dataset.trRemove,intensity:'default'});return;
    }
    if(host&&screen==='staff'&&host.contains(event.target)){
      const recruit=event.target.closest('[data-st-recruit]');
      if(recruit){openStaffRecruit(recruit.dataset.stRecruit);return;}
      if(event.target.closest('[data-st-back]')){staffView.page='overview';staffView.feedback=null;render();return;}
      const negotiation=event.target.closest('[data-st-negotiation]');
      if(negotiation){const person=state.members.find(m=>m.id===negotiation.dataset.stNegotiation);
        if(person)selectStaffTarget(person,negotiation.dataset.stRole,true);return;}
      const candidate=event.target.closest('[data-st-candidate]');
      if(candidate){const person=state.market[staffView.role].find(m=>m.id===candidate.dataset.stCandidate);
        if(person)selectStaffTarget(person,staffView.role,false);return;}
      const dismiss=event.target.closest('[data-st-dismiss]');
      if(dismiss){const member=state.members.find(m=>m.id===dismiss.dataset.stDismiss);
        if(member&&window.confirm(`Dismiss ${member.name}? A two-week salary settlement is charged.`)){
          staffView.feedback=null;send({action:'release',member_id:member.id});}
        return;}
      const counter=event.target.closest('[data-st-counter]');
      if(counter){staffView.offerWage=Number(counter.dataset.stCounter);staffView.feedback=null;render();return;}
    }
    const button=event.target.closest('[data-cs-action]');if(!button||!host||!host.contains(button))return;
    const action=button.dataset.csAction;
    if(action==='refresh'){refresh();return;}
    if(screen==='training' && action==='auto_thresholds'){
      send({action:'configure',auto_thresholds:trainingThresholdValues(),changed_field:trainingView.lastThreshold});return;
    }
    if(screen==='staff' && action==='release'){
      if(!window.confirm('Dismiss this staff member? A two-week settlement will be charged.'))return;
      send({action:'release',member_id:button.dataset.id});return;
    }
    if(screen==='medical' && ['aggressive','conservative'].includes(action)){
      const description=action==='aggressive'?'An early return may result in a new setback.':'This keeps the normal recovery estimate without the extra relapse risk.';
      if(!window.confirm(`Choose ${action} treatment? ${description} This decision cannot be reversed.`))return;
      send({action:'treat',method:action,player_id:button.dataset.player});
    }
  });
  document.addEventListener('submit',event=>{
    const form=event.target.closest('[data-st-offer-form]');
    if(!form||screen!=='staff'||!host||!host.contains(form))return;
    event.preventDefault();if(!form.reportValidity())return;
    staffView.offerWage=Number(form.elements.weekly_wage_gbp.value);
    staffView.offerYears=Number(form.elements.years.value);
    staffView.offerBonus=Number(form.elements.signing_bonus_gbp.value);
    sendStaffOffer();
  });
  document.addEventListener('keydown',event=>{
    if(screen!=='training'||!host||!host.contains(event.target))return;
    if(event.key==='Escape'){
      const picker=event.target.closest('[data-tr-picker]');
      closeTrainingPickers();
      picker?.querySelector('[data-tr-picker-trigger]')?.focus();
    }
    if(event.key==='ArrowDown'&&event.target.matches('[data-tr-picker-trigger]')){
      event.preventDefault();const trigger=event.target;
      trigger.click();const options=trigger.closest('[data-tr-picker]').querySelectorAll('[data-tr-picker-option]');
      if(options.length)options[0].focus();
    }
    if((event.key==='ArrowDown'||event.key==='ArrowUp')&&event.target.matches('[data-tr-picker-option]')){
      event.preventDefault();const options=[...event.target.closest('.tr-picker-menu').querySelectorAll('[data-tr-picker-option]')];
      const next=options[(options.indexOf(event.target)+(event.key==='ArrowDown'?1:-1)+options.length)%options.length];
      next?.focus();
    }
  });
  document.addEventListener('input',event=>{
    if(screen==='staff'&&host&&host.contains(event.target)){
      if(event.target.matches('[data-st-search]')){
        staffView.search=event.target.value;
        // Avoid destroying the focused input until the user commits the search.
        const list=host.querySelector('.st-candidate-list');
        if(list){list.querySelectorAll('[data-st-candidate]').forEach(row=>{
          const item=(state.market[staffView.role]||[]).find(x=>x.id===row.dataset.stCandidate);
          row.hidden=!!item&&!item.name.toLowerCase().includes(staffView.search.toLowerCase());
        });}
      }
      if(event.target.closest('[data-st-offer-form]')){
        const input=event.target;
        if(input.name==='weekly_wage_gbp')staffView.offerWage=Number(input.value);
        if(input.name==='years')staffView.offerYears=Number(input.value);
        if(input.name==='signing_bonus_gbp')staffView.offerBonus=Number(input.value);
        staffUpdateProjected();
      }
      return;
    }
    if(!host||!host.contains(event.target)||screen!=='training')return;
    const el=event.target;
    if(el.dataset.trAutoRange||el.dataset.trAutoNumber){
      const key=el.dataset.trAutoRange||el.dataset.trAutoNumber;
      if(el.value!==''&&Number.isFinite(Number(el.value)))shiftAutoBoundary(key,el.value);
      return;
    }
    if(el.dataset.trFilter==='search'){trainingView.search=el.value;trainingRosterRows();}
  });
  document.addEventListener('change',event=>{
    if(screen==='staff'&&host&&host.contains(event.target)){
      if(event.target.matches('[data-st-sort]')){staffView.sort=event.target.value;render();}
      return;
    }
    if(!host||!host.contains(event.target)||screen!=='training')return;
    const el=event.target;
    if(el.dataset.trAutoNumber&&el.value===''){
      el.value=trainingThresholdValues()[el.dataset.trAutoNumber];return;
    }
    if(el.hasAttribute('data-tr-individual-player')){trainingView.playerId=el.value;drawIndividualTraining();return;}
    if(el.hasAttribute('data-tr-individual-mode')){send({action:'individual',player_id:trainingView.playerId,intensity:el.value});return;}
    if(el.hasAttribute('data-tr-individual-focus')){sendDevelopmentFocus(trainingView.playerId,el.value);return;}
    if(el.dataset.trFilter==='plan'||el.dataset.trFilter==='focus'){
      trainingView[el.dataset.trFilter]=el.value;trainingRosterRows();
    }
  });
  window.addEventListener('fm-identity-ready',()=>{if(host && screen==='staff' && state)render();});
  window.FMSupport=Object.freeze({mount,refresh});
})();
