/* TS-UI-15: verified career Newsroom with a deterministic, club-neutral photo pool.
 * No stock photo purports to depict a specific player; uploaded player photos by
 * persistent ID take precedence. All news text still originates from /api/news. */
(() => {
  'use strict';
  const esc=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const labels={result:'Match report',transfer:'Transfer',loan:'Loan move',title:'Trophy winner',award:'Season award',
    medical:'Medical',training:'Training',academy:'Youth academy',press:'Press conference',board:'Club statement'};
  const sections={all:'All news',result:'Matches',transfer:'Transfers',loan:'Loans',title:'Titles',award:'Awards',
    medical:'Medical',training:'Training',academy:'Academy',press:'Press',board:'Club'};
  let stories=[],status='loading',serial=0,expanded=false,root=null,selectedFilter='all',query='',serverSeason=null;
  const homePanel=()=>document.getElementById('activity-panel');
  const homeGrid=()=>document.querySelector('.club-news .story-grid');
  const media=s=>window.FMNewsMedia?.markup?.(s)||'<span class="nr-media nr-media-fallback"></span>';
  const dateLabel=s=>s.date||(s.season?`Season ${s.season}`:'Career archive');
  const label=s=>labels[s.category]||'Football news';
  function findStory(id){return stories.find(s=>String(s.id)===String(id));}
  function closeDialog(){document.querySelector('.fm-news-backdrop')?.remove();document.removeEventListener('keydown',onEscape);}
  function onEscape(event){if(event.key==='Escape')closeDialog();}
  function openStory(id){
    const story=findStory(id);if(!story)return;
    closeDialog();
    const backdrop=document.createElement('div');backdrop.className='fm-news-backdrop';
    const peers=stories.filter(s=>s.id!==story.id&&s.category===story.category).slice(0,3);
    const actions=[
      story.player_id?'<button type="button" data-news-history="player">Player history →</button>':'',
      story.club_id?'<button type="button" data-news-history="club">Club history →</button>':'',
      story.competition_id?'<button type="button" data-news-history="competition">Competition →</button>':'',
      story.route?`<button type="button" data-news-route="${esc(story.route)}">${story.route==='Transfers'?'Open Transfers':story.route==='Competitions'?'View competition':'Open Scouting'} →</button>`:''
    ].join('');
    backdrop.innerHTML=`<article role="dialog" aria-modal="true" aria-labelledby="fm-news-dialog-title" class="fm-news-dialog fm-news-story-${esc(story.category)}">
      <div class="fm-news-dialog-top"><span>FOOTBALL WORLD · ${esc(label(story))} · ${esc(dateLabel(story))}</span>
        <button type="button" class="fm-news-close" aria-label="Close story">×</button></div>
      <div class="fm-news-dialog-hero">${media(story)}<span class="fm-news-dialog-category">${esc(label(story))}</span></div>
      <div class="fm-news-dialog-copy"><h2 id="fm-news-dialog-title">${esc(story.title)}</h2>
        <p>${esc(story.body)}</p><small>Based on recorded events in your career.</small>
        <div class="fm-news-dialog-actions">${actions}<button type="button" class="fm-news-close">Close</button></div>
      </div>
      ${peers.length?`<section class="fm-news-related"><strong>Related stories</strong><div>${peers.map(p=>`<button type="button" data-fm-news="${esc(p.id)}">${esc(p.title)}</button>`).join('')}</div></section>`:''}
      </article>`;
    backdrop.addEventListener('click',e=>{if(e.target===backdrop)closeDialog();});
    backdrop.querySelectorAll('.fm-news-close').forEach(b=>b.addEventListener('click',closeDialog));
    backdrop.querySelectorAll('[data-fm-news]').forEach(b=>b.addEventListener('click',()=>openStory(b.dataset.fmNews)));
    for(const type of ['player','club','competition']){
      backdrop.querySelector('[data-news-history="'+type+'"]')?.addEventListener('click',()=>{
        closeDialog();window.FMNavigation?.history?.(type,story[type+'_id']);
      });
    }
    backdrop.querySelector('[data-news-route]')?.addEventListener('click',()=>{
      closeDialog();
      if(story.route==='Competitions'&&story.competition_id)window.FMNavigation?.competition?.(story.competition_id);
      else if(['Transfers','Scouting'].includes(story.route))window.FMNavigation?.navigate?.(story.route);
    });
    document.body.append(backdrop);document.addEventListener('keydown',onEscape);
    backdrop.querySelector('.fm-news-close')?.focus();
  }
  function connect(container){
    container?.querySelectorAll('[data-fm-news]').forEach(b=>b.addEventListener('click',()=>openStory(b.dataset.fmNews)));
  }
  function renderCards(){
    const container=homeGrid();if(!container)return;
    if(status!=='ready'){
      container.innerHTML=`<p class="fm-news-empty">${status==='error'?'News unavailable: check the game server.':'Loading verified career news…'}</p>`;return;
    }
    if(!stories.length){container.innerHTML='<p class="fm-news-empty">No confirmed events yet. Results, transfers and trophies appear as the career advances.</p>';return;}
    container.innerHTML=stories.slice(0,3).map((story,i)=>`<button type="button" class="story-card fm-news-card ${i===0?'is-featured':''}" data-fm-news="${esc(story.id)}">
      ${media(story)}<span class="story-copy"><span class="story-category">${esc(label(story))}</span>
      <strong>${esc(story.title)}</strong><small>${esc(dateLabel(story))}</small></span></button>`).join('');
    connect(container);
  }
  function renderPanel(container=homePanel()){
    if(!container||!document.getElementById('activity-stories')?.classList.contains('active'))return;
    if(status!=='ready'){
      container.innerHTML=`<p class="fm-news-empty">${status==='error'?'News unavailable: check the game server.':'Loading verified football news…'}</p>`;return;
    }
    if(!stories.length){container.innerHTML='<p class="fm-news-empty">No reportable football news yet. The world has not recorded newsworthy events.</p>';return;}
    const shown=expanded?stories:stories.slice(0,7);
    container.innerHTML=shown.map(story=>`<button type="button" class="notification-row fm-news-row" data-fm-news="${esc(story.id)}">
      ${media(story)}<span class="notification-copy"><small>${esc(label(story))} · ${esc(dateLabel(story))}</small>
      <strong>${esc(story.title)}</strong><span>${esc(story.body)}</span></span></button>`).join('')+
      (!expanded&&stories.length>shown.length?'<button class="fm-news-more" type="button">Show more career news</button>':'');
    connect(container);
    container.querySelector('.fm-news-more')?.addEventListener('click',()=>{expanded=true;renderPanel(container);});
  }
  function card(story,variant='standard'){
    return `<button type="button" data-fm-news="${esc(story.id)}" class="nr-story nr-${variant} nr-category-${esc(story.category)}">
      ${media(story)}<span class="nr-story-copy"><span class="nr-story-meta">${esc(label(story))} · ${esc(dateLabel(story))}</span>
      <strong>${esc(story.title)}</strong>${variant==='lead'?`<span class="nr-story-excerpt">${esc(story.body)}</span>`:''}</span></button>`;
  }
  function filtered(){
    return stories.filter(s=>(selectedFilter==='all'||s.category===selectedFilter)&&
      (!query||`${s.title} ${s.body} ${label(s)}`.toLowerCase().includes(query.toLowerCase())));
  }
  function renderNewsroom(){
    if(!root)return;
    const genres=Object.entries(sections).filter(([key])=>key==='all'||stories.some(s=>s.category===key));
    const result=filtered();
    root.innerHTML=`<div class="nr-root">
      <header class="nr-banner"><span class="nr-banner-kicker">WORLD FOOTBALL · LIVE CAREER ARCHIVE</span>
        <h2>Newsroom</h2><p>Match reports, transfers, trophies and confirmed developments from your football world.</p>
        <span class="nr-banner-season">${esc(serverSeason||'Career news')}</span></header>
      <div class="nr-toolbar"><nav aria-label="News categories" class="nr-filters">${genres.map(([key,name])=>`<button type="button" data-nr-filter="${esc(key)}" class="${selectedFilter===key?'active':''}" aria-pressed="${selectedFilter===key}">${esc(name)}</button>`).join('')}</nav>
        <label class="nr-search-label"><span class="sr-only">Search news</span><input class="nr-search" type="search" placeholder="Search headlines…" value="${esc(query)}"></label></div>
      ${status==='loading'?'<section class="nr-empty">Loading real football news…</section>':status==='error'?'<section class="nr-empty">The news feed is unavailable. Check the game server and reopen this page.</section>':
        result.length?`<div class="nr-content"><div class="nr-lead-column">${card(result[0],'lead')}
          ${result.length>4?`<h3 class="nr-section-title">Latest headlines</h3><div class="nr-headlines">${result.slice(4,12).map(s=>card(s,'brief')).join('')}</div>`:''}</div>
          <aside class="nr-trending"><h3>Latest developments</h3>${result.slice(1,4).map(s=>card(s,'side')).join('')||'<p>More stories will appear as your career advances.</p>'}</aside>
          ${result.length>12?`<div class="nr-extra"><h3 class="nr-section-title">More stories</h3>${result.slice(12).map(s=>card(s,'standard')).join('')}</div>`:''}</div>`:
        `<section class="nr-empty nr-empty-illustrated"><img src="/portable/assets/news/stadium-floodlights-01.webp" alt="" loading="lazy">
          <div><h3>${query||selectedFilter!=='all'?'No matching stories':'Your football world is just getting started'}</h3>
          <p>${query||selectedFilter!=='all'?'Try another category or search.':'No confirmed events have been recorded yet. Play fixtures or complete transfers to populate the Newsroom.'}</p></div></section>`}
      <p class="nr-truth-note">News comes from verified career records. Editorial photography illustrates the category; individual player photographs are taken from your imported player database when available.</p>
    </div>`;
    root.querySelectorAll('[data-nr-filter]').forEach(b=>b.addEventListener('click',()=>{selectedFilter=b.dataset.nrFilter;query='';renderNewsroom();}));
    root.querySelector('.nr-search')?.addEventListener('input',e=>{
      const caret=e.target.selectionStart;query=e.target.value;renderNewsroom();
      const replacement=root.querySelector('.nr-search');replacement?.focus();
      if(replacement&&typeof caret==='number')replacement.setSelectionRange(caret,caret);
    });
    connect(root);
  }
  async function refresh(){
    const request=++serial;
    try{
      const response=await fetch('/api/news',{cache:'no-store'});
      if(!response.ok)throw Error(`HTTP ${response.status}`);
      const payload=await response.json();if(request!==serial)return;
      if(payload.source!=='career-ledgers'||!Array.isArray(payload.stories))throw Error('Unexpected news response');
      stories=payload.stories;serverSeason=payload.season||null;status='ready';expanded=false;
      window.FMNewsMedia?.assignSequence?.(stories);
    }catch(error){if(request!==serial)return;status='error';stories=[];console.warn('News unavailable',error);}
    renderCards();renderPanel();renderNewsroom();
  }
  function mount(container){root=container;renderNewsroom();if(status==='loading'||status==='error')refresh();}
  window.addEventListener('fm-assets-ready',()=>{if(status==='ready'){renderCards();renderPanel();renderNewsroom();}});
  window.FMNews={refresh,renderPanel,renderCards,renderNewsroom,openStory,mount,getStories:()=>stories.slice()};
})();
