'use strict';
/* TS-24.3.1. Scouting discovery and a separate club negotiation view.
 * Economics, validation and provisional settlements remain Python-owned.
 */
(() => {
  let host=null,model=null,busy=false,view='scouting',tab='players',search='',position='all',
      minOvr='',maxAge='',chosen=null,dealId=null,countering=false,lastError='',loansModel=null,loanMode='active',loanQuery='',loanSelected=null,requestedLoanTalk=null,dealMode='transfer',loanDrafts=new Map(),transferDrafts=new Map();
  const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const money=n=>`\u00a3${Math.max(0,Number(n)||0).toLocaleString('en-GB',{maximumFractionDigits:0})}`;
  const brief=n=>{const v=Math.max(0,Number(n)||0);return v>=1e6?`\u00a3${(v/1e6).toFixed(1).replace(/\.0$/,'')}M`:v>=1e3?`\u00a3${(v/1e3).toFixed(v<1e4?1:0).replace(/\.0$/,'')}K`:money(v);};
  const seasonDate=(str,years)=>{const [y,m,d]=(str||'2026-08-01').split('-').map(Number);return `${y+years}-${String(m).padStart(2,'0')}-${String(d).padStart(2,'0')}`;};
  const statuses={manager_turn:'Decision required',agreed:'Club agreement reached',pending_window:'Awaiting registration',completed:'Transfer completed',failed:'Player talks failed',rejected:'Rejected',withdrawn:'Withdrawn',expired:'Expired'};
  const opt=(v,t,s)=>`<option value="${esc(v)}" ${String(v)===String(s)?'selected':''}>${esc(t)}</option>`;
  const loanPerson=(pid)=>[...(loansModel?.outgoing||[]),...(loansModel?.incoming||[])].find(p=>p.id===pid)||null;
  const player=()=>model?.targets?.find(p=>p.id===chosen)||model?.offers?.find(d=>d.id===dealId)?.player_profile||loanPerson(chosen||loanSelected?.id)||null;
  const currentLoanTalk=()=>loansModel?.negotiations?.find(t=>t.id===loanSelected?.talkId)||null;
  const loanCounterpart=()=>{
    const own=model.club_id, talk=currentLoanTalk(),p=player()||{};
    const parent=talk?.parent_id||loanSelected?.owner||p.club_id||own;
    const outgoing=parent===own;
    const borrower=talk?.borrower_id||loanSelected?.borrower||(outgoing?null:own);
    const otherId=outgoing?borrower:parent;
    const name=otherId&&(loansModel?.destinations||[]).find(x=>x.id===otherId)?.name||
       (otherId===own?model.club:p.club)||'Choose borrowing club';
    return {parent,borrower,otherId,otherName:name,outgoing,talk};
  };
  const saveDraft=()=>{
    const form=host?.querySelector(dealMode==='loan'?'#tr-loan-form':'#tr-offer-form');
    if(!form)return;
    const data={};form.querySelectorAll('input[name],select[name]').forEach(x=>{
      data[x.name]=x.type==='checkbox'?x.checked:x.value;
    });
    (dealMode==='loan'?loanDrafts:transferDrafts).set(chosen||loanSelected?.id||dealId||'',data);
  };
  const restoreDraft=()=>{
    const form=host?.querySelector(dealMode==='loan'?'#tr-loan-form':'#tr-offer-form');
    const entry=(dealMode==='loan'?loanDrafts:transferDrafts).get(chosen||loanSelected?.id||dealId||'');
    if(!form||!entry)return;
    form.querySelectorAll('input[name],select[name]').forEach(x=>{
      if(!Object.hasOwn(entry,x.name))return;
      if(x.type==='checkbox')x.checked=Boolean(entry[x.name]);
      else x.value=entry[x.name];
    });
    window.FMLoanNegotiations?.sync?.(host);updatePayments();
  };
  const payments=()=>window.FMTransferPayments;
  const deal=()=>model?.offers?.find(d=>d.id===dealId)||null;
  const openDeal=pid=>model?.offers?.find(d=>d.player_id===pid&&['manager_turn','agreed','pending_window'].includes(d.status))||null;
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
  const ownerId = d => d?.status==='completed' ? d.buyer_id : d?.seller_id;
  const ownerName = d => d?.status==='completed' ? d.buyer : d?.seller;
  const clubVisual = (clubId, name) => window.FMClubIdentity?.resolve?.(clubId,name)||{display_name:name||clubId||'Club',crest:null};
  const transferCrest=(clubId,name,big=false)=>{
    const item=clubVisual(clubId,name),asset=item.crest;
    const source=asset&&(window.FMEntityAssets?.url?.(asset)||'/portable/'+asset);
    const kind=big?'tr-neg-club-image':'tr-small-club-image';
    return source?`<img class="${kind}" src="${esc(source)}" alt="" data-fm-asset="optional" loading="lazy">`:
      `<span class="${kind} tr-club-placeholder" aria-label="${esc(item.display_name)} placeholder crest">${esc(item.display_name.split(/\s+/).slice(0,2).map(x=>x[0]).join(''))}</span>`;
  };
  const nav=()=>window.FMNavigation;
  const controls=(name,value,note)=>`<div class="tr-stat"><small>${esc(name)}</small><strong>${esc(value)}</strong><span>${esc(note)}</span></div>`;
  const selectedFilters=()=>{
    const query=search.trim().toLowerCase(),ovr=Number(minOvr)||0,age=Number(maxAge)||200;
    return (model?.targets||[]).filter(p=>
      (position==='all'||p.position===position)&&(!ovr||(p.ovr!==null&&p.ovr>=ovr))&&p.age<=age&&
      `${p.name} ${p.club} ${p.position}`.toLowerCase().includes(query))
      .sort((a,b)=>a.name.localeCompare(b.name)||a.id.localeCompare(b.id));
  };
  function offerEntry(d,inbox=false){
    return `<article class="tr-discussion-card"><div class="tr-discussion-primary"><span class="tr-kicker">${d.direction==='outgoing'?'YOUR OFFER':'OFFER RECEIVED'} ${inbox?'\u00b7 INBOX':''}</span>
       <strong>${esc(d.player)}</strong><small>${transferCrest(ownerId(d),ownerName(d))} ${esc(clubVisual(ownerId(d),ownerName(d)).display_name)} \u00b7 ${esc(d.updated_on)}</small></div>
       <div class="tr-discussion-price"><strong>${brief(d.guaranteed_gbp??d.fixed_gbp)}</strong><span>Guaranteed \u00b7 ${brief(d.valuation.headline_gbp)} possible</span></div>
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
      <p class="tr-footnote">Reports are snapshots from the recorded date. Negotiations stay available without scouting; unknown ratings and market values stay hidden.</p></section>`;
  }
  function searchView(){
    const offers=model.offers||[], incoming=offers.filter(d=>d.direction==='incoming');
    const list=selectedFilters(),positions=[...new Set(model.targets.map(p=>p.position))].sort();
    const shown=tab==='received'?incoming:offers;
    const marketNews=model.world_transfers||[];
    return `<div class="tr-hub">
       <header class="tr-hub-hero"><div class="tr-kicker">RECRUITMENT \u00b7 FIRST TEAM</div><h2>Scouting centre</h2><p>Discover players across England, review club offers and start a dedicated negotiation when you are ready.</p>
         <div class="tr-hub-facts"><span>Available budget <b>${brief(model.available_transfer_budget_gbp)}</b></span><span>Active negotiations <b>${offers.filter(d=>d.status==='manager_turn').length}</b></span><span>Offers received <b>${incoming.length}</b></span><span>Window <b>${model.window_open?'Open':'Closed'}</b>${model.window?.closes_on&&model.window_open?` · until ${esc(model.window.closes_on)}`:model.window?.opens_on?` · next ${esc(model.window.opens_on)}`:''}</span></div></header>
       <nav class="tr-tabs" role="tablist" aria-label="Scouting sections">
        ${[['players','Player search'],['reports',`Scout reports (${scoutInfo().reports.length})`],['negotiations',`Negotiations (${offers.length})`],['received',`Offers received (${incoming.length})`],['world',`World transfers (${marketNews.length})`],['loans','Loans & free agents']].map(([id,label])=>`<button type="button" data-tr-tab="${id}" role="tab" aria-selected="${tab===id}">${label}</button>`).join('')}</nav>
       ${tab==='loans'?loanHub():tab==='reports'?scoutingReportsHub():tab==='world'?`<section class="tr-panel tr-negotiations-list"><div class="tr-heading-row"><div><h3>Recent world transfers</h3><p>Completed purchases between AI-managed clubs. No transfers are created by opening this page.</p></div></div>${marketNews.length?marketNews.map(d=>`<article class="tr-discussion-card"><div class="tr-discussion-primary"><span class="tr-kicker">${esc(d.date)}</span><strong>${esc(d.player)}</strong><small>${esc(d.from_club)} → ${esc(d.to_club)}</small></div><div class="tr-discussion-price"><strong>${brief(d.fee_gbp)}</strong><span>Guaranteed transfer fee</span></div></article>`).join(''):'<div class="tr-empty">No AI transfers recorded yet. Clubs review their squads during the transfer windows.</div>'}</section>`:tab==='players'?`<section class="tr-panel tr-discover"><div class="tr-heading-row"><div><h3>Find your next signing</h3><p>These are estimates, not guaranteed asking prices. Open the player profile or make an offer.</p></div><span class="tr-tag">${list.length} matches</span></div>
         <div class="tr-scout-filters"><label><span>Player or club</span><input id="tr-search" type="search" placeholder="Search players and clubs" value="${esc(search)}" autocomplete="off" /></label>
           <label><span>Position</span><select id="tr-position">${[['all','All positions'],...positions.map(x=>[x,x])].map(([a,b])=>opt(a,b,position)).join('')}</select></label>
           <label><span>Minimum GRL</span><select id="tr-min-ovr">${[['','Any level'],['55','55+'],['65','65+'],['70','70+'],['75','75+'],['80','80+'],['85','85+']].map(([a,b])=>opt(a,b,minOvr)).join('')}</select></label>
           <label><span>Maximum age</span><select id="tr-max-age">${[['','Any age'],['18','18'],['21','21'],['24','24'],['29','29'],['34','34']].map(([a,b])=>opt(a,b,maxAge)).join('')}</select></label></div>
         <div class="tr-scout-count">${Math.min(list.length,80)} shown of ${list.length} results \u00b7 Alphabetical order · Unknown ratings never influence sorting</div>
         <div class="tr-discover-list">${list.slice(0,80).map(p=>`<article class="tr-prospect"><div class="tr-prospect-badge">${esc(p.position)}</div><div class="tr-prospect-name"><strong><button type="button" class="ch-link" data-career-type="player" data-career-id="${esc(p.id)}">${esc(p.name)}</button></strong><small>${transferCrest(p.club_id,p.club)} <button type="button" class="ch-link" data-career-type="club" data-career-id="${esc(p.club_id)}">${esc(clubVisual(p.club_id,p.club).display_name)}</button> \u00b7 ${p.age} years \u00b7 Contract until ${esc(p.contract_until)}</small></div><div class="tr-prospect-rating"><strong>${p.ovr==null?'??':p.ovr.toFixed(1)}</strong><small>GRL</small></div><div class="tr-prospect-value"><strong>${p.value_gbp==null?'??':brief(p.value_gbp)}</strong><small>Market estimate</small></div><div class="tr-prospect-actions">${scoutButton(p.id)}<button class="tr-btn" type="button" data-tr-profile="${esc(p.id)}">Profile</button><button class="tr-btn tr-btn-primary" type="button" data-tr-player="${esc(p.id)}">${openDeal(p.id)?'Open negotiation':'Make offer'} \u2192</button></div></article>`).join('')}
           ${!list.length?'<div class="tr-empty">No players match those filters.</div>':''}</div>
       </section>`:`<section class="tr-panel tr-negotiations-list"><div class="tr-heading-row"><div><h3>${tab==='received'?'Offers received':'Your negotiations'}</h3><p>Open any discussion to review the offer and its full history.</p></div></div>${shown.length?shown.map(d=>offerEntry(d,tab==='received')).join(''):'<div class="tr-empty">No offers here yet. Browse players to start a negotiation.</div>'}</section>`}
       <p class="tr-footnote">New bids open during January, July and August. Professional scout reports are now available and optional. Unknown general OVR and market values remain hidden until observed. Club offers reserve money until player and agent agree personal terms; a completed deal moves the player and money.</p>
       </div>`;
  }
  const loanPlayer=(p)=>`<span class="tr-loan-person"><strong>${esc(p.name)}</strong><small>${esc(p.position||'?')} · ${p.ovr==null?'??':Number(p.ovr).toFixed(1)} GRL · ${p.age||'?'} yrs</small></span>`;
  const loanMoney=(n)=>n==null?'??':brief(n);
  function loanHub(){
    if(!loansModel)return '<section class="tr-panel"><h3>Loans & free agents</h3><p>Loading live player and loan records...</p><button type="button" class="tr-btn" data-tr-loan-reload>Reload</button></section>';
    const data=loansModel;
    let rows='';const filter=loanQuery.trim().toLowerCase();
    if(loanMode==='active'){
      rows=data.loans.filter(l=>!filter||`${l.player.name} ${l.parent} ${l.borrower}`.toLowerCase().includes(filter)).map(l=>`<article class="tr-loan-row">${loanPlayer(l.player)}<div><strong>${esc(l.status)}</strong><small>${esc(l.parent)} → ${esc(l.borrower)}</small></div><div><strong>${esc(l.ends_on)}</strong><small>${l.wage_percent}% borrower wage · ${esc(l.playing_time)} · ${l.appearances} apps · ${l.minutes||0} min${l.target_minutes>0?` / ${l.target_minutes} min target`:``}${l.playing_time_on_track===false?` · BELOW TARGET`:``}</small></div><div class="tr-loan-buttons">${l.status==='active'&&l.recall_allowed&&l.parent_id===data.manager_club_id?`<button class="tr-btn" type="button" data-tr-loan-recall="${esc(l.id)}">Recall</button>`:''}${l.option_exercisable&&l.borrower_id===data.manager_club_id&&l.option_gbp!==null?`<button class="tr-btn tr-btn-primary" type="button" data-tr-loan-buy="${esc(l.id)}">Buy ${brief(l.option_gbp)}</button>`:''}</div></article>`).join('');
    }else if(loanMode==='talks'){
      rows=(data.negotiations||[]).filter(t=>!filter||`${t.parent} ${t.borrower} ${t.player_id}`.toLowerCase().includes(filter)).map(t=>`<article class="tr-loan-row"><div><strong>${esc(t.parent)} → ${esc(t.borrower)}</strong><small>${esc(t.status)} · ${esc(t.reason)}</small></div><div><strong>${t.terms.months} months · ${t.terms.borrower_wage_percent}% borrower wage</strong><small>Patience ${t.patience}% · ${t.history.length} messages</small></div><button class="tr-btn tr-btn-primary" type="button" data-tr-loan-talk="${esc(t.id)}">Review discussion</button></article>`).join('');
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
        const talk=(data.negotiations||[]).find(t=>t.id===loanSelected.talkId);
        const entity=[...data.outgoing,...data.incoming].find(p=>p.id===loanSelected.id)||{id:loanSelected.id,name:loanSelected.name||'Player',position:'?',age:'?',ovr:null,nationality:''};
        const owner=loanSelected.owner||talk?.parent_id;
        const borrower=talk?.borrower_id||loanSelected.borrower||data.manager_club_id;
        const counter=talk?.parent_id||owner;
        form=window.FMLoanNegotiations?.render({player:entity,managerId:data.manager_club_id,managerName:data.manager_club_name||model.club,
          parentId:counter,parentName:talk?.parent||(data.destinations.find(x=>x.id===counter)?.name||entity.club||model.club),
          borrowerId:borrower,borrowerName:talk?.borrower||(data.destinations.find(x=>x.id===borrower)?.name||model.club),
          talk,day:data.as_of,destinations:data.destinations})||'<p>Loan negotiation panel unavailable. Reload the game.</p>';
      }else if(loanSelected.mode==='free'){
        const a=data.free_agents.find(p=>p.id===loanSelected.id);
        if(a)form=`<form id="tr-free-form" class="tr-loan-form"><div class="tr-heading-row"><h3>Offer contract · ${esc(a.name)}</h3><button class="tr-btn" data-tr-loan-cancel type="button">Cancel</button></div><p>Agent expectation: ${brief(a.minimum_weekly_gbp)}/week · ${esc(a.role)} role</p><div class="tr-loan-fields"><label>Weekly salary (£)<input name="weekly_wage_gbp" type="number" min="75" max="1500000" value="${a.minimum_weekly_gbp}" required></label><label>Duration<select name="years">${[1,2,3,4,5].filter(y=>y<=a.max_years).map(y=>`<option value="${y}">${y} year${y>1?'s':''}</option>`).join('')}</select></label><label>Squad role<select name="role">${['star','important','regular','rotation','backup'].map(r=>`<option value="${r}" ${r===a.role?'selected':''}>${r}</option>`).join('')}</select></label></div><button class="tr-btn tr-btn-primary" type="submit">Offer professional contract</button></form>`;
      }
    }
    return `<section class="tr-panel tr-loan-hub"><div class="tr-heading-row"><div><h3>Loans, free agents & buybacks</h3><p>Multi-round loan negotiations, salary sharing and complete options to buy. Registrations respect the transfer window.</p></div><span class="tr-tag">${data.summary.active} world loans · ${data.summary.unsigned} free agents</span></div><nav class="tr-loan-tabs">${[['active','My loans'],['talks',`Discussions (${(data.negotiations||[]).length})`],['outgoing','Loan out'],['incoming','Loan in'],['free','Free agents'],['buyback','Buybacks']].map(([id,name])=>`<button type="button" class="tr-btn" data-tr-loan-tab="${id}" aria-pressed="${loanMode===id}">${name}</button>`).join('')}</nav><div id="tr-loan-confirm" hidden></div><label class="tr-loan-search">Search <input type="search" id="tr-loan-search" value="${esc(loanQuery)}" placeholder="Search players or clubs"></label>${form}<div class="tr-loan-list">${rows||'<p class="tr-empty">No eligible players or agreements in this category.</p>'}</div>${!data.window_open?'<p class="tr-footnote">Loans can be negotiated now; registration occurs at the next window. Options to buy can be exercised in the eligible registration window.</p>':''}</section>`;
  }
  async function loadLoans(){
    try{const response=await fetch('/api/loans',{cache:'no-store'});if(!response.ok)throw Error('HTTP '+response.status);loansModel=await response.json();if(host&&(tab==='loans'||view==='loans'||dealMode==='loan')){if(requestedLoanTalk){const talk=loansModel.negotiations?.find(t=>t.id===requestedLoanTalk);if(talk){loanSelected={mode:'loan',id:talk.player_id,owner:talk.parent_id,borrower:talk.borrower_id,talkId:talk.id};chosen=talk.player_id;loanMode='talks';}requestedLoanTalk=null;}draw();}}
    catch(error){const message=host?.querySelector('#ln-feedback');if(message)message.textContent='Loans: '+error.message;else console.error('Loan read:',error.message);}
  }
  async function postLoan(command){
    if(busy)return false;
    busy=true;host.setAttribute('aria-busy','true');
    try{const response=await fetch('/api/loans',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(command)});const data=await response.json();if(!response.ok)throw Error(data.error||'HTTP '+response.status);return data;}
    catch(error){const message=host?.querySelector('#ln-feedback');if(message)message.textContent=error.message;else showFeedback('Loans: '+error.message);return null;}
    finally{busy=false;host?.setAttribute('aria-busy','false');}
  }
  function rowBonus(i,bonus){
    const limits={'appearances':[10,100],'goals':[5,40],'assists':[5,35],'promotion':[1,1]};
    const kind=bonus?.kind||'appearances',pair=limits[kind]||limits.appearances;
    const threshold=bonus?.threshold??(kind==='promotion'?1:kind==='appearances'?20:10);
    return `<div class="tr-clause tr-bonus-row" data-tr-bonus-row><div class="tr-clause-type"><span class="tr-clause-icon">+</span><label><span>Achievement</span><select data-tr-bonus-kind>${[['appearances','Appearances'],['goals','Goals scored'],['assists','Assists'],['promotion','Promotion']].map(([a,b])=>opt(a,b,kind)).join('')}</select></label></div>
       <label><span>Trigger</span><input data-tr-bonus-threshold type="number" min="${pair[0]}" max="${pair[1]}" step="1" value="${threshold}" ${kind==='promotion'?'readonly':''} required /></label>
       <label><span>Bonus amount (\u00a3)</span><input data-tr-bonus-amount data-tr-money type="text" inputmode="numeric" value="${payments().format(bonus?.amount_gbp??0)}" required /></label>
       <button type="button" class="tr-icon-button" data-tr-remove-bonus aria-label="Remove bonus">\u00d7</button></div>`;
  }
  function compose(dealRecord){
    const previousOwn=dealRecord?.history?.filter(e=>e.by_manager).at(-1)?.terms;
    const t=countering&&previousOwn?previousOwn:null;
    const fixed=t?.fixed_gbp??0;
    const bs=t?.bonuses||[],isSell=!!t&&t.sell_on_type!=='none',isBuy=!!t&&t.buyback_gbp!==null;
    const scheduled=!!t?.installments_gbp, count=t?.installment_count||2, interval=t?.installment_interval_months||6;
    const newOfferClosed=false;
    const moneyField=(name,value,label)=>`<div class="tr-money"><span aria-hidden="true">£</span><input type="text" inputmode="numeric" autocomplete="off" name="${name}" ${name==='fixed_gbp'?'id="tr-upfront-field"':''} data-tr-money required value="${payments().format(value)}" aria-label="${label}"><button type="button" class="tr-money-step" data-tr-step="${name}" data-tr-delta="-10000" aria-label="Reduce ${label} by ten thousand pounds">−</button><button type="button" class="tr-money-step" data-tr-step="${name}" data-tr-delta="10000" aria-label="Increase ${label} by ten thousand pounds">+</button></div>`;
    const increments=name=>`<div class="tr-money-increments" aria-label="Manual amount increments">${[1,5,10].map(n=>`<button type="button" class="tr-btn" data-tr-step="${name}" data-tr-delta="${n*1000000}" title="Add ${money(n*1000000)} to your own amount">+£${n}M</button>`).join('')}</div>`;
    return `<section class="tr-panel tr-proposal"><div class="tr-panel-top"><div><div class="tr-kicker">YOUR OFFER</div><h3>Build your offer</h3><p>Set your upfront payment. Add installments or optional clauses only when you need them.</p></div></div>
      ${!model.window_open?`<p class="tr-terms-warning">Window closed: you can negotiate now. A signed deal will be registered no earlier than ${esc(model.window?.opens_on||'the next window')}.</p>`:''}
      <form id="tr-offer-form" novalidate>
        ${player()?.club_id===model.club_id&&!dealRecord?`<label class="tr-offer-buyer">Potential buying club<select name="buyer_id" required><option value="">Choose club…</option>${(loansModel?.destinations||[]).filter(x=>x.id!==model.club_id).map(x=>`<option value="${esc(x.id)}">${esc(x.name)}</option>`).join('')}</select></label>`:''}
        <div class="tr-upfront-section"><label for="tr-upfront-field">Upfront payment (£)</label><div class="tr-amount-row">${moneyField('fixed_gbp',fixed,'Upfront payment')}${increments('fixed_gbp')}</div></div>
        <div class="tr-installments-section"><div class="tr-clause-heading"><div><strong>Installments <span class="tr-muted">(optional)</span></strong><small>Add a separate amount, payable after registration.</small></div><label class="tr-switch"><input id="tr-installments-enabled" type="checkbox" role="switch" aria-label="Add payment in installments" ${scheduled?'checked':''}><span></span></label></div>
          <div id="tr-installments-fields" ${scheduled?'':'hidden'}>
            <div class="tr-installment-total"><label>Total installment amount (£)</label>${moneyField('installments_gbp',t?.installments_gbp||0,'Total installment amount')}</div>
            <div class="tr-sliders"><label><strong>Number of payments</strong><input type="range" name="installment_count" min="0" max="2" step="1" value="${[2,4,6].indexOf(count)}" aria-label="Number of installments" aria-valuetext="${count} payments"><span class="tr-slider-marks"><span>2</span><span>4</span><span>6</span></span></label>
              <label><strong>Payment frequency</strong><input type="range" name="installment_interval_months" min="0" max="2" step="1" value="${[6,12,18].indexOf(interval)}" aria-label="Months between payments" aria-valuetext="Every ${interval} months"><span class="tr-slider-marks"><span>Every 6 months</span><span>Every 12 months</span><span>Every 18 months</span></span></label></div>
            <div id="tr-installment-summary" class="tr-installment-summary" aria-live="polite"></div>
          </div>
        </div>
        <div class="tr-clause-section"><div class="tr-clause-heading"><div><strong>Performance bonuses <span class="tr-muted">(optional)</span></strong><small>Only paid if the agreed milestone is reached.</small></div><button class="tr-btn" data-tr-add-bonus type="button" ${bs.length>=3?'disabled':''}>+ Add bonus</button></div><div id="tr-bonuses">${bs.map((b,i)=>rowBonus(i,b)).join('')}</div><p class="tr-clause-empty" data-tr-bonuses-empty ${bs.length?'hidden':''}>No performance bonuses added.</p></div>
        <div class="tr-clause-section"><div class="tr-clause-heading"><div><strong>Future sale percentage</strong><small>Percentage of the next fee or of the profit, never both.</small></div><button class="tr-btn" data-tr-toggle-sell type="button">${isSell?'Remove clause':'+ Add clause'}</button></div>
          <div id="tr-sell-fields" ${isSell?'':'hidden'}><label><span>Mechanism</span><select name="sell_on_type">${[['gross','Percentage of next sale'],['profit','Percentage of next profit']].map(([a,b])=>opt(a,b,t?.sell_on_type||'gross')).join('')}</select></label><label><span>Seller percentage (%)</span><input name="sell_on_percent" type="number" min="1" max="35" step="1" value="${isSell?t.sell_on_percent:15}"></label></div><p class="tr-clause-empty" data-tr-sell-empty ${isSell?'hidden':''}>No sell-on clause added.</p></div>
        <div class="tr-clause-section"><div class="tr-clause-heading"><div><strong>Buyback option</strong><small>A future return to the selling club still requires player consent.</small></div><button class="tr-btn" data-tr-toggle-buy type="button">${isBuy?'Remove clause':'+ Add clause'}</button></div>
          <div id="tr-buy-fields" ${isBuy?'':'hidden'}><label><span>Buyback price (£)</span><input name="buyback_gbp" type="text" inputmode="numeric" data-tr-money value="${isBuy?payments().format(t.buyback_gbp):'0'}"></label><label><span>Valid until</span><input name="buyback_until" type="date" min="${esc(model.date)}" max="${seasonDate(model.date,5)}" value="${isBuy?t.buyback_until:''}"></label></div><p class="tr-clause-empty" data-tr-buy-empty ${isBuy?'hidden':''}>No buyback option added.</p></div>
        <div class="tr-proposal-actions"><button class="tr-btn" type="button" data-tr-preview>Evaluate proposal</button><button class="tr-btn tr-btn-primary" type="submit" ${newOfferClosed?'disabled':''}>${dealRecord?'Send counteroffer':'Submit offer'} →</button><button class="tr-btn" type="button" data-tr-reset>Reset terms</button><button class="tr-btn tr-btn-danger tr-walk-away" type="button" ${dealRecord?`data-tr-withdraw="${esc(dealRecord.id)}"`:'data-tr-back'}>Walk away</button></div>
        <div id="tr-preview" class="tr-preview" aria-live="polite">Upfront + installments are guaranteed. Performance bonuses are conditional.</div>
      </form></section>`;
  }

  function updatePayments(){
    const form=host?.querySelector('#tr-offer-form');if(!form)return;
    const enabled=form.querySelector('#tr-installments-enabled').checked;
    const fields=form.querySelector('#tr-installments-fields');fields.hidden=!enabled;
    fields.querySelectorAll('input,button').forEach(el=>el.disabled=!enabled);
    const count=[2,4,6][Number(form.elements.namedItem('installment_count').value)];
    const interval=[6,12,18][Number(form.elements.namedItem('installment_interval_months').value)];
    form.elements.namedItem('installment_count').setAttribute('aria-valuetext',`${count} payments`);
    form.elements.namedItem('installment_interval_months').setAttribute('aria-valuetext',`Every ${interval} months`);
    const output=form.querySelector('#tr-installment-summary');
    try{
      const total=payments().amount(form.elements.namedItem('installments_gbp').value);
      const initial=payments().amount(form.elements.namedItem('fixed_gbp').value);
      const rows=payments().schedule(total,count,interval,model.date);
      output.innerHTML=rows.length?`<div><strong>${count} payments · every ${interval} months</strong><span>${money(rows[0].amount_gbp)} each${total%count?' (rounding on final payment)':''} · ${count*interval} months total</span></div><div class="tr-payment-timeline">${rows.map(r=>`<span><i></i><b>+${r.months} months</b><small>${esc(r.due_on)}</small><small>${money(r.amount_gbp)}</small></span>`).join('')}</div><small>Total guaranteed: <b>${money(initial+total)}</b>. Dates shown assume registration today; actual dates start when the transfer completes.</small>`:'<span>Enter the total amount to split into installments. No amount is suggested.</span>';
    }catch(error){output.textContent=error.message;}
  }

  function discussion(d){
    const history=[...(d?.prior_loan_history||[]),...(d?.history||[])], tolerance=d?.tolerance||{level:'Open',remaining_percent:100};
    const own=model.club_id, otherId=d?(d.seller_id===own?d.buyer_id:d.seller_id):player()?.club_id;
    const otherName=d?(d.seller_id===own?d.buyer:d.seller):player()?.club;
    const other=clubVisual(otherId,otherName);
    const lastOther=[...history].reverse().find(e=>!e.by_manager&&e.mode!=='loan');
    const terms=lastOther?.terms;
    const accepted=['agreed','pending_window','completed'].includes(d?.status);
    const label=d?.status==='manager_turn'?'Counteroffer received':d?statuses[d.status]:'Opening talks';
    const tension=['Closed','Critical'].includes(tolerance.level)?'is-critical':tolerance.level==='Tense'?'is-tense':'';
    const termRows=terms?`<dl class="tr-stance-list"><div><dt>Upfront payment</dt><dd>${brief(terms.fixed_gbp)}</dd></div><div><dt>Total installments</dt><dd>${brief(terms.installments_gbp||0)}</dd></div>${terms.installments_gbp?`<div><dt>Payment schedule</dt><dd>${terms.installment_count} · every ${terms.installment_interval_months} months</dd></div>`:''}<div><dt>Guaranteed total</dt><dd>${brief(terms.fixed_gbp+(terms.installments_gbp||0))}</dd></div><div><dt>Conditional bonuses</dt><dd>${terms.bonuses.length?brief(terms.bonuses.reduce((s,b)=>s+b.amount_gbp,0)):'None'}</dd></div></dl>`:'<p class="tr-empty-stance">No club terms received yet. Submit your own proposal to start the discussion.</p>';
    const features=terms?[terms.installments_gbp?'Installments on the stated schedule':'Upfront payment',...(terms.bonuses.length?['Performance milestones']:[]),...(terms.sell_on_percent?[`${terms.sell_on_percent}% of future ${terms.sell_on_type==='profit'?'profit':'fee'}`]:[]),...(terms.buyback_gbp?['Buyback option']:[])]:[];
    return `<section class="tr-panel tr-negotiation-status"><div class="tr-status-heading"><div class="tr-kicker">NEGOTIATION STATUS</div><span class="tr-status-chip ${tension}">${esc(label)}</span></div>
      <div class="tr-patience"><strong>Relationship & tolerance</strong><div class="tr-tolerance-row"><div class="tr-tolerance-track" role="meter" aria-label="Negotiation patience" aria-valuemin="0" aria-valuemax="100" aria-valuenow="${tolerance.remaining_percent}" aria-valuetext="${esc(tolerance.level)}"><i style="left:${Math.max(1,Math.min(99,100-tolerance.remaining_percent))}%"></i></div><span class="tr-tolerance-label ${tension}">${esc(tolerance.level)}</span></div><p>${esc(d?.reason||'The selling club is ready to hear your proposal. This bar shows patience, not an acceptance probability.')}</p></div>
      <div class="tr-stance-cards"><section class="tr-stance-card"><h4>Current club terms</h4><div class="tr-party">${transferCrest(otherId,otherName)}<span><strong>${esc(other.display_name)}</strong><small>${lastOther?'Their communicated proposal':'Awaiting a first response'}</small></span></div>${termRows}
        ${d?.may_answer?`<div class="tr-stance-actions"><button type="button" class="tr-btn tr-btn-primary" data-tr-accept="${esc(d.id)}">Accept club terms</button><button type="button" class="tr-btn tr-btn-danger" data-tr-reject="${esc(d.id)}">Reject</button></div>`:''}</section>
      <section class="tr-stance-card"><h4>What they're open to</h4><div class="tr-party">${transferCrest(otherId,otherName)}<span><strong>${esc(other.display_name)}</strong><small>Based on actual discussions</small></span></div>${features.length?`<ul class="tr-communicated-terms">${features.map(x=>`<li>${esc(x)}</li>`).join('')}</ul>`:'<p class="tr-empty-stance">Not yet communicated.</p>'}<p class="tr-knowledge-note">No hidden price range or private acceptance threshold is shown.</p></section></div>
      <div class="tr-thread-section"><div class="tr-kicker">CONVERSATION</div><div class="tr-thread" role="log" aria-label="Negotiation conversation">${history.length?[...history].reverse().map(e=>`<article class="tr-message ${e.by_manager?'is-own':''}" data-fm-club-theme="${esc(e.by_club_id)}" data-fm-club-name="${esc(e.by_club)}"><div class="tr-message-dot"></div>${transferCrest(e.by_club_id,e.by_club)}<div class="tr-message-content"><div class="tr-message-meta"><strong>${esc(clubVisual(e.by_club_id,e.by_club).display_name)}</strong><time>${esc(e.on_date)}</time></div><p>${esc(e.note)}</p><strong class="tr-message-fee">${e.mode==='loan'?`Loan · ${e.terms.months} months · ${e.terms.borrower_wage_percent}% wages`:brief(e.terms.fixed_gbp)+' upfront'+(e.terms.installments_gbp?' + '+brief(e.terms.installments_gbp)+' in installments':'')}</strong>${e.mode!=='loan'&&e.terms.installments_gbp?`<span>${e.terms.installment_count} payments · every ${e.terms.installment_interval_months} months</span>`:''}<span>${e.mode==='loan'?'Proposed role: '+esc(e.terms.playing_time):(e.terms.bonuses||[]).length?e.terms.bonuses.map(b=>`${brief(b.amount_gbp)} after ${b.threshold} ${esc(b.kind)}`).join(' · '):'No performance bonuses'}${e.mode!=='loan'&&e.terms.sell_on_percent?` · ${e.terms.sell_on_percent}% future ${e.terms.sell_on_type==='profit'?'profit':'fee'}`:''}${e.mode!=='loan'&&e.terms.buyback_gbp?` · Buyback ${brief(e.terms.buyback_gbp)}`:''}</span></div></article>`).join(''):'<div class="tr-thread-empty">No messages yet. Your opening amount is entirely your choice.</div>'}</div></div>
      ${accepted?'<p class="tr-terms-warning">Club agreement reached. Registration and player consent determine the actual transfer date.</p>':''}</section>`;
  }

  function personalPane(d){
    const q=d.personal_quote||{};
    if(d.direction==='incoming')return `<section class="tr-panel tr-personal-panel"><div class="tr-kicker">PLAYER & AGENT · FINAL APPROVAL</div><h3>Complete sale to ${esc(d.buyer)}</h3>
       <p>Your club agreed to ${brief(d.fixed_gbp)} upfront plus ${brief(d.terms.installments_gbp||0)} in guaranteed installments. The buying club must still agree wages and convince the player. This step can fail.</p>
       <p class="tr-agent-expectation">${esc(q.reason||'The player decides whether to accept the destination.')}</p>
       <button class="tr-btn tr-btn-primary" type="button" data-tr-personal-resolve="${esc(d.id)}">Ask player and agent to decide →</button></section>`;
    const quote=d.personal_quote||{};
    const talk={mode:'transfer',dealId:d.id,status:d.personal_status||'open',
      patience:d.personal_patience??100,counter:d.personal_terms,
      history:d.personal_history||[],reason:(d.personal_status==='counter'?d.reason:'')};
    return window.FMContractNegotiations?.form({quote,talk,id:'tr-personal-form'})||
      '<section class="tr-panel">Contract negotiation module unavailable. Reload the game.</section>';
  }
  function embeddedLoanView(){
    if(!loansModel)return '<section class="tr-panel"><h3>Loading loan terms…</h3><p>The player and conversation will stay on this page.</p></section>';
    const context=loanCounterpart(),p=player()||{id:chosen,name:'Player',age:'?',position:'?',ovr:null};
    if(!context.parent)return '<section class="tr-panel">Choose a player before preparing the loan.</section>';
    return window.FMLoanNegotiations?.render?.({
      embedded:true,player:{...p,name:p.name||p.full_name||'Player'},
      managerId:model.club_id,managerName:model.club,
      parentId:context.parent,parentName:context.parent===model.club_id?model.club:(p.club||context.otherName),
      borrowerId:context.borrower,borrowerName:context.borrower===model.club_id?model.club:context.otherName,
      talk:context.talk,day:loansModel.as_of||model.date,
      destinations:loansModel.destinations||[]})||
      '<section class="tr-panel">Loan offer editor unavailable. Reload the game.</section>';
  }
  function negotiationView(){
    const d=deal(),p=player()||d?.player_profile;
    if(!p&&!d)return `<div class="tr-immersive"><button class="tr-btn" data-tr-back>← Back to Scouting</button><p class="tr-empty">This player or negotiation is no longer available.</p></div>`;
    const actual=p||{}, own=model.club_id;
    const loanContext=dealMode==='loan'?loanCounterpart():null;
    const otherId=loanContext?.otherId||(d?(d.seller_id===own?d.buyer_id:d.seller_id):actual.club_id);
    const otherName=loanContext?.otherName||(d?(d.seller_id===own?d.buyer:d.seller):actual.club);
    const other=clubVisual(otherId,otherName),manager=clubVisual(own,model.club);
    const nation=window.FMPortraits?.nation?.(actual.nationality,'tr-player-nation')||esc(actual.nationality||'');
    const face=window.FMPortraits?.portrait?.(actual,'tr-player-face')||`<span class="tr-player-face">${esc(actual.name?.[0]||'?')}</span>`;
    const previous=dealMode==='transfer'&&!d?openDeal(actual.id):null;
    const editable=(!d&&!previous)||d?.may_answer;
    const knowledge=actual.knowledge_source==='scout_report'?`Report: ${actual.observed_on}`:actual.knowledge_source==='public'?'Public knowledge':actual.knowledge_source==='own_club'?'Your player':'Not scouted';
    let content;
    if(d?.status==='pending_window')content=`<section class="tr-panel tr-personal-complete"><div class="tr-kicker">SIGNED · AWAITING REGISTRATION</div><h3>Transfer agreed</h3><p>The club and player have agreed. The player stays with ${esc(clubVisual(d.seller_id,d.seller).display_name)} until the next buying-club transfer window opens.</p><strong>Planned arrival: ${esc(d.arrival_on||'Next available window')}</strong><p>No fee has been charged and no registration has taken place yet. Financial and squad eligibility are checked at registration.</p></section>`;
    else if(d?.status==='agreed')content=personalPane(d);
    else if(d?.status==='completed')content=`<section class="tr-panel tr-personal-complete"><div class="tr-kicker">REGISTRATION CONFIRMED</div><h3>Transfer completed</h3><p>${esc(d.player)} joined ${esc(clubVisual(d.buyer_id,d.buyer).display_name)}.</p><p>${money(d.fixed_gbp)} paid upfront · ${money(d.outstanding_installments_gbp||0)} in outstanding installments.</p>${d.installment_schedule?.length?`<div class="tr-completion-schedule">${d.installment_schedule.map(r=>`<div><span>${esc(r.due_on)}</span><strong>${money(r.amount_gbp)}</strong><span>${r.paid?'Paid':'Scheduled'}</span></div>`).join('')}</div>`:''}<p>Performance bonuses and future-sale clauses remain recorded obligations.</p></section>`;
    else if(previous)content=`<section class="tr-panel"><h3>Existing discussion</h3><p>Continue the active negotiation for this player.</p><button type="button" class="tr-btn tr-btn-primary" data-tr-deal="${esc(previous.id)}">Open negotiation →</button></section>`;
    else if(editable)content=compose(d);
    else content=`<section class="tr-panel tr-closed"><div class="tr-kicker">${esc(statuses[d?.status]||'DISCUSSION')}</div><h3>${esc(d?.status==='rejected'?'Negotiations ended':statuses[d?.status]||'Awaiting response')}</h3><p>${esc(d?.reason||'')}</p><p>No further offer can be sent in this discussion. The history remains available.</p><button type="button" class="tr-btn" data-tr-back>Back to Scouting</button></section>`;
    return `<div class="tr-immersive tr-fix02"><header class="tr-immersive-header"><div class="tr-page-title"><button type="button" class="tr-back" data-tr-back>← Back to ${esc(window.FMNavigation?.previousLabel?.()||'Scouting')}</button><h1>Negotiation</h1></div><span class="tr-immersive-tag">TS-FIX-02 · TRANSFER NEGOTIATION</span></header>
      <div class="tr-deal-mode tr-inline-mode" role="group" aria-label="Choose offer structure"><span>OFFER STRUCTURE</span><button type="button" class="tr-btn ${dealMode==='transfer'?'tr-btn-primary':''}" aria-pressed="${dealMode==='transfer'}" data-tr-switch-transfer="${esc(d?.player_id||actual.id||'')}">Permanent transfer</button><button type="button" class="tr-btn ${dealMode==='loan'?'tr-btn-primary':''}" aria-pressed="${dealMode==='loan'}" data-tr-switch-loan="${esc(d?.player_id||actual.id||'')}" data-tr-owner="${esc(d?.seller_id||actual.club_id||'')}">Loan</button><small>One discussion · flexible terms</small></div>
      <section class="tr-neg-hero"><div class="tr-hero-player" data-fm-club-theme="${esc(actual.club_id)}" data-fm-club-name="${esc(actual.club)}">${face}<div class="tr-player-identity"><h2>${esc(actual.name||d.player)}</h2><p>${esc(actual.age??'??')} years old · ${esc(actual.position||'')} · ${nation}</p><div class="tr-rating-facts"><div><small>OVR</small><strong title="General overall, not match-adjusted rating">${actual.ovr===null||actual.ovr===undefined?'??':Number(actual.ovr).toFixed(1)}</strong></div><div><small>Market value</small><strong title="${actual.value_gbp==null?'Unknown':money(actual.value_gbp)}">${actual.value_gbp==null?'??':brief(actual.value_gbp)}</strong></div><span class="tr-tag tr-knowledge-tag">${esc(knowledge)}</span></div></div></div>
      <div class="tr-hero-club" data-fm-club-theme="${esc(otherId)}" data-fm-club-name="${esc(otherName)}">${transferCrest(otherId,otherName,true)}<div><small class="tr-kicker">${dealMode==='loan'?'OTHER CLUB':d?.direction==='incoming'?'BUYING CLUB':'SELLING CLUB'}</small><h3>${esc(other.display_name)}</h3><p>${esc(d?.direction==='incoming'?'Your negotiating counterpart':actual.league||'')}</p><button class="tr-btn" type="button" data-tr-club="${esc(otherId)}">View Club →</button></div></div>
      <div class="tr-hero-club tr-own-club">${transferCrest(own,model.club,true)}<div><small class="tr-kicker">YOUR CLUB</small><h3>${esc(manager.display_name)}</h3><p>${esc(model.club_league||'')}</p></div></div>
      <div class="tr-hero-budget"><small>Available transfer budget</small><strong>${brief(d?.available_upfront_gbp??model.available_transfer_budget_gbp)}</strong><span>Upfront payment budget</span><button type="button" class="tr-btn" data-tr-finances>View Finances →</button></div></section>
      <div id="tr-feedback" role="status" aria-live="polite" hidden></div><div id="tr-confirm" hidden></div>
      ${dealMode==='loan'?embeddedLoanView():`<div class="tr-neg-layout"><div class="tr-neg-main">${content}</div><aside class="tr-neg-sidebar">${d?.status==='agreed'&&d.direction==='outgoing'&&window.FMContractNegotiations?
        window.FMContractNegotiations.panel({quote:d.personal_quote,talk:{mode:'transfer',dealId:d.id,
        patience:d.personal_patience??100,status:d.personal_status,counter:d.personal_terms,
        history:d.personal_history||[],reason:d.personal_status==='counter'?d.reason:''},
        clubId:model.club_id,clubName:model.club}):discussion(d)}</aside></div>`}</div>`;
  }

  function draw(){
    if(!host||!model)return;
    if(view==='negotiation'&&deal()?.may_answer)countering=true;
    host.innerHTML=view==='negotiation'?negotiationView():view==='loans'?`<div class="tr-immersive tr-fix02"><header class="tr-immersive-header"><div class="tr-page-title"><button class="tr-back" type="button" data-tr-back>← Back to Transfers</button><h1>Choose a player for a loan</h1></div></header>${loanHub()}</div>`:searchView();
    if(view==='negotiation'){
      const sidebar=document.querySelector('.sidebar');
      if(sidebar){let brand=sidebar.querySelector('.tr-sidebar-club');if(!brand){brand=document.createElement('div');brand.className='tr-sidebar-club';sidebar.prepend(brand);}
        const identity=clubVisual(model.club_id,model.club);brand.innerHTML=transferCrest(model.club_id,model.club,true)+`<strong>${esc(identity.display_name)}</strong>`;
      }
    }
    updatePayments();
    window.FMLoanNegotiations?.sync?.(host);
    for(const type of ['sell','buy']){const section=host.querySelector(`#tr-${type}-fields`);if(section)section.querySelectorAll('input,select').forEach(f=>f.disabled=section.hidden);}
    if(lastError)showFeedback(lastError);
    window.FMClubIdentity?.paintWithin?.(host);
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
      bonuses.push({kind,threshold:Number(row.querySelector('[data-tr-bonus-threshold]').value),amount_gbp:payments().amount(row.querySelector('[data-tr-bonus-amount]').value)});
    }
    const fixed=payments().amount(form.elements.namedItem('fixed_gbp').value);
    const sell=host.querySelector('#tr-sell-fields');
    const buy=host.querySelector('#tr-buy-fields');
    const sellActive=sell&&!sell.hidden,buyActive=buy&&!buy.hidden;
    const buybackPrice=buyActive?payments().amount(form.elements.namedItem('buyback_gbp').value):null;
    const buybackDate=buyActive?form.elements.namedItem('buyback_until').value:null;
    if(buyActive&&(!buybackDate||!buybackPrice))throw Error('Set both buyback price and expiry, or remove the clause');
    const useInstallments=form.querySelector('#tr-installments-enabled')?.checked;
    const installmentTotal=useInstallments?payments().amount(form.elements.namedItem('installments_gbp').value):0;
    const count=useInstallments?[2,4,6][Number(form.elements.namedItem('installment_count').value)]:0;
    const interval=useInstallments?[6,12,18][Number(form.elements.namedItem('installment_interval_months').value)]:0;
    if(useInstallments&&installmentTotal<count)throw Error('Enter a positive amount for each installment, or switch installments off.');
    const terms={fixed_gbp:fixed,installments_gbp:installmentTotal,installment_count:count,installment_interval_months:interval,bonuses,sell_on_type:sellActive?form.elements.namedItem('sell_on_type').value:'none',
      sell_on_percent:sellActive?Number(form.elements.namedItem('sell_on_percent').value):0,
      buyback_gbp:buybackPrice,buyback_until:buybackDate||null};
    if(!Number.isSafeInteger(fixed)||fixed<0||bonuses.some(b=>!Number.isSafeInteger(b.amount_gbp)||!Number.isSafeInteger(b.threshold)))throw Error('Use valid integer offer values');
    if(terms.fixed_gbp>(deal()?.available_upfront_gbp??model.available_transfer_budget_gbp) && (!deal()&&player()?.club_id!==model.club_id||deal()?.direction==='outgoing'))throw Error('The upfront amount exceeds your available transfer budget');
    if(terms.installments_gbp>(deal()?.available_installment_credit_gbp??model.installment_finance?.available_credit_gbp??0) && (!deal()&&player()?.club_id!==model.club_id||deal()?.direction==='outgoing'))throw Error('Installments exceed board credit. Check Finances for the allowance and existing commitments.');
    return terms;
  }
  function showFeedback(message,error=true){
    lastError=error?String(message):'';
    let box=host?.querySelector('#tr-feedback');
    if(!box&&host){box=document.createElement('div');box.id='tr-feedback';host.prepend(box);}
    if(box){box.hidden=false;box.className='tr-feedback '+(error?'is-error':'');box.setAttribute('role',error?'alert':'status');box.textContent=message;}
  }
  function askLoanConfirmation(message, title='Confirm loan action'){
    const box=host.querySelector('#tr-loan-confirm');
    if(!box)return Promise.resolve(false);
    box.hidden=false;box.className='tr-inline-confirm';
    box.setAttribute('role','region');box.setAttribute('aria-label',title);
    box.innerHTML=`<strong>${esc(title)}</strong><p>${esc(message)}</p><button type="button" class="tr-btn tr-btn-primary" data-ln-confirm-yes>Confirm</button><button type="button" class="tr-btn" data-ln-confirm-no>Cancel</button>`;
    box.scrollIntoView({block:'nearest'});
    return new Promise(resolve=>{
      const finish=value=>{box.hidden=true;box.replaceChildren();resolve(value);};
      box.querySelector('[data-ln-confirm-yes]').addEventListener('click',()=>finish(true),{once:true});
      box.querySelector('[data-ln-confirm-no]').addEventListener('click',()=>finish(false),{once:true});
      box.querySelector('[data-ln-confirm-no]').focus();
    });
  }
  function askConfirmation(message){
    const box=host.querySelector('#tr-confirm');
    if(!box)return Promise.resolve(false);
    box.hidden=false;box.className='tr-inline-confirm';box.setAttribute('role','region');box.setAttribute('aria-label','Confirm transfer completion');
    box.innerHTML=`<strong>Complete this transfer?</strong><p>${esc(message)}</p><button type="button" class="tr-btn tr-btn-primary" data-tr-confirm-yes>Confirm completion</button><button type="button" class="tr-btn" data-tr-confirm-no>Keep negotiating</button>`;
    box.scrollIntoView({block:'nearest'});
    return new Promise(resolve=>{
      const finish=value=>{box.hidden=true;box.replaceChildren();resolve(value);};
      box.querySelector('[data-tr-confirm-yes]').addEventListener('click',()=>finish(true),{once:true});
      box.querySelector('[data-tr-confirm-no]').addEventListener('click',()=>finish(false),{once:true});
      box.querySelector('[data-tr-confirm-no]').focus();
    });
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
      const data=await res.json();if(!res.ok)throw Error(data.error||`HTTP ${res.status}`);lastError='';return data;
    }catch(error){lastError=String(error.message||error);showFeedback(lastError);return null;}
    finally{busy=false;host?.setAttribute('aria-busy','false');}
  }
  async function refresh(){
    if(!host)return;
    try{const response=await fetch('/api/transfers',{cache:'no-store'});if(!response.ok)throw Error(`HTTP ${response.status}`);model=await response.json();await window.FMClubIdentity?.ready;draw();}
    catch(error){host.innerHTML=`<section class="tr-panel"><h3>Scouting unavailable</h3><p>${esc(error.message)}</p><button class="tr-btn" type="button" data-tr-refresh>Retry</button></section>`;}
  }
  function mount(element,options={}){
    if(host!==element){host=element;listen();}
    const next=options.view==='negotiation'?'negotiation':options.view==='loans'?'loans':'scouting';
    view=next==='loans'&&(options.playerId||options.talkId)?'negotiation':next;
    dealMode=next==='loans'?'loan':'transfer';chosen=options.playerId||null;dealId=options.dealId||null;countering=false;lastError='';
    loanDrafts.clear();transferDrafts.clear();
    loanSelected=next==='loans'&&chosen?{mode:'loan',id:chosen,owner:options.ownerId||null}:null;requestedLoanTalk=options.talkId||null;
    if(next==='loans')loanMode=chosen?'incoming':requestedLoanTalk?'talks':'active';
    if(options.tab)tab=options.tab;
    if(tab==='loans'||view==='loans'||dealMode==='loan'||(view==='negotiation'&&!dealId))loadLoans();
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
      if(button.dataset.trSwitchLoan!==undefined){
        if(dealMode==='loan')return;
        saveDraft();dealMode='loan';chosen=button.dataset.trSwitchLoan||chosen;
        loanSelected=loanSelected||{mode:'loan',id:chosen,owner:button.dataset.trOwner||player()?.club_id,
          borrower:deal()?.buyer_id};
        await loadLoans();draw();restoreDraft();return;
      }
      if(button.dataset.trSwitchTransfer!==undefined){
        if(dealMode==='transfer')return;
        saveDraft();dealMode='transfer';chosen=button.dataset.trSwitchTransfer||chosen;
        const linked=currentLoanTalk()?.linked_transfer_deal_id;
        if(linked){dealId=linked;await refresh();}
        else {
          // A loan-to-transfer proposal starts as a draft. The existing loan
          // talk remains live until the manager actually submits that draft.
          if(currentLoanTalk()?.status==='counter')dealId=null;
          draw();restoreDraft();
        }
        return;
      }
      if(button.dataset.trClub){nav()?.club(button.dataset.trClub);return;}
      if(button.hasAttribute('data-tr-finances')){nav()?.navigate('Finances');return;}
      if(button.dataset.trStep){const field=host.querySelector(`[name="${button.dataset.trStep}"]`);if(field){try{field.value=payments().format(Math.min(500000000,Math.max(0,payments().amount(field.value)+Number(button.dataset.trDelta))));updatePayments();}catch(error){showFeedback(error.message);}}return;}
      if(button.hasAttribute('data-tr-reset')){
        const form=host.querySelector('#tr-offer-form');if(!form)return;
        form.querySelectorAll('[data-tr-money]').forEach(f=>f.value='0');
        form.querySelector('#tr-installments-enabled').checked=false;
        form.querySelector('[name=installment_count]').value='0';form.querySelector('[name=installment_interval_months]').value='0';
        form.querySelector('#tr-bonuses').replaceChildren();form.querySelector('[data-tr-bonuses-empty]').hidden=false;form.querySelector('[data-tr-add-bonus]').disabled=false;
        for(const type of ['sell','buy'])if(!form.querySelector(`#tr-${type}-fields`).hidden)toggleClause(type);
        updatePayments();showFeedback('Draft cleared. The club patience and negotiation history are unchanged.',false);return;
      }
      if(button.dataset.trTab){tab=button.dataset.trTab;draw();if(tab==='loans')loadLoans();return;}
      if(button.dataset.trLoanTab){loanMode=button.dataset.trLoanTab;loanSelected=null;draw();return;}
      if(button.hasAttribute('data-tr-loan-reload')){await loadLoans();return;}
      if(button.hasAttribute('data-tr-loan-cancel')){if(view==='negotiation'){dealMode='transfer';draw();}else{loanSelected=null;draw();}return;}
      if(button.dataset.trLoanSelect){loanSelected={mode:'loan',id:button.dataset.trLoanSelect,owner:button.dataset.trLoanOwner};chosen=loanSelected.id;dealMode='loan';view='negotiation';draw();return;}
      if(button.dataset.trLoanTalk){const talk=(loansModel?.negotiations||[]).find(t=>t.id===button.dataset.trLoanTalk);if(talk){loanSelected={mode:'loan',id:talk.player_id,owner:talk.parent_id,borrower:talk.borrower_id,talkId:talk.id};chosen=talk.player_id;dealMode=talk.linked_transfer_deal_id?'transfer':'loan';dealId=talk.linked_transfer_deal_id||null;view='negotiation';if(dealId)await refresh();else draw();}return;}
      if(button.hasAttribute('data-ln-add-bonus')){const holder=host.querySelector('#ln-bonuses');if(holder&&holder.children.length<3)holder.insertAdjacentHTML('beforeend',window.FMLoanNegotiations.bonus());return;}
      if(button.hasAttribute('data-ln-remove')){button.closest('[data-ln-bonus]')?.remove();window.FMLoanNegotiations.sync(host);return;}
      if(button.dataset.lnAccept||button.dataset.lnWalk){const action=button.dataset.lnAccept?'loan_accept_counter':'loan_walk';const id=button.dataset.lnAccept||button.dataset.lnWalk;const result=await postLoan({action,talk_id:id});if(result){if(action==='loan_walk')loanSelected=null;await loadLoans();}return;}
      if(button.dataset.trLoanFree){loanSelected={mode:'free',id:button.dataset.trLoanFree};draw();return;}
      if(button.dataset.trLoanRecall){if(await askLoanConfirmation('Return this player to the parent club? This ends the loan early.','Recall player')){if(await postLoan({action:'loan_recall',loan_id:button.dataset.trLoanRecall}))await loadLoans();}return;}
      if(button.dataset.trLoanBuy){if(await askLoanConfirmation('Exercise the previously agreed purchase package? If the market is closed, registration and the upfront payment wait until the next window.','Activate purchase option')){if(await postLoan({action:'loan_buy_option',loan_id:button.dataset.trLoanBuy}))await loadLoans();}return;}
      if(button.dataset.trLoanBuyback){if(await askLoanConfirmation('Activate the agreed buyback at its contract price?','Activate buyback')){if(await postLoan({action:'buyback',deal_id:button.dataset.trLoanBuyback}))await loadLoans();}return;}
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
        if(!await askConfirmation('Let the buying club and player agree a contract? If accepted, registration and the upfront payment complete immediately. Deferred obligations remain scheduled.'))return;
        if(await post({action:'personal_resolve',deal_id:button.dataset.trPersonalResolve}))await refresh();return;
      }
      if(button.hasAttribute('data-tr-personal-accept')){
        if(!await askConfirmation('Accept these player-agent conditions? Registration, upfront fee and signing bonus will be committed; installments remain payable on their dates.'))return;
        if(await post({action:'personal_accept',deal_id:deal()?.id||button.dataset.trPersonalAccept}))await refresh();return;
      }
      if(button.hasAttribute('data-tr-preview')){
        let terms;try{terms=validateTerms();}catch(error){showFeedback(error.message);return;}
        const output=host.querySelector('#tr-preview');
        const guaranteed=terms.fixed_gbp+terms.installments_gbp;
        const conditional=terms.bonuses.reduce((sum,b)=>sum+b.amount_gbp,0);
        if(output)output.innerHTML=`<strong>${money(guaranteed)} guaranteed in total</strong><span>${money(terms.fixed_gbp)} now + ${money(terms.installments_gbp)} deferred.</span><span>Up to ${money(conditional)} in conditional bonuses, plus any future-sale rights.</span><small>This checks your financial commitment. It does not predict the other club's acceptance.</small>`;
        return;
      }
      const action=button.hasAttribute('data-tr-accept')?'accept':button.hasAttribute('data-tr-reject')?'reject':button.hasAttribute('data-tr-withdraw')?'withdraw':null;
      if(action){const id=button.dataset.trAccept||button.dataset.trReject||button.dataset.trWithdraw;
        if(await post({action,deal_id:id}))await refresh();
      }
    });
    host.addEventListener('change',ev=>{
      const field=ev.target;
      if(field.id==='tr-installments-enabled'||field.type==='range'){updatePayments();return;}
      if(field.closest('#tr-loan-form')){window.FMLoanNegotiations?.sync(host);return;}
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
      if(ev.target.matches('[data-loan-money]')){const input=ev.target;const cleaned=input.value.replace(/[^0-9]/g,'');if(cleaned&&Number(cleaned)<=500000000)input.value=window.FMTransferPayments.format(Number(cleaned));window.FMLoanNegotiations.sync(host);return;}
      if(ev.target.closest('#tr-loan-form')){window.FMLoanNegotiations.sync(host);return;}
      if(ev.target.matches('[data-tr-money]')){
        const field=ev.target,raw=field.value,caret=field.selectionStart;
        if(/^[0-9,]+$/.test(raw)){
          const digits=raw.slice(0,caret??raw.length).replace(/,/g,'').length;
          const numeric=raw.replace(/,/g,'');
          if(numeric&&Number(numeric)<=500000000){field.value=payments().format(Number(numeric));let pos=0,seen=0;while(pos<field.value.length&&seen<digits){if(/\d/.test(field.value[pos]))seen++;pos++;}field.setSelectionRange(pos,pos);}
        }
        updatePayments();return;
      }
      if(ev.target.type==='range'){updatePayments();return;}
      if(ev.target.id==='tr-loan-search'){loanQuery=ev.target.value;draw();const input=host.querySelector('#tr-loan-search');input?.focus();input?.setSelectionRange(loanQuery.length,loanQuery.length);return;}
      if(ev.target.id!=='tr-search')return;
      search=ev.target.value;const start=ev.target.selectionStart;draw();
      const input=host.querySelector('#tr-search');input?.focus();if(start!==null)input?.setSelectionRange(start,start);
    });
    host.addEventListener('submit',async ev=>{
      if(ev.target.id==='tr-loan-form'){
        ev.preventDefault();const f=ev.target;if(!f.reportValidity()||!loanSelected)return;
        try{
          const cmd={action:'loan_propose',player_id:loanSelected.id,parent_id:loanSelected.owner,borrower_id:f.elements.namedItem('borrower_id').value,
                     ...(!loanSelected.talkId&&deal()?.may_answer?{source_transfer_deal_id:dealId}:{}),
                     ...(loanSelected.talkId?{talk_id:loanSelected.talkId}:{}),terms:window.FMLoanNegotiations.read(f)};
          const reply=await postLoan(cmd);
          if(reply){
            loanSelected.talkId=reply.talk_id||loanSelected.talkId;loanSelected.borrower=cmd.borrower_id;
            if(cmd.source_transfer_deal_id)dealId=null;
            if(reply.status==='alternate_transfer'&&reply.transfer_deal_id){
              // The selling club changed the offer type. Stay on this SAME page.
              dealMode='transfer';dealId=reply.transfer_deal_id;
              await refresh();await loadLoans();
            }else await loadLoans();
          }
        }catch(error){const notice=host.querySelector('#ln-feedback');if(notice)notice.textContent=error.message;}
        return;
      }
      if(ev.target.id==='tr-free-form'){
        ev.preventDefault();const f=ev.target;if(!f.reportValidity()||!loanSelected)return;
        const cmd={action:'sign_free_agent',player_id:loanSelected.id,weekly_wage_gbp:Number(f.elements.namedItem('weekly_wage_gbp').value),years:Number(f.elements.namedItem('years').value),role:f.elements.namedItem('role').value};
        if(await askLoanConfirmation('Offer this free agent a professional contract under the displayed terms?','Offer contract')){if(await postLoan(cmd)){loanSelected=null;await loadLoans();}}return;
      }
      if(ev.target.id==='tr-personal-form'){
        ev.preventDefault();const form=ev.target,d=deal();if(!d||!form.reportValidity())return;
        let terms;try{terms=window.FMContractNegotiations.readForm(form);}catch(error){showFeedback(error.message);return;}
        if(!await askConfirmation(`Offer ${money(terms.weekly_wage_gbp)}/week, ${terms.years} years and ${money(terms.signing_bonus_gbp)} signing bonus? If the player accepts, the transfer completes immediately.`))return;
        if(await post({action:'personal_offer',deal_id:d.id,terms}))await refresh();return;
      }
      if(ev.target.id!=='tr-offer-form')return;ev.preventDefault();
      let terms;try{terms=validateTerms();}catch(error){showFeedback(error.message);return;}
      const p=player(),d=deal();
      const command=dealMode==='transfer'&&!d&&currentLoanTalk()?.status==='counter'?{action:'transfer_from_loan',talk_id:currentLoanTalk().id,terms}:
        countering&&d?{action:'counter',deal_id:d.id,terms}:
        p?.club_id===model.club_id?
        {action:'offer_sale',player_id:p.id,buyer_id:host.querySelector('#tr-offer-form [name="buyer_id"]')?.value,terms}:
        p?{action:'submit',seller_id:p.club_id,player_id:p.id,terms}:null;
      if(!command)return;
      const result=await post(command);if(!result)return;
      countering=false;
      if(result.status==='alternate_loan'&&result.loan_talk_id){
        dealId=result.deal_id||dealId;chosen=p.id;dealMode='loan';
        loanSelected={mode:'loan',id:p.id,owner:p.club_id,borrower:model.club_id,
                      talkId:result.loan_talk_id};
        await loadLoans();await refresh();
      }else{
        if(result.deal_id)dealId=result.deal_id;
        await refresh();
      }
    });
  }
  window.FMTransfers=Object.freeze({mount,refresh});
})();
