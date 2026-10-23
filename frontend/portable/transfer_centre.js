/* TS-UI-09 Transfer Centre. Presentation and navigation only: all decisions remain Python-owned. */
(() => {
  'use strict';
  let host=null, datasets=null, loadSerial=0, busy=false, message='';
  let expanded={received:false,sent:false,shortlist:false,history:false,activity:false};
  let typeFilter='all', priorityFilter='all', query='', shortlistLimit=8;
  const esc=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const money=n=>n==null?'??':`£${Math.abs(Number(n)||0).toLocaleString('en-GB',{maximumFractionDigits:0})}`;
  const brief=n=>{if(n==null)return '??';const v=Number(n)||0;return v>=1e6?`£${(v/1e6).toFixed(1).replace(/\.0$/,'')}M`:v>=1e3?`£${(v/1e3).toFixed(1).replace(/\.0$/,'')}K`:money(v);};
  const formatDate=s=>/^\d{4}-\d{2}-\d{2}$/.test(s||'')?`${s.slice(8,10)}/${s.slice(5,7)}/${s.slice(0,4)}`:'—';
  const club=(id,name)=>window.FMClubIdentity?.resolve?.(id,name)||{display_name:name||id||'Club',crest:null};
  const nav=()=>window.FMNavigation;
  const crest=(id,name,cls='')=>{
    const c=club(id,name),source=c.crest&&(window.FMEntityAssets?.url?.(c.crest)||'/portable/'+c.crest);
    const abbr=c.display_name.split(/\s+/).filter(Boolean).slice(0,2).map(x=>x[0]).join('').toUpperCase()||'?';
    const col=window.FMClubIdentity?.fallbackColour?.(id)||'#477d9c';
    return source?`<img class="tc-crest ${cls}" src="${esc(source)}" data-fm-asset="optional" alt="${esc(c.display_name)} crest" title="${esc(c.display_name)}" loading="lazy" decoding="async">`:
      `<span class="tc-crest tc-shield ${cls}" style="--tc-shield:${esc(col)}" role="img" aria-label="${esc(c.display_name)} crest" title="${esc(c.display_name)}">${esc(abbr)}</span>`;
  };
  const face=(p,cls='')=>p&&window.FMPortraits?.portrait?.(p,`tc-face ${cls}`)||`<span class="tc-face tc-face-fallback ${cls}" aria-hidden="true">${esc(p?.name?.charAt(0)||'?')}</span>`;
  const flag=(n)=>n&&(window.FMNationFlags?.render?.(n,'tc-flag')||`<span class="tc-flag-fallback">${esc(n)}</span>`)||'';
  const shortStatus=(v)=>({manager_turn:'Decision required',agreed:'Club agreement',pending_window:'Awaiting window',completed:'Completed',failed:'Failed',rejected:'Rejected',withdrawn:'Withdrawn',expired:'Expired',open:'Negotiating',countered:'Counteroffer',active:'Active',closed:'Closed'}[v]||v||'Discussion');
  const statusClass=s=>['completed','agreed','active'].includes(s)?'tc-good':['manager_turn','pending_window','open','countered'].includes(s)?'tc-amber':['rejected','withdrawn','failed','expired','closed','broken'].includes(s)?'tc-red':'tc-blue';
  const sortNewest=(a,b)=>String(b.day||'').localeCompare(String(a.day||''));
  function offers(){
    const t=datasets?.transfers, l=datasets?.loans;
    if(!t)return [];
    const manager=t.club_id;
    const purchases=(t.offers||[]).map(o=>({
      id:o.id,type:'transfer',direction:o.direction==='incoming'?'received':'sent',
      name:o.player,profile:o.player_profile,playerId:o.player_id,
      clubId:o.direction==='incoming'?o.buyer_id:o.seller_id,
      clubName:o.direction==='incoming'?o.buyer:o.seller,
      amount:o.guaranteed_gbp??o.fixed_gbp,priceLabel:'Guaranteed',status:o.status,
      day:o.updated_on||o.settled_on||t.date, events:o.history?.length||0
    }));
    const loans=(l?.negotiations||[]).map(talk=>{
      const opening=talk.history?.[0];
      const startedHere=opening?.by_club_id===manager;
      const from=startedHere?'sent':'received';
      const otherId=talk.parent_id===manager?talk.borrower_id:talk.parent_id;
      const other=talk.parent_id===manager?talk.borrower:talk.parent;
      const playerData=[...(l?.incoming||[]),...(l?.outgoing||[]),...(l?.loans||[]).map(x=>x.player)].find(p=>p.id===talk.player_id);
      return {id:talk.id,type:'loan',direction:from,name:playerData?.name||talk.player_name||'Loan player',profile:playerData,playerId:talk.player_id,
        clubId:otherId,clubName:other,amount:null,priceLabel:`${talk.terms?.borrower_wage_percent??0}% wages`,status:talk.status,
        day:talk.history?.at(-1)?.date||talk.expires_on||t.date,events:talk.history?.length||0,ownerId:talk.parent_id};
    });
    return [...purchases,...loans].sort(sortNewest);
  }
  function showOffers(direction){const rows=offers().filter(o=>o.direction===direction&&(typeFilter==='all'||o.type===typeFilter));return rows;}
  const personSub=o=>{
    const p=o.profile||{};const n=p.nationality||'';
    return `${p.age==null?'':esc(p.age)+' · '}${esc(p.position||'')} ${flag(n)}`;
  };
  const openAction=o=>o.type==='loan'?`data-tc-loan="${esc(o.id)}"`:`data-tc-deal="${esc(o.id)}"`;
  function offerRow(o){
    return `<div class="tc-offer-row" data-tc-type="${esc(o.type)}">
      <div class="tc-person">${face(o.profile)}<div class="tc-person-name"><strong>${esc(o.name)}</strong><small>${personSub(o)}</small></div></div>
      <div class="tc-other">${crest(o.clubId,o.clubName)}<span>${esc(club(o.clubId,o.clubName).display_name)}</span></div>
      <span class="tc-type">${o.type==='loan'?'Loan':'Transfer'}</span>
      <span class="tc-money">${o.type==='loan'?esc(o.priceLabel):brief(o.amount)}</span>
      <span class="tc-status ${statusClass(o.status)}">${esc(shortStatus(o.status))}</span>
      <time class="tc-date">${formatDate(o.day)}</time>
      <button type="button" class="tc-button tc-row-action" ${openAction(o)}>View →</button>
    </div>`;
  }
  function offerPanel(direction){
    const data=showOffers(direction), all=!!expanded[direction],title=direction==='received'?'Received Offers':'Sent Offers';
    const shown=all?data.slice(0,70):data.slice(0,5);
    return `<section class="tc-card tc-offer-panel" aria-label="${title}">
      <header class="tc-card-heading"><div><h3>${title} <span class="tc-count">${data.length}</span></h3><p>${direction==='received'?'Offers made by other clubs for your players.':'Your club’s offers to sign other players.'}</p></div>
      ${data.length>5?`<button type="button" class="tc-button" data-tc-expand="${direction}" aria-expanded="${all}">${all?'Show less':'View all'} →</button>`:''}</header>
      <div class="tc-table-head"><span>Player</span><span>${direction==='received'?'From':'To'}</span><span>Type</span><span>Offer</span><span>Status</span><span>Date</span><span>Action</span></div>
      <div class="tc-offer-list">${shown.map(offerRow).join('')||`<div class="tc-empty">No ${direction==='received'?'received':'sent'} offers${typeFilter!=='all'?' of this type':''} yet.</div>`}</div>
      ${data.length>70&&all?`<div class="tc-small-note">Showing the 70 most recent offers.</div>`:''}
    </section>`;
  }
  function shortList(){
    const players=(datasets?.scouting?.players||[]).filter(p=>p.priority);
    const filtered=players.filter(p=>(priorityFilter==='all'||p.priority===priorityFilter)&&(!query||`${p.name} ${p.club} ${p.position}`.toLowerCase().includes(query.toLowerCase())))
      .sort((a,b)=>({top:0,future:1,monitor:2}[a.priority]??3)-({top:0,future:1,monitor:2}[b.priority]??3)||a.name.localeCompare(b.name));
    const slice=expanded.shortlist?filtered.slice(0,100):filtered.slice(0,shortlistLimit);
    const arr=slice.map(p=>{
      const value=p.public_profile?.market_value_gbp!=null?brief(p.public_profile.market_value_gbp):p.report?.value_range_gbp?`${brief(p.report.value_range_gbp[0])}–${brief(p.report.value_range_gbp[1])}`:'??';
      const report=p.report?'Report available':p.scouting?`Scouting ${p.scouting.progress}%`:'Not scouted';
      return `<div class="tc-short-row" data-player="${esc(p.id)}"><button type="button" class="tc-favorite" data-tc-short-remove="${esc(p.id)}" aria-label="Remove ${esc(p.name)} from shortlist" title="Remove from shortlist">★</button>
        ${face(p)}<div class="tc-short-name"><strong>${esc(p.name)}</strong><small>${flag(p.nationality)} ${esc(p.age)} · ${esc(p.position)}</small></div>
        <div class="tc-short-club">${crest(p.club_id,p.club)}<span>${esc(club(p.club_id,p.club).display_name)}</span></div>
        <span class="tc-short-value">${value}</span><span class="tc-scout-status">${esc(report)}</span>
        <button type="button" class="tc-button" data-tc-player="${esc(p.id)}">Negotiate →</button>
      </div>`;
    }).join('');
    return `<section class="tc-card tc-shortlist"><header class="tc-card-heading"><div><h3>Shortlist <span class="tc-count">${players.length}</span></h3><p>Your saved targets from Scouting. Ratings and valuations remain hidden until known.</p></div><button class="tc-button" type="button" data-tc-scout>+ Find players</button></header>
      <div class="tc-short-controls"><input type="search" aria-label="Search shortlist" data-tc-query placeholder="Search shortlist" value="${esc(query)}" />
        <select aria-label="Shortlist priority" data-tc-priority><option value="all" ${priorityFilter==='all'?'selected':''}>All priorities</option>${[['top','Top targets'],['future','For future'],['monitor','Monitoring']].map(([v,n])=>`<option value="${v}" ${priorityFilter===v?'selected':''}>${n}</option>`).join('')}</select></div>
      <div class="tc-short-scroll">${arr||'<div class="tc-empty">No saved players match the filters. Add targets from Scouting.</div>'}</div>
      ${filtered.length>slice.length?`<button class="tc-button tc-more" type="button" data-tc-expand="shortlist">View all ${filtered.length} saved players →</button>`:expanded.shortlist&&players.length>shortlistLimit?'<button class="tc-button tc-more" type="button" data-tc-expand="shortlist">Show fewer</button>':''}
    </section>`;
  }
  function historyPanel(){
    const data=offers().filter(x=>x.events>0), limit=expanded.history?50:5;
    return `<section class="tc-card tc-history"><header class="tc-card-heading"><div><h3>Negotiation History <span class="tc-count">${data.length}</span></h3><p>Previous rounds and active discussions, including loans.</p></div>${data.length>5?`<button class="tc-button" data-tc-expand="history" type="button">${expanded.history?'Show less':'View all'} →</button>`:''}</header>
      <div class="tc-history-list">${data.slice(0,limit).map(x=>`<div class="tc-history-row">${crest(x.clubId,x.clubName)}<div><strong>${esc(x.name)}</strong><small>${esc(x.clubName)} · ${x.events} rounds · ${formatDate(x.day)}</small></div><span class="tc-status ${statusClass(x.status)}">${esc(shortStatus(x.status))}</span><button type="button" class="tc-button" ${openAction(x)}>Review →</button></div>`).join('')||'<div class="tc-empty">No negotiation rounds recorded yet.</div>'}</div>
    </section>`;
  }
  function marketActivity(){
    const list=datasets?.transfers?.world_transfers||[], shown=expanded.activity?list.slice(0,45):list.slice(0,5);
    return `<section class="tc-card tc-activity"><header class="tc-card-heading"><div><h3>Market Activity</h3><p>Confirmed transfers between AI clubs.</p></div>${list.length>5?`<button class="tc-button" type="button" data-tc-expand="activity">${expanded.activity?'Less':'View all'} →</button>`:''}</header>
      <div class="tc-activity-list">${shown.map(x=>`<div class="tc-activity-row"><div><strong>${esc(x.player)}</strong><small>${esc(x.from_club)} → ${esc(x.to_club)}</small></div><div><strong>${brief(x.fee_gbp)}</strong><small>${formatDate(x.date)}</small></div></div>`).join('')||'<div class="tc-empty">No completed world transfers yet.</div>'}</div></section>`;
  }
  function financeCard(){
    const f=datasets?.finances||{},t=datasets?.transfers||{};
    const total=f.transfer_budget_gbp??t.transfer_budget_gbp, available=f.transfer_available_gbp??t.available_transfer_budget_gbp;
    const committed=total!=null&&available!=null?Math.max(0,total-available):null;
    return `<section class="tc-card tc-finance"><header class="tc-card-heading"><div><h3>Budget Summary</h3><p>Live club finances</p></div></header>
      <dl class="tc-finance-list"><div><dt>Transfer budget</dt><dd>${brief(total)}</dd></div><div><dt>Committed spend</dt><dd>${brief(committed)}</dd></div><div><dt>Remaining funds</dt><dd class="tc-positive">${brief(available)}</dd></div><hr><div><dt>Wage budget</dt><dd>${f.wage_budget_weekly_gbp==null?'—':brief(f.wage_budget_weekly_gbp)+'/wk'}</dd></div><div><dt>Current wage bill</dt><dd>${f.weekly_payroll_gbp==null?'—':brief(f.weekly_payroll_gbp)+'/wk'}</dd></div><div><dt>Wage room</dt><dd class="tc-positive">${f.wage_headroom_weekly_gbp==null?'—':brief(f.wage_headroom_weekly_gbp)+'/wk'}</dd></div></dl>
      <button type="button" class="tc-button" data-tc-finances>View Finances →</button></section>`;
  }
  function windowCard(){
    const w=datasets?.transfers?.window||{}, open=!!datasets?.transfers?.window_open;
    const current=datasets?.transfers?.date||'2026-07-01';
    const until=open?w.closes_on:w.opens_on;
    const days=until?Math.max(0,Math.round((Date.parse(until+'T00:00:00Z')-Date.parse(current+'T00:00:00Z'))/86400000)):null;
    return `<section class="tc-card tc-market-window"><div class="tc-window-top"><span class="tc-calendar-icon" aria-hidden="true">▦</span><div><h3>Transfer Window</h3><strong class="${open?'tc-positive':'tc-muted'}"><span class="tc-window-dot"></span>${open?'Open':'Closed'}</strong><p>${open?'Closes':'Next opening'} ${formatDate(until)}</p></div></div>
      ${days!=null?`<div class="tc-window-track"><span style="width:${Math.max(6,Math.min(100,open?Math.round(days/62*100):Math.round(days/180*100)))}%"></span></div><small>${days} days ${open?'remaining':'to next window'}</small>`:''}</section>`;
  }
  function hero(){
    const t=datasets?.transfers||{}, f=datasets?.finances||{},ci=club(t.club_id,t.club);
    return `<section class="tc-card tc-hero" data-fm-club-theme="${esc(t.club_id)}" data-fm-club-name="${esc(t.club)}" aria-label="Club transfer summary">
      <div class="tc-hero-art" role="img" aria-label="Generic footballer and transfer documents"></div>
      <div class="tc-club-block">${crest(t.club_id,t.club,'tc-club-large')}<div><h2>${esc(ci.display_name)}</h2><p>${esc(t.club_league||'')}</p><button class="tc-button" type="button" data-tc-club="${esc(t.club_id)}">View Club →</button></div></div>
      <div class="tc-hero-finances"><div><small>Transfer Budget</small><strong>${brief(t.available_transfer_budget_gbp)}</strong><span>Available to spend</span><button class="tc-button" data-tc-finances type="button">View Finances →</button></div><div><small>Wage Budget</small><strong>${f.wage_budget_weekly_gbp==null?'—':brief(f.wage_budget_weekly_gbp)+'/wk'}</strong><span>Current wage bill: ${f.weekly_payroll_gbp==null?'—':brief(f.weekly_payroll_gbp)+'/wk'}</span></div></div>
    </section>`;
  }
  function draw(){
    if(!host||!datasets?.transfers)return;
    const filtered=typeFilter!=='all';
    host.innerHTML=`<div class="tc-centre">
      ${message?`<div class="tc-banner" role="status">${esc(message)}<button type="button" class="tc-button" data-tc-dismiss>×</button></div>`:''}
      <div class="tc-top-grid">${hero()}${windowCard()}</div>
      <div class="tc-filter-bar"><span class="tc-filter-label">Offer type</span>${[['all','All offers'],['transfer','Transfers'],['loan','Loans']].map(([v,n])=>`<button type="button" class="tc-type-button ${typeFilter===v?'is-selected':''}" data-tc-type="${v}" aria-pressed="${typeFilter===v}">${n}</button>`).join('')}
        <button class="tc-button tc-prepare-loan" type="button" data-tc-open-loans>+ Start loan negotiation →</button></div>
      <div class="tc-offer-grid">${offerPanel('received')}${offerPanel('sent')}</div>
      <div class="tc-bottom-grid">${shortList()}${financeCard()}${marketActivity()}</div>
      ${historyPanel()}
    </div>`;
    host.setAttribute('aria-busy',String(busy));
    window.FMClubIdentity?.paintWithin?.(host);
  }
  async function refresh(){
    if(!host)return;const serial=++loadSerial;busy=true;
    if(!datasets)host.innerHTML='<section class="tc-card tc-loading">Loading your transfer centre…</section>';
    const fetchJson=async url=>{const resp=await fetch(url,{cache:'no-store'});if(!resp.ok)throw Error(`${url}: HTTP ${resp.status}`);return resp.json();};
    const results=await Promise.allSettled([fetchJson('/api/transfers'),fetchJson('/api/scouting/hub'),fetchJson('/api/loans'),fetchJson('/api/finances')]);
    if(serial!==loadSerial||!host)return;
    busy=false;
    if(results[0].status!=='fulfilled'){
      host.innerHTML=`<section class="tc-card tc-loading"><h3>Transfer data unavailable</h3><p>${esc(results[0].reason?.message||'Unable to contact the game server.')}</p><button type="button" class="tc-button" data-tc-retry>Retry</button></section>`;return;
    }
    datasets={transfers:results[0].value,scouting:results[1].status==='fulfilled'?results[1].value:null,
      loans:results[2].status==='fulfilled'?results[2].value:null,finances:results[3].status==='fulfilled'?results[3].value:null};
    const missing=['scouting','loans','finances'].filter(k=>!datasets[k]);
    message=missing.length?`Some live panels could not load (${missing.join(', ')}). Reload to try again.`:message;
    await window.FMClubIdentity?.ready;
    if(serial!==loadSerial||!host)return;
    window.FMClubIdentity?.applyShell?.(datasets.transfers.club_id,datasets.transfers.club);
    draw();
  }
  async function updateShortlist(id){
    if(busy)return;busy=true;host.setAttribute('aria-busy','true');
    try{
      const response=await fetch('/api/scouting',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action:'shortlist_remove',player_id:id})});
      const result=await response.json();if(!response.ok)throw Error(result.error||`HTTP ${response.status}`);
      message='Player removed from shortlist.';await refresh();
    }catch(e){busy=false;message='Could not update shortlist: '+e.message;draw();}
  }
  function handleClick(e){
    const node=e.target.closest('button');if(!node||!host?.contains(node))return;
    if(node.hasAttribute('data-tc-dismiss')){message='';draw();return;}
    if(node.hasAttribute('data-tc-retry')){refresh();return;}
    if(node.hasAttribute('data-tc-scout')){nav()?.navigate?.('Scouting');window.FMScouting?.showSearch?.();return;}
    if(node.hasAttribute('data-tc-finances')){nav()?.navigate?.('Finances');return;}
    if(node.dataset.tcClub){nav()?.club?.(node.dataset.tcClub);return;}
    if(node.dataset.tcDeal){nav()?.negotiateDeal?.(node.dataset.tcDeal);return;}
    if(node.dataset.tcLoan){nav()?.loanTalk?.(node.dataset.tcLoan);return;}
    if(node.dataset.tcPlayer){nav()?.negotiatePlayer?.(node.dataset.tcPlayer);return;}
    if(node.dataset.tcShortRemove){updateShortlist(node.dataset.tcShortRemove);return;}
    if(node.hasAttribute('data-tc-open-loans')){nav()?.loanPlayer?.();return;}
    if(node.dataset.tcType){typeFilter=node.dataset.tcType;draw();return;}
    if(node.dataset.tcExpand){expanded[node.dataset.tcExpand]=!expanded[node.dataset.tcExpand];draw();return;}
  }
  function handleChange(e){if(e.target.matches('[data-tc-priority]')){priorityFilter=e.target.value;draw();}}
  function handleInput(e){if(e.target.matches('[data-tc-query]')){
    const input=e.target,selection=input.selectionStart;query=input.value;draw();const replacement=host.querySelector('[data-tc-query]');replacement?.focus();
    if(selection!=null)replacement?.setSelectionRange(selection,selection);
  }}
  function mount(element){
    if(host!==element){host=element;host.addEventListener('click',handleClick);host.addEventListener('change',handleChange);host.addEventListener('input',handleInput);datasets=null;}
    refresh();
  }
  window.FMTransferCentre=Object.freeze({mount,refresh});
})();
