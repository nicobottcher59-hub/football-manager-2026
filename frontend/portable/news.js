/* TS-28.1: verified global football news, separate from manager notifications.
 * All headlines come from /api/news; never use the old UI-1 sample stories.
 */
(() => {
  'use strict';
  const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const labels = {result:'Match result',transfer:'Confirmed transfer',loan:'Confirmed loan',title:'Trophy winner',award:'Season award'};
  let stories = [], status = 'loading', serial = 0, expanded = false;
  const panel = () => document.getElementById('activity-panel');
  const grid = () => document.querySelector('.club-news .story-grid');
  function findStory(id) { return stories.find(s => s.id === id); }
  function label(story) { return story.date || (story.season ? `Season ${story.season}` : 'Career archive'); }

  function closeDialog() {
    document.querySelector('.fm-news-backdrop')?.remove();
    document.removeEventListener('keydown', onEscape);
  }
  function onEscape(event) { if(event.key === 'Escape') closeDialog(); }
  function openStory(id) {
    const item = findStory(id);
    if(!item) return;
    closeDialog();
    const backdrop = document.createElement('div');
    backdrop.className = 'fm-news-backdrop';
    backdrop.innerHTML = `<section class="fm-news-dialog" role="dialog" aria-modal="true" aria-labelledby="fm-news-dialog-title">
      <div class="fm-news-dialog-top"><span>${esc(labels[item.category]||'Career news')} · ${esc(label(item))}</span>
        <button type="button" class="fm-news-close" aria-label="Close story">×</button></div>
      <h2 id="fm-news-dialog-title">${esc(item.title)}</h2><p>${esc(item.body)}</p>
      <div class="fm-news-dialog-actions"><button type="button" class="fm-news-close">Close</button>
        ${item.player_id?'<button type="button" class="fm-news-player">Player history →</button>':''}${item.club_id?'<button type="button" class="fm-news-club">Club history →</button>':''}${item.competition_id?'<button type="button" class="fm-news-competition">Competition history →</button>':''}${item.route?'<button type="button" class="fm-news-go">'+(item.route==='Competitions'?'View competition':item.route==='Transfers'?'Open Transfers':'Open Scouting')+' →</button>':''}</div></section>`;
    backdrop.addEventListener('click', event => { if(event.target === backdrop)closeDialog(); });
    backdrop.querySelectorAll('.fm-news-close').forEach(b=>b.addEventListener('click',closeDialog));
    backdrop.querySelector('.fm-news-go')?.addEventListener('click',()=>{
      closeDialog();
      if(item.route === 'Competitions' && item.competition_id){
        window.FMNavigation?.competition(item.competition_id);
      } else if(item.route === 'Transfers') window.FMNavigation?.navigate('Transfers');
      else if(item.route === 'Scouting') window.FMNavigation?.navigate('Scouting');
    });
    for(const [cls,type,id] of [['fm-news-player','player',item.player_id],['fm-news-club','club',item.club_id],['fm-news-competition','competition',item.competition_id]]){
      backdrop.querySelector('.'+cls)?.addEventListener('click',()=>{closeDialog();window.FMNavigation?.history(type,id);});
    }
    document.body.append(backdrop);
    document.addEventListener('keydown', onEscape);
    backdrop.querySelector('.fm-news-close').focus();
  }
  function attach(container) {
    container.querySelectorAll('[data-fm-news]').forEach(button => button.addEventListener('click',()=>openStory(button.dataset.fmNews)));
  }
  function renderCards() {
    const container = grid();
    if(!container)return;
    if(status === 'error') {container.innerHTML='<p class="fm-news-empty">Cannot load career news. Try again after reconnecting to the game server.</p>';return;}
    if(status === 'loading') {container.innerHTML='<p class="fm-news-empty">Loading real career news…</p>';return;}
    if(!stories.length) {container.innerHTML='<p class="fm-news-empty">No reportable events yet. Advance the career to generate confirmed results and transfers.</p>';return;}
    container.innerHTML=stories.slice(0,3).map((story,i)=>
      `<button class="story-card fm-news-card ${i===0?'is-featured':''}" type="button" data-fm-news="${esc(story.id)}">
        <span class="fm-news-art fm-news-${esc(story.category)}" aria-hidden="true"></span>
        <span class="story-copy"><span class="story-category">${esc(labels[story.category]||'Career news')}</span>
        <strong>${esc(story.title)}</strong><small>${esc(label(story))}</small></span></button>`).join('');
    attach(container);
  }
  function renderPanel(container=panel()) {
    if(!container || !document.getElementById('activity-stories')?.classList.contains('active'))return;
    if(status !== 'ready') {
      container.innerHTML = `<p class="fm-news-empty">${status==='error'?'News unavailable; check the game server.':'Loading football news…'}</p>`;
      return;
    }
    if(!stories.length) {container.innerHTML='<p class="fm-news-empty">No reportable football news yet. Results, confirmed transfers and winners will appear here.</p>';return;}
    const shown = expanded?stories:stories.slice(0,7);
    container.innerHTML=shown.map(story=>
      `<button type="button" class="notification-row fm-news-row" data-fm-news="${esc(story.id)}">
        <span class="notification-copy"><small>${esc(labels[story.category]||'Career news')} · ${esc(label(story))}</small>
          <strong>${esc(story.title)}</strong><span>${esc(story.body)}</span></span></button>`).join('') +
      (!expanded&&stories.length>shown.length?'<button class="fm-news-more" type="button">Show more career news</button>':'');
    attach(container);
    container.querySelector('.fm-news-more')?.addEventListener('click',()=>{expanded=true;renderPanel(container);});
  }
  async function refresh() {
    const request = ++serial;
    try {
      const response = await fetch('/api/news',{cache:'no-store'});
      if(!response.ok)throw Error(`HTTP ${response.status}`);
      const data=await response.json();
      if(request!==serial)return;
      if(data.source!=='career-ledgers'||!Array.isArray(data.stories))throw Error('Unexpected news response');
      stories=data.stories;status='ready';expanded=false;
    }catch(error){if(request!==serial)return;status='error';stories=[];console.warn('Live career news unavailable',error);}
    renderCards();renderPanel();
  }
  window.FMNews={refresh,renderPanel,renderCards,openStory};
})();
