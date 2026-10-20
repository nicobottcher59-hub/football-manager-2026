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
    const photo=view.images[player.id];
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
  const bar = (label,value,type='neutral') => `<div class="s2-measure"><div class="s2-measure-label"><span>${html(label)}</span><strong>${pct(value)}</strong></div><div class="s2-track"><span class="s2-fill ${type}" style="width:${clamp(value)}%"></span></div></div>`;
  const fact = (label,val,sub='') => `<div class="s2-fact"><span>${html(label)}</span><strong>${val}</strong>${sub?`<small>${html(sub)}</small>`:''}</div>`;
  const date = str => {const m=/^(\d{4})-(\d{2})-(\d{2})$/.exec(String(str||''));return m?`${Number(m[3])} ${['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'][Number(m[2])-1]||m[2]} ${m[1]}`:'—';};
  const notice = text => `<p class="s2-muted s2-info"><span aria-hidden="true">ⓘ</span> ${html(text)}</p>`;
  function clubTheme(data) {
    const id=data.club_id;
    const entry=view.identities[id]||{};
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
  function rosterRow(p,data){
    const selected=p.id===state.expanded;
    const status=p.injury?'Injured':Number(p.suspension)>0?'Suspended':p.available?'Available':'Unavailable';
    const mood=numeric(p.morale)?Number(p.morale):null;
    const moodLabel=mood==null?'Morale unknown':mood>=75?'Good morale':mood>=55?'Stable morale':'Low morale';
    const moodIcon=mood==null?'—':`<svg class="s26-mood-svg" viewBox="0 0 24 24" aria-hidden="true" focusable="false"><circle cx="12" cy="12" r="10" fill="currentColor"/><circle cx="8.5" cy="9.5" r="1.2" fill="#082532"/><circle cx="15.5" cy="9.5" r="1.2" fill="#082532"/><path d="${mood>=75?'M7 13 Q12 19 17 13':mood>=55?'M7 15 Q12 14 17 15':'M7 17 Q12 11 17 17'}" stroke="#082532" stroke-width="1.65" stroke-linecap="round" fill="none"/></svg>`;
    const condition=numeric(p.condition)?integer(p.condition)+'%':'—';
    const number=p.number==null?'':`<span class="s27-row-dorsal" title="Squad number ${html(p.number)}">#${html(p.number)}</span>`;
    return `<div class="s2-roster-row s25-player-card s26-player-card s27-player-card ${selected?'selected':''} ${p.available?'':'unavailable'}"
      role="row" tabindex="0" aria-selected="${selected}" data-s2-row="${html(p.id)}" data-roster-expand="${html(p.id)}" aria-label="Select ${html(p.name)}">
      <span class="s2-row-portrait s26-row-portrait s27-row-portrait">${avatar(p)}<i class="s2-portrait-edge" aria-hidden="true"></i></span>
      <div class="s2-name-cell s26-name-cell s27-name-cell" role="cell">
        <div class="s2-name-line s26-name-line s27-name-line"><strong class="s2-player-label">${html(p.name)}</strong>${captainBadge(p,data)}<button type="button" class="s2-profile-shortcut s26-profile-shortcut" data-open-career-player="${html(p.id)}" title="Open full profile of ${html(p.name)}" aria-label="Open full profile of ${html(p.name)}"><span aria-hidden="true">↗</span></button></div>
        <div class="s2-subline s26-subline s27-subline"><span class="s2-position-tag">${html(p.primary_position||'?')}</span><span class="s27-age">${html(p.age??'—')} yrs</span><span class="s25-nation">${nation(p)}</span>${number}</div>
      </div>
      <div class="s27-readiness-group" role="cell">
        <span class="s2-mood s25-row-morale s26-morale ${mood!=null&&mood<55?'s2-mood-low':mood!=null&&mood<75?'s2-mood-mid':'s2-mood-good'}" title="${html(moodLabel)}" aria-label="${html(moodLabel)}">${moodIcon}</span>
        <div class="s2-row-readiness s26-condition" aria-label="Condition ${condition}"><span class="s2-mini-track"><i style="--s2-width:${clamp(p.condition)}%" class="${Number(p.condition)<70?'warn':''}"></i></span><small>${condition}</small></div>
      </div>
      <div class="s2-row-rating s26-rating" role="cell">${badge(p.act)}</div>
      ${!p.available?`<span class="s2-row-warning" title="${html(status)}" aria-label="${html(status)}">!</span>`:''}
      <span class="s2-row-select-chevron s26-chevron" aria-hidden="true">›</span>
    </div>`;
  }
  function rosterContents(data){
    const list=allPlayers(data);
    return list.map(p=>rosterRow(p,data)).join('')||'<div class="s2-no-matches">No matching players.</div>';
  }
  function roster(data){
    const available=data.roster.filter(p=>p.available).length;
    const sortChoices=[['position','Position'],['grl','GRL'],['name','Name']];
    return `<section class="s2-roster s26-roster" aria-label="Squad player list">
      <div class="s26-directory-head"><div class="s2-roster-label s26-roster-title"><span class="s2-kicker">SQUAD DIRECTORY</span><h2>Players <span>${data.roster.length}</span></h2></div>
        <div class="s25-list-tools s26-list-tools"><label class="s25-search s26-search"><span aria-hidden="true">⌕</span><input type="search" data-s2-search aria-label="Search players" placeholder="Search players…" value="${html(view.query)}" autocomplete="off"></label>
        <label class="s25-sort s26-sort"><span>Sort by</span><select data-s2-sort aria-label="Sort players">${sortChoices.map(([key,label])=>`<option value="${key}" ${key===view.order?'selected':''}>${label}</option>`).join('')}</select></label></div>
      </div>
      <div class="s2-list-scroll s26-list-scroll" role="table" aria-label="Squad players">${rosterContents(data)}</div>
      <footer class="s2-roster-footer s26-roster-footer"><span data-s25-list-count>${allPlayers(data).length} of ${data.roster.length} players</span><span class="s2-scroll-icon" aria-hidden="true">Scroll ↕</span></footer>
      <span class="s2-roster-progress s26-sr-only" aria-label="${available} players available">${available} available</span>
    </section>`;
  }
  // A stylized kit is presentation-only. The badge/number/photo are loaded
  // from player and club identities, never tied to a specific club or fabricated IDs.
  function kitGraphic(p,data,illustrated=false){
    const identity=view.identities[data.club_id]||{};
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
    const avail=p.injury?'Injured':Number(p.suspension)>0?'Suspended':p.available?'Available':'Unavailable';
    const theme=view.identities[data.club_id]||{};
    const crest=safeAsset(theme.crest)?`<img src="/portable/${html(theme.crest)}" alt="" loading="lazy">`:'<span aria-hidden="true">✦</span>';
    const banner=safeAsset(theme.hero_image)?`style="--s25-hero-photo:url('/portable/${html(theme.hero_image)}')"`:'';
    const heroNumber=p.number==null?'':html(p.number);
    const watermarkStyle=safeAsset(theme.crest)?`style="--s27-watermark:url('/portable/${html(theme.crest)}')"`:'';
    const watermarkClass=safeAsset(theme.crest)?' s27-masked':'';
    // Context adjustment is not a historical ability gain: label it accurately.
    const delta=numeric(p.act)&&numeric(p.base_ovr)?Number(p.act)-Number(p.base_ovr):null;
    const contextDifference=delta!==null&&Math.abs(delta)>=.05?`<span class="s27-context-delta ${delta<0?'negative':''}" title="Current rating relative to base overall; not a historical gain">${delta>0?'+':''}${delta.toFixed(1)} vs base</span>`:'';
    return `<header class="s2-player-hero s25-player-hero s26-player-hero s27-player-hero" data-selected-player="${html(p.id)}" ${banner}>
      <div class="s2-hero-grain" aria-hidden="true"></div><span class="s2-hero-back-number" aria-hidden="true">${heroNumber}</span><span class="s2-hero-ambient" aria-hidden="true"></span>
      <div class="s2-hero-portrait s26-hero-portrait s27-hero-portrait">${avatar(p,true)}${captainBadge(p,data,true)}</div>
      <div class="s2-hero-main s26-hero-identity s27-hero-identity"><span class="s2-eyebrow">${html(p.primary_position||'—')} · FIRST TEAM</span><h2 class="s2-player-name">${html(p.name)}</h2>
        <p class="s2-hero-bio">${nation(p)}<span>${html(p.age??'—')} yrs</span><span>${p.foot?html(nice(p.foot))+' foot':'Foot not recorded'}</span></p>
        <div class="s2-role-pills s27-role-pills"><span class="s2-position-primary">${html(p.primary_position||'—')}</span>${(p.secondary_positions||[]).slice(0,3).map(pos=>`<span>${html(pos)}</span>`).join('')}<span class="${p.available?'is-good':'is-bad'}">${html(avail)}</span></div>
        <button type="button" class="s2-hero-open-profile" data-open-career-player="${html(p.id)}" aria-label="Open complete profile of ${html(p.name)}">Full player profile <span aria-hidden="true">→</span></button>
      </div>
      <div class="s2-hero-extras s25-shirt-stage s26-kit-stage s27-kit-stage" aria-label="Club home shirt"><div class="s2-hero-club-watermark${watermarkClass}" ${watermarkStyle}>${crest}</div><div class="s26-kit-holder s27-kit-holder">${kitGraphic(p,data)}</div></div>
      <div class="s2-hero-scores s25-hero-scores s26-hero-scores s27-hero-scores"><div class="s25-dorsal s26-dorsal ${p.number==null?'is-unassigned':''}"><small>SQUAD NUMBER</small><strong>${p.number==null?'—':html(p.number)}</strong></div><div class="s2-score-primary"><small>Current GRL</small>${badge(p.act)}${contextDifference}</div><div><small>Base OVR</small>${badge(p.base_ovr)}</div></div>
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
  function seasonTab(p,data){
    const opt=data.statistics||{};
    const season=state.season||data.stats_selection?.season||opt.current_season||'';
    const comp=state.competition||'all';
    const selectedComp=opt.competitions?.find(c=>c.id===comp)?.name||'All competitions';
    const seasons=(opt.seasons||[]).length?opt.seasons:[season];
    const comps=opt.competitions||[];
    const eligible=opt.club_competitions?.[season];
    const relevant=Array.isArray(eligible) ? comps.filter(c=>eligible.includes(c.id)) : comps;
    const options=relevant.some(c=>c.id===comp)?relevant:comp==='all'?relevant:[...relevant,...comps.filter(c=>c.id===comp)];
    const stats=p.season_stats||{},coverage=stats.coverage||{};
    const supported=opt.supported||[];
    const available=label=>supported.includes(label);
    const hero=[['appearances','Apps','♧'],['starts','Starts','▤'],['minutes','Minutes','◷'],['goals','Goals','⚽'],['assists','Assists','↗']];
    const more=statKeys.filter(([key])=>!hero.some(([heroKey])=>key===heroKey));
    return `<section class="s2-card s2-season-selector"><div class="s2-season-top"><div><h3><span class="s2-card-icon">▤</span> Season performance</h3><p>Recorded statistics from the active career, not projections.</p></div><div class="s2-season-filters"><label>Season<select data-s2-season aria-label="Statistics season">${seasons.map(s=>`<option value="${html(s)}" ${s===season?'selected':''}>${html(s)}</option>`).join('')}</select></label><label>Competition<select data-s2-competition aria-label="Statistics competition"><option value="all" ${comp==='all'?'selected':''}>All competitions</option>${options.map(c=>`<option value="${html(c.id)}" ${c.id===comp?'selected':''}>${html(c.name)}</option>`).join('')}</select></label></div></div><div class="s2-season-context">${html(season)} <span>·</span> <strong>${html(selectedComp)}</strong></div></section>
      <section class="s2-season-hero">${hero.map(([key,label,icon])=>`<div class="s2-stat-tile"><span class="s2-stat-icon" aria-hidden="true">${icon}</span><small>${label}</small><strong>${available(key)?integer(stats[key]):'—'}</strong></div>`).join('')}</section>
      <div class="s2-two-cards s2-season-lower"><section class="s2-card"><h3><span class="s2-card-icon">◉</span> Performance detail</h3><div class="s2-stat-list">${more.map(([key,label])=>`<div><span>${html(label)}</span><strong>${available(key)?key==='pass_completion'?pct(stats[key]):['xg','average_match_rating'].includes(key)?one(stats[key]):integer(stats[key]):'—'}</strong></div>`).join('')}</div></section><section class="s2-card s2-season-coverage"><h3><span class="s2-card-icon">✓</span> Data coverage</h3><div class="s2-coverage-indicator ${coverage.complete_season?'complete':'partial'}">${coverage.complete_season?'Complete tracked season':'Limited historical coverage'}</div><p>${coverage.complete_season?'All tracked matches in this season are included.':'Some earlier matches may not have detailed tracking. Missing values are shown as unknown.'}</p><div class="s2-coverage-facts">${fact('Detailed appearances',integer(coverage.recorded_appearances))}${fact('Recorded since',html(coverage.from||'Unknown'))}</div><p class="s2-muted">${html(opt.clean_sheet_definition||'Match rating is distinct from current GRL.')}</p></section></div>`;
  }
  function statusTab(p,data){
    const av=p.injury?'Injured':Number(p.suspension)>0?'Suspended':p.available?'Available':'Unavailable';
    const fatigue=p.fatigue,morale=numeric(p.morale)?Number(p.morale):null;
    const mood=morale==null?'No morale recorded':morale>=75?'Good morale':morale>=55?'Stable morale':'Low morale';
    return `<section class="s2-card s2-morale-feature"><div class="s2-morale-orb" style="--s2-morale:${clamp(p.morale)}%"><span>${morale==null?'—':morale>=75?'☺':morale>=55?'◉':'!'}</span></div><div class="s2-morale-description"><span class="s2-eyebrow">DRESSING ROOM</span><h3>${html(mood)}</h3><p>Recorded morale <strong>${pct(p.morale)}</strong>. Happiness is a separate measure and is never inferred from morale.</p></div><span class="s2-available-pill ${p.available?'is-ready':'is-unavailable'}">${p.available?'✓':'!'} ${html(av)}</span></section>
      <div class="s2-two-cards s2-status-grid"><section class="s2-card"><h3><span class="s2-card-icon">♥</span> Physical condition</h3>${bar('Condition',p.condition,Number(p.condition)<70?'warn':'good')}${bar('Match sharpness',p.sharpness,Number(p.sharpness)<70?'warn':'good')}${bar('Fatigue',fatigue,'fatigue')}</section>
      <section class="s2-card"><h3><span class="s2-card-icon">↗</span> Form & squad status</h3>${bar('Morale',p.morale,Number(p.morale)<55?'warn':'good')}${bar('Form',p.form,'form')}<div class="s2-state-line"><span>Happiness</span><strong>${p.happiness==null?'Not separately recorded':html(p.happiness)}</strong></div></section></div>
      <section class="s2-card s2-development"><h3><span class="s2-card-icon">↗</span> Training & development</h3><div class="s2-graphics" data-player-graphics="${html(p.id)}" data-graphics-mode="development"><p class="s2-muted">Loading the registered development review…</p></div></section>`;
  }
  function contractTab(p,data){
    const c=p.contract_details||{};
    const market=p.market_value==null?'—':html(p.market_value);
    const status=c.status==='out_of_contract_retained'?'Expired / retained':p.contract_details?'Registered':'Not recorded';
    return `<div class="s2-management"><section class="s2-card s2-contract-card"><div class="s2-section-heading"><h3><span class="s2-card-icon">▤</span> Contract</h3><span class="s2-status-pill">${html(status)}</span></div><div class="s2-contract-facts">${fact('Weekly wage',c.weekly_wage?html(c.weekly_wage)+'/w':'—')}${fact('Expiration',html(date(c.expires_on)))}${fact('Market valuation',market,'Estimate, not asking price')}${fact('Dorsal',p.number==null?'Not assigned':'#'+html(p.number))}</div><p class="s2-muted">Contract terms and valuation come from the active Python career. Unsupported clauses and bonuses are not invented.</p></section>
      <section class="s2-card s2-actions-card"><div class="s2-section-heading"><h3><span class="s2-card-icon">⚙</span> Player actions</h3><span class="s2-subtle-label">${data.readonly?'Read-only profile':'Available career / DEV operations'}</span></div>
       ${data.readonly?`<div class="s2-actions-grid"><button type="button" data-open-transfer-offer="${html(p.id)}" class="s2-action">↗ <span>Make transfer offer</span></button></div>`:
       `<div class="s2-action-fields"><label>Squad number<select data-roster-filter="rt-player-number" id="rt-player-number" aria-label="Squad number"><option value="" ${p.number==null?'selected':''}>Not assigned</option>${Array.from({length:99},(_,i)=>`<option value="${i+1}" ${Number(p.number)===i+1?'selected':''}>${i+1}</option>`).join('')}</select></label><label>Transfer status<select data-roster-filter="rt-transfer-status" id="rt-transfer-status" aria-label="Transfer status">${Object.entries(transferLabels).map(([key,label])=>`<option value="${key}" ${p.transfer_status===key?'selected':''}>${html(label)}</option>`).join('')}</select></label></div><div class="s2-actions-grid"><button type="button" data-open-finances class="s2-action s2-primary-action"><span aria-hidden="true">▤</span> Open contract negotiations ↗</button><button type="button" data-s2-navigate="Dressing Room" class="s2-action">☏ <span>Player conversations ↗</span></button><button type="button" data-s2-navigate="Training" class="s2-action">◎ <span>Individual training ↗</span></button><button type="button" data-s2-navigate="Tactics" class="s2-action">⚑ <span>Captain & set pieces ↗</span></button><button type="button" data-s2-navigate="Medical Centre" class="s2-action">✚ <span>Medical centre ↗</span></button></div>`}
       <p class="s2-muted">Squad numbers and transfer flags are DEV roster metadata; real negotiations and conversations open their existing sections.</p></section></div>`;
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
    if(count)count.textContent=`${allPlayers(view.data).length} of ${view.data.roster.length} players`;
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
    const id=view.data?.club_id,entry=view.identities[id];
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
      const playerHero=$('.s25-player-hero');
      if(playerHero && safeAsset(entry.hero_image))playerHero.style.setProperty('--s25-hero-photo',`url('/portable/${entry.hero_image}')`);
      // A slow identity fetch must also update the selected player's kit and
      // hero crest. Repaint only these decorations, preserving tab/list scroll.
      const active=view.data.roster?.find(p=>p.id===state.expanded);
      const watermark=$('.s2-hero-club-watermark');
      if(watermark && safeAsset(entry.crest)){
        watermark.classList.add('s27-masked');
        watermark.style.setProperty('--s27-watermark',`url('/portable/${entry.crest}')`);
        if(!watermark.querySelector('img'))watermark.innerHTML=`<img src="/portable/${html(entry.crest)}" alt="" loading="lazy">`;
      }
      const kit=$('.s26-kit-holder .s2-shirt-art,.s26-kit-holder .s2-shirt-image');
      if(kit && active && !kit.dataset.identityReady){
        const holder=document.createElement('div');
        holder.innerHTML=kitGraphic(active,view.data);
        const themedKit=holder.firstElementChild;
        if(themedKit){themedKit.dataset.identityReady='1';kit.replaceWith(themedKit);}
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
  window.FMRoster={...original,render,onClick,onChange,onInput,state};
  window.FMSquadUI02={render,view,portraitSource:id=>view.images[id]||null,focusPosition};
})();
