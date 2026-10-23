/* TS-UI-10.01 — scalable trophies by country / competition ID.
 * Categories are presentational. Titles are calculated from verified career
 * results and optional pre-career history; this module never writes the save. */
(() => {
  'use strict';
  const escapeHtml = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;'}[c]));
  const slug = value => String(value || '').normalize('NFKD').replace(/[\u0300-\u036f]/g, '').toLowerCase().trim().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
  const fallback = {schema_version: 1, countries: {}, regions: {}, global_categories: []};
  let catalogue = fallback;
  let request = null;
  function load(){
    if (!request) request = fetch('/portable/data/honour-competitions.json', {cache:'no-store'})
      .then(r => {if(!r.ok)throw Error('Honours catalogue unavailable');return r.json();})
      .then(data => {if(data?.schema_version===1 && data.countries && data.regions && Array.isArray(data.global_categories)) catalogue=data;return catalogue;})
      .catch(()=>catalogue);
    return request;
  }
  const arr = value => Array.isArray(value) ? value : [];
  function categories(country, source = catalogue){
    const tag=slug(country);
    let domestic=[];
    const match=Object.entries(source.countries||{}).find(([id,entry]) => tag===slug(id)||arr(entry.aliases).some(x=>slug(x)===tag));
    if(match) domestic=arr(match[1].categories);
    const continental=Object.values(source.regions||{}).flatMap(region=>arr(region.countries).some(c=>slug(c)===tag)?arr(region.categories):[]);
    return [...domestic,...continental,...arr(source.global_categories)].map(c=>({...c, competition_ids:arr(c.competition_ids).map(slug)}));
  }
  function trophyEvents(data, historic){
    const items=[];
    const seen=new Set();
    for(const row of arr(data?.trophies)){
      const key=slug(row.id||row.competition_id||row.name), season=String(row.season||'');
      if(!key || seen.has(`${key}|${season}`))continue;
      seen.add(`${key}|${season}`);
      items.push({key,name:String(row.name||row.competition||row.id||''),total:1,season});
    }
    for(const row of arr(historic?.honours)){
      if(!row || typeof row!=='object')continue;
      const key=slug(row.competition_id||row.competition||'');
      const seasons=arr(row.seasons);
      const total=Number.isSafeInteger(row.total)&&row.total>=0?row.total:seasons.length;
      if(!key || !total)continue;
      items.push({key,name:String(row.competition||row.competition_id||''),total,season:seasons[seasons.length-1]||''});
    }
    return items;
  }
  function summarise(data, historic, source = catalogue){
    const country=data?.institution?.country||historic?.country||'';
    const raw=categories(country,source);
    const history=trophyEvents(data,historic);
    const known=new Set(raw.flatMap(c=>c.competition_ids));
    const unknown=new Map();
    const add=(key,label)=>{
      if(!key || known.has(key)||unknown.has(key))return;
      unknown.set(key,{id:`other-${key}`,label:String(label||key).slice(0,110),competition_ids:[key],rank:120});
    };
    // Never drop competitions from other countries or newly imported databases.
    for(const row of arr(data?.live?.competitions))add(slug(row.id),row.name||row.id);
    for(const row of history)add(row.key,row.name||row.key);
    const rows=[...raw,...unknown.values()];
    const numbered=rows.map(cat=>{
      const keys=new Set(arr(cat.competition_ids).map(slug));
      const titles=history.filter(t=>keys.has(t.key));
      const count=titles.reduce((sum,t)=>sum+t.total,0);
      const last=titles.map(t=>String(t.season||'')).filter(Boolean).sort().pop()||'';
      return {...cat,count,last,source_count:titles.length};
    });
    numbered.sort((a,b)=>(Number(a.rank)||100)-(Number(b.rank)||100)||String(a.label).localeCompare(String(b.label)));
    return numbered;
  }
  function picture(item){
    const name=String(item.image||'');
    if(!/^[a-z0-9-]+\.png$/.test(name))return '<span class="ci-honour-fallback" aria-hidden="true">🏆</span>';
    return `<img loading="lazy" decoding="async" class="ci-honour-picture" src="/portable/assets/trophies/${escapeHtml(name)}" alt="" aria-hidden="true">`;
  }
  function render(data,historic){
    const items=summarise(data,historic);
    const tiles=items.map(item=>`<div class="ci-trophy-tile" role="listitem" title="${escapeHtml(item.label)}${item.subtitle?' — '+escapeHtml(item.subtitle):''}">
      <div class="ci-trophy-art">${picture(item)}</div>
      <strong class="ci-trophy-count">${Number(item.count).toLocaleString('en-GB')}</strong>
      <span class="ci-trophy-label">${escapeHtml(item.label)}</span>
      ${item.subtitle?`<small class="ci-trophy-subtitle">${escapeHtml(item.subtitle)}</small>`:''}
    </div>`).join('');
    const hasHistoric=arr(historic?.honours).length>0;
    return `<div class="ci-trophy-scroll" tabindex="0" role="region" aria-label="Trophies; scroll to see more competitions" data-ci-trophy-scroll>
      <div class="ci-trophy-track" role="list">${tiles||'<div class="ci-empty">No competitions registered for this club.</div>'}</div>
    </div>
    <div class="ci-trophy-bottom"><span>${hasHistoric?'Career + imported history':'Career titles · Historical archive pending'}</span>
      <div class="ci-trophy-arrows"><button type="button" aria-label="Previous trophies" data-ci-trophy-direction="-1">‹</button><button type="button" aria-label="Next trophies" data-ci-trophy-direction="1">›</button></div></div>
    <button class="ci-secondary-button" type="button" data-ci-tab="history">View all honours →</button>`;
  }
  // Used by isolated tests; never mutates the internal catalogue.
  window.FMClubHonours=Object.freeze({load,render,summarise,categories});
})();
