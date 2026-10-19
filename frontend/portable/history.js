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
  let host=null, entity='', identifier='', selectedSeason='', offset=0, request=0;
  function playerPage(d){
    const timeline=table(['Season','Clubs (verified match appearances)','Apps','Minutes','Goals','Assists','Avg','Coverage'],d.seasons.map(stats).join(''),'No season performance registered.');
    const transfers=table(['Recorded agreement','From','To','Guaranteed fee'],d.transfers.map(t=>`<tr><td title="${h(t.date_note)}">${column(t.date)} *</td><td>${button('club',t.from_id,t.from)}</td><td>${button('club',t.to_id,t.to)}</td><td>${money(t.fee_gbp)}</td></tr>`).join(''));
    const loans=table(['Start','Club','Loaned to','Ends','Status'],d.loans.map(t=>`<tr><td>${h(t.date)}</td><td>${button('club',t.from_id,t.from)}</td><td>${button('club',t.to_id,t.to)}</td><td>${h(t.ends_on)}</td><td>${h(t.status)}</td></tr>`).join(''));
    const titles=table(['Season','Competition','Club'],d.honours.map(t=>`<tr><td>${h(t.season)}</td><td>${button('competition',t.competition_id,t.competition)}</td><td>${button('club',t.club_id,t.club)}</td></tr>`).join(''));
    const current=d.current_club_id?button('club',d.current_club_id,d.current_club):'Free agent';
    return `<div class="ch-subheading">${h(d.position)} · ${h(d.nationality)} · Born ${h(d.birth_date)} · ${d.status==='retired'?`Retired ${h(d.retired_on||'')}`:d.status==='free_agent'?'Free agent':`Current club: ${current}`}</div>
      ${section('Season-by-season career',timeline)}
      ${section('Confirmed transfers',transfers,'* Agreement date; registration day not recorded')}
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
    const moves=table(['Agreement','Player','From','To','Fee'],d.transfers.map(t=>`<tr><td>${column(t.date)}</td><td>${button('player',t.player_id,t.player_name)}</td><td>${button('club',t.from_id,t.from)}</td><td>${button('club',t.to_id,t.to)}</td><td>${money(t.fee_gbp)}</td></tr>`).join(''));
    const veterans=table(['Retired player','Retired on'],d.retired_players.map(p=>`<tr><td>${button('player',p.id,p.name)}</td><td>${h(p.retired_on)}</td></tr>`).join(''));
    return `<div class="ch-actions">${d.has_active_squad?`<button type="button" class="ch-primary" data-history-squad="${h(d.id)}">View current squad and attributes →</button>`:''}<label>Season <select data-history-season>${choices}</select></label></div>
    ${section('Season record',seasons)}${section('Trophy cabinet',cups)}${matchPanel(d)}${section('Confirmed transfer history',moves)}${section('Retired players at this club',veterans)}`;
  }
  function competitionPage(d){
    const choices=d.available_seasons.map(s=>`<option value="${h(s)}" ${s===d.season?'selected':''}>${h(s)}</option>`).join('');
    const winners=table(['Season','Champion'],d.champions.map(w=>`<tr><td>${h(w.season)}</td><td>${button('club',w.club_id,w.club)}</td></tr>`).join(''));
    const ranking=table(['Position','Club','Points','Played','Goal difference'],d.table.map(r=>`<tr><td>${r.position}</td><td>${button('club',r.club_id,r.club)}</td><td>${column(r.points)}</td><td>${column(r.played)}</td><td>${column(r.gd)}</td></tr>`).join(''),'This cup has no league standings.');
    return `<div class="ch-actions"><label>Recorded season <select data-history-season>${choices}</select></label><button type="button" class="ch-primary" data-history-competition="${h(d.id)}">Open current competition →</button></div>
      <p class="ch-subheading">${d.season_complete?'Completed season':'Ongoing season'} · ${d.champion_id?'Champion: '+button('club',d.champion_id,d.champion):'Champion not yet confirmed'}</p>
      ${section('Past champions',winners)}${section('Final league standings / current standings',ranking)}${matchPanel(d)}`;
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
      selectedSeason=data.season||'';
      const body=entity==='player'?playerPage(data):entity==='club'?clubPage(data):competitionPage(data);
      host.innerHTML=`<div class="ch-root"><div class="ch-hero"><span class="ch-eyebrow">${h(entity.toUpperCase())} · VERIFIED CAREER ARCHIVE</span><h2>${h(data.name)}</h2><button type="button" class="ch-back" data-history-back>← Back</button></div>${body}<p class="ch-note">${h(data.note)}</p></div>`;
    }catch(err){if(token===request&&host)host.innerHTML=`<section class="ch-card" role="alert"><h3>Career history unavailable</h3><p>${h(err.message)}</p><button type="button" data-history-retry>Retry</button></section>`;}
  }
  function mount(element,type,id){
    if(host!==element){host=element;host.addEventListener('click',click);host.addEventListener('change',change);}
    if(type!==entity||id!==identifier){entity=type;identifier=id;selectedSeason='';offset=0;}
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
  function change(event){if(event.target.matches('[data-history-season]')){selectedSeason=event.target.value;offset=0;fetchHistory();}}
  return {mount};
})();
