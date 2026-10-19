/* TS-20: read-only automatic squad dynamics. Native browser JS; no Node runtime.
 * Rendering/selection never POST and never advance the football clock. */
(() => {
  'use strict';
  const esc = x => String(x ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const signed = n => `${Number(n) > 0 ? '+' : ''}${Number(n).toFixed(2)}`;
  const percent = n => Math.min(100, Math.max(0, Number(n) || 0));
  let host = null, model = null, selected = null, request = 0;
  const glyph = {leaders:'\u25c6', influential:'\u25c7', core:'\u25cf', emerging:'\u25cb'};
  function portrait(p) {
    return window.FMPortraits?.portrait(p, 'dr-face') || `<span class="dr-initials">${esc(p.short_name.slice(0,2))}</span>`;
  }
  function tile(p) {
    return `<button type="button" class="dr-player ${p.id===selected?'is-selected':''}" data-dr-player="${esc(p.id)}" aria-pressed="${p.id===selected}" title="${esc(p.name)}: ${esc(p.tier_label)}">
      ${portrait(p)}<span class="dr-player-copy"><strong>${esc(p.short_name)}</strong><small>${esc(p.position)}${p.newcomer?' &middot; New':p.young_player?' &middot; Young player':''}</small></span>
      <span class="dr-trend ${esc(p.trend)}" aria-label="Influence ${esc(p.trend)}">${p.trend==='rising'?'\u2197':p.trend==='easing'?'\u2198':'\u2014'}</span></button>`;
  }
  function network() {
    if (!model.members.length) return '<p class="dr-muted">No registered players.</p>';
    const positions = new Map();
    model.members.forEach((p, i) => {
      const angle = (i/model.members.length)*Math.PI*2-Math.PI/2;
      positions.set(p.id, {x:300+Math.cos(angle)*229,y:177+Math.sin(angle)*125});
    });
    const links = model.links.filter(l=>l.a===selected || l.b===selected).sort((a,b)=>b.strength-a.strength).slice(0,6);
    const lines = links.map(l=>{
      const a=positions.get(l.a), b=positions.get(l.b);
      return a && b ? `<line x1="${a.x}" y1="${a.y}" x2="${b.x}" y2="${b.y}" class="${l.strength>=70?'is-close':''}" stroke-width="${l.strength>=70?2:1}"/>` : '';
    }).join('');
    const nodes = model.members.map(p=>{
      const xy=positions.get(p.id), active=p.id===selected;
      return `<g role="button" tabindex="0" data-dr-player="${esc(p.id)}" aria-label="Connections for ${esc(p.name)}" aria-pressed="${active}" class="dr-node ${active?'is-selected':''}">
        <title>${esc(p.name)} &middot; ${esc(p.tier_label)}</title><circle cx="${xy.x}" cy="${xy.y}" r="${active?17:12}"/>
        <text x="${xy.x}" y="${xy.y+4}" class="dr-node-initial">${esc(p.short_name.slice(0,1))}</text>
        <text x="${xy.x}" y="${xy.y+30}">${esc(p.short_name)}</text></g>`;
    }).join('');
    return `<svg class="dr-network" viewBox="0 0 600 360" role="group" aria-label="Squad relationships. Select a player to inspect their strongest connections.">
      <ellipse cx="300" cy="177" rx="229" ry="125" class="dr-orbit"/>${lines}${nodes}</svg>`;
  }
  function details() {
    const p=model.members.find(m=>m.id===selected);
    if (!p) return '<p class="dr-muted">Choose a player in the pyramid.</p>';
    const support=model.members.find(m=>m.id===p.support_player_id);
    const peers=model.links.filter(l=>l.a===p.id||l.b===p.id).sort((a,b)=>b.strength-a.strength).slice(0,3);
    return `<div class="dr-profile-heading">${portrait(p)}<div><span class="dr-eyebrow">${esc(p.tier_label)}</span><h3>${esc(p.name)}</h3><span class="dr-muted">${p.age} years &middot; ${esc(p.position)}</span></div></div>
      <p class="dr-observation">${esc(p.character_note)}</p>
      <div class="dr-label-row"><strong>Integration</strong><span>${esc(p.integration_label)}</span></div>
      <div class="dr-meter" role="meter" aria-label="Integration" aria-valuemin="0" aria-valuemax="100" aria-valuenow="${percent(p.integration)}"><i style="width:${percent(p.integration)}%"></i></div>
      <div class="dr-facts"><div><strong>${p.recent_appearances}</strong><small>Appearances</small></div><div><strong>${p.recent_minutes}</strong><small>Minutes</small></div><div><strong>${signed(p.social_morale_effect)}</strong><small>Morale context / 100</small></div></div>
      <p class="dr-caption">Actual matches in the last 42 days. Injuries and suspensions do not count as voluntary omissions.</p>
      <div class="dr-support"><span class="dr-eyebrow">Natural support</span><p>${support?`<strong>${esc(support.name)}</strong> helps this player settle. No assignment needed.`:'No specific integration support needed or established yet.'}</p></div>
      <h4>Closest working connections</h4><div class="dr-peers">${peers.map(l=>{
        const q=model.members.find(m=>m.id===(l.a===p.id?l.b:l.a));
        return q?`<button type="button" data-dr-player="${esc(q.id)}"><span>${esc(q.name)}</span><small>${esc(l.label)}</small></button>`:'';
      }).join('')||'<p class="dr-muted">Connections are still developing.</p>'}</div>
      <h4>What explains the current picture?</h4><div class="dr-reasons">${p.reasons.map(x=>`<p>${esc(x)}</p>`).join('')}</div>
      <p class="dr-caption">Observed since ${esc(p.observed_since)}. Personality values stay hidden; no OVR or ability change here.</p>
      <button type="button" class="mi-talk-open" data-dr-talk="${esc(p.id)}">Talk to this player</button>`;
  }
  function render() {
    if (!host||!model) return;
    if(!model.members.some(p=>p.id===selected)) selected=model.members[0]?.id||null;
    host.innerHTML=`<div class="dr-intro"><div><span class="dr-eyebrow">TS-20 &middot; AUTOMATIC SQUAD DYNAMICS</span><h2>A team beyond the team sheet</h2><p>Influence is earned over time. Relationships evolve quietly while you focus on football.</p></div><span class="dr-live"><i></i> No decisions required</span></div>
      <div class="dr-summary"><article><span>Atmosphere</span><strong>${esc(model.atmosphere_label)}</strong><small>Calm, gradual changes</small></article><article><span>Social morale context</span><strong>${signed(model.average_morale_effect)} <em>/ 100</em></strong><small>Individual effects capped at &plusmn;${model.max_morale_effect}</small></article><article><span>Next hierarchy review</span><strong class="dr-date">${esc(model.next_review)}</strong><small>Last updated ${esc(model.updated_on)}</small></article></div>
      <div class="dr-main"><section class="dr-panel dr-pyramid-panel" aria-labelledby="dr-pyramid-title"><div class="dr-section-heading"><div><span class="dr-eyebrow">INFLUENCE, NOT ABILITY</span><h3 id="dr-pyramid-title">Squad hierarchy</h3></div><span class="dr-count">${model.members.length} players</span></div>
        <div class="dr-pyramid">${model.tiers.map(t=>`<div class="dr-tier dr-tier-${esc(t.id)}"><div class="dr-tier-title"><span>${glyph[t.id]} ${esc(t.label)}</span><span>${t.count}</span></div><div class="dr-tier-players">${model.members.filter(p=>p.tier===t.id).map(tile).join('')||'<span class="dr-empty-tier">No player established here yet</span>'}</div></div>`).join('')}</div>
        <p class="dr-caption dr-hierarchy-note">Weekly reviews &middot; Gradual promotions and demotions &middot; Veterans are not automatically leaders</p></section>
        <aside class="dr-panel dr-profile" aria-label="Selected player social context">${details()}</aside></div>
      <div class="dr-lower"><section class="dr-panel"><div class="dr-section-heading"><div><span class="dr-eyebrow">SHARED TIME &amp; UNDERSTANDING</span><h3>Working connections</h3></div><span class="dr-count">${model.groups.length} close ${model.groups.length===1?'group':'groups'}</span></div>${network()}<p class="dr-caption">Select a player to see up to six strongest links. A line represents observed rapport, not a fixed friendship or a match bonus.</p></section>
      <section class="dr-panel dr-journal"><div class="dr-section-heading"><div><span class="dr-eyebrow">INFORMATION, NOT INTERRUPTIONS</span><h3>Recent changes</h3></div><button type="button" class="dr-refresh" data-dr-refresh>Refresh</button></div>
        <div class="dr-events">${model.events.slice(0,8).map(e=>`<article><time>${esc(e.date)}</time><p>${esc(e.message)}</p></article>`).join('')||'<div class="dr-quiet"><span>Everything is quiet</span><p>Meaningful changes will appear here as days and matches pass. There is nothing you need to do.</p></div>'}</div></section></div>
      <details class="dr-explainer"><summary>How this works</summary>${model.notes.map(n=>`<p>${esc(n)}</p>`).join('')}<p>The library and tactics stay in Edit Tactics. Player development and aging belong to a later update. Save your career to preserve this history.</p></details>`;
    host.querySelectorAll('[data-dr-player]').forEach(el=>{
      const choose=()=>{selected=el.getAttribute('data-dr-player');render();
        const next=[...host.querySelectorAll('.dr-player')].find(e=>e.dataset.drPlayer===selected);
        next?.focus({preventScroll:true});};
      el.addEventListener('click',choose);
      if(el.tagName.toLowerCase()==='g') el.addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();choose();}});
    });
    host.querySelector('[data-dr-refresh]')?.addEventListener('click',refresh);
    host.querySelector('[data-dr-talk]')?.addEventListener('click',()=>window.FMNavigation?.navigate('Inbox',false,{player:selected}));
  }
  async function refresh() {
    if(!host) return;
    const serial=++request, target=host;
    target.setAttribute('aria-busy','true');
    try {
      const response=await fetch('/api/dressing-room',{cache:'no-store'});
      if(!response.ok) throw new Error(`Python HTTP ${response.status}`);
      const data=await response.json();
      if(serial!==request||target!==host) return;
      if(data.source!=='python-dressing-room'||!Array.isArray(data.members)) throw new Error('Unexpected dressing room response');
      model=data;render();
    } catch(error) {
      if(serial!==request||target!==host) return;
      // Never leave old career information displayed as if it were current.
      model=null;
      target.innerHTML=`<div class="dr-panel dr-error" role="status"><h3>Dressing room unavailable</h3><p>${esc(error.message)}. Your squad has not been changed.</p><button type="button" data-dr-retry>Try again</button></div>`;
      target.querySelector('[data-dr-retry]').addEventListener('click',refresh);
    } finally {if(serial===request&&target===host)target.setAttribute('aria-busy','false');}
  }
  function mount(element) {
    host=element;
    host.innerHTML='<div class="dr-panel dr-loading" role="status">Reading the current dressing room...</div>';
    refresh();
  }
  window.FMDressingRoom=Object.freeze({mount,refresh});
})();
