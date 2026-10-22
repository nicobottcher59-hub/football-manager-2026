/* TS-UI-02.2 — Real split-view squad UI, powered exclusively by the existing Python read model.
 * The original roster view stays available beneath this presentation layer for compatibility.
 * No simulation rules, player abilities or transfer contracts are derived in the browser.
 */
(() => {
  'use strict';
  const original = window.FMRoster;
  if (!original) throw new Error('Load roster.js before squad_ui02.js');
  const state = original.state;
  const view = { tab:'profile', order:'position', query:'', rendered:false, data:null, identities:{}, images:{}, positionFocus:{}, stamp:0 };
  const $ = selector => document.querySelector(selector);
  const html = x => String(x ?? '').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const numeric = n => n !== '' && n != null && Number.isFinite(Number(n));
  const one = n => numeric(n) ? Number(n).toFixed(1) : '—';
  const integer = n => numeric(n) ? Math.round(Number(n)).toLocaleString('en-GB') : '—';
  const pct = n => numeric(n) ? `${one(n)}%` : '—';
  const clamp = n => Math.max(0,Math.min(100,Number(n)||0));
  const compact = n => numeric(n) ? new Intl.NumberFormat('en-GB',{notation:'compact',maximumFractionDigits:1}).format(n) : '—';
  const nice = value => String(value||'').replaceAll('_',' ').replace(/\b\w/g,c=>c.toUpperCase());
  const POS_ORDER = ['GK','RB','RCB','CB','LCB','LB','RWB','LWB','RM','RDM','DM','CDM','LDM','RCM','CM','LCM','LM','RAM','AM','CAM','LAM','RW','RF','SS','LW','LF','CF','ST'];
  const statKeys = [
    ['appearances','Appearances'],['starts','Starts'],['minutes','Minutes'],['goals','Goals'],
    ['assists','Assists'],['clean_sheets','Clean sheets'],['shots','Shots'],['shots_on_target','Shots on target'],
    ['xg','xG'],['pass_completion','Pass completion'],['yellow_cards','Yellow cards'],
    ['red_cards','Red cards'],['average_match_rating','Average rating']
  ];
  const transferLabels = {normal:'Available',transfer_listed:'Transfer listed',loan_listed:'Loan listed',untouchable:'Untouchable'};
  const safeAsset = s => typeof s==='string' && /^assets\/[a-zA-Z0-9_/-]+\.(?:png|jpg|jpeg|webp)$/.test(s);
  const safeColor = s => typeof s==='string' && /^#[0-9A-Fa-f]{6}$/.test(s);
  const avatar = (player, big=false) => {
    const fallback=window.FMPortraits?.portrait(player,big?'s2-avatar-art s2-avatar-large':'s2-avatar-art') || '<span class="s2-avatar-art">♟</span>';
    const photo=window.FMEntityAssets?.getPhoto?.(player.id) ? null : view.images[player.id];
    return `<span class="s2-avatar ${big?'s2-big':''}" data-player-image-key="${html(player.id)}">${fallback}${safeAsset(photo)?`<img class="s2-real-photo" src="${html(photo)}" alt="" loading="lazy">`:''}</span>`;
  };
  const nation = p => window.FMPortraits?.nation(p.nationality) || html(p.nationality||'Unrecorded');
  // The only captain badge is the effective on-field captain from Python's
  // verified set-piece/lineup read model. Never guess from a player's name or OVR.
  function isCurrentCaptain(player,data){
    const captain=data?.set_pieces?.roles?.find(entry=>entry.role==='captain');
    return !!captain?.effective_id && captain.effective_id===player.id;
  }
  function captainBadge(player,data,hero=false){
    return isCurrentCaptain(player,data)
      ? `<span class="s25-captain ${hero?'hero':''}" title="Captain of the current XI" aria-label="Captain of the current XI">C</span>`
      : '';
  }
  const badge = v => v == null?'—':`<span class="s2-score ${Number(v)>=85?'s2-score-excellent':Number(v)>=75?'s2-score-good':Number(v)>=60?'s2-score-medium':'s2-score-low'}">${one(v)}</span>`;
  const measurement = (value,unit='') => {
    if(value==null||value==='') return '—';
    if(typeof value==='number'&&Number.isFinite(value)) return `${integer(value)}${unit?` ${unit}`:''}`;
    const raw=String(value).trim();
    return raw?html(raw):'—';
  };
  const bodyMetric = (label,value,unit='') => `<span class="s29-body-metric"><small>${html(label)}</small><strong>${measurement(value,unit)}</strong></span>`;
  const footBadge = (side,active) => {
    const short=side==='left'?'L':'R';
    const label=side==='left'?'Left foot':'Right foot';
    return `<span class="s29-foot ${side} ${active?'is-active':'is-inactive'}" aria-label="${label}${active?' (preferred)':''}"><span class="s29-foot-icon" aria-hidden="true">👟</span><b>${short}</b></span>`;
  };
  const footSwitcher = p => {
    const preferred=String(p.foot||'').toLowerCase();
    return `<span class="s29-foot-meta"><small>Foot</small><span class="s29-foot-switch" role="img" aria-label="Preferred foot: ${preferred==='left'?'left':preferred==='right'?'right':'unrecorded'}">${footBadge('left',preferred==='left')}${footBadge('right',preferred==='right')}</span></span>`;
  };
  const bar = (label,value,type='neutral') => `<div class="s2-measure"><div class="s2-measure-label"><span>${html(label)}</span><strong>${pct(value)}</strong></div><div class="s2-track"><span class="s2-fill ${type}" style="width:${clamp(value)}%"></span></div></div>`;
  const fact = (label,val,sub='') => `<div class="s2-fact"><span>${html(label)}</span><strong>${val}</strong>${sub?`<small>${html(sub)}</small>`:''}</div>`;
  const date = str => {const m=/^(\d{4})-(\d{2})-(\d{2})$/.exec(String(str||''));return m?`${Number(m[3])} ${['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'][Number(m[2])-1]||m[2]} ${m[1]}`:'—';};
  const notice = text => `<p class="s2-muted s2-info"><span aria-hidden="true">ⓘ</span> ${html(text)}</p>`;
  // Keep Squad's already-loaded catalogue as a safety net while the shared
  // resolver starts inside an iframe. Imported, ID-keyed assets always win.
  const squadIdentity=(id,name)=>({
    ...(window.FMClubIdentity?.resolve?.(id,name)||{}),
    ...(view.identities[id]||{}),
    ...(window.FMEntityAssets?.getClub?.(id)||{})
  });
  function clubTheme(data) {
    const id=data.club_id;
    const entry=squadIdentity(id,data.club);
    const primary=safeColor(entry.primary_color)?entry.primary_color:'#1487d8';
    const accent=safeColor(entry.accent_color)?entry.accent_color:'#d5ad70';
    const root=document.documentElement;
    root.style.setProperty('--s2-club-primary',primary);
    root.style.setProperty('--s2-club-accent',accent);
    root.style.setProperty('--s2-club-rgb',[1,3,5].map(x=>parseInt(primary.slice(x,x+2),16)).join(','));
    root.style.setProperty('--s2-club-secondary',safeColor(entry.secondary_color)?entry.secondary_color:'#f2f6fc');
    root.dataset.squadClubId=String(id||'');
    const crest=safeAsset(entry.crest)?`/portable/${entry.crest}`:null;
    const banner=safeAsset(entry.hero_image)?`/portable/${entry.hero_image}`:null;
    return {name:entry.display_name||data.club, crest, banner};
  }
  function useClubArt(data){
    const cfg=clubTheme(data);
    const crest=cfg.crest?`<img src="${html(cfg.crest)}" alt="">`:'<span aria-hidden="true">⚽</span>';
    return `<div class="s2-club-crest" aria-label="${html(cfg.name)}">${crest}</div>`;
  }
  function allPlayers(data){
    const query=view.query.toLocaleLowerCase().trim();
    const entries=data.roster.filter(p=>!query || `${p.name} ${p.primary_position} ${p.nationality}`.toLocaleLowerCase().includes(query));
    return entries.sort((a,b)=>{
      if(view.order==='grl')return (Number(b.act)||0)-(Number(a.act)||0)||String(a.name).localeCompare(b.name);
      if(view.order==='name')return String(a.name).localeCompare(String(b.name));
      if(view.order==='condition')return (numeric(b.condition)?Number(b.condition):-1)-(numeric(a.condition)?Number(a.condition):-1)||String(a.name).localeCompare(String(b.name));
      const ia=POS_ORDER.indexOf(String(a.primary_position||'')),ib=POS_ORDER.indexOf(String(b.primary_position||''));
      return (ia<0?99:ia)-(ib<0?99:ib)||(Number(b.act)||0)-(Number(a.act)||0)||String(a.name).localeCompare(b.name);
    });
  }
  // The row selects a footballer. Only the separate arrow button navigates
  // to the career profile, avoiding the competing name/row click targets.
  // Selecting the card updates Squad; only the ↗ button opens career history.
  // TS-UI-02.6: the squad directory is a selection list, not a spreadsheet.
  // Secondary buttons explicitly open the full profile; row/name select locally.
  // TS-UI-02.7: the directory uses one compact, accessible player card.
  // Dorsal and captain appear only when recorded by the career model.
  // TS-UI-02.8: clean, player-data-driven player cards. No legacy layout classes.
  // TS-UI-02.10: a three-zone card gives recorded facts a clear hierarchy.
  // Selection, profile navigation and effective-XI captain remain unchanged.
  function rosterRow(p,data){
    const selected=p.id===state.expanded;
    const mood=numeric(p.morale)?Number(p.morale):null;
    const moodText=mood==null?'Morale not recorded':mood>=75?'Good morale':mood>=55?'Stable morale':'Low morale';
    const moodClass=mood==null?'unknown':mood>=75?'positive':mood>=55?'neutral':'negative';
    const mouth=mood==null?'M7 15h10':mood>=75?'M7 13q5 6 10 0':mood>=55?'M7 15h10':'M7 17q5 -5 10 0';
    const moodSvg=`<svg viewBox="0 0 24 24" aria-hidden="true" focusable="false"><circle cx="12" cy="12" r="10" fill="currentColor"/><circle cx="8.4" cy="9.5" r="1.15" fill="#063044"/><circle cx="15.6" cy="9.5" r="1.15" fill="#063044"/><path d="${mouth}" fill="none" stroke="#063044" stroke-width="1.7" stroke-linecap="round"/></svg>`;
    const fitness=numeric(p.condition)?`${integer(p.condition)}%`:'—';
    const conditionTrack=numeric(p.condition)?`<i style="--s28-progress:${clamp(p.condition)}%" class="${Number(p.condition)<70?'warning':''}"></i>`:'';
    const number=p.number==null?'<span class="s28-jersey-unassigned" title="Shirt number not assigned">—</span>':`<span class="s28-jersey-number" title="Shirt number ${html(p.number)}">${html(p.number)}</span>`;
    const form=numeric(p.form)?`<span class="s210-form" title="Recorded form ${one(p.form)} out of 100"><small>FORM</small><strong>${integer(p.form)}</strong></span>`:'';
    return `<div class="s29-player-card s28-player-card s2-roster-row s210-player-card ${selected?'selected':''} ${p.available?'':'is-unavailable'}" role="row" tabindex="0" aria-selected="${selected}" data-s2-row="${html(p.id)}" data-roster-expand="${html(p.id)}" aria-label="Select ${html(p.name)}">
      <div class="s28-row-face s210-portrait" role="cell">${avatar(p)}<span class="s210-shirt-number">${number}</span><span class="s28-face-glow" aria-hidden="true"></span></div>
      <div class="s28-row-identity s210-identity" role="cell"><div class="s28-row-title s210-name-line"><strong title="${html(p.name)}">${html(p.name)}</strong>${captainBadge(p,data)}<button type="button" class="s28-profile-link" data-open-career-player="${html(p.id)}" title="Open full profile of ${html(p.name)}" aria-label="Open full profile of ${html(p.name)}">↗</button></div>
        <div class="s28-row-meta s210-meta-line"><span class="s28-row-pos">${html(p.primary_position||'—')}</span><span class="s210-age">${html(p.age??'—')} yrs</span><span class="s28-row-nation">${nation(p)}</span></div>
        <div class="s210-vitals"><span class="s28-row-condition s210-condition" title="Condition ${fitness}"><small>FIT</small><span class="s28-track">${conditionTrack}</span><span class="s28-condition-value">${fitness}</span></span>
          <span class="s28-morale s210-morale ${moodClass}" title="${html(moodText)}${mood==null?'':` · ${one(p.morale)} / 100`}" aria-label="${html(moodText)}" >${moodSvg}<span class="s210-morale-value">${mood==null?'—':integer(p.morale)}</span></span>${form}</div></div>
      <div class="s28-row-overall s210-rating" role="cell"><small>GRL</small>${badge(p.act)}<span class="s28-row-arrow" aria-hidden="true">›</span></div>
    </div>`;
  }
  function rosterContents(data){
    const list=allPlayers(data);
    return list.map(p=>rosterRow(p,data)).join('')||'<div class="s2-no-matches">No matching players.</div>';
  }
  function roster(data){
    const available=data.roster.filter(p=>p.available).length;
    const sortChoices=[['position','Position'],['grl','GRL'],['condition','Condition'],['name','Name']];
    return `<section class="s29-directory s28-directory s210-directory" aria-label="Squad player list">
      <header class="s29-directory-head s28-directory-head s210-head"><div class="s28-directory-title s210-headline"><span class="s28-kicker">FIRST TEAM · SQUAD DIRECTORY</span>
        <div class="s210-heading"><h2>Players <span class="s28-count">${data.roster.length}</span></h2><span class="s210-available"><i aria-hidden="true"></i>${available} AVAILABLE</span></div></div>
        <div class="s29-tools s28-tools s210-tools"><label class="s28-search"><svg aria-hidden="true" viewBox="0 0 24 24"><circle cx="10.5" cy="10.5" r="6"/><path d="m15 15 5 5"/></svg><input type="search" data-s2-search aria-label="Search players" placeholder="Search players or positions…" value="${html(view.query)}" autocomplete="off"></label>
          <label class="s28-sort"><span class="sr-only">Sort players</span><select data-s2-sort aria-label="Sort players">${sortChoices.map(([key,label])=>`<option value="${key}" ${key===view.order?'selected':''}>Sort: ${label}</option>`).join('')}</select></label></div></header>
      <div class="s29-list-scroll s28-list-scroll s2-list-scroll" role="table" aria-label="Squad players">${rosterContents(data)}</div>
      <footer class="s28-directory-footer s210-footer"><span data-s25-list-count>${allPlayers(data).length} players in your first team</span><span aria-label="Scroll the squad directory">SCROLL ↕</span></footer>
      <span class="s28-screen-reader" aria-label="${available} players available">${available} available</span>
    </section>`;
  }
  // A stylized kit is presentation-only. The badge/number/photo are loaded
  // from player and club identities, never tied to a specific club or fabricated IDs.
  function kitGraphic(p,data,illustrated=false){
    const identity=squadIdentity(data.club_id,data.club);
    if(!illustrated && safeAsset(identity.kit_image))return `<img class="s2-shirt-image" src="/portable/${html(identity.kit_image)}" alt="" loading="lazy">`;
    const stripes=identity.kit_style==='vertical_stripes';
    return `<svg class="s2-shirt-art" viewBox="0 0 130 146" aria-hidden="true" focusable="false">
      <defs><linearGradient id="s2-shirt-grad" x1="0" y1="0" x2="1" y2="1"><stop stop-color="#ffffff" stop-opacity=".97"/><stop offset=".58" stop-color="#e5ebf2"/><stop offset="1" stop-color="#bdc8d2"/></linearGradient><clipPath id="s2-shirt-mask"><path d="M40 9h50l25 18 12 29-26 14-12-19v83H41V51L29 70 3 56l12-29Z"/></clipPath></defs>
      <path d="M40 9h50l25 18 12 29-26 14-12-19v83H41V51L29 70 3 56l12-29Z" fill="url(#s2-shirt-grad)" stroke="#e8f3ff" stroke-opacity=".45" stroke-width="2"/>
      <g clip-path="url(#s2-shirt-mask)" fill="var(--s2-club-primary)">${stripes?'<path d="M43 8h12v135H43zM66 8h12v135H66zM89 8h12v135H89z" opacity=".9"/>':'<path d="M0 0h130v146H0z" opacity=".9"/>'}</g>
      <path d="M51 9Q65 29 79 9" fill="none" stroke="#12263d" stroke-width="5"/>
      <text x="65" y="71" text-anchor="middle" fill="#ffffff" stroke="#061322" stroke-width=".5" font-size="9" font-weight="800" textLength="68" lengthAdjust="spacingAndGlyphs">${html((p.name||'').split(' ').slice(-1)[0].toUpperCase())}</text>
      ${p.number!=null?`<text x="65" y="112" text-anchor="middle" fill="#ffffff" stroke="#071a2a" stroke-width="1" paint-order="stroke" font-size="41" font-weight="900">${html(p.number)}</text>`:''}
    </svg>`;
  }
  function playerHeader(p,data){
    const availability=p.injury?'Injured':Number(p.suspension)>0?'Suspended':p.available?'Available':'Unavailable';
    const identity=squadIdentity(data.club_id,data.club);
    const crest=safeAsset(identity.crest)?'':`<span class="s28-crest-fallback" aria-hidden="true">✦</span>`;
    const watermarkStyle=safeAsset(identity.crest)?`style="--s28-watermark:url('/portable/${html(identity.crest)}')"`:'';
    const delta=numeric(p.act)&&numeric(p.base_ovr)?Number(p.act)-Number(p.base_ovr):null;
    const ratingDelta=delta!==null&&Math.abs(delta)>=.05?`<span class="s28-rating-delta ${delta<0?'negative':''}" title="Contextual rating difference; not a permanent ability change">${delta>0?'+':''}${delta.toFixed(1)}</span>`:'';
    return `<header class="s29-hero s28-hero" data-selected-player="${html(p.id)}">
      <div class="s29-portrait s28-portrait"><div class="s28-portrait-frame">${avatar(p,true)}${captainBadge(p,data,true)}</div></div>
      <div class="s29-bio s28-bio"><span class="s28-eyebrow">${html(p.primary_position||'—')} · FIRST TEAM</span><h2 class="s28-player-name">${html(p.name)}</h2>
        <div class="s28-player-data">${nation(p)}<span>${html(p.age??'—')} years old</span>${bodyMetric('Height',p.height_cm??p.height,'cm')}${bodyMetric('Weight',p.weight_kg??p.weight,'kg')}${footSwitcher(p)}</div>
        <div class="s28-badges"><span class="s28-primary-pos">${html(p.primary_position||'—')}</span>${(p.secondary_positions||[]).slice(0,3).map(pos=>`<span class="s28-secondary-pos">${html(pos)}</span>`).join('')}<span class="s28-availability ${p.available?'ready':'alert'}">${html(availability)}</span></div>
        <button type="button" class="s28-full-profile" data-open-career-player="${html(p.id)}" aria-label="Open complete profile of ${html(p.name)}">Full player profile <span aria-hidden="true">→</span></button>
      </div>
      <div class="s29-kit-stage s28-kit-stage" aria-label="Club home shirt"><div class="s29-crest-silhouette" aria-hidden="true" ${safeAsset(identity.crest)?`style="--s29-crest:url('/portable/${html(identity.crest)}')"`:''}></div><div class="s28-crest-watermark ${safeAsset(identity.crest)?'has-crest':'no-crest'}" ${watermarkStyle}>${crest}</div><div class="s29-kit-holder s28-kit-holder">${kitGraphic(p,data)}</div></div>
      <div class="s29-metrics s28-metrics"><div class="s28-dorsal-metric"><small>SQUAD NUMBER</small><strong class="${p.number==null?'unassigned':''}">${p.number==null?'—':html(p.number)}</strong></div><div class="s28-current-metric"><small>CURRENT GRL</small>${badge(p.act)}${ratingDelta}</div><div class="s28-base-metric"><small>BASE OVR</small>${badge(p.base_ovr)}</div></div>
    </header>`;
  }
  const pitchPoints={GK:[50,85],RB:[78,69],RCB:[62,72],CB:[50,72],LCB:[38,72],LB:[22,69],RWB:[84,59],LWB:[16,59],DM:[50,59],CDM:[50,59],RDM:[63,58],LDM:[37,58],CM:[50,47],RCM:[63,45],LCM:[37,45],RM:[82,44],LM:[18,44],AM:[50,34],CAM:[50,34],RAM:[65,33],LAM:[35,33],RW:[83,24],LW:[17,24],RF:[68,20],LF:[32,20],CF:[50,18],ST:[50,14],SS:[50,25]};
  // The pitch is a positional diagram, not a second tactics editor.
  // Coordinates are visual only; familiarities and position codes are from Python.
  function knownPositions(p){
    const codes=[p.primary_position,...(p.secondary_positions||[]),...(p.familiarities||[]).map(f=>f.position)];
    return [...new Set(codes.filter(Boolean))];
  }
  function focusedPosition(p){
    const known=knownPositions(p);
    const chosen=view.positionFocus[p.id];
    return known.includes(chosen)?chosen:known[0]||'';
  }
  function positionMap(p){
    const positions=knownPositions(p), selected=focusedPosition(p);
    const dots=positions.map((pos,i)=>{
      const [x,y]=pitchPoints[pos]||[50,50];
      const isPrimary=pos===p.primary_position;
      return `<button type="button" data-s2-focus-position="${html(pos)}" class="s2-pos-dot s24-pitch-dot ${isPrimary?'primary':'secondary'} ${pos===selected?'is-active':''}" style="--s24-px:${x}%;--s24-py:${y}%" aria-pressed="${pos===selected}" title="Inspect ${html(pos)}" aria-label="Highlight position ${html(pos)}"><span>${isPrimary?html(pos):''}</span></button>`;
    }).join('');
    return `<div class="s2-pos-pitch s24-pitch" role="group" aria-label="Recorded player positions. Select a dot to highlight its familiarity">
      <svg class="s24-pitch-lines" viewBox="0 0 210 320" aria-hidden="true" preserveAspectRatio="none">
        <defs><linearGradient id="s24-grass" x1="0" y1="0" x2="1" y2="1"><stop stop-color="#0a6b50"/><stop offset=".54" stop-color="#0d493d"/><stop offset="1" stop-color="#07382f"/></linearGradient></defs>
        <rect width="210" height="320" fill="url(#s24-grass)"/>
        <path d="M0 53h210M0 107h210M0 160h210M0 213h210M0 267h210" stroke="#b4f7ce" opacity=".055" stroke-width="50"/>
        <g fill="none" stroke="#c9f3df" stroke-opacity=".46" stroke-width="1.4"><rect x="10" y="11" width="190" height="298" rx="1"/><path d="M10 160h190"/><circle cx="105" cy="160" r="32"/><circle cx="105" cy="160" r="2" fill="#c9f3df"/><path d="M59 11v42h92V11M59 309v-42h92v42M82 11v13h46V11M82 309v-13h46v13"/><path d="M74 53a38 38 0 0 0 62 0M74 267a38 38 0 0 1 62 0"/></g>
      </svg>${dots}<div class="s24-pitch-caption"><span>SELECTED POSITION</span><strong data-s24-pitch-label>${html(selected)}</strong></div></div>`;
  }
  function groupedAttributes(p){
    const groups=['technical','mental','physical','goalkeeping'];
    const actual=Object.keys(p.attributes||{});
    return [...groups.filter(g=>actual.includes(g)),...actual.filter(g=>!groups.includes(g))]
      .map(group=>({group,entries:Object.entries(p.attributes?.[group]||{})
        .filter(([,value])=>typeof value==='number'&&Number.isFinite(value))
        .sort(([a],[b])=>a.localeCompare(b))}))
      .filter(group=>group.entries.length);
  }
  function profileTab(p,data){
    const known=knownPositions(p),selected=focusedPosition(p),familiarities=p.familiarities||[];
    const rows=known.map(pos=>{
      const f=familiarities.find(item=>item.position===pos);
      const value=f?.effective;
      const label=pos===p.primary_position?'Primary':p.secondary_positions?.includes(pos)?'Secondary':'Learned';
      return `<button type="button" class="s24-position-row ${pos===selected?'is-active':''}" data-s2-focus-position="${html(pos)}" aria-pressed="${pos===selected}" aria-label="Highlight ${html(pos)} familiarity"><span class="s24-position-row-head"><strong>${html(pos)}</strong><span>${label}</span><b>${numeric(value)?one(value):'—'}</b></span><span class="s24-familiarity-track"><i style="--s2-width:${clamp(value)}%"></i></span></button>`;
    }).join('');
    const groups=groupedAttributes(p);
    const attributes=groups.map(({group,entries})=>`<section class="s24-attribute-group"><h4>${html(nice(group))}<span>${entries.length}</span></h4><div class="s24-attribute-rows">${entries.map(([key,value])=>{
      const strength=value>=80?'high':value>=65?'good':value>=45?'medium':'low';
      return `<div class="s24-attribute-row" title="${html(nice(key))}: ${one(value)} / 100"><span class="s24-attribute-label">${html(nice(key))}</span><span class="s24-attribute-meter"><i class="${strength}" style="--s2-width:${clamp(value)}%"></i></span><strong class="${strength}">${one(value)}</strong></div>`;
    }).join('')}</div></section>`).join('');
    return `<div class="s2-two-cards s2-profile-top s24-profile-top ${known.length===1?'s27-single-position':''}">
      <section class="s2-card s2-positions-card s24-positions-card"><h3><span class="s2-card-icon">◈</span> Positions & familiarity</h3><div class="s2-positions-layout s24-positions-layout">${positionMap(p)}<div class="s2-pos-familiarities s24-familiarities">${rows||'<span class="s24-empty">No positions recorded.</span>'}</div></div></section>
      <section class="s2-card s2-charts s24-comparison-card"><h3><span class="s2-card-icon">⬡</span> Role comparison <span class="s24-help" tabindex="0" title="Player: actual attributes, scale 0–100. Role emphasis: normalized weights from the selected engine role; not minimum skill thresholds or potential.">i</span></h3><div class="s2-graphics" data-player-graphics="${html(p.id)}" data-graphics-mode="comparison"><div class="s24-chart-loading">Loading comparison…</div></div></section>
    </div><section class="s2-card s2-attributes-card s24-attributes-card"><div class="s24-card-heading"><h3><span class="s2-card-icon">✧</span> Player attributes</h3><span class="s24-count">${groups.reduce((n,g)=>n+g.entries.length,0)} attributes</span></div><div class="s2-attributes-list s24-attribute-groups">${attributes||'<span class="s24-empty">No attributes recorded.</span>'}</div></section>`;
  }
  // TS-UI-02.14: symmetrical season overview using *only* supported recorded statistics.
  // Unavailable statistics remain unknown; no inferred trend or fabricated match events.
  function seasonTab(p,data){
    const opt=data.statistics||{};
    const season=state.season||data.stats_selection?.season||opt.current_season||'';
    const comp=state.competition||'all';
    const selectedComp=opt.competitions?.find(c=>c.id===comp)?.name||'All competitions';
    const seasons=(opt.seasons||[]).length?opt.seasons:[season];
    const comps=opt.competitions||[];
    const eligible=opt.club_competitions?.[season];
    const relevant=Array.isArray(eligible)?comps.filter(c=>eligible.includes(c.id)):comps;
    const options=relevant.some(c=>c.id===comp)?relevant:comp==='all'?relevant:[...relevant,...comps.filter(c=>c.id===comp)];
    const stats=p.season_stats||{},coverage=stats.coverage||{};
    const supported=new Set(opt.supported||[]);
    const stat=(key,style='integer')=>{
      if(!supported.has(key)||!numeric(stats[key]))return '—';
      return style==='percent'?`${one(stats[key])}%`:style==='decimal'?one(stats[key]):integer(stats[key]);
    };
    const kpis=[
      ['appearances','Apps','◈','appearances'],['starts','Starts','▶','starts'],
      ['minutes','Minutes','◷','minutes'],['goals','Goals','⚽','goals'],
      ['assists','Assists','↗','assists'],['average_match_rating','Avg. rating','★','rating']
    ];
    const section=(name,kind,icon,spotlight,spotKey,spotFmt,rows,detail)=>`<section class="s214-season-group s214-${kind}" aria-label="${html(name)}">
      <header><span class="s214-group-icon" aria-hidden="true">${icon}</span><strong>${html(name)}</strong><span class="s214-group-accent" aria-hidden="true"></span></header>
      <div class="s214-group-spotlight"><div><small>${html(spotlight)}</small><strong>${stat(spotKey,spotFmt)}</strong></div><span class="s214-spotlight-symbol" aria-hidden="true">${icon}</span></div>
      <div class="s214-season-rows">${rows.map(([key,label,fmt])=>`<div><span>${html(label)}</span><strong>${stat(key,fmt)}</strong></div>`).join('')}</div>
      <footer>${html(detail)}</footer>
    </section>`;
    return `<div class="s214-season-dashboard" aria-label="Recorded season statistics">
      <section class="s2-card s2-season-selector s214-season-selector"><div class="s2-season-top"><div><span class="s214-season-eyebrow">CAREER PERFORMANCE</span><h3><span class="s2-card-icon">▤</span> Season performance</h3><p>Verified match statistics · no projections</p></div><div class="s2-season-filters"><label>Season<select data-s2-season aria-label="Statistics season">${seasons.map(s=>`<option value="${html(s)}" ${s===season?'selected':''}>${html(s)}</option>`).join('')}</select></label><label>Competition<select data-s2-competition aria-label="Statistics competition"><option value="all" ${comp==='all'?'selected':''}>All competitions</option>${options.map(c=>`<option value="${html(c.id)}" ${c.id===comp?'selected':''}>${html(c.name)}</option>`).join('')}</select></label></div></div><div class="s214-season-context"><span aria-hidden="true">●</span>${html(season)} <b>·</b> <strong>${html(selectedComp)}</strong></div></section>
      <div class="s214-kpi-grid" aria-label="Season summary">${kpis.map(([key,label,icon,kind])=>`<div class="s214-kpi s214-kpi-${kind}"><span class="s214-kpi-icon" aria-hidden="true">${icon}</span><small>${label}</small><strong>${stat(key,key==='average_match_rating'?'decimal':'integer')}</strong></div>`).join('')}</div>
      <div class="s214-season-groups">
        ${section('Shooting','shooting','◎','Shots','shots','integer', [['shots_on_target','On target'],['xg','Expected goals','decimal'],['goals','Goals scored']],'Finishing · recorded events')}
        ${section('Passing','passing','↗','Completion','pass_completion','percent', [['assists','Assists'],['appearances','Appearances']],'Possession · verified totals')}
        ${section('Defence & discipline','discipline','◇','Clean sheets','clean_sheets','integer', [['yellow_cards','Yellow cards'],['red_cards','Red cards']],'Match conduct · recorded events')}
      </div>
      <section class="s214-season-coverage" aria-label="Data coverage"><div class="s214-coverage-icon" aria-hidden="true">✓</div><div class="s214-coverage-copy"><strong>${coverage.complete_season?'Complete tracked season':'Partial recorded history'}</strong><span>${coverage.complete_season?'All tracked matches this season are included.':'Missing historical match details remain unknown.'}</span></div><div class="s214-coverage-facts"><span>Detailed apps <b>${numeric(coverage.recorded_appearances)?integer(coverage.recorded_appearances):'—'}</b></span><span>Recorded since <b>${html(coverage.from||'—')}</b></span></div><details class="s214-coverage-note"><summary>Coverage definition</summary>${html(opt.clean_sheet_definition||'Match rating differs from current GRL.')}</details></section>
    </div>`;
  }
  // TS-UI-02.12: the other two Squad tabs are compact dashboard layouts.
  // Every displayed metric is taken from the active Python read model.
  function dashboardMetric(label,value,kind='normal'){
    const recorded=numeric(value);
    return `<div class="s212-measure ${kind}"><div class="s212-measure-title"><span>${html(label)}</span><b>${recorded?integer(value)+'%':'—'}</b></div><div class="s212-measure-track" role="meter" aria-label="${html(label)}" aria-valuemin="0" aria-valuemax="100" ${recorded?`aria-valuenow="${clamp(value)}"`:'aria-valuetext="Not recorded"'}><i style="--s212-progress:${recorded?clamp(value):0}%"></i></div></div>`;
  }
  function statusTab(p,data){
    const availability=p.injury?'Injured':Number(p.suspension)>0?'Suspended':p.available?'Available':'Unavailable';
    const morale=numeric(p.morale)?Number(p.morale):null;
    const mood=morale==null?'Unrecorded':morale>=75?'Good':morale>=55?'Stable':'Low';
    const moodTone=morale==null?'unknown':morale>=75?'positive':morale>=55?'stable':'low';
    const fitness=numeric(p.condition)?`${integer(p.condition)}%`:'—';
    const form=numeric(p.form)?one(p.form):'—';
    const moodPercent=morale==null?'—':`${integer(morale)}%`;
    const moodMouth=morale==null?'M18 35H32':morale>=75?'M17 30Q25 39 33 30':morale>=55?'M17 34H33':'M17 38Q25 28 33 38';
    const moodGraphic=`<svg viewBox="0 0 50 50" fill="none" aria-hidden="true" focusable="false"><circle cx="25" cy="25" r="18" stroke="currentColor" stroke-width="2" opacity=".9"/><circle cx="19.5" cy="21" r="1.8" fill="currentColor"/><circle cx="30.5" cy="21" r="1.8" fill="currentColor"/><path d="${moodMouth}" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"/></svg>`;
    return `<div class="s212-status-dashboard s213-status-dashboard" aria-label="Player condition and development">
      <div class="s212-status-overview">
        <section class="s212-panel s212-condition-panel s213-performance-tile" aria-label="Physical condition"><div class="s213-tile-art" aria-hidden="true"><span>✚</span></div><h3><span class="s212-panel-icon tone-green" aria-hidden="true">✚</span> Physical condition</h3>
          <div class="s212-condition-content"><div class="s212-ring" style="--s212-progress:${numeric(p.condition)?clamp(p.condition):0}%" role="img" aria-label="Condition: ${fitness}"><div><strong>${fitness}</strong><small>CONDITION</small></div></div>
            <div class="s212-condition-breakdown">${dashboardMetric('Match sharpness',p.sharpness)}${dashboardMetric('Fatigue',p.fatigue,'fatigue')}</div></div>
          <span class="s213-tile-footer"><i aria-hidden="true"></i> Live player condition</span>
        </section>
        <section class="s212-panel s212-form-panel s213-performance-tile"><div class="s213-tile-art" aria-hidden="true"><span>↗</span></div><h3><span class="s212-panel-icon tone-blue" aria-hidden="true">↗</span> Current form</h3>
          <div class="s212-form-content"><strong>${form}</strong><span>/ 100</span><small>Recorded player form</small></div>
          <div class="s212-form-progress" role="meter" aria-label="Form" aria-valuemin="0" aria-valuemax="100" ${numeric(p.form)?`aria-valuenow="${clamp(p.form)}"`:'aria-valuetext="Not recorded"'}><i style="--s212-progress:${numeric(p.form)?clamp(p.form):0}%"></i></div>
          <span class="s213-tile-footer"><i aria-hidden="true"></i> Current performance index</span>
        </section>
        <section class="s212-panel s212-morale-panel s213-performance-tile"><div class="s213-tile-art" aria-hidden="true"><span>♥</span></div><h3><span class="s212-panel-icon tone-amber" aria-hidden="true">♥</span> Morale & status</h3>
          <div class="s212-morale-content ${moodTone}"><span class="s212-morale-face" aria-hidden="true">${moodGraphic}</span><div><strong>${html(mood)} morale</strong><span>${moodPercent} recorded</span></div></div>
          <div class="s213-morale-meter" role="meter" aria-label="Morale" aria-valuemin="0" aria-valuemax="100" ${morale!=null?`aria-valuenow="${clamp(morale)}"`:'aria-valuetext="Not recorded"'}><i style="--s213-morale:${morale==null?0:clamp(morale)}%"></i></div>
          <div class="s212-availability-row"><span class="s212-status-badge ${p.available?'ready':'alert'}">${p.available?'✓':'!'} ${html(availability)}</span><small title="Happiness is separate from morale">${p.happiness==null?'Happiness not recorded':`Happiness: ${html(p.happiness)}`}</small></div>
        </section>
      </div>
      <section class="s212-panel s212-development-card s213-development-card"><div class="s212-development-head"><h3><span class="s212-panel-icon tone-amber" aria-hidden="true">◇</span> Training & development</h3><span class="s212-development-context"><span class="s213-data-light" aria-hidden="true"></span> Verified career reviews</span></div>
        <div class="s2-graphics s212-development-graphics" data-player-graphics="${html(p.id)}" data-graphics-mode="development"><p class="s212-loading">Loading the recorded development review…</p></div>
      </section>
    </div>`;
  }
  // Expires on a recorded date; the bar is decorative, never a fabricated
  // contract completion percentage (contract start dates are not recorded).
  function contractDaysRemaining(end,asOf){
    const iso=/^\d{4}-\d{2}-\d{2}$/;
    if(!iso.test(String(end||''))||!iso.test(String(asOf||'')))return null;
    const a=Date.parse(end+'T00:00:00Z'),b=Date.parse(asOf+'T00:00:00Z');
    if(!Number.isFinite(a)||!Number.isFinite(b))return null;
    return Math.round((a-b)/86400000);
  }
  // Custom dark pickers: no OS-native white popup. Native select remains
  // available for existing action dispatch and automation; no new backend route.
  function managerPicker(id,label,options,current){
    const selected=options.find(([key])=>String(key)===String(current))||options[0];
    return `<div class="s214-picker-field"><span class="s214-picker-label">${html(label)}</span><div class="s214-picker" data-s214-picker>
      <select id="${id}" data-roster-filter="${id}" aria-label="${html(label)}" tabindex="-1" aria-hidden="true" class="s214-native-select">${options.map(([key,text])=>`<option value="${html(key)}" ${String(key)===String(current)?'selected':''}>${html(text)}</option>`).join('')}</select>
      <button type="button" class="s214-picker-trigger" data-s214-picker-toggle aria-label="${html(label)}: ${html(selected[1])}" aria-haspopup="listbox" aria-expanded="false"><span data-s214-picker-label>${html(selected[1])}</span><span class="s214-picker-chevron" aria-hidden="true">⌄</span></button>
      <div class="s214-picker-menu" role="listbox" aria-label="${html(label)}" hidden>${options.map(([key,text])=>`<button type="button" role="option" data-s214-picker-option="${html(key)}" aria-selected="${String(key)===String(current)}">${html(text)}<span aria-hidden="true">✓</span></button>`).join('')}</div>
    </div></div>`;
  }
  function closeManagerPickers(except){
    document.querySelectorAll('[data-s214-picker]').forEach(picker=>{
      if(picker===except)return;
      picker.querySelector('.s214-picker-menu').hidden=true;
      picker.querySelector('[data-s214-picker-toggle]').setAttribute('aria-expanded','false');
    });
  }
  function contractTab(p,data){
    const c=p.contract_details||{};
    const market=p.market_value==null?'—':html(p.market_value);
    const status=c.status==='out_of_contract_retained'?'Expired / retained':p.contract_details?'Registered':'Not recorded';
    const contractIsActive=!!p.contract_details&&c.status!=='out_of_contract_retained';
    const remaining=contractDaysRemaining(c.expires_on,data.date);
    const duration=remaining==null?'End date not recorded':remaining<0?'Contract end date passed':remaining===0?'Expires today':remaining===1?'1 day remaining':`${integer(remaining)} days remaining`;
    const mini=(icon,label,value,sub='')=>`<div class="s212-contract-fact s213-contract-mini"><span class="s212-fact-icon" aria-hidden="true">${icon}</span><div><small>${html(label)}</small><strong>${value}</strong>${sub?`<em>${html(sub)}</em>`:''}</div></div>`;
    return `<div class="s212-management s213-management" aria-label="Contract and actions">
      <div class="s212-contract-overview">
        <section class="s212-panel s212-contract-main s2-contract-card s213-contract-main" title="Unsupported clauses and bonuses are not invented.">
          <div class="s213-contract-title"><h3><span class="s212-panel-icon tone-coral" aria-hidden="true">▤</span> Contract overview</h3><span class="s213-contract-subtitle">${data.readonly?'CLUB RECORD · READ ONLY':'ACTIVE CAREER RECORD'}</span></div>
          <div class="s213-contract-finances"><div class="s213-wage-feature"><span class="s213-feature-symbol" aria-hidden="true">£</span><span class="s213-fact-kicker">WEEKLY WAGE</span><strong>${c.weekly_wage?html(c.weekly_wage):'—'}</strong><small>Per week</small></div>
            <div class="s213-value-feature"><span class="s213-feature-symbol" aria-hidden="true">↗</span><span class="s213-fact-kicker">MARKET VALUATION</span><strong>${market}</strong><small>Estimate · not asking price</small></div></div>
          <div class="s212-contract-grid s213-contract-grid">${mini('▦','Contract expires',html(date(c.expires_on)))}${mini('#','Squad number',p.number==null?'Not assigned':'#'+html(p.number))}</div>
        </section>
        <section class="s212-panel s212-contract-state s213-contract-state ${contractIsActive?'active':'inactive'}"><h3><span class="s212-panel-icon ${contractIsActive?'tone-green':'tone-amber'}" aria-hidden="true">${contractIsActive?'✓':'!'}</span> Contract status</h3>
          <div class="s213-contract-seal" aria-hidden="true"><span>▣</span></div>
          <div class="s212-state-center"><div><strong>${html(status)}</strong><small>${html(duration)}</small></div></div>
          <div class="s213-contract-expiry"><span aria-hidden="true">◷</span> End date: <strong>${html(date(c.expires_on))}</strong></div>
        </section>
      </div>
      <section class="s212-panel s212-actions-panel s2-actions-card s213-actions-panel"><div class="s212-actions-heading"><h3><span class="s212-panel-icon tone-amber" aria-hidden="true">⚙</span> Manager actions</h3><small>${data.readonly?'Rival club · read only':'YOUR SQUAD · ACTIVE CONTROLS'}</small></div>
        ${data.readonly?`<div class="s212-quick-actions s213-quick-actions"><button type="button" data-open-transfer-offer="${html(p.id)}" class="s2-action s212-action s212-primary-action s213-action"><span class="s213-action-symbol" aria-hidden="true">↗</span><span class="s213-action-label">Make transfer offer</span><span class="s213-action-corner" aria-hidden="true">↗</span></button></div>`:
        `<div class="s212-action-controls s213-action-controls s214-action-controls">${managerPicker('rt-player-number','Squad number',[['','Not assigned'],...Array.from({length:99},(_,i)=>[String(i+1),String(i+1)])],p.number==null?'':String(p.number))}
          ${managerPicker('rt-transfer-status','Transfer status',Object.entries(transferLabels),p.transfer_status)}</div>
          <div class="s212-quick-actions s213-quick-actions"><button type="button" data-open-finances class="s2-action s212-action s212-primary-action s213-action"><span class="s213-action-symbol" aria-hidden="true">▤</span><span class="s213-action-label">Contract negotiations</span><span class="s213-action-corner" aria-hidden="true">↗</span></button><button type="button" data-s2-navigate="Dressing Room" class="s2-action s212-action s213-action"><span class="s213-action-symbol" aria-hidden="true">☏</span><span class="s213-action-label">Conversations</span><span class="s213-action-corner" aria-hidden="true">↗</span></button><button type="button" data-s2-navigate="Training" class="s2-action s212-action s213-action"><span class="s213-action-symbol" aria-hidden="true">◎</span><span class="s213-action-label">Training</span><span class="s213-action-corner" aria-hidden="true">↗</span></button><button type="button" data-s2-navigate="Tactics" class="s2-action s212-action s213-action"><span class="s213-action-symbol" aria-hidden="true">⚑</span><span class="s213-action-label">Captain & set pieces</span><span class="s213-action-corner" aria-hidden="true">↗</span></button><button type="button" data-s2-navigate="Medical Centre" class="s2-action s212-action s213-action"><span class="s213-action-symbol" aria-hidden="true">✚</span><span class="s213-action-label">Medical centre</span><span class="s213-action-corner" aria-hidden="true">↗</span></button></div>`}
      </section>
    </div>`;
  }
  function inspector(p,data){
    const tabs=[['profile','Profile / Attributes','◇'],['season','Season statistics','▥'],['status','Status & development','♥'],['management','Contract & actions','▣']];
    const parts={profile:()=>profileTab(p,data),season:()=>seasonTab(p,data),status:()=>statusTab(p,data),management:()=>contractTab(p,data)};
    return `<section class="s2-inspector" aria-label="Selected player details">
      ${playerHeader(p,data)}
      <div class="s2-tabs" role="tablist" aria-label="Player sections">${tabs.map(([key,label,icon])=>`<button type="button" role="tab" data-s2-tab="${key}" class="${view.tab===key?'active':''}" aria-selected="${view.tab===key}" aria-controls="s2-tab-panel"><span class="s2-tab-icon" aria-hidden="true">${icon}</span>${html(label)}</button>`).join('')}</div>
      <div class="s2-detail-scroll" data-s2-active-tab="${view.tab}" id="s2-tab-panel" role="tabpanel" aria-label="${html(tabs.find(([id])=>id===view.tab)?.[1]||'Profile')}" tabindex="0">${(parts[view.tab]||parts.profile)()}</div>
      <footer class="s2-detail-footer"><span class="s2-footer-led" aria-hidden="true"></span><span>LIVE PLAYER DATA</span><button type="button" data-open-career-player="${html(p.id)}">Full player history & profile ↗</button></footer>
    </section>`;
  }
  function render(data){
    if(!data||!Array.isArray(data.roster))return original.render(data);
    view.data=data;view.rendered=true;
    const art=clubTheme(data);
    if(!state.expanded||!data.roster.some(p=>p.id===state.expanded))state.expanded=allPlayers(data)[0]?.id||null;
    const selected=data.roster.find(p=>p.id===state.expanded);
    const avg=data.roster.filter(p=>numeric(p.act)).map(p=>Number(p.act));
    const average=avg.length?avg.reduce((a,b)=>a+b,0)/avg.length:null;
    const hero=art.banner?`style="--s2-banner:url('${html(art.banner)}')"`:'';
    const output=`<div class="s2-shell"><div class="s2-page-header" ${hero}><div class="s2-brand-info">${useClubArt(data)}<div><span class="s2-eyebrow">CLUB SQUAD · FIRST TEAM</span><strong data-s26-club-name>${html(art.name)}</strong><p>Squad hub <span aria-hidden="true">◆</span> ${data.roster.length} registered players</p></div></div><div class="s2-squad-totals"><div><b>${data.roster.length}</b><small>Players</small></div><div><b>${one(average)}</b><small>Average GRL</small></div><div><b>${data.roster.filter(p=>p.available).length}</b><small>Available</small></div></div></div><div class="s2-workspace">${roster(data)}${selected?inspector(selected,data):'<section class="s2-inspector s2-empty">No players registered.</section>'}</div></div>`;
    queueMicrotask(()=>{
      if(view.tab==='profile'||view.tab==='status')window.FMPlayerPresentation?.hydrate(document,data);
      activateLoadedArt();
    });
    return output;
  }
  function showSelectedPlayer(){
    const data=view.data;
    const player=data?.roster?.find(item=>item.id===state.expanded);
    const current=$('.s2-inspector');
    if(!player||!current)return false;
    document.querySelectorAll('.s2-roster-row').forEach(row=>{
      const chosen=row.dataset.s2Row===state.expanded;
      row.classList.toggle('selected',chosen);
      row.setAttribute('aria-selected',String(chosen));
    });
    const holder=document.createElement('div');
    holder.innerHTML=inspector(player,data);
    current.replaceWith(holder.firstElementChild);
    activateLoadedArt();
    if(view.tab==='profile'||view.tab==='status')window.FMPlayerPresentation?.hydrate(document,data);
    return true;
  }
  function switchInspectorTab(tab){
    if(!['profile','season','status','management'].includes(tab))return false;
    if(tab===view.tab)return true;
    const data=view.data,player=data?.roster?.find(item=>item.id===state.expanded);
    const panel=$('.s2-detail-scroll'),tablist=$('.s2-tabs');
    if(!player||!panel||!tablist)return false;
    const parts={profile:profileTab,season:seasonTab,status:statusTab,management:contractTab};
    view.tab=tab;
    tablist.querySelectorAll('[data-s2-tab]').forEach(button=>{
      const active=button.dataset.s2Tab===tab;
      button.classList.toggle('active',active);
      button.setAttribute('aria-selected',String(active));
      button.setAttribute('tabindex',active?'0':'-1');
    });
    panel.dataset.s2ActiveTab=tab;
    panel.setAttribute('aria-label',tablist.querySelector(`[data-s2-tab="${tab}"]`)?.textContent.trim()||tab);
    panel.innerHTML=`<div class="s24-tab-content">${parts[tab](player,data)}</div>`;
    panel.scrollTop=0;
    if(tab==='profile'||tab==='status')window.FMPlayerPresentation?.hydrate(document,data);
    return true;
  }
  function focusPosition(pos){
    const player=view.data?.roster?.find(item=>item.id===state.expanded);
    if(!player||!knownPositions(player).includes(pos))return true;
    view.positionFocus[player.id]=pos;
    document.querySelectorAll('[data-s2-focus-position]').forEach(el=>{
      const active=el.dataset.s2FocusPosition===pos;
      el.classList.toggle('is-active',active);
      el.setAttribute('aria-pressed',String(active));
    });
    const label=$('[data-s24-pitch-label]');if(label)label.textContent=pos;
    return true;
  }
  function onClick(button,refresh){
    if(button.hasAttribute('data-s214-picker-toggle')){
      const picker=button.closest('[data-s214-picker]');
      const menu=picker?.querySelector('.s214-picker-menu');
      if(!menu)return true;
      const opening=menu.hidden;
      closeManagerPickers();
      if(opening){
        const scroll=picker.closest('.s2-detail-scroll');
        const room=(scroll?.getBoundingClientRect().bottom||window.innerHeight)-button.getBoundingClientRect().bottom;
        picker.classList.toggle('s214-drop-up',room<190);
        menu.hidden=false;button.setAttribute('aria-expanded','true');
        (menu.querySelector('[aria-selected="true"]')||menu.querySelector('[role="option"]'))?.focus({preventScroll:true});
      }
      return true;
    }
    if(button.hasAttribute('data-s214-picker-option')){
      const picker=button.closest('[data-s214-picker]');
      const select=picker?.querySelector('select');
      const trigger=picker?.querySelector('[data-s214-picker-toggle]');
      if(!select||!trigger)return true;
      const before=select.value;
      select.value=button.dataset.s214PickerOption;
      const label=select.selectedOptions?.[0]?.textContent||button.textContent;
      picker.querySelector('[data-s214-picker-label]').textContent=label;
      trigger.setAttribute('aria-label',`${select.getAttribute('aria-label')}: ${label}`);
      picker.querySelectorAll('[data-s214-picker-option]').forEach(option=>option.setAttribute('aria-selected',String(option===button)));
      closeManagerPickers();trigger.focus({preventScroll:true});
      if(select.value!==before)select.dispatchEvent(new Event('change',{bubbles:true}));
      return true;
    }
    if(button.dataset.s2Tab){if(!switchInspectorTab(button.dataset.s2Tab))refresh();return true;}
    if(button.dataset.s2FocusPosition)return focusPosition(button.dataset.s2FocusPosition);
    if(button.dataset.s2Navigate){
      const page=button.dataset.s2Navigate;
      if(!['Dressing Room','Training','Medical Centre','Tactics'].includes(page))return true;
      if(parent!==window)parent.postMessage({type:'fm-squad-open-section',page},location.origin);
      else location.href='/portable/#page/'+encodeURIComponent(page);
      return true;
    }
    if(button.dataset.rosterExpand){state.expanded=button.dataset.rosterExpand;if(!showSelectedPlayer())refresh();return true;}
    return false;
  }
  function onChange(input, command, refresh){
    if(input.matches('[data-s2-sort]')){view.order=input.value;updateRosterList(true);return true;}
    if(input.matches('[data-s2-season]')){state.season=input.value;state.competition='all';window.FMRoster.reload?.();return true;}
    if(input.matches('[data-s2-competition]')){state.competition=input.value;window.FMRoster.reload?.();return true;}
    if(input.id==='rt-player-number'){
      const p=state.expanded;
      if(view.data?.readonly||!p)return true;
      command({action:'squad_number',player_id:p,number:input.value===''?null:Number(input.value)},'Squad number updated in Python.');return true;
    }
    if(input.id==='rt-transfer-status'){
      const p=state.expanded;
      if(view.data?.readonly||!p)return true;
      command({action:'transfer_status',player_id:p,status:input.value},'Transfer status updated in Python.');return true;
    }
    return false;
  }
  function updateRosterList(resetScroll=false){
    const list=$('.s2-list-scroll');
    if(!list||!view.data)return false;
    const previous=resetScroll?0:list.scrollTop;
    list.innerHTML=rosterContents(view.data);
    list.scrollTop=previous;
    const count=$('[data-s25-list-count]');
    if(count)count.textContent=`${allPlayers(view.data).length} players in your first team`;
    activateLoadedArt();
    return true;
  }
  function onInput(input, refresh){
    if(!input.matches('[data-s2-search]'))return false;
    view.query=input.value;
    if(!updateRosterList(true))refresh();
    return true;
  }
  function activateLoadedArt(){
    if(!view.rendered)return;
    const id=view.data?.club_id,entry=id?squadIdentity(id,view.data?.club):null;
    if(entry){
      clubTheme(view.data);
      // Late-loaded club identity must update its displayed name, not only art.
      // This fixes the initial fictional-club name persisting in the Squad banner.
      const clubLabel=$('[data-s26-club-name]');
      if(clubLabel && typeof entry.display_name==='string' && entry.display_name.trim())clubLabel.textContent=entry.display_name;
      const crest=$('.s2-club-crest');
      if(crest && safeAsset(entry.crest) && !crest.querySelector('img'))crest.innerHTML=`<img src="/portable/${html(entry.crest)}" alt="">`;
      const head=$('.s2-page-header');
      if(head && safeAsset(entry.hero_image))head.style.setProperty('--s2-banner',`url('/portable/${entry.hero_image}')`);
      // TS-UI-02.8: only refresh presentation assets; preserve the active tab
      // and independently scrolled directory and inspector.
      const newSilhouette=$('.s29-crest-silhouette');
      if(newSilhouette && safeAsset(entry.crest))newSilhouette.style.setProperty('--s29-crest',`url('/portable/${entry.crest}')`);
      const watermark=$('.s28-crest-watermark');
      if(watermark && safeAsset(entry.crest)){
        watermark.style.setProperty('--s28-watermark',`url('/portable/${entry.crest}')`);
        watermark.classList.remove('no-crest');
        watermark.classList.add('has-crest');
        watermark.querySelector('.s28-crest-fallback')?.remove();
      }
      const holder=$('.s28-kit-holder');
      const active=view.data.roster?.find(p=>p.id===state.expanded);
      if(holder && active && safeAsset(entry.kit_image)){
        const url=`/portable/${entry.kit_image}`;
        const current=holder.querySelector('.s2-shirt-image');
        if(!current || current.getAttribute('src')!==url){
          holder.innerHTML=kitGraphic(active,view.data);
        }
      }
    }
    document.querySelectorAll('[data-player-image-key]').forEach(el=>{
      if(el.querySelector('img.s2-real-photo'))return;
      const source=view.images[el.dataset.playerImageKey];
      if(!safeAsset(source))return;
      const image=document.createElement('img');image.className='s2-real-photo';image.alt='';image.loading='lazy';image.src=source;
      image.addEventListener('error',()=>image.remove(),{once:true});el.append(image);
    });
    // A missing kit file must fall back to the catalogue-defined illustrative
    // shirt; missing assets for future clubs must never leave a broken image.
    document.querySelectorAll('.s2-shirt-image').forEach(img=>{
      if(img.dataset.fallbackWired)return;
      img.dataset.fallbackWired='1';
      const fallback=()=>{
        const player=view.data?.roster?.find(p=>p.id===state.expanded);
        if(!player||!img.isConnected)return;
        const holder=document.createElement('div');
        holder.innerHTML=kitGraphic(player,view.data,true);
        if(holder.firstElementChild)img.replaceWith(holder.firstElementChild);
      };
      img.addEventListener('error',fallback,{once:true});
      if(img.complete && !img.naturalWidth)fallback();
    });
    document.querySelectorAll('.s2-avatar .s2-real-photo').forEach(img=>{
      if(img.dataset.wired)return;img.dataset.wired='1';
      img.addEventListener('error',()=>img.remove(),{once:true});
    });
  }
  // Assets are optional. Missing/invalid entries never break the UI or create fictitious faces.
  fetch('/portable/data/club-identities.json',{cache:'no-store'})
    .then(r=>r.ok?r.json():null).then(x=>{if(x?.schema_version===1&&x.clubs&&typeof x.clubs==='object')view.identities=x.clubs;activateLoadedArt();})
    .catch(()=>{});
  fetch('data/player-portraits.json',{cache:'no-store'})
    .then(r=>r.ok?r.json():null).then(x=>{if(x?.schema_version===1&&x.portraits&&typeof x.portraits==='object')view.images=x.portraits;activateLoadedArt();})
    .catch(()=>{});
  window.addEventListener('fm-identity-ready',activateLoadedArt);
  window.addEventListener('fm-assets-ready',activateLoadedArt);
  // Keyboard and outside-click support for accessible dark action pickers.
  document.addEventListener('pointerdown',event=>{
    if(!event.target.closest('[data-s214-picker]'))closeManagerPickers();
  });
  document.addEventListener('keydown',event=>{
    const picker=event.target.closest?.('[data-s214-picker]');
    if(!picker)return;
    const trigger=picker.querySelector('[data-s214-picker-toggle]');
    const menu=picker.querySelector('.s214-picker-menu');
    const choices=[...menu.querySelectorAll('[role="option"]')];
    if(event.key==='Escape'&&!menu.hidden){event.preventDefault();closeManagerPickers();trigger.focus({preventScroll:true});return;}
    if(!['ArrowDown','ArrowUp','Home','End'].includes(event.key))return;
    event.preventDefault();
    if(menu.hidden){onClick(trigger);return;}
    const index=choices.indexOf(document.activeElement);
    const next=event.key==='Home'?0:event.key==='End'?choices.length-1:event.key==='ArrowDown'?Math.min(choices.length-1,index+1):Math.max(0,index-1);
    choices[next]?.focus({preventScroll:true});
  });
  window.FMRoster={...original,render,onClick,onChange,onInput,state};
  window.FMSquadUI02={render,view,portraitSource:id=>window.FMEntityAssets?.getPhoto?.(id)||view.images[id]||null,focusPosition};
})();
