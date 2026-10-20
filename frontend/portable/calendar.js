/* UI-3.4.1: managed-club calendar with clickable days, sourced from /api/calendar.
   No fake historical games, stadiums, results, opponents or day progression. */
window.FMCalendar = (() => {
  'use strict';
  let root=null, snapshot=null, month=null, filter='all', selectedId=null, selectedDate=null, simulating=false, requestId=0;
  const html=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const names=['January','February','March','April','May','June','July','August','September','October','November','December'];
  const shortWeekdays=['Mon','Tue','Wed','Thu','Fri','Sat','Sun'];
  const competitionKind=id=>({'dev-premier':'league',league:'league','fa-cup':'fa','carabao-cup':'carabao','champions-league':'champions','europa-league':'europa','conference-league':'conference','efl-trophy':'trophy'})[id]||'other';
  const hash=s=>[...String(s)].reduce((v,c)=>(Math.imul(v,31)+c.charCodeAt(0))|0,17);
  const badge=(name,managed=false)=>{
    const hue=managed?204:Math.abs(hash(name))%360;
    const abbr=managed?'N':String(name).split(/[\s-]+/).filter(Boolean).slice(0,2).map(x=>x[0]).join('').toUpperCase();
    return `<span class="cal-crest ${managed?'cal-crest-managed':''}" style="--crest-hue:${hue}" role="img" aria-label="Fictional ${html(name)} crest"><span>${html(abbr||'?')}</span></span>`;
  };
  const parseUTC=s=>new Date(`${s}T12:00:00Z`);
  const monthOf=date=>date.slice(0,7);
  const today=()=>snapshot?.date||new Date().toISOString().slice(0,10);
  const fmtDay=s=>new Intl.DateTimeFormat('en-GB',{day:'numeric',month:'short',year:'numeric',weekday:'short',timeZone:'UTC'}).format(parseUTC(s));
  const kickoff=iso=>iso ? `${iso.slice(11,16)} UTC` : 'Time TBD';
  const outcomeClass=o=>o==='V'?'win':o==='D'?'loss':o==='E'?'draw':'pending';
  const outcomeLabel=o=>o==='V'?'Win':o==='D'?'Loss':o==='E'?'Draw':'Upcoming';
  const scoreText=g=>g.score?`${g.score.home}–${g.score.away}`:kickoff(g.kickoff);
  const tileScore=g=>g.score?scoreText(g):(g.kickoff?g.kickoff.slice(11,16):'TBD');
  const isManaged=(club)=>club===snapshot.club;
  function switchMonth(step){
    const [year,m]=month.split('-').map(Number);
    const next=new Date(Date.UTC(year,m-1+step,1));
    month=`${next.getUTCFullYear()}-${String(next.getUTCMonth()+1).padStart(2,'0')}`;
    const visible=visibleMatches();
    selectedId=visible.length?visible[0].id:null;
    selectedDate=null;
    render();
  }
  function visibleMatches(){return (snapshot?.matches||[]).filter(g=>g.date.startsWith(month)&&(filter==='all'||g.competition_id===filter));}
  function selectBest(){
    const games=visibleMatches();
    if(games.some(g=>g.id===selectedId))return;
    if(selectedDate!==null){
      selectedId=games.find(g=>g.date===selectedDate)?.id||null;
      return;
    }
    const upcoming=games.find(g=>g.date>=today()&&!g.score);
    const picked=upcoming||games[0];
    selectedId=picked?.id||null;
    selectedDate=picked?.date||today();
  }
  function fixture(g){
    const picked=g.id===selectedId;
    const cls=outcomeClass(g.outcome);
    return `<button type="button" data-cal-match="${html(g.id)}" class="cal-fixture cal-comp-${competitionKind(g.competition_id)} cal-${cls}${picked?' cal-selected':''}" aria-pressed="${picked}" aria-label="${html(g.competition)}: ${html(g.opponent)} ${g.home?'home':'away'} ${html(g.score?scoreText(g):'upcoming')}" title="${html(g.competition)} · ${html(g.round)}">
      <span class="cal-fixture-top"><span class="cal-comp-dot"></span><span>${html(g.competition)}</span></span>
      <span class="cal-fixture-main">${badge(g.home_club,isManaged(g.home_club))}${badge(g.away_club,isManaged(g.away_club))}<span class="cal-venue">${g.home?'H':'A'}</span><strong class="cal-fixture-score">${html(tileScore(g))}</strong></span>
      <span class="cal-fixture-opponent" role="link" tabindex="0" data-cal-club="${html(g.opponent_id)}">${html(g.opponent)}</span>
      ${g.score?`<span class="cal-outcome-label cal-outcome-${cls}">${outcomeLabel(g.outcome)}${g.penalties?' · pens':''}</span>`:''}
    </button>`;
  }
  function fifaWindow(iso){
    return (snapshot?.fifa_windows||[]).find(w=>w.start<=iso&&iso<=w.end)||null;
  }
  function grid(){
    const [year,m]=month.split('-').map(Number);
    const first=new Date(Date.UTC(year,m-1,1));
    const start=(first.getUTCDay()+6)%7;
    const count=new Date(Date.UTC(year,m,0)).getUTCDate();
    const cells=Math.ceil((start+count)/7)*7;
    const matches=visibleMatches();
    const byDate=new Map();
    for(const g of matches){if(!byDate.has(g.date))byDate.set(g.date,[]);byDate.get(g.date).push(g);}
    return `<div class="cal-weekdays">${shortWeekdays.map(d=>`<div>${d}</div>`).join('')}</div>
    <div class="cal-days">${Array.from({length:cells},(_,i)=>{
      const day=i-start+1;
      const valid=day>=1&&day<=count;
      const iso=`${month}-${String(day).padStart(2,'0')}`;
      const games=valid?byDate.get(iso)||[]:[];
      const active=iso===today();
      const international=valid?fifaWindow(iso):null;
      const marker=international?`<span class="cal-fifa-mark" role="img" aria-label="${html(international.name)}" title="${html(international.name)}">🌐</span>`:'';
      const past=valid && iso<today();
      const ghost=new Date(Date.UTC(year,m-1,day)).getUTCDate();
      return `<div class="cal-day ${valid?'':'cal-outside'} ${past?'cal-past':''} ${active?'cal-today':''} ${iso>today()?'cal-future':''} ${iso===selectedDate?'cal-selected-day':''}"${valid?` data-cal-cell="${iso}" role="gridcell" tabindex="0" aria-label="${html(fmtDay(iso))}, ${games.length} fixtures${international?', FIFA window':''}"`:''}${active?' aria-current="date"':''}>
        ${valid?`<div class="cal-day-label"><button type="button" class="cal-day-select" data-cal-date="${iso}" title="Select ${iso}" aria-label="Select ${iso} to auto-simulate through this date">${day}</button>${active?'<small>TODAY</small>':''}${marker}</div>${games.map(fixture).join('')}`:`<div class="cal-day-label"><span>${ghost}</span></div>`}
      </div>`;
    }).join('')}</div>`;
  }
  function detail(){
    const g=snapshot.matches.find(x=>x.id===selectedId);
    if(!g)return `<section class="cal-detail-card panel"><h3>Match details</h3><div class="cal-no-selection">No match scheduled on ${html(fmtDay(selectedDate||today()))}.<p>You can still auto-simulate to this date. Future cup ties appear only after the Python world draws them.</p></div></section>`;
    const resultClass=outcomeClass(g.outcome);
    const aggregate=g.aggregate;
    const aggInfo=aggregate?`<div class="cal-aggregate"><strong>Aggregate · ${aggregate.managed_goals}–${aggregate.opponent_goals}</strong><span>${aggregate.complete?(aggregate.qualified?'Qualified on aggregate / tiebreak':'Eliminated on aggregate / tiebreak'):'Tie not decided yet'}</span></div>`:'';
    return `<section class="cal-detail-card panel cal-comp-${competitionKind(g.competition_id)}">
      <div class="cal-side-title"><span>${html(g.competition)} · ${html(g.round)}</span><span class="cal-side-source">${html(g.source.toUpperCase())} pairing</span></div>
      <div class="cal-detail-stadium"><div class="cal-detail-teams">
        <div><button type="button" class="ts22-club-link" data-club-id="${html(g.home_id)}">${badge(g.home_club,isManaged(g.home_club))}<strong>${html(g.home_club)}</strong></button><small>Home</small></div>
        <span class="cal-vs">${g.score?`${g.score.home} : ${g.score.away}`:'VS'}</span>
        <div><button type="button" class="ts22-club-link" data-club-id="${html(g.away_id)}">${badge(g.away_club,isManaged(g.away_club))}<strong>${html(g.away_club)}</strong></button><small>Away</small></div>
      </div></div>
      <div class="cal-detail-meta"><span>▦ ${html(fmtDay(g.date))}</span><span>◷ ${html(kickoff(g.kickoff))}</span></div>
      <div class="cal-detail-body">
        <div class="cal-stage-row"><span>${html(g.round)}</span><strong class="cal-locality">${g.home?'Home fixture':'Away fixture'}</strong></div>
        <div class="cal-stage-row"><span>Status</span><strong>${html(g.score?'Played':g.status==='scheduled'?'Scheduled':g.status)}</strong></div>
        ${g.rescheduled&&g.original_date?`<div class="cal-stage-row"><span>Rescheduled from</span><strong>${html(fmtDay(g.original_date))}</strong></div>`:''}
        ${g.score?`<div class="cal-result-panel cal-result-${resultClass}"><strong>${html(outcomeLabel(g.outcome))} · ${html(scoreText(g))}</strong><small>${g.penalties?`Penalty shootout ${g.penalties.home}–${g.penalties.away} · winner determines result colour`:'Score of this individual match'}</small></div>`:'<div class="cal-fixture-pending">Match not played yet. No result has been registered in Python.</div>'}
        ${aggInfo}
        <div class="cal-truth-note">Fixture from the current fictional Python season. Club crests are provisional. Stadium, referee and match preview are not yet connected.</div>
      </div>
    </section>`;
  }
  function simulateBox(){
    const target=selectedDate||today();
    const past=target<today();
    const beyond=target>(window.FMProgression?.state()?.season_cutoff||'9999-12-31');
    return `<section class="cal-sim-card panel"><div class="cal-sim-heading"><span>Selected day</span><strong>${html(fmtDay(target))}</strong></div>
      <p>Auto-simulates every fixture, including Northbridge matches, until this day. Only a real intervention event would pause it (those events are not yet implemented).</p>
      <button type="button" data-cal-simulate="${html(target)}" ${past||beyond||simulating?'disabled':''}>
      ${simulating?'Simulating...':past?'Past date':beyond?'Outside current season':'Simulate to this date →'}</button>
      <small>DEV session only · Results are not saved when the server closes.</small>
    </section>`;
  }
  function upcoming(){
    const list=snapshot.matches.filter(g=>!g.score&&g.status==='scheduled'&&g.date>=today()).slice(0,6);
    return `<section class="cal-next-card panel"><div class="cal-next-heading"><h3>Upcoming fixtures</h3><small>From Python</small></div>${list.length?list.map(g=>`<button type="button" data-cal-upcoming="${html(g.id)}"><span class="cal-next-date">${html(g.date.slice(8,10))} ${html(names[Number(g.date.slice(5,7))-1].slice(0,3))}</span><span class="cal-next-comp cal-comp-${competitionKind(g.competition_id)}"></span>${badge(g.opponent)}<span class="cal-next-team">${html(g.opponent)}<small>${html(g.competition)}</small></span><span class="cal-next-venue">${g.home?'H':'A'}</span></button>`).join(''):'<p class="cal-empty-upcoming">No future fixtures are scheduled.</p>'}</section>`;
  }
  function render(){
    if(!root)return;
    if(!snapshot){root.innerHTML='<section class="cal-loading">Loading the club calendar from Python…</section>';return;}
    selectBest();
    const [y,m]=month.split('-').map(Number);
    const opts=[{id:'all',name:'All competitions'},...snapshot.competitions];
    root.innerHTML=`<div class="cal-root" role="region" aria-label="Northbridge FC calendar">
      <div class="cal-toolbar"><div class="cal-month-controls"><button type="button" data-cal-action="prev" aria-label="Previous month">‹</button><span aria-live="polite">${names[m-1]} ${y}</span><button type="button" data-cal-action="next" aria-label="Next month">›</button><button class="cal-today-button" type="button" data-cal-action="today">Today</button></div>
      <div class="cal-filter-tabs" role="group" aria-label="Filter by competition">${opts.map(c=>`<button type="button" data-cal-filter="${html(c.id)}" class="cal-filter-chip cal-comp-${competitionKind(c.id)} ${filter===c.id?'active':''}" aria-pressed="${filter===c.id}"><span class="cal-comp-dot"></span>${html(c.name)}</button>`).join('')}</div></div>
      <div class="cal-layout"><div class="cal-month panel">${grid()}<footer class="cal-legend"><span><i class="win"></i>Win</span><span><i class="draw"></i>Draw</span><span><i class="loss"></i>Loss</span><small>Background = competition · Border = result · All dates/results from Python</small></footer></div><aside class="cal-sidebar">${simulateBox()}${detail()}${upcoming()}</aside></div>
      <div class="cal-footer-note">${html(snapshot.season)} · Fictional clubs and generated opponents · ${snapshot.matches.length} known fixtures · UTC kickoffs. No future draw or past result is invented. Continue advances one day; Calendar can auto-play your matches.</div>
    </div>`;
  }
  function click(event){
    const club=event.target.closest("[data-cal-club]");if(club){event.preventDefault();event.stopPropagation();window.FMNavigation?.club(club.dataset.calClub);return;}
    const button=event.target.closest('button');
    if(!button||!root.contains(button))return;
    if(button.dataset.calAction){
      if(button.dataset.calAction==='today'){month=monthOf(today());filter='all';selectedId=null;selectedDate=today();render();}
      else switchMonth(button.dataset.calAction==='prev'?-1:1);
    }else if(button.dataset.calFilter){filter=button.dataset.calFilter;selectedId=null;render();}
    else if(button.dataset.calDate){selectedDate=button.dataset.calDate;selectedId=null;render();}
    else if(button.dataset.calMatch){selectedId=button.dataset.calMatch;selectedDate=snapshot.matches.find(g=>g.id===selectedId)?.date||selectedDate;render();}
    else if(button.dataset.calUpcoming){const match=snapshot.matches.find(g=>g.id===button.dataset.calUpcoming);if(match){month=monthOf(match.date);filter='all';selectedId=match.id;selectedDate=match.date;render();}}
    else if(button.dataset.calSimulate)runSimulation(button.dataset.calSimulate);
  }
  function cellClick(event){
    const cell=event.target.closest('[data-cal-cell]');
    if(!cell||!root.contains(cell))return;
    if(event.target.closest('button'))return;
    selectedDate=cell.dataset.calCell;selectedId=null;render();
  }
  function cellKeydown(event){
    if(event.target.matches('[data-cal-club]') && (event.key==='Enter'||event.key===' ')){event.preventDefault();event.stopPropagation();window.FMNavigation?.club(event.target.dataset.calClub);return;}
    if(event.target.matches('[data-cal-cell]') && (event.key==='Enter'||event.key===' ')){
      event.preventDefault();selectedDate=event.target.dataset.calCell;selectedId=null;render();
    }
  }
  async function runSimulation(target){
    if(simulating||target<today()||!window.FMProgression?.simulateUntil)return;
    if(!window.FMSimulationOverlay?.confirm)return;
    // Preview counts only fixtures currently visible to the club calendar.
    // Future cup draws can introduce additional matches during the run.
    const knownMatches=snapshot.matches.filter(game=>game.date>=today()&&game.date<=target&&!game.score).length;
    const accepted=await window.FMSimulationOverlay.confirm({target,fromDate:today(),knownMatches});
    if(!accepted || simulating || target<today())return;
    simulating=true;render();
    try{await window.FMProgression.simulateUntil(target);await refresh();}
    finally{simulating=false;render();}
  }
  async function refresh(){
    if(!root)return;
    const serial=++requestId;
    try{
      const res=await fetch('/api/calendar',{cache:'no-store'});
      if(!res.ok)throw Error(`HTTP ${res.status}`);
      const data=await res.json();
      if(serial!==requestId)return;
      if(!data||!Array.isArray(data.matches)||!/^\d{4}-\d{2}-\d{2}$/.test(data.date))throw Error('Invalid calendar response');
      snapshot=data;
      if(month===null)month=monthOf(data.date);
      if(selectedDate===null)selectedDate=data.date;
      render();
    }catch(error){
      if(serial!==requestId)return;
      console.warn('Calendar API unavailable',error);
      root.innerHTML='<section class="cal-error panel"><h2>Calendar unavailable</h2><p>Open the game with INICIAR_INTERFAZ_WINDOWS.bat to load its Python season. Fixtures cannot be invented while the backend is offline.</p><button type="button" data-cal-retry="true">Retry</button></section>';
    }
  }
  function mount(element){
    if(root!==element){if(root){root.removeEventListener('click',click);root.removeEventListener('click',cellClick);root.removeEventListener('keydown',cellKeydown);}root=element;root.addEventListener('click',click);root.addEventListener('click',cellClick);root.addEventListener('keydown',cellKeydown);root.addEventListener('click',e=>{if(e.target.closest('[data-cal-retry]'))refresh();});}
    refresh();
  }
  return {mount,refresh};
})();
