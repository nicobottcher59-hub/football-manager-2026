'use strict';
/* TS-23.1 Academy presentation and youth scouting; vanilla browser JS, no Node. */
(() => {
  let host = null, state = null, tab = 'u17', loading = false, marketOpen = false, negotiation = null, feedback = null;
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
  const personIcon = `<svg viewBox="0 0 24 24" aria-hidden="true" focusable="false"><circle cx="12" cy="8" r="4"/><path d="M4 21v-2c0-4.5 3-7 8-7s8 2.5 8 7v2"/></svg>`;
  const initials = full => String(full||'?').split(' ').map(s=>s[0]).slice(0,2).join('').toUpperCase();
  const portrait = (p, big=false) => `<span class="ya-avatar${big?' ya-avatar-lg':''}" aria-hidden="true"><span class="ya-avatar-figure"><span class="ya-avatar-head"></span><span class="ya-avatar-body"></span></span><span class="ya-avatar-badge">${esc(initials(p.name))}</span></span>`;
  const youthPortrait = p => `<span class="ya-roster-portrait">${window.FMPortraits?.portrait?.(p, 'ya-roster-face') || portrait(p)}</span>`;
  // Stable club IDs belong to the Python football world. Display names, crests
  // and colours are resolved independently through the shared club catalogue.
  const clubIdentity = (id, name) => window.FMClubIdentity?.resolve?.(id,name) ||
    {id,display_name:name||id||'Club',short_name:name||id||'Club',crest:null};
  const clubDisplayName = (id,name) => clubIdentity(id,name).display_name || name || id || 'Club';
  const clubEmblem = (id,name) => {
    const identity=clubIdentity(id,name);
    return identity.crest
      ? `<img class="ya-table-crest" src="${esc(identity.crest)}" alt="" loading="lazy">`
      : '';
  };
  const stat = (icon,value,label,sub='') => `<div class="ya-stat"><span class="ya-stat-icon">${symbol(icon)}</span><strong>${esc(value)}</strong><span>${esc(label)}</span>${sub?`<small>${esc(sub)}</small>`:''}</div>`;
  const formattedCountry = c => esc(c==='Northern Ireland'?'N. Ireland':c);
  const potentialLabel = p => Array.isArray(p?.potential_range) && p.potential_range.length===2
    ? `~${p.potential_range[0]}–${p.potential_range[1]}` : '—';
  const potentialStars = p => {
    if (!Array.isArray(p?.potential_range)) return '';
    const centre=(Number(p.potential_range[0])+Number(p.potential_range[1]))/2;
    const stars=Math.max(1,Math.min(5,Math.round((centre-26)/13)));
    return `<span class="ya-stars" aria-label="Approximate potential: ${esc(potentialLabel(p))}">${'★'.repeat(stars)}<span>${'★'.repeat(5-stars)}</span></span>`;
  };
  function header() {return '';} // Global shared club hero precedes navigation tabs.
  function clubHero(){
    const club = clubIdentity(state.club_id,state.club_name);
    const clubName = String(club.display_name || state.club_name || 'Club');
    const shortClubName = String(club.short_name || clubName);
    const printedName = clubName.length>34 && shortClubName.length<clubName.length ? shortClubName : clubName;
    const crest=club.crest?`<img src="${esc(club.crest)}" alt="" loading="eager">`:
      '<span class="ya-club-fallback" aria-hidden="true">⚽</span>';
    let title='',description='',stats=[];
    if(tab==='u17'||tab==='u21'){
      const players=state[tab]||[],avg=players.length?players.reduce((x,p)=>x+Number(p.ovr||0),0)/players.length:0;
      const played=state.league_tables?.[tab]?.played||0;
      const standing=(state.standings?.[tab]||[]).findIndex(p=>p.club_id===state.club_id);
      title=tab==='u17'?'U17 / Academy':'U21 / Reserves';
      description='Automatic youth matches · Development · Promotions';
      stats=[['players',players.length,'Players'],['stars',rating(avg),'Average GRL'],['calendar',played,'Matches'],['arrow',played&&standing>=0?'#'+(standing+1):'—','League place']];
    }else if(tab==='u15'){
      title='Next academy intake · U15';description='Early talent assessment · Upcoming academy generation';
      stats=[['players',state.u15.length,'Prospects'],['arrow',state.u15.filter(p=>p.upcoming).length,'Eligible next year'],
             ['position',new Set(state.u15.map(p=>p.position)).size,'Positions'],
             ['stars',state.u15.filter(p=>/Very promising|Exceptional/.test(p.projection)).length,'Top projections']];
    }else{
      const scouts=state.scouts||[],reports=scouts.map(s=>s.next_report).filter(Boolean).sort();
      title='Youth scouting';description='Scout talent, review reports and sign to U17';
      stats=[['budget',money(state.recruitment_funds),'Academy funds'],['players',`${scouts.length}/${state.scout_slots||3}`,'Scouts'],
             ['stars',(state.candidates||[]).length,'Prospects'],['clock',reports.length?shortDate(reports[0]):'—','Next report']];
    }
    return `<header class="ya-club-hero" aria-label="Youth Academy club header">
      <div class="ya-hero-identity"><div class="ya-hero-crest">${crest}</div>
        <div class="ya-hero-copy"><span class="ya-hero-overline"><span class="ya-hero-club-name" title="${esc(clubName)}">${esc(printedName)}</span><span class="ya-hero-context">YOUTH DEVELOPMENT</span></span>
          <h2>${esc(title)}</h2><p>${esc(description)}</p></div></div>
      <div class="ya-club-hero-kpis">${stats.map(([ic,v,t])=>`<span class="ya-hero-kpi"><i>${symbol(ic)}</i><strong>${esc(v)}</strong><small>${esc(t)}</small></span>`).join('')}</div>
    </header>`;
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
      return `<div class="ya-u15-card" title="${esc(p.name)} · ${esc(p.projection)} · Potential ${esc(potentialLabel(p))}"><span class="ya-pitch-avatar">${esc(initials(p.name))}</span><div><span class="ya-u15-position">${esc(order[i])}</span><strong>${esc(p.name.split(' ').slice(-1)[0])}</strong><small>${p.age} yrs</small></div>${potentialStars(p)}${projection(p.projection==='Limited projection'?'Limited':p.projection)}</div>`;
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
      <div class="ya-bench-list">${players.map(p=>`<div class="ya-bench-row">${portrait(p)}<span class="ya-bench-identity"><strong>${esc(p.name)}</strong><small>${p.position} · ${p.age} yrs · GRL ${rating(p.ovr)}</small></span>${potentialStars(p)}${projection(p.projection)}</div>`).join('')}</div></section></div>
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
    const st=state.standings?.[level]||[];
    const isManaged = row=>String(row.club_id)===String(state.club_id);
    const managedRank=st.findIndex(isManaged);
    const fixtures=state.fixtures?.[level]||[];
    const next=fixtures.find(f=>!f.score),latest=fixtures.filter(f=>f.score).slice(-4).reverse();
    const visible=st.slice(0,8).map((row,index)=>[row,index]);
    if(managedRank>=8)visible.push([st[managedRank],managedRank]);
    const standingRow=([row,index])=>{
      const name=clubDisplayName(row.club_id,row.club);
      return `<div class="ya-standing${isManaged(row)?' is-own':''}" ${isManaged(row)?'aria-label="Your club in the youth league"':''}>
        <span class="ya-standing-rank">${index+1}</span>
        <span class="ya-standing-identity">${clubEmblem(row.club_id,row.club)}<strong title="${esc(name)}">${esc(name)}</strong></span>
        <span>${Number(row.played)||0} P</span><b>${Number(row.points)||0} pts</b>
      </div>`;
    };
    const opponent = g=>clubDisplayName(g.opponent_club_id,g.opponent);
    return `<aside class="ya-league-rail">
      <div class="ya-panel ya-rail-card"><div class="ya-section-title"><h3>Next youth match</h3></div>
        ${next?`<div class="ya-opp-icon">${clubEmblem(next.opponent_club_id,next.opponent)||symbol('squad')}</div>
        <strong>${esc(opponent(next))}</strong><p>${shortDate(next.date)} · ${next.home?'Home':'Away'}</p>`:
        '<p>No upcoming match scheduled.</p>'}</div>
      <div class="ya-panel ya-rail-card"><div class="ya-section-title"><h3>Recent results</h3></div>
        ${latest.length?latest.map(g=>`<div class="ya-result"><span>${g.home?'H':'A'}</span><b>${esc(opponent(g))}</b><strong>${esc(g.score)}</strong></div>`).join(''):
        '<p>No youth fixtures completed yet.</p>'}</div>
      <div class="ya-panel ya-rail-card"><div class="ya-section-title"><h3>${level.toUpperCase()} league table</h3><span class="ya-small-pill">${st.length} clubs</span></div>
        <div class="ya-standings">${visible.map(standingRow).join('')}</div></div>
    </aside>`;
  }
  function roster(level){
    const players=state[level]||[];
    const positions=unique(players.map(p=>p.position));
    const matched=players.filter(p=>(squadFilter.position==='all'||p.position===squadFilter.position)&&
      `${p.name} ${p.country} ${p.position}`.toLowerCase().includes(squadFilter.query.toLowerCase()));
    matched.sort((a,b)=>squadFilter.sort==='age'?a.age-b.age:
      squadFilter.sort==='name'?a.name.localeCompare(b.name):b.ovr-a.ovr);
    const cards=matched.map(p=>{
      const percent=Math.max(0,Math.min(100,Number(p.sharpness)||0));
      const recentGain=Number(p.development_delta)||0;
      const trend=recentGain>0.05?'↗':recentGain < -0.05?'↘':'→';
      const promotedTo=level==='u17'?'u21':'u17';
      const academyAction=level==='u17'?'Promote to U21':'Move to U17';
      const ageLimited=level==='u21'&&Number(p.age)>17;
      // A player aged 18+ is genuinely ineligible for U17 in the Python engine.
      // Never display an enabled-looking action that the engine would reject.
      const moveAction=ageLimited
        ? `<span class="ya-age-note" title="U17 players must be 17 or younger">U17 age limit</span>`
        : `<button class="ya-btn ya-btn-academy" data-youth-action="move" data-target="${promotedTo}" data-id="${esc(p.id)}">${academyAction}</button>`;
      const minutes=Math.max(0,Math.round(Number(p.minutes)||0));
      const gainLabel=(recentGain>0?'+':'')+recentGain.toFixed(2);
      const currentLevel=level==='u17'?'U17 academy':'U21 reserves';
      return `<article class="ya-roster-card" data-search="${esc(`${p.name} ${p.country} ${p.position}`.toLowerCase())}">
        <div class="ya-roster-main">${youthPortrait(p)}<div class="ya-roster-name"><strong>${esc(p.name)}</strong>
          <small>${esc(p.age)} yrs · ${formattedCountry(p.country)}</small><span class="ya-roster-group">${currentLevel}</span></div>
          <span class="ya-position-pill">${esc(p.position)}</span>
          <span class="ya-card-ovr"><small>GRL</small><strong>${rating(p.ovr)}</strong></span></div>
        <div class="ya-roster-metrics">
          <span class="ya-approx"><small>Potential estimate</small><strong>${potentialStars(p)}${esc(potentialLabel(p))}</strong><em>Approximate range</em></span>
          <span class="ya-card-development"><small>Development</small><strong>${trend} ${esc(p.projection||'Adapting')}</strong><em>Recent gain ${esc(gainLabel)}</em></span>
          <span class="ya-card-minutes"><small>Youth minutes</small><strong>${minutes.toLocaleString('en-GB')}</strong><em>Recorded total</em></span>
          <span class="ya-card-rhythm"><small>Match sharpness</small><i><b style="width:${percent}%"></b></i><strong>${Math.round(percent)}%</strong></span>
        </div>
        <div class="ya-roster-actions">${moveAction}
          <button class="ya-btn ya-btn-first" data-youth-action="move" data-target="first" data-id="${esc(p.id)}">Promote to 1st team</button>
          <button class="ya-btn ya-btn-danger ya-btn-release" data-youth-action="release" data-id="${esc(p.id)}">Release</button></div>
      </article>`;
    }).join('');
    return `<div class="ya-main-grid ya-roster-layout"><div class="ya-roster-stack">${formationBoard(level,players)}</div>${youthLeague(level)}</div>
      <section class="ya-panel ya-youth-squad-panel"><div class="ya-section-title"><div><h3>${level.toUpperCase()} squad <span class="ya-muted">(${players.length})</span></h3><p>Academy players · approximate potential · promotions</p></div><span class="ya-small-pill">${matched.length} displayed</span></div>
      <div class="ya-roster-toolbar"><input type="search" id="ya-squad-query" aria-label="Search youth players" placeholder="Search player, position or nationality" value="${esc(squadFilter.query)}">
        ${select('squadPosition',[['all','All positions'],...positions.map(v=>[v,v])],squadFilter.position,'Position')}
        ${select('squadSort',[['rating','GRL: highest'],['age','Age: youngest'],['name','Name: A–Z']],squadFilter.sort,'Sort')}</div>
      <div class="ya-roster-cards">${cards}</div>${!matched.length?'<p class="ya-empty-inline">No players match these filters.</p>':''}</section>`;
  }
  function scoutCard(slot){
    const scout=(state.scouts||[]).find(s=>s.id===`scout-${slot}`);
    if(!scout)return `<article class="ya-scout-card ya-scout-open"><div class="ya-open-mark">+</div><h3>Scout ${slot}</h3><p>Vacant position</p>
      <small>Recruit a specialist to discover youth talent.</small><button class="ya-btn ya-btn-primary" data-youth-open-market="1">Recruit scout</button></article>`;
    return `<article class="ya-scout-card ya-scout-employed"><div class="ya-scout-identity"><span class="ya-scout-person" aria-hidden="true">${personIcon}</span>
      <div><span class="ya-green-label">● CONTRACTED</span><h3>${esc(scout.name)}</h3><p>Scout ${slot} · Judging ${scout.quality}/100</p></div></div>
      <div class="ya-scout-details"><div><small>Judging quality</small><strong>${scout.quality}/100</strong></div><div><small>Monthly wage</small><strong>${money(scout.monthly_wage)}</strong></div></div>
      <div class="ya-scout-contract"><span>Contract expires</span><b>${shortDate(scout.contract_until)}</b></div>
      <form data-youth-scout="${esc(scout.id)}" class="ya-scout-form"><div class="ya-scout-inputs">
        ${select('country',countries.map(c=>[c,c]),scout.country,'Scouting destination')}
        ${select('position',profiles,scout.position,'Positional focus')}</div>
        <div class="ya-scout-deadline"><span>Next report</span><strong>${shortDate(scout.next_report)}</strong></div>
        <button class="ya-btn ya-btn-wide" type="submit">${scout.next_report?'Update scouting mission':'Assign 90-day mission'} →</button></form>
      <div class="ya-scout-actions"><button class="ya-btn ya-btn-soft" data-youth-negotiate-scout="${esc(scout.id)}">Open negotiations</button>
      <button class="ya-btn ya-btn-quiet" data-youth-action="fire_scout" data-id="${esc(scout.id)}">End contract</button></div></article>`;
  }
  function candidateRows(){
    const candidates=(state.candidates||[]).filter(p=>(candidateFilter.position==='all'||p.position===candidateFilter.position)&&
      (candidateFilter.region==='all'||p.country===candidateFilter.region)&&
      (candidateFilter.scout==='all'||p.scout===candidateFilter.scout)&&
      (candidateFilter.risk==='all'||p.poaching_risk===candidateFilter.risk));
    const priority={High:3,Medium:2,Low:1};
    candidates.sort((a,b)=>candidateFilter.sort==='risk'?(priority[b.poaching_risk]||0)-(priority[a.poaching_risk]||0):
      candidateFilter.sort==='age'?a.age-b.age:candidateFilter.sort==='recent'?b.discovered_on.localeCompare(a.discovered_on):
      (b.potential_range?.[1]||0)-(a.potential_range?.[1]||0));
    if(!candidates.length)return `<div class="ya-empty-prospects"><span aria-hidden="true">⌕</span><h3>${state.candidates.length?'No matching players':'No discoveries yet'}</h3>
      <p>${state.candidates.length?'Adjust your filters.':'Once a scout completes a mission, discovered prospects appear here automatically.'}</p></div>`;
    const scoutName=id=>(state.scouts||[]).find(s=>s.id===id)?.name||id;
    return `<div class="ya-table-scroll"><table class="ya-data-table ya-prospect-table"><thead><tr><th>Player</th><th>Position</th><th>Age</th>
      <th>GRL estimate</th><th>Potential (approx.)</th><th>Scout</th><th>Confidence</th><th>Poaching risk</th><th>Decision</th></tr></thead><tbody>${candidates.map(p=>{
      const aged=Number(p.age)>17;
      return `<tr><td><div class="ya-person-cell"><span class="ya-prospect-person" aria-hidden="true">${personIcon}</span>
        <span><strong>${esc(p.name)}</strong><small>${formattedCountry(p.country)}</small></span></div></td>
        <td><span class="ya-position-pill">${esc(p.position)}</span></td><td>${esc(p.age)}</td><td><span class="ya-grl">~${rating(p.ovr_estimate)}</span></td>
        <td><span class="ya-prospect-potential">${potentialStars(p)}<b>${esc(potentialLabel(p))}</b><small>${esc(p.projection)}</small></span></td>
        <td><span class="ya-scout-ref">${esc(scoutName(p.scout))}</span></td><td><div class="ya-confidence-meter"><span style="width:${Math.min(100,Number(p.confidence_score)||0)}%"></span></div><b>${esc(p.confidence_score)}%</b></td>
        <td><span class="ya-risk ya-risk-${String(p.poaching_risk||'low').toLowerCase()}">${esc(p.poaching_risk||'Low')}</span></td>
        <td><button class="ya-btn ya-btn-primary ya-sign-btn" data-youth-action="sign" data-id="${esc(p.id)}" ${aged?'disabled title="Over the U17 age limit"':''}>Sign to U17</button></td></tr>`;
    }).join('')}</tbody></table></div>`;
  }
  function scouting(){
    const scouts=state.scouts||[];const count=scouts.length;const slots=state.scout_slots||3;
    const nextDates=scouts.map(s=>s.next_report).filter(Boolean).sort();
    return `${header('Youth scouting','Recruit specialist scouts, assign destinations and review new prospects every 90 days. Unsigned players can join rival clubs.',[
      stat('budget',money(state.recruitment_funds),'Recruitment allocation'),stat('budget',money(state.monthly_scout_cost),'Monthly wages'),stat('players',`${count} / ${slots}`,'Scouts hired'),stat('clock',nextDates.length?shortDate(nextDates[0]):'No mission','Next report')],'scout')}
      <section class="ya-scout-grid">${Array.from({length:slots},(_,i)=>scoutCard(i+1)).join('')}</section>
      <section class="ya-panel ya-prospects-section"><div class="ya-section-title"><div><h3>Discovered prospects <span class="ya-muted">(${state.candidates.length})</span></h3><p>All discoveries are followed automatically. Unsigned players may be signed by rival clubs.</p></div><span class="ya-risk-callout">⚠ Unsigned prospects can be poached</span></div>
      <div class="ya-prospect-filters">${select('candidatePosition',[['all','All positions'],...unique(state.candidates.map(p=>p.position)).map(p=>[p,p])],candidateFilter.position,'Position')}${select('candidateRegion',[['all','All countries'],...unique(state.candidates.map(p=>p.country)).map(p=>[p,p])],candidateFilter.region,'Country')}${select('candidateScout',[['all','All scouts'],...unique(state.candidates.map(p=>p.scout)).map(p=>[p,p])],candidateFilter.scout,'Scout')}${select('candidateRisk',[['all','All risks'],['Low','Low'],['Medium','Medium'],['High','High']],candidateFilter.risk,'Poaching risk')}${select('candidateSort',[['potential','Potential'],['risk','Risk'],['recent','Recently discovered'],['age','Youngest']],candidateFilter.sort,'Sort')}</div>
      ${candidateRows()}</section>
      ${(state.lost_prospects||[]).length?`<section class="ya-lost-history ya-panel"><h3>Signed by rival clubs</h3><p>These players were discovered but not signed in time.</p><div>${state.lost_prospects.slice(0,6).map(p=>`<span>${esc(p.name)} → ${esc(p.club)} · ${shortDate(p.date)}</span>`).join('')}</div></section>`:''}
      ${marketOpen?marketDialog():''}`;
  }
  function marketDialog(){
    const offers=state.market_offers||[];
    let inside='';
    if(negotiation){
      const n=negotiation;
      const person=n.scoutId?(state.scouts||[]).find(s=>s.id===n.scoutId):offers.find(o=>o.id===n.offerId);
      if(!person){negotiation=null;return marketDialog();}
      inside=`<div class="ya-market-person"><span class="ya-scout-person ya-scout-person-large" aria-hidden="true">${personIcon}</span><div><small>${n.scoutId?'CONTRACT RENEWAL':'NEW APPOINTMENT'}</small>
        <h3>${esc(person.name)}</h3><p>Judging quality: <b>${esc(person.quality)}/100</b> · Requested salary: <b>${money(n.demand)}/month</b></p></div></div>
      <form class="ya-negotiation-form" data-youth-offer-form><h3>Contract proposal</h3>
        <label>Monthly wage <input name="monthly_wage" type="number" min="100" max="100000" step="100" required value="${esc(n.wage)}"></label>
        <label>Contract length <select name="years">${[1,2,3,4].map(y=>option(y,`${y} ${y===1?'year':'years'}`,n.years)).join('')}</select></label>
        <label>Signing bonus <input name="signing_fee" type="number" min="0" max="200000" step="100" required value="${esc(n.bonus)}"></label>
        ${n.response?`<div class="ya-offer-response" role="status"><strong>Offer declined</strong><span>${esc(n.response.message)}</span>
          <span>Counteroffer: ${money(n.response.counter_monthly_wage)} / month</span>
          <button class="ya-btn" type="button" data-youth-use-counter="${esc(n.response.counter_monthly_wage)}">Use counteroffer</button></div>`:''}
        <p class="ya-budget-note">Any accepted signing bonus is charged now. Monthly wages are charged to the academy allocation.</p>
        <div class="ya-negotiation-actions"><button type="button" class="ya-btn" data-youth-market-back="1">${n.scoutId?'Back to academy':'Back to candidates'}</button>
        <button type="submit" class="ya-btn ya-btn-primary">Submit offer</button></div></form>`;
    }else{
      inside=`<div class="ya-offer-list">${offers.map(o=>`<div class="ya-offer"><div class="ya-person-cell"><span class="ya-scout-person" aria-hidden="true">${personIcon}</span>
        <span><strong>${esc(o.name)}</strong><small>Judging ${esc(o.quality)}/100</small></span></div>
        <span><small>Requested salary</small><b>${money(o.monthly_wage)}/mo</b></span>
        <span><small>Expected fee</small><b>${money(o.signing_fee)}</b></span>
        <button class="ya-btn ya-btn-primary" data-youth-negotiate-offer="${esc(o.id)}">Open negotiations</button></div>`).join('')||'<p>No new candidates available.</p>'}</div>`;
    }
    return `<div class="ya-modal-backdrop" data-youth-close-market="1"><section class="ya-modal" role="dialog" aria-modal="true" aria-label="Youth scout negotiations">
      <div class="ya-section-title"><div><h2>${negotiation?'Scout negotiations':'Recruit a youth scout'}</h2><p>Agree on salary, term and signing bonus before hiring.</p></div>
      <button type="button" class="ya-close" data-youth-close-market="1" aria-label="Close">✕</button></div>
      <div class="ya-modal-budget">Available recruitment allocation: <b>${money(state.recruitment_funds)}</b></div>${inside}</section></div>`;
  }
  function render(){
    if(!host||!state)return;
    window.FMClubIdentity?.applyTheme?.(state.club_id,state.club_name);
    const content=tab==='u15'?field():tab==='scouts'?scouting():roster(tab);
    host.innerHTML=`<div class="ya-layout">${clubHero()}
      <div class="ya-tabs" role="tablist" aria-label="Academy views">${[['u17','U17'],['u21','U21 / Reserves'],['u15','Next academy intake'],['scouts','Youth scouts']].map(([id,label])=>`<button type="button" role="tab" data-youth-tab="${id}" aria-selected="${tab===id}">${label}</button>`).join('')}</div>
      ${feedback?`<div class="ya-feedback" role="status">${esc(feedback)}</div>`:''}
      <div class="ya-body">${content}</div></div>`;
    host.setAttribute('aria-busy',String(loading));
  }
  async function command(payload){
    if(loading)return null;
    loading=true;host.setAttribute('aria-busy','true');
    try{
      const res=await fetch('/api/youth',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
      const data=await res.json();if(!res.ok)throw Error(data.error||`HTTP ${res.status}`);
      if(payload.action==='offer_scout'){
        if(data.accepted){feedback=`${data.name}: contract agreed · ${money(data.monthly_wage)}/month.`;marketOpen=false;negotiation=null;await refresh();}
        else{negotiation.response=data;render();}
      }else{feedback=payload.action==='sign'?'Prospect signed to U17.':null;await refresh();}
      return data;
    }catch(err){window.alert(`Youth Academy: ${err.message}`);return null;
    }finally{loading=false;host?.setAttribute('aria-busy','false');}
  }
  async function refresh(){
    if(!host)return;
    try{const res=await fetch('/api/youth',{cache:'no-store'});if(!res.ok)throw Error(`HTTP ${res.status}`);state=await res.json();render();}
    catch(err){host.innerHTML=`<section class="ya-panel"><h3>Academy unavailable</h3><p>${esc(err.message)}</p><button class="ya-btn" data-youth-refresh="1">Retry</button></section>`;}
  }
  function bindOnce(){
    host.addEventListener('click',async event=>{
      const el=event.target.closest('button,[data-youth-close-market]');if(!el||!host.contains(el))return;
      if(el.dataset.youthTab){tab=el.dataset.youthTab;marketOpen=false;negotiation=null;feedback=null;render();return;}
      if(el.dataset.youthRefresh){await refresh();return;}
      if(el.dataset.youthOpenMarket){marketOpen=true;negotiation=null;render();return;}
      if(el.dataset.youthCloseMarket){if(event.target===el||el.tagName==='BUTTON'){marketOpen=false;negotiation=null;render();}return;}
      if(el.dataset.youthMarketBack){if(negotiation?.scoutId){marketOpen=false;negotiation=null;}else{negotiation=null;marketOpen=true;}render();return;}
      if(el.dataset.youthUseCounter){
        if(!negotiation)return;const field=host.querySelector('[data-youth-offer-form] [name="monthly_wage"]');
        if(field)field.value=el.dataset.youthUseCounter;negotiation.wage=Number(el.dataset.youthUseCounter);negotiation.response=null;render();return;
      }
      if(el.dataset.youthNegotiateOffer){
        const offer=(state.market_offers||[]).find(o=>o.id===el.dataset.youthNegotiateOffer);if(!offer)return;
        negotiation={offerId:offer.id,scoutId:null,demand:offer.monthly_wage,wage:offer.monthly_wage,years:2,bonus:offer.signing_fee,response:null};
        marketOpen=true;render();return;
      }
      if(el.dataset.youthNegotiateScout){
        const scout=(state.scouts||[]).find(s=>s.id===el.dataset.youthNegotiateScout);if(!scout)return;
        const demand=Math.max(100,Math.round(scout.monthly_wage*1.09/100)*100);
        negotiation={offerId:null,scoutId:scout.id,demand,wage:demand,years:2,bonus:0,response:null};marketOpen=true;render();return;
      }
      if(el.dataset.youthAction){
        const action=el.dataset.youthAction;
        if(action==='fire_scout'){
          const scout=(state.scouts||[]).find(s=>s.id===el.dataset.id);
          if(!window.confirm(`End ${scout?.name||'scout'} contract? Termination cost: ${money(scout?.monthly_wage)}.`))return;
          await command({action,scout_id:el.dataset.id});return;
        }
        if(action==='release'&&!window.confirm('Release this youth player from the club?'))return;
        if(action==='sign'&&!window.confirm('Sign this prospect directly to your U17 squad?'))return;
        await command({action,player_id:el.dataset.id,...(el.dataset.target?{target:el.dataset.target}:{})});
      }
    });
    host.addEventListener('submit',async event=>{
      const form=event.target.closest('[data-youth-scout],[data-youth-offer-form]');if(!form)return;
      event.preventDefault();
      if(form.hasAttribute('data-youth-offer-form')){
        if(!negotiation)return;
        const wage=Number(form.elements.namedItem('monthly_wage').value);
        const years=Number(form.elements.namedItem('years').value);
        const bonus=Number(form.elements.namedItem('signing_fee').value);
        if(!Number.isInteger(wage)||!Number.isInteger(years)||!Number.isInteger(bonus))return;
        Object.assign(negotiation,{wage,years,bonus,response:null});
        await command({action:'offer_scout',offer_id:negotiation.offerId,scout_id:negotiation.scoutId,
          monthly_wage:wage,years,signing_fee:bonus});return;
      }
      await command({action:'assign_scout',scout_id:form.dataset.youthScout,
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
      host.querySelectorAll('.ya-roster-card').forEach(card=>{card.hidden=!(card.dataset.search||'').includes(squadFilter.query.toLowerCase());});
    });
  }
  function mount(element){if(host!==element){host=element;bindOnce();}host.innerHTML='<div class="ya-panel">Loading academy...</div>';refresh();}
  window.addEventListener('fm-identity-ready',()=>{if(host&&state)render();});
  window.FMYouthAcademy=Object.freeze({mount,refresh});
})();
