/* UI-3.3.2 hotfix: separate club competitions from other-leagues explorer.
   No simulated standings, results, future draws, or fabricated bracket links. */
window.FMCompetitions = (() => {
  'use strict';
  const h = v => String(v ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const clamp = (x, lo, hi) => Math.max(lo, Math.min(hi, x));
  const hash = s => [...String(s)].reduce((v,c) => (Math.imul(v,31)+c.charCodeAt(0))|0, 17);
  const abbr = s => String(s).split(/[\s-]+/).filter(Boolean).slice(0,2).map(x=>x[0]).join('').toUpperCase();
  const number = v => Number.isFinite(v) ? String(v) : '–';
  const ci=id=>window.FMCompetitionBranding?.resolve(id)||{key:'neutral',accent:'#65b9f8'};
  const ciVars=id=>window.FMCompetitionBranding?.vars(id)||'';
  const ciLogo=(id,cls)=>window.FMCompetitionBranding?.badge(id,cls)||'🏆';
  const competitionColor = id => ci(id).accent;
  const fixtureStamp = m => m?.kickoff ? m.kickoff.slice(11,16) + ' UTC' : 'TBD';
  const dayStamp = d => d ? new Intl.DateTimeFormat('en-GB',{month:'short',day:'numeric',timeZone:'UTC'}).format(new Date(d+'T12:00:00Z')) : 'Date TBD';
  let root=null, index=null, data=null, selectedComp=null, stage=null, roundId=null, groupId=null, focus='club', zoomLevel=3, anchorTieId=null;
  let explorerView='mine';
  const selectedByView={mine:null,other:null};
  const freshFilters=()=>({participant:'clubs',scope:'all',continent:'all',country:'all',type:'all',division:'all'});
  let filters=freshFilters();
  let indexSerial=0, detailSerial=0, dragState=null;

  const shownClub=(id,name)=>window.FMClubIdentity?.resolve?.(id,name)?.display_name||name||id||'Club';
  function crest(name, id, large=false) {
    const entry=window.FMClubIdentity?.resolve?.(id,name);
    if(entry?.crest)return `<img data-fm-asset="optional" class="cmp-crest cmp-crest-real ${large?'cmp-crest-large':''}" src="${h(window.FMEntityAssets?.url(entry.crest)||entry.crest)}" loading="lazy" alt="">`;
    const managed=data?.managed_id===id;
    const hue=Math.abs(hash(id||name))%360;
    return `<span class="cmp-crest ${managed?'cmp-crest-managed':''} ${large?'cmp-crest-large':''}" style="--cmp-hue:${hue}" role="img" aria-label="${h(shownClub(id,name))} crest">${h(abbr(name)||'?')}</span>`;
  }
  function opts() { return explorerView==='mine' ? (index?.competitions||[]) : (index?.other_competitions||[]); }
  function filteredOptions() {
    if(explorerView==='mine')return opts();
    return opts().filter(c=>
      (filters.participant==='all' || c.participant_type===filters.participant) &&
      (filters.scope==='all' || c.scope===filters.scope) &&
      (filters.continent==='all' || c.continent===filters.continent) &&
      (filters.country==='all' || c.country===filters.country) &&
      (filters.type==='all' || c.competition_type===filters.type) &&
      (filters.division==='all' || c.division===Number(filters.division))
    );
  }
  const unique=(values)=>[...new Set(values.filter(Boolean))].sort((a,b)=>String(a).localeCompare(String(b)));
  function filterSelect(field,label,items,allLabel){
    const options=[['all',allLabel],...items];
    return `<label class="cmp-filter-field"><span>${h(label)}</span><select data-cmp-filter="${field}" aria-label="${h(label)}">${options.map(([v,n])=>
      `<option value="${h(v)}" ${String(filters[field])===String(v)?'selected':''}>${h(n)}</option>`).join('')}</select></label>`;
  }
  // Own competitions retain the original UI-3.3.1 horizontal selector.
  // Only Other Leagues exposes the worldwide directory filters.
  function clubTabs(){
    return `<nav class="cmp-comp-selector" aria-label="Your club competitions">${opts().map(c=>
      `<button type="button" data-cmp-competition="${h(c.id)}" data-competition-brand="${h(ci(c.id).key)}" class="${c.id===data?.id?'active':''}" style="${ciVars(c.id)}"><span class="cmp-tab-dot"></span>${ciLogo(c.id,'ci-selector-logo')}${h(c.name)}<small>★</small></button>`).join('')}</nav>`;
  }
  // These are discovery choices, not claims that leagues have been simulated.
  // Every competition shown below the filters still comes from the live Python index.
  const geography={
    'Africa':['Algeria','Egypt','Ghana','Morocco','Nigeria','Senegal','South Africa','Tunisia'],
    'Asia':['China','India','Japan','Saudi Arabia','South Korea','United Arab Emirates'],
    'Europe':['Austria','Belgium','Croatia','Denmark','England','France','Germany','Greece','Ireland','Italy','Netherlands','Norway','Poland','Portugal','Scotland','Spain','Sweden','Switzerland','Turkey','Ukraine','Wales'],
    'North America':['Canada','Costa Rica','Mexico','United States'],
    'Oceania':['Australia','New Zealand'],
    'South America':['Argentina','Brazil','Chile','Colombia','Ecuador','Paraguay','Peru','Uruguay']
  };
  const continentNames=Object.keys(geography);
  function directoryBrowser(){
    const available=opts();
    const candidates=filteredOptions();
    const continents=unique([...continentNames,...available.map(c=>c.continent)]);
    const countryEntries=[];
    for(const [continent,countries] of Object.entries(geography)){
      if(filters.continent==='all'||filters.continent===continent)countryEntries.push(...countries);
    }
    const extra=available.filter(c=>filters.continent==='all'||c.continent===filters.continent).map(c=>c.country);
    const countries=unique([...countryEntries,...extra]);
    const cont=filterSelect('continent','Continent',continents.map(v=>[v,v]),'All continents');
    const nation=filters.scope!=='international'
      ?filterSelect('country','Country',countries.map(v=>[v,v]),'All countries') : '';
    const categories=filterSelect('type','Competition type',
      (filters.scope==='national'?[['league','Leagues'],['cup','Domestic cups']]
      :filters.scope==='international'?[['continental','Continental tournaments']]
      :[['league','Leagues'],['cup','Domestic cups'],['continental','Continental tournaments']]),
      'All types');
    const division=(filters.scope!=='international' && (filters.type==='all'||filters.type==='league'))
      ?filterSelect('division','Division',[["1","First division"],["2","Second division"],["3","Third division"],["4","Fourth division"]], 'All divisions') : '';
    const emptyMessage=filters.participant==='national-teams'
      ?'National-team competitions are not implemented yet.'
      :filters.country!=='all'
      ?`No competitions from ${filters.country} are available in the current world. You can select other countries, but they will appear here only when their leagues are added.`
      :filters.continent!=='all'
      ?`No matching competitions are currently loaded for ${filters.continent}. No tables or fixtures have been generated.`
      :'No competitions match these filters. Try a different scope, competition type or division.';
    return `<section class="cmp-directory panel" aria-label="Other leagues and cups explorer">
      <div class="cmp-directory-head"><h2>Explore other leagues & cups</h2><small>Read-only · Existing world competitions only</small></div>
      <div class="cmp-directory-fields">
        <label class="cmp-filter-field"><span>Participants</span><select data-cmp-filter="participant" aria-label="Participants">
          <option value="clubs" ${filters.participant==='clubs'?'selected':''}>Clubs</option><option value="national-teams" ${filters.participant==='national-teams'?'selected':''}>National teams (future)</option></select></label>
        <label class="cmp-filter-field"><span>Scope</span><select data-cmp-filter="scope" aria-label="Scope">
          <option value="all" ${filters.scope==='all'?'selected':''}>All scopes</option><option value="national" ${filters.scope==='national'?'selected':''}>National</option>
          <option value="international" ${filters.scope==='international'?'selected':''}>International</option></select></label>
        ${cont}${nation}${categories}${division}
        <label class="cmp-filter-field cmp-filter-competition"><span>Competition · ${candidates.length} found</span>
          <select data-cmp-competition-select aria-label="Select other competition" ${candidates.length?'':'disabled'}>
          ${candidates.length?candidates.map(c=>`<option value="${h(c.id)}" ${c.id===selectedComp?'selected':''}>${h(c.name)}</option>`).join(''):'<option>No competitions available</option>'}</select></label>
      </div>
      ${candidates.length?'':`<p class="cmp-directory-empty" role="status">${h(emptyMessage)}</p>`}
      <p class="cmp-directory-note">Countries and continents are navigation filters, not imported leagues. Only competitions present in the current Python world can be opened.</p>
    </section>`;
  }
  function explorerFallback(){
    const navigation=explorerView==='mine'?clubTabs():directoryBrowser();
    const message=explorerView==='mine'?'Your club has no registered competitions for this season.':'Choose another region or filter above to explore the currently implemented leagues and cups.';
    return `<div class="cmp-root">${navigation}<section class="cmp-empty-directory panel"><span>◇</span><h3>No competition selected</h3><p>${h(message)}</p></section></div>`;
  }
  const isCup = () => stage === 'knockout' || data?.kind === 'cup';
  function rounds() {return isCup() ? (data?.knockout || []) : (data?.rounds || []);}
  function chosenRound() {return rounds().find(x=>x.id===roundId) || rounds()[0] || null;}
  const hasManagedDraw = () => (data?.knockout||[]).some(r=>r.ties.some(t=>t.managed));

  function activeRound(list){
    if (!list.length) return null;
    if (isCup()) {
      const known=list.filter(r=>r.drawn);
      return (known.find(r=>r.matches.some(m=>!m.score)) || known[known.length-1] || list[0]).id;
    }
    return (list.find(r=>r.matches.some(m=>!m.score)) || list[list.length-1]).id;
  }
  function rememberDefaults(){
    stage=(data.kind==='cup')?'knockout':'primary';
    if (data.kind==='league') stage='league';
    groupId=data.group_id||null;
    focus=hasManagedDraw()?'club':'all';
    zoomLevel=3;anchorTieId=null;
    roundId=activeRound(rounds());
  }
  function matchStatus(m){
    if(!m.score) return fixtureStamp(m);
    return `${m.score.home} – ${m.score.away}`;
  }
  function matchOutcome(m){
    if (!m.score) return '';
    if(m.penalties) return m.penalties.home > m.penalties.away ? 'home-win' : 'away-win';
    if(m.score.home===m.score.away) return 'draw';
    return m.score.home>m.score.away ? 'home-win':'away-win';
  }
  function displayRow(m, tie){
    const selected=m.managed;
    const extra=m.penalties?`<small class="cmp-pen-note">Pens ${m.penalties.home}–${m.penalties.away}</small>`:'';
    const agg=tie?.aggregate && tie.legs?.length>1 ? `<small class="cmp-agg-note">Aggregate ${tie.aggregate.a}–${tie.aggregate.b}${tie.complete?' · qualified: '+h(tie.winner_id===tie.club_a_id?tie.club_a:tie.club_b):' · pending'}</small>`:'';
    return `<div class="cmp-fixture-row ${selected?'cmp-highlight':''}" title="${h(shownClub(m.home_id,m.home))} vs ${h(shownClub(m.away_id,m.away))} · ${h(dayStamp(m.date))}">
      <div class="cmp-side-club"><button type="button" class="ts22-club-link" data-club-id="${h(m.home_id)}">${crest(m.home,m.home_id)}<span>${h(shownClub(m.home_id,m.home))}</span></button></div>
      <div class="cmp-game-score"><strong class="${matchOutcome(m)}">${h(matchStatus(m))}</strong>${extra}${agg}</div>
      <div class="cmp-side-club cmp-away"><button type="button" class="ts22-club-link" data-club-id="${h(m.away_id)}">${crest(m.away,m.away_id)}<span>${h(shownClub(m.away_id,m.away))}</span></button></div>
    </div>`;
  }
  function tieForFixture(round,fixtureId){ return round?.ties?.find(t=>t.legs.some(m=>m.id===fixtureId)); }

  function roundSidebar(){
    const r=chosenRound();
    if(!r) return `<section class="cmp-fixtures-panel panel"><h3>Fixtures</h3><p class="cmp-empty">No rounds available in this competition.</p></section>`;
    const list=r.matches || [];
    const current=rounds().findIndex(x=>x.id===r.id);
    const knockout=isCup();
    const played=list.filter(x=>x.score).length;
    let previousDay='';
    const items=list.map(m=>{
      const day=m.date||'';
      const heading=day!==previousDay?`<div class="cmp-date-group">${h(dayStamp(day))}</div>`:'';
      previousDay=day;
      return heading+displayRow(m,knockout?tieForFixture(r,m.id):null);
    }).join('');
    const empty=knockout && !r.drawn ? 'Draw not completed yet. The clubs and ties are not known.' : 'No registered fixtures in this round.';
    return `<section class="cmp-fixtures-panel panel">
      <div class="cmp-side-heading"><div><span class="cmp-side-kicker">${knockout?'Cup round':'League fixtures'}</span><h3>${h(r.label)}</h3></div>
        <div class="cmp-round-controls"><button type="button" data-cmp-step="-1" aria-label="Previous round" ${current===0?'disabled':''}>‹</button>
        <span title="Selected ${knockout?'round':'matchday'}">${current+1}/${rounds().length}</span>
        <button type="button" data-cmp-step="1" aria-label="Next round" ${current>=rounds().length-1?'disabled':''}>›</button></div></div>
      <div class="cmp-fixture-counter">${list.length} ${list.length===1?'match':'matches'} · ${played} played · All clubs${knockout?' · Leg scores shown individually':''}</div>
      <div class="cmp-fixtures-scroll">${items||`<div class="cmp-empty">${h(empty)}</div>`}</div>
      <div class="cmp-side-bottom">${knockout?'Rounds and results from real Python draw history.':'Standings show the current world state, not a historic table for the selected matchday.'}<br/>Crests from club identity catalog when available · Kickoffs in UTC</div>
    </section>`;
  }
  function table(){
    let tableRows=data.table||[];
    if(groupId && data.groups?.length){tableRows=data.groups.find(g=>g.id===groupId)?.table || tableRows;}
    const cls=p=>p==='relegation'||p==='eliminated'?'down':p==='direct'?'direct':p==='playoff'?'playoff':p==='advance'||p==='continental'?'up':'';
    const group=data.groups?.length?`<label class="cmp-group-picker">Group <select data-cmp-group aria-label="Choose group">${data.groups.map(g=>`<option value="${h(g.id)}" ${g.id===groupId?'selected':''}>${h(g.label)}${g.managed?' · My team':''}</option>`).join('')}</select></label>`:'';
    return `<div class="cmp-main-panel panel"><div class="cmp-panel-top"><div><span class="cmp-kicker">${data.kind==='multi'?(data.format==='uefa'?'36-TEAM LEAGUE PHASE':'GROUP STANDINGS'):'LEAGUE TABLE'}</span><h3>${h(data.kind==='multi'?(data.format==='uefa'?'League Phase':'Group Stage'):data.name)}</h3></div>${group}</div>
      <div class="cmp-table-wrap"><table class="cmp-table"><thead><tr><th>POS</th><th>TEAM</th><th>P</th><th>W</th><th>D</th><th>L</th><th>GF</th><th>GA</th><th>GD</th><th>PTS</th></tr></thead><tbody>
      ${tableRows.map(r=>`<tr class="${r.managed?'cmp-my-team':''} ${cls(r.route)?'cmp-zone-'+cls(r.route):''}" title="${h(r.route||'Current league position')}">
        <td class="cmp-pos">${r.position}</td><td><span class="cmp-team-cell"><button type="button" class="ts22-club-link" data-club-id="${h(r.club_id)}">${crest(r.club,r.club_id)}<strong>${h(shownClub(r.club_id,r.club))}</strong></button>${r.managed?'<small>YOU</small>':''}</span></td>
        <td>${number(r.played)}</td><td>${number(r.won)}</td><td>${number(r.drawn)}</td><td>${number(r.lost)}</td><td>${number(r.gf)}</td><td>${number(r.ga)}</td><td class="${r.gd>0?'cmp-positive':r.gd<0?'cmp-negative':''}">${r.gd>0?'+':''}${number(r.gd)}</td><td class="cmp-points">${number(r.points)}</td>
      </tr>`).join('')}</tbody></table></div>
      <div class="cmp-table-foot">${data.qualifications_note?h(data.qualifications_note):'Current league standings'} · Generated fictional clubs · ${data.table.length} total entrants</div>
    </div>`;
  }
  function tieScore(tie){
    if(!tie.aggregate) return '<strong>VS</strong>';
    const agg = tie.aggregate;
    return `<strong>${agg.a} – ${agg.b}</strong><small>${tie.legs.length>1?'Agg':''}${tie.penalties?' · pens':''}</small>`;
  }
  // The bracket is a symmetrical visual overview of the actual draw history.
  // Unresolved future draws are separate placeholders, NOT speculative pairings.
  // Zoom levels expose progressively more context, not just larger CSS text.
  const BRACKET_LEVELS = [
    {name:'Whole bracket',factor:1},
    {name:'Both sides',factor:1.8},
    {name:'Section',factor:3.25},
    {name:'Tie detail',factor:5.7}
  ];
  const BRACKET_COL = 181;
  const BRACKET_GAP = 56;
  const BRACKET_STEP = BRACKET_COL + BRACKET_GAP;
  const BRACKET_TOP = 78;
  const BRACKET_TILE_HEIGHT = 80;

  function bracketCard(tie, side, round) {
    const winner=tie.winner_id;
    const legText = tie.legs?.length>1 ? `${tie.legs.length} legs` : '';
    const outcome = tie.aggregate ? `${tie.aggregate.a}–${tie.aggregate.b}` : 'VS';
    const details = [legText, tie.penalties?'Penalties':''].filter(Boolean).join(' · ');
    return `<div class="cmp-bilateral-tie ${tie.managed?'cmp-tie-managed':''} ${tie.complete?'cmp-tie-complete':''}"
      data-cmp-tie="${h(tie.id)}" data-cmp-round="${h(round.id)}" data-cmp-side="${side}"
      title="${h(round.label)}: ${h(shownClub(tie.club_a_id,tie.club_a))} vs ${h(shownClub(tie.club_b_id,tie.club_b))} · ${h(outcome)}">
      <span class="cmp-bilateral-team ${winner===tie.club_a_id?'cmp-tie-winner':''}"><button type="button" class="ts22-club-link ts22-bracket-club" data-club-id="${h(tie.club_a_id)}">${crest(tie.club_a,tie.club_a_id)}<span class="cmp-bilateral-name">${h(shownClub(tie.club_a_id,tie.club_a))}</span></button></span>
      <button type="button" class="cmp-bilateral-score ts22-tie-details" data-cmp-tie="${h(tie.id)}" data-cmp-round="${h(round.id)}" data-cmp-side="${side}">${h(outcome)}<small>${h(details|| (tie.complete?'Final result':'Scheduled'))}</small></button>
      <span class="cmp-bilateral-team ${winner===tie.club_b_id?'cmp-tie-winner':''}"><button type="button" class="ts22-club-link ts22-bracket-club" data-club-id="${h(tie.club_b_id)}">${crest(tie.club_b,tie.club_b_id)}<span class="cmp-bilateral-name">${h(shownClub(tie.club_b_id,tie.club_b))}</span></button></span>
    </div>`;
  }

  function bracketGeometry(list) {
    const wings=Math.max(0,list.length-1);
    const widest=Math.max(1,...list.slice(0,-1).map(r=>Math.ceil((r.ties||[]).length/2)));
    return {w:Math.max(600,2*wings*BRACKET_STEP+BRACKET_COL+64),
            h:Math.max(615,widest*96+130), wings};
  }

  function bracketPlacement(list) {
    // Place confirmed predecessors on the same wing as their next drawn tie.
    // This is *layout*, not an assumption about undrawn future opponents.
    const wings=list.map(()=>({left:[],right:[]}));
    for(let index=list.length-2;index>=0;index--){
      const ties=list[index].ties||[], next=list[index+1];
      const planned={left:[],right:[]}, unplaced=[];
      for(const tie of ties){
        const progressing=tie.complete&&tie.winner_id&&next.drawn
          ?next.ties.find(t=>[t.club_a_id,t.club_b_id].includes(tie.winner_id))
          :null;
        const side=progressing && wings[index+1].left.some(t=>t.id===progressing.id)?'left'
                  :progressing && wings[index+1].right.some(t=>t.id===progressing.id)?'right':null;
        if(side)planned[side].push({tie,target:progressing.id});
        else unplaced.push(tie);
      }
      const targetLeft=Math.ceil(ties.length/2);
      for(const tie of unplaced){
        const side=planned.left.length<targetLeft?'left':'right';
        planned[side].push({tie,target:null});
      }
      for(const side of ['left','right']){
        const succeeding=wings[index+1][side];
        planned[side].sort((a,b)=>{
          const ia=a.target?succeeding.findIndex(t=>t.id===a.target):-1;
          const ib=b.target?succeeding.findIndex(t=>t.id===b.target):-1;
          return (ia<0?Number.MAX_SAFE_INTEGER:ia)-(ib<0?Number.MAX_SAFE_INTEGER:ib);
        });
        wings[index][side]=planned[side].map(x=>x.tie);
      }
    }
    return wings;
  }

  function bracketWing(round,index,side,geometry,placement) {
    const x=side==='left' ? 32+index*BRACKET_STEP
                          : geometry.w-32-BRACKET_COL-index*BRACKET_STEP;
    const selected=round.id===roundId?' cmp-active-round':'';
    const header=`<button type="button" class="cmp-bilateral-round-head${selected}"
      data-cmp-select-round="${h(round.id)}" style="left:${x}px;top:18px;width:${BRACKET_COL}px">
      ${h(round.label)}<small>${round.drawn?`${round.ties.length} ties in draw`:'Draw pending'}</small></button>`;
    const ties=placement[index][side];
    if(!round.drawn || ties.length===0){
      return header+`<div class="cmp-bracket-pending cmp-bilateral-placeholder" data-cmp-round="${h(round.id)}"
        style="left:${x}px;top:${Math.round(geometry.h/2-55)}px;width:${BRACKET_COL}px">
        <span class="cmp-pending-icon">◇</span> ${round.drawn?'No ties on this side':'Draw pending'}
        <small>${round.drawn?'All confirmed matches are shown':'Opponents not known'}</small></div>`;
    }
    const available=geometry.h-145;
    return header+ties.map((tie,i)=>{
      const cy=BRACKET_TOP+(i+.5)*available/ties.length;
      return `<div class="cmp-bilateral-slot" style="left:${x}px;top:${Math.round(cy-BRACKET_TILE_HEIGHT/2)}px;width:${BRACKET_COL}px;height:${BRACKET_TILE_HEIGHT}px">
        ${bracketCard(tie,side,round)}</div>`;
    }).join('');
  }

  function bracketFinal(round,geometry){
    const x=Math.round((geometry.w-BRACKET_COL)/2);
    const y=Math.round(geometry.h/2-BRACKET_TILE_HEIGHT/2);
    const ties=round?.ties||[];
    const header=`<div class="cmp-bilateral-final-label" style="left:${x-20}px;top:13px;width:${BRACKET_COL+40}px">
      <span aria-hidden="true">🏆</span><strong>${h(round?.label||'Final')}</strong><small>Centre of the bracket</small></div>`;
    const content=ties.length?ties.map((tie,i)=>{
      const pos=y+(i-(ties.length-1)/2)*100;
      return `<div class="cmp-bilateral-slot cmp-final-slot" style="left:${x}px;top:${pos}px;width:${BRACKET_COL}px;height:${BRACKET_TILE_HEIGHT}px">${bracketCard(tie,'final',round)}</div>`;
    }).join(''):`<div class="cmp-bracket-pending cmp-bilateral-placeholder cmp-bilateral-final-pending"
      style="left:${x}px;top:${y-16}px;width:${BRACKET_COL}px">
      <span class="cmp-pending-icon">◇</span> Final not drawn
      <small>No projected finalists</small></div>`;
    return `<div class="cmp-bilateral-centre" aria-label="Final stage">${header}${content}</div>`;
  }

  function bracket(){
    const list=data.knockout||[];
    if(!list.length){return `<section class="cmp-main-panel cmp-bracket-panel panel"><div class="cmp-empty">No knockout stages registered yet.</div></section>`;}
    const geometry=bracketGeometry(list);
    const preceding=list.slice(0,-1);
    const final=list[list.length-1];
    const placement=bracketPlacement(list);
    const wings=preceding.map((r,i)=>bracketWing(r,i,'left',geometry,placement)+bracketWing(r,i,'right',geometry,placement)).join('');
    const entry=data.managed_entry_round_label;
    const pendingEntry=!hasManagedDraw()&&entry?` · ${h(data.managed_club)} enters ${h(entry)} (draw pending)`:'';
    return `<section class="cmp-main-panel cmp-bracket-panel panel"><div class="cmp-panel-top"><div>
      <span class="cmp-kicker">TWO-SIDED KNOCKOUT BRACKET</span><h3>${h(data.name)} · Road to the final</h3></div>
      <div class="cmp-bracket-actions">
      <button type="button" data-cmp-focus="club" class="${focus==='club'?'on':''}" ${!hasManagedDraw()?'disabled title="Your tie has not been drawn yet"':''}>My path</button>
      <button type="button" data-cmp-focus="all" class="${focus==='all'?'on':''}">Full bracket</button>
      <div class="cmp-zoom" role="group" aria-label="Bracket zoom and scope">
        <button type="button" data-cmp-zoom="-1" aria-label="Zoom out to show more of the bracket" ${zoomLevel===0?'disabled':''}>−</button>
        <span class="cmp-zoom-label" aria-live="polite">${BRACKET_LEVELS[zoomLevel].name}</span>
        <button type="button" data-cmp-zoom="1" aria-label="Zoom in to show more tie detail" ${zoomLevel===BRACKET_LEVELS.length-1?'disabled':''}>+</button>
      </div></div></div>
      <div class="cmp-bracket-scroll" data-cmp-pan tabindex="0" aria-label="Two-sided knockout bracket, pan to explore both sides">
        <div class="cmp-bracket-board cmp-bilateral-board" data-level="${zoomLevel}" style="width:${geometry.w}px;height:${geometry.h}px">
          <div class="cmp-bilateral-background" aria-hidden="true"></div>
          ${wings}${bracketFinal(final,geometry)}
        </div>
      </div>
      <div class="cmp-bracket-foot"><strong>−</strong> reveals both sides and the final · <strong>+</strong> zooms into individual ties · Drag/scroll to explore.${pendingEntry}
      <br/>Solid links mean confirmed progression only. Faded line ends indicate an unresolved future draw; no opponents or pairings are predicted.</div>
    </section>`;
  }
  function layout(){
    const active=chosenRound();
    const hasSubtabs=data.stages?.length>1;
    return `<div class="cmp-root" data-competition-brand="${h(ci(data.id).key)}" style="${ciVars(data.id)}">
      ${explorerView==='mine'?clubTabs():directoryBrowser()}
      <div class="cmp-topline"><div class="cmp-title"><div class="cmp-title-emblem">${ciLogo(data.id,'ci-title-logo')}</div><div><span class="cmp-kicker">${h(data.kind==='cup'?'KNOCKOUT CUP':data.kind==='league'?'DOMESTIC LEAGUE':data.format==='uefa'?'EUROPEAN COMPETITION':'GROUP + KNOCKOUT')}</span><h2>${h(data.name)}</h2><p>Season ${h(data.season)} · Fictional participants · Real Python data</p></div></div>
        <div class="cmp-meta"><button type="button" class="ch-primary" data-career-type="competition" data-career-id="${h(data.id)}">Past seasons ↗</button><span><small>SEASON</small><strong>${h(data.season)}</strong></span><span><small>CURRENT VIEW</small><strong>${h(active?.label||'Pending draw')}</strong></span></div></div>
      ${hasSubtabs?`<div class="cmp-stages" role="group" aria-label="Competition stage">${data.stages.map(s=>`<button type="button" data-cmp-stage="${h(s.id)}" class="${s.id===stage?'active':''}" aria-pressed="${s.id===stage}">${h(s.label)}</button>`).join('')}</div>`:''}
      <div class="cmp-round-toolbar"><div><span>SELECT ${isCup()?'ROUND':'MATCHDAY'}</span><select data-cmp-round aria-label="Select ${isCup()?'round':'matchday'}">${rounds().map(r=>`<option value="${h(r.id)}" ${r.id===roundId?'selected':''}>${h(r.label)}${isCup()&&!r.drawn?' · not drawn':''}</option>`).join('')}</select><button type="button" data-cmp-current>Current</button></div>
      <p>${isCup()?'Both sides · confirmed draws only':'Scores shown for actual played fixtures only'}</p></div>
      <div class="cmp-layout">${isCup()?bracket():table()}${roundSidebar()}</div>
      <div class="cmp-global-note">All results and schedules read from WorldSeasonRunner · Future rounds require actual draws · No simulated history or official team matchups · Continue remains inactive.</div>
    </div>`;
  }
  // Bracket links are drawn only for documented winners who appear in the
  // next actually drawn round. Decorative short stubs deliberately do not join
  // different ties: a random future draw has no predetermined tree structure.
  function drawConfirmedLinks(){
    if(!root||!data||!isCup())return;
    const board=root.querySelector('.cmp-bilateral-board');
    if(!board)return;
    board.querySelector('.cmp-bracket-links')?.remove();
    const list=data.knockout||[];
    const tiles=[...board.querySelectorAll('.cmp-bilateral-tie')];
    const paths=[];
    function getTile(id){return tiles.find(tile=>tile.dataset.cmpTie===id);}
    for(let i=0;i<list.length-1;i++){
      const current=list[i], next=list[i+1];
      if(!current.drawn||!next.drawn)continue;
      for(const tie of current.ties){
        if(!tie.complete||!tie.winner_id)continue;
        const target=next.ties.find(candidate=>[candidate.club_a_id,candidate.club_b_id].includes(tie.winner_id));
        if(!target)continue;
        const source=getTile(tie.id), dest=getTile(target.id);
        if(!source||!dest)continue;
        const a=source.closest('.cmp-bilateral-slot'),b=dest.closest('.cmp-bilateral-slot');
        if(!a||!b)continue;
        const toRight=source.dataset.cmpSide==='left';
        const destSide=dest.dataset.cmpSide;
        if(destSide!=='final' && destSide!==source.dataset.cmpSide)continue;
        const destOnLeft=destSide==='left'||(destSide==='final'&&toRight);
        const x1=a.offsetLeft+(toRight?a.offsetWidth:0), y1=a.offsetTop+a.offsetHeight/2;
        const x2=b.offsetLeft+(destOnLeft?0:b.offsetWidth),y2=b.offsetTop+b.offsetHeight/2;
        const mid=(x1+x2)/2;
        paths.push(`<path class="cmp-confirmed-link" d="M ${x1} ${y1} H ${mid} V ${y2} H ${x2}"/>`);
      }
    }
    // Subtle free-ended dashes create a cup-bracket silhouette without
    // claiming two arbitrary ties feed into the same future opponent.
    for(const tile of tiles){
      if(tile.dataset.cmpSide==='final')continue;
      const slot=tile.closest('.cmp-bilateral-slot');
      const rightward=tile.dataset.cmpSide==='left';
      const x=slot.offsetLeft+(rightward?slot.offsetWidth:0);
      const end=x+(rightward?23:-23),y=slot.offsetTop+slot.offsetHeight/2;
      paths.push(`<path class="cmp-unresolved-stub" d="M ${x} ${y} H ${end}"/>`);
    }
    const svg=document.createElementNS('http://www.w3.org/2000/svg','svg');
    svg.classList.add('cmp-bracket-links');
    svg.setAttribute('width',String(board.offsetWidth));
    svg.setAttribute('height',String(board.offsetHeight));
    svg.setAttribute('viewBox',`0 0 ${board.offsetWidth} ${board.offsetHeight}`);
    svg.innerHTML=paths.join('');
    board.prepend(svg);
  }
  function updateBracketViewport(){
    const viewport=root?.querySelector('.cmp-bracket-scroll');
    const board=viewport?.querySelector('.cmp-bilateral-board');
    if(!viewport||!board)return;
    const baseFit=Math.min((viewport.clientWidth-12)/board.offsetWidth,
                           (viewport.clientHeight-12)/board.offsetHeight,1);
    const scale=clamp(baseFit*BRACKET_LEVELS[zoomLevel].factor,.09,1.48);
    board.style.zoom=String(scale);
    const percentage=Math.round(scale*100);
    const zoomLabel=root.querySelector('.cmp-zoom-label');
    if(zoomLabel)zoomLabel.textContent=`${BRACKET_LEVELS[zoomLevel].name} · ${percentage}%`;
    drawConfirmedLinks();
    let target=null;
    if(anchorTieId)target=[...board.querySelectorAll('.cmp-bilateral-tie')].find(el=>el.dataset.cmpTie===anchorTieId);
    if(!target && focus==='club')target=board.querySelector('.cmp-tie-managed');
    if(!target && focus==='club' && data.managed_entry_round_id){
      target=[...board.querySelectorAll('.cmp-bilateral-round-head')].find(el=>el.dataset.cmpSelectRound===data.managed_entry_round_id);
    }
    if(!target && zoomLevel>0){
      target=[...board.querySelectorAll('.cmp-bilateral-tie')].find(el=>el.dataset.cmpRound===roundId)
             ||board.querySelector('.cmp-bilateral-final-label');
    }
    if(zoomLevel===0 || (!target && focus==='all')){
      viewport.scrollLeft=Math.max(0,(board.offsetWidth*scale-viewport.clientWidth)/2);
      viewport.scrollTop=Math.max(0,(board.offsetHeight*scale-viewport.clientHeight)/2);
      return;
    }
    if(target){
      const anchor=target.closest('.cmp-bilateral-slot')||target;
      viewport.scrollLeft=Math.max(0,(anchor.offsetLeft+anchor.offsetWidth/2)*scale-viewport.clientWidth/2);
      viewport.scrollTop=Math.max(0,(anchor.offsetTop+anchor.offsetHeight/2)*scale-viewport.clientHeight/2);
    }
  }
  function render(){
    if(!root)return;
    if(!index){root.innerHTML='<div class="cmp-loading panel">Loading competitions from Python…</div>';return;}
    root.innerHTML=data?layout():explorerFallback();
    if(data?.kind==='league' && window.FMWorldSquads){
      const squads=document.createElement('section');
      squads.className='ws-root panel';
      root.appendChild(squads);
      window.FMWorldSquads.mount(squads,data.id);
    }
    if(isCup())requestAnimationFrame(updateBracketViewport);
  }
  async function loadIndex(){
    if(!root)return;
    const seq=++indexSerial;
    try{
      const res=await fetch('/api/competitions',{cache:'no-store'});
      if(!res.ok)throw Error(`HTTP ${res.status}`);
      const next=await res.json();
      if(seq!==indexSerial)return;
      // The UI and Python index are a single interface contract. If only
      // UI files were updated, old Python may still return ten competitions
      // in `competitions` and no `other_competitions`: never render that as
      // ten club tabs and an empty Other Leagues page.
      if(next.schema_version!==2 || !Array.isArray(next.competitions) ||
         !Array.isArray(next.other_competitions) ||
         next.competitions.some(c=>c.managed!==true) ||
         next.other_competitions.some(c=>c.managed!==false)){
        throw Error('OUTDATED_COMPETITIONS_API');
      }
      index=next;
      const available=filteredOptions();
      const prefer=available.find(x=>x.id==='dev-premier') || available[0];
      const nextId=available.some(c=>c.id===selectedComp)?selectedComp:prefer?.id;
      if(nextId)await chooseCompetition(nextId);
      else{detailSerial++;data=null;selectedComp=null;render();}
    }catch(err){
      if(seq!==indexSerial)return;
      console.warn('Competitions unavailable',err);
      const stale=String(err?.message)==='OUTDATED_COMPETITIONS_API';
      root.innerHTML=stale
        ?'<section class="cmp-error panel" role="alert"><h2>Python backend desactualizado</h2><p>El servidor todav&iacute;a devuelve la lista antigua de competiciones. Cerr&aacute; TODAS las ventanas del servidor (Ctrl+C), copi&aacute; el hotfix completo en la carpeta del juego incluyendo src/football_manager/ui_shell/competitions.py, reinici&aacute; INICIAR_INTERFAZ_WINDOWS.bat y actualiz&aacute; con Ctrl+Shift+R. No se mostraron competiciones incorrectas.</p><button type="button" data-cmp-retry>Reintentar</button></section>'
        :'<section class="cmp-error panel"><h2>Competitions unavailable</h2><p>Start the game using INICIAR_INTERFAZ_WINDOWS.bat. The UI will not invent standings or brackets when Python is offline.</p><button type="button" data-cmp-retry>Retry</button></section>';
    }
  }
  async function chooseCompetition(id){
    if(!root||!id)return;
    const seq=++detailSerial;
    selectedComp=id;
    selectedByView[explorerView]=id;
    root.innerHTML=`<div class="cmp-root">${explorerView==='mine'?clubTabs():directoryBrowser()}<section class="cmp-loading panel">Loading actual competition results and fixtures…</section></div>`;
    try{
      const res=await fetch('/api/competitions/'+encodeURIComponent(id),{cache:'no-store'});
      if(!res.ok)throw Error(`HTTP ${res.status}`);
      const detail=await res.json();
      if(seq!==detailSerial)return;
      if(detail.id!==id || !Array.isArray(detail.stages))throw Error('Invalid competition data');
      data=detail;rememberDefaults();render();
    }catch(err){
      if(seq!==detailSerial)return;
      console.warn('Competition details unavailable',err);
      data=null;
      root.innerHTML='<section class="cmp-error panel"><h2>Competition unavailable</h2><p>Could not retrieve this competition from Python. No fixtures or scores were generated.</p><button type="button" data-cmp-retry>Retry</button></section>';
    }
  }
  function nearestCurrent(){roundId=activeRound(rounds());anchorTieId=null;render();}
  function clicked(event){
    const btn=event.target.closest('button');
    if(!btn||!root.contains(btn))return;
    if(btn.hasAttribute('data-cmp-retry')){loadIndex();return;}
    if(btn.hasAttribute('data-cmp-competition')){
      const id=btn.dataset.cmpCompetition;
      if(explorerView==='mine' && opts().some(c=>c.id===id) && id!==selectedComp)chooseCompetition(id);
      return;
    }
    if(!data)return;
    if(btn.hasAttribute('data-cmp-stage')){stage=btn.dataset.cmpStage;roundId=activeRound(rounds());focus=hasManagedDraw()?'club':'all';zoomLevel=3;anchorTieId=null;render();return;}
    if(btn.hasAttribute('data-cmp-step')){const rs=rounds(),i=rs.findIndex(x=>x.id===roundId);roundId=rs[clamp(i+Number(btn.dataset.cmpStep),0,rs.length-1)]?.id||roundId;anchorTieId=null;render();return;}
    if(btn.hasAttribute('data-cmp-current')){nearestCurrent();return;}
    if(btn.hasAttribute('data-cmp-select-round')){roundId=btn.dataset.cmpSelectRound;anchorTieId=null;render();return;}
    if(btn.hasAttribute('data-cmp-focus')){focus=btn.dataset.cmpFocus;anchorTieId=null;zoomLevel=focus==='all'?0:3;render();return;}
    if(btn.hasAttribute('data-cmp-zoom')){
      zoomLevel=clamp(zoomLevel+Number(btn.dataset.cmpZoom),0,BRACKET_LEVELS.length-1);
      render();return;
    }
    if(btn.hasAttribute('data-cmp-tie')){
      const r=(data.knockout||[]).find(r=>r.ties.some(t=>t.id===btn.dataset.cmpTie));
      if(r){roundId=r.id;anchorTieId=btn.dataset.cmpTie;render();}
    }
  }
  function changed(event){
    const el=event.target;
    if(explorerView==='other' && el.matches('[data-cmp-filter]')){
      const field=el.dataset.cmpFilter;
      if(!Object.hasOwn(filters,field))return;
      filters[field]=el.value;
      if(field==='scope'){
        filters.country='all';filters.division='all';filters.type='all';
      }
      if(field==='continent') {filters.country='all';filters.division='all';}
      if(field==='type')filters.division='all';
      if(field==='country')filters.division='all';
      const available=filteredOptions();
      if(!available.length){detailSerial++;selectedComp=null;data=null;render();return;}
      if(available.some(c=>c.id===selectedComp)&&data?.id===selectedComp){render();return;}
      chooseCompetition(available[0].id);return;
    }
    if(explorerView==='other' && el.matches('[data-cmp-competition-select]')){
      if(filteredOptions().some(c=>c.id===el.value) && el.value!==data?.id)chooseCompetition(el.value);
      return;
    }
    if(el.matches('[data-cmp-round]')){roundId=el.value;anchorTieId=null;render();}
    if(el.matches('[data-cmp-group]')){groupId=el.value;render();}
  }
  function mount(node, mode='mine', requested=null){
    if(mode!=='mine' && mode!=='other')throw Error('Unknown competition screen');
    if(root!==node){
      root=node;
      root.addEventListener('click',clicked);
      root.addEventListener('change',changed);
      // Drag empty parts of the zoomed canvas to browse either wing.
      // Clicking an actual match card still opens that round normally.
      root.addEventListener('pointerdown',event=>{
        const pane=event.target.closest('.cmp-bracket-scroll');
        if(!pane||event.button!==0||event.target.closest('button'))return;
        dragState={pane,x:event.clientX,y:event.clientY,left:pane.scrollLeft,top:pane.scrollTop};
        pane.setPointerCapture(event.pointerId);
      });
      root.addEventListener('pointermove',event=>{
        if(!dragState)return;
        dragState.pane.scrollLeft=dragState.left+dragState.x-event.clientX;
        dragState.pane.scrollTop=dragState.top+dragState.y-event.clientY;
      });
      root.addEventListener('pointerup',()=>{dragState=null;});
      root.addEventListener('pointercancel',()=>{dragState=null;});
    }
    if(explorerView!==mode){
      selectedByView[explorerView]=selectedComp;
      explorerView=mode;
      selectedComp=selectedByView[mode];
      data=null;
      detailSerial++;
    }
    if(requested){selectedComp=requested;selectedByView[mode]=requested;}
    loadIndex();
  }
  return {mount,refresh:()=>loadIndex()};
})();
