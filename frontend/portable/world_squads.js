/* TS-21.1: native browser JavaScript. No build step, npm or Node runtime. */
window.FMWorldSquads = (() => {
  'use strict';
  const esc = value => String(value ?? '').replace(/[&<>"']/g, c =>
    ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const remembered = new Map();
  const shownClub=(id,name)=>window.FMClubIdentity?.resolve?.(id,name)?.display_name||name||id||'Club';
  async function get(url, signal) {
    const response = await fetch(url, {cache:'no-store', signal});
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || `HTTP ${response.status}`);
    return data;
  }
  function tacticDetail(tactic, heading) {
    return `<details class="ws-tactic"><summary>${esc(heading)}: ${esc(tactic.formation)}
      <span>${esc(tactic.style)}</span></summary>
      <div class="ws-role-grid">${tactic.slots.map(s => `<div><b>${esc(s.position)}</b><span>${esc(s.role)}</span></div>`).join('')}</div>
      <div class="ws-instructions">${tactic.instructions.map(g => `<details><summary>${esc(g.name)}</summary>
        <dl>${g.rows.map(r => `<dt>${esc(r.name)}</dt><dd>${esc(r.value)}</dd>`).join('')}</dl></details>`).join('')}</div></details>`;
  }
  function detail(data) {
    return `<div class="ws-summary"><h3><button type="button" class="ts22-club-link" data-club-id="${esc(data.club_id)}">${esc(shownClub(data.club_id,data.name))}</button></h3><span>${data.count} players</span>
      <span>Tier ${data.tier}</span><span>XI OVR in role: ${esc(data.mean_xi_ovr ?? '-')}</span>
      <span>${data.coverage.complete?'Two complete XIs covered':'Coverage needs attention'}</span>
      ${data.squad_planning?`<span>Squad planning: XI ${data.squad_planning.starters_covered}/11 · Backups ${data.squad_planning.backups_covered}/11 · Third GK ${data.squad_planning.third_keeper_covered?'yes':'needed'}</span>`:''}</div>
      ${data.warning?`<p role="status">${esc(data.warning)}</p>`:''}
      ${tacticDetail(data.primary,'Primary plan')}${tacticDetail(data.alternative,'Alternative plan')}
      <div class="ws-table-scroll"><table class="ws-table"><thead><tr><th>Player</th><th>Age</th><th>Position</th>
        <th>Other positions</th><th>Role</th><th>OVR</th><th>Apps</th><th>Minutes</th><th>Goals</th></tr></thead>
      <tbody>${data.players.map(p => `<tr><td><details><summary>${esc(p.name)} ${p.starter?'<small>XI</small>':''}</summary>
        <div class="ws-player-attributes">${Object.entries(p.attributes).map(([g,values]) => `<h4>${esc(g)}</h4>
          <dl>${Object.entries(values).map(([k,v]) => `<dt>${esc(k.replaceAll('_',' '))}</dt><dd>${v}</dd>`).join('')}</dl>`).join('')}</div>
        </details></td><td>${p.age}</td><td>${esc(p.position)}</td><td>${esc(p.secondary_positions.join(', ') || '-')}</td>
        <td>${esc(p.role)}</td><td><b>${p.ovr.toFixed(1)}</b></td><td>${p.appearances}</td><td>${p.minutes}</td><td>${p.goals}</td></tr>`).join('')}</tbody></table></div>
      <p class="ws-note">OVR is evaluated in the displayed position and role, using the existing rating rules.
      XI is the current selection for your club; for other clubs it is a strongest-available reference, not a confirmed next-match lineup.
      Only committed match appearances are counted; tracking starts ${esc(data.tracked_from)}.
      Attribute development, aging and Newgens are not enabled in this foundation update.</p>`;
  }
  async function mount(root, competitionId) {
    const controller = new AbortController();
    let serial = 0;
    root.innerHTML = '<h2>Club squads &amp; tactical identities</h2><p role="status">Loading persistent squads...</p>';
    try {
      const index = await get('/api/world-squads', controller.signal);
      if (!root.isConnected) return;
      const league = index.leagues.find(l => l.id === competitionId);
      if (!league) {root.remove(); return;}
      let selected = remembered.get(competitionId);
      if (!league.clubs.some(c => c.id === selected)) selected = league.clubs[0]?.id;
      root.innerHTML = `<div class="ws-header"><div><h2>Club squads &amp; tactical identities</h2>
        <p>${index.club_count} persistent clubs / ${index.player_count} players across England</p></div>
        <label>Inspect club<select data-ws-club aria-label="Inspect club squad">${league.clubs.map(c =>
          `<option value="${esc(c.id)}" ${c.id===selected?'selected':''}>${esc(shownClub(c.id,c.name))} (${c.count})</option>`).join('')}</select></label></div>
        <div data-ws-detail aria-live="polite"></div>`;
      const target = root.querySelector('[data-ws-detail]');
      async function load(id) {
        const request = ++serial;
        remembered.set(competitionId,id);
        target.innerHTML = '<p role="status">Loading club...</p>';
        try {
          const data = await get('/api/world-squads/' + encodeURIComponent(id), controller.signal);
          if (request !== serial || !root.isConnected) return;
          target.innerHTML = detail(data);
        } catch (error) {
          if (request !== serial || !root.isConnected) return;
          target.innerHTML = `<p role="alert">${esc(error.message)}</p><button type="button" data-ws-retry>Retry</button>`;
          target.querySelector('[data-ws-retry]').addEventListener('click', () => load(id));
        }
      }
      root.querySelector('[data-ws-club]').addEventListener('change', event => load(event.target.value));
      if (selected) await load(selected);
    } catch (error) {
      if (!root.isConnected) return;
      root.innerHTML = `<h2>Club squads</h2><p role="alert">${esc(error.message)}</p>
        <button type="button" data-ws-retry>Retry</button>`;
      root.querySelector('[data-ws-retry]').addEventListener('click', () => mount(root, competitionId));
    }
  }
  return {mount};
})();
