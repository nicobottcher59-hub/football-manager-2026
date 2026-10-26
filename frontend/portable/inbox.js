/* TS-25: live manager inbox, real career events and voluntary conversations.
 * No simulated responses on the frontend: POST requests go to Python.
 */
(() => {
  'use strict';
  const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  let host = null, data = null, selected = null, filter = 'all', chosen = null, chosenTopic = null;
  let busy = false, requestNo = 0;
  const labels = {medical:'Medical',contracts:'Contracts',scouting:'Scouting',calendar:'Calendar',
    results:'Matches',market:'Transfers',dressing_room:'Squad',conversations:'Conversations',
    academy:'Academy',system:'Club'};
  const messages = () => data?.messages || [];
  const active = () => data?.players || [];
  const outstanding = m => m.requires_reply && !m.resolved;
  function button(html, cls='') { return `<button type="button" class="${cls}">${html}</button>`; }
  function sendSafe(command){ send(command).catch(error=>{
    const field=host?.querySelector('.mi-footnote');if(field)field.textContent=String(error.message||error);
  }); }
  const messageIcon = {medical:'✚',contracts:'✎',scouting:'⌕',calendar:'▦',results:'⚽',market:'⇄',dressing_room:'♟',conversations:'◉',academy:'★',system:'◆'};
  function playerPhoto(id){
    const path=id&&window.FMEntityAssets?.getPhoto?.(id);
    return path&&window.FMEntityAssets?.safePath?.(path) ? window.FMEntityAssets.url(path) : null;
  }
  function messageRow(m) {
    const photo=playerPhoto(m.player_id);
    return `<button class="mi-item ${!m.read?'mi-unread':''} ${m.id===selected?'mi-selected':''}" type="button" data-mi-id="${m.id}">
      <span class="mi-item-avatar">${photo?`<img class="fm-photo-real" data-fm-asset="optional" src="${esc(photo)}" alt="" loading="lazy">`:''}<span aria-hidden="true">${messageIcon[m.category]||'✉'}</span></span>
      <span class="mi-item-top"><strong>${esc(m.title)}</strong><small>${esc(m.date)}</small></span>
      <span class="mi-item-copy">${esc(m.body)}</span>
      <span class="mi-item-meta"><span>${esc(labels[m.category]||m.category)}</span>${outstanding(m)?'<em>Player request · respond by '+esc(m.decision_due)+'</em>':''}</span>
    </button>`;
  }
  function render() {
    if (!host || !data) return;
    const list = messages().filter(m=>filter==='all'||(filter==='unread'&&!m.read)||(filter==='pending'&&outstanding(m))||filter===m.category);
    if (!list.some(m=>m.id===selected)) selected = list[0]?.id ?? null;
    const current = messages().find(m=>m.id===selected);
    host.innerHTML = `<div class="mi-header"><div><span class="mi-eyebrow">CLUB COMMUNICATIONS · MANAGER'S OFFICE</span><h2>Manager Inbox</h2><p>Direct conversations, reports and decisions from your real career.</p></div>
      <span class="mi-pill">${data.unread} unread · ${data.requests} player requests · ${(data.active_promises||[]).length} commitments</span></div>
      <div class="mi-toolbar"><label>Filter <select id="mi-filter"><option value="all">All messages</option><option value="unread">Unread</option><option value="pending">Pending decisions</option>
      ${Object.keys(labels).map(key=>`<option value="${key}">${esc(labels[key])}</option>`).join('')}</select></label>
      <div class="mi-toolbar-actions"><button class="mi-open-news" type="button">Open Newsroom</button><button class="mi-talk-open" type="button">Start player conversation</button></div></div>
      <div class="mi-grid"><div class="mi-list" aria-label="Messages">${list.map(messageRow).join('')||'<p class="mi-empty">No messages in this category.</p>'}</div>
      <section class="mi-detail" aria-label="Message details">${current?`${playerPhoto(current.player_id)?`<div class="mi-detail-player-photo"><img class="fm-photo-real" data-fm-asset="optional" src="${esc(playerPhoto(current.player_id))}" alt="" loading="lazy"></div>`:''}<span class="mi-eyebrow">${esc(labels[current.category]||current.category)} · ${esc(current.date)}</span>
        <h3>${esc(current.title)}</h3><p>${esc(current.body)}</p><div class="mi-detail-actions">
        ${current.player_id?`<button type="button" class="mi-reply" data-career-type="player" data-career-id="${esc(current.player_id)}">View player history →</button>`:''}
        ${!current.read?button('Mark as read','mi-read'):''}
        ${current.player_id && active().some(p=>p.id===current.player_id)?`<button class="mi-reply" data-player="${esc(current.player_id)}" type="button">${outstanding(current)?'Discuss request':'Talk to this player'}</button>`:''}
        ${outstanding(current) && current.player_id && active().some(p=>p.id===current.player_id)?`<button class="mi-decline" type="button">Decline request</button><p class="mi-deadline">Respond by ${esc(current.decision_due)}; ignoring a request may disappoint the player.</p>`:''}
        ${current.read && !current.requires_reply && !current.resolved?button('Archive notice','mi-resolve'):''}
        ${current.category==='scouting'?(current.source_key?.startsWith('professional-scout:')?button('Open Scouting','mi-route-transfers'):button('Open Youth Academy','mi-route-youth')):''}
        ${current.category==='contracts'?button('Open Finances','mi-route-finance'):''}
        ${current.category==='market'?button('Open Transfers','mi-route-market'):''}
        ${current.category==='calendar'||current.category==='results'?button('Open Calendar','mi-route-calendar'):''}
        </div>`:'<h3>No notifications yet</h3><p>Your real career updates will appear as the world advances.</p>'}</section></div>
      <div class="mi-editor" hidden></div><p class="mi-footnote">${esc(data.notice||'')}</p>`;
    const filterInput=host.querySelector('#mi-filter');filterInput.value=filter;
    filterInput.addEventListener('change',event=>{filter=event.target.value;render();});
    host.querySelectorAll('[data-mi-id]').forEach(b=>b.addEventListener('click',()=>{
      selected=Number(b.dataset.miId);const m=messages().find(m=>m.id===selected);
      render();if(m&&!m.read)sendSafe({action:'read',message_id:m.id});
    }));
    host.querySelector('.mi-talk-open').addEventListener('click',()=>openTalk(chosen));
    host.querySelector('.mi-open-news').addEventListener('click',()=>window.FMNavigation?.navigate?.('Newsroom'));
    host.querySelector('.mi-read')?.addEventListener('click',()=>sendSafe({action:'read',message_id:selected}));
    host.querySelector('.mi-reply[data-player]')?.addEventListener('click',e=>{chosenTopic=current?.suggested_topic||null;openTalk(e.currentTarget.dataset.player);});
    host.querySelector('.mi-decline')?.addEventListener('click',()=>sendSafe({action:'respond',message_id:selected,choice:'decline'}));
    host.querySelector('.mi-resolve')?.addEventListener('click',()=>sendSafe({action:'resolve',message_id:selected}));
    for(const [cls,route] of [['mi-route-youth','Youth Academy'],['mi-route-finance','Finances'],['mi-route-transfers','Scouting'],['mi-route-market','Transfers'],['mi-route-calendar','Calendar']])
      host.querySelector('.'+cls)?.addEventListener('click',()=>window.FMNavigation?.navigate(route));
    if(chosen) openTalk(chosen,true);
  }
  function openTalk(playerId, refreshOnly=false) {
    if(!host || !data)return;
    const editor=host.querySelector('.mi-editor');if(!editor)return;
    editor.hidden=false;
    const roster=active();if(!roster.length){editor.textContent='No registered players available.';return;}
    const first=roster.find(p=>p.id===playerId)||roster[0];chosen=first.id;
    editor.innerHTML=`<div class="mi-editor-top"><div><span class="mi-eyebrow">DIRECT CONVERSATION</span><h3>Talk to a player</h3></div><button type="button" class="mi-editor-close">Close</button></div>
      <div class="mi-editor-controls"><label>Player<select id="mi-player">${roster.map(p=>`<option value="${esc(p.id)}">${esc(p.name)} · ${esc(p.position)}</option>`).join('')}</select></label>
      <label>Topic<select id="mi-topic">${data.topics.map(t=>`<option value="${esc(t.id)}">${esc(t.label)}</option>`).join('')}</select></label></div>
      <div class="mi-player-info"></div>
      <label class="mi-promise"><input type="checkbox" id="mi-promise"> <span class="mi-promise-label">Make a commitment</span></label><p class="mi-promise-note">Only commit if you intend to follow through. The game verifies real actions.</p>
      <div class="mi-editor-bottom"><button class="mi-confirm" type="button">Have conversation</button><p class="mi-editor-result" aria-live="polite"></p></div>`;
    const selector=editor.querySelector('#mi-player');selector.value=chosen;
    const topicSelect=editor.querySelector('#mi-topic');
    if(chosenTopic && data.topics.some(t=>t.id===chosenTopic)) topicSelect.value=chosenTopic;
    chosenTopic=null;
    function updatePlayer(){
      chosen=selector.value;const p=roster.find(x=>x.id===chosen);
      editor.querySelector('.mi-player-info').textContent=
        `${p.name} · Morale ${p.morale}/100 · Trust ${p.trust}/100 · Conversation pressure ${p.pressure}/100 · Contract: ${p.contract_until||'Not listed'}${p.active_promise?' · Active promise: '+p.promise_kinds.join(', '):''}${p.pending_requests?' · Pending requests: '+p.pending_requests:''}`;
    }
    selector.addEventListener('change',updatePlayer);updatePlayer();
    function updateCommitment(){
      const topic=data.topics.find(t=>t.id===topicSelect.value);
      const allowed=Boolean(topic?.promise_kind);
      editor.querySelector('.mi-promise').hidden=!allowed;
      editor.querySelector('.mi-promise-note').hidden=!allowed;
      editor.querySelector('.mi-promise-label').textContent=topic?.promise_label||'No commitment available';
      if(!allowed)editor.querySelector('#mi-promise').checked=false;
    }
    topicSelect.addEventListener('change',updateCommitment);
    updateCommitment();
    editor.querySelector('.mi-editor-close').addEventListener('click',()=>{chosen=null;editor.hidden=true;});
    editor.querySelector('.mi-confirm').addEventListener('click',async()=>{
      const topic=editor.querySelector('#mi-topic').value;
      const option=data.topics.find(t=>t.id===topic);
      const pledge=option?.promise_kind&&editor.querySelector('#mi-promise').checked;
      const field=editor.querySelector('.mi-editor-result');field.textContent='Speaking with player...';
      try { const result=await send({action:'talk',player_id:chosen,topic,promise_kind:pledge?option.promise_kind:null},false);
        if(result){chosen=null;render();const fresh=host.querySelector('.mi-editor');fresh.hidden=false;
          fresh.innerHTML=`<div class="mi-editor-top"><h3>Player reaction</h3><button class="mi-editor-close" type="button">Close</button></div>
            <p>${esc(result.reaction)}</p><p>Morale change: ${esc(result.morale_delta)} · Trust: ${esc(result.trust)}/100 · Pressure: ${esc(result.pressure)}/100</p>`;
          fresh.querySelector('button').addEventListener('click',()=>fresh.hidden=true);
        }
      } catch(error){ field.textContent=String(error.message||error); }
    });
  }
  async function send(payload,rerender=true) {
    if(busy)return null;
    busy=true;
    try{
      const response=await fetch('/api/inbox',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
      const result=await response.json();if(!response.ok)throw Error(result.error||`HTTP ${response.status}`);
      await refresh(rerender);return result;
    }finally{busy=false;}
  }
  async function refresh(shouldRender=true){
    const serial=++requestNo;
    try{
      const response=await fetch('/api/inbox',{cache:'no-store'});if(!response.ok)throw Error(`HTTP ${response.status}`);
      const next=await response.json();if(serial!==requestNo)return;
      data=next;const badge=document.querySelector('.sidebar .nav-item .nav-badge');
      if(badge)badge.textContent=String(data.unread);
      if(shouldRender)render();
      const activeTab=document.getElementById('activity-inbox');
      if(activeTab?.classList.contains('active'))renderHome(document.getElementById('activity-panel'));

    } catch(error){
      if(host)host.innerHTML='<section class="mi-error">Cannot load live Inbox. Start the Python server and retry.</section>';
      console.warn('Live manager inbox unavailable',error);
    }
  }
  function renderHome(panel){
    if(!panel)return;
    if(!data){panel.textContent='Loading club notifications...';return;}
    const recent=messages().slice(0,5);
    panel.innerHTML=recent.map(m=>`<button type="button" class="notification-row" data-mi-home="${m.id}">
      <span class="notification-icon blue">✉</span><span class="notification-copy"><strong>${esc(m.title)}</strong><span>${esc(m.body)}</span></span>
      <span class="notification-meta"><small>${esc(m.date)}</small>${!m.read?'<i class="unread-dot" aria-label="Unread"></i>':''}</span></button>`).join('')||'<p class="mi-empty">No new club notifications yet.</p>';
    panel.querySelectorAll('[data-mi-home]').forEach(b=>b.addEventListener('click',()=>{
      selected=Number(b.dataset.miHome);window.FMNavigation?.navigate('Inbox');
    }));
    const badge=document.querySelector('#activity-inbox .unread-count');if(badge)badge.textContent=String(data.unread);
  }
  window.addEventListener('fm-assets-ready',()=>{if(host&&data&&host.isConnected)render();});
  window.FMInbox = {mount:(target,playerId)=>{host=target;chosen=playerId||null;refresh();},refresh,renderHome};
})();
