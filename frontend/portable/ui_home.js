/* TS-UI-01A: Approved cinematic Home. Read-only render of the existing Python world.
 * No fixture, ranking, knockout pairing, result or player attribute is fabricated. */
(() => {
  'use strict';
  const host = document.querySelector('.dashboard-grid');
  if (!host) return;
  const h = v => String(v ?? '').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const num = value => Number.isFinite(Number(value)) ? Number(value).toFixed(1).replace('.',',') : '\u2014';
  const title = value => String(value ?? '').replace(/\s*\(development\)/g,'').replace(/\s*\(fictional clubs\)/g,'');
  const icon = (name) => {
    const shapes = {
      arrow:'<path d="m9 5 7 7-7 7"/>',
      team:'<circle cx="8" cy="8" r="3"/><path d="M2 21v-3a6 6 0 0 1 12 0v3M17 5a3 3 0 0 1 0 6M17 15a5 5 0 0 1 5 5v1"/>',
      calendar:'<rect x="3" y="5" width="18" height="16" rx="2"/><path d="M7 2v6M17 2v6M3 10h18"/>',
      cup:'<path d="M7 3h10v8a5 5 0 0 1-10 0V3ZM7 5H3v3a4 4 0 0 0 4 4M17 5h4v3a4 4 0 0 1-4 4M12 16v5M8 21h8"/>',
      mail:'<rect x="3" y="5" width="18" height="15" rx="2"/><path d="m3 7 9 7 9-7"/>',
      stadium:'<path d="M3 11c5-5 13-5 18 0v7c-5 4-13 4-18 0v-7ZM3 11c5 5 13 5 18 0M8 8V4h8v4"/>',
      pin:'<path d="M20 10c0 5-8 12-8 12S4 15 4 10a8 8 0 1 1 16 0Z"/><circle cx="12" cy="10" r="2.5"/>',
      people:'<circle cx="8" cy="8" r="3"/><path d="M2 20a6 6 0 0 1 12 0M17 5a3 3 0 0 1 0 6M16 14a5 5 0 0 1 6 5"/>',
      heart:'<path d="M20.5 9c0 5-8.5 11-8.5 11S3.5 14 3.5 9a4.5 4.5 0 0 1 8.5-2 4.5 4.5 0 0 1 8.5 2Z"/>',
      form:'<path d="M3 17 10 10l4 4 7-8M15 6h6v6"/>',
      smile:'<circle cx="12" cy="12" r="9"/><path d="M8 14c1 2 3 3 4 3s3-1 4-3M8 10h.01M16 10h.01"/>'
    };
    return `<svg viewBox="0 0 24 24" width="19" height="19" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${shapes[name]||shapes.arrow}</svg>`;
  };
  const state = {squad:null, calendar:null, competitions:[], competition:null, inbox:null, news:null, selected:null, activity:'inbox', clubId:null, identity:null, loading:false};
  let sequence=0, competitionSerial=0;
  const get = selector => document.querySelector('#tsui-home '+selector);
  const safeRoute=(route) => window.FMNavigation?.navigate(route);
  const dateLabel=value => /^\d{4}-\d{2}-\d{2}$/.test(value||'')?
    new Intl.DateTimeFormat('es-AR',{day:'numeric',month:'short',timeZone:'UTC'}).format(new Date(value+'T12:00:00Z')):'Fecha pendiente';
  const fullDate=value => /^\d{4}-\d{2}-\d{2}$/.test(value||'')?
    new Intl.DateTimeFormat('es-AR',{weekday:'short',day:'numeric',month:'short',timeZone:'UTC'}).format(new Date(value+'T12:00:00Z')):'Sin fecha';
  function getIdentity() {return window.FMClubIdentity?.resolve(state.clubId,state.squad?.club) ||
    {display_name:state.squad?.club||'Club',founded:null,stadium:null,location:null,hero_image:null,crest:null,visual_only:false};}
  const shownClub=(id,name) => window.FMClubIdentity?.resolve(id,name).display_name || name || id;
  function badge(outcome) {
    const cls={V:'win',D:'loss',E:'draw'}[outcome]||'unknown';
    return `<span class="tsui-result tsui-${cls}" aria-label="${{V:'Victoria',D:'Derrota',E:'Empate'}[outcome]||'Resultado desconocido'}">${h(outcome||'?')}</span>`;
  }
  // Chronological form, using recorded match outcomes. Future fixtures never count.
  function formBoxes(outcomes) {
    const known=(Array.isArray(outcomes)?outcomes:[]).filter(v=>['V','E','D'].includes(v)).slice(-5);
    // Five slots are always visible; outlined dashes explicitly mean "not played",
    // never a fictional draw or inferred result. Actual form is chronological.
    const missing=Array.from({length:5-known.length},()=>'<span class="tsui-result tsui-pending" title="Sin partido registrado" aria-label="Sin resultado registrado">–</span>').join('');
    return missing+known.map(v=>badge(v)).join('');
  }
  function lastResults() {return (state.calendar?.matches||[]).filter(m=>m.score&&m.date<=state.calendar.date).slice(-5);}
  function recentStrip() { const games=lastResults();return formBoxes(games.map(g=>g.outcome));}
  function cardHeading(label, route, symbol) {
    return `<div class="tsui-card-heading"><button type="button" class="tsui-card-link" data-tsui-route="${h(route)}">${icon(symbol)}<span>${label}</span>${icon('arrow')}</button></div>`;
  }
  function initialMarkup() {
    const layout = document.createElement('section');
    layout.id='tsui-home';layout.className='tsui-home';layout.setAttribute('aria-label','Resumen del club');
    layout.innerHTML=`<section class="tsui-hero" aria-label="Informaci\u00f3n del club">
      <div class="tsui-hero-background"></div><div class="tsui-hero-shade"></div>
      <div class="tsui-hero-content"><div class="tsui-brand-row">
        <div class="tsui-large-crest" aria-hidden="true">${icon('cup')}</div>
        <div class="tsui-hero-text"><span class="tsui-hero-eyebrow">NUESTRO CLUB \u00b7 NUESTRA HISTORIA</span>
          <h2 class="tsui-club-name">Cargando club\u2026</h2>
          <p class="tsui-hero-tagline">Una identidad distinta para cada equipo.</p>
        </div></div>
        <div class="tsui-hero-bottom"><div class="tsui-hero-facts" aria-label="Datos institucionales">
          <div class="tsui-institutional" id="tsui-founded">${icon('calendar')}<span><small>FUNDACI\u00d3N</small><strong>\u2014</strong></span></div>
          <div class="tsui-institutional" id="tsui-stadium">${icon('stadium')}<span><small>ESTADIO</small><strong>\u2014</strong></span></div>
          <div class="tsui-institutional" id="tsui-location">${icon('pin')}<span><small>CIUDAD</small><strong>\u2014</strong></span></div>
        </div><div class="tsui-hero-results"><span>\u00daLTIMOS 5 PARTIDOS</span><div class="tsui-results-items">\u2014</div></div></div>
      </div>
      <div class="tsui-hero-note" role="note">Identidad visual e institucional \u00b7 Partida deportiva ficticia</div>
    </section>
    <div class="tsui-home-widgets">
      <section class="tsui-home-card tsui-team-card" aria-label="Equipo">
        ${cardHeading('Equipo','Squad','team')}
        <div class="tsui-status-grid" aria-label="Indicadores reales del plantel"></div>
        <div class="tsui-pitch-title"><span class="tsui-formation-label">Cargando alineaci\u00f3n\u2026</span><button type="button" data-tsui-route="Tactics" title="Abrir t\u00e1cticas">${icon('arrow')}</button></div>
        <div class="tsui-pitch" role="group" aria-label="Alineaci\u00f3n titular"><div class="tsui-pitch-lines"><div class="tsui-midline"></div><div class="tsui-center-circle"></div><div class="tsui-goal-box tsui-top-box"></div><div class="tsui-goal-box tsui-bottom-box"></div></div><div class="tsui-players"></div></div>
      </section>
      <section class="tsui-home-card tsui-calendar-card" aria-label="Calendario">
        ${cardHeading('Calendario','Calendar','calendar')}
        <div class="tsui-card-label">PR\u00d3XIMOS PARTIDOS</div><div class="tsui-fixtures tsui-loading">Cargando calendario\u2026</div>
        <div class="tsui-calendar-form"><div class="tsui-card-label">\u00daLTIMOS 5 PARTIDOS</div><div class="tsui-calendar-results"></div></div>
      </section>
      <section class="tsui-home-card tsui-competition-card" aria-label="Competiciones">
        ${cardHeading('Competiciones','Competitions','cup')}
        <div class="tsui-competition-tabs" role="tablist" aria-label="Competiciones del club"></div>
        <div class="tsui-competition-body" role="tabpanel" aria-live="polite">Cargando competiciones\u2026</div>
      </section>
      <section class="tsui-home-card tsui-inbox-card" aria-label="Buz\u00f3n y noticias">
        ${cardHeading('Buz\u00f3n','Inbox','mail')}
        <div class="tsui-inbox-tabs" role="tablist" aria-label="Elegir novedades"><button type="button" role="tab" data-tsui-activity="inbox" aria-selected="true">Inbox <span class="tsui-unread"></span></button><button type="button" role="tab" data-tsui-activity="news" aria-selected="false">Noticias</button></div>
        <div class="tsui-updates" role="tabpanel" aria-label="Mensajes y noticias, lista desplazable" aria-live="polite" tabindex="0">Cargando novedades\u2026</div>
      </section>
    </div>`;
    host.appendChild(layout);
    document.body.classList.add('tsui-ready');
    document.body.classList.toggle('tsui-home-active',host.style.display!=='none');
  }
  function renderIdentity() {
    const item=getIdentity();state.identity=item;
    const hero=get('.tsui-hero');
    if(!hero)return;
    const name=get('.tsui-club-name');name.textContent=item.display_name;
    name.dataset.clubId=state.clubId||'';name.setAttribute('role','link');name.tabIndex=0;
    get('.tsui-hero-tagline').textContent=item.tagline||item.location||'Identidad y trayectoria del club';
    const crest=get('.tsui-large-crest');crest.innerHTML=item.crest?`<img src="${h(item.crest)}" alt="Escudo de ${h(item.display_name)}">`:icon('cup');
    const photo=get('.tsui-hero-background');photo.style.backgroundImage=item.hero_image?`url("${item.hero_image}")`:"url('assets/stadium.svg')";
    const fact=(selector,value) => {const tag=get(selector+' strong');if(tag)tag.textContent=value??'No registrado';};
    fact('#tsui-founded',item.founded || 'No registrado');fact('#tsui-stadium',item.stadium);fact('#tsui-location',item.location);
    get('.tsui-hero-results .tsui-results-items').innerHTML=recentStrip();
    const note=get('.tsui-hero-note');note.hidden=!item.visual_only;
    window.FMClubIdentity?.applyShell(state.clubId,state.squad?.club);
    // Reusable background/footer for any configured club; not hardcoded by team.
    const side=document.querySelector('.sidebar-bottom');
    if(side){if(item.hero_image){side.classList.add('tsui-sidebar-branded');side.style.setProperty('--tsui-sidebar-photo',`url("${item.hero_image}")`);}
      else{side.classList.remove('tsui-sidebar-branded');side.style.removeProperty('--tsui-sidebar-photo');}}
  }
  function renderStatuses() {
    const root=get('.tsui-status-grid'), squad=state.squad;
    const definitions=[['morale','Moral','smile'],['condition','Condici\u00f3n','heart'],['chemistry','Qu\u00edmica','team'],['form','Forma','form']];
    const levels=value=>value>=85?'Excelente':value>=75?'Muy buena':value>=60?'Buena':value>=40?'Regular':'Baja';
    root.innerHTML=definitions.map(([key,label,symbol])=>{
      const score=squad?.squad_status?.[key];const valid=Number.isFinite(score);
      return `<div class="tsui-stat" title="${h(label)}: ${valid?num(score):'Pendiente'} / 100">
        <div class="tsui-stat-icon">${icon(symbol)}</div><div class="tsui-stat-body"><small>${label}</small><strong>${valid?levels(score):'Pendiente'}</strong></div>
        <div class="tsui-stat-track"><span style="width:${valid?Math.max(0,Math.min(100,score)):0}%"></span></div><b>${valid?num(score):'\u2014'}</b>
      </div>`;
    }).join('');
  }
  function renderPitch() {
    const squad=state.squad;
    const target=get('.tsui-players');
    if(!squad || !Array.isArray(squad.starters) || !window.FMTacticalBoard?.place){target.innerHTML='<p class="tsui-pitch-empty">Sin alineaci\u00f3n disponible</p>';return;}
    get('.tsui-formation-label').textContent=squad.formation?.name||'Alineaci\u00f3n principal';
    const positions=window.FMTacticalBoard.place(squad,'in_possession');
    const players=new Map(squad.starters.map(p=>[p.slot_id,p]));
    target.innerHTML=(squad.slots||[]).map(slot=>{
      const player=players.get(slot.slot_id), coord=positions?.[slot.slot_id];
      if(!player||!coord)return '';
      const x=Math.max(11,Math.min(89,coord.x)),y=Math.max(12,Math.min(88,coord.y));
      const face=window.FMPortraits?.portrait?window.FMPortraits.portrait(player,'tsui-face'):`<span class="tsui-fallback-face">${h((player.short_name||player.name||'?').slice(0,1))}</span>`;
      return `<button class="tsui-pitch-player" data-tsui-player="${h(player.id)}" title="${h(player.name)} \u00b7 GRL ${num(player.act)}" style="left:${x}%;top:${y}%"><span class="tsui-player-photo">${face}<b>${num(player.act)}</b></span><span class="tsui-player-name">${h(player.short_name||player.name)}</span></button>`;
    }).join('');
  }
  function opponentIdentity(f) {
    return window.FMClubIdentity?.resolve(f.opponent_id, f.opponent) || {display_name:f.opponent};
  }
  function opponentCrest(f, highlighted=false) {
    const identity=opponentIdentity(f);
    const label=identity.display_name||f.opponent||'?';
    const image=identity.crest?`<img src="${h(identity.crest)}" alt="" loading="lazy">`:h(label.slice(0,1));
    return `<span class="tsui-other-crest ${highlighted?'tsui-other-crest-large':''}" aria-hidden="true">${image}</span>`;
  }
  function opponentForm(f, featured=false) {
    const form=Array.isArray(f.opponent_form)?f.opponent_form:[];
    return `<span class="tsui-opponent-form ${featured?'tsui-opponent-form-featured':''}" aria-label="Últimos resultados de ${h(opponentIdentity(f).display_name||f.opponent)}">${formBoxes(form)}</span>`;
  }
  const branding=id=>window.FMCompetitionBranding?.resolve(id)||{key:'neutral',accent:'#79bce4',logo:null};
  const brandStyle=id=>window.FMCompetitionBranding?.vars(id)||'';
  const brandLogo=(id,cls)=>window.FMCompetitionBranding?.badge(id,cls)||'';
  function competitionLabel(id,name,featured=false) {
    return `<span class="tsui-fixture-comp ${featured?'tsui-featured-comp':''}" aria-label="${h(title(name))}">${brandLogo(id,'ci-fixture-logo')}<span class="tsui-comp-name">${h(title(name))}</span></span>`;
  }
  function compSummary(model, subtitle) {
    return `<div class="tsui-competition-summary">${brandLogo(model.id,'ci-summary-logo')}<span><strong>${h(title(model.name))}</strong><small>${h(subtitle)}</small></span></div>`;
  }
  function renderCalendar() {
    const area=get('.tsui-fixtures');
    if(!state.calendar){area.textContent='Calendario no disponible.';return;}
    const next=state.calendar.matches.filter(g=>!g.score&&g.date>=state.calendar.date).slice(0,5);
    if(!next.length){area.innerHTML='<p class="tsui-empty">No hay partidos programados. Revisá el calendario para la próxima temporada.</p>';}
    else {
      const first=next[0];
      const opponent=opponentIdentity(first).display_name||first.opponent;
      const featured=`<button type="button" class="tsui-featured-fixture" data-competition-brand="${h(branding(first.competition_id).key)}" style="${brandStyle(first.competition_id)}" data-tsui-route="Calendar" title="Abrir el próximo partido en Calendario">
        <span class="tsui-featured-top"><span class="tsui-featured-eyebrow">PRÓXIMO RIVAL</span><span class="tsui-featured-home">${first.home?'EN CASA':'DE VISITANTE'}</span></span>
        <span class="tsui-featured-team">${opponentCrest(first,true)}<span class="tsui-featured-name"><strong>${h(opponent)}</strong>${competitionLabel(first.competition_id,first.competition,true)}</span><span class="tsui-featured-chevron">${icon('arrow')}</span></span>
        <span class="tsui-featured-date">${icon('calendar')}<span>${h(fullDate(first.date))}${first.kickoff?' · '+h(first.kickoff.slice(11,16))+' UTC':''}</span></span>
        <span class="tsui-featured-form"><small>FORMA DEL RIVAL · ÚLTIMOS 5</small>${opponentForm(first,true)}</span>
      </button>`;
      const others=next.slice(1).map(f=>`<button class="tsui-fixture-row" type="button" data-competition-brand="${h(branding(f.competition_id).key)}" style="${brandStyle(f.competition_id)}" data-tsui-route="Calendar" title="Abrir el encuentro en Calendario">
        <span class="tsui-fixture-date">${h(dateLabel(f.date))}<small>${h(f.kickoff?f.kickoff.slice(11,16)+' UTC':'Hora pendiente')}</small></span>
        <span class="tsui-fixture-opponent">${opponentCrest(f)}<span class="tsui-fixture-content"><strong>${h(opponentIdentity(f).display_name||f.opponent)}</strong>${competitionLabel(f.competition_id,f.competition)}<small>${f.home?'Local':'Visita'}</small>${opponentForm(f)}</span></span>
        <span class="tsui-location-type">${icon('arrow')}</span>
      </button>`).join('');
      area.innerHTML=featured+others;
    }
    get('.tsui-calendar-results').innerHTML=recentStrip();
    get('.tsui-hero-results .tsui-results-items').innerHTML=recentStrip();
  }
  function renderCompTabs() {
    const options=(state.competitions||[]).filter(row=>row.managed);
    const bar=get('.tsui-competition-tabs');
    bar.dataset.columns=options.length >= 4 ? '2' : 'auto';
    bar.innerHTML=options.map(option=>`<button type="button" role="tab" class="${option.id===state.selected?'selected':''}" data-competition-brand="${h(branding(option.id).key)}" style="${brandStyle(option.id)}" data-tsui-competition="${h(option.id)}" aria-selected="${option.id===state.selected}" title="${h(option.name)}">${brandLogo(option.id,'ci-tab-logo')}<span>${h(title(option.name))}</span></button>`).join('');
    if(!options.length)get('.tsui-competition-body').innerHTML='<p class="tsui-empty">No hay competiciones registradas para este club.</p>';
  }
  const clubButton=(id,name)=>id?`<button type="button" data-tsui-club="${h(id)}">${h(shownClub(id,name))}</button>`:h(name||'Pendiente');
  function renderLeague(model){
    const rows=model?.table||[];if(!rows.length)return '<p class="tsui-empty">Sin posiciones disponibles todav\u00eda.</p>';
    const index=rows.findIndex(r=>r.managed);
    const start=Math.max(0,Math.min(Math.max(0,rows.length-6),index<0?0:index-2));
    return `${compSummary(model,'Tabla actual')}
      <div class="tsui-league-rows"><div class="tsui-table-head"><span>POS</span><span>CLUB</span><span>PJ</span><span>DG</span><span>PTS</span></div>
      ${rows.slice(start,start+6).map(row=>`<div class="tsui-league-row ${row.managed?'is-managed':''}"><span>${h(row.position)}</span><span class="tsui-cell-club">${clubButton(row.club_id,row.club)}</span><span>${h(row.played)}</span><span>${h(row.gd>0?'+'+row.gd:row.gd)}</span><b>${h(row.points)}</b></div>`).join('')}</div>`;
  }
  function tieRow(tie){
    const score=tie.aggregate?tie.aggregate:null;
    const a=score?score.a:'\u2014',b=score?score.b:'\u2014';
    return `<div class="tsui-bracket-tie ${tie.managed?'is-managed':''}">
      <div>${clubButton(tie.club_a_id,tie.club_a)}<strong>${h(a)}</strong></div>
      <div>${clubButton(tie.club_b_id,tie.club_b)}<strong>${h(b)}</strong></div>
    </div>`;
  }
  function compactTie(tie,label,optional=false) {
    if(!tie)return `<div class="tsui-mini-tie tsui-mini-tie-pending"><small>${h(label)}</small><div class="tsui-mini-tie-pending-icon">◇</div><strong>Sorteo pendiente</strong><span>No hay cruce confirmado</span></div>`;
    return `<div class="tsui-mini-tie ${tie.managed?'is-managed':''}"><small>${h(label)}</small>${tieRow(tie)}</div>`;
  }
  function renderKnockout(model) {
    const rounds=Array.isArray(model?.knockout)?model.knockout:[];
    const mine=rounds.flatMap((round,index)=>(round.ties||[]).filter(t=>t.managed).map(t=>({round,index,tie:t})));
    if(!mine.length){
      return `${compSummary(model,'Camino en la copa')}<div class="tsui-mini-path">
        ${compactTie(null,'Entrada: '+(model.managed_entry_round_label||'Por confirmar'))}
        ${compactTie(null,'Ronda siguiente')}</div>
        <p class="tsui-bracket-note">El equipo está inscrito. Todavía no hay un cruce propio sorteado.</p>`;
    }
    // Prefer the most recent unfinished managed tie; otherwise the most recent played one.
    const active=mine.find(x=>!x.tie.complete)||mine[mine.length-1];
    const advancing=active.tie.complete && active.tie.winner_id===state.clubId;
    const eliminated=active.tie.complete && !advancing;
    // Many cups in this game REDRAW every round (fixed_bracket === false).
    // Never assume adjacent ties form a future pairing. Only show a real next
    // tie if the managed club is explicitly listed in the next published draw.
    const confirmedNext=rounds.slice(active.index+1).flatMap(r=>(r.ties||[]).filter(t=>t.managed)
      .map(t=>({tie:t,label:r.label}))).find(Boolean);
    const second=confirmedNext?compactTie(confirmedNext.tie,'Cruce siguiente · '+confirmedNext.label):
      `<div class="tsui-mini-tie tsui-mini-tie-pending"><small>${eliminated?'Recorrido finalizado':'Posible rival · próxima ronda'}</small>
        <div class="tsui-mini-tie-pending-icon">${eliminated?'✓':'◇'}</div>
        <strong>${eliminated?'Eliminado':'Sorteo pendiente'}</strong>
        <span>${eliminated?'El club no continúa en esta copa':'No hay rival confirmado. No se predice la siguiente llave.'}</span></div>`;
    return `${compSummary(model,'Tu partido y la próxima ronda')}<div class="tsui-mini-path" aria-label="Camino de copa del club: máximo dos cruces">
      ${compactTie(active.tie,'Tu partido · '+active.round.label)}
      <div class="tsui-mini-link" aria-hidden="true"><span></span><b>→</b><span></span></div>${second}</div>
      <p class="tsui-bracket-note">Las copas se sortean por ronda. Solo se muestra un rival futuro cuando ya está confirmado.</p>`;
  }
  function renderCompetitionBody(model) {
    if(model.kind==='league')return renderLeague(model);
    if(model.kind==='multi' && !(model.knockout||[]).some(r=>r.ties?.some(t=>t.managed)))return renderLeague(model);
    return renderKnockout(model);
  }
  async function loadCompetition(id) {
    if (!id) return;
    const serial=++competitionSerial;
    state.selected=id;
    const themed=get('.tsui-competition-card');
    const body=get('.tsui-competition-body');
    themed.dataset.competitionBrand=branding(id).key;
    themed.style.cssText=brandStyle(id);
    body.dataset.competitionBrand=branding(id).key;
    body.style.cssText=brandStyle(id);
    renderCompTabs();
    get('.tsui-competition-body').innerHTML='<p class="tsui-empty">Cargando competici\u00f3n\u2026</p>';
    try{
      const response=await fetch('/api/competitions/'+encodeURIComponent(id),{cache:'no-store'});
      if(!response.ok)throw Error('La competici\u00f3n no est\u00e1 disponible');
      const model=await response.json();if(serial!==competitionSerial)return;
      state.competition=model;
      get('.tsui-competition-body').innerHTML=renderCompetitionBody(model);
    }catch(error){if(serial===competitionSerial)get('.tsui-competition-body').innerHTML='<p class="tsui-empty">No se pudo obtener el torneo. <button type="button" data-tsui-retry>Reintentar</button></p>';}
  }
  const updateKind=category=>({medical:'medical',injury:'medical',scouting:'scouting',results:'result',
    result:'result',title:'award',award:'award',transfer:'transfer',market:'transfer',contracts:'contract',
    conversations:'conversation',calendar:'calendar',system:'system'})[category]||'club';
  const updateIcon=category=>({medical:'heart',scouting:'people',result:'cup',award:'cup',transfer:'form',
    contract:'mail',conversation:'team',calendar:'calendar'})[updateKind(category)]||'mail';
  const updateLabel=category=>({medical:'Centro médico',scouting:'Ojeo',result:'Resultados',award:'Premios',
    transfer:'Mercado',contract:'Contratos',conversation:'Vestuario',calendar:'Calendario',system:'Club',club:'Club'})[updateKind(category)]||'Club';
  function updateMarkup(item,index,isNews) {
    const category=isNews?item.category:(item.category||'system');
    const feature=index===0;
    const action=isNews?`data-tsui-news="${h(item.id)}"`:'data-tsui-route="Inbox"';
    const body=item.body||'';
    return `<button type="button" class="tsui-update tsui-update-${h(updateKind(category))} ${feature?'tsui-update-featured':''}" ${action}>
      <span class="tsui-update-icon">${icon(updateIcon(category))}</span>
      <span class="tsui-update-copy"><small><em>${h(updateLabel(category))}</em> · ${h(item.date||item.season||'')}</small>
      <strong>${h(item.title)}</strong><span>${h(body)}</span></span>
      ${!isNews&&!item.read?'<i class="tsui-unread-dot" aria-label="Sin leer"></i>':(feature?'<span class="tsui-update-arrow" aria-hidden="true">›</span>':'')}
    </button>`;
  }
  function renderUpdates() {
    const tabs=get('.tsui-inbox-tabs');
    tabs.querySelectorAll('[data-tsui-activity]').forEach(button=>{
      const selected=button.dataset.tsuiActivity===state.activity;
      button.setAttribute('aria-selected',String(selected));button.classList.toggle('selected',selected);
    });
    const unread=tabs.querySelector('.tsui-unread');unread.textContent=state.inbox?.unread?String(state.inbox.unread):'';
    unread.hidden=!state.inbox?.unread;
    const box=get('.tsui-updates');
    const previousActivity=box.dataset.activity;
    box.dataset.activity=state.activity;
    if(previousActivity!==state.activity)box.scrollTop=0;
    if(state.activity==='inbox'){
      if(!state.inbox){box.innerHTML='<p class="tsui-empty">Cargando mensajes…</p>';return;}
      const rows=state.inbox.messages||[];
      box.innerHTML=rows.length?rows.slice(0,5).map((m,i)=>updateMarkup(m,i,false)).join(''):
        '<p class="tsui-empty">No hay mensajes por ahora.</p>';
      if(rows.length<3)box.insertAdjacentHTML('beforeend',`<div class="tsui-inbox-idle">${icon('mail')}<strong>${rows.length?'Al día con tus mensajes':'Todo bajo control'}</strong><span>Los informes y las decisiones pendientes aparecerán cuando ocurran en tu carrera.</span></div>`);
    }else{
      if(!state.news){box.innerHTML='<p class="tsui-empty">Cargando noticias…</p>';return;}
      const rows=state.news.stories||[];
      box.innerHTML=rows.length?rows.slice(0,6).map((story,i)=>updateMarkup(story,i,true)).join(''):
        `<div class="tsui-news-idle">${icon('cup')}<strong>A la espera de novedades</strong><span>Partidos, fichajes confirmados, campeones y premios aparecerán aquí cuando sucedan.</span></div>`;
    }
  }
  function renderSquad(squad) {
    state.squad=squad;state.clubId=squad.club_id;
    renderIdentity();renderStatuses();renderPitch();
  }
  async function fetchJson(url) {const response=await fetch(url,{cache:'no-store'});if(!response.ok)throw Error(`${url}: ${response.status}`);return response.json();}
  async function refresh(){
    if (host.style.display==='none')return;
    const serial=++sequence;
    state.loading=true;
    const paths=['/api/squad','/api/calendar','/api/competitions','/api/inbox','/api/news'];
    const keys=['squad','calendar','competitions','inbox','news'];
    await Promise.allSettled(paths.map(async(path,i)=>{
      const data=await fetchJson(path);
      if(serial!==sequence)return;
      const key=keys[i];
      if(key==='squad')renderSquad(data);
      else if(key==='calendar'){state.calendar=data;renderCalendar();}
      else if(key==='competitions'){
        state.competitions=(data.competitions||[]).filter(c=>c.managed);
        if(!state.competitions.some(c=>c.id===state.selected))state.selected=state.competitions[0]?.id||null;
        renderCompTabs();if(state.selected)await loadCompetition(state.selected);
      }
      else if(key==='inbox'){state.inbox=data;renderUpdates();}
      else if(key==='news'){state.news=data;renderUpdates();}
    }));
    if(serial!==sequence)return;
    state.loading=false;
    if(!state.squad){get('.tsui-club-name').textContent='Conect\u00e1 el juego para ver tu club';get('.tsui-status-grid').innerHTML='<p class="tsui-empty">Inici\u00e1 la interfaz de Windows para cargar el plantel.</p>';}
  }
  let refreshTimer=null;
  function scheduleRefresh(){if(refreshTimer)clearTimeout(refreshTimer);refreshTimer=setTimeout(()=>{refreshTimer=null;refresh();},90);}
  host.addEventListener('click',event=>{
    const tab=event.target.closest('[data-tsui-competition]');if(tab){loadCompetition(tab.dataset.tsuiCompetition);return;}
    const activity=event.target.closest('[data-tsui-activity]');if(activity){state.activity=activity.dataset.tsuiActivity;renderUpdates();return;}
    const story=event.target.closest('[data-tsui-news]');if(story){window.FMNews?.openStory?.(story.dataset.tsuiNews);return;}
    const route=event.target.closest('[data-tsui-route]');if(route){safeRoute(route.dataset.tsuiRoute);return;}
    const player=event.target.closest('[data-tsui-player]');if(player){window.FMNavigation?.history('player',player.dataset.tsuiPlayer);return;}
    const club=event.target.closest('[data-tsui-club]');if(club){window.FMNavigation?.club(club.dataset.tsuiClub);return;}
    if(event.target.closest('[data-tsui-retry]'))loadCompetition(state.selected);
  });
  window.addEventListener('fm-ui-home-refresh',scheduleRefresh);
  window.addEventListener('fm-identity-ready',()=>{if(state.clubId)renderIdentity();});
  initialMarkup();
  window.FMClubIdentity?.ready.then(()=>{if(state.clubId)renderIdentity();});
  refresh();
  window.FMUIHome=Object.freeze({refresh,selectedCompetition:()=>state.selected,clubId:()=>state.clubId});
})();
