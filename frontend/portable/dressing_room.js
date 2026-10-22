/* TS-UI-06.02: approved four-tier Dressing Room and photographic club header.
 * The existing TS-20 Python projection remains authoritative and read-only.
 * Club colours, crest and display name are resolved from the shared catalogue. */
(() => {
  'use strict';
  const esc = x => String(x ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const signed = n => `${Number(n) > 0 ? '+' : ''}${(Number(n) || 0).toFixed(2)}`;
  const percent = n => Math.min(100, Math.max(0, Number(n) || 0));
  const monthNames = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
  const dateLabel = iso => { const [y,m,d] = String(iso||'').split('-'); return +m >= 1 && +m <= 12 && y && d ? `${Number(d)} ${monthNames[Number(m)-1]} ${y}` : String(iso||'—'); };
  let host = null, model = null, selected = null, request = 0;
  const tierIcons = { leaders:'♛', influential:'♟', core:'♟', emerging:'✧' };

  function portrait(p, classes='dr-face') {
    return window.FMPortraits?.portrait(p, classes) || `<span class="${classes} dr-initials">${esc((p.short_name || p.name || '?').slice(0,2))}</span>`;
  }
  function tierLabel(t) { return t.id === 'emerging' ? 'Developing influence' : t.label; }
  function tile(p) {
    return `<button type="button" class="dr-player ${p.id === selected ? 'is-selected' : ''}" data-dr-player="${esc(p.id)}" aria-pressed="${p.id === selected}" title="${esc(p.name)} — ${esc(p.tier_label)}">
      ${portrait(p)}<span class="dr-player-copy"><strong>${esc(p.short_name)}</strong><small>${esc(p.position)}</small></span>
      ${p.trend === 'rising' ? '<span class="dr-trend rising" aria-label="Influence rising">↗</span>' : p.trend === 'easing' ? '<span class="dr-trend easing" aria-label="Influence easing">↘</span>' : ''}
    </button>`;
  }
  function pyramidTier(t) {
    const players = model.members.filter(p => p.tier === t.id);
    return `<div class="dr-tier dr-tier-${esc(t.id)}" data-dr-tier="${esc(t.id)}">
      <div class="dr-tier-title"><span class="dr-tier-symbol" aria-hidden="true">${tierIcons[t.id] || '◆'}</span><strong>${esc(tierLabel(t))} (${players.length})</strong></div>
      <div class="dr-tier-players">${players.map(tile).join('') || '<span class="dr-empty-tier">No players in this tier</span>'}</div>
    </div>`;
  }
  function teamMorale() {
    // The actual effective 0-100 morale comes from the existing Python projection.
    // The social morale modifier is a different, +/-2 metric; do not relabel it.
    if (!model.members.length) return {label:'—',value:0};
    const value = percent(model.members.reduce((sum,p)=>sum+(Number(p.morale)||0),0)/model.members.length);
    return {value, label:value>=80?'Excellent':value>=65?'Good':value>=50?'Stable':'Low'};
  }
  function clubIdentity() {
    // Never bake any team's crest, name or colours into the photograph.
    const id=window.FMClubIdentity?.resolve?.(model.club_id,model.club);
    return {name:id?.display_name || model.club || 'Your club',crest:id?.crest || null};
  }
  function hero() {
    const club=clubIdentity();
    const crest=club.crest
      ? `<img src="${esc(club.crest)}" alt="" loading="eager">`
      : '<span class="dr-crest-fallback" aria-hidden="true">⚽</span>';
    return `<header class="dr-intro" aria-label="Dressing Room club overview">
      <div class="dr-intro-identity"><span class="dr-brand-crest">${crest}</span>
        <div class="dr-intro-copy"><span class="dr-eyebrow">${esc(club.name)} · FIRST TEAM</span>
          <h2>Dressing Room</h2><strong class="dr-hero-tagline">A team beyond the team sheet</strong>
          <p>Influence is earned over time. Relationships evolve quietly while you focus on football.</p>
        </div>
      </div>
      <div class="dr-hero-kpis">${summary('hero')}</div>
    </header>`;
  }
  function summary(mode='') {
    const morale = teamMorale();
    return `<div class="dr-summary${mode==='hero'?' dr-summary-in-hero':''}">
      <article class="dr-kpi-atmosphere"><span class="dr-kpi-icon" aria-hidden="true">♧</span><div class="dr-kpi-copy"><span>Atmosphere</span><strong>${esc(model.atmosphere_label)}</strong><div class="dr-kpi-track"><i style="width:${percent(model.atmosphere)}%"></i></div></div></article>
      <article class="dr-kpi-morale"><span class="dr-kpi-icon" aria-hidden="true">♥</span><div class="dr-kpi-copy"><span>Team morale</span><strong>${esc(morale.label)}</strong><div class="dr-kpi-track"><i style="width:${morale.value}%"></i></div></div></article>
      <article class="dr-kpi-review"><span class="dr-kpi-icon" aria-hidden="true">▣</span><div class="dr-kpi-copy"><span>Next review</span><strong class="dr-date">${esc(dateLabel(model.next_review))}</strong><div class="dr-kpi-track"><i style="width:${percent(100 - Math.min(100, Math.max(0, Math.round((Date.parse(model.next_review+'T00:00:00Z')-Date.parse(model.date+'T00:00:00Z'))/604800000*100))))}%"></i></div></div></article>
    </div>`;
  }
  function details() {
    const p = model.members.find(m=>m.id===selected);
    if(!p) return '<div class="dr-muted dr-empty-profile">Select a player from the hierarchy.</div>';
    const support=model.members.find(m=>m.id===p.support_player_id);
    const peers=model.links.filter(l=>l.a===p.id||l.b===p.id).sort((a,b)=>b.strength-a.strength).slice(0,3);
    const insight = support ? `${support.name} is helping this player settle.` : (p.reasons.find(x=>!x.startsWith('No significant social concern')) || (p.integration >= 65 ? 'Settled within the squad.' : p.character_note));
    return `<div class="dr-profile-heading">${portrait(p)}<div class="dr-profile-name"><h3>${esc(p.name)}</h3><span class="dr-muted">${esc(p.age)} years old · ${esc(p.position)}</span></div></div>
      <div class="dr-profile-divider"></div>
      <div class="dr-label-row"><strong>Integration</strong><span>${esc(p.integration_label)}</span></div>
      <div class="dr-meter" role="meter" aria-label="Integration" aria-valuemin="0" aria-valuemax="100" aria-valuenow="${percent(p.integration)}"><i style="width:${percent(p.integration)}%"></i></div>
      <div class="dr-facts"><div><strong>${esc(p.recent_appearances)}</strong><small>Appearances</small></div><div><strong>${esc(p.recent_minutes)}</strong><small>Minutes</small></div><div><strong>${signed(p.social_morale_effect)}</strong><small>Social impact</small></div></div>
      <div class="dr-support"><span class="dr-support-symbol" aria-hidden="true">✦</span><div><strong>Key insight</strong><p>${esc(insight)}</p></div></div>
      <h4>Key connections</h4><div class="dr-peers">${peers.map(l=>{
        const q=model.members.find(m=>m.id===(l.a===p.id?l.b:l.a));
        return q ? `<button type="button" data-dr-player="${esc(q.id)}" title="${esc(l.label)} with ${esc(q.name)}">${portrait(q,'dr-face dr-peer-face')}<span>${esc(q.name)}</span><small>${esc(l.label)}</small></button>` : '';
      }).join('') || '<p class="dr-muted">Relationships are developing.</p>'}</div>
      <div class="dr-actions"><button type="button" class="ch-link" data-career-type="player" data-career-id="${esc(p.id)}">View history</button><button type="button" class="mi-talk-open" data-dr-talk="${esc(p.id)}">Talk to player</button></div>`;
  }
  function network() {
    if (!model.members.length) return '<p class="dr-muted">No registered players.</p>';
    // Selected player is the centre of the network. Everyone else is shown
    // across two rows, with ONLY the six strongest observed links highlighted.
    const peers = model.members.filter(p=>p.id!==selected);
    const first = Math.ceil(peers.length/2);
    const positions = new Map([[selected,{x:50,y:18}]]);
    peers.forEach((p,i)=>{
      const firstRow=i<first, idx=firstRow?i:i-first, count=firstRow?first:peers.length-first;
      const x=7+(idx+.5)*86/Math.max(1,count);
      positions.set(p.id,{x,y:firstRow?54:83});
    });
    const connections=model.links.filter(l=>l.a===selected||l.b===selected).sort((a,b)=>b.strength-a.strength).slice(0,6);
    const edges=connections.map(l=>{
      const a=positions.get(l.a),b=positions.get(l.b);
      return a&&b?`<line x1="${a.x}" y1="${a.y}" x2="${b.x}" y2="${b.y}" class="${l.strength>=70?'is-close':''}" />`:'';
    }).join('');
    const nodes=model.members.map(p=>{
      const xy=positions.get(p.id); if(!xy)return '';
      return `<button type="button" class="dr-node ${p.id===selected?'is-selected':''}" data-dr-player="${esc(p.id)}" aria-pressed="${p.id===selected}" aria-label="Show relationships for ${esc(p.name)}" title="${esc(p.name)}" style="left:${xy.x}%;top:${xy.y}%">
        ${portrait(p,'dr-face dr-node-face')}<span>${esc(p.short_name)}</span></button>`;
    }).join('');
    return `<div class="dr-network-shell"><div class="dr-network" role="group" aria-label="Squad relationships. Select any player to inspect their recorded links."><svg viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true"><g>${edges}</g></svg>${nodes}</div></div>`;
  }
  function events() {
    if (!model.events.length) return '<div class="dr-quiet"><span class="dr-quiet-icon" aria-hidden="true">◌</span><strong>No recent changes</strong><p>Squad dynamics are stable.</p></div>';
    return model.events.slice(0,8).map(e=>`<article class="dr-event"><span class="dr-event-icon" aria-hidden="true">${e.kind==='hierarchy'?'↗':'•'}</span><div><p>${esc(e.message)}</p><time>${esc(dateLabel(e.date))}</time></div></article>`).join('');
  }
  function centerScrollableGraph() {
    const shell=host?.querySelector('.dr-network-shell');
    if(shell && shell.scrollWidth>shell.clientWidth) {
      shell.scrollLeft=(shell.scrollWidth-shell.clientWidth)/2;
    }
  }
  window.addEventListener('resize',centerScrollableGraph);
  window.addEventListener('fm-identity-ready',()=>{if(host&&model)render();});
  function render() {
    if (!host||!model)return;
    if(!model.members.some(p=>p.id===selected))selected=model.members[0]?.id||null;
    // Same crest, name and palette as Squad, Training and Staff.
    window.FMClubIdentity?.applyTheme?.(model.club_id,model.club);
    host.innerHTML=`${hero()}
      ${summary()}
      <div class="dr-main"><section class="dr-panel dr-pyramid-panel" aria-labelledby="dr-pyramid-title"><div class="dr-section-heading"><h3 id="dr-pyramid-title">Squad hierarchy</h3><span class="dr-count">${model.members.length} players</span></div>
        <div class="dr-pyramid">${model.tiers.map(pyramidTier).join('')}</div></section>
        <aside class="dr-panel dr-profile" aria-label="Selected player social context"><div class="dr-section-heading"><h3>Player Details</h3></div>${details()}</aside></div>
      <div class="dr-lower"><section class="dr-panel dr-connections"><div class="dr-section-heading"><h3>Working connections</h3><span class="dr-count">${model.groups.length} close ${model.groups.length===1?'group':'groups'}</span></div>${network()}</section>
      <section class="dr-panel dr-journal"><div class="dr-section-heading"><h3>Recent changes</h3><button type="button" class="dr-refresh" data-dr-refresh aria-label="Refresh social dynamics">Refresh</button></div><div class="dr-events">${events()}</div></section></div>
      <details class="dr-explainer"><summary>How this works</summary>${model.notes.map(n=>`<p>${esc(n)}</p>`).join('')}</details>`;
    host.querySelectorAll('[data-dr-player]').forEach(el=>{
      el.addEventListener('click',()=>{
        const kind=el.classList.contains('dr-node')?'dr-node':el.classList.contains('dr-player')?'dr-player':'dr-peers';
        selected=el.getAttribute('data-dr-player');render();
        const next=[...host.querySelectorAll('[data-dr-player]')].find(e=>e.getAttribute('data-dr-player')===selected&&(kind==='dr-peers'?e.classList.contains('dr-player'):e.classList.contains(kind)));
        next?.focus({preventScroll:true});
      });
    });
    // Keep the selected player visible on compact screens; no page overflow.
    centerScrollableGraph();
    host.querySelector('[data-dr-refresh]')?.addEventListener('click',refresh);
    host.querySelector('[data-dr-talk]')?.addEventListener('click',()=>window.FMNavigation?.navigate('Inbox',false,{player:selected}));
  }
  async function refresh() {
    if (!host) return;
    const serial=++request,target=host;
    target.setAttribute('aria-busy','true');
    try {
      const response=await fetch('/api/dressing-room',{cache:'no-store'});
      if(!response.ok)throw new Error(`Python HTTP ${response.status}`);
      const data=await response.json();
      if(serial!==request||target!==host)return;
      if(data.source!=='python-dressing-room'||!Array.isArray(data.members))throw new Error('Unexpected dressing room response');
      model=data;render();
    }catch(error){
      if(serial!==request||target!==host)return;
      model=null;
      target.innerHTML=`<div class="dr-panel dr-error" role="status"><h3>Dressing room unavailable</h3><p>${esc(error.message)}. Your squad has not been changed.</p><button type="button" data-dr-retry>Try again</button></div>`;
      target.querySelector('[data-dr-retry]')?.addEventListener('click',refresh);
    }finally{if(serial===request&&target===host)target.setAttribute('aria-busy','false');}
  }
  function mount(element) {
    host=element;host.innerHTML='<div class="dr-panel dr-loading" role="status">Reading the current dressing room...</div>';
    refresh();
  }
  window.FMDressingRoom=Object.freeze({mount,refresh});
})();
