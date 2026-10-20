'use strict';
/* UI-3.1 portable viewer: live Python squad in Home/Squad/Tactics,
 * with live career news sourced from the Python world ledger. No npm required. */
(() => {
  const $ = (selector, root = document) => root.querySelector(selector);
  const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];
  const svg = (name, size = 18) => {
    const paths = {
      close: '<path d="M18 6 6 18M6 6l12 12"/>',
      check: '<path d="m4 12 5 5L20 6"/>',
      chevron: '<path d="m9 5 7 7-7 7"/>',
      alert: '<path d="M12 3 2 21h20L12 3ZM12 9v5M12 17h.01"/>',
      trophy: '<path d="M7 3h10v8a5 5 0 0 1-10 0V3ZM7 5H3v3a4 4 0 0 0 4 4M17 5h4v3a4 4 0 0 0 4-4M12 16v5M8 21h8"/>',
      football: '<circle cx="12" cy="12" r="9"/><path d="m7 7 3 3 7-3-2 6 3 4-6-1-5 2 1-7z"/>',
      news: '<rect x="3" y="3" width="18" height="18" rx="2"/><path d="M7 7h10M7 11h10M7 15h5"/>',
      home: '<path d="m3 10 9-7 9 7v11H3zM9 21v-8h6v8"/>'
    };
    return `<svg viewBox="0 0 24 24" width="${size}" height="${size}" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">${paths[name] || paths.chevron}</svg>`;
  };
  const escapeHtml = value => String(value).replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
  const decimal = value => typeof value === 'number' && Number.isFinite(value) ? value.toFixed(1).replace('.', ',') : '—';
  const grade = value => value >= 85 ? 'fm-grade-top' : value >= 75 ? 'fm-grade-good' : value >= 60 ? 'fm-grade-mid' : 'fm-grade-low';
  const dateLabel = value => /^\d{4}-\d{2}-\d{2}$/.test(value || '') ? new Intl.DateTimeFormat('en-GB',{weekday:'short',day:'2-digit',month:'short',year:'numeric',timeZone:'UTC'}).format(new Date(`${value}T12:00:00Z`)) : 'Date unavailable';

  function showModal({title, detail, category = 'FM Project'}) {
    $('.modal-backdrop')?.remove();
    const backdrop = document.createElement('div');
    backdrop.className = 'modal-backdrop';
    backdrop.innerHTML = `<section class="modal" role="dialog" aria-modal="true" aria-labelledby="portable-dialog-title">
      <div class="modal-top"><span class="modal-category"></span><button aria-label="Close dialog" class="icon-button" type="button">${svg('close', 20)}</button></div>
      <h2 id="portable-dialog-title"></h2><p></p>
      <div class="modal-footer"><button type="button" class="action-green">Got it ${svg('check',17)}</button></div>
      </section>`;
    $('.modal-category', backdrop).textContent = category;
    $('h2', backdrop).textContent = title;
    $('p', backdrop).textContent = detail;
    const close = () => {
      backdrop.remove();
      document.removeEventListener('keydown', esc);
    };
    const esc = event => { if (event.key === 'Escape') close(); };
    $('button.icon-button', backdrop).addEventListener('click', close);
    $('button.action-green', backdrop).addEventListener('click', close);
    backdrop.addEventListener('mousedown', event => { if (event.target === backdrop) close(); });
    document.addEventListener('keydown', esc);
    document.body.append(backdrop);
    $('button.icon-button', backdrop).focus();
  }

  let pythonHome = null;
  let homeFetchSerial = 0;
  function homeStatus(value){
    const v=Number(value);
    return v>=85?'Excellent':v>=75?'Very good':v>=60?'Good':'Needs attention';
  }
  function updateHomeFromPython(data){
    if(!data || !Array.isArray(data.starters) || !Array.isArray(data.slots) || data.starters.length!==11) return;
    pythonHome=data;
    const pitch=$('.tactics-card .pitch');
    const board=window.FMTacticalBoard?.place(data,'in_possession');
    if(!pitch || !board || !window.FMPortraits) return;
    $$('.pitch-player',pitch).forEach(el=>el.remove());
    const players=new Map(data.starters.map(player=>[player.slot_id,player]));
    for(const slot of data.slots){
      const player=players.get(slot.slot_id);
      const position=board[slot.slot_id];
      if(!player || !position)continue;
      const el=document.createElement('div');
      el.className='pitch-player fm-home-live-player';
      el.style.left=`${position.x}%`;
      el.style.top=`${position.y}%`;
      el.title=`${player.name} · ${player.position} · OVR ${decimal(player.ovr)} · ACT ${decimal(player.act)}`;
      el.innerHTML=`<div class="player-photo">${window.FMPortraits.portrait(player,'fm-face-home')}<span class="ovr-tag ${grade(player.act)} ts22-home-rating">${decimal(player.act)}<small>GRL</small></span></div><div class="pitch-name">${escapeHtml(player.short_name||player.name)}</div><div class="pitch-position">${escapeHtml(player.position)}</div>`;
      pitch.append(el);
    }
    pitch.setAttribute('aria-label',`${data.starters.length} live Python players in ${data.formation.name}. Current GRL labels use one decimal.`);
    $('.formation-name strong').textContent=data.formation.name;
    const selected=$('.formation-diagnostics .lineup-ready');
    if(selected)selected.textContent=`✓ ${data.starters.length}/11 selected`;
    const tired=$('.formation-diagnostics .lineup-alert');
    if(tired)tired.textContent=data.squad_status.tired ? `⚠ ${data.squad_status.tired} tired players` : '✓ No fitness alerts';
    const statuses=['morale','condition','chemistry','form'];
    $$('.mini-metrics .metric-tile').forEach((tile,i)=>{
      const score=data.squad_status[statuses[i]];
      if(typeof score !== 'number')return;
      const label=tile.querySelector('.metric-detail strong');
      const value=tile.querySelector('.metric-bottom > span');
      const fill=tile.querySelector('.metric-fill');
      if(label)label.textContent=homeStatus(score);
      if(value)value.textContent=decimal(score);
      if(fill)fill.style.width=`${Math.max(0,Math.min(100,score))}%`;
      tile.title=`${statuses[i]}: ${decimal(score)} / 100 (live Python)`;
    });
    const date=data.date;
    const dateText=dateLabel(date);
    $('.club-identity small').textContent=dateText;
    $('.sidebar-bottom strong').textContent=dateText;
    const club=data.club||'Club';
    $$('.hero-primary h2, .club-identity strong').forEach(el=>el.textContent=club);
    // Country/competition/club hero assets remain aesthetic preview values; remove
    // season table claims that would otherwise contradict the new development date.
    const heroStats=$$('.hero-highlights > div');
    if(heroStats.length>=3){
      heroStats[0].querySelector('strong').textContent='—';
      heroStats[0].querySelector('span').textContent='League position pending';
      heroStats[1].querySelector('strong').textContent='—';
      heroStats[1].querySelector('span').textContent='Points pending';
      heroStats[2].innerHTML='<span>Match form</span><span class="fm-home-no-form">No completed fixtures in this DEV session</span>';
    }
    const seasonFact=$('.hero-footer .hero-fact strong');
    if(seasonFact){const year=Number(date.slice(0,4));seasonFact.textContent= date.slice(5,7)>='07' ? `${year}/${String(year+1).slice(-2)}` : `${year-1}/${String(year).slice(-2)}`;}
    const teams=$$('.next-match .versus-team');
    const fixture=data.next_match||'Next fixture not available';
    const match=fixture.match(/^(.+?)\s+vs\s+(.+)$/i);
    if(teams.length===2){
      teams[0].querySelector('strong').textContent=club;
      const opponent=match?(match[1]===club?match[2]:match[1]):fixture;
      teams[1].querySelector('strong').textContent=opponent;
      const emblem=teams[1].querySelector('svg');
      if(emblem){
        const badge=document.createElement('div');badge.className='fm-opponent-badge';badge.textContent=opponent.split(' ').map(s=>s[0]||'').slice(0,2).join('').toUpperCase();
        emblem.replaceWith(badge);
      } else {const badge=teams[1].querySelector('.fm-opponent-badge');if(badge)badge.textContent=opponent.split(' ').map(s=>s[0]||'').slice(0,2).join('').toUpperCase();}
    }
    const details=$$('.next-match .match-bottom > span');
    if(details.length>=3){details[0].textContent='Python DEV fixture';details[1].textContent='Time TBD';details[2].textContent='Venue TBD';}
    $('.next-match .action-green').title='Open Calendar to inspect the next scheduled fixture';
    $('.preview-label').textContent='UI-3.5 · LIVE PYTHON';
    $('.tactics-caption').textContent='Illustrated portraits are placeholders · Names, current GRL and team metrics come from the Python session';
    $('.app-footer span:first-child').textContent='FM Project · UI-3.5 Python DEV session';
    $('.app-footer span:last-child').textContent='Live Python world progression · verified news · manual save required';
    window.FMClubIdentity?.applyShell(data.club_id,data.club);
    // Continue is managed separately by the authoritative /api/progression service.
  }
  async function refreshHome(){
    const serial=++homeFetchSerial;
    try{
      const response=await fetch('/api/squad',{cache:'no-store'});
      if(!response.ok)throw Error(`Python ${response.status}`);
      const snapshot=await response.json();
      if(serial===homeFetchSerial){
        updateHomeFromPython(snapshot);
        refreshHomeWorldData(serial);
        window.FMNews?.refresh();
      }
    }catch(err){
      if(serial!==homeFetchSerial)return;
      console.warn('Home: live Python data unavailable',err);
      $('.preview-label').textContent='PYTHON OFFLINE · UI DEMO';
      // Never present the old static XI as the active roster if the server is down.
      $$('.pitch-player', $('.tactics-card .pitch')).forEach(el=>el.remove());
      $('.formation-name strong').textContent='Python session unavailable';
      const note=$('.tactics-caption');if(note)note.textContent='Start with INICIAR_INTERFAZ_WINDOWS.bat to load real squad data.';
    }
  }

  const navButtons = $$('.sidebar .nav-item');
  const dashboard = $('.dashboard-grid');
  const main = $('.main-content');
  const footer = $('.app-footer');
  const headerTitle = $('.header-left h1');
  const headerSubhead = $('.header-left p');
  const continueControl = $('.continue-button');
  let progressionState = null;
  let progressionBusy = false;
  let progressionRequest = 0;
  function renderProgression(state){
    if(!state)return;
    progressionState=state;
    $('.club-identity small').textContent=dateLabel(state.date);
    $('.sidebar-bottom strong').textContent=dateLabel(state.date);
    continueControl.innerHTML=`${escapeHtml(state.button_label)} ${svg('chevron',20)}`;
    continueControl.disabled=progressionBusy || (state.season_complete && !state.match_day);
    continueControl.title=state.match_day
      ?'Your match is due. Open Match Center inside the game.'
      :'Advance exactly one day in the Python world';
  }
  async function refreshProgression(){
    if(progressionBusy)return;
    const serial=++progressionRequest;
    try{
      const response=await fetch('/api/progression',{cache:'no-store'});
      if(!response.ok)throw Error(`Progression HTTP ${response.status}`);
      const state=await response.json();
      if(serial===progressionRequest)renderProgression(state);
    }catch(error){
      if(serial!==progressionRequest)return;
      continueControl.disabled=true;
      continueControl.title='Start the Python server to enable world progression';
      console.warn('Python progression unavailable',error);
    }
  }
  async function submitProgression(action,extra={}){
    if(progressionBusy)return null;
    progressionBusy=true;
    ++progressionRequest;
    continueControl.disabled=true;
    continueControl.textContent=action==='simulate_until'?'Simulating...':'Advancing...';
    try{
      let payload;
      if(action==='simulate_until'){
        if(!window.FMSimulationOverlay?.run)throw Error('Simulation progress UI unavailable');
        payload=await window.FMSimulationOverlay.run(extra.date);
      }else{
        const response=await fetch('/api/progression',{
          method:'POST',headers:{'Content-Type':'application/json'},
          body:JSON.stringify({action,...extra})
        });
        payload=await response.json();
        if(!response.ok)throw Error(payload.error || `Python HTTP ${response.status}`);
      }
      renderProgression(payload.state);
      if(dashboard.style.display!=='none')refreshHome();
      window.FMInbox?.refresh();
      if(calendarPanel.style.display!=='none')window.FMCalendar?.refresh();
      if(dressingPanel.style.display!=='none')window.FMDressingRoom?.refresh();
    if(supportPanel.style.display!=='none')window.FMSupport?.refresh();
    if(youthPanel.style.display!=='none')window.FMYouthAcademy?.refresh();
      if(youthPanel.style.display!=='none')window.FMYouthAcademy?.refresh();
      if(financesPanel.style.display!=='none')window.FMFinances?.refresh();
      if(transfersPanel.style.display!=='none')window.FMTransfers?.refresh();
      if(competitionPanel.style.display!=='none'){
        const other=$('.sidebar .nav-item.is-active span')?.textContent.trim()==='Other Leagues';
        window.FMCompetitions?.mount(competitionPanel,other?'other':'mine');
      }
      if(squadFrame.style.display!=='none'){
        const active=$('.sidebar .nav-item.is-active span')?.textContent.trim();
        const view=active==='Tactics'?'tactics':'squad';
        squadFrame.src=`../public/squad/embed.html?view=${view}&world=${encodeURIComponent(payload.state.date)}`;
      }
      return payload;
    }catch(error){
      showModal({title:'Progression status',category:action==='simulate_until'?'Check Python server':'No partial changes committed',
        detail:String(error.message||error)});
      return null;
    }finally{
      progressionBusy=false;
      await refreshProgression();
    }
  }
  window.FMProgression={
    state:()=>progressionState,
    refresh:refreshProgression,
    simulateUntil:date=>submitProgression('simulate_until',{date})
  };
  // UI-1 Home is explicitly sample data, but shares the global rating format.
  $$('.ovr-tag').forEach(tag => {
    const value=Number(tag.textContent.trim().replace(',', '.'));
    if (!Number.isFinite(value)) return;
    const label=value.toFixed(1).replace('.', ',');
    tag.textContent=label;
    tag.setAttribute('aria-label', `OVR ${label}`);
  });
  const squadFrame = document.createElement('iframe');
  squadFrame.className = 'fm-squad-frame';
  squadFrame.title = 'Squad roster and team tactics';
  squadFrame.style.display = 'none';
  main.insertBefore(squadFrame, footer);
  const dressingPanel=document.createElement('section');
  dressingPanel.className='fm-dressing-room-screen';
  dressingPanel.style.display='none';
  main.insertBefore(dressingPanel,footer);
  const youthPanel=document.createElement('section');
  youthPanel.className='fm-youth-academy-screen';youthPanel.style.display='none';
  main.insertBefore(youthPanel,footer);
  const transfersPanel=document.createElement('section');
  transfersPanel.className='fm-transfers-screen';transfersPanel.style.display='none';
  main.insertBefore(transfersPanel,footer);
  const supportPanel=document.createElement('section');
  supportPanel.className='fm-club-support-screen';supportPanel.style.display='none';
  main.insertBefore(supportPanel,footer);
  const inboxPanel=document.createElement('section');
  inboxPanel.className='fm-inbox-screen';inboxPanel.style.display='none';
  main.insertBefore(inboxPanel,footer);
  const financesPanel=document.createElement('section');
  financesPanel.className='fm-finances-screen';financesPanel.style.display='none';
  main.insertBefore(financesPanel,footer);
  const calendarPanel=document.createElement('section');
  calendarPanel.className='fm-calendar-screen';
  calendarPanel.style.display='none';
  main.insertBefore(calendarPanel,footer);
  const competitionPanel=document.createElement('section');
  competitionPanel.className='fm-competitions-screen';
  competitionPanel.style.display='none';
  main.insertBefore(competitionPanel,footer);
  const historyPanel=document.createElement('section');historyPanel.className='fm-history-screen';historyPanel.style.display='none';main.insertBefore(historyPanel,footer);
  const matchFrame=document.createElement('iframe');
  matchFrame.id='fm-match-frame';matchFrame.className='ts22-match-frame';matchFrame.title='Match Center';matchFrame.style.display='none';main.insertBefore(matchFrame,footer);
  const clubFrame=document.createElement('iframe');
  clubFrame.id='fm-club-frame';clubFrame.className='ts22-club-frame';clubFrame.title='Club squad profile';clubFrame.style.display='none';main.insertBefore(clubFrame,footer);
  const routeBack=document.createElement('button');routeBack.type='button';routeBack.className='ts22-route-back';routeBack.textContent='Back';routeBack.hidden=true;
  $('.header-left').prepend(routeBack);
  let routeState={page:'Home'};
  let negotiationOrigin='Scouting';
  function goBack(){if(history.state?.fm22&&history.state.depth>0)history.back();
    else navigate(routeState.page==='Negotiation'?'Scouting':'Home');}
  routeBack.addEventListener('click',goBack);
  const placeholder = document.createElement('section');
  placeholder.className = 'panel placeholder-page';
  placeholder.style.display = 'none';
  placeholder.innerHTML = `<div class="placeholder-emblem">${svg('football', 46)}</div><span class="eyebrow">UPCOMING SECTION</span><h2></h2><p>This section is not available in the current UI increment. The Python simulation is untouched.</p><button class="action-green" type="button">${svg('home',17)} Back to Home</button>`;
  main.insertBefore(placeholder, footer);

  function loadFrame(frame, src){
    const url=new URL(src, location.href).href;
    if(frame.dataset.route===url){
      if(src.includes('/squad/'))frame.contentWindow?.postMessage({type:'fm-squad-refresh'},location.origin);
      return;
    }
    frame.dataset.route=url;
    // Child navigations must not create extra entries in the joint browser
    // history; Back belongs to the application route, not a previous iframe.
    if(frame.contentWindow)frame.contentWindow.location.replace(url);
    else frame.src=url;
  }
  function navigate(page, fromFrame = false, extra = {}, record = true) {
    if(page==='Transfers')page='Scouting'; // Restore historic TS-24.3 bookmarks.
    if(routeState.page==='Home'&&page!=='Home')window.FMHomeCompetition?.reset();
    if(page==='Negotiation'&&routeState.page!=='Negotiation')
      negotiationOrigin=routeState.page==='Club Profile'?'player profile':'Scouting';
    routeState={page,...extra};
    const hash=page==='Match Center'?'#match/'+encodeURIComponent(extra.fixture||''):
      page==='Club Profile'?'#club/'+encodeURIComponent(extra.club||'')+(extra.player?'/'+encodeURIComponent(extra.player):''):
      page==='Career History'?'#history/'+encodeURIComponent(extra.entity||'')+'/'+encodeURIComponent(extra.id||''):
      page==='Negotiation'?'#negotiation/'+(extra.deal?'deal/':'player/')+encodeURIComponent(extra.deal||extra.player||''):
      '#page/'+encodeURIComponent(page)+(extra.competition?'/'+encodeURIComponent(extra.competition):'');
    if(record && location.hash!==hash){const depth=(history.state?.fm22?history.state.depth:-1)+1;history.pushState({fm22:true,depth},'',hash);}
    const matchPage=page==='Match Center',clubPage=page==='Club Profile';
    const negotiationPage=page==='Negotiation';
    document.body.classList.toggle('tr-negotiation-open',negotiationPage);
    document.body.classList.toggle('ts22-match-open',matchPage);
    matchFrame.style.display=matchPage?'block':'none';clubFrame.style.display=clubPage?'block':'none';routeBack.hidden=!clubPage && page!=='Career History';
    if(matchPage){const src=`match.html?embedded=1&fixture=${encodeURIComponent(extra.fixture||'')}`;loadFrame(matchFrame,src);}
    if(clubPage){const src=`../public/squad/embed.html?view=squad&club=${encodeURIComponent(extra.club||'')}${extra.player?'&player='+encodeURIComponent(extra.player):''}`;loadFrame(clubFrame,src);}

    const home = page === 'Home';
    const squad = page === 'Squad' || page === 'Tactics';
    const calendar = page === 'Calendar';
    const dressingRoom = page === 'Dressing Room';
    const inbox = page === 'Inbox';
    const clubSupport = ['Staff','Training','Medical Centre'].includes(page);
    const youthAcademy = page === 'Youth Academy';
    const finances = page === 'Finances';
    const transfers = page === 'Scouting' || negotiationPage;
    const competitions = page === 'Competitions';
    const otherLeagues = page === 'Other Leagues';
    const competitionPage = competitions || otherLeagues;
    const careerPage = page === 'Career History';
    const clubInfoPage = page === 'Club Info';
    navButtons.forEach(button => {
      const selected = $('span', button)?.textContent.trim() === page;
      button.classList.toggle('is-active', selected);
      if (selected) button.setAttribute('aria-current', 'page');
      else button.removeAttribute('aria-current');
    });
    dashboard.style.display = home ? '' : 'none';
    placeholder.style.display = !home && !squad && !calendar && !competitionPage && !dressingRoom && !inbox && !clubSupport && !youthAcademy && !finances && !transfers && !matchPage && !clubPage && !careerPage && !clubInfoPage ? 'flex' : 'none';
    supportPanel.style.display = clubSupport ? 'block' : 'none';
    if(clubSupport)window.FMSupport?.mount(supportPanel,page==='Staff'?'staff':page==='Training'?'training':'medical');
    dressingPanel.style.display = dressingRoom ? 'block' : 'none';
    inboxPanel.style.display = inbox ? 'block' : 'none';
    if(inbox)window.FMInbox?.mount(inboxPanel,extra.player||null);
    youthPanel.style.display = youthAcademy ? 'block' : 'none';
    transfersPanel.style.display = transfers ? 'block' : 'none';
    if(transfers)window.FMTransfers?.mount(transfersPanel,{view:negotiationPage?'negotiation':'scouting',
      playerId:extra.player||null,dealId:extra.deal||null,tab:extra.tab||null});
    financesPanel.style.display = finances ? 'block' : 'none';
    if(finances) window.FMFinances?.mount(financesPanel);
    if(youthAcademy)window.FMYouthAcademy?.mount(youthPanel);
    if(dressingRoom) window.FMDressingRoom?.mount(dressingPanel);
    calendarPanel.style.display = calendar ? 'block' : 'none';
    if(calendar) window.FMCalendar?.mount(calendarPanel);
    competitionPanel.style.display = competitionPage ? 'block' : 'none';
    historyPanel.style.display = careerPage || clubInfoPage ? 'block' : 'none';
    // Never fail silently if an asset was not loaded or the career is unavailable.
    function showHistory(type,id){
      if(!type||!id){
        historyPanel.innerHTML='<section class="ch-card" role="alert"><h3>History unavailable</h3><p>No player or club was selected.</p></section>';
      }else if(typeof window.FMHistory?.mount !== 'function'){
        historyPanel.innerHTML='<section class="ch-card" role="alert"><h3>History module failed to load</h3><p>Reload the game page and verify that the latest patch files were copied into the portable folder.</p></section>';
      }else window.FMHistory.mount(historyPanel,type,id);
    }
    if(careerPage)showHistory(extra.entity,extra.id);
    if(clubInfoPage){
      if(pythonHome?.club_id)showHistory('club',pythonHome.club_id);
      else {
        historyPanel.innerHTML='<div class="ch-loading">Loading your club information…</div>';
        fetch('/api/squad',{cache:'no-store'}).then(r=>{
          if(!r.ok)throw Error('Club information request failed');
          return r.json();
        }).then(v=>{if(routeState.page==='Club Info')showHistory('club',v.club_id);})
          .catch(()=>{if(routeState.page==='Club Info')historyPanel.innerHTML='<section class="ch-card" role="alert"><h3>Club information unavailable</h3><p>Could not read the current club from the local game server. Try reloading the page.</p></section>';});
      }
    }
    if(competitionPage) window.FMCompetitions?.mount(competitionPanel, otherLeagues ? 'other' : 'mine', extra.competition);
    squadFrame.style.display = squad ? 'block' : 'none';
    if (squad && !fromFrame) {
      const src = `../public/squad/embed.html?view=${page === 'Tactics' ? 'tactics' : 'squad'}`;
      loadFrame(squadFrame,src);
    }
    $('.preview-label').textContent = 'UI-3.5 · PYTHON DEV';
    refreshProgression();
    document.body.classList.toggle('tsui-home-active',home);
    document.body.classList.toggle('tsui-squad-active',page==='Squad');
    if (home) { refreshHome();window.dispatchEvent(new CustomEvent('fm-ui-home-refresh')); }
    headerTitle.textContent = page;
    headerSubhead.textContent = home
      ? 'Live results, fixtures and verified football news from your career.'
      : squad ? (page==='Squad' ? 'Sortable roster, full player attributes, recorded season statistics and player management.' : 'Formation, individual roles and team tactics backed by the Python development session.')
      : careerPage ? 'Permanent player, club and competition archive. Verified career facts only.'
      : clubInfoPage ? 'Club identity, current squad, staffing capacity, records and verified historical results.'
      : clubPage ? 'Persistent squad, player profiles and recorded club information. Read-only.'
      : clubSupport ? (page==='Staff'?'Hire coaching, medical and fitness specialists.':page==='Training'?'Configure squad groups and automatic physical protection.':'Injury timelines, recovery treatments and player opinions.')
      : inbox ? 'Live club messages, scouting reports, medical news and player conversations.'
      : youthAcademy ? 'U15 preview, automated U17/U21 leagues and quarterly scouting.'
      : negotiationPage ? 'Dedicated negotiation: guaranteed fees, optional clauses and club replies.'
      : transfers ? 'Search professional players and manage your club negotiations.'
      : finances ? 'Club cash, transfer allocation, wage budget and registered player contracts.'
      : dressingRoom ? 'Automatic hierarchy, working relationships and quiet squad dynamics. No micromanagement required.'
      : calendar ? 'View club fixtures and recorded results. Dates and opponents come from the Python world calendar.'
      : competitions ? 'Your club competitions, standings, fixtures and confirmed cup brackets.'
      : otherLeagues ? 'Browse other leagues and cups by continent, country and division.'
      : 'This section is planned for a future update.';
    if (!home && !squad && !calendar && !competitionPage && !dressingRoom && !inbox && !clubSupport && !youthAcademy && !finances && !transfers) $('h2', placeholder).textContent = page;
    window.scrollTo({top:0, behavior:'auto'});
  }
  window.addEventListener('message', event => {
    if (event.source !== squadFrame.contentWindow || event.origin !== window.location.origin) return;
    if (event.data?.type === 'fm-open-youth-academy') { navigate('Youth Academy'); return; }
    if (event.data?.type === 'fm-open-finances') { navigate('Finances'); return; }
    if (event.data?.type === 'fm-squad-open-section' && ['Dressing Room','Training','Medical Centre','Tactics'].includes(event.data.page)) { navigate(event.data.page); return; }
    if (event.data?.type === 'fm-squad-state' && /^\d{4}-\d{2}-\d{2}$/.test(event.data.date)) {
      $('.club-identity small').textContent = dateLabel(event.data.date);
      $('.sidebar-bottom strong').textContent = dateLabel(event.data.date);
      if (dashboard.style.display !== 'none') refreshHome();
    }
    if (squadFrame.style.display!=='none' && event.data?.type === 'fm-squad-route') navigate(event.data.page === 'tactics' ? 'Tactics' : 'Squad', true);
  });
  window.addEventListener('message',event => {
    if(event.origin!==window.location.origin || event.source!==matchFrame.contentWindow || event.data?.type!=='fm-match-world-changed')return;
    refreshProgression();
    if(dashboard.style.display!=='none')refreshHome();
    window.FMInbox?.refresh();
    if(supportPanel.style.display!=='none')window.FMSupport?.refresh();
    if(calendarPanel.style.display!=='none')window.FMCalendar?.refresh();
    if(dressingPanel.style.display!=='none')window.FMDressingRoom?.refresh();
    if(supportPanel.style.display!=='none')window.FMSupport?.refresh();
    if(youthPanel.style.display!=='none')window.FMYouthAcademy?.refresh();
    if(financesPanel.style.display!=='none')window.FMFinances?.refresh();
      if(transfersPanel.style.display!=='none')window.FMTransfers?.refresh();
    if(competitionPanel.style.display!=='none'){
      const other=$('.sidebar .nav-item.is-active span')?.textContent.trim()==='Other Leagues';
      window.FMCompetitions?.mount(competitionPanel, other?'other':'mine');
    }
    if(squadFrame.style.display!=='none')squadFrame.contentWindow?.location.reload();
  });
  window.addEventListener('focus', () => {
    if(dressingPanel.style.display!=='none')window.FMDressingRoom?.refresh();
    if(supportPanel.style.display!=='none')window.FMSupport?.refresh();
    if(youthPanel.style.display!=='none')window.FMYouthAcademy?.refresh();
    if(financesPanel.style.display!=='none')window.FMFinances?.refresh();
      if(transfersPanel.style.display!=='none')window.FMTransfers?.refresh();
  });
  navButtons.forEach(button => button.addEventListener('click', () => navigate($('span',button).textContent.trim())));
  $('button.action-green', placeholder).addEventListener('click', () => navigate('Home'));
  $('.tactics-card .text-action').addEventListener('click', () => navigate('Tactics'));

  $('.continue-button').addEventListener('click', async () => {
    if(progressionBusy)return;
    if(!progressionState){await refreshProgression();return;}
    if(progressionState.match_day){
      const match=progressionState.pending_match;
      navigate('Match Center',false,{fixture:match?.id||''});
      return;
    }
    await submitProgression('advance_day');
  });
  $('.header-icon-button').addEventListener('click', () => showModal({
    title:'About UI-3.5', category:'Python DEV · Daily Progression',
    detail:'Continue advances exactly one day. On matchday it opens Match Center in this tab. Calendar auto-simulates through your own fixtures and advances to the selected date. Complete career save slots are available through the Python save API; this screen does not auto-save.'
  }));
  $('.next-match .action-green').addEventListener('click', () => navigate('Calendar'));

  async function refreshHomeWorldData(serial){
    try{
      const [competitionResponse,calendarResponse]=await Promise.all([
        fetch('/api/competitions',{cache:'no-store'}),
        fetch('/api/calendar',{cache:'no-store'})
      ]);
      if(!competitionResponse.ok || !calendarResponse.ok)throw Error('World view API unavailable');
      const index=await competitionResponse.json();
      const calendar=await calendarResponse.json();
      if(serial!==homeFetchSerial)return;
      const leagueItem=index.competitions?.find(c=>c.kind==='league'&&c.managed);
      if(leagueItem){
        const response=await fetch(`/api/competitions/${encodeURIComponent(leagueItem.id)}`,{cache:'no-store'});
        if(!response.ok)throw Error('League table unavailable');
        const leagueModel=await response.json();
        if(serial!==homeFetchSerial)return;
        renderHomeLeague(leagueModel);
      }
      window.FMHomeCompetition?.refresh();
      const managedId=index.managed_id;
      document.querySelectorAll('.club-identity, .hero-primary h2').forEach(el=>{el.dataset.clubId=managedId;el.tabIndex=0;el.setAttribute('role','link');});
      const results=calendar.matches.filter(g=>g.score&&g.date<=calendar.date).sort((a,b)=>a.date.localeCompare(b.date));
      const last5=results.slice(-5);
      const hero=$$('.hero-highlights > div');
      if(hero.length>=3){
        hero[2].innerHTML='<span>Recent form</span>'+(last5.length
          ?`<span class="recent-form">${last5.map(g=>`<b class="${g.outcome==='V'?'win':g.outcome==='E'?'draw':'loss'}">${g.outcome==='V'?'W':g.outcome==='E'?'D':'L'}</b>`).join('')}</span>`
          :'<span class="fm-home-no-form">No played matches</span>');
      }
      const next=calendar.matches.find(g=>!g.score && g.date>=calendar.date);
      if(next){
        const ids=[managedId,next.opponent_id];
        $$('.next-match .versus-team').forEach((el,i)=>{el.dataset.clubId=ids[i];el.tabIndex=0;el.setAttribute('role','link');});
        const teams=$$('.next-match .versus-team');if(teams.length===2){teams[0].querySelector('small').textContent=next.home?'Home':'Away';teams[1].querySelector('small').textContent=next.home?'Away':'Home';}
        const meta=$$('.next-match .match-bottom > span');
        if(meta.length>=3){
          meta[0].textContent=next.date;
          meta[1].textContent=next.kickoff?next.kickoff.slice(11,16)+' UTC':'Time TBD';
          meta[2].textContent=next.competition;
        }
      }
    }catch(error){console.warn('Home world summary unavailable',error);}
  }
  
  function renderHomeLeague(data){
    if(!Array.isArray(data.table))return;
    const table=data.table;
    const hero=$$('.hero-highlights > div');
    const managed=table.find(r=>r.managed);
    if(managed&&hero.length>=2){
      hero[0].querySelector('strong').textContent=ordinal(managed.position);
      hero[0].querySelector('span').textContent='League position';
      hero[1].querySelector('strong').textContent=String(managed.points);
      hero[1].querySelector('span').textContent='Points';
    }
  }
  function ordinal(n){return n===1?'1st':n===2?'2nd':n===3?'3rd':`${n}th`;}
  const league = $('.league-card');
  const clubCrest = $('.league-row .row-club svg')?.outerHTML || '';

  refreshHome();
  refreshProgression();
  const activityPanel = $('#activity-panel');
  const inboxButton = $('#activity-inbox');
  const storiesButton = $('#activity-stories');
  function activityTab(view){
    const live = view === 'inbox';
    inboxButton.classList.toggle('active',live);
    storiesButton.classList.toggle('active',!live);
    inboxButton.setAttribute('aria-selected',String(live));
    storiesButton.setAttribute('aria-selected',String(!live));
    activityPanel.setAttribute('aria-labelledby',live?'activity-inbox':'activity-stories');
    if(live)window.FMInbox?.renderHome(activityPanel);
    else window.FMNews?.renderPanel(activityPanel);
  }
  inboxButton.addEventListener('click',()=>activityTab('inbox'));
  storiesButton.addEventListener('click',()=>activityTab('stories'));
  $('.inbox-card .text-action').addEventListener('click',()=>{if(storiesButton.classList.contains('active'))window.FMNews?.renderPanel(activityPanel);else navigate('Inbox');});
  $('.club-news .text-action').addEventListener('click',()=>activityTab('stories'));
  activityTab('inbox');
  window.FMInbox?.refresh();

  window.FMNavigation={
    navigate,club:(id,player)=>navigate('Club Profile',false,{club:id,player}),
    history:(entity,id)=>navigate('Career History',false,{entity,id}),
    competition:id=>navigate('Competitions',false,{competition:id}),
    match:id=>navigate('Match Center',false,{fixture:id}),back:goBack,
    negotiatePlayer:id=>navigate('Negotiation',false,{player:id}),
    negotiateDeal:(id,replace=false)=>{
      if(replace){
        const uri='#negotiation/deal/'+encodeURIComponent(id);
        history.replaceState(history.state||{fm22:true,depth:0},'',uri);
        navigate('Negotiation',false,{deal:id},false);
      }else navigate('Negotiation',false,{deal:id});
    },
    previousLabel:()=>negotiationOrigin
  };
  function readHash(){
    let parts;try{parts=location.hash.slice(1).split('/').map(decodeURIComponent);}catch(_){navigate('Home',false,{},false);return;}
    if(parts[0]==='history'&&['player','club','competition'].includes(parts[1])&&parts[2])navigate('Career History',false,{entity:parts[1],id:parts[2]},false);
    else if(parts[0]==='match')navigate('Match Center',false,{fixture:parts[1]||''},false);
    else if(parts[0]==='club'&&parts[1])navigate('Club Profile',false,{club:parts[1],player:parts[2]},false);
    else if(parts[0]==='negotiation'&&parts[2])navigate('Negotiation',false,
      parts[1]==='deal'?{deal:parts[2]}:{player:parts[2]},false);
    else {const allowed=navButtons.map(b=>$('span',b).textContent.trim());
      const target=parts[1]==='Transfers'?'Scouting':parts[1];
      navigate(allowed.includes(target)?target:'Home',false,{competition:parts[2]},false);}
  }
  window.addEventListener('popstate',readHash);
  if(!history.state?.fm22)history.replaceState({fm22:true,depth:0},'',location.href);
  if(location.hash)readHash();
  document.addEventListener('click',event=>{
    const link=event.target.closest('[data-career-type][data-career-id]');
    if(link&&['player','club','competition'].includes(link.dataset.careerType)&&link.dataset.careerId){event.preventDefault();event.stopPropagation();window.FMNavigation.history(link.dataset.careerType,link.dataset.careerId);return;}
    const target=event.target.closest('[data-club-id]');if(!target)return;
    event.preventDefault();event.stopPropagation();window.FMNavigation.club(target.dataset.clubId);
  });
  document.addEventListener('keydown',event=>{
    if(event.key==='Enter'&&event.target.matches('[data-club-id][role="link"]')){event.preventDefault();window.FMNavigation.club(event.target.dataset.clubId);}
  });
  window.addEventListener('message',event=>{
    if(event.origin!==location.origin||![matchFrame.contentWindow,clubFrame.contentWindow,squadFrame.contentWindow].includes(event.source))return;
    if(event.data?.type==='fm-open-club'&&typeof event.data.clubId==='string')window.FMNavigation.club(event.data.clubId,event.data.playerId);
    if(event.data?.type==='fm-open-history'&&['player','club','competition'].includes(event.data.entity)&&typeof event.data.id==='string'&&event.data.id)window.FMNavigation.history(event.data.entity,event.data.id);
    if(event.source===clubFrame.contentWindow&&event.data?.type==='fm-open-transfer-offer'
       &&typeof event.data.playerId==='string'&&event.data.playerId.length>0
       &&event.data.clubId===routeState.club){
      window.FMNavigation.negotiatePlayer(event.data.playerId);
    }
    if(event.data?.type==='fm-match-back'&&event.source===matchFrame.contentWindow)goBack();
    if(event.data?.type==='fm-match-return'&&event.source===matchFrame.contentWindow){matchFrame.contentWindow.location.replace('about:blank');delete matchFrame.dataset.route;navigate('Home');}
  });
})();
