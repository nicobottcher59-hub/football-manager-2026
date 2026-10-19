'use strict';
/* TS-24.3.1. Scouting discovery and a separate club negotiation view.
 * Economics, validation and provisional settlements remain Python-owned.
 */
(() => {
  let host=null,model=null,busy=false,view='scouting',tab='players',search='',position='all',
      minOvr='',maxAge='',chosen=null,dealId=null,countering=false,lastError='',loansModel=null,loanMode='active',loanQuery='',loanSelected=null;
  const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const money=n=>`\u00a3${Math.max(0,Number(n)||0).toLocaleString('en-GB',{maximumFractionDigits:0})}`;
  const brief=n=>{const v=Math.max(0,Number(n)||0);return v>=1e6?`\u00a3${(v/1e6).toFixed(1).replace(/\.0$/,'')}M`:v>=1e3?`\u00a3${(v/1e3).toFixed(v<1e4?1:0).replace(/\.0$/,'')}K`:money(v);};
  const seasonDate=(str,years)=>{const [y,m,d]=(str||'2026-08-01').split('-').map(Number);return `${y+years}-${String(m).padStart(2,'0')}-${String(d).padStart(2,'0')}`;};
  const statuses={manager_turn:'Decision required',agreed:'Club agreement reached',completed:'Transfer completed',failed:'Player talks failed',rejected:'Rejected',withdrawn:'Withdrawn',expired:'Expired'};
  const opt=(v,t,s)=>`<option value="${esc(v)}" ${String(v)===String(s)?'selected':''}>${esc(t)}</option>`;
  const player=()=>model?.targets?.find(p=>p.id===chosen)||null;
  const deal=()=>model?.offers?.find(d=>d.id===dealId)||null;
  const openDeal=pid=>model?.offers?.find(d=>d.player_id===pid&&['manager_turn','agreed'].includes(d.status))||null;
  const scoutInfo=()=>model?.professional_scouting||{assignments:[],reports:[],free_slots:0,capacity:0,occupied:0,scout_count:0};
  const pendingScout=id=>scoutInfo().assignments.find(a=>a.player_id===id);
  const completedScout=id=>scoutInfo().reports.find(r=>r.player_id===id);
  const scoutButton=id=>{
    const active=pendingScout(id),done=completedScout(id);
    if(active)return `<button class="tr-btn" type="button" data-tr-scout-reports="${esc(id)}">Scouting ${active.progress}%</button>`;
    if(done)return `<button class="tr-btn" type="button" data-tr-scout-reports="${esc(id)}">View report</button>`;
    return `<button class="tr-btn" type="button" data-tr-scout-assign="${esc(id)}" ${scoutInfo().free_slots<=0?'disabled':''} title="${scoutInfo().free_slots<=0?'All scouting places are occupied':'Start a professional scouting report'}">Scout player</button>`;
  };
  const opponent=d=>d.direction==='outgoing'?d.seller:d.buyer;
  const nav=()=>window.FMNavigation;
  const controls=(name,value,note)=>`<div class="tr-stat"><small>${esc(name)}</small><strong>${esc(value)}</strong><span>${esc(note)}</span></div>`;
  const selectedFilters=()=>{
    const query=search.trim().toLowerCase(),ovr=Number(minOvr)||0,age=Number(maxAge)||200;
    return (model?.targets||[]).filter(p=>
      (position==='all'||p.position===position)&&p.ovr>=ovr&&p.age<=age&&
      `${p.name} ${p.club} ${p.position}`.toLowerCase().includes(query))
      .sort((a,b)=>Number(b.value_gbp<=model.available_transfer_budget_gbp)-Number(a.value_gbp<=model.available_transfer_budget_gbp)||b.ovr-a.ovr||b.value_gbp-a.value_gbp||a.name.localeCompare(b.name));
  };
  function offerEntry(d,inbox=false){
    return `<article class="tr-discussion-card"><div class="tr-discussion-primary"><span class="tr-kicker">${d.direction==='outgoing'?'YOUR OFFER':'OFFER RECEIVED'} ${inbox?'\u00b7 INBOX':''}</span>
       <strong>${esc(d.player)}</strong><small>${esc(opponent(d))} \u00b7 ${esc(d.updated_on)}</small></div>
       <div class="tr-discussion-price"><strong>${brief(d.fixed_gbp)}</strong><span>Guaranteed \u00b7 ${brief(d.valuation.headline_gbp)} possible</span></div>
       <div class="tr-discussion-status"><strong class="${d.status==='agreed'?'tr-ok':''}">${esc(statuses[d.status]||d.status)}</strong><small>${esc(d.reason||'')}</small></div>
       <button class="tr-btn tr-btn-primary" type="button" data-tr-deal="${esc(d.id)}">Open negotiation \u2192</button></article>`;
  }
  function scoutingReportsHub(){
    const s=scoutInfo();
    const active=s.assignments.map(a=>`<article class="tr-discussion-card tr-scout-card"><div class="tr-discussion-primary"><span class="tr-kicker">IN PROGRESS · ${a.progress}%</span><strong>${esc(a.name)}</strong><small>${esc(a.scout)} · ${a.days_left===null?'Paused until a scout is available':`Approximately ${a.days_left} day(s) remaining`}</small></div><div class="tr-discussion-price"><strong>${a.progress}%</strong><span>Observation completed</span></div><button class="tr-btn" type="button" data-tr-scout-cancel="${esc(a.player_id)}">Cancel</button></article>`).join('');
    const reports=s.reports.map(r=>`<article class="tr-discussion-card tr-scout-report"><div class="tr-discussion-primary"><span class="tr-kicker">REPORT · ${esc(r.date)}</span><strong>${esc(r.name)}</strong><small>${esc(r.club)} · ${esc(r.position)} · ${r.age} yrs · ${esc(r.scout)}</small><p class="tr-scout-summary">${esc(r.verdict)}</p><small>Strongest visible attributes: ${r.strengths.map(esc).join(', ')}</small></div><div class="tr-discussion-price"><strong>${Number(r.ovr).toFixed(1)} GRL</strong><span>Value at report: ${brief(r.value_gbp)}</span></div><div class="tr-prospect-actions"><button class="tr-btn" type="button" data-tr-profile-scout="${esc(r.player_id)}">Profile</button>${model.targets.some(p=>p.id===r.player_id)&&((new Date(model.date)-new Date(r.date))/86400000)>=30?`<button class="tr-btn" type="button" data-tr-scout-assign="${esc(r.player_id)}" ${s.free_slots<=0?'disabled':''}>Refresh report</button>`:''}</div></article>`).join('');
    return `<section class="tr-panel tr-scout-hub"><div class="tr-heading-row"><div><h3>Professional scout reports</h3><p>Optional evaluations based on visible player data. Reports arrive as career days pass; more and better scouts cover more players and work faster.</p></div><span class="tr-tag">${s.occupied} / ${s.capacity} active slots · ${s.scout_count} scouts</span></div>
      <h4>Players being observed</h4>${active||'<div class="tr-empty">No active assignments. Choose Scout player in Player search.</div>'}
      <h4>Completed reports (${s.reports.length})</h4>${reports||'<div class="tr-empty">Your professional scouts have not delivered a report yet.</div>'}
      <p class="tr-footnote">Reports are snapshots from the recorded date. GRL, attributes, profiles and negotiations stay available without scouting.</p></section>`;
  }
  function searchView(){
    const offers=model.offers||[], incoming=offers.filter(d=>d.direction==='incoming');
    const list=selectedFilters(),positions=[...new Set(model.targets.map(p=>p.position))].sort();
    const shown=tab==='received'?incoming:offers;
    const marketNews=model.world_transfers||[];
    return `<div class="tr-hub">
       <header class="tr-hub-hero"><div class="tr-kicker">RECRUITMENT \u00b7 FIRST TEAM</div><h2>Scouting centre</h2><p>Discover players across England, review club offers and start a dedicated negotiation when you are ready.</p>
         <div class="tr-hub-facts"><span>Available budget <b>${brief(model.available_transfer_budget_gbp)}</b></span><span>Active negotiations <b>${offers.filter(d=>d.status==='manager_turn').length}</b></span><span>Offers received <b>${incoming.length}</b></span><span>Window <b>${model.window_open?'Open':'Closed'}</b></span></div></header>
       <nav class="tr-tabs" role="tablist" aria-label="Scouting sections">
        ${[['players','Player search'],['reports',`Scout reports (${scoutInfo().reports.length})`],['negotiations',`Negotiations (${offers.length})`],['received',`Offers received (${incoming.length})`],['world',`World transfers (${marketNews.length})`],['loans','Loans & free agents']].map(([id,label])=>`<button type="button" data-tr-tab="${id}" role="tab" aria-selected="${tab===id}">${label}</button>`).join('')}</nav>
       ${tab==='loans'?loanHub():tab==='reports'?scoutingReportsHub():tab==='world'?`<section class="tr-panel tr-negotiations-list"><div class="tr-heading-row"><div><h3>Recent world transfers</h3><p>Completed purchases between AI-managed clubs. No transfers are created by opening this page.</p></div></div>${marketNews.length?marketNews.map(d=>`<article class="tr-discussion-card"><div class="tr-discussion-primary"><span class="tr-kicker">${esc(d.date)}</span><strong>${esc(d.player)}</strong><small>${esc(d.from_club)} → ${esc(d.to_club)}</small></div><div class="tr-discussion-price"><strong>${brief(d.fee_gbp)}</strong><span>Guaranteed transfer fee</span></div></article>`).join(''):'<div class="tr-empty">No AI transfers recorded yet. Clubs review their squads during the transfer windows.</div>'}</section>`:tab==='players'?`<section class="tr-panel tr-discover"><div class="tr-heading-row"><div><h3>Find your next signing</h3><p>These are estimates, not guaranteed asking prices. Open the player profile or make an offer.</p></div><span class="tr-tag">${list.length} matches</span></div>
         <div class="tr-scout-filters"><label><span>Player or club</span><input id="tr-search" type="search" placeholder="Search players and clubs" value="${esc(search)}" autocomplete="off" /></label>
           <label><span>Position</span><select id="tr-position">${[['all','All positions'],...positions.map(x=>[x,x])].map(([a,b])=>opt(a,b,position)).join('')}</select></label>
           <label><span>Minimum GRL</span><select id="tr-min-ovr">${[['','Any level'],['55','55+'],['65','65+'],['70','70+'],['75','75+'],['80','80+'],['85','85+']].map(([a,b])=>opt(a,b,minOvr)).join('')}</select></label>
           <label><span>Maximum age</span><select id="tr-max-age">${[['','Any age'],['18','18'],['21','21'],['24','24'],['29','29'],['34','34']].map(([a,b])=>opt(a,b,maxAge)).join('')}</select></label></div>
         <div class="tr-scout-count">${Math.min(list.length,80)} shown of ${list.length} results \u00b7 Affordable players first, then highest GRL</div>
         <div class="tr-discover-list">${list.slice(0,80).map(p=>`<article class="tr-prospect"><div class="tr-prospect-badge">${esc(p.position)}</div><div class="tr-prospect-name"><strong>${esc(p.name)}</strong><small>${esc(p.club)} \u00b7 ${p.age} years \u00b7 Contract until ${esc(p.contract_until)}</small></div><div class="tr-prospect-rating"><strong>${p.ovr.toFixed(1)}</strong><small>GRL</small></div><div class="tr-prospect-value"><strong>${brief(p.value_gbp)}</strong><small>Market estimate</small></div><div class="tr-prospect-actions">${scoutButton(p.id)}<button class="tr-btn" type="button" data-tr-profile="${esc(p.id)}">Profile</button><button class="tr-btn tr-btn-primary" type="button" data-tr-player="${esc(p.id)}">${openDeal(p.id)?'Open negotiation':'Make offer'} \u2192</button></div></article>`).join('')}
           ${!list.length?'<div class="tr-empty">No players match those filters.</div>':''}</div>
       </section>`:`<section class="tr-panel tr-negotiations-list"><div class="tr-heading-row"><div><h3>${tab==='received'?'Offers received':'Your negotiations'}</h3><p>Open any discussion to review the offer and its full history.</p></div></div>${shown.length?shown.map(d=>offerEntry(d,tab==='received')).join(''):'<div class="tr-empty">No offers here yet. Browse players to start a negotiation.</div>'}</section>`}
       <p class="tr-footnote">New bids open during January, July and August. Professional scout reports are now available and optional. Knowledge limits remain planned for TS-27. Club offers reserve money until player and agent agree personal terms; a completed deal moves the player and money.</p>
       </div>`;
  }
  const loanPlayer=(p)=>`<span class="tr-loan-person"><strong>${esc(p.name)}</strong><small>${esc(p.position||'?')} · ${Number(p.ovr||0).toFixed(1)} GRL · ${p.age||'?'} yrs</small></span>`;
  const loanMoney=(n)=>brief(n||0);
  function loanHub(){
    if(!loansModel)return '<section class="tr-panel"><h3>Loans & free agents</h3><p>Loading live player and loan records...</p><button type="button" class="tr-btn" data-tr-loan-reload>Reload</button></section>';
    const data=loansModel;
    let rows='';const filter=loanQuery.trim().toLowerCase();
    if(loanMode==='active'){
      rows=data.loans.filter(l=>!filter||`${l.player.name} ${l.parent} ${l.borrower}`.toLowerCase().includes(filter)).map(l=>`<article class="tr-loan-row">${loanPlayer(l.player)}<div><strong>${esc(l.status)}</strong><small>${esc(l.parent)} → ${esc(l.borrower)}</small></div><div><strong>${esc(l.ends_on)}</strong><small>${l.wage_percent}% borrower wage · ${esc(l.playing_time)} · ${l.appearances} apps · ${l.minutes||0} min${l.target_minutes>0?` / ${l.target_minutes} min target`:``}${l.playing_time_on_track===false?` · BELOW TARGET`:``}</small></div><div class="tr-loan-buttons">${l.status==='active'&&l.parent_id===data.manager_club_id?`<button class="tr-btn" type="button" data-tr-loan-recall="${esc(l.id)}">Recall</button>`:''}${l.status==='active'&&l.borrower_id===data.manager_club_id&&l.option_gbp!==null?`<button class="tr-btn tr-btn-primary" type="button" data-tr-loan-buy="${esc(l.id)}">Buy ${brief(l.option_gbp)}</button>`:''}</div></article>`).join('');
    }else if(loanMode==='outgoing'||loanMode==='incoming'){
      const items=loanMode==='outgoing'?data.outgoing:data.incoming;
      rows=items.filter(p=>!filter||`${p.name} ${p.club}`.toLowerCase().includes(filter)).slice(0,80).map(p=>`<article class="tr-loan-row">${loanPlayer(p)}<div><strong>${loanMoney(p.weekly_gbp)}/week</strong><small>${esc(p.club)}</small></div><button class="tr-btn tr-btn-primary" type="button" data-tr-loan-select="${esc(p.id)}" data-tr-loan-owner="${esc(p.club_id)}">Prepare loan →</button></article>`).join('');
    }else if(loanMode==='free'){
      rows=data.free_agents.filter(p=>!filter||`${p.name} ${p.previous_club}`.toLowerCase().includes(filter)).slice(0,100).map(p=>`<article class="tr-loan-row">${loanPlayer(p)}<div><strong>${loanMoney(p.minimum_weekly_gbp)}/week</strong><small>Former club: ${esc(p.previous_club)}</small></div><button class="tr-btn tr-btn-primary" type="button" data-tr-loan-free="${esc(p.id)}" ${!p.interested?'disabled':''}>${p.interested?'Discuss contract':'Not interested'}</button></article>`).join('');
    }else if(loanMode==='buyback'){
      rows=data.buybacks.map(b=>`<article class="tr-loan-row">${loanPlayer(b.player)}<div><strong>${brief(b.price_gbp)}</strong><small>${esc(b.club)} · until ${esc(b.until)}</small></div><button class="tr-btn tr-btn-primary" type="button" data-tr-loan-buyback="${esc(b.deal_id)}">Activate buyback</button></article>`).join('');
    }
    let form='';
    if(loanSelected){
      if(loanSelected.mode==='loan'){
        const choices=loanSelected.owner===data.manager_club_id?data.destinations:[{id:data.manager_club_id,name:'Your club'}];
        form=`<form id="tr-loan-form" class="tr-loan-form"><div class="tr-heading-row"><h3>Loan proposal</h3><button class="tr-btn" type="button" data-tr-loan-cancel>Cancel</button></div><div class="tr-loan-fields"><label>Borrowing club<select name="borrower_id" required>${choices.map(x=>`<option value="${esc(x.id)}">${esc(x.name)}</option>`).join('')}</select></label><label>Duration<select name="months"><option value="6">6 months</option><option value="12">1 year</option><option value="24">2 years</option></select></label><label>Borrower pays salary (%)<input name="borrower_wage_percent" type="number" min="0" max="100" step="5" value="50" required></label><label>Promised playing time<select name="playing_time"><option value="rotation">Rotation</option><option value="starter">Regular starter</option><option value="backup">Backup</option></select></label><label class="tr-loan-option"><input type="checkbox" id="tr-loan-option-check"> Optional purchase price</label><label>Option fee (£)<input name="option_gbp" type="number" min="5000" step="5000" value="500000" disabled></label></div><button class="tr-btn tr-btn-primary" type="submit">Propose loan</button><p>Loan is subject to the borrowing club's needs, the player's wishes and both clubs' finances.</p></form>`;
      }else if(loanSelected.mode==='free'){
        const a=data.free_agents.find(p=>p.id===loanSelected.id);
        if(a)form=`<form id="tr-free-form" class="tr-loan-form"><div class="tr-heading-row"><h3>Offer contract · ${esc(a.name)}</h3><button class="tr-btn" data-tr-loan-cancel type="button">Cancel</button></div><p>Agent expectation: ${brief(a.minimum_weekly_gbp)}/week · ${esc(a.role)} role</p><div class="tr-loan-fields"><label>Weekly salary (£)<input name="weekly_wage_gbp" type="number" min="75" max="1500000" value="${a.minimum_weekly_gbp}" required></label><label>Duration<select name="years">${[1,2,3,4,5].filter(y=>y<=a.max_years).map(y=>`<option value="${y}">${y} year${y>1?'s':''}</option>`).join('')}</select></label><label>Squad role<select name="role">${['star','important','regular','rotation','backup'].map(r=>`<option value="${r}" ${r===a.role?'selected':''}>${r}</option>`).join('')}</select></label></div><button class="tr-btn tr-btn-primary" type="submit">Offer professional contract</button></form>`;
      }
    }
    return `<section class="tr-panel tr-loan-hub"><div class="tr-heading-row"><div><h3>Loans, free agents & buybacks</h3><p>Half-season, one-season and two-season loans. Optional purchase clauses; no installment payments.</p></div><span class="tr-tag">${data.summary.active} world loans · ${data.summary.unsigned} free agents</span></div><nav class="tr-loan-tabs">${[['active','My loans'],['outgoing','Loan out'],['incoming','Loan in'],['free','Free agents'],['buyback','Buybacks']].map(([id,name])=>`<button type="button" class="tr-btn" data-tr-loan-tab="${id}" aria-pressed="${loanMode===id}">${name}</button>`).join('')}</nav><label class="tr-loan-search">Search <input type="search" id="tr-loan-search" value="${esc(loanQuery)}" placeholder="Search players or clubs"></label>${form}<div class="tr-loan-list">${rows||'<p class="tr-empty">No eligible players or agreements in this category.</p>'}</div>${!data.window_open?'<p class="tr-footnote">New loans and permanent buybacks require an open transfer window (January, July, August). Free agents can sign outside the window.</p>':''}</section>`;
  }
  async function loadLoans(){
    try{const response=await fetch('/api/loans',{cache:'no-store'});if(!response.ok)throw Error('HTTP '+response.status);loansModel=await response.json();if(host&&tab==='loans')draw();}
    catch(error){window.alert('Loans: '+error.message);}
  }
  async function postLoan(command){
    if(busy)return false;
    busy=true;host.setAttribute('aria-busy','true');
    try{const response=await fetch('/api/loans',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(command)});const data=await response.json();if(!response.ok)throw Error(data.error||'HTTP '+response.status);return true;}
    catch(error){window.alert('Loans: '+error.message);return false;}
    finally{busy=false;host?.setAttribute('aria-busy','false');}
  }
  function rowBonus(i,bonus){
    const limits={'appearances':[10,100],'goals':[5,40],'assists':[5,35],'promotion':[1,1]};
    const kind=bonus?.kind||'appearances',pair=limits[kind]||limits.appearances;
    const threshold=bonus?.threshold??(kind==='promotion'?1:kind==='appearances'?20:10);
    return `<div class="tr-clause tr-bonus-row" data-tr-bonus-row><div class="tr-clause-type"><span class="tr-clause-icon">+</span><label><span>Achievement</span><select data-tr-bonus-kind>${[['appearances','Appearances'],['goals','Goals scored'],['assists','Assists'],['promotion','Promotion']].map(([a,b])=>opt(a,b,kind)).join('')}</select></label></div>
       <label><span>Trigger</span><input data-tr-bonus-threshold type="number" min="${pair[0]}" max="${pair[1]}" step="1" value="${threshold}" ${kind==='promotion'?'readonly':''} required /></label>
       <label><span>Bonus amount (\u00a3)</span><input data-tr-bonus-amount type="number" min="10000" max="500000000" step="10000" value="${bonus?.amount_gbp??10000}" required /></label>
       <button type="button" class="tr-icon-button" data-tr-remove-bonus aria-label="Remove bonus">\u00d7</button></div>`;
  }
  function compose(dealRecord){
    const p=player(), t=countering&&dealRecord?dealRecord.terms:null;
    const fixed=t?.fixed_gbp??Math.max(5000,Math.round((p?.value_gbp||dealRecord?.market_value_gbp||1000000)*.98/5000)*5000);
    const bs=t?.bonuses||[],isSell=t&&t.sell_on_type!=='none',isBuy=t&&t.buyback_gbp!==null;
    const newOfferClosed=!model.window_open&&!dealRecord;
    return `<section class="tr-panel tr-proposal"><div class="tr-panel-top"><div><div class="tr-kicker">${countering?'YOUR COUNTEROFFER':'YOUR PROPOSAL'}</div><h3>${countering?'Reply with new terms':'Build your offer'}</h3><p>Start with a guaranteed fee. Optional clauses appear only when you add them.</p></div><span class="tr-tag">No instalments</span></div>
       ${newOfferClosed?'<p class="tr-terms-warning">Transfer window closed. New offers open in January, July and August. Existing talks can still be reviewed.</p>':''}
       <form id="tr-offer-form"><label class="tr-fee-label"><span>Guaranteed payment (\u00a3)</span><input name="fixed_gbp" type="number" min="5000" max="500000000" step="5000" required value="${fixed}" /></label>
         <div class="tr-clause-section"><div class="tr-clause-heading"><div><strong>Performance bonuses</strong><small>Uncertain payments do not count as guaranteed money.</small></div><button class="tr-btn tr-btn-outline" data-tr-add-bonus type="button" ${bs.length>=3?'disabled':''}>+ Add bonus</button></div><div id="tr-bonuses">${bs.map((b,i)=>rowBonus(i,b)).join('')}</div><p class="tr-clause-empty" data-tr-bonuses-empty ${bs.length?'hidden':''}>No performance bonuses selected.</p></div>
         <div class="tr-clause-section"><div class="tr-clause-heading"><div><strong>Future sale percentage</strong><small>Sell-on share of the next fee or of the profit, never both.</small></div><button class="tr-btn tr-btn-outline" data-tr-toggle-sell type="button">${isSell?'Remove clause':'+ Add clause'}</button></div>
           <div id="tr-sell-fields" ${!isSell?'hidden':''}><label><span>Mechanism</span><select name="sell_on_type">${[['gross','Percentage of next sale'],['profit','Percentage of next profit']].map(([a,b])=>opt(a,b,t?.sell_on_type||'gross')).join('')}</select></label><label><span>Seller percentage (%)</span><input name="sell_on_percent" type="number" min="1" max="35" step="1" value="${isSell?t.sell_on_percent:15}" /></label></div>
           <p class="tr-clause-empty" data-tr-sell-empty ${isSell?'hidden':''}>No sell-on clause selected.</p></div>
         <div class="tr-clause-section"><div class="tr-clause-heading"><div><strong>Buyback option</strong><small>The selling club may try to buy back the player, subject to consent.</small></div><button class="tr-btn tr-btn-outline" data-tr-toggle-buy type="button">${isBuy?'Remove clause':'+ Add clause'}</button></div>
           <div id="tr-buy-fields" ${!isBuy?'hidden':''}><label><span>Buyback price (\u00a3)</span><input name="buyback_gbp" type="number" min="5000" max="500000000" step="5000" value="${isBuy?t.buyback_gbp:''}" /></label><label><span>Valid until</span><input name="buyback_until" type="date" min="${esc(model.date)}" max="${seasonDate(model.date,5)}" value="${isBuy?t.buyback_until:''}" /></label></div>
           <p class="tr-clause-empty" data-tr-buy-empty ${isBuy?'hidden':''}>No buyback option selected.</p></div>
         <div class="tr-proposal-actions"><button class="tr-btn tr-btn-outline" type="button" data-tr-preview>Evaluate risk</button><button class="tr-btn tr-btn-primary" type="submit" ${newOfferClosed?'disabled':''}>${countering?'Send counteroffer':'Submit offer'} \u2192</button>${countering?'<button class="tr-btn" type="button" data-tr-cancel-counter>Cancel</button>':''}</div>
         <div id="tr-preview" class="tr-preview" aria-live="polite"><span>Only the fixed fee is guaranteed. Extra clauses are optional.</span></div></form></section>`;
  }
  function discussion(d){
    const history=d.history||[];
    return `<section class="tr-panel tr-timeline"><div class="tr-panel-top"><div><div class="tr-kicker">CLUB CONVERSATION</div><h3>Negotiation history</h3></div><span class="tr-tag">${history.length} ${history.length===1?'message':'messages'}</span></div>
      <div class="tr-thread">${history.map((e,i)=>`<article class="tr-message ${e.by_manager?'is-own':''}"><div class="tr-message-dot"></div><div class="tr-message-content"><div class="tr-message-meta"><strong>${esc(e.by_club)}</strong><time>${esc(e.on_date)}</time></div><p>${esc(e.note)}</p><strong class="tr-message-fee">${brief(e.terms.fixed_gbp)} guaranteed</strong><span>${e.terms.bonuses.length?`${e.terms.bonuses.length} conditional ${e.terms.bonuses.length===1?'bonus':'bonuses'}`:'No bonuses'}${e.terms.sell_on_type!=='none'?` \u00b7 ${e.terms.sell_on_percent}% sell-on`:''}${e.terms.buyback_gbp!==null?' \u00b7 Buyback option':''}</span></div></article>`).join('')}</div>
      <div class="tr-discussion-outcome ${d.status==='agreed'?'is-agreed':''}"><strong>${esc(statuses[d.status]||d.status)}</strong><p>${esc(d.reason||'')}</p><small>Expires ${esc(d.expires_on)}</small></div></section>`;
  }
  function personalPane(d){
    const q=d.personal_quote||{};
    if(d.direction==='incoming')return `<section class="tr-panel tr-personal-panel"><div class="tr-kicker">PLAYER & AGENT · FINAL APPROVAL</div><h3>Complete sale to ${esc(d.buyer)}</h3>
       <p>Your club agreed to sell for ${brief(d.fixed_gbp)}. The buying club must still agree wages and convince the player. This step can fail.</p>
       <p class="tr-agent-expectation">${esc(q.reason||'The player decides whether to accept the destination.')}</p>
       <button class="tr-btn tr-btn-primary" type="button" data-tr-personal-resolve="${esc(d.id)}">Ask player and agent to decide →</button></section>`;
    const t=d.personal_status==='counter'&&d.personal_terms?d.personal_terms:null;
    const suggested=q.weekly_wage_gbp||10000,possible=q.interested!==false;
    return `<section class="tr-panel tr-personal-panel"><div class="tr-kicker">STEP 2 · PERSONAL CONTRACT</div><h3>Negotiate with the player and agent</h3>
       <p>A club agreement alone cannot move this player. The footballer evaluates your division, ambitions, squad role, wage and contract duration.</p>
       <div class="tr-agent-expectation"><strong>${possible?'Agent expectations':'Player is unlikely to join'}</strong><span>${esc(q.reason||'')}</span>
       ${possible?`<span>Indicative salary: <b>${money(suggested)}/week</b> · Role: <b>${esc(q.role||'regular')}</b> · Suggested signing bonus: <b>${brief(q.suggested_signing_bonus_gbp||0)}</b></span>`:''}</div>
       ${d.personal_status==='counter'?`<div class="tr-agent-counter"><strong>Agent counteroffer received</strong><p>The player requests ${money(t.weekly_wage_gbp)}/week, ${esc(t.role)} role, ${t.years} years and ${brief(t.signing_bonus_gbp)} signing-on fee.</p>
           <button type="button" class="tr-btn tr-btn-primary" data-tr-personal-accept="${esc(d.id)}">Accept agent terms and complete transfer →</button></div>`:''}
       <form id="tr-personal-form"><div class="tr-personal-fields">
         <label><span>Weekly salary (£)</span><input name="weekly_wage_gbp" type="number" min="75" max="1500000" step="25" required value="${t?.weekly_wage_gbp??suggested}" /></label>
         <label><span>Contract length</span><select name="years">${Array.from({length:q.max_years||5},(_,i)=>opt(i+1,`${i+1} ${i===0?'year':'years'}`,t?.years||q.years||3)).join('')}</select></label>
         <label><span>Promised squad role</span><select name="role">${[['star','Star player'],['important','Important player'],['regular','Regular starter'],['rotation','Rotation'],['backup','Backup']].map(([a,b])=>opt(a,b,t?.role||q.role||'regular')).join('')}</select></label>
         <label><span>Signing-on bonus (£)</span><input name="signing_bonus_gbp" type="number" min="0" max="50000000" step="5000" value="${t?.signing_bonus_gbp??0}" required /></label>
       </div><div class="tr-proposal-actions"><button class="tr-btn tr-btn-primary" type="submit">${possible?'Offer personal terms':'Ask player for decision'} →</button></div></form>
       <p class="tr-footnote">The transfer fee, signing bonus and weekly wage must fit your budgets. No money is paid before the player accepts.</p>
       ${d.personal_history?.length?`<div class="tr-personal-history"><h4>Agent conversation</h4>${d.personal_history.map(e=>`<p><b>${e.actor==='club'?'Your club':'Player agent'}:</b> ${esc(e.note)} · ${money(e.terms.weekly_wage_gbp)}/week · ${esc(e.terms.role)}</p>`).join('')}</div>`:''}
       </section>`;
  }
  function negotiationView(){
    const d=deal(),p=player(),reference=p?.value_gbp||d?.market_value_gbp||0;
    if(!p&&!d)return `<div class="tr-immersive"><button class="tr-btn" data-tr-back>\u2190 Back to Scouting</button><p class="tr-empty">This player or discussion is no longer available. Try the Scouting search.</p></div>`;
    const label=d?.player||p?.name,club=d?opponent(d):p.club;
    const status=d?statuses[d.status]||d.status:'Preparing a first offer';
    const previous=openDeal(p?.id);
    const editable=!d && !previous || countering&&d?.may_answer;
    const actions=d&&d.may_answer&&!countering ? `<section class="tr-panel tr-reply"><div><strong>It is your turn to decide</strong><p>Review the club's current proposal before replying.</p></div><div class="tr-reply-buttons"><button type="button" class="tr-btn tr-btn-primary" data-tr-accept="${esc(d.id)}">Accept club terms</button><button type="button" class="tr-btn" data-tr-counter="${esc(d.id)}">Counteroffer</button><button type="button" class="tr-btn tr-btn-danger" data-tr-reject="${esc(d.id)}">Reject</button></div></section>`:'';
    return `<div class="tr-immersive"><header class="tr-immersive-header"><button type="button" class="tr-back" data-tr-back>\u2190 Back to ${window.FMNavigation?.previousLabel?.()||'Scouting'}</button><div class="tr-immersive-tag">TS-24.4 \u00b7 TRANSFER NEGOTIATION</div></header>
      <section class="tr-neg-hero"><div class="tr-neg-crest">\u2694</div><div class="tr-neg-title"><div class="tr-kicker">${esc(model.club)} \u00b7 ${esc(club)}</div><h2>${esc(label)}</h2><p>${p?`${p.age} years old \u00b7 ${esc(p.position)} \u00b7 ${p.ovr.toFixed(1)} GRL`:esc(d?.direction==='incoming'?'You are the selling club':'Transfer proposal')}</p><span class="tr-current-status">${esc(status)}</span></div><div class="tr-neg-stats">${controls('Market estimate',brief(reference),'Not an asking price')}${controls('Available to spend',brief(model.available_transfer_budget_gbp),'Guaranteed fee budget')}${controls('Current proposal',d?brief(d.fixed_gbp):'New','Guaranteed payment')}</div></section>
      ${d?.status==='agreed'?`<div class="tr-accepted-banner">Club terms agreed. The next step is the player and agent. No fee has been paid yet.</div>`:''}
      ${actions}
      <div class="tr-neg-layout"><div class="tr-neg-main">${d?.status==='agreed'?personalPane(d):''}${d?.status==='completed'?`<section class="tr-panel tr-personal-complete"><div class="tr-kicker">REGISTRATION CONFIRMED</div><h3>Transfer completed</h3><p>${esc(d.player)} has joined ${esc(d.buyer)}. ${brief(d.fixed_gbp)} guaranteed was paid to ${esc(d.seller)}.</p><p>${d.personal_terms?`${money(d.personal_terms.weekly_wage_gbp)} per week · ${d.personal_terms.years} years · ${esc(d.personal_terms.role)}`:''}</p><p>Conditional bonuses and buyback conditions remain saved for future settlement.</p></section>`:''}${previous&&!d?`<section class="tr-panel tr-locked"><div class="tr-kicker">EXISTING DISCUSSION</div><h3>Club conversation in progress</h3><p>There is already an active proposal for this player. Continue it instead of submitting a duplicate offer.</p><button type="button" class="tr-btn tr-btn-primary" data-tr-deal="${esc(previous.id)}">Continue negotiation →</button></section>`:editable?compose(d):(d?.status==='agreed'||d?.status==='completed')?'':d?`<section class="tr-panel tr-locked"><div class="tr-kicker">CURRENT CLUB TERMS</div><h3>${brief(d.fixed_gbp)} guaranteed</h3><p>Maximum headline: ${brief(d.valuation.headline_gbp)} \u00b7 Risk-adjusted: ${brief(d.valuation.risk_adjusted_gbp)}</p>${d.status==='manager_turn'&&!d.may_answer?'<p>Awaiting the other club.</p>':''}${d.status==='manager_turn'&&!d.may_answer?`<button class="tr-btn tr-btn-danger" type="button" data-tr-withdraw="${esc(d.id)}">Withdraw proposal</button>`:''}</section>`:''}
        <div class="tr-terms-warning">Club offers alone do not transfer a player. Player consent and an affordable contract complete registration and guaranteed payment. Future conditional clauses remain recorded.</div></div>
        <aside class="tr-neg-sidebar">${d?discussion(d):`<section class="tr-panel tr-timeline"><div class="tr-kicker">CONVERSATION</div><h3>Start negotiations</h3><p>Submit your offer to receive a response. Every subsequent counteroffer will be saved here.</p><div class="tr-thread-empty">No messages yet</div></section>`}</aside></div>
      </div>`;
  }
  function draw(){
    if(!host||!model)return;
    host.innerHTML=view==='negotiation'?negotiationView():searchView();
    host.setAttribute('aria-busy',String(busy));
  }
  function validateTerms(){
    const form=host.querySelector('#tr-offer-form');if(!form)throw Error('No negotiation offer form is available');
    if(!form.reportValidity())throw Error('Check the amounts and terms in your offer');
    const bonuses=[],kinds=new Set();
    for(const row of form.querySelectorAll('[data-tr-bonus-row]')){
      const kind=row.querySelector('[data-tr-bonus-kind]').value;
      if(kinds.has(kind))throw Error('Each bonus trigger can only be used once');
      kinds.add(kind);
      bonuses.push({kind,threshold:Number(row.querySelector('[data-tr-bonus-threshold]').value),amount_gbp:Number(row.querySelector('[data-tr-bonus-amount]').value)});
    }
    const fixed=Number(form.elements.namedItem('fixed_gbp').value);
    const sell=host.querySelector('#tr-sell-fields');
    const buy=host.querySelector('#tr-buy-fields');
    const sellActive=sell&&!sell.hidden,buyActive=buy&&!buy.hidden;
    const buybackPrice=buyActive?Number(form.elements.namedItem('buyback_gbp').value):null;
    const buybackDate=buyActive?form.elements.namedItem('buyback_until').value:null;
    if(buyActive&&(!buybackDate||!buybackPrice))throw Error('Set both buyback price and expiry, or remove the clause');
    const terms={fixed_gbp:fixed,bonuses,sell_on_type:sellActive?form.elements.namedItem('sell_on_type').value:'none',
      sell_on_percent:sellActive?Number(form.elements.namedItem('sell_on_percent').value):0,
      buyback_gbp:buybackPrice,buyback_until:buybackDate||null};
    if(!Number.isSafeInteger(fixed)||fixed<5000||bonuses.some(b=>!Number.isSafeInteger(b.amount_gbp)||!Number.isSafeInteger(b.threshold)))throw Error('Use valid integer offer values');
    if(terms.fixed_gbp>model.available_transfer_budget_gbp && (!deal()||deal().direction==='outgoing'))throw Error('The guaranteed amount exceeds your available transfer budget');
    return terms;
  }
  async function postScout(command){
    if(busy)return;
    busy=true;host?.setAttribute('aria-busy','true');
    try{
      const response=await fetch('/api/scouting',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(command)});
      const payload=await response.json();if(!response.ok)throw Error(payload.error||`HTTP ${response.status}`);
      await refresh();
    }catch(error){window.alert('Scouting: '+String(error.message||error));}
    finally{busy=false;host?.setAttribute('aria-busy','false');}
  }
  async function post(command){
    if(busy)return null;
    busy=true;host.setAttribute('aria-busy','true');
    try{
      const res=await fetch('/api/transfers',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(command)});
      const data=await res.json();if(!res.ok)throw Error(data.error||`HTTP ${res.status}`);return data;
    }catch(error){lastError=String(error.message||error);window.alert(`Negotiation: ${lastError}`);return null;}
    finally{busy=false;host?.setAttribute('aria-busy','false');}
  }
  async function refresh(){
    if(!host)return;
    try{const response=await fetch('/api/transfers',{cache:'no-store'});if(!response.ok)throw Error(`HTTP ${response.status}`);model=await response.json();draw();}
    catch(error){host.innerHTML=`<section class="tr-panel"><h3>Scouting unavailable</h3><p>${esc(error.message)}</p><button class="tr-btn" type="button" data-tr-refresh>Retry</button></section>`;}
  }
  function mount(element,options={}){
    if(host!==element){host=element;listen();}
    const next=options.view==='negotiation'?'negotiation':'scouting';
    view=next;chosen=options.playerId||null;dealId=options.dealId||null;countering=false;
    if(options.tab)tab=options.tab;
    if(tab==='loans')loadLoans();
    host.innerHTML='<section class="tr-panel">Loading scouting...</section>';refresh();
  }
  function toggleClause(type){
    const body=host.querySelector(`#tr-${type}-fields`),empty=host.querySelector(`[data-tr-${type}-empty]`);
    if(!body)return;body.hidden=!body.hidden;if(empty)empty.hidden=!body.hidden;
    const button=host.querySelector(`[data-tr-toggle-${type}]`);if(button)button.textContent=body.hidden?'+ Add clause':'Remove clause';
    body.querySelectorAll('input,select').forEach(field=>{field.disabled=body.hidden;field.required=!body.hidden;});
  }
  function listen(){
    host.addEventListener('click',async ev=>{
      const button=ev.target.closest('button');if(!button||!host.contains(button))return;
      if(button.dataset.trTab){tab=button.dataset.trTab;draw();if(tab==='loans')loadLoans();return;}
      if(button.dataset.trLoanTab){loanMode=button.dataset.trLoanTab;loanSelected=null;draw();return;}
      if(button.hasAttribute('data-tr-loan-reload')){await loadLoans();return;}
      if(button.hasAttribute('data-tr-loan-cancel')){loanSelected=null;draw();return;}
      if(button.dataset.trLoanSelect){loanSelected={mode:'loan',id:button.dataset.trLoanSelect,owner:button.dataset.trLoanOwner};draw();return;}
      if(button.dataset.trLoanFree){loanSelected={mode:'free',id:button.dataset.trLoanFree};draw();return;}
      if(button.dataset.trLoanRecall){if(window.confirm('Recall player from loan?')){if(await postLoan({action:'loan_recall',loan_id:button.dataset.trLoanRecall}))await loadLoans();}return;}
      if(button.dataset.trLoanBuy){if(window.confirm('Exercise the agreed purchase option and sign the player immediately?')){if(await postLoan({action:'loan_buy_option',loan_id:button.dataset.trLoanBuy}))await loadLoans();}return;}
      if(button.dataset.trLoanBuyback){if(window.confirm('Activate the agreed buyback and negotiate an immediate return?')){if(await postLoan({action:'buyback',deal_id:button.dataset.trLoanBuyback}))await loadLoans();}return;}
      if(button.dataset.trScoutAssign){await postScout({action:'assign',player_id:button.dataset.trScoutAssign});return;}
      if(button.dataset.trScoutCancel){if(window.confirm('Cancel this scouting observation?'))await postScout({action:'cancel',player_id:button.dataset.trScoutCancel});return;}
      if(button.dataset.trScoutReports){tab='reports';draw();return;}
      if(button.dataset.trProfileScout){const id=button.dataset.trProfileScout;const match=model.targets.find(p=>p.id===id);if(match)nav()?.club(match.club_id,id);else window.alert('This player is no longer listed in a professional first team.');return;}
      if(button.dataset.trPlayer){const old=openDeal(button.dataset.trPlayer);
        if(old)nav()?.negotiateDeal(old.id);else nav()?.negotiatePlayer(button.dataset.trPlayer);return;}
      if(button.dataset.trProfile){const p=model.targets.find(x=>x.id===button.dataset.trProfile);if(p)nav()?.club(p.club_id,p.id);return;}
      if(button.dataset.trDeal){nav()?.negotiateDeal(button.dataset.trDeal);return;}
      if(button.hasAttribute('data-tr-back')){nav()?.back();return;}
      if(button.hasAttribute('data-tr-refresh')){refresh();return;}
      if(button.hasAttribute('data-tr-add-bonus')){
        const holder=host.querySelector('#tr-bonuses');if(!holder||holder.children.length>=3)return;
        holder.insertAdjacentHTML('beforeend',rowBonus(holder.children.length));
        host.querySelector('[data-tr-bonuses-empty]').hidden=true;button.disabled=holder.children.length>=3;return;
      }
      if(button.hasAttribute('data-tr-remove-bonus')){
        button.closest('[data-tr-bonus-row]')?.remove();const holder=host.querySelector('#tr-bonuses');
        if(holder){host.querySelector('[data-tr-bonuses-empty]').hidden=holder.children.length>0;host.querySelector('[data-tr-add-bonus]').disabled=holder.children.length>=3;}return;
      }
      if(button.hasAttribute('data-tr-toggle-sell')){toggleClause('sell');return;}
      if(button.hasAttribute('data-tr-toggle-buy')){toggleClause('buy');return;}
      if(button.hasAttribute('data-tr-counter')){countering=true;draw();return;}
      if(button.hasAttribute('data-tr-cancel-counter')){countering=false;draw();return;}
      if(button.hasAttribute('data-tr-personal-resolve')){
        if(!window.confirm('Let the buying club and player negotiate wages? If accepted, the sale completes immediately.'))return;
        if(await post({action:'personal_resolve',deal_id:button.dataset.trPersonalResolve}))await refresh();return;
      }
      if(button.hasAttribute('data-tr-personal-accept')){
        if(!window.confirm('Accept these player-agent conditions and complete the transfer?'))return;
        if(await post({action:'personal_accept',deal_id:button.dataset.trPersonalAccept}))await refresh();return;
      }
      if(button.hasAttribute('data-tr-preview')){
        let terms;try{terms=validateTerms();}catch(error){window.alert(error.message);return;}
        const p=player();if(!p||countering){const div=host.querySelector('#tr-preview');if(div)div.textContent='Risk preview is available for a new bid on a rival player.';return;}
        const result=await post({action:'preview',seller_id:p.club_id,player_id:p.id,terms});
        if(result){const output=host.querySelector('#tr-preview');if(output)output.innerHTML=`<strong>${brief(result.valuation.risk_adjusted_gbp)} risk-adjusted</strong><span>${brief(result.valuation.headline_gbp)} is only the maximum possible amount, not guaranteed.</span><small>This is not the seller\'s private acceptance price.</small>`;}
        return;
      }
      const action=button.hasAttribute('data-tr-accept')?'accept':button.hasAttribute('data-tr-reject')?'reject':button.hasAttribute('data-tr-withdraw')?'withdraw':null;
      if(action){const id=button.dataset.trAccept||button.dataset.trReject||button.dataset.trWithdraw;
        if(!window.confirm(action==='accept'?'Agree club terms and proceed to player/agent negotiations?':`${action==='reject'?'Reject':'Withdraw'} this offer?`))return;
        if(await post({action,deal_id:id}))await refresh();
      }
    });
    host.addEventListener('change',ev=>{
      const field=ev.target;
      if(field.id==='tr-loan-option-check'){const amount=host.querySelector('[name=option_gbp]');if(amount)amount.disabled=!field.checked;return;}
      if(field.id==='tr-position'){position=field.value;draw();return;}
      if(field.id==='tr-min-ovr'){minOvr=field.value;draw();return;}
      if(field.id==='tr-max-age'){maxAge=field.value;draw();return;}
      if(field.matches('[data-tr-bonus-kind]')){
        const row=field.closest('[data-tr-bonus-row]');if(!row)return;
        const limits={appearances:[10,100,20],goals:[5,40,10],assists:[5,35,10],promotion:[1,1,1]};
        const [min,max,value]=limits[field.value],threshold=row.querySelector('[data-tr-bonus-threshold]');
        threshold.min=String(min);threshold.max=String(max);threshold.value=String(value);threshold.readOnly=field.value==='promotion';
      }
    });
    host.addEventListener('input',ev=>{
      if(ev.target.id==='tr-loan-search'){loanQuery=ev.target.value;draw();const input=host.querySelector('#tr-loan-search');input?.focus();input?.setSelectionRange(loanQuery.length,loanQuery.length);return;}
      if(ev.target.id!=='tr-search')return;
      search=ev.target.value;const start=ev.target.selectionStart;draw();
      const input=host.querySelector('#tr-search');input?.focus();if(start!==null)input?.setSelectionRange(start,start);
    });
    host.addEventListener('submit',async ev=>{
      if(ev.target.id==='tr-loan-form'){
        ev.preventDefault();const f=ev.target;if(!f.reportValidity()||!loanSelected)return;
        const cmd={action:'loan_offer',player_id:loanSelected.id,parent_id:loanSelected.owner,borrower_id:f.elements.namedItem('borrower_id').value,months:Number(f.elements.namedItem('months').value),borrower_wage_percent:Number(f.elements.namedItem('borrower_wage_percent').value),playing_time:f.elements.namedItem('playing_time').value,option_gbp:f.elements.namedItem('option_gbp').disabled?null:Number(f.elements.namedItem('option_gbp').value)};
        if(window.confirm('Send this temporary loan proposal?')){if(await postLoan(cmd)){loanSelected=null;loanMode='active';await loadLoans();}}return;
      }
      if(ev.target.id==='tr-free-form'){
        ev.preventDefault();const f=ev.target;if(!f.reportValidity()||!loanSelected)return;
        const cmd={action:'sign_free_agent',player_id:loanSelected.id,weekly_wage_gbp:Number(f.elements.namedItem('weekly_wage_gbp').value),years:Number(f.elements.namedItem('years').value),role:f.elements.namedItem('role').value};
        if(window.confirm('Offer a professional contract to this free agent?')){if(await postLoan(cmd)){loanSelected=null;await loadLoans();}}return;
      }
      if(ev.target.id==='tr-personal-form'){
        ev.preventDefault();const form=ev.target,d=deal();if(!d||!form.reportValidity())return;
        const terms={weekly_wage_gbp:Number(form.elements.namedItem('weekly_wage_gbp').value),
          years:Number(form.elements.namedItem('years').value),role:form.elements.namedItem('role').value,
          signing_bonus_gbp:Number(form.elements.namedItem('signing_bonus_gbp').value)};
        if(!window.confirm(`Offer ${money(terms.weekly_wage_gbp)}/week, ${terms.years} years and ${money(terms.signing_bonus_gbp)} signing bonus?`))return;
        if(await post({action:'personal_offer',deal_id:d.id,terms}))await refresh();return;
      }
      if(ev.target.id!=='tr-offer-form')return;ev.preventDefault();
      let terms;try{terms=validateTerms();}catch(error){window.alert(error.message);return;}
      const p=player(),d=deal();
      const command=countering&&d?{action:'counter',deal_id:d.id,terms}:
        p?{action:'submit',seller_id:p.club_id,player_id:p.id,terms}:null;
      if(!command)return;
      if(!window.confirm(`Send ${money(terms.fixed_gbp)} guaranteed, with ${terms.bonuses.length} performance bonuses? No money moves yet.`))return;
      const result=await post(command);if(!result)return;
      countering=false;
      if(result.deal_id&&!dealId)nav()?.negotiateDeal(result.deal_id,true);
      else await refresh();
    });
  }
  window.FMTransfers=Object.freeze({mount,refresh});
})();
