'use strict';
/* TS-23.1 Academy presentation and youth scouting; vanilla browser JS, no Node. */
(() => {
  let host = null, state = null, tab = 'u17', loading = false, marketOpen = false;
  let candidateFilter = {position:'all', region:'all', scout:'all', risk:'all', sort:'potential'};
  let squadFilter = {query:'',position:'all',sort:'rating'};
  const esc = val => String(val ?? '').replace(/[&<>"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
  const money = n => '£' + Math.max(0,Number(n)||0).toLocaleString('en-GB',{maximumFractionDigits:0});
  const rating = n => Number(n ?? 0).toFixed(1);
  const shortDate = s => {if(!s)return 'Not assigned';const [y,m,d]=s.split('-');return `${d}/${m}/${y}`;};
  const countries = ['England','Scotland','Wales','Ireland','Northern Ireland','Brazil','Argentina','France','Spain','Germany','Portugal','Netherlands','Italy','Nigeria','Ghana','Japan','Colombia','Uruguay'];
  const profiles = [['any','Any position'],['GK','Goalkeepers'],['CB','Centre backs'],['FB','Full backs'],['MID','Midfielders'],['WIDE','Wide players'],['ST','Strikers']];
  const symbol = (name) => ({squad:'♙',academy:'✦',players:'♟',budget:'◈',calendar:'▦',target:'◎',form:'▥',scout:'⌕',stars:'✧',position:'⛶',arrow:'↗',clock:'◷'}[name]||'✦');
  const unique = values => [...new Set(values)].filter(Boolean).sort((a,b)=>String(a).localeCompare(String(b)));
  const option = (value,label,chosen) => `<option value="${esc(value)}"${String(value)===String(chosen)?' selected':''}>${esc(label)}</option>`;
  const select = (id, opts, value, label) => `<label class="ya-filter"><span>${esc(label)}</span><select data-youth-filter="${id}" aria-label="${esc(label)}">${opts.map(([v,t])=>option(v,t,value)).join('')}</select></label>`;
  const projectionClass = s => /Exceptional|Elite|Very promising/i.test(s)?'elite':/Promising/i.test(s)?'promising':/Limited/i.test(s)?'limited':'ordinary';
  const projection = s => `<span class="ya-tag ya-tag-${projectionClass(s)}">${esc(s||'Developing')}</span>`;
  const initials = full => String(full||'?').split(' ').map(s=>s[0]).slice(0,2).join('').toUpperCase();
  const portrait = (p, big=false) => `<span class="ya-avatar${big?' ya-avatar-lg':''}" aria-hidden="true"><span class="ya-avatar-figure"><span class="ya-avatar-head"></span><span class="ya-avatar-body"></span></span><span class="ya-avatar-badge">${esc(initials(p.name))}</span></span>`;
  const youthPortrait = p => `<span class="ya-roster-portrait">${window.FMPortraits?.portrait?.(p, 'ya-roster-face') || portrait(p)}</span>`;
  const stat = (icon,value,label,sub='') => `<div class="ya-stat"><span class="ya-stat-icon">${symbol(icon)}</span><strong>${esc(value)}</strong><span>${esc(label)}</span>${sub?`<small>${esc(sub)}</small>`:''}</div>`;
  const formattedCountry = c => esc(c==='Northern Ireland'?'N. Ireland':c);
  function header(title, description, stats, icon='academy'){
    return `<section class="ya-hero"><div class="ya-hero-intro"><span class="ya-hero-icon" aria-hidden="true">${symbol(icon)}</span><div><div class="ya-eyebrow">YOUTH DEVELOPMENT · ${esc(state.season)}</div><h2>${esc(title)}</h2><p>${esc(description)}</p></div></div><div class="ya-hero-stats">${stats.join('')}</div></section>`;
  }
  function playerLines(p){return `<strong>${esc(p.name)}</strong><small>${esc(p.age)} years · ${formattedCountry(p.country)}</small>`;}
  function field(){
    const order = ['GK','LB','LCB','RCB','RB','DM','LCM','RCM','LW','ST','RW'];
    const players = [...(state.u15||[])].sort((a,b)=>b.ovr-a.ovr||a.name.localeCompare(b.name));
    const groups = [ ['GK'],['LB','LWB'],['LCB','CB','RCB'],['RCB','CB','LCB'],['RB','RWB'],['DM','CM'],['LCM','CM','AM'],['RCM','CM','AM'],['LW'],['ST'],['RW'] ];
    const eleven = groups.map((roles,i)=>{
      const idx=players.findIndex(p=>roles.includes(p.position));
      return players.splice(idx===-1?0:idx,1)[0] || null;
    });
    function token(i){
      const p=eleven[i];if(!p)return '<div class="ya-u15-card ya-u15-placeholder">Vacant</div>';
      return `<div class="ya-u15-card" title="${esc(p.name)} · ${esc(p.projection)}"><span class="ya-pitch-avatar">${esc(initials(p.name))}</span><div><span class="ya-u15-position">${esc(order[i])}</span><strong>${esc(p.name.split(' ').slice(-1)[0])}</strong><small>${p.age} yrs</small></div>${projection(p.projection==='Limited projection'?'Limited':p.projection)}</div>`;
    }
    const fieldLine = (...positions) => `<div class="ya-field-line">${positions.map(token).join('')}</div>`;
    const eligible = state.u15.filter(p=>p.upcoming).length;
    const top = state.u15.filter(p=>/Exceptional|Very promising/.test(p.projection||'')).length;
    const distribution = new Set(state.u15.map(p=>p.position)).size;
    return `${header('Next academy intake · U15','Your future academy class, already registered and developing behind the scenes. This is a read-only preview.',[
      stat('players',state.u15.length,'Young prospects'),stat('arrow',eligible,'Promotion eligible','At next season rollover'),stat('position',distribution,'Natural positions'),stat('stars',top,'Top projections')],'academy')}
      <div class="ya-main-grid ya-intake-layout"><section class="ya-panel ya-pitch-panel"><div class="ya-section-title"><div><h3>Projected starting XI</h3><p>Automatic 4-3-3 based on the currently available players</p></div><span class="ya-small-pill">Preview only</span></div>
      <div class="ya-field"><div class="ya-field-outline"></div><div class="ya-field-box ya-field-box-top"></div><div class="ya-field-circle"></div><div class="ya-field-box ya-field-box-bottom"></div>
      ${fieldLine(8,9,10)}${fieldLine(6,5,7)}${fieldLine(1,2,3,4)}${fieldLine(0)}</div></section>
      <section class="ya-panel ya-bench-panel"><div class="ya-section-title"><div><h3>Bench & other prospects</h3><p>${players.length} additional players</p></div><span class="ya-small-pill">U15</span></div>
      <div class="ya-bench-list">${players.map(p=>`<div class="ya-bench-row">${portrait(p)}<span class="ya-bench-identity"><strong>${esc(p.name)}</strong><small>${p.position} · ${p.age} yrs · GRL ${rating(p.ovr)}</small></span>${projection(p.projection)}</div>`).join('')}</div></section></div>
      <div class="ya-pathway"><div><strong>Academy pathway</strong><small>Age determines promotion eligibility; opening this page does not advance anyone.</small></div><div class="ya-pathway-track"><span class="is-current">U15</span><b>→</b><span>U17</span><b>→</b><span>U21</span><b>→</b><span>First team</span></div></div>`;
  }
  function squadLayout(players){
    const pool=[...(players||[])].sort((a,b)=>b.ovr-a.ovr||a.name.localeCompare(b.name));
    const order=['GK','LB','LCB','RCB','RB','DM','LCM','RCM','LW','ST','RW'];
    const groups=[['GK'],['LB','LWB'],['LCB','CB','RCB'],['RCB','CB','LCB'],['RB','RWB'],['DM','CM'],['LCM','CM','AM'],['RCM','CM','AM'],['LW'],['ST'],['RW']];
    const eleven=groups.map(roles=>{
      const idx=pool.findIndex(p=>roles.includes(p.position));
      return pool.splice(idx===-1?0:idx,1)[0]||null;
    });
    return {order, eleven, bench: pool};
  }
  function lineupCard(p, fallbackPos=''){
    if(!p)return `<div class="ya-formation-chip ya-formation-vacant"><span>${esc(fallbackPos)}</span><small>Vacant</small></div>`;
    const shortName=String(p.name||'').split(' ').slice(-1)[0]||p.name;
    return `<div class="ya-formation-chip" title="${esc(p.name)} · ${esc(p.position)} · GRL ${rating(p.ovr)}">
      <div class="ya-chip-upper">${youthPortrait(p)}<span class="ya-chip-rating"><strong>${rating(p.ovr)}</strong><small>GRL</small></span></div>
      <div class="ya-chip-lower"><strong>${esc(shortName)}</strong><span>${esc(p.position||fallbackPos)} · ${esc(p.age)} yrs</span></div>
    </div>`;
  }
  function formationBoard(level, players){
    const {order, eleven}=squadLayout(players);
    const row=(group,...indexes)=>`<div class="ya-formation-row ya-formation-row-${group}">${indexes.map(i=>lineupCard(eleven[i],order[i])).join('')}</div>`;
    return `<section class="ya-panel ya-squad-board-panel">
      <div class="ya-section-title"><div><h3>${level.toUpperCase()} · Projected XI</h3><p>Visual 4-3-3 preview based on player ratings and positions — youth matches remain automatic.</p></div><span class="ya-small-pill">View only · 4-3-3</span></div>
      <div class="ya-formation-pitch" role="group" aria-label="${level.toUpperCase()} projected 4-3-3 starting eleven">
        <div class="ya-pitch-boundary"></div><div class="ya-pitch-half-line"></div><div class="ya-pitch-center-circle"></div>
        <div class="ya-pitch-penalty ya-pitch-penalty-top"></div><div class="ya-pitch-penalty ya-pitch-penalty-bottom"></div>
        ${row('attack',8,9,10)}${row('midfield',6,5,7)}${row('defence',1,2,3,4)}${row('keeper',0)}
      </div>
    </section>`;
  }
  function youthLeague(level){
    const st=state.standings?.[level]||[];const ours=st.find(x=>x.club_id===state.club_id);
    const rank=st.findIndex(x=>x.club_id===state.club_id);
    const games=state.fixtures?.[level]||[];
    const next=games.find(f=>!f.score),latest=games.filter(f=>f.score).slice(-4).reverse();
    return `<aside class="ya-league-rail"><div class="ya-panel ya-rail-card"><div class="ya-section-title"><h3>Next youth match</h3></div>${next?`<div class="ya-opp-icon">${symbol('squad')}</div><strong>${esc(next.opponent)}</strong><p>${shortDate(next.date)} · ${next.home?'Home':'Away'}</p>`:'<p>No upcoming match scheduled.</p>'}</div>
      <div class="ya-panel ya-rail-card"><div class="ya-section-title"><h3>Recent results</h3></div>${latest.length?latest.map(g=>`<div class="ya-result"><span>${g.home?'H':'A'}</span><b>${esc(g.opponent)}</b><strong>${esc(g.score)}</strong></div>`).join(''):'<p>No youth fixtures completed yet.</p>'}</div>
      <div class="ya-panel ya-rail-card"><div class="ya-section-title"><h3>${level.toUpperCase()} league table</h3><span class="ya-small-pill">${st.length} clubs</span></div><div class="ya-standings">${st.slice(0,8).map((r,i)=>`<div class="ya-standing${r.club_id===state.club_id?' is-own':''}"><span>${i+1}</span><strong>${esc(r.club)}</strong><span>${r.played} P</span><b>${r.points} pts</b></div>`).join('')}</div>${rank>=8?`<div class="ya-standing is-own"><span>${rank+1}</span><strong>${esc(ours.club)}</strong><span>${ours.played} P</span><b>${ours.points} pts</b></div>`:''}</div></aside>`;
  }
  function roster(level){
    const players=state[level]||[];const table=state.league_tables?.[level]||{};
    const av=players.length?players.reduce((sum,p)=>sum+p.ovr,0)/players.length:0;
    const ready=players.filter(p=>p.ovr>=60).length;
    const ranking=(state.standings?.[level]||[]).findIndex(x=>x.club_id===state.club_id);
    const choices=unique(players.map(p=>p.position));
    const matched=players.filter(p=>(squadFilter.position==='all'||squadFilter.position===p.position)&&
      `${p.name} ${p.country} ${p.position}`.toLowerCase().includes(squadFilter.query.toLowerCase()));
    matched.sort((a,b)=>squadFilter.sort==='age'?a.age-b.age:
      squadFilter.sort==='name'?a.name.localeCompare(b.name):b.ovr-a.ovr);
    return `${header(`${level.toUpperCase()} / ${level==='u21'?'Reserves':'Academy'}`,'Automatic youth matches, individual development and promotion decisions. No manual match-day management.',[
      stat('players',players.length,'Squad size'),stat('stars',rating(av),'Average GRL'),stat('calendar',table.played||0,'Games played'),stat('form',ranking>=0&&table.played?`#${ranking+1}`:'—','League position'),stat('arrow',ready,'GRL 60+ prospects')],'squad')}
      <div class="ya-main-grid ya-roster-layout"><div class="ya-roster-stack">${formationBoard(level, players)}<section class="ya-panel"><div class="ya-section-title"><div><h3>${level.toUpperCase()} squad <span class="ya-muted">(${players.length})</span></h3><p>Player management · promote, move or release players below</p></div></div>
      <div class="ya-roster-toolbar"><input type="search" id="ya-squad-query" aria-label="Search youth players" placeholder="Search player, position, nationality" value="${esc(squadFilter.query)}" />${select('squadPosition',[['all','All positions'],...choices.map(p=>[p,p])],squadFilter.position,'Position')}${select('squadSort',[['rating','GRL: highest'],['age','Age: youngest'],['name','Name: A–Z']],squadFilter.sort,'Sort')}</div>
      <div class="ya-table-scroll"><table class="ya-data-table"><thead><tr><th>Player</th><th>Pos</th><th>Age</th><th>GRL</th><th>Development</th><th>Match rhythm</th><th>Actions</th></tr></thead><tbody>${matched.map(p=>{
        const percent=Math.max(0,Math.min(100,p.sharpness||0));
        const trend=(p.development_delta||0)>.05?'positive':(p.development_delta||0)<-.05?'negative':'neutral';
        return `<tr><td><div class="ya-person-cell">${youthPortrait(p)}<span>${playerLines(p)}</span></div></td><td><span class="ya-position-pill">${esc(p.position)}</span></td><td>${p.age}</td><td><span class="ya-grl">${rating(p.ovr)}</span></td><td><span class="ya-trend ${trend}">${trend==='positive'?'↗':trend==='negative'?'↘':'→'} ${esc(p.projection)}</span></td><td><div class="ya-sharp"><span style="width:${percent}%"></span></div><small>${Math.round(percent)}%</small></td><td><div class="ya-row-actions"><button data-youth-action="move" data-target="first" data-id="${esc(p.id)}" class="ya-btn ya-btn-primary">Promote</button><button data-youth-action="move" data-target="${level==='u17'?'u21':'u17'}" data-id="${esc(p.id)}" class="ya-btn" ${level==='u21'&&p.age>17?'disabled title="Over age for U17"':''}>${level==='u17'?'U21':'U17'}</button><button data-youth-action="release" data-id="${esc(p.id)}" class="ya-btn ya-btn-danger">Release</button></div></td></tr>`;
      }).join('')}</tbody></table></div>${!matched.length?'<p class="ya-empty-inline">No players match the selected filters.</p>':''}</section></div>${youthLeague(level)}</div>`;
  }
  function scoutCard(slot){
    const scout=(state.scouts||[]).find(s=>s.id===`scout-${slot}`);
    if(!scout)return `<article class="ya-scout-card ya-scout-open"><div class="ya-open-mark">+</div><h3>Scout ${slot}</h3><p>No scout hired</p><small>Recruit a youth scout to discover talent in different countries.</small><button class="ya-btn ya-btn-primary" data-youth-open-market="1">Hire scout</button></article>`;
    return `<article class="ya-scout-card"><div class="ya-scout-identity">${portrait(scout,true)}<div><span class="ya-green-label">● CONTRACTED</span><h3>${esc(scout.name)}</h3><p>Scout ${slot} · Judging ${scout.quality}/100</p></div></div><div class="ya-scout-details"><div><small>Judging ability</small><strong>${scout.quality}/100</strong></div><div><small>Monthly wage</small><strong>${money(scout.monthly_wage)}</strong></div></div><div class="ya-scout-contract"><span>Contract until</span><b>${scout.contract_until?shortDate(scout.contract_until):'Existing agreement'}</b></div>
     <form data-youth-scout="${esc(scout.id)}" class="ya-scout-form"><div class="ya-scout-inputs">${select('country',countries.map(c=>[c,c]),scout.country,'Destination')}${select('position',profiles,scout.position,'Profile')}</div><div class="ya-scout-deadline"><span>Next report</span><strong>${shortDate(scout.next_report)}</strong></div><button class="ya-btn ya-btn-wide" type="submit">${scout.next_report?'Update 90-day mission':'Assign 90-day mission'} →</button></form><button class="ya-btn ya-btn-quiet ya-scout-release" data-youth-action="fire_scout" data-id="${esc(scout.id)}">End contract${scout.monthly_wage?` · ${money(scout.monthly_wage)}`:''}</button></article>`;
  }
  function candidateRows(){
    const candidates=(state.candidates||[]).filter(p=>(candidateFilter.position==='all'||p.position===candidateFilter.position)&&
      (candidateFilter.region==='all'||p.country===candidateFilter.region)&&
      (candidateFilter.scout==='all'||p.scout===candidateFilter.scout)&&
      (candidateFilter.risk==='all'||p.poaching_risk===candidateFilter.risk));
    const priority={High:3,Medium:2,Low:1};
    candidates.sort((a,b)=> candidateFilter.sort==='risk' ? (priority[b.poaching_risk]||0)-(priority[a.poaching_risk]||0):
      candidateFilter.sort==='age'?a.age-b.age: candidateFilter.sort==='recent'?b.discovered_on.localeCompare(a.discovered_on):
      (b.potential_range?.[1]||0)-(a.potential_range?.[1]||0));
    if(!candidates.length)return `<div class="ya-empty-prospects"><span aria-hidden="true">⌕</span><h3>${state.candidates.length?'No matches for these filters':'No discoveries yet'}</h3><p>${state.candidates.length?'Try adjusting the filters above.':'Hire a youth scout, assign a 90-day mission, and review the candidates when the report arrives.'}</p></div>`;
    return `<div class="ya-table-scroll"><table class="ya-data-table ya-prospect-table"><thead><tr><th>Player</th><th>Age</th><th>Position</th><th>GRL est.</th><th>Potential estimate</th><th>Report</th><th>Risk</th><th>Decision</th></tr></thead><tbody>${candidates.map(p=>`<tr><td><div class="ya-person-cell">${portrait(p)}<span><strong>${esc(p.name)}</strong><small>${formattedCountry(p.country)} · ${esc(p.scout)}</small></span></div></td><td>${p.age}</td><td><span class="ya-position-pill">${esc(p.position)}</span></td><td><span class="ya-grl">${rating(p.ovr_estimate)}</span></td><td><span class="ya-potential">${esc((p.potential_range||[]).join('–'))}</span> ${projection(p.projection)}</td><td><span class="ya-confidence">${esc(p.confidence)}</span></td><td><span class="ya-risk ya-risk-${String(p.poaching_risk||'low').toLowerCase()}">⚠ ${esc(p.poaching_risk||'Low')}</span></td><td><div class="ya-row-actions"><button class="ya-btn ya-btn-primary" data-youth-action="sign" data-id="${esc(p.id)}">Sign to academy</button><button class="ya-btn" data-youth-action="watch" data-id="${esc(p.id)}" ${p.status==='watching'?'disabled':''}>${p.status==='watching'?'On watchlist':'Keep tracked'}</button><button class="ya-btn ya-btn-quiet" data-youth-action="dismiss" data-id="${esc(p.id)}">✕</button></div></td></tr>`).join('')}</tbody></table></div>`;
  }
  function scouting(){
    const scouts=state.scouts||[];const count=scouts.length;const slots=state.scout_slots||3;
    const nextDates=scouts.map(s=>s.next_report).filter(Boolean).sort();
    return `${header('Youth scouting','Recruit specialist scouts, assign destinations and review new prospects every 90 days. Unsigned players can join rival clubs.',[
      stat('budget',money(state.recruitment_funds),'Recruitment allocation'),stat('budget',money(state.monthly_scout_cost),'Monthly wages'),stat('players',`${count} / ${slots}`,'Scouts hired'),stat('clock',nextDates.length?shortDate(nextDates[0]):'No mission','Next report')],'scout')}
      <section class="ya-scout-grid">${Array.from({length:slots},(_,i)=>scoutCard(i+1)).join('')}</section>
      <section class="ya-panel ya-prospects-section"><div class="ya-section-title"><div><h3>Discovered prospects <span class="ya-muted">(${state.candidates.length})</span></h3><p>Recruit now, or keep watching for a more accurate report. Waiting carries a genuine risk of another club signing the player.</p></div><span class="ya-risk-callout">⚠ Unsigned prospects can be poached</span></div>
      <div class="ya-prospect-filters">${select('candidatePosition',[['all','All positions'],...unique(state.candidates.map(p=>p.position)).map(p=>[p,p])],candidateFilter.position,'Position')}${select('candidateRegion',[['all','All countries'],...unique(state.candidates.map(p=>p.country)).map(p=>[p,p])],candidateFilter.region,'Country')}${select('candidateScout',[['all','All scouts'],...unique(state.candidates.map(p=>p.scout)).map(p=>[p,p])],candidateFilter.scout,'Scout')}${select('candidateRisk',[['all','All risks'],['Low','Low'],['Medium','Medium'],['High','High']],candidateFilter.risk,'Poaching risk')}${select('candidateSort',[['potential','Potential'],['risk','Risk'],['recent','Recently discovered'],['age','Youngest']],candidateFilter.sort,'Sort')}</div>
      ${candidateRows()}</section>
      ${(state.lost_prospects||[]).length?`<section class="ya-lost-history ya-panel"><h3>Signed by rival clubs</h3><p>These players were discovered but not signed in time.</p><div>${state.lost_prospects.slice(0,6).map(p=>`<span>${esc(p.name)} → ${esc(p.club)} · ${shortDate(p.date)}</span>`).join('')}</div></section>`:''}
      ${marketOpen?marketDialog():''}`;
  }
  function marketDialog(){
    const offers=state.market_offers||[];
    return `<div class="ya-modal-backdrop" data-youth-close-market="1"><section class="ya-modal" role="dialog" aria-modal="true" aria-label="Hire youth scout"><div class="ya-section-title"><div><h2>Hire a youth scout</h2><p>Signing fees are charged immediately. Monthly wages come from the separate academy recruitment allocation.</p></div><button type="button" class="ya-close" data-youth-close-market="1" aria-label="Close">✕</button></div><div class="ya-modal-budget">Available for scouting: <b>${money(state.recruitment_funds)}</b></div><div class="ya-offer-list">${offers.map(o=>`<div class="ya-offer"><div class="ya-person-cell">${portrait(o)}<span><strong>${esc(o.name)}</strong><small>Judging ${o.quality}/100</small></span></div><span><small>Signing fee</small><b>${money(o.signing_fee)}</b></span><span><small>Monthly wage</small><b>${money(o.monthly_wage)}</b></span><button class="ya-btn ya-btn-primary" data-youth-hire="${esc(o.id)}" ${o.signing_fee+o.monthly_wage>state.recruitment_funds?'disabled':''}>Hire</button></div>`).join('')}</div></section></div>`;
  }
  function render(){
    if(!host||!state)return;
    const content=tab==='u15'?field():tab==='scouts'?scouting():roster(tab);
    host.innerHTML=`<div class="ya-topline"><div><div class="ya-eyebrow">U17 · U21 · YOUTH DEVELOPMENT</div><p>Manage academy squads, upcoming intakes and your scouting network.</p></div><span class="ya-top-season">${esc(state.club_name)} · ${esc(state.season)}</span></div><div class="ya-tabs" role="tablist" aria-label="Academy views">${[['u17','U17'],['u21','U21 / Reserves'],['u15','Next academy intake'],['scouts','Youth scouts']].map(([id,label])=>`<button type="button" role="tab" data-youth-tab="${id}" aria-selected="${tab===id}">${label}</button>`).join('')}</div><div class="ya-body">${content}</div>`;
    host.setAttribute('aria-busy',String(loading));
  }
  async function command(payload){
    if(loading)return;
    loading=true;host.setAttribute('aria-busy','true');
    try{
      const res=await fetch('/api/youth',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
      const data=await res.json();if(!res.ok)throw Error(data.error||`HTTP ${res.status}`);
      if(payload.action==='hire_scout')marketOpen=false;
      await refresh();
    }catch(err){window.alert(`Youth Academy: ${err.message}`);}finally{loading=false;host?.setAttribute('aria-busy','false');}
  }
  async function refresh(){
    if(!host)return;
    try{const res=await fetch('/api/youth',{cache:'no-store'});if(!res.ok)throw Error(`HTTP ${res.status}`);state=await res.json();render();}
    catch(err){host.innerHTML=`<section class="ya-panel"><h3>Academy unavailable</h3><p>${esc(err.message)}</p><button class="ya-btn" data-youth-refresh="1">Retry</button></section>`;}
  }
  function bindOnce(){
    host.addEventListener('click', async event=>{
      const el=event.target.closest('button,[data-youth-close-market]');if(!el||!host.contains(el))return;
      if(el.dataset.youthTab){tab=el.dataset.youthTab;marketOpen=false;render();return;}
      if(el.dataset.youthRefresh){await refresh();return;}
      if(el.dataset.youthOpenMarket){marketOpen=true;render();return;}
      if(el.dataset.youthCloseMarket){if(event.target===el||el.tagName==='BUTTON'){marketOpen=false;render();}return;}
      if(el.dataset.youthHire){const offer=state.market_offers.find(o=>o.id===el.dataset.youthHire);if(!offer)return;
        if(window.confirm(`Hire ${offer.name} for ${money(offer.signing_fee)} signing fee and ${money(offer.monthly_wage)} per month?`))await command({action:'hire_scout',offer_id:offer.id});return;
      }
      if(el.dataset.youthAction){const action=el.dataset.youthAction;
        if(action==='fire_scout'){
          const scout=state.scouts.find(s=>s.id===el.dataset.id);
          if(!window.confirm(`End ${scout?.name||'scout'} contract? Termination cost: ${money(scout?.monthly_wage)}.`))return;
          await command({action,scout_id:el.dataset.id});return;
        }
        if(['release','dismiss'].includes(action)&&!window.confirm(`Confirm ${action} for this player?`))return;
        if(action==='sign'&&!window.confirm('Sign this prospect to your academy? The player will leave your scouting list.'))return;
        await command({action,player_id:el.dataset.id,...(el.dataset.target?{target:el.dataset.target}:{})});
      }
    });
    host.addEventListener('submit',async event=>{
      const form=event.target.closest('[data-youth-scout]');if(!form)return;
      event.preventDefault();await command({action:'assign_scout',scout_id:form.dataset.youthScout,
        country:form.querySelector('[data-youth-filter="country"]').value,
        position:form.querySelector('[data-youth-filter="position"]').value});
    });
    host.addEventListener('change',event=>{
      const key=event.target.dataset.youthFilter;if(!key)return;
      const map={candidatePosition:'position',candidateRegion:'region',candidateScout:'scout',candidateRisk:'risk',candidateSort:'sort',squadPosition:'position',squadSort:'sort'};
      if(key in map){(key.startsWith('candidate')?candidateFilter:squadFilter)[map[key]]=event.target.value;render();}
    });
    host.addEventListener('input',event=>{
      if(event.target.id!=='ya-squad-query')return;
      squadFilter.query=event.target.value;
      const rows=host.querySelectorAll('.ya-data-table tbody tr');
      rows.forEach(row=>{row.hidden=!row.textContent.toLowerCase().includes(squadFilter.query.toLowerCase());});
    });
  }
  function mount(element){if(host!==element){host=element;bindOnce();}host.innerHTML='<div class="ya-panel">Loading academy...</div>';refresh();}
  window.FMYouthAcademy=Object.freeze({mount,refresh});
})();
