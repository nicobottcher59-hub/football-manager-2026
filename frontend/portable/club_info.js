/* TS-UI-10 — Club Info: a live universal club profile backed by career ledgers.
 * No permanent title counts or competition membership are cached in the UI.
 * Optional pre-career records are imported by stable club ID, separately. */
(() => {
  'use strict';
  const h = value => String(value ?? '').replace(/[&<>"']/g, ch=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
  const number = n => Number.isFinite(Number(n)) && n != null ? Number(n).toLocaleString('en-GB') : '—';
  const price = n => n==null?'—':'£'+number(n);
  const empty = text => `<div class="ci-empty">${h(text)}</div>`;
  const safeUrl = source => String(window.FMEntityAssets?.url?.(source) || (source?.startsWith?.('assets/') ? '/portable/'+source : '') || '');
  const flags = country => window.FMNationFlags?.render?.(country,'ci-nationality')||'◇';
  const compBadge = cid => window.FMCompetitionBranding?.badge?.(cid,'ci-competition-logo')||'<span class="ci-competition-placeholder">✦</span>';
  const badgeClub = (id,name,klass='') => {
    const info=window.FMClubIdentity?.resolve?.(id,name)||{};
    if(info.crest) return `<img src="${h(safeUrl(info.crest))}" class="ci-club-crest ${h(klass)}" data-fm-asset="optional" alt="${h(info.display_name||name||'Club')} crest" loading="lazy">`;
    return `<span class="ci-club-crest ci-club-fallback ${h(klass)}" aria-label="${h(info.display_name||name||'Club')} crest">${h(String(info.short_name||info.display_name||name||'FC').split(/\s+/).map(v=>v[0]).join('').slice(0,3).toUpperCase())}</span>`;
  };
  const card=(title,body,cls='')=>`<section class="ci-card ${cls}"><h3>${h(title)}</h3>${body}</section>`;
  const stat=(label,value)=>`<div class="ci-stat"><small>${h(label)}</small><strong>${h(value??'—')}</strong></div>`;
  const routeCompetition=(id,label)=>`<button class="ci-inline-link" data-ci-competition="${h(id)}" type="button">${h(label||id)}</button>`;
  let host=null, clubId='', response=null, historical={}, tab='history', page=0, serial=0;
  const tabs=[['history','Historical honours'],['seasons','Season archive'],['records','Club records'],['career','Career history']];
  const PAGE=9;
  let legacyPromise=null;
  const imports=new Map();
  const legacyArchive=()=>{
    if(!legacyPromise)legacyPromise=fetch('/portable/data/club-historical-records.json',{cache:'no-store'})
      .then(r=>r.ok?r.json():null)
      .then(d=>d?.schema_version===1&&d.clubs&&!Array.isArray(d.clubs)?d.clubs:{})
      .catch(()=>({}));
    return legacyPromise;
  };
  function importedFor(id){
    if(!imports.has(id))imports.set(id,(async()=>{
      // One optional document per immutable club ID: no whole-world historical
      // payload or repeated download as the football database expands.
      if(/^[a-zA-Z0-9_-]{1,128}$/.test(id)){
        try{
          const result=await fetch(`/portable/data/club-histories/${encodeURIComponent(id)}.json`,{cache:'no-store'});
          if(result.ok){
            const data=await result.json();
            if(data?.schema_version===1&&data.club_id===id&&data.record&&typeof data.record==='object')
              return data.record;
          }
        }catch(_) { /* missing optional archive is not a runtime failure */ }
      }
      const legacy=await legacyArchive();
      return legacy[id]||{};
    })());
    return imports.get(id);
  }
  function hero(d,identity,seed){
    const inst=d.institution||{},live=d.live||{};
    const bg=identity.hero_image ? `style="--ci-art:url('${h(safeUrl(identity.hero_image))}')"` : '';
    const country=inst.country||seed.country||null,leagueName=live.league?.name||inst.league||'Competition not registered';
    const tags=[inst.founded??identity.founded?`Founded ${inst.founded??identity.founded}`:null,
      inst.registered?'Professional club':null,inst.playing_style?inst.playing_style.replace(/[-_]/g,' '):null]
      .filter(Boolean).map(v=>`<span class="ci-tag">${h(v)}</span>`).join('');
    return `<section class="ci-hero" ${bg} data-fm-club-theme="${h(d.id)}" data-fm-club-name="${h(d.name)}">
      <div class="ci-hero-body">${badgeClub(d.id,d.name,'ci-hero-crest')}
      <div class="ci-hero-title"><span class="ci-eyebrow">CLUB PROFILE · ${h(live.season||'CAREER')}</span>
      <h2>${h(identity.display_name||d.name)}</h2>
      <p>${country?flags(country)+' '+h(country):''}<span class="ci-hero-league">${h(leagueName)}</span></p>
      <div class="ci-hero-tags">${tags||'<span class="ci-tag">Club identity</span>'}</div></div></div>
      <div class="ci-hero-side"><span>CAREER PROFILE</span><strong>${h(live.season||'—')}</strong><span>${h(live.date||'')}</span>${d.has_active_squad?'<button type="button" class="ci-secondary-button" data-ci-squad>View squad →</button>':''}</div>
    </section>`;
  }
  function overview(d,seed){
    const inst=d.institution||{},finance=inst.finance||{},live=d.live||{};
    const year=inst.founded??window.FMClubIdentity?.resolve?.(d.id,d.name)?.founded??seed.founded??null;
    const body=seed.biography?`<p class="ci-overview-copy">${h(seed.biography)}</p>`:
      '<p class="ci-overview-copy">Club identity and career results are linked to the current world. Detailed historical biography will appear when verified records are imported.</p>';
    const fields=[['Founded',year??'Not recorded'],['Country',inst.country||seed.country||'Not recorded'],
      ['Current league',live.league?.name||'Not registered'],
      ['Transfer budget',finance.transfer_budget_gbp==null?'—':price(finance.transfer_budget_gbp)]];
    return card('Club Overview',body+`<div class="ci-overview-facts">${fields.map(x=>stat(...x)).join('')}</div>
      <div class="ci-overview-footer"><span>Club strength</span><strong>${inst.team_strength==null?'—':number(inst.team_strength)}</strong><span>Current season</span><strong>${h(live.season||'—')}</strong></div>`,'ci-overview');
  }
  function currentSeason(d){
    const live=d.live||{},league=live.league,fixture=live.next_fixture;
    const stats=league?[['Played',league.played],['Won',league.won],['Drawn',league.drawn],['Lost',league.lost],['For',league.gf],['Against',league.ga],['Points',league.points]]:[];
    const form=(live.form||[]).map(x=>`<span class="ci-form ci-form-${h(x.toLowerCase())}" title="${h(x==='W'?'Win':x==='D'?'Draw':'Loss')}">${h(x)}</span>`).join('');
    return card('Current Season',`<div class="ci-season-league">
        <div>${league?compBadge(league.id):''}<div><strong>${h(league?.name||'No league registered')}</strong><span>${h(live.season||'')}</span></div></div>
        <div class="ci-position"><strong>${league?.position==null?'—':h(league.position)+ordinal(league.position)}</strong><span>Position</span></div>
      </div>${stats.length?`<div class="ci-season-stats">${stats.map(x=>stat(x[0],x[1])).join('')}</div>`:empty('No league table currently available.')}
      <div class="ci-fixture-bar"><div><small>Recent form</small><div class="ci-form-row">${form||'<span class="ci-muted">Awaiting results</span>'}</div></div>
        <div><small>Next fixture</small><div class="ci-next-fixture">${fixture?`${badgeClub(fixture.opponent_id,fixture.opponent)}<div><strong>${h(fixture.opponent)}</strong><span>${h(fixture.date)} · ${h(fixture.home?'Home':'Away')} · ${h(fixture.competition)}</span></div>`:'<span class="ci-muted">No upcoming fixture</span>'}</div></div></div>`,'ci-current');
  }
  const ordinal=n => {const v=Number(n);return v%100>=11&&v%100<=13?'th':({1:'st',2:'nd',3:'rd'}[v%10]||'th');};
  function competitions(d){
    const entries=d.live?.competitions||[];
    return card('Competitions',entries.map(c=>`<button type="button" class="ci-comp-row" data-ci-competition="${h(c.id)}">${compBadge(c.id)}<span><strong>${h(c.name)}</strong><small>${h(c.type==='league'?'League':c.type==='continental'?'Continental':'Cup')}</small></span><em>${c.position!=null?h(c.position)+ordinal(c.position):h(c.status)}</em></button>`).join('')||empty('No active competition registrations.'),'ci-competitions');
  }
  function honours(d,seed){
    // The module renders country-specific trophies from confirmed results.
    // No independent title totals are stored inside Club Info.
    const content=window.FMClubHonours?.render?.(d,seed)||empty('Competition honours are not available yet.');
    return card('Honours & Achievements',content,'ci-honours');
  }
  function timelineEvent(s){
    const details=[];
    if(s.titles?.length)details.push('🏆 '+s.titles.map(t=>t.name).join(', '));
    if(s.promoted?.length)details.push('↑ Promoted');
    if(s.relegated?.length)details.push('↓ Relegated');
    if(s.complete&&s.position!=null)details.push(`Finished ${s.position}${ordinal(s.position)} in ${s.league}`);
    if(!s.complete)details.push('Current season · '+(s.league||'No league'));
    return details;
  }
  function history(d,seed){
    const events=(d.seasons||[]).flatMap(s=>timelineEvent(s).map(t=>({season:s.season,text:t})));
    const historics=Array.isArray(seed.timeline)?seed.timeline:[];
    const headline=`<div class="ci-history-tabs" role="tablist" aria-label="Club history">${tabs.map(([id,label])=>`<button type="button" role="tab" class="${tab===id?'is-selected':''}" aria-selected="${tab===id}" data-ci-tab="${id}">${label}</button>`).join('')}</div>`;
    let archive=[];
    if(tab==='history')archive=[...historics.map(t=>({date:t.date||t.season||'Historical',text:t.text||''})),
      ...(Array.isArray(seed.honours)?seed.honours:[]).flatMap(t=>(Array.isArray(t.seasons)&&t.seasons.length?t.seasons:[null]).map(year=>({date:year||'Pre-career',text:year?'Won '+(t.competition||'Competition'):`${t.total??'Unspecified'} title(s) · ${t.competition||'Competition'}`}))),
      ...(d.trophies||[]).map(t=>({date:t.season,text:'Won '+t.name}))];
    if(tab==='seasons')archive=(d.seasons||[]).map(s=>({date:s.season,text:(s.complete?'Completed':'Ongoing')+' · '+(s.league||'Not registered')+
      (s.position!=null?' · '+s.position+ordinal(s.position):'')+
      (s.promoted?.length?' · Promoted':'')+(s.relegated?.length?' · Relegated':'')}));
    if(tab==='career')archive=events.map(e=>({date:e.season,text:e.text}));
    if(tab==='records')archive=(Array.isArray(seed.records)?seed.records:[]).map(r=>({date:r.season||'Historical',text:`${r.label||'Record'}: ${r.value??'—'}`}))
      .concat(Object.entries(d.records||{}).flatMap(([key,values])=>(values||[]).slice(0,3).map(p=>({date:key,text:`${p.player} · ${p.value}`}))));
    const shown=archive.slice(page*PAGE,(page+1)*PAGE);
    const rows=shown.map(e=>`<div class="ci-timeline-item"><span class="ci-timeline-dot"></span><time>${h(e.date)}</time><span>${h(e.text)}</span></div>`).join('');
    const paging=archive.length>PAGE?`<div class="ci-timeline-pager"><span>${page*PAGE+1}–${Math.min(archive.length,(page+1)*PAGE)} of ${archive.length}</span><button type="button" data-ci-page="-1" ${page===0?'disabled':''}>←</button><button type="button" data-ci-page="1" ${(page+1)*PAGE>=archive.length?'disabled':''}>→</button></div>`:'';
    return card('Club History',headline+`<div class="ci-timeline">${rows||empty(tab==='history'?'No verified historical titles have been imported yet.':tab==='records'?'No recorded club records available.':'Career milestones appear as seasons are completed.')}</div>${paging}
      <div class="ci-history-note">Imported historical records and career events are maintained separately by club ID.</div>`,'ci-history');
  }
  function records(d,seed){
    const dataset=Object.entries(d.records||{}).flatMap(([key,rows])=>(rows||[]).slice(0,1).map(r=>({label:({goals:'Career goals',appearances:'Career appearances',assists:'Career assists'}[key]||key),value:r.value,player:r.player})));
    const proven=(Array.isArray(seed.records)?seed.records:[]).slice(0,3).map(r=>({label:r.label,value:r.value,player:r.holder||r.player||'Historical record'}));
    const rows=[...proven,...dataset].slice(0,5);
    return card('Club Records',rows.map((r,i)=>`<div class="ci-record-row"><span class="ci-record-symbol">${['♙','⚽','★','↗','◆'][i]}</span><div><small>${h(r.label)}</small><span>${h(r.player)}</span></div><strong>${h(r.value??'—')}</strong></div>`).join('')||empty('Records accumulate as your career progresses, or when verified archives are imported.')+
       `<button class="ci-secondary-button" type="button" data-ci-tab="records">View all records →</button>`,'ci-records');
  }
  function philosophyIcon(index){
    const paths=[
      '<circle cx="6" cy="7" r="2"/><circle cx="18" cy="7" r="2"/><circle cx="12" cy="18" r="2"/><path d="M7.5 8.5 11 16M16.5 8.5 13 16M8.5 7H15"/>',
      '<path d="M12 2 4 5v6c0 5.2 3.3 8.6 8 11 4.7-2.4 8-5.8 8-11V5z"/><path d="M9 15V8l3 2 3-2v7"/>',
      '<path d="M3 21h18M5 17h3v4H5zM11 12h3v9h-3zM17 5h3v16h-3z"/>',
      '<rect x="4" y="3" width="16" height="18" rx="2"/><path d="M8 7h8M8 11h8M8 15h5"/><path d="M14 20l2-2 2 2"/>'
    ];
    return `<span class="ci-philosophy-icon ci-philosophy-icon-${index%4}" aria-hidden="true"><svg viewBox="0 0 24 24" width="34" height="34" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">${paths[index%4]}</svg></span>`;
  }
  function philosophy(d,seed){
    const inst=d.institution||{},data=(Array.isArray(seed.philosophy)?seed.philosophy:[]).filter(x=>x?.title);
    const fields=data.length?data:[
      {title:'Playing identity',detail:inst.playing_style?inst.playing_style.replace(/[-_]/g,' '):'Not recorded'},
      {title:'Current division',detail:d.live?.league?.name||'Not registered'},
      {title:'Career history',detail:`${(d.seasons||[]).filter(s=>s.complete).length} completed seasons recorded`},
      {title:'Historical archive',detail:seed.biography?'Imported':'Awaiting verified records'}];
    return card('Identity & Philosophy',`<div class="ci-philosophy-grid">${fields.slice(0,6).map((x,i)=>`<div>${philosophyIcon(i)}<div><strong>${h(x.title)}</strong><small>${h(x.detail||'—')}</small></div></div>`).join('')}</div>`,'ci-philosophy');
  }
  function render(){
    if(!host||!response)return;
    const d=response,seed=historical[clubId]||{},identity=window.FMClubIdentity?.resolve?.(d.id,d.name)||{};
    const previousHonoursScroll=host.querySelector('[data-ci-trophy-scroll]')?.scrollLeft||0;
    host.innerHTML=`<div class="ci-root" data-fm-club-theme="${h(d.id)}" data-fm-club-name="${h(d.name)}">${hero(d,identity,seed)}
      <div class="ci-major-grid">${overview(d,seed)}${currentSeason(d)}${competitions(d)}</div>
      <div class="ci-minor-grid">${honours(d,seed)}${history(d,seed)}${records(d,seed)}</div>${philosophy(d,seed)}
      <p class="ci-provenance">Career results are live and verified from the current save. Historical facts appear only when a club-ID archive is supplied; no missing honours or records are invented.</p></div>`;
    window.FMClubIdentity?.paintWithin?.(host);
    const trophyScroll=host.querySelector('[data-ci-trophy-scroll]');
    if(trophyScroll)trophyScroll.scrollLeft=previousHonoursScroll;
  }
  async function mount(element,id){
    if(host!==element){host=element;host.addEventListener('click',click);host.addEventListener('wheel',trophyWheel,{passive:false});}
    const nextId=String(id||'');const changed=nextId!==clubId;
    clubId=nextId;if(changed){tab='career';page=0;}
    const sequence=++serial;
    if(!clubId){host.innerHTML=empty('No club selected.');return;}
    host.innerHTML='<div class="ci-loading">Loading club profile…</div>';
    try{
      const [res,archive]=await Promise.all([fetch(`/api/history/club/${encodeURIComponent(clubId)}`,{cache:'no-store'}),importedFor(clubId),window.FMClubHonours?.load?.()||Promise.resolve()]);
      const data=await res.json();
      if(!res.ok||data.type!=='club'||data.id!==clubId||data.source!=='verified-career-ledgers')throw Error(data.error||'Club history unavailable');
      if(sequence!==serial||!host)return;
      response=data;historical={[clubId]:archive};render();
    }catch(error){if(sequence===serial&&host)host.innerHTML=`<section class="ci-card" role="alert"><h3>Club information unavailable</h3><p>${h(error.message)}</p><button type="button" data-ci-retry>Retry</button></section>`;}
  }
  function click(event){
    const button=event.target.closest('button');if(!button||!host?.contains(button))return;
    if(button.dataset.ciTrophyDirection){const scroller=host.querySelector('[data-ci-trophy-scroll]');if(scroller)scroller.scrollBy({left:Number(button.dataset.ciTrophyDirection)*300,behavior:'smooth'});}
    else if(button.dataset.ciCompetition)window.FMNavigation?.competition?.(button.dataset.ciCompetition);
    else if(button.hasAttribute('data-ci-squad'))window.FMNavigation?.clubSquad?.(clubId);
    else if(button.dataset.ciTab){tab=button.dataset.ciTab;page=0;render();
      if(button.classList.contains('ci-secondary-button'))host.querySelector('.ci-history')?.scrollIntoView?.({block:'nearest'});}
    else if(button.dataset.ciPage){page=Math.max(0,page+Number(button.dataset.ciPage));render();}
    else if(button.hasAttribute('data-ci-retry'))mount(host,clubId);
  }
  function trophyWheel(event){
    const scroller=event.target.closest?.('[data-ci-trophy-scroll]');
    if(!scroller||event.ctrlKey||event.metaKey||event.shiftKey||scroller.scrollWidth<=scroller.clientWidth)return;
    if(Math.abs(event.deltaY)<=Math.abs(event.deltaX))return;
    const next=scroller.scrollLeft+event.deltaY;
    if(next>=0&&next<=scroller.scrollWidth-scroller.clientWidth){event.preventDefault();scroller.scrollLeft=next;}
  }
  window.FMClubInfo=Object.freeze({mount});
})();
