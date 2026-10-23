/* TS-UI-08 — scouting hub, search and shortlist. Python is authoritative.
 * Uses Squad's shared player portrait service, the shared club identity catalog,
 * and the existing professional scout calendar, negotiation and Inbox systems.
 */
(() => {
  'use strict';
  let host = null, model = null, page = 'hub', selected = null, profileTab = 'overview';
  let fetching = false, writing = false, requestSeq = 0, feedback = '';
  let filters = {query:'', country:'', league:'', club:'', position:'', ageMin:'', ageMax:''};
  let sort = 'name', sortDir = 'asc', limit = 100, shortlistFilter = 'all';
  const esc = v => String(v ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const fmt = v => Number(v).toLocaleString('en-GB');
  const cash = v => v == null ? '??' : '£' + (v >= 1e6 ? (v/1e6).toFixed(1)+'M' : v>=1e3?(v/1e3).toFixed(0)+'K':fmt(v));
  const range = (values, formatter = v => String(v)) => Array.isArray(values) && values.length === 2
    ? `${formatter(values[0])}–${formatter(values[1])}` : '??';
  const player = id => model?.players?.find(p => p.id === id) || null;
  const selectedPlayer = () => player(selected);
  const scoutFor = id => model?.scouts?.find(s => s.id === id);
  const knowledge = p => p?.report || p?.public_profile || null;
  const knownAbility = p => p.report ? range(p.report.overall_range) : (p.public_profile ? String(p.public_profile.overall.toFixed(1)) : '??');
  const knownValue = p => p.report ? range(p.report.value_range_gbp,cash) : cash(p.public_profile?.market_value_gbp);
  const sortValue = (p,field) => {
    if(field==='name')return p.name.toLowerCase();
    if(field==='age')return p.age;
    if(field==='height')return p.height_cm;
    if(field==='rating')return p.public_profile?.overall ?? (p.report ? (p.report.overall_range[0]+p.report.overall_range[1])/2 : null);
    if(field==='value')return p.public_profile?.market_value_gbp ?? (p.report ? (p.report.value_range_gbp[0]+p.report.value_range_gbp[1])/2 : null);
    if(field==='progress')return p.report ? 100 : p.scouting?.progress ?? 0;
    return p.name.toLowerCase();
  };
  const status = p => p.report ? 'Report complete' : p.scouting ? `Scouting ${p.scouting.progress}%` : 'Not scouted';
  const people = () => model?.scouts || [];
  const portrait = (p,cls='') => window.FMPortraits?.portrait?.(p,cls)||`<span class="sc-face">${esc(p.name?.[0]||'?')}</span>`;
  const identity = () => window.FMClubIdentity?.resolve?.(model?.club_id, model?.club) || {display_name:model?.club||'Club',crest:null};
  const displayClub = (cid, fallback) => window.FMClubIdentity?.resolve?.(cid, fallback)?.display_name || fallback || cid;
  const clubMark = (cid, fallback='', large=false) => {
    const obj = model?.clubs?.find(c=>c.id===cid);
    const club = window.FMClubIdentity?.resolve?.(cid,obj?.name||fallback||cid);
    const name = club?.display_name || obj?.name || fallback || cid || 'Unknown club';
    const cls = large ? 'sc-player-club-crest' : 'sc-mini-crest';
    const source = club?.crest && (window.FMEntityAssets?.url?.(club.crest) || '/portable/' + club.crest);
    const initials = String(name).split(/\s+/).filter(Boolean).slice(0,2).map(x=>x[0]).join('').toUpperCase() || '?';
    // A missing club badge is a distinct shield, never a football icon.
    // Importing a real crest under the same club ID replaces it automatically.
    const fallbackColor = window.FMClubIdentity?.fallbackColour?.(cid) || '#447d9d';
    return source
      ? `<img class="${cls}" data-fm-asset="optional" data-fm-crest-fallback="${esc(initials)}" data-fm-crest-club-id="${esc(cid)}" src="${esc(source)}" alt="${esc(name)} crest" title="${esc(name)}" loading="lazy" decoding="async">`
      : `<span class="${cls} sc-crest-placeholder" style="--sc-placeholder-color:${esc(fallbackColor)}" role="img" aria-label="${esc(name)} crest" title="${esc(name)}">${esc(initials)}</span>`;
  };
  const flag = n => window.FMNationFlags?.render?.(n,'sc-nation') || `<span class="sc-nationality-backup" title="${esc(n)}">◇</span>`;
  const button = (name,action,style='',disabled=false) => `<button type="button" class="sc-btn ${style}" data-sc-action="${esc(action)}" ${disabled?'disabled':''}>${esc(name)}</button>`;
  const pills = (values) => (values||[]).map(x=>`<span class="sc-position">${esc(x)}</span>`).join('');
  const valueOrUnknown = (value) => value == null ? '—' : esc(value);
  const navTabs = () => `<nav class="sc-subnav" aria-label="Scouting pages">${[['hub','Scouting Hub'],['search','Player Search'],['network',`Scout Network (${people().length})`]].map(([id,label])=>
    `<button type="button" class="${page===id?'is-active':''}" data-sc-page="${id}" aria-current="${page===id?'page':'false'}">${esc(label)}</button>`).join('')}</nav>`;
  function hero(){
    const id=identity(); const counts=[['Scouts',people().length],['Watching',`${model.occupied} / ${model.capacity}`],['Reports',model.reports_completed],['Leads',model.recommendations.length]];
    return `<header class="sc-hero"><div class="sc-hero-identity"><span class="sc-hero-crest">${id.crest?`<img src="${esc(id.crest)}" alt="">`:'⚽'}</span>
      <div class="sc-hero-copy"><small>${esc(id.display_name)} · SCOUTING</small><h2>${page==='hub'?'Scouting centre':page==='search'?'Player search':page==='shortlist'?'Shortlist':'Scouting network'}</h2>
      <p>${page==='hub'?'Find talent. Build your future.':page==='search'?'Explore every registered professional player.':page==='shortlist'?'Your saved targets and observation priorities.':'Your scouts, destinations and workload.'}</p></div></div>
      <div class="sc-hero-metrics">${counts.map(([label,num])=>`<div><strong>${esc(num)}</strong><small>${label}</small></div>`).join('')}</div></header>`;
  }
  const options = (values, chosen, first) => `<option value="">${esc(first)}</option>${values.map(([val,label])=>`<option value="${esc(val)}" ${String(val)===String(chosen)?'selected':''}>${esc(label)}</option>`).join('')}`;
  function formContents(className='sc-hub-filters'){
    const countries = (model.countries||[]).map(c=>[c,c]);
    const leagues = (model.leagues||[]).map(c=>[c,c]);
    const clubs = (model.clubs||[]).filter(c=>!filters.league || c.league===filters.league).map(c=>[c.id,c.name]);
    const positions=[...new Set(model.players.flatMap(p=>p.positions))].sort().map(x=>[x,x]);
    return `<div class="${className}">
      <label><span>Name</span><input name="query" type="search" placeholder="Player name" value="${esc(filters.query)}" maxlength="100"></label>
      <label><span>Nationality</span><select name="country">${options(countries,filters.country,'Any country')}</select></label>
      <label><span>League</span><select name="league">${options(leagues,filters.league,'Any league')}</select></label>
      <label><span>Team</span><select name="club">${options(clubs,filters.club,'Any team')}</select></label>
      <label><span>Position</span><select name="position">${options(positions,filters.position,'Any position')}</select></label>
      <label><span>Min. age</span><input name="ageMin" type="number" min="15" max="50" value="${esc(filters.ageMin)}" placeholder="Any"></label>
      <label><span>Max. age</span><input name="ageMax" type="number" min="15" max="50" value="${esc(filters.ageMax)}" placeholder="Any"></label>
    </div>`;
  }
  function filtered(onlyShortlist=false){
    if(!model)return [];
    const q=filters.query.trim().toLowerCase();
    const values=model.players.filter(p => (!onlyShortlist || !!p.priority) &&
      (!onlyShortlist || shortlistFilter==='all'||p.priority===shortlistFilter) &&
      (!q || `${p.name} ${p.club} ${p.nationality}`.toLowerCase().includes(q)) &&
      (!filters.country||p.nationality===filters.country) &&
      (!filters.league||p.league===filters.league) &&
      (!filters.club||p.club_id===filters.club) &&
      (!filters.position||p.positions.includes(filters.position)) &&
      (!filters.ageMin||p.age>=Number(filters.ageMin)) &&
      (!filters.ageMax||p.age<=Number(filters.ageMax)));
    const sign=sortDir==='desc'?-1:1;
    values.sort((a,b)=>{
      const left=sortValue(a,sort),right=sortValue(b,sort);
      // Unknown metrics always last in BOTH directions; never sort with
      // unpublished raw GRL, value or height from the Python world model.
      if(left==null)return right==null ? a.name.localeCompare(b.name) : 1;
      if(right==null)return -1;
      const delta=typeof left==='number' && typeof right==='number' ? left-right : String(left).localeCompare(String(right));
      return delta ? sign*delta : a.name.localeCompare(b.name);
    });
    return values;
  }
  const briefPlayer=p=>`${esc(p.position)} · ${p.age} yrs · ${flag(p.nationality)}`;
  function hub(){
    const recommended=model.recommendations.map(rec=>({rec,p:player(rec.player_id)})).filter(x=>x.p).slice(0,5);
    const reportStats={finished:model.reports_completed,working:model.occupied,scouts:people().length,leads:model.recommendations.length};
    return `<div class="sc-hub-grid">
      <section class="sc-card sc-hub-search"><div class="sc-card-title"><div><h3>⌕ &nbsp; Search players</h3><p>Find players worldwide with no discovery restrictions.</p></div></div>
        <form data-sc-form="hub">${formContents()}<div class="sc-hub-actions"><button class="sc-btn sc-btn-primary" type="submit">Search players →</button></div></form></section>
      <section class="sc-card sc-hub-recs"><div class="sc-card-title"><div><h3>✦ &nbsp; Scout recommendations</h3><p>Leads from the territories assigned to your scouts.</p></div></div>
        <div class="sc-recommendations">${recommended.length?recommended.map(({rec,p})=>`<div class="sc-recommendation">${portrait(p,'sc-list-face')}
          <div class="sc-recommendation-name"><strong>${esc(p.name)}</strong><small class="sc-rec-club">${clubMark(p.club_id,p.club)} ${esc(displayClub(p.club_id,p.club))} · ${briefPlayer(p)} · ${esc(rec.scout)}</small></div>
          <div class="sc-recommendation-actions"><button data-sc-select="${esc(p.id)}" data-sc-open="search">View</button>${p.priority?'<span class="sc-recommendation-saved">✓ Shortlisted</span>':button('+ Shortlist','shortlist_add:'+p.id)}</div></div>`).join(''):'<div class="sc-empty">No recommendations yet. Hire scouts in Staff to start building your network.</div>'}</div>
        <button type="button" data-sc-page="search" class="sc-wide-link">View player search →</button></section>
      <section class="sc-card sc-hub-network"><div class="sc-card-title"><div><h3>♙ &nbsp; Scout assignments</h3><p>Quality and destination affect your recruitment network.</p></div></div>
        <div class="sc-network-preview">${people().length?people().slice(0,5).map(s=>`<div class="sc-network-line"><span class="sc-staff-icon">♟</span>
          <div><strong>${esc(s.name)}</strong><small>${labelDestination(s.destination)}</small></div>
          <div class="sc-network-line-stats"><strong>${s.occupied} / ${s.capacity}</strong><small>Assigned</small></div></div>`).join(''):'<div class="sc-empty">No scouts hired. Recruit in the Staff department.</div>'}</div>
        <button type="button" data-sc-page="network" class="sc-wide-link">Manage scout network →</button></section>
    </div>
    <section class="sc-card sc-short-preview sc-intelligence-panel"><div class="sc-card-title"><div><h3>✦ &nbsp; Recruitment intelligence</h3><p>Scouting capacity, reports and worldwide leads. Saved targets now live in Transfers.</p></div><button type="button" class="sc-btn" data-sc-action="transfers">Open Transfers →</button></div>
      <div class="sc-short-summary"><div class="sc-short-counts">${[['Reports',reportStats.finished],['Watching',reportStats.working],['Scouts',reportStats.scouts],['Leads',reportStats.leads]].map(([label,num])=>`<div><strong>${num}</strong><small>${label}</small></div>`).join('')}</div>
      <div class="sc-intel-copy"><strong>From discovery to negotiation</strong><p>Assign scouts for better attribute ranges, add interesting players to your shortlist and manage all offers inside Transfers.</p><button type="button" class="sc-btn sc-btn-primary" data-sc-action="transfers">View shortlist & offers →</button></div></div></section>`;
  }
  function labelDestination(destination){
    if(!destination || destination==='all')return 'All available leagues';
    if(destination.startsWith('league:'))return 'League: '+destination.slice(7);
    if(destination.startsWith('country:'))return 'Nationality: '+destination.slice(8);
    return 'Unassigned';
  }
  function network(){
    return `<section class="sc-card"><div class="sc-card-title"><div><h3>Scout network</h3><p>Your professional scouts work on individual reports and territory recommendations. Hire or negotiate contracts in Staff.</p></div><button data-sc-action="staff" class="sc-btn sc-btn-primary">Open Staff →</button></div>
      <div class="sc-team-grid">${people().length?people().map(s=>`<article class="sc-team-card"><div class="sc-team-main"><span class="sc-staff-icon sc-staff-lg" aria-hidden="true">♟</span><div><h4>${esc(s.name)}</h4><small>Professional scout · Quality ${s.quality}/100</small><div class="sc-stars">${'★'.repeat(Math.round(s.quality/20))}${'☆'.repeat(5-Math.round(s.quality/20))}</div></div><strong>${s.occupied} / ${s.capacity}<small> observing</small></strong></div>
        <label><span>Assigned scouting destination</span><select data-sc-destination="${esc(s.id)}"><option value="all" ${s.destination==='all'?'selected':''}>Worldwide / all leagues</option>${(model.leagues||[]).map(l=>`<option value="league:${esc(l)}" ${s.destination==='league:'+l?'selected':''}>${esc(l)}</option>`).join('')}${(model.countries||[]).map(c=>`<option value="country:${esc(c)}" ${s.destination==='country:'+c?'selected':''}>Nationality: ${esc(c)}</option>`).join('')}</select></label><div class="sc-team-caption">${esc(labelDestination(s.destination))}</div></article>`).join(''):'<div class="sc-empty">There are no employed professional scouts. Open Staff to recruit scouts with salary negotiations.</div>'}</div>
      <div class="sc-network-note"><strong>Calendar-driven scouting</strong><span>More scouts allow more simultaneous reports. More experienced scouts generally finish reports faster. Individual assignments progress when your career calendar advances; completed reports reach Inbox.</span></div></section>`;
  }
  function listRow(p){
    const chosen=p.id===selected;
    return `<button type="button" class="sc-roster-row ${chosen?'is-selected':''}" data-sc-select="${esc(p.id)}" aria-pressed="${chosen}">
      ${portrait(p,'sc-row-face')}<span class="sc-roster-about"><strong>${esc(p.name)}</strong><span class="sc-roster-meta">${pills([p.position])}<span class="sc-row-age">${esc(p.age)} yrs</span>${flag(p.nationality)}</span><small class="sc-roster-clubline">${clubMark(p.club_id)}<span class="sc-roster-league">${esc(p.league)}</span></small></span>
      <span class="sc-roster-side"><strong class="${p.report?'has-report':''}">${knownAbility(p)}</strong><small>${p.public_profile&&!p.report?'Public GRL':p.report?'Est. GRL':p.scouting?`${p.scouting.progress}% scouted`:'?? GRL'}</small><span class="sc-roster-value">${knownValue(p)}</span><span class="sc-roster-priority">${p.priority?esc(priorityName(p.priority)):p.report?'Report ready':'Not scouted'}</span></span></button>`;
  }
  const priorityName = p => ({top:'Top target',future:'For future',monitor:'Monitoring'}[p]||'Not shortlisted');
  function directory(){
    const only=page==='shortlist'; const data=filtered(only);
    if(selected && !data.some(p=>p.id===selected))selected=data[0]?.id||null;
    if(!selected && data.length)selected=data[0].id;
    return `<section class="sc-directory">
      <div class="sc-dir-top"><form data-sc-form="results" class="sc-results-filters">${formContents('sc-filter-strip')}
        <div class="sc-filter-buttons"><button class="sc-btn sc-btn-primary" type="submit">Apply filters</button><button class="sc-btn sc-btn-outline" type="button" data-sc-action="clear_filters">Reset</button></div></form></div>
      <div class="sc-directory-layout"><section class="sc-card sc-roster-list"><header class="sc-roster-title"><div><h3>${only?'Shortlisted players':'Search results'} <span>${fmt(data.length)}</span></h3><p>${only?'Players you have saved from the worldwide search.':'All registered professional players matchable by public information.'}</p></div></header>
        ${only?`<div class="sc-priority-filters">${[['all','All'],['top','Top targets'],['future','For future'],['monitor','Monitoring']].map(([id,name])=>`<button type="button" data-sc-priority-filter="${id}" class="${shortlistFilter===id?'is-selected':''}">${name}</button>`).join('')}</div>`:''}
        <div class="sc-list-sort"><span>${Math.min(limit,data.length)} shown of ${fmt(data.length)}</span><label>Sort <select data-sc-sort>${[['name','Name'],['age','Age'],['height','Height'],['rating','Rating / GRL'],['value','Market value'],['progress','Scouting progress']].map(([id,n])=>`<option value="${id}" ${sort===id?'selected':''}>${n}</option>`).join('')}</select></label><button type="button" class="sc-sort-direction" data-sc-sort-dir aria-label="Reverse sort order" title="${sortDir==='asc'?'Ascending':'Descending'} order">${sortDir==='asc'?'↑ Asc':'↓ Desc'}</button></div>
        <div class="sc-list-scroll" role="group" aria-label="${only?'Shortlisted players':'Search results'}">${data.slice(0,limit).map(listRow).join('')||'<div class="sc-empty">No players match these filters.</div>'}</div>
        <footer class="sc-roster-bottom"><span>${fmt(data.length)} ${only?'saved players':'players found'}</span>${data.length>limit?`<button type="button" data-sc-action="show_more">Show more ↓</button>`:'<span>End of list</span>'}</footer></section>
      <section class="sc-card sc-inspector" aria-label="Selected scouting profile" ${selectedPlayer()?`data-fm-club-theme="${esc(selectedPlayer().club_id)}" data-fm-club-name="${esc(selectedPlayer().club)}"`:''}>${selectedPlayer()?inspector(selectedPlayer()):'<div class="sc-empty">Choose a player to view their profile.</div>'}</section></div></section>`;
  }
  function inspector(p){
    const rep=p.report||null,project=p.scouting||null,publicKnowledge=p.public_profile||null;
    return `<div class="sc-profile-hero"><div class="sc-profile-head">${portrait(p,'sc-large-face')}
       <div class="sc-profile-id"><small class="sc-profile-club-name">${clubMark(p.club_id,p.club,true)} <span>${esc(displayClub(p.club_id,p.club))} · ${esc(p.league)}</span></small><h2>${esc(p.name)}</h2><div class="sc-profile-meta">${flag(p.nationality)} <span>${p.age} years old</span> ${pills(p.positions)}</div>
         <span class="sc-profile-public">${esc(p.foot)}-footed · ${p.report?'Report completed':p.scouting?'Under observation':'Public identity'}</span></div><div class="sc-profile-status">${rep?'REPORT READY':publicKnowledge?'WORLD-CLASS · PUBLIC':project?'UNDER OBSERVATION':'NOT SCOUTED'}</div></div>
       <div class="sc-profile-facts"><div><small>Height</small><b>${valueOrUnknown(p.height_cm)}${p.height_cm?' cm':''}</b></div><div><small>Weight</small><b>${valueOrUnknown(p.weight_kg)}${p.weight_kg?' kg':''}</b></div>
         <div><small>GRL</small><b>${knownAbility(p)}</b></div><div><small>Value</small><b>${knownValue(p)}</b></div></div></div>
       <div class="sc-profile-actions"><button class="sc-btn sc-btn-blue" data-sc-action="scout:${esc(p.id)}" ${rep||project||model.free_slots<1?'disabled':''}>${rep?'Report complete':project?'Scouting in progress':model.free_slots<1?'Scouts occupied':'Assign scout'}</button>
         <button class="sc-btn sc-btn-green" data-sc-action="${p.priority?'shortlist_remove':'shortlist_add'}:${esc(p.id)}">${p.priority?'✓ Shortlisted':'+ Add to shortlist'}</button>
         <button class="sc-btn sc-btn-outline" data-sc-action="negotiate:${esc(p.id)}">Open negotiation</button></div>
       ${p.priority?`<div class="sc-priority-editor"><label>Shortlist priority <select data-sc-priority="${esc(p.id)}">${[['top','Top target'],['future','For future'],['monitor','Monitoring']].map(([v,n])=>`<option value="${v}" ${p.priority===v?'selected':''}>${n}</option>`).join('')}</select></label></div>`:''}
       <nav class="sc-profile-tabs" aria-label="Player report sections">${[['overview','Overview'],['attributes','Attributes'],['report','Scout report'],['contract','Contract & market']].map(([id,n])=>`<button class="${profileTab===id?'is-current':''}" data-sc-tab="${id}">${n}</button>`).join('')}</nav>
       <div class="sc-inspector-content">${profileTab==='report'?reportPane(p):profileTab==='attributes'?attributesPane(p):profileTab==='contract'?contractPane(p):overviewPane(p)}</div>`;
  }
  function overviewPane(p){
    const rep=p.report,known=knowledge(p);
    const potential=known?.potential_range;
    const glimpses=rep?.attributes||p.public_profile?.attributes||p.attribute_estimates||[];
    // Summarise a few genuine attribute bands so unscouted profiles are useful.
    // The full technical/mental/physical list remains under Attributes.
    const focus=['Pace','Heading','Passing','Tackling','Finishing','Strength'];
    const shortlist=focus.map(name=>glimpses.find(a=>a.name===name)).filter(Boolean).slice(0,4);
    const preview=shortlist.length?`<section class="sc-profile-section sc-attribute-preview"><div class="sc-preview-heading"><h4>Attribute indications</h4><small>${rep?'Scout assessment':p.public_profile?'Publicly known':'Early, broad estimates'}</small></div><div class="sc-preview-grid">${shortlist.map(a=>`<div><span>${esc(a.name)}</span><strong>${a.value==null?range(a.range):esc(a.value)}</strong></div>`).join('')}</div><p>Indicative only. Open Attributes to see all ranges; scouting makes estimates more precise.</p></section>`:'';
    return `<div class="sc-profile-stats"><div><small>${p.public_profile&&!rep?'Public GRL':'Estimated GRL'}</small><strong>${knownAbility(p)}</strong></div><div><small>Potential estimate</small><strong>${range(potential)}</strong></div><div><small>Market value</small><strong>${knownValue(p)}</strong></div><div><small>Scout confidence</small><strong>${rep?rep.confidence+'%':'??'}</strong></div></div>
      ${preview}<section class="sc-profile-section"><h4>Positions & familiarity</h4><div class="sc-field-map"><div class="sc-field-mark">${pills(p.positions)}</div></div></section>
      <section class="sc-profile-section"><h4>${rep?'Scout verdict':p.public_profile?'Public reputation':'Scouting status'}</h4><p>${rep?esc(rep.verdict):p.public_profile?'Established world-class footballer. Public ability and estimated market value are known without assigning a scout; hidden potential remains unknown.':'No completed report. Attribute indications are broad; OVR, potential and market value remain undisclosed.'}</p></section>`;
  }
  function attributesPane(p){
    const attrs=p.report?.attributes||p.public_profile?.attributes||p.attribute_estimates;
    if(!attrs?.length)return `<div class="sc-locked"><strong>Attributes unavailable</strong><p>This player has no attribute indications recorded.</p></div>`;
    const mode=p.report?'Scout-estimated ranges':p.public_profile?'Publicly known attributes':p.scouting?'Observation in progress · narrowing estimates':'Early indications · broad ranges';
    return `<div class="sc-range-notice"><strong>${esc(mode)}</strong><span>Ranges are estimates, not exact ratings. They remain stable until the player changes or observation progresses.</span></div><div class="sc-attributes">${['technical','mental','physical','goalkeeping'].filter(group=>attrs.some(a=>a.group===group)).map(group=>`<section><h4>${group.toUpperCase()}</h4>${attrs.filter(a=>a.group===group).map(a=>`<div class="sc-attr-row"><span>${esc(a.name)}</span><strong>${a.value==null?range(a.range):esc(a.value)}</strong></div>`).join('')}</section>`).join('')}</div>`;
  }
  function contractPane(p){
    return `<div class="sc-profile-stats sc-contract-grid"><div><small>Current wage / week</small><strong>${cash(p.weekly_wage_gbp)}</strong></div><div><small>Contract expires</small><strong>${esc(p.contract_until||'—')}</strong></div><div><small>${p.report?'Estimated market value':'Market value'}</small><strong>${knownValue(p)}</strong></div><div><small>Transfer scouting</small><strong class="sc-contract-status">${esc(status(p))}</strong></div></div>
    <section class="sc-profile-section"><h4>Recruitment decision</h4><p>You may open the existing Transfers negotiation without a completed scouting report. Unknown ability and transfer value are a recruitment risk; the selling club still determines its asking price.</p></section>`;
  }
  function reportPane(p){
    if(!p.report){const obs=p.scouting;return `<div class="sc-locked"><strong>${obs?'Scouting in progress':'No scouting report available'}</strong><p>${obs?`${esc(obs.scout)} is observing ${esc(p.name)}. Approximate completion: ${obs.days_left==null?'waiting for an active scout':obs.days_left+' calendar days'}.`:'Assign a professional scout to receive an evaluation, including ability, potential and market value ranges.'}</p>${obs?`<div class="sc-progress"><span style="width:${Math.max(0,Math.min(100,obs.progress))}%"></span></div><small>${obs.progress}% complete</small>`:''}</div>`;}
    return `<div class="sc-report"><p class="sc-report-meta">Completed ${esc(p.report.date)} · ${esc(p.report.scout)} · Confidence ${p.report.confidence}%</p>
      <h4>Professional scouting assessment</h4><p>${esc(p.report.verdict)}</p><h4>Strengths</h4><ul>${p.report.strengths.map(x=>`<li>${esc(x)}</li>`).join('')}</ul><h4>Areas to improve</h4><p>Not verified in the current report.</p><p class="sc-report-caution">Values are scouting estimates, not guaranteed selling prices or exact hidden potential. Completed reports are delivered to Inbox.</p></div>`;
  }
  function body(){return `<div class="sc-hub-shell">${hero()}${navTabs()}${feedback?`<div class="sc-feedback" role="status">${esc(feedback)}</div>`:''}${page==='hub'?hub():page==='network'?network():directory()}</div>`;}
  function draw(){if(!host||!model)return;host.innerHTML=body();window.FMClubIdentity?.paintWithin?.(host);host.setAttribute('aria-busy',String(fetching||writing));}
  async function reload(){
    if(!host)return;const current=++requestSeq;fetching=true;
    if(!model)host.innerHTML='<section class="sc-card sc-loading">Loading the professional scouting network…</section>';
    try{
      const res=await fetch('/api/scouting/hub',{cache:'no-store'});
      if(!res.ok)throw Error('The scouting service is unavailable ('+res.status+')');
      const next=await res.json();if(current!==requestSeq||!host)return;
      if(!next.players||!next.scouts)throw Error('The scouting response is incomplete');
      model=next;
      await window.FMClubIdentity?.ready;
      if(current!==requestSeq||!host)return;
      // Club theme is shared with Staff, Youth and Squad; never hardcode a team.
      window.FMClubIdentity?.applyShell?.(model.club_id,model.club);
      fetching=false;draw();
    }catch(err){if(current!==requestSeq||!host)return;fetching=false;host.innerHTML=`<section class="sc-card sc-loading"><h3>Scouting unavailable</h3><p>${esc(err.message)}</p><button class="sc-btn sc-btn-primary" data-sc-action="retry">Try again</button></section>`;}
  }
  async function command(value){
    if(writing)return; writing=true; feedback=''; host.setAttribute('aria-busy','true');
    try{
      const response=await fetch('/api/scouting',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(value)});
      const body=await response.json();if(!response.ok)throw Error(body.error||`Scouting request failed (${response.status})`);
      feedback=value.action==='destination'?'Scout destination updated.':value.action==='assign'?'Observation added to the scouting workload.':value.action==='shortlist_remove'?'Player removed from shortlist.':'Shortlist saved.';
      writing=false; await reload();
    }catch(e){writing=false;feedback=e.message;draw();}
  }
  function toPage(next){page=next;limit=100;profileTab='overview';feedback='';draw();host.scrollIntoView({block:'start',behavior:'instant'});}
  function updateFilters(form){
    const data=new FormData(form);
    for(const id of Object.keys(filters))filters[id]=String(data.get(id)||'').trim();
    // Changing league clears a team filter that belongs to a different league.
    if(filters.club && !model.clubs.some(c=>c.id===filters.club&&(!filters.league||c.league===filters.league)))filters.club='';
  }
  function events(){
    host.addEventListener('submit',event=>{
      const form=event.target.closest('[data-sc-form]');if(!form)return;
      event.preventDefault(); updateFilters(form);limit=100;selected=null;
      if(form.dataset.scForm==='hub')page='search';draw();
    });
    host.addEventListener('change',event=>{
      const node=event.target;
      if(node.dataset.scDestination){command({action:'destination',scout_id:node.dataset.scDestination,destination:node.value});return;}
      if(node.dataset.scPriority){command({action:'shortlist_priority',player_id:node.dataset.scPriority,priority:node.value});return;}
      if(node.dataset.scSort){sort=node.value;draw();return;}
      if(node.matches('select[name="league"]')){
        filters.league=node.value;filters.club='';
        const form=node.closest('form');if(form){const data=new FormData(form);for(const [key,value] of data.entries()){if(key!=='club')filters[key]=String(value);} }
        draw();return;
      }
    });
    host.addEventListener('click',event=>{
      const node=event.target.closest('button');if(!node||!host.contains(node))return;
      if(node.dataset.scPage){if(node.dataset.scPage==='shortlist')window.FMNavigation?.navigate?.('Transfers');else toPage(node.dataset.scPage);return;}
      if(node.dataset.scPriorityFilter){shortlistFilter=node.dataset.scPriorityFilter;selected=null;draw();return;}
      if(node.dataset.scTab){profileTab=node.dataset.scTab;draw();return;}
      if(node.dataset.scSelect){if(node.dataset.scOpen)page=node.dataset.scOpen;selected=node.dataset.scSelect;profileTab='overview';
        // From hub, keep filters neutral when opening a recommendation or shortlist player.
        if(node.dataset.scOpen)filters={query:'',country:'',league:'',club:'',position:'',ageMin:'',ageMax:''};
        draw();if(node.dataset.scOpen)host.scrollIntoView({block:'start',behavior:'instant'});return;}
      if(node.hasAttribute('data-sc-sort-dir')){sortDir=sortDir==='asc'?'desc':'asc';draw();return;}
      const cmd=node.dataset.scAction;if(!cmd)return;
      if(cmd==='retry'){reload();return;}
      if(cmd==='clear_filters'){filters={query:'',country:'',league:'',club:'',position:'',ageMin:'',ageMax:''};selected=null;draw();return;}
      if(cmd==='show_more'){limit+=100;draw();return;}
      if(cmd==='staff'){window.FMNavigation?.navigate?.('Staff');return;}
      if(cmd==='transfers'){window.FMNavigation?.navigate?.('Transfers');return;}
      const [action,id]=cmd.split(':');if(!id)return;
      if(action==='negotiate'){
        const item=player(id);if(item)window.FMNavigation?.negotiatePlayer?.(id);
        return;
      }
      if(action==='scout'){
        const item=player(id);if(!item||item.report||item.scouting||model.free_slots<1)return;
        command({action:'assign',player_id:id});return;
      }
      if(action==='shortlist_remove')command({action:'shortlist_remove',player_id:id});
      if(action==='shortlist_add')command({action:'shortlist_add',player_id:id,priority:'monitor'});
    });
  }
  function mount(element){
    if(host!==element){host=element;events();model=null;selected=null;page='hub';}
    if(!model)reload();else draw();
  }
  window.FMScouting=Object.freeze({mount,refresh:reload,showSearch:()=>{if(host){page='search';selected=null;draw();}}});
})();
