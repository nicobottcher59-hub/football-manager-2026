/* TS-UI-11 — one living player career by immutable player ID.
 * All totals, seasons, clubs, awards and honours originate in certified Python
 * ledgers or explicitly imported, ID-matched historical archives. */
(() => {
  'use strict';
  const h = x => String(x ?? '').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const arr = x => Array.isArray(x)?x:[];
  const safeName = x => /^[a-z0-9-]+\.png$/.test(String(x||'')) ? x : '';
  const num = x => x===null||x===undefined||!Number.isFinite(Number(x))?'—':Number(x).toLocaleString('en-GB');
  const fixed = x => x===null||x===undefined||!Number.isFinite(Number(x))?'—':Number(x).toFixed(2);
  const gbp = x => x==null?'Undisclosed':'£'+num(x);
  const date = x => typeof x==='string'&&/^\d{4}-\d{2}-\d{2}$/.test(x)?`${x.slice(8,10)}/${x.slice(5,7)}/${x.slice(0,4)}`:String(x||'—');
  const slug = x => String(x||'').normalize('NFKD').replace(/[\u0300-\u036f]/g,'').toLowerCase().trim().replace(/[^a-z0-9]+/g,'-').replace(/^-|-$/g,'');
  let awardCatalogue={categories:[]}, honourCatalogue={countries:{},regions:{},global_categories:[]};
  let readyPromise=null, metric='overall', archiveCache=new Map();
  function load(){
    if(!readyPromise)readyPromise=Promise.all([
      fetch('/portable/data/individual-awards.json').then(r=>r.ok?r.json():null).catch(()=>null),
      fetch('/portable/data/honour-competitions.json').then(r=>r.ok?r.json():null).catch(()=>null)
    ]).then(([awards,honours])=>{
      if(awards?.schema_version===1&&Array.isArray(awards.categories))awardCatalogue=awards;
      if(honours?.schema_version===1&&honours.countries)honourCatalogue=honours;
    });
    return readyPromise;
  }
  function historicalFor(id){
    if(!archiveCache.has(id))archiveCache.set(id,(async()=>{
      if(!/^[a-zA-Z0-9_-]{1,128}$/.test(id))return {};
      try{
        const response=await fetch('/portable/data/player-histories/'+encodeURIComponent(id)+'.json',{cache:'no-store'});
        if(response.ok){const data=await response.json();
          if(data?.schema_version===1&&data.player_id===id&&data.record&&typeof data.record==='object'&&!Array.isArray(data.record))return data.record;
        }
      }catch(_){}
      return {};
    })());
    return archiveCache.get(id);
  }
  const allCategories = () => [
    ...Object.values(honourCatalogue.countries||{}).flatMap(x=>arr(x.categories)),
    ...Object.values(honourCatalogue.regions||{}).flatMap(x=>arr(x.categories)),
    ...arr(honourCatalogue.global_categories)
  ];
  function categoryFor(id,kind='honour'){
    const key=slug(id);
    if(kind==='award'){
      if(/^xi_(gk|def|mid|att)/.test(String(id)))return {id:'team-of-the-season',category:id,label:'Team of the Season',group_by_scope:false};
      return arr(awardCatalogue.categories).find(x=>x.category===id)||null;
    }
    // Prefer exact cup, then the English all-leagues umbrella for Premier;
    // lower-division titles have their own image and remain actual titles.
    const matches=allCategories().filter(x=>arr(x.competition_ids).some(v=>slug(v)===key));
    if(key.includes('championship')||key.includes('league-one')||key.includes('league-two')){
      return matches.find(x=>x.id==='eng-lower')||matches[0]||null;
    }
    return matches.find(x=>x.id!=='eng-lower')||matches[0]||null;
  }
  function crest(id,name,extra=''){
    if(!id)return `<span class="pc-crest pc-crest-empty ${h(extra)}" aria-hidden="true">◇</span>`;
    const club=window.FMClubIdentity?.resolve?.(id,name)||{};
    const label=club.display_name||name||id;
    const short=String(club.short_name||label).split(/\s+/).filter(Boolean).slice(0,2).map(x=>x[0]).join('').toUpperCase()||'?';
    const source=club.crest&&window.FMEntityAssets?.url?.(club.crest);
    const color=window.FMClubIdentity?.fallbackColour?.(id)||'#477d9c';
    return source ? `<img class="pc-crest ${h(extra)}" data-fm-asset="optional" data-fm-crest-fallback="${h(short)}" data-fm-crest-club-id="${h(id)}" alt="${h(label)} crest" src="${h(source)}">`
     : `<span class="pc-crest pc-crest-empty ${h(extra)}" style="--sc-placeholder-color:${h(color)}" title="${h(label)}">${h(short)}</span>`;
  }
  const clubButton=(id,name)=>id?`<button type="button" class="pc-club-action" data-career-type="club" data-career-id="${h(id)}">${crest(id,name)}<span>${h(window.FMClubIdentity?.resolve?.(id,name)?.display_name||name||id)}</span></button>`:'<span class="pc-dim">Not recorded</span>';
  const trophyArt=(file,type)=>safeName(file)?`<img class="pc-trophy-image" loading="lazy" decoding="async" src="/portable/assets/${type==='award'?'awards':'trophies'}/${h(file)}" alt="">`:'<span class="pc-trophy-generic" aria-hidden="true">🏆</span>';
  function mergeLists(primary,imported,key){
    const result=[],seen=new Set();
    for(const item of [...arr(primary),...arr(imported)]){
      if(!item||typeof item!=='object')continue;
      const id=key(item);if(!id||seen.has(id))continue;
      seen.add(id);result.push(item);
    }
    return result;
  }
  function overlay(d,seed){
    const seasons=mergeLists(d.seasons,seed.seasons,s=>String(s.season||''));
    const awards=mergeLists(d.awards,seed.awards,a=>[a.season,a.category,a.competition_id].join('|'));
    const honours=mergeLists(d.honours,seed.honours,a=>[a.season,a.competition_id,a.club_id].join('|'));
    return {...d,seasons,awards,honours,has_imported_history:
      arr(seed.seasons).length>0||arr(seed.awards).length>0||arr(seed.honours).length>0};
  }
  function hero(d){
    const c=window.FMClubIdentity?.resolve?.(d.current_club_id,d.current_club)||{};
    const theme=d.current_club_id?window.FMClubIdentity?.theme?.(d.current_club_id,d.current_club):null;
    const face=window.FMPortraits?.portrait?.({id:d.id,name:d.name,position:d.position,club_id:d.current_club_id,club:d.current_club},'pc-player-face')||'<span class="pc-face-fallback">◉</span>';
    const flag=window.FMNationFlags?.render?.(d.nationality,'pc-flag')||'◇';
    const bg=c.hero_image&&window.FMEntityAssets?.url?.(c.hero_image);
    const inline=`--pc-accent:${h(theme?.highlight||'#db5476')};--pc-color:${h(theme?.primary||'#a64162')};${bg?`--pc-background:url(&quot;${h(bg)}&quot;);`:''}`;
    const name=h(c.display_name||d.current_club||'Free agent');
    return `<section class="pc-hero" style="${inline}" data-fm-club-theme="${h(d.current_club_id||'')}" data-fm-club-name="${name}">
      <div class="pc-hero-image">${face}</div><div class="pc-hero-text">
        <span class="pc-eyebrow">PLAYER · CAREER ARCHIVE</span><h2>${h(d.name)}</h2>
        <div class="pc-hero-line"><span class="pc-position">${h(d.position)}</span>${flag} ${h(d.nationality)} <span class="pc-separator">·</span> ${d.age==null?'Age unavailable':h(d.age)+' years old'}</div>
        <p>Born ${h(date(d.birth_date))} <span class="pc-separator">·</span> Preferred foot: ${h(d.preferred_foot||'—')} <span class="pc-separator">·</span> ${d.status==='retired'?'Retired':d.status==='free_agent'?'Free agent':'Active player'}</p>
      </div><div class="pc-hero-club">${d.current_club_id?`<button type="button" data-career-type="club" data-career-id="${h(d.current_club_id)}">${crest(d.current_club_id,d.current_club,'pc-hero-crest')}<span><strong>${name}</strong><small>Current club →</small></span></button>`:'<strong>Free agent</strong>'}</div>
    </section>`;
  }
  function total(seasons,field){
    const rows=arr(seasons).map(s=>s.statistics||{});
    const vals=rows.map(r=>r[field]);const known=vals.filter(v=>v!==null&&v!==undefined&&Number.isFinite(Number(v)));
    if(!known.length)return {value:null,partial:false};
    const value=known.reduce((a,b)=>a+Number(b),0);
    return {value,partial:known.length<rows.length};
  }
  function overview(d){
    const seasons=arr(d.seasons);
    const apps=total(seasons,'appearances'),goals=total(seasons,'goals'),assists=total(seasons,'assists'),clean=total(seasons,'clean_sheets');
    const ratings=seasons.filter(s=>Number(s.statistics?.appearances)>0&&s.statistics?.average_match_rating!=null);
    const ratedApps=ratings.reduce((n,s)=>n+Number(s.statistics.appearances),0);
    const weighted=ratedApps?ratings.reduce((n,s)=>n+Number(s.statistics.average_match_rating)*s.statistics.appearances,0)/ratedApps:null;
    const clubs=new Set(seasons.flatMap(s=>arr(s.clubs).map(c=>c.id)));
    if(d.current_club_id)clubs.add(d.current_club_id);
    const items=[['⚽',apps,'Appearances'],['🥅',d.position==='GK'?clean:goals,d.position==='GK'?'Clean sheets':'Goals'],['👟',assists,'Assists'],['▥',{value:weighted,partial:ratings.length<seasons.length},'Average rating'],['🛡',{value:clubs.size||null},'Known clubs'],['🏆',{value:arr(d.honours).length},'Team honours']];
    return `<section class="pc-overview" aria-label="Career summary">${items.map(([icon,stat,label],i)=>`<div class="pc-overview-stat"><span class="pc-stat-symbol pc-stat-symbol-${i}" aria-hidden="true">${icon}</span><div><strong>${stat.value==null?'—':label==='Average rating'?fixed(stat.value):num(stat.value)}${stat.partial?'*':''}</strong><small>${h(label)}</small></div></div>`).join('')}</section>`;
  }
  const statLabel=k=>k==='overall'?'Overall Rating (OVR)':k;
  function development(d){
    const points=arr(d.progression), fields=[...new Set(['overall',...points.flatMap(p=>Object.keys(p.indicators||{}))])];
    if(!fields.includes(metric))metric='overall';
    const pick=p=>metric==='overall'?p.overall:p.indicators?.[metric];
    const values=points.map((p,i)=>({value:Number(pick(p)),date:p.date,season:p.season,index:i})).filter(x=>pick(points[x.index])!=null&&Number.isFinite(x.value));
    const px=x=>58+x*690/Math.max(points.length-1,1);
    const py=v=>235-(Math.max(0,Math.min(100,v))/100)*176;
    const path=values.length>1?values.map((o,i)=>(i?'L':'M')+px(o.index).toFixed(2)+' '+py(o.value).toFixed(2)).join(' '):'';
    const options=fields.map(f=>`<option value="${h(f)}" ${f===metric?'selected':''}>${h(statLabel(f))}</option>`).join('');
    const plot=values.length?`<svg class="pc-svg" viewBox="0 0 790 280" role="img" aria-label="${h(statLabel(metric))} progress chart">
      ${[0,25,50,75,100].map(v=>`<line x1="58" y1="${py(v)}" x2="748" y2="${py(v)}" stroke="#2a526d" stroke-dasharray="3 6"/><text x="16" y="${py(v)+4}" fill="#95b8cf" font-size="13">${v}</text>`).join('')}
      ${path?`<path d="${path}" stroke="#3dc8fc" stroke-width="3.5" fill="none" stroke-linejoin="round"/>`:''}
      ${values.map(x=>`<circle cx="${px(x.index)}" cy="${py(x.value)}" r="5" fill="#59dcf9" stroke="#07334c" stroke-width="2"><title>${h(x.season)}: ${x.value.toFixed(1)}</title></circle>`).join('')}
      ${values.map((x,i)=>`<text x="${px(x.index)}" y="${py(x.value)-13}" text-anchor="middle" fill="#eafaff" font-size="13">${x.value.toFixed(1)}</text>`).join('')}
      ${points.length?`<text x="58" y="265" fill="#a6c9df" font-size="12">${h(points[0].season)}</text><text x="748" y="265" text-anchor="end" fill="#a6c9df" font-size="12">${h(points.at(-1).season)}</text>`:''}
     </svg>`:'<div class="pc-empty-graph">No recorded development observations yet.</div>';
    return `<section class="pc-panel pc-development" data-history-progression><div class="pc-panel-head"><h3>Player Development</h3><select data-pc-metric aria-label="Development measurement">${options}</select></div>
       ${plot}<p class="pc-note">${values.length===1?'One real observation so far. The progression curve appears as more seasons are recorded.':`${values.length} actual observations · No estimated historic ratings`}</p></section>`;
  }
  function carousel(title,items,kind){
    const cards=items.map(item=>{
      const info=item.info;
      const label=info?.label||item.label||item.id;
      return `<article class="pc-prize-card" role="listitem" title="${h(label)}"><div class="pc-prize-art">${trophyArt(info?.image,kind)}</div>
        <strong class="pc-prize-count">${num(item.seasons.length)}</strong>
        <span class="pc-prize-title">${h(label)}</span>
        ${item.sub&&kind==='award'?`<small>${h(item.sub)}</small>`:''}
        <div class="pc-prize-years">${item.seasons.map(x=>`<span>${h(x)}</span>`).join('')}</div></article>`;
    }).join('');
    return `<section class="pc-panel pc-prize-panel pc-${kind==='award'?'awards':'honours'}"><div class="pc-panel-head"><h3>${h(title)}</h3><div class="pc-scroll-buttons"><span>Scroll for more</span><button type="button" data-pc-scroll="-1" aria-label="Previous ${h(title)}">‹</button><button type="button" data-pc-scroll="1" aria-label="Next ${h(title)}">›</button></div></div>
      <div class="pc-prize-track" tabindex="0" role="list" aria-label="${h(title)}" data-pc-track>${cards||`<div class="pc-empty-prizes">${kind==='award'?'No individual awards earned yet.':'No team honours earned yet.'}</div>`}</div></section>`;
  }
  function individualAwards(d){
    const grouped=new Map();
    for(const a of arr(d.awards)){
      const info=categoryFor(a.category,'award');
      const key=(info?.id||a.category||'unknown') + (info?.group_by_scope===false?':'+a.competition_id:'');
      if(!grouped.has(key))grouped.set(key,{id:key,label:info?.label||a.label||a.category,info,sub:'',seasons:[]});
      const item=grouped.get(key);
      if(a.season&&!item.seasons.includes(a.season))item.seasons.push(a.season);
      if(info?.group_by_scope===false)item.sub=a.competition||'';
    }
    const items=[...grouped.values()].map(x=>({...x,seasons:x.seasons.sort()}));
    const order=arr(awardCatalogue.categories).map(x=>x.category);
    items.sort((a,b)=>order.indexOf(a.info?.category)-order.indexOf(b.info?.category)||a.label.localeCompare(b.label));
    return carousel('Individual Awards',items,'award');
  }
  function teamHonours(d){
    const grouped=new Map();
    for(const a of arr(d.honours)){
      const cid=a.competition_id||a.id; if(!cid)continue;
      const info=categoryFor(cid);
      // Distinct competitions remain distinct for multi-country careers;
      // only synonymous IDs for the exact trophy share a card.
      const id=info?.id==='eng-leagues-all'||info?.id==='eng-lower'?slug(cid):(info?.id||slug(cid));
      if(!grouped.has(id))grouped.set(id,{id,label:a.competition||info?.label||cid,
        info:info?{...info,label:(info.id==='eng-leagues-all'||info.id==='eng-lower')?(a.competition||info.label):info.label}:null,
        seasons:[]});
      const obj=grouped.get(id);
      if(a.season&&!obj.seasons.includes(a.season))obj.seasons.push(a.season);
    }
    const trophies=[...grouped.values()].map(t=>({...t,seasons:t.seasons.sort()}));
    trophies.sort((a,b)=>(Number(a.info?.rank)||100)-(Number(b.info?.rank)||100)||a.label.localeCompare(b.label));
    return carousel('Team Honours',trophies,'honour');
  }
  function careerEvents(d){
    const events=[];
    for(const t of arr(d.transfers))events.push({when:t.date||'',date:date(t.date),type:'transfer',title:'Permanent transfer',detail:`${t.from} → ${t.to}${t.fee_gbp!=null?' · '+gbp(t.fee_gbp):''}`,clubId:t.to_id,club:t.to});
    for(const l of arr(d.loans))events.push({when:l.date||'',date:date(l.date),type:'loan',title:'Loan move',detail:`${l.from} → ${l.to} · Until ${date(l.ends_on)}`,clubId:l.to_id,club:l.to});
    for(const a of arr(d.honours))events.push({when:a.season?.slice(0,4)||'',date:a.season||'',type:'trophy',title:'Team honour',detail:`${a.competition}${a.club?' · '+a.club:''}`,clubId:a.club_id,club:a.club});
    // This is not a fictitious debut: it is the earliest verified season with
    // a participant in the match ledger.
    const observed=arr(d.seasons).filter(x=>Number(x.statistics?.appearances)>0).sort((a,b)=>String(a.season).localeCompare(String(b.season)));
    if(observed.length)events.push({when:observed[0].season.slice(0,4),date:observed[0].season,type:'record',title:'First recorded season',detail:`${num(observed[0].statistics.appearances)} recorded appearances`,clubId:observed[0].clubs?.[0]?.id,club:observed[0].clubs?.[0]?.name});
    events.sort((a,b)=>String(a.when).localeCompare(String(b.when))||String(a.title).localeCompare(String(b.title)));
    return events;
  }
  function journey(d){
    const events=careerEvents(d);
    return `<section class="pc-panel pc-journey"><div class="pc-panel-head"><h3>Career Journey</h3><span>Verified milestones</span></div>
      <div class="pc-journey-list">${events.length?events.map(e=>`<div class="pc-journey-item pc-journey-${h(e.type)}"><span class="pc-journey-dot"></span><small>${h(e.date)}</small><div>${crest(e.clubId,e.club)}<strong>${h(e.title)}</strong></div><p>${h(e.detail)}</p></div>`).join(''):'<p class="pc-empty-prizes">Career milestones will appear after verified matches, moves or titles.</p>'}</div></section>`;
  }
  function seasons(d){
    const rows=arr(d.seasons).map(s=>{
      const st=s.statistics||{}, played=arr(s.clubs);
      const clubs=played.length?played.map(c=>clubButton(c.id,c.name)).join(' '):'<span class="pc-dim">Club attribution unavailable</span>';
      const coverage=s.coverage?.complete_season?'Complete':'Partial';
      const contents=arr(s.competitions).length?`<div class="pc-comp-table"><div class="pc-comp-row pc-comp-head"><span>Competition</span><span>Apps</span><span>Min</span><span>Goals</span><span>Assists</span><span>Avg</span></div>${s.competitions.map(row=>`<div class="pc-comp-row"><span>${h(row.competition)}</span><span>${num(row.statistics?.appearances)}</span><span>${num(row.statistics?.minutes)}</span><span>${num(row.statistics?.goals)}</span><span>${num(row.statistics?.assists)}</span><span>${fixed(row.statistics?.average_match_rating)}</span></div>`).join('')}</div>`:'<p class="pc-note">Competition-by-competition records were not collected for this season.</p>';
      return `<details class="pc-season"><summary><span>${h(s.season)}</span><span>${clubs}</span><span>${num(st.appearances)}</span><span>${num(st.goals)}</span><span>${num(st.assists)}</span><span>${fixed(st.average_match_rating)}</span><span class="pc-season-status ${coverage==='Complete'?'is-complete':''}">${coverage}</span></summary>${contents}</details>`;
    }).join('');
    return `<section class="pc-panel pc-seasons"><div class="pc-panel-head"><h3>Season by Season</h3><span>Open a season for each competition</span></div>
      <div class="pc-table-scroll"><div class="pc-season-head"><span>Season</span><span>Club</span><span>Apps</span><span>Goals</span><span>Assists</span><span>Avg</span><span>Coverage</span></div>${rows||'<p class="pc-empty-prizes">No recorded seasons yet.</p>'}</div>
      <p class="pc-note">Incomplete tracking is marked Partial; missing values are never treated as zero.</p></section>`;
  }
  function transfers(d){
    const rows=arr(d.transfers).map(t=>`<div class="pc-move-row"><span>${h(date(t.date))}</span>${clubButton(t.from_id,t.from)}<span class="pc-arrow">→</span>${clubButton(t.to_id,t.to)}<strong>${h(gbp(t.fee_gbp))}</strong></div>`).join('');
    return `<section class="pc-panel pc-transfers"><div class="pc-panel-head"><h3>Confirmed Transfers</h3></div><div class="pc-move-scroll">${rows||'<p class="pc-empty-prizes">No confirmed transfers recorded.</p>'}</div></section>`;
  }
  function loans(d){
    const rows=arr(d.loans).map(l=>`<div class="pc-move-row pc-loan-row"><span>${h(date(l.date))} – ${h(date(l.ends_on))}</span>${clubButton(l.from_id,l.from)}<span class="pc-arrow">→</span>${clubButton(l.to_id,l.to)}<strong>${h(l.status)}</strong></div>`).join('');
    return `<section class="pc-panel pc-loans"><div class="pc-panel-head"><h3>Loans</h3></div><div class="pc-move-scroll">${rows||'<p class="pc-empty-prizes">No loans recorded.</p>'}</div></section>`;
  }
  function render(d,seed={}){
    const source=overlay(d,seed);
    return `<div class="pc-root">${hero(source)}${overview(source)}
      <div class="pc-grid">${development(source)}${individualAwards(source)}${journey(source)}${teamHonours(source)}${seasons(source)}${transfers(source)}${loans(source)}</div>
      <p class="pc-provenance">Verified career records${source.has_imported_history?' + separately imported player-ID history':''}. Team honours are certified from the champion's registered roster at season-end. Missing statistics and awards are not invented; the Puskás award awaits a verified goal-quality record.</p>
    </div>`;
  }
  function click(event,host){
    const button=event.target.closest?.('[data-pc-scroll]');
    if(!button||!host.contains(button))return false;
    button.closest('.pc-prize-panel')?.querySelector('[data-pc-track]')?.scrollBy({left:280*Number(button.dataset.pcScroll),behavior:'smooth'});
    return true;
  }
  function wheel(event,host){
    const scroller=event.target.closest?.('[data-pc-track]');
    if(!scroller||!host.contains(scroller)||event.ctrlKey||event.metaKey||event.shiftKey||scroller.scrollWidth<=scroller.clientWidth)return;
    if(Math.abs(event.deltaY)<=Math.abs(event.deltaX))return;
    const goal=scroller.scrollLeft+event.deltaY;
    if(goal>=0&&goal<=scroller.scrollWidth-scroller.clientWidth){event.preventDefault();scroller.scrollLeft=goal;}
  }
  function change(event,host,d){
    if(!event.target.matches?.('[data-pc-metric]'))return false;
    metric=event.target.value;
    const old=host.querySelector('[data-history-progression]');
    if(old)old.outerHTML=development(d);
    return true;
  }
  window.FMPlayerCareer=Object.freeze({render,load,historicalFor,click,wheel,change,categoryFor,overlay,overview,individualAwards,teamHonours,careerEvents});
})();
