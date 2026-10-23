/* TS-28.2: career history browser. All information comes from verified Python
 * ledgers; links share one router for players, clubs and competitions. */
window.FMHistory = (() => {
  'use strict';
  const h = value => String(value ?? '').replace(/[&<>"']/g, c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const money = value => typeof value==='number' ? '£'+value.toLocaleString('en-GB') : '—';
  const column = value => value===null || value===undefined ? '—' : h(value);
  const button = (kind,id,label) => `<button type="button" class="ch-link" data-career-type="${h(kind)}" data-career-id="${h(id)}">${h(label)}</button>`;
  const stats = item => {
    const s=item.statistics||{};
    return `<tr><td>${h(item.season)}</td><td>${item.clubs.length?item.clubs.map(c=>button('club',c.id,c.name)).join(', '):'<span class="ch-muted">Not registered in historical match records</span>'}</td><td>${column(s.appearances)}</td><td>${column(s.minutes)}</td><td>${column(s.goals)}</td><td>${column(s.assists)}</td><td>${column(s.average_match_rating)}</td><td>${item.coverage.complete_season?'Complete':`Partial${item.coverage.from?' from '+h(item.coverage.from):''}`}</td></tr>`;
  };
  const table = (head, rows, empty='No verified records yet.') => `<div class="ch-scroll"><table class="ch-table"><thead><tr>${head.map(x=>`<th>${h(x)}</th>`).join('')}</tr></thead><tbody>${rows||`<tr><td colspan="${head.length}" class="ch-muted">${h(empty)}</td></tr>`}</tbody></table></div>`;
  const section = (title,body,sub='') => `<section class="ch-card"><div class="ch-card-head"><h3>${h(title)}</h3>${sub?`<small>${h(sub)}</small>`:''}</div>${body}</section>`;
  let host=null, entity='', identifier='', selectedSeason='', offset=0, request=0, chartMetric='overall', cached=null;
  const short=(n)=>typeof n==='number'?n.toFixed(1):'—';
  const valOrUnknown=(value)=>value===null||value===undefined||value===''?'<span class="ch-muted">Not recorded</span>':h(value);
  const fact=(label,value)=>`<div class="ch-fact"><small>${h(label)}</small><strong>${valOrUnknown(value)}</strong></div>`;
  const awardPanel=(items)=>section('Individual awards',table(['Season','Recognition','Competition','Player','Club'],
    (items||[]).map(x=>`<tr><td>${h(x.season)}</td><td>${h(x.label)}</td><td>${x.competition_id==='world'?'Simulated World':button('competition',x.competition_id,x.competition)}</td><td>${button('player',x.player_id,x.player)}</td><td>${x.club_id?button('club',x.club_id,x.club):'—'}</td></tr>`).join(''), 'No verified season-end awards yet.'),
    'Awards are certified after each completed season.');
  function recordsPanel(records){
    const names={goals:'Goals',assists:'Assists',appearances:'Appearances'};
    const rows=Object.keys(names).flatMap(key=>(records?.[key]||[]).map((p,i)=>
      `<tr><td>${h(names[key])}</td><td>${i+1}</td><td>${button('player',p.player_id,p.player)}</td><td><strong>${p.value}</strong></td></tr>`)).join('');
    return section('Historical records',table(['Record','Rank','Player','Total'],rows),
      'Only verified full single-club seasons count toward club totals.');
  }
  function progressionPanel(d){
    const points=(d.progression||[]);
    const metrics=['overall',...Object.keys(points[0]?.indicators||{})];
    if(!metrics.includes(chartMetric))chartMetric='overall';
    const labels=points.map(p=>p.date);
    const get=p=>chartMetric==='overall'?p.overall:p.indicators?.[chartMetric];
    const valid=points.map((p,i)=>({...p,i,v:Number(get(p))})).filter(p=>Number.isFinite(p.v));
    const coords=valid.map(p=>`${(44+p.i*(650/Math.max(1,points.length-1))).toFixed(2)},${(190-p.v*1.65).toFixed(2)}`).join(' ');
    const circles=valid.map(p=>`<circle cx="${(44+p.i*(650/Math.max(1,points.length-1))).toFixed(2)}" cy="${(190-p.v*1.65).toFixed(2)}" r="4.5" fill="#64d5ed"><title>${h(p.date)} · ${h(chartMetric==='overall'?'OVR':chartMetric)}: ${p.v.toFixed(2)}</title></circle>`).join('');
    const options=metrics.map(m=>`<option value="${h(m)}" ${m===chartMetric?'selected':''}>${h(m==='overall'?'Overall rating (OVR)':m)}</option>`).join('');
    const graph=`<div class="ch-actions"><label>Measure <select data-history-metric>${options}</select></label><small class="ch-muted">${valid.length} actual observation${valid.length===1?'':'s'}</small></div>`+
     `<div class="ch-graph-wrap"><svg class="ch-graph" viewBox="0 0 740 240" role="img" aria-label="Historical ${h(chartMetric)} chart with ${valid.length} actual observations">
       <line x1="44" y1="25" x2="44" y2="190" stroke="#4e7086"/><line x1="44" y1="190" x2="702" y2="190" stroke="#4e7086"/>
       <line x1="44" y1="107.5" x2="702" y2="107.5" stroke="#264960" stroke-dasharray="4 5"/>
       <text x="10" y="30" fill="#9cbace" font-size="12">100</text><text x="18" y="111" fill="#9cbace" font-size="12">50</text><text x="25" y="193" fill="#9cbace" font-size="12">0</text>
       ${valid.length>1?`<polyline fill="none" stroke="#64d5ed" stroke-width="3" stroke-linejoin="round" points="${coords}"/>`:''}${circles}
       ${labels.length?`<text x="44" y="218" font-size="12" fill="#abcde0">${h(labels[0])}</text><text x="700" y="218" text-anchor="end" font-size="12" fill="#abcde0">${h(labels.at(-1))}</text>`:''}
       </svg></div>`;
    const log=table(['Season','Date','OVR','Technical avg','Mental avg','Physical avg'],points.map(p=>
      `<tr><td>${h(p.season)}</td><td>${h(p.date)}${p.is_current?' (live)':''}</td><td>${short(p.overall)}</td><td>${short(p.indicators?.['Technical average'])}</td><td>${short(p.indicators?.['Mental average'])}</td><td>${short(p.indicators?.['Physical average'])}</td></tr>`).join(''),'No recorded rating observations yet.');
    return `<div data-history-progression>${section('Player development',graph+log,'Rating and selected attribute measures; tracking starts with TS-28.3.')}</div>`;
  }
  function institutionPanel(d){
    const o=d.institution||{};
    const brand=window.FMClubIdentity?.resolve?.(d.id,d.name)||{};
    const location=brand.location||null;
    const founded=o.founded??brand.founded??null;
    const stadium=o.stadium||brand.stadium||null;
    const city=o.city||location||null;
    if(!o.registered)return section('Club identity',`<p class="ch-muted">${h(o.note||'No professional club record is available.')}</p>`);
    const info=`<div class="ch-facts">${fact('Country',o.country)}${fact('Location',city)}${fact('Stadium',stadium)}${fact('Stadium capacity',o.stadium_capacity)}${fact('Founded',founded)}
      ${fact('Current tier',o.current_tier)}${fact('League',o.league)}${fact('Playing style',o.playing_style)}${fact('Simulator team strength',o.team_strength)}</div>`;
    const finances=o.finance?`<div class="ch-facts">${fact('Available cash',money(o.finance.cash_gbp))}${fact('Transfer budget',money(o.finance.transfer_budget_gbp))}${fact('Weekly wage budget',money(o.finance.wage_budget_weekly_gbp))}</div>`:'<p class="ch-muted">Finances unavailable for this club.</p>';
    const staffing=table(['Department','Current staff','Provisional capacity','Average staff quality'],(o.facilities?.staffing_slots||[]).map(x=>
      `<tr><td>${h(({coach:'Coaches',fitness:'Fitness',medic:'Medical',scout:'Scouts'})[x.role]||x.role)}</td><td>${x.count}</td><td>${x.capacity}</td><td>${x.average_quality??'—'}</td></tr>`).join(''));
    const env=o.training_environment?`<p class="ch-muted">Training baseline: ${short(o.training_environment.quality)} · Coaching baseline: ${short(o.training_environment.coaching)} (${h(o.training_environment.source)}).</p>`:'';
    const leading=table(['Player','Position','GRL'],(o.top_players||[]).map(x=>
      `<tr><td>${button('player',x.id,x.name)}</td><td>${h(x.position)}</td><td>${short(x.overall)}</td></tr>`).join(''));
    return section('Club identity',info,h('Recorded club information'))+section('Finances · snapshot',finances)
      +section('Facilities and staff',env+staffing+`<p class="ch-note">${h(o.note||'')}</p>`,
       'Staff capacity is provisional; facility upgrades will be managed in TS-29.')
      +section('Current leading players',leading);
  }
  function playerPage(d){
    const timeline=table(['Season','Clubs (verified match appearances)','Apps','Minutes','Goals','Assists','Avg','Coverage'],d.seasons.map(stats).join(''),'No season performance registered.');
    const transfers=table(['Transfer date','From','To','Guaranteed fee'],d.transfers.map(t=>`<tr><td title="${h(t.date_note)}">${column(t.date)} *</td><td>${button('club',t.from_id,t.from)}</td><td>${button('club',t.to_id,t.to)}</td><td>${money(t.fee_gbp)}</td></tr>`).join(''));
    const loans=table(['Start','Club','Loaned to','Ends','Status'],d.loans.map(t=>`<tr><td>${h(t.date)}</td><td>${button('club',t.from_id,t.from)}</td><td>${button('club',t.to_id,t.to)}</td><td>${h(t.ends_on)}</td><td>${h(t.status)}</td></tr>`).join(''));
    const titles=table(['Season','Competition','Club'],d.honours.map(t=>`<tr><td>${h(t.season)}</td><td>${button('competition',t.competition_id,t.competition)}</td><td>${button('club',t.club_id,t.club)}</td></tr>`).join(''));
    const current=d.current_club_id?button('club',d.current_club_id,d.current_club):'Free agent';
    return `<div class="ch-subheading">${h(d.position)} · ${h(d.nationality)} · Born ${h(d.birth_date)} · ${d.status==='retired'?`Retired ${h(d.retired_on||'')}`:d.status==='free_agent'?'Free agent':`Current club: ${current}`}</div>
      ${progressionPanel(d)}
      ${awardPanel(d.awards)}
      ${section('Season-by-season career',timeline)}
      ${section('Confirmed transfers',transfers,'* Registration date for new transfers; legacy entries may retain the agreement date')}
      ${section('Loans',loans)}
      ${section('Club honours at season end',titles,'No retroactive awards; not individual player prizes')}`;
  }
  const matchRows = rows => rows.map(m=>`<tr><td>${h(m.date)}</td><td>${button('competition',m.competition_id,m.competition)}</td><td>${button('club',m.home_id,m.home)}</td><td><strong>${m.home_goals} – ${m.away_goals}</strong></td><td>${button('club',m.away_id,m.away)}</td></tr>`).join('');
  function matchPanel(d){
    const page=d.fixtures;
    const pager=`<div class="ch-pager"><span>${page.total} played matches · ${page.total?`${page.offset+1}–${Math.min(page.total,page.offset+page.matches.length)}`:'No results'}</span><div><button type="button" data-history-step="-1" ${page.offset===0?'disabled':''}>← Previous</button><button type="button" data-history-step="1" ${page.next_offset===null?'disabled':''}>Next →</button></div></div>`;
    return section('Recorded matches',pager + table(['Date','Competition','Home','Score','Away'],matchRows(page.matches)));
  }
  function clubPage(d){
    const choices=d.seasons.map(x=>`<option value="${h(x.season)}" ${x.season===d.season?'selected':''}>${h(x.season)}</option>`).join('');
    const seasons=table(['Season','League','Finish','Promotion / relegation','Titles'],d.seasons.map(s=>`<tr><td>${h(s.season)} ${s.complete?'':'(ongoing)'}</td><td>${s.league_id?button('competition',s.league_id,s.league):'—'}</td><td>${s.position??'—'}</td><td>${s.promoted.length?'Promoted':s.relegated.length?'Relegated':'—'}</td><td>${s.titles.map(t=>button('competition',t.id,t.name)).join(', ')||'—'}</td></tr>`).join(''));
    const cups=table(['Season','Competition'],d.trophies.map(t=>`<tr><td>${h(t.season)}</td><td>${button('competition',t.id,t.name)}</td></tr>`).join(''));
    const moves=table(['Transfer date','Player','From','To','Fee'],d.transfers.map(t=>`<tr><td>${column(t.date)}</td><td>${button('player',t.player_id,t.player_name)}</td><td>${button('club',t.from_id,t.from)}</td><td>${button('club',t.to_id,t.to)}</td><td>${money(t.fee_gbp)}</td></tr>`).join(''));
    const veterans=table(['Retired player','Retired on'],d.retired_players.map(p=>`<tr><td>${button('player',p.id,p.name)}</td><td>${h(p.retired_on)}</td></tr>`).join(''));
    return `<div class="ch-actions">${d.has_active_squad?`<button type="button" class="ch-primary" data-history-squad="${h(d.id)}">View current squad and attributes →</button>`:''}<label>Season <select data-history-season>${choices}</select></label></div>
    ${institutionPanel(d)}${recordsPanel(d.records)}${awardPanel(d.awards)}${section('Season record',seasons)}${section('Trophy cabinet',cups)}${matchPanel(d)}${section('Confirmed transfer history',moves)}${section('Retired players at this club',veterans)}`;
  }
  function competitionPage(d){
    const choices=d.available_seasons.map(s=>`<option value="${h(s)}" ${s===d.season?'selected':''}>${h(s)}</option>`).join('');
    const winners=table(['Season','Champion'],d.champions.map(w=>`<tr><td>${h(w.season)}</td><td>${button('club',w.club_id,w.club)}</td></tr>`).join(''));
    const ranking=table(['Position','Club','Points','Played','Goal difference'],d.table.map(r=>`<tr><td>${r.position}</td><td>${button('club',r.club_id,r.club)}</td><td>${column(r.points)}</td><td>${column(r.played)}</td><td>${column(r.gd)}</td></tr>`).join(''),'This cup has no league standings.');
    return `<div class="ch-actions"><label>Recorded season <select data-history-season>${choices}</select></label><button type="button" class="ch-primary" data-history-competition="${h(d.id)}">Open current competition →</button></div>
      <p class="ch-subheading">${d.season_complete?'Completed season':'Ongoing season'} · ${d.champion_id?'Champion: '+button('club',d.champion_id,d.champion):'Champion not yet confirmed'}</p>
      ${awardPanel(d.awards)}${recordsPanel(d.records)}${section('Past champions',winners)}${section('Final league standings / current standings',ranking)}${matchPanel(d)}`;
  }
  async function fetchHistory(){
    if(!host||!entity||!identifier)return;
    const token=++request;
    host.innerHTML='<div class="ch-loading">Loading recorded career history…</div>';
    try{
      const q=new URLSearchParams();if(selectedSeason)q.set('season',selectedSeason);if(offset)q.set('offset',String(offset));
      const res=await fetch(`/api/history/${encodeURIComponent(entity)}/${encodeURIComponent(identifier)}?${q}`,{cache:'no-store'});
      const data=await res.json();if(!res.ok)throw Error(data.error||'Career history unavailable');
      if(token!==request||!host)return;
      if(data.source!=='verified-career-ledgers'||data.type!==entity||data.id!==identifier)throw Error('Invalid career archive response');
      selectedSeason=data.season||'';cached=data;
      const body=entity==='player'?playerPage(data):entity==='club'?clubPage(data):competitionPage(data);
      const club=entity==='club' ? window.FMClubIdentity?.resolve?.(data.id,data.name) : null;
      const art=club?.crest ? `<img class="ch-hero-club-crest" src="${h(window.FMEntityAssets?.url?.(club.crest)||club.crest)}" data-fm-asset="optional" alt="" loading="lazy">` : '';
      const shown=club?.display_name||data.name;
      const subtitle='';
      host.innerHTML=`<div class="ch-root"><div class="ch-hero ch-hero-with-crest">${art}<div><span class="ch-eyebrow">${h(entity.toUpperCase())} · VERIFIED CAREER ARCHIVE</span><h2>${h(shown)}</h2>${subtitle}</div><button type="button" class="ch-back" data-history-back>← Back</button></div>${body}<p class="ch-note">${h(data.note)}</p></div>`;
      window.FMClubIdentity?.paintWithin?.(host);
    }catch(err){if(token===request&&host)host.innerHTML=`<section class="ch-card" role="alert"><h3>Career history unavailable</h3><p>${h(err.message)}</p><button type="button" data-history-retry>Retry</button></section>`;}
  }
  function mount(element,type,id){
    if(host!==element){host=element;host.addEventListener('click',click);host.addEventListener('change',change);}
    if(type!==entity||id!==identifier){entity=type;identifier=id;selectedSeason='';offset=0;chartMetric='overall';cached=null;}
    fetchHistory();
  }
  function click(event){
    const b=event.target.closest('button');if(!b||!host.contains(b))return;
    if(b.hasAttribute('data-history-back'))window.FMNavigation?.back();
    if(b.hasAttribute('data-history-retry'))fetchHistory();
    if(b.hasAttribute('data-history-squad'))window.FMNavigation?.club(b.dataset.historySquad);
    if(b.hasAttribute('data-history-competition'))window.FMNavigation?.competition(b.dataset.historyCompetition);
    if(b.hasAttribute('data-history-step')){offset=Math.max(0,offset+80*Number(b.dataset.historyStep));fetchHistory();}
  }
  function change(event){
    if(event.target.matches('[data-history-season]')){selectedSeason=event.target.value;offset=0;fetchHistory();}
    if(event.target.matches('[data-history-metric]')&&entity==='player'&&cached){chartMetric=event.target.value;
      const chart=host.querySelector('[data-history-progression]');
      if(chart)chart.outerHTML=progressionPanel(cached);
    }
  }
  return {mount};
})();
