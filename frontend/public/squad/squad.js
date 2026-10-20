/* FM Project UI-2: interactive portable React-agnostic surface.
 * All domain mutations and OVR/ACT come from Python's DevelopmentSession.
 * The tactical discs are a schematic, not the frozen legacy spatial simulator. */
(() => {
  'use strict';
  const root=document.getElementById('squad-root');
  const notice=document.getElementById('squad-notice');
  const params=new URLSearchParams(window.location.search);
  const inspectedClub=params.get('club');
  let screen=params.get('view')==='tactics'?'tactics':'squad';
  let phase='in_possession', tacticMode='lineup';
  let data=null, selectedSlot=null, benchToSwap=null, activeTab='role', busy=false;
  let lastEdit=null, error=null, hintTimer=null;
  // TS-19.1.1: formation picker changes Python state only after confirmation.
  let pickerOpen=false, pickerDraft=null, pickerGroup='all', pickerSearch='';
  let pitchObserver=null;
  const $=(selector,scope=root)=>scope.querySelector(selector);
  const $$=(selector,scope=root)=>Array.from(scope.querySelectorAll(selector));
  const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const short=v=>String(v).replaceAll('_',' ').replace(/\b\w/g,c=>c.toUpperCase());
  const n=v=>Math.round(Number(v)||0);
  const rating=v=>window.FMRoster.format(v);
  const statusColor=v=>v<55?'danger':v<75?'amber':'good';
  const grade=v=>v>=85?'fm-grade-top':v>=75?'fm-grade-good':v>=60?'fm-grade-mid':'fm-grade-low';
  const shape=()=>window.FMTacticalBoard.place(data,phase);
  const fieldInfo=(g,f)=>data.tactics.fields.find(x=>x.group===g && x.field===f);
  const metric=(name,value,label)=>`<div class="fm-metric"><div class="fm-metric-name">${esc(name)}</div><div class="fm-metric-score ${statusColor(value)}">${rating(value)}<span>/100</span></div><div class="fm-progress"><span class="${statusColor(value)}" style="width:${n(value)}%"></span></div><small>${esc(label)}</small></div>`;
  const face=(player,classes='')=>window.FMPortraits?.portrait(player,classes)||shirt(player?.position==='GK'?'keeper':'blue');
  const nation=(country)=>window.FMPortraits?.nation(country)||esc(country||'Unknown');
  const shirt=(color='blue')=>`<svg class="shirt ${color}" viewBox="0 0 50 48" aria-hidden="true"><path d="M16 5h18l9 6 6 12-10 5-4-7v24H15V21l-4 7-10-5L7 11z" fill="currentColor" stroke="#87d8ff" stroke-width="1.4"/><path d="M20 5q5 10 10 0" fill="none" stroke="#bedbf0" stroke-width="3"/><path d="M23 15h4v21h-4z" fill="#88d9ed" opacity=".23"/></svg>`;
  const busyClass=()=>busy?'is-busy':'';
  function announce(text, isError=false){
    notice.textContent=text;
    notice.classList.toggle('error',isError);
    notice.classList.add('shown');
    clearTimeout(hintTimer);
    hintTimer=setTimeout(()=>notice.classList.remove('shown'),5600);
  }
  function route(next){
    screen=next; selectedSlot=null; benchToSwap=null; activeTab='role'; tacticMode='lineup';pickerOpen=false;
    const uri=new URL(location.href);uri.searchParams.set('view',screen);history.replaceState({},'',uri);
    try{if(parent!==window)parent.postMessage({type:'fm-squad-route',page:screen==='tactics'?'tactics':'squad'},window.location.origin);}catch(_){/* standalone */}
    render();
  }
  function publishSnapshot(){
    if(!data || parent===window)return;
    try { parent.postMessage({type:'fm-squad-state',date:data.date,revision:'ui-3.1'},window.location.origin); }
    catch(_){/* Standalone view */}
  }
  async function load(){
    try{
      const filters=new URLSearchParams();const rs=window.FMRoster.state;
      if(rs.season)filters.set('season',rs.season);if(rs.competition!=='all')filters.set('competition',rs.competition);
      const endpoint=inspectedClub?'/api/clubs/'+encodeURIComponent(inspectedClub):'/api/squad';
      const res=await fetch(endpoint+'?'+filters,{cache:'no-store'});
      if(!res.ok)throw Error(`Python service unavailable (${res.status})`);
      data=await res.json();error=null;publishSnapshot();render();
      if(!inspectedClub)window.FMOpeningBalance?.mount(root,load);
    }catch(err){
      error=err.message;
      root.innerHTML=`<section class="fm-panel fm-offline"><h2>Python service required</h2><p>${esc(error)}</p><p>To edit real squad and tactics data, open the game with <strong>INICIAR_INTERFAZ_WINDOWS.bat</strong>. No Node.js or npm is necessary.</p><button class="fm-primary" data-action="retry">Retry connection</button></section>`;
    }
  }
  async function command(payload, success){
    if(busy||inspectedClub)return;
    const keepScroll = {
      roster: $('.rt-table-wrap')?.scrollLeft ?? null,
      squadList: $('.s2-list-scroll')?.scrollTop ?? null,
      squadDetail: $('.s2-detail-scroll')?.scrollTop ?? null,
      team: $('.fm-tactic-controls')?.scrollTop ?? null,
      instructions: $('.fm-instruction-scroll')?.scrollTop ?? null,
      attributes: $('.fm-attr-scroll')?.scrollTop ?? null,
      expanders: $$('.fm-expander').map(el=>el.open),
    };
    busy=true;
    try{
      const res=await fetch('/api/squad',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
      const result=await res.json();
      if(!res.ok)throw Error(result.error||'Command rejected');
      data=result;
      // A squad-number/transfer command returns the default season totals. If
      // the user is inspecting one competition, immediately re-read that scope.
      if(screen==='squad' && window.FMRoster?.state?.competition && window.FMRoster.state.competition!=='all'){
        const scoped=new URLSearchParams();
        if(window.FMRoster.state.season)scoped.set('season',window.FMRoster.state.season);
        scoped.set('competition',window.FMRoster.state.competition);
        const current=await fetch('/api/squad?'+scoped,{cache:'no-store'});
        if(current.ok)data=await current.json();
      }
      publishSnapshot();
      selectedSlot=selectedSlot && result.slots.some(s=>s.slot_id===selectedSlot)?selectedSlot:null;
      if(success)announce(success);
      render();
      restoreScroll(keepScroll);
      return true;
    }catch(err){
      const message='Change not applied: '+err.message;
      // Re-read Python truth after a rejected optimistic slider preview.
      try {
        const snapshot=await fetch('/api/squad',{cache:'no-store'});
        if(snapshot.ok)data=await snapshot.json();
      }catch(_){/* Preserve the last known snapshot if the service went offline. */}
      render();
      restoreScroll(keepScroll);
      announce(message,true);
      return false;
    }finally{busy=false;}
  }
  function restoreScroll(previous){
    if(previous.roster!==null && $('.rt-table-wrap')) $('.rt-table-wrap').scrollLeft=previous.roster;
    if(previous.squadList!=null && $('.s2-list-scroll')) $('.s2-list-scroll').scrollTop=previous.squadList;
    if(previous.squadDetail!=null && $('.s2-detail-scroll')) $('.s2-detail-scroll').scrollTop=previous.squadDetail;
    if(previous.team!==null && $('.fm-tactic-controls')) $('.fm-tactic-controls').scrollTop=previous.team;
    if(previous.instructions!==null && $('.fm-instruction-scroll')) $('.fm-instruction-scroll').scrollTop=previous.instructions;
    if(previous.attributes!==null && $('.fm-attr-scroll')) $('.fm-attr-scroll').scrollTop=previous.attributes;
    $$('.fm-expander').forEach((el,i)=>{if(i<previous.expanders.length)el.open=previous.expanders[i];});
  }
  function toolbar(){
    const title=tacticMode==='editor'?'Team Tactical Editor':'Starting XI & Formation';
    return `<div class="fm-toolbar"><div class="fm-toolbar-left"><div class="fm-heading"><strong>${title}</strong><span class="fm-source">LIVE PYTHON DEV SESSION</span></div><div class="fm-subtitle">${esc(data.club)} · ${esc(data.date)} · ${esc(data.next_match)}</div></div>
    <div class="fm-toolbar-actions"><div class="fm-formation-current"><span>Formation</span><button type="button" class="fm-formation-trigger" data-action="open-formations" aria-haspopup="dialog" aria-label="Choose formation, currently ${esc(data.formation.name)}"><strong>${esc(data.formation.name)}</strong><span class="fm-formation-trigger-icon" aria-hidden="true">▦</span><span class="fm-formation-trigger-cta">Choose formation</span></button></div>
    <div class="fm-segment" role="group" aria-label="Tactical phase"><button type="button" data-phase="in_possession" class="${phase==='in_possession'?'active':''}" aria-pressed="${phase==='in_possession'}">In possession</button><button type="button" data-phase="out_of_possession" class="${phase==='out_of_possession'?'active':''}" aria-pressed="${phase==='out_of_possession'}">Out of possession</button></div>
    <button type="button" class="fm-primary" data-tactic-mode="${tacticMode==='editor'?'lineup':'editor'}">${tacticMode==='editor'?'← Back to lineup':'⚙ Edit team tactics'}</button></div></div>`;
  }
  function formationDiagram(formation, large=false){
    // Catalogue coordinates come from the Python formation definitions. These
    // are position markers, not player cards or a second tactical simulation.
    return `<div class="fm-formation-pitch ${large?'fm-formation-pitch-large':''}" aria-label="${esc(formation.name)} base positions">
      <div class="fm-formation-field"><span class="fm-formation-half"></span><span class="fm-formation-centre"></span><span class="fm-formation-box fm-formation-box-top"></span><span class="fm-formation-box fm-formation-box-bottom"></span></div>
      ${(formation.slots||[]).map(slot=>`<span class="fm-formation-marker ${slot.label==='GK'?'keeper':''}" style="left:${Number(slot.x).toFixed(1)}%;top:${Number(slot.y).toFixed(1)}%" title="${esc(slot.label)}" aria-hidden="true">${large?esc(slot.label):''}</span>`).join('')}
    </div>`;
  }
  function formationDialog(){
    const choices=data.formations.map(f=>({...f,backLine:f.name.split('-')[0]})).filter(f=>(pickerGroup==='all'||f.backLine===pickerGroup) && f.name.toLowerCase().includes(pickerSearch.toLowerCase()));
    const chosen=data.formations.find(f=>f.id===pickerDraft)||data.formations[0];
    const current=data.formation.id;
    const groups=[['all','All formations'],['3','Back three'],['4','Back four'],['5','Back five']];
    return `<div id="fm-formation-dialog" class="fm-formation-overlay" role="presentation">
      <button type="button" class="fm-formation-backdrop" data-action="close-formations" aria-label="Close formation selector"></button>
      <section class="fm-formation-modal" role="dialog" aria-modal="true" aria-labelledby="fm-formation-heading" aria-describedby="fm-formation-description">
        <header class="fm-formation-header"><div><span class="fm-formation-eyebrow">TACTICAL SETUP · ${data.formations.length} FORMATIONS</span><h2 id="fm-formation-heading">Choose formation</h2><p id="fm-formation-description">Explore the existing formation catalogue. Your lineup only changes when you confirm.</p></div><button type="button" class="fm-formation-close" data-action="close-formations" aria-label="Close formation selector">×</button></header>
        <div class="fm-formation-body"><div class="fm-formation-library">
          <div class="fm-formation-filters"><label class="fm-formation-search-label" for="fm-formation-search">Search formations</label><input id="fm-formation-search" class="fm-formation-search" type="search" placeholder="Search 4-3-3, diamond, DM…" autocomplete="off" value="${esc(pickerSearch)}"></div>
          <div class="fm-formation-tabs" role="group" aria-label="Filter formations">${groups.map(([id,label])=>`<button type="button" data-formation-group="${id}" class="${pickerGroup===id?'active':''}" aria-pressed="${pickerGroup===id}">${label}</button>`).join('')}</div>
          <div class="fm-formation-scroll" aria-label="Formation choices"><div class="fm-formation-tiles">${choices.map(form=>`<button type="button" class="fm-formation-tile ${form.id===pickerDraft?'selected':''}" data-formation-pick="${esc(form.id)}" aria-pressed="${form.id===pickerDraft}" aria-label="Preview ${esc(form.name)}"><span class="fm-formation-tile-pitch">${formationDiagram(form)}</span><span class="fm-formation-tile-bottom"><strong>${esc(form.name)}</strong>${form.id===current?'<span class="fm-formation-is-current">CURRENT</span>':''}</span></button>`).join('')}</div>${!choices.length?'<div class="fm-formation-empty">No matching formations. Try another name or category.</div>':''}</div>
        </div><aside class="fm-formation-preview" aria-label="Selected formation preview"><div class="fm-formation-preview-heading"><span>FORMATION PREVIEW</span>${chosen.id===current?'<span class="fm-preview-current">Currently active</span>':'<span class="fm-preview-change">Preview only</span>'}</div><h3>${esc(chosen.name)}</h3><p>Base structure · ${chosen.slots?.length||0} positions</p>${formationDiagram(chosen,true)}<div class="fm-formation-preview-note">Player positions are shown as tactical markers. Switching formation retains the existing Python behavior for resetting role assignments.</div><div class="fm-formation-modal-actions"><button type="button" class="fm-secondary" data-action="close-formations">Cancel</button><button type="button" class="fm-primary" data-action="apply-formation" ${chosen.id===current||busy?'disabled':''}>${chosen.id===current?'Already selected':'Use this formation'}</button></div></aside></div>
      </section>
    </div>`;
  }
  function openFormationDialog(){
    if(!data||busy)return;
    pickerOpen=true;pickerDraft=data.formation.id;pickerGroup='all';pickerSearch='';
    render();$('#fm-formation-search')?.focus();
  }
  function closeFormationDialog(){
    if(busy)return; // Do not cancel the UI while Python is applying a choice.
    pickerOpen=false;pickerDraft=null;render();
    $('[data-action="open-formations"]')?.focus();
  }
  function redrawFormationDialog(focusSearch=false){
    const existing=$('#fm-formation-dialog');
    if(!existing)return;
    const scroll=$('.fm-formation-scroll')?.scrollTop||0;
    existing.outerHTML=formationDialog();
    if($('.fm-formation-scroll'))$('.fm-formation-scroll').scrollTop=scroll;
    if(focusSearch){
      const input=$('#fm-formation-search');input?.focus();input?.setSelectionRange(pickerSearch.length,pickerSearch.length);
    }
  }
  async function confirmFormation(){
    if(busy||!pickerDraft||pickerDraft===data.formation.id)return;
    const id=pickerDraft;
    // The exact preexisting action is used; previews never mutate the domain.
    selectedSlot=null;benchToSwap=null;
    if(await command({action:'formation',id},'Formation updated in Python. Roles reset to position defaults.')){
      closeFormationDialog();
    }
  }
  function pitchCard(slot,p,pos){
    const style=`left:${pos.x.toFixed(2)}%;top:${pos.y.toFixed(2)}%;`;
    if(screen==='tactics' && tacticMode==='editor' && window.FMStudio)return window.FMStudio.marker(slot,p,pos,selectedSlot===slot.slot_id,data.studio);
    if(screen==='tactics' && tacticMode==='editor')return `<div class="fm-token ${p.position==='GK'?'keeper':''}" data-slot="${esc(slot.slot_id)}" style="${style}" aria-label="${esc(slot.label||slot.position)} tactical marker"><span class="token-glow"></span></div>`;
    const selected=selectedSlot===slot.slot_id;
    const pending=benchToSwap?' is-swap-target':'';
    return `<button type="button" draggable="true" class="fm-player-chip ${selected?'selected':''}${pending}" data-player-slot="${esc(slot.slot_id)}" style="${style}" title="${esc(p.name)} — OVR ${rating(p.ovr)} / ACT ${rating(p.act)}" aria-label="${esc(p.name)} at ${esc(p.position)}, OVR ${rating(p.ovr)}, ACT ${rating(p.act)}, condition ${n(p.condition)} percent">
      <span class="fm-player-top">${face(p,'fm-face-pitch')}<span class="fm-player-ovr ${grade(p.act)}">${rating(p.act)} <small>GRL</small></span></span>
      <span class="fm-player-name">${esc(p.short_name)}</span>
      <span class="fm-player-meta">${esc(slot.label||slot.position)} <b>${rating(p.act)} ACT</b></span>
      <span class="fm-player-condition"><span class="${statusColor(p.condition)}" style="width:${n(p.condition)}%"></span></span>
    </button>`;
  }
  function pitch(){
    const points=shape(),players=new Map(data.starters.map(p=>[p.slot_id,p]));
    const rings=tacticMode==='editor'?'fm-schematic':'fm-real-roster';
    const on=phase==='in_possession';
    return `<section class="fm-pitch-panel fm-panel"><div class="fm-pitch-caption"><span class="fm-green-dot"></span>${tacticMode==='editor'?'Tactical shape · ': 'Starting team · '}${on?'In possession':'Out of possession'}<span class="fm-pitch-caption-right">${tacticMode==='editor'?'PHASE TARGETS · ATTACKING UP':'OVR / ACT / CONDITION'}</span></div>
    <div class="fm-pitch ${rings}" aria-label="${on?'In-possession':'Out-of-possession'} tactical formation">
      ${tacticMode==='editor'?'<canvas class="ts-overlay" aria-hidden="true"></canvas>':''}
      <div class="fm-pitch-lines"><div class="fm-center-line"></div><div class="fm-center-circle"></div><div class="fm-top-box"></div><div class="fm-bottom-box"></div><div class="fm-top-six"></div><div class="fm-bottom-six"></div><div class="fm-top-dot"></div><div class="fm-bottom-dot"></div></div>
      <div class="fm-shape-layer" id="fm-shape-layer">
      ${data.slots.map(slot=>pitchCard(slot,players.get(slot.slot_id),points[slot.slot_id])).join('')}
      </div></div>
    ${tacticMode==='editor'?window.FMStudio.footer(data,phase)
      :`<div class="fm-pitch-foot"><span>Click a player to edit their role and instructions.</span><span>Drag a starter to swap positions; select a substitute to replace one.</span></div>`}</section>`;
  }
  function statusPanel(){
    const m=data.squad_status;
    return `<section class="fm-panel fm-status"><div class="fm-panel-head"><h2>Squad Status</h2><small>Starting XI averages</small></div><div class="fm-status-grid">${metric('Morale',m.morale,'Dressing room')}${metric('Condition',m.condition,'Match fitness')}${metric('Chemistry',m.chemistry,'Team cohesion')}${metric('Form',m.form,'Recent form')}</div></section>`;
  }
  function subsPanel(){
    return `<section class="fm-panel fm-subs"><div class="fm-panel-head"><h2>Substitutes <span class="fm-count">${data.bench.length}</span></h2><small>${benchToSwap?'Choose a starter →':'Click to select replacement'}</small></div>
      ${benchToSwap?`<div class="fm-swap-hint">Replace a starter with <b>${esc(data.bench.find(p=>p.id===benchToSwap)?.name||'')}</b>. <button data-action="cancel-swap">Cancel</button></div>`:''}
      <div class="fm-subs-list">${data.bench.map((p,i)=>`<button type="button" data-bench="${esc(p.id)}" class="fm-bench-row ${benchToSwap===p.id?'active':''}"><span class="fm-sub-no">${i+12}</span>${face(p,'fm-face-bench')}<span class="fm-sub-main"><strong>${esc(p.name)}</strong><small>${esc(p.position)} · ${rating(p.ovr)} OVR · ${rating(p.act)} ACT</small></span><span class="fm-sub-phys"><span>${n(p.condition)}%</span><i><i style="width:${n(p.condition)}%" class="${statusColor(p.condition)}"></i></i></span></button>`).join('')}</div></section>`;
  }
  function setPiecePanel(){
    const entries=data.set_pieces?.roles||[];
    const labels={captain:'Captain',penalties:'Penalties',free_kicks:'Free kicks',corners_left:'Left corners',corners_right:'Right corners'};
    const options=[{id:'',name:'Automatic (best available)'},...(data.set_pieces?.players||[])];
    return `<section class="fm-panel fm-setpieces fm-ts27-pieces"><div class="fm-panel-head"><h2>Captain & set pieces</h2><small>Saved in career</small></div><div class="fm-setpieces-inner">
      ${entries.map(row=>`<div class="fm-ts27-role"><label><strong>${esc(labels[row.role]||row.role)}</strong>
        ${selector(options,row.orders[0]||'',`data-set-piece="${esc(row.role)}" data-rank="0" aria-label="First choice for ${esc(labels[row.role])}"`)}
        </label><small>On pitch: ${esc(row.effective_name||'No eligible player')}${row.fallback?' (automatic backup)':''}</small>
        <details><summary>Backup order</summary>${[1,2].map(i=>`<label class="fm-ts27-backup">${i===1?'Second choice':'Third choice'} ${selector(options,row.orders[i]||'',`data-set-piece="${esc(row.role)}" data-rank="${i}" aria-label="Priority ${i+1} for ${esc(labels[row.role])}"`)}</label>`).join('')}</details>
      </div>`).join('')}
      <p class="fm-caption">Only available players on the pitch can take responsibility. Saved preferences never force unavailable players to play; all missing choices fall back automatically.</p>
    </div></section>`;
  }
  function opponentPanel(){
    const report=data.match_preparation;
    if(!report?.available)return '';
    const metricLabels={pressing:'Press',directness:'Direct',possession:'Possession',defensive_depth:'Line'};
    return `<section class="fm-panel fm-ts27-opponent" aria-label="Next opponent report">
      <div class="fm-panel-head"><h2>Next opponent · ${esc(report.opponent)}</h2><small>${esc(report.formation)} · ${esc(report.style)}</small></div>
      <div class="fm-ts27-report">
        <div class="fm-ts27-metrics">${Object.entries(report.metrics).map(([k,v])=>`<span><small>${esc(metricLabels[k]||k)}</small><b>${Number(v).toFixed(0)}</b></span>`).join('')}</div>
        <div class="fm-ts27-insights"><strong>Observed tactical tendencies</strong>${report.tendencies.map(s=>`<p>${esc(s)}</p>`).join('')}</div>
        <div class="fm-ts27-players"><strong>Key players in projected XI</strong><div>${report.key_players.map(p=>`<span>${esc(p.name)} · ${esc(p.position)} · ${Number(p.ovr).toFixed(0)} OVR</span>`).join('')}</div></div>
        <details><summary>Recent recorded results (${report.recent.length})</summary>${report.recent.map(r=>`<p>${esc(r.date)} · ${esc(r.opponent)} · ${r.goals_for}-${r.goals_against}</p>`).join('')||'<p>No played games recorded yet.</p>'}</details>
        <p class="fm-caption">${esc(report.disclaimer)}</p>
      </div></section>`;
  }
  function outsidePanel(){
    const items=data.outside;
    return `<section class="fm-panel fm-outside"><div class="fm-panel-head"><h2>Out of Matchday Squad <span class="fm-count">${items.length}</span></h2><small>Not in starting XI or on bench</small></div>${items.length?`<div class="fm-outside-list">${items.map(p=>`<div class="fm-outside-player">${face(p,'fm-face-outside')}<div><strong>${esc(p.name)}</strong><small>${esc(p.position)} · OVR ${rating(p.ovr)}</small></div><span class="${p.available?'fm-ready':'fm-injury'}">${p.injury?'Injured':p.suspension?'Suspended':'Available'}</span></div>`).join('')}</div>`:`<p class="fm-empty">No players outside the matchday squad in this DEV roster: 11 starters + ${data.bench.length} substitutes. This section will populate when squads have additional players.</p>`}</section>`;
  }
  function selector(options,value,extras=''){
    return `<select class="fm-select" ${extras}>${options.map(item=>`<option value="${esc(item.id)}" ${item.id===value?'selected':''}>${esc(item.name)}</option>`).join('')}</select>`;
  }
  function individualOptions(item){
    const opts=[{id:'default',name:`Role default (${short(item.effective)})`}];
    if(item.kind==='target'){
      opts.push({id:'',name:'No target'});
      data.targets.positions.forEach(p=>opts.push({id:`position:${p}`,name:`Mark position · ${p}`}));
      data.targets.players.forEach(p=>opts.push({id:`player:${p.id}`,name:`Opponent · ${p.name}`}));
      data.targets.roles.forEach(r=>opts.push({id:`role:${r}`,name:`Role · ${short(r)}`}));
    }else item.options.forEach(v=>opts.push({id:v,name:short(v)}));
    return selector(opts,item.override===null?'default':item.override,`data-individual="${item.field}"`);
  }
  function rolePanel(){
    const slot=data.slots.find(s=>s.slot_id===selectedSlot);
    const player=data.starters.find(p=>p.slot_id===selectedSlot);
    if(!slot || !player)return '';
    const tabs=[['role','Role & position'],['instructions','Instructions'],['attributes','Attributes']];
    return `<section class="fm-panel fm-player-details"><div class="fm-player-profile"><div class="fm-profile-left">${face(player,'fm-face-profile')}<div><div class="fm-player-eyebrow">${esc(slot.position)} · ${nation(player.nationality)} · ${player.age} years</div><h2>${esc(player.name)}</h2><p>${esc(player.role)} · Foot: ${esc(player.foot)}</p></div></div><div class="fm-profile-ratings"><span>${rating(player.ovr)}<small>OVR</small></span><span>${rating(player.act)}<small>ACT</small></span><button type="button" data-action="close-player" aria-label="Close player editor">×</button></div></div>
      <div class="fm-player-mini">${[['Condition',player.condition],['Morale',player.morale],['Positional familiarity',player.familiarity],['Role fit',player.role_fit]].map(([name,v])=>`<div><small>${name}</small><strong>${rating(v)}</strong><i><i class="${statusColor(v)}" style="width:${n(v)}%"></i></i></div>`).join('')}</div>
      <div class="fm-position-strip" aria-label="Dynamic positional familiarity">${player.familiarities.map(f=>`<span title="${f.is_primary?'Primary':f.is_secondary?'Secondary':'Learned'} · ${rating(f.effective)} / 100">${esc(f.position)} <b>${rating(f.effective)}</b></span>`).join('')}</div>
      <div class="fm-player-tabs" role="tablist">${tabs.map(([key,title])=>`<button role="tab" type="button" data-player-tab="${key}" aria-selected="${activeTab===key}" class="${activeTab===key?'active':''}">${title}</button>`).join('')}</div>
      ${tacticMode==='editor'&&window.FMStudio?window.FMStudio.positionControl(data,slot,phase):''}
      ${activeTab==='role'?`<div class="fm-player-form"><h3>Current role</h3>${selector(slot.roles,slot.role_id,`data-change="role" data-slot-id="${esc(slot.slot_id)}"`)}<p class="fm-caption">All compatible Python role definitions available for this position. Changing a role resets its individual overrides, matching the current sandbox behavior.</p><h3>Alternatives (${slot.roles.length})</h3><div class="fm-role-list">${slot.roles.map(r=>`<button type="button" data-role-id="${esc(r.id)}" class="${r.id===slot.role_id?'active':''}">${esc(r.name)}<span>${r.id===slot.role_id?'Selected':'Choose'}</span></button>`).join('')}</div></div>`:''}
      ${activeTab==='instructions'?`<div class="fm-player-form"><div class="fm-inline"><h3>Individual instructions (${slot.individual.length})</h3><button data-action="reset-individual" class="fm-text-btn">Reset all</button></div><p class="fm-caption">Only selections marked as overrides replace the role's defaults. Marking and pressing targets use the Python domain types.</p><div class="fm-instruction-scroll">${slot.individual.map(item=>`<label class="fm-individual-row"><span>${esc(item.label)} <small>${item.override===null?'Role default':'Custom override'}</small></span>${individualOptions(item)}</label>`).join('')}</div></div>`:''}
      ${activeTab==='attributes'?`<div class="fm-player-form"><h3>Player attributes from Python</h3><div class="fm-attr-scroll">${Object.entries(player.attributes).map(([category,values])=>`<h4>${esc(short(category))}</h4><div class="fm-attrs">${Object.entries(values||{}).filter(([,v])=>typeof v==='number').map(([key,val])=>`<div><span>${esc(short(key))}</span><b>${n(val)}</b></div>`).join('')}</div>`).join('')}</div></div>`:''}
      <div class="fm-panel-bottom"><button type="button" class="fm-secondary" data-open-career-player="${esc(player.id)}">Career history ↗</button><button class="fm-secondary" data-action="close-player">${tacticMode==='editor'?'Back to team instructions':'Back to lineup'}</button></div>
    </section>`;
  }
  function lineupScreen(){
    return `<div class="fm-content-grid"><div class="fm-left">${pitch()}</div><div class="fm-right">${selectedSlot?rolePanel():`${statusPanel()}<div class="fm-columns">${subsPanel()}${setPiecePanel()}</div>`}</div></div>${outsidePanel()}`;
  }
  function fieldControl(item){
    const isLevel=item.kind==='level';
    const title=item.label;
    if(isLevel){
      const idx=Math.max(0,item.options.indexOf(item.value));
      return `<div class="fm-control" data-field-row="${esc(item.group)}.${esc(item.field)}"><div class="fm-control-head"><label for="fm-${esc(item.group)}-${esc(item.field)}">${esc(title)}</label><strong data-field-label>${esc(short(item.value))}</strong></div><input id="fm-${esc(item.group)}-${esc(item.field)}" type="range" min="0" max="${item.options.length-1}" step="1" value="${idx}" data-range-group="${esc(item.group)}" data-range-field="${esc(item.field)}" aria-label="${esc(title)}"><div class="fm-scale"><span>Very low</span><span>Very high</span></div></div>`;
    }
    return `<div class="fm-control fm-control-choice"><label>${esc(title)}${selector(item.options.map(id=>({id,name:short(id)})),item.value,`data-tactic-field="${esc(item.field)}" data-tactic-group="${esc(item.group)}"`)}</label></div>`;
  }
  function tacticsScreen(){
    const group=phase==='in_possession'?'in_possession':'out_of_possession';
    const mainFields=data.tactics.fields.filter(f=>f.group===group);
    const transition=data.tactics.fields.filter(f=>f.group==='transition');
    const game=data.tactics.fields.filter(f=>f.group==='game_management');
    const scores=data.tactics.style_scores;
    return `${opponentPanel()}${window.FMStudio.library(data)}<div class="fm-content-grid fm-tactics-grid"><div class="fm-left">${pitch()}<section class="fm-panel fm-style-panel"><div class="fm-panel-head"><h2>Style Analysis</h2><span class="fm-technical">Python domain calculation</span></div><div class="fm-style-grid">${Object.entries(scores).map(([k,v])=>`<div><small>${short(k)}</small><b>${rating(v)}</b><i><i style="width:${n(v)}%"></i></i></div>`).join('')}</div></section></div>
      ${selectedSlot?rolePanel():`<section class="fm-panel fm-tactic-controls"><div class="fm-panel-head"><div><h2>Team Tactics</h2><small>${esc(data.tactics.style)} · Tactical familiarity ${rating(data.squad_status.tactical_familiarity)}/100</small></div></div>
      <div class="fm-preset"><label for="fm-preset">Tactical preset</label>${selector([...data.tactics.presets,{id:'custom',name:'Custom (manual edits)'}],data.tactics.preset,`data-change="preset" id="fm-preset" ${data.tactics.preset==='custom'?'':' '}`)}<p>Preset changes replace team instructions and role assignments as in Python.</p></div>
      <div class="fm-control-section"><h3>${phase==='in_possession'?'In possession':'Out of possession'} <span>${mainFields.length} instructions</span></h3><div class="fm-controls-grid">${mainFields.map(fieldControl).join('')}</div></div>
      <details class="fm-expander" open><summary>Transitions <span>${transition.length} parameters</span></summary><div class="fm-controls-grid">${transition.map(fieldControl).join('')}</div></details>
      <details class="fm-expander"><summary>Match management <span>${game.length} parameters</span></summary><div class="fm-controls-grid">${game.map(fieldControl).join('')}</div></details>
      <p class="fm-model-disclaimer">Instructions feed the Python match model. Explicit phase targets override automatic marker positioning, not the other instruction effects. Spatial overlays are estimates, not match telemetry.</p>
    </section>`}</div>${setPiecePanel()}`;
  }
  function refreshKeepingTable(){
    const table=$('.rt-table-wrap');
    const left=table?.scrollLeft ?? 0, top=table?.scrollTop ?? 0;
    const squadList=$('.s2-list-scroll')?.scrollTop ?? null;
    const detail=$('.s2-detail-scroll')?.scrollTop ?? null;
    render();
    const newer=$('.rt-table-wrap');
    if(newer){newer.scrollLeft=left;newer.scrollTop=top;}
    if(squadList!=null && $('.s2-list-scroll'))$('.s2-list-scroll').scrollTop=squadList;
    if(detail!=null && $('.s2-detail-scroll'))$('.s2-detail-scroll').scrollTop=detail;
  }
  function render(){
    if(!data)return;
    if(inspectedClub&&data.available===false){root.innerHTML=`<section class="rt-card"><h2>${esc(data.club)}</h2><p>${esc(data.message)}</p></section>`;return;}
    // TS-UI-02.2: preserve independent panel positions during model refreshes.
    // An open tab or a newly selected player explicitly resets the inspector only.
    const squadListTop=screen==='squad'?$('.s2-list-scroll')?.scrollTop:null;
    const squadDetailTop=screen==='squad'?$('.s2-detail-scroll')?.scrollTop:null;
    root.innerHTML=(screen==='squad'?window.FMRoster.render(data):toolbar()+(tacticMode==='editor'?tacticsScreen():lineupScreen()))+(pickerOpen?formationDialog():'');
    if(squadListTop!=null && $('.s2-list-scroll'))$('.s2-list-scroll').scrollTop=squadListTop;
    if(squadDetailTop!=null && $('.s2-detail-scroll'))$('.s2-detail-scroll').scrollTop=squadDetailTop;
    root.classList.toggle('is-tactics',screen==='tactics');
    root.classList.toggle('is-squad',screen==='squad');
    root.classList.toggle('is-tactical-editor',screen==='tactics'&&tacticMode==='editor');
    if(screen==='tactics' && tacticMode==='editor' && window.FMStudio)window.FMStudio.mount({
      root,data,phase,shape,command,announce,busy:()=>busy,render,
      select:slot=>{selectedSlot=slot;activeTab='role';render();},
    });
    if(pitchObserver)pitchObserver.disconnect();
    const pitchElement=$('.fm-pitch');
    if(pitchElement && screen==='tactics' && tacticMode!=='editor'){
      if(typeof ResizeObserver!=='undefined'){
        pitchObserver=new ResizeObserver(()=>requestAnimationFrame(positionLineupCards));
        pitchObserver.observe(pitchElement);
      }
      requestAnimationFrame(positionLineupCards);
    }
    try { if (parent !== window) parent.postMessage({type:'fm-squad-state',date:data.date},window.location.origin); } catch(_) {/* standalone */}
  }
  function positionLineupCards(){
    const pitch=$('.fm-pitch');
    if(!pitch || !data || screen!=='tactics' || tacticMode==='editor')return;
    const cards=$$('[data-player-slot]',pitch);
    if(!cards.length)return;
    const sample=cards[0].getBoundingClientRect();
    const bounds=pitch.getBoundingClientRect();
    if(!sample.width||!sample.height||!bounds.width||!bounds.height)return;
    const layout=window.FMFormationLayout.arrange(shape(),data.slots,{
      width:bounds.width,height:bounds.height,cardWidth:sample.width,cardHeight:sample.height,
    });
    cards.forEach(card=>{
      const point=layout[card.dataset.playerSlot];
      if(!point)return;
      card.style.left=(100*point.x/bounds.width).toFixed(3)+'%';
      card.style.top=(100*point.y/bounds.height).toFixed(3)+'%';
    });
  }
  function refreshBoard(){
    if(!data)return;
    const points=shape();
    if(screen==='tactics'&&tacticMode!=='editor'){
      positionLineupCards();return;
    }
    $$('[data-player-slot],.fm-token').forEach(el=>{
      const id=el.dataset.playerSlot||el.dataset.slot;
      if(!points[id])return;
      el.style.left=points[id].x.toFixed(2)+'%';
      el.style.top=points[id].y.toFixed(2)+'%';
      el.classList.remove('is-updating'); void el.offsetWidth; el.classList.add('is-updating');
    });
    const label=$('.fm-board-help strong'); if(label&&lastEdit)label.textContent=lastEdit;
    if(tacticMode==='editor')window.FMStudio?.refresh();
  }
  root.addEventListener('click',event=>{
    const button=event.target.closest('button');
    if(!button){
      // TS-UI-02.2: the entire list row opens the inspector; player names
      // remain separate buttons leading to the full player history/profile.
      const row=screen==='squad'?event.target.closest('[data-s2-row]'):null;
      if(row)window.FMRoster.onClick({dataset:{rosterExpand:row.dataset.s2Row}},refreshKeepingTable);
      return;
    }
    if(button.hasAttribute('data-open-career-player')) {
      const id=button.dataset.openCareerPlayer;
      if(parent!==window)parent.postMessage({type:'fm-open-history',entity:'player',id},window.location.origin);
      else window.location.href='/portable/#history/player/'+encodeURIComponent(id);
      return;
    }
    if(button.hasAttribute('data-open-transfer-offer')) {
      // Club profiles are read-only; the parent owns game navigation.
      if(inspectedClub && parent!==window)parent.postMessage({type:'fm-open-transfer-offer',
        clubId:inspectedClub,playerId:button.dataset.openTransferOffer},window.location.origin);
      return;
    }
    if(button.hasAttribute('data-open-finances')) {
      if(parent!==window)parent.postMessage({type:'fm-open-finances'},window.location.origin);
      return;
    }
    if(button.hasAttribute('data-open-youth-academy')) {
      if(parent!==window)parent.postMessage({type:'fm-open-youth-academy'},window.location.origin);
      return;
    }
    if(button.dataset.action==='retry')return load();
    if(button.dataset.action==='open-formations')return openFormationDialog();
    if(button.dataset.action==='close-formations')return closeFormationDialog();
    if(button.dataset.action==='apply-formation')return confirmFormation();
    if(button.dataset.formationGroup){pickerGroup=button.dataset.formationGroup;redrawFormationDialog();$('[data-formation-group="'+pickerGroup+'"]')?.focus();return;}
    if(button.dataset.formationPick){pickerDraft=button.dataset.formationPick;redrawFormationDialog();$$('[data-formation-pick]').find(item=>item.dataset.formationPick===pickerDraft)?.focus();return;}
    if(pickerOpen)return; // Prevent background mutations while the dialog is open.
    if(screen==='squad' && window.FMRoster.onClick(button, refreshKeepingTable))return;
    if(button.dataset.route)return route(button.dataset.route);
    if(button.dataset.tacticMode){tacticMode=button.dataset.tacticMode;selectedSlot=null;benchToSwap=null;render();return;}
    if(button.dataset.phase){phase=button.dataset.phase; render();return;}
    if(button.dataset.playerTab){activeTab=button.dataset.playerTab;render();return;}
    if(button.dataset.action==='close-player'){selectedSlot=null;render();return;}
    if(button.dataset.action==='cancel-swap'){benchToSwap=null;render();return;}
    if(button.dataset.action==='reset-individual'){
      return command({action:'reset_player_instructions',slot_id:selectedSlot},'All individual overrides reset to role defaults.');
    }
    if(button.dataset.roleId){return command({action:'role',slot_id:selectedSlot,role_id:button.dataset.roleId},'Role changed in Python.');}
    if(button.dataset.bench){benchToSwap=button.dataset.bench;selectedSlot=null;render();return;}
    if(button.dataset.playerSlot){
      if(benchToSwap){
        const starter=data.starters.find(p=>p.slot_id===button.dataset.playerSlot);
        const bench=benchToSwap;benchToSwap=null;
        return command({action:'swap_bench',starter_id:starter.id,bench_id:bench},'Lineup and substitutes updated in Python.');
      }
      selectedSlot=button.dataset.playerSlot; activeTab='role';render();
    }
  });
  // TS-UI-02.3: selectable cards also work with Enter/Space. Navigation has
  // its own explicit button, so focusing the player's name never opens both.
  root.addEventListener('keydown',event=>{
    if(screen!=='squad'||!['Enter',' '].includes(event.key))return;
    if(event.target.closest('button,input,select,textarea,a'))return;
    const card=event.target.closest('[data-s2-row]');
    if(!card)return;
    event.preventDefault();
    window.FMRoster.onClick({dataset:{rosterExpand:card.dataset.s2Row}},refreshKeepingTable);
    $('.s2-roster-row.selected')?.focus({preventScroll:true});
  });
  root.addEventListener('change',event=>{
    const e=event.target;
    if(pickerOpen)return;
    if(screen==='squad' && window.FMRoster.onChange(e, command, refreshKeepingTable))return;
    if(e.dataset.setPiece){
      return command({action:'set_piece',role:e.dataset.setPiece,rank:Number(e.dataset.rank),player_id:e.value},'Set-piece order saved.');
    }
    if(e.dataset.change==='preset'){
      if(e.value==='custom')return;
      return command({action:'preset',id:e.value},'Tactical preset applied in Python.');
    }
    if(e.dataset.change==='role')return command({action:'role',slot_id:e.dataset.slotId,role_id:e.value},'Role updated in Python.');
    if(e.dataset.individual){return command({action:'player_instruction',slot_id:selectedSlot,field:e.dataset.individual,value:e.value},'Individual instruction saved in Python.');}
    if(e.dataset.tacticField){
      lastEdit=e.dataset.tacticField.replaceAll('_',' ');
      return command({action:'team_instruction',group:e.dataset.tacticGroup,field:e.dataset.tacticField,value:e.value},'Team instruction saved in Python.');
    }
    if(e.dataset.rangeField){
      const item=fieldInfo(e.dataset.rangeGroup,e.dataset.rangeField);
      const option=item.options[Number(e.value)];
      lastEdit=item.label;
      return command({action:'team_instruction',group:item.group,field:item.field,value:option},'Team instruction saved in Python.');
    }
  });
  root.addEventListener('input',event=>{
    const e=event.target;
    if(e.id==='fm-formation-search'){
      pickerSearch=e.value;redrawFormationDialog(true);return;
    }
    if(pickerOpen)return;
    if(screen==='squad' && window.FMRoster.onInput(e, refreshKeepingTable))return;
    if(!e.dataset.rangeField || !data)return;
    const item=fieldInfo(e.dataset.rangeGroup,e.dataset.rangeField);
    const value=item.options[Number(e.value)];
    item.value=value;
    const label=e.closest('.fm-control').querySelector('[data-field-label]');if(label)label.textContent=short(value);
    lastEdit=item.label;
    refreshBoard();
  });
  let dragSlot=null;
  root.addEventListener('dragstart',e=>{
    const button=e.target.closest('[data-player-slot]');
    if(!button||pickerOpen)return;
    dragSlot=button.dataset.playerSlot;e.dataTransfer.effectAllowed='move';
    e.dataTransfer.setData('text/plain',dragSlot);
  });
  root.addEventListener('dragover',e=>{
    const target=e.target.closest('[data-player-slot]');
    if(target&&dragSlot&&!pickerOpen){e.preventDefault();e.dataTransfer.dropEffect='move';}
  });
  root.addEventListener('drop',e=>{
    const target=e.target.closest('[data-player-slot]');
    if(!target||!dragSlot||pickerOpen)return;
    e.preventDefault();const first=dragSlot,second=target.dataset.playerSlot;dragSlot=null;
    if(first===second)return;
    selectedSlot=null;
    command({action:'swap_starters',first,second},'Starting players swapped in Python.');
  });
  root.addEventListener('dragend',()=>{dragSlot=null;});
  window.addEventListener('keydown',event=>{
    if(!pickerOpen)return;
    if(event.key==='Escape'){
      event.preventDefault();closeFormationDialog();return;
    }
    if(event.key!=='Tab')return;
    const dialog=$('.fm-formation-modal');
    const focusables=dialog?Array.from(dialog.querySelectorAll('button:not([disabled]), input:not([disabled])')):[];
    if(!focusables.length)return;
    const first=focusables[0],last=focusables[focusables.length-1];
    if(event.shiftKey&&document.activeElement===first){event.preventDefault();last.focus();}
    else if(!event.shiftKey&&document.activeElement===last){event.preventDefault();first.focus();}
  });
  window.addEventListener('resize',()=>requestAnimationFrame(positionLineupCards));
  window.addEventListener('message',event=>{
    if(event.source!==parent || event.origin!==window.location.origin)return;
    if(event.data?.type==='fm-squad-refresh' && !busy){load();return;}
    if(event.data?.type==='fm-open-squad'){const next=event.data.view==='tactics'?'tactics':'squad';if(next!==screen){screen=next;tacticMode='lineup';selectedSlot=null;benchToSwap=null;pickerOpen=false;}render();}
  });
  window.FMRoster.reload=load;
  if(params.get('player'))window.FMRoster.state.expanded=params.get('player');
  window.addEventListener('focus',()=>{if(!busy)load();});
  load();
})();
