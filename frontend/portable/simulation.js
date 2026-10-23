/* UI-3.4.1 hotfix: show only managed-club matches while the entire
   Python world continues to simulate. No invented scores or dates. */
window.FMSimulationOverlay = (() => {
  'use strict';
  const safe = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));
  const dateText = d => /^\d{4}-\d{2}-\d{2}$/.test(d||'')
    ? new Intl.DateTimeFormat('en-GB',{weekday:'short',day:'numeric',month:'short',year:'numeric',timeZone:'UTC'}).format(new Date(`${d}T12:00:00Z`))
    : 'Waiting for world progress';
  const competitionText = id => ({league:'Premier League','dev-premier':'Premier League','fa-cup':'FA Cup','carabao-cup':'Carabao Cup','champions-league':'Champions League','europa-league':'Europa League','conference-league':'Conference League','efl-trophy':'EFL Trophy'})[id] || String(id || 'Fixture').replace(/^dev-/,'').replace(/[-_]/g,' ');
  const clubBrand=(id,name)=>window.FMClubIdentity?.resolve?.(id,name)||{display_name:name||id||'Club',crest:null};
  const clubLabel=(id,name)=>safe(clubBrand(id,name).display_name);
  const clubCrest=(id,name)=>{
    const identity=clubBrand(id,name);
    if(!identity.crest)return `<span class="fm-sim-crest fm-sim-crest-fallback" aria-hidden="true">${safe((identity.short_name||identity.display_name||'C').split(/\s+/).slice(0,2).map(s=>s.charAt(0)).join('').toUpperCase())}</span>`;
    const src=window.FMEntityAssets?.url?.(identity.crest)||identity.crest;
    return `<img class="fm-sim-crest" data-fm-asset="optional" src="${safe(src)}" alt="" loading="lazy">`;
  };
  const compBrand=(id)=>{
    const brand=window.FMCompetitionBranding;
    const theme=brand?.resolve?.(id);
    return {logo:brand?.badge?.(id,'fm-sim-comp-logo')||'',
      colour:theme?.accent||'#79bce4'};
  };
  let active = false;
  let confirming = false;

  // This dialog is separate from the full-screen result feed. The fixture
  // count is only currently known club fixtures; future cup draws are unknown.
  function confirm({target, fromDate, knownMatches = 0}) {
    if(active || confirming) return Promise.resolve(false);
    if(!/^\d{4}-\d{2}-\d{2}$/.test(target || '') || !/^\d{4}-\d{2}-\d{2}$/.test(fromDate || '')) return Promise.resolve(false);
    confirming = true;
    const days = Math.round((Date.parse(`${target}T12:00:00Z`) - Date.parse(`${fromDate}T12:00:00Z`)) / 86400000) + 1;
    const count = Math.max(0, Number(knownMatches) || 0);
    const backdrop = document.createElement('div');
    backdrop.className = 'fm-sim-confirm-backdrop';
    backdrop.innerHTML = `<section class="fm-sim-confirm-dialog" role="dialog" aria-modal="true" aria-labelledby="fm-sim-confirm-title" aria-describedby="fm-sim-confirm-desc">
      <div class="fm-sim-confirm-head"><div class="fm-sim-confirm-icon" aria-hidden="true">↠</div><div>
        <span class="fm-sim-eyebrow">CAREER · CALENDAR</span>
        <h2 id="fm-sim-confirm-title">Simulate to this date?</h2></div></div>
      <p id="fm-sim-confirm-desc">The entire football world will advance, including your club's matches. Only <strong>your team's results</strong> will appear in the simulation feed.</p>
      <div class="fm-sim-confirm-stats">
        <div class="fm-sim-confirm-target"><small>SELECTED DATE</small><strong class="fm-sim-confirm-date"></strong><span class="fm-sim-confirm-from"></span></div>
        <div class="fm-sim-confirm-metrics"><span><strong class="fm-sim-confirm-days"></strong><small>DAYS TO PROCESS</small></span><span><strong class="fm-sim-confirm-matches"></strong><small>KNOWN CLUB FIXTURES</small></span></div>
      </div>
      <div class="fm-sim-confirm-notice"><span aria-hidden="true">ⓘ</span><p>More cup fixtures may be drawn during the simulation. Your DEV session is temporary, and this advance cannot be undone.</p></div>
      <div class="fm-sim-confirm-actions"><button type="button" class="fm-sim-confirm-cancel">Cancel</button><button type="button" class="fm-sim-confirm-accept">Start simulation <span aria-hidden="true">→</span></button></div>
    </section>`;
    backdrop.querySelector('.fm-sim-confirm-date').textContent=dateText(target);
    backdrop.querySelector('.fm-sim-confirm-from').textContent=`From ${dateText(fromDate)}`;
    backdrop.querySelector('.fm-sim-confirm-days').textContent=Math.max(0,days).toLocaleString('en-GB');
    backdrop.querySelector('.fm-sim-confirm-matches').textContent=count.toLocaleString('en-GB');
    const cancel = backdrop.querySelector('.fm-sim-confirm-cancel');
    const accept = backdrop.querySelector('.fm-sim-confirm-accept');
    const previousFocus = document.activeElement;
    document.body.appendChild(backdrop);
    cancel.focus();
    return new Promise(resolve => {
      const finish = answer => {
        document.removeEventListener('keydown', keydown, true);
        backdrop.remove();
        confirming = false;
        if(previousFocus?.isConnected && typeof previousFocus.focus==='function') previousFocus.focus();
        resolve(answer);
      };
      const keydown = event => {
        if(event.key === 'Escape'){event.preventDefault();finish(false);}
        else if(event.key === 'Tab'){
          const first=cancel, last=accept;
          if(event.shiftKey && document.activeElement===first){event.preventDefault();last.focus();}
          else if(!event.shiftKey && document.activeElement===last){event.preventDefault();first.focus();}
        }
      };
      cancel.addEventListener('click',()=>finish(false));
      accept.addEventListener('click',()=>finish(true));
      backdrop.addEventListener('mousedown',event=>{if(event.target===backdrop)finish(false);});
      document.addEventListener('keydown',keydown,true);
    });
  }

  function open(target) {
    const modal = document.createElement('div');
    modal.className = 'fm-sim-overlay';
    modal.innerHTML = `<section class="fm-sim-window" role="dialog" aria-modal="true" aria-labelledby="fm-sim-title">
      <header class="fm-sim-top"><div><span class="fm-sim-eyebrow">CALENDAR · LIVE PYTHON WORLD</span>
        <h2 id="fm-sim-title">Simulating your season</h2><p class="fm-sim-range"></p></div>
        <span class="fm-sim-pulse">● WORLD RUNNING</span></header>
      <div class="fm-sim-status"><div><small>PYTHON WORLD DATE</small><strong class="fm-sim-date">Starting...</strong>
        <span class="fm-sim-description">Waiting for Python results</span></div>
        <strong class="fm-sim-percentage">0%</strong></div>
      <div class="fm-sim-progress" role="progressbar" aria-label="Simulation progress" aria-valuemin="0" aria-valuemax="100" aria-valuenow="0"><div class="fm-sim-progress-fill"></div></div>
      <div class="fm-sim-summary"><span><strong class="fm-sim-managed-count">0</strong><small>YOUR MATCHES SHOWN</small></span>
        <span><strong class="fm-sim-days-count">0</strong><small>DAYS PROCESSED</small></span></div>
      <div class="fm-sim-feed-heading"><h3>Your club results</h3>
        <label>Display speed <select class="fm-sim-speed" aria-label="Results display speed">
        <option value="105">1×</option><option value="35" selected>3×</option><option value="8">12×</option><option value="0">Instant</option></select></label></div>
      <div class="fm-sim-feed" role="log" aria-live="off" aria-label="Your club match results"><div class="fm-sim-feed-empty">Waiting for your next club result. Other teams are being simulated in the background.</div></div>
      <footer class="fm-sim-bottom"><p class="fm-sim-note">Results are provisional until the entire run succeeds. Do not close the Python server.</p>
        <button type="button" class="fm-sim-done" disabled>Return to calendar</button></footer>
    </section>`;
    modal.querySelector('.fm-sim-range').textContent = `Target: ${dateText(target)} · Includes your own matches`;
    document.body.appendChild(modal);
    return modal;
  }

  async function run(target) {
    if(active)throw new Error('A simulation is already displayed');
    active = true;
    const modal = open(target);
    const select = q => modal.querySelector(q);
    const entries = [];
    let cursor = 0, jobState = null, shown = 0, queue = [], pollingDone = false, terminal = null;
    let displayedDays = 0;
    let resolveDone;
    const donePromise = new Promise(resolve => { resolveDone = resolve; });
    const done = select('.fm-sim-done');
    done.addEventListener('click', () => { if(!done.disabled)resolveDone(); });

    function appendResult(item) {
      if(item.type!=='result' || item.managed!==true) return;
      shown += 1;
      const homeScore = Number(item.home_goals), awayScore = Number(item.away_goals);
      const penalties = Number(item.penalties_home) || Number(item.penalties_away);
      const row = document.createElement('div');
      row.className = 'fm-sim-result fm-sim-own';
      const competition=compBrand(item.competition_id);
      // Only competition branding owns the local accent. The main game shell
      // retains the managed club identity for all careers.
      row.style.setProperty('--fm-sim-comp-accent',competition.colour);
      row.innerHTML = `<div class="fm-sim-result-meta"><span>${safe(dateText(item.date))}</span><span class="fm-sim-comp">${competition.logo}<span>${safe(item.competition||competitionText(item.competition_id))}</span></span></div>
        <div class="fm-sim-result-main"><span class="fm-sim-team">${clubCrest(item.home_id,item.home_club)}<span>${clubLabel(item.home_id,item.home_club)}</span></span>
          <strong class="fm-sim-score">${homeScore} – ${awayScore}</strong>
          <span class="fm-sim-team fm-sim-away"><span>${clubLabel(item.away_id,item.away_club)}</span>${clubCrest(item.away_id,item.away_club)}</span></div>
        ${penalties?`<div class="fm-sim-shootout">Penalties ${Number(item.penalties_home)}–${Number(item.penalties_away)}</div>`:''}`;
      const feed = select('.fm-sim-feed');
      feed.querySelector('.fm-sim-feed-empty')?.remove();
      feed.prepend(row);
      // Latest 7 rows stay visible; every row in the feed comes from Python.
      if(feed.children.length>7)feed.lastElementChild.remove();
      select('.fm-sim-managed-count').textContent = shown.toLocaleString('en-GB');
      select('.fm-sim-description').textContent = `${competitionText(item.competition_id)} · ${shown.toLocaleString('en-GB')} club scores shown`;
    }
    function updateProgress(state,force = false) {
      if(!state)return;
      if(state.current_day)select('.fm-sim-date').textContent = dateText(state.current_day);
      const pct = force?100:state.percent;
      select('.fm-sim-progress-fill').style.width = `${Math.max(0,Math.min(100,pct))}%`;
      select('.fm-sim-percentage').textContent = `${Math.round(pct)}%`;
      select('.fm-sim-progress').setAttribute('aria-valuenow',String(Math.round(pct)));
      displayedDays = Math.max(displayedDays, state.days_completed);
      select('.fm-sim-days-count').textContent = displayedDays;
    }

    async function poll(jobId) {
      let errors = 0;
      while(true) {
        try {
          if(queue.length>180){await sleep(90);continue;}
          const res = await fetch(`/api/progression/jobs/${encodeURIComponent(jobId)}?after=${cursor}&limit=100`,{cache:'no-store'});
          const payload = await res.json();
          if(!res.ok)throw new Error(payload.error || `Status HTTP ${res.status}`);
          if(!Array.isArray(payload.events))throw new Error('Invalid simulation progress response');
          errors=0;
          cursor=payload.next_cursor;
          // Keep advancing the cursor across ALL Python world results, but
          // display ONLY fixtures in which our managed club participated.
          queue.push(...payload.events.filter(item => item.type==='result' && item.managed===true));
          jobState=payload;
          updateProgress(payload);
          if(payload.status==='failed') {
            terminal={error:payload.error||'The Python simulation failed'};
            pollingDone=true;
            break;
          }
          if(payload.status==='completed' && !payload.has_more && cursor===payload.results_available) {
            terminal={result:payload.result};
            pollingDone=true;
            break;
          }
          await sleep(payload.has_more ? 35 : 180);
        } catch(error) {
          errors++;
          if(errors>=5){terminal={error:`Connection to Python lost: ${String(error.message||error)}. The simulation may still be running; check the server window.`,uncertain:true};pollingDone=true;break;}
          await sleep(300);
        }
      }
    }

    async function display() {
      while(!pollingDone || queue.length) {
        if(queue.length) {
          const item=queue.shift();
          if(item.type==='result')appendResult(item);
          if(jobState)updateProgress(jobState);
          const delay=Number(select('.fm-sim-speed').value);
          // One result is rendered per cycle. Instant is an intentional fast
          // display mode, not a fake score nor an altered simulation speed.
          if(delay)await sleep(delay);
          else if(shown%100===0)await sleep(0);
        } else await sleep(70);
      }
      if(terminal?.error){
        select('.fm-sim-pulse').textContent='● SIMULATION FAILED';
        select('.fm-sim-pulse').classList.add('fm-sim-pulse-error');
        select('.fm-sim-note').textContent=terminal.uncertain ? `${terminal.error} The final game state is unknown until contact is restored.` : `${terminal.error} · No partial game progress was committed.`;
        done.textContent=terminal.uncertain?'Close (check server)':'Close (no changes applied)';
        done.disabled=false;
        await donePromise;
        throw new Error(terminal.error);
      }
      const paused = terminal?.result?.stopped_for_decision === true;
      updateProgress(jobState,!paused);
      select('.fm-sim-pulse').textContent=paused?'DECISION REQUIRED':'✓ SIMULATION COMPLETE';
      select('.fm-sim-pulse').classList.add('fm-sim-pulse-done');
      select('.fm-sim-description').textContent=`${shown.toLocaleString('en-GB')} of your club's matches played`;
      if(shown===0)select('.fm-sim-feed-empty').textContent='Your club had no matches during this period. Other clubs were simulated in the background.';
      select('.fm-sim-note').textContent=paused
        ? `Paused on ${dateText(terminal.result.to_date)}: ${terminal.result.decisions.length} transfer decision(s) require your response. Your original target is retained in Calendar.`
        : `World committed through ${dateText(terminal.result.to_date)}. Save your career to preserve these changes.`;
      done.textContent=paused?'Review negotiation':'Return to calendar';
      done.disabled=false;
      done.focus();
      await donePromise;
      return terminal.result;
    }

    try {
      const start = await fetch('/api/progression/jobs',{
        method:'POST',headers:{'Content-Type':'application/json'},
        body:JSON.stringify({action:'simulate_until',date:target})
      });
      const data=await start.json();
      if(!start.ok)throw new Error(data.error||`Simulation HTTP ${start.status}`);
      if(!data.job_id)throw new Error('Python did not return a simulation job');
      select('.fm-sim-range').textContent=`${dateText(data.from_date)} → ${dateText(target)} · Actual Python match results`;
      const stream=poll(data.job_id);
      const finished=await display();
      await stream;
      return finished;
    } finally {
      modal.remove();
      active=false;
    }
  }
  return {run,confirm,isActive:()=>active || confirming};
})();
