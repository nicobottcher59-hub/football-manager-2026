'use strict';
/* TS-UI-12: club-ID driven finance dashboard. Python owns all monetary facts. */
(() => {
  let host=null, state=null, serial=0, tab='overview', search='', onlyExpiring=false, sortBy='expiry';
  const safe=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const amount=v=>Number.isFinite(Number(v))?Number(v):0;
  const gbp=v=>`${amount(v)<0?'-':''}£${Math.abs(amount(v)).toLocaleString('en-GB',{maximumFractionDigits:0})}`;
  const compact=v=>{const n=amount(v),abs=Math.abs(n),sign=n<0?'-':'';return abs>=1e9?`${sign}£${(abs/1e9).toFixed(1).replace(/\.0$/,'')}B`:abs>=1e6?`${sign}£${(abs/1e6).toFixed(1).replace(/\.0$/,'')}M`:abs>=1e3?`${sign}£${(abs/1e3).toFixed(1).replace(/\.0$/,'')}K`:gbp(n);};
  const dateLabel=iso=>/^\d{4}-\d{2}-\d{2}$/.test(iso||'')?`${iso.slice(8)}/${iso.slice(5,7)}/${iso.slice(0,4)}`:'—';
  const percent=(value,total)=>Math.max(0,Math.min(100,100*amount(value)/Math.max(1,amount(total))));
  const daysUntil=(iso,from)=>/^\d{4}-\d{2}-\d{2}$/.test(iso||'')&&/^\d{4}-\d{2}-\d{2}$/.test(from||'')?
    Math.round((Date.parse(iso+'T00:00:00Z')-Date.parse(from+'T00:00:00Z'))/86400000):99999;
  const icon=(key)=>{
    const paths={bank:'M3 10h18M4 10V20M10 10V20M14 10V20M20 10V20M2 20h20M12 2l10 6H2z',
      transfer:'M4 7h16m-4-4 4 4-4 4M20 17H4m4-4-4 4 4 4',
      player:'M8 4h8M12 2v4M6 22v-4a6 6 0 0 1 12 0v4M9 12a3 3 0 1 0 6 0 3 3 0 0 0-6 0',
      staff:'M16 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2M8.5 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8M22 21v-2a4 4 0 0 0-3-3.9M16.2 3.1a4 4 0 0 1 0 7.8',
      chart:'M3 3v18h18M7 16l4-4 3 2 6-7M17 7h3v3',
      trophy:'M8 21h8M12 17v4M6 3h12v6a6 6 0 0 1-12 0V3zM6 5H2v3a4 4 0 0 0 4 4m12-7h4v3a4 4 0 0 1-4 4',
      calendar:'M3 5h18v16H3zM8 2v6M16 2v6M3 10h18',
      warning:'M12 3 2 21h20L12 3zM12 9v5M12 18h.01',
      file:'M5 2h9l5 5v15H5zM14 2v5h5M8 12h8M8 16h8',
      arrow:'M5 12h14m-5-5 5 5-5 5',
      history:'M3 12a9 9 0 1 0 3-6.7L3 8M3 3v5h5M12 7v5l3 2'};
    return `<svg viewBox="0 0 24 24" width="19" height="19" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="${paths[key]||paths.chart}"/></svg>`;
  };
  const identity=()=>window.FMClubIdentity?.resolve?.(state.club_id,state.club)||{display_name:state.club};
  function badge(){
    const c=identity(),source=c.crest && (window.FMEntityAssets?.url?.(c.crest)||'/portable/'+c.crest);
    return source?`<img class="fe-crest" src="${safe(source)}" data-fm-asset="optional" alt="${safe(c.display_name||state.club)} crest">`:
      `<span class="fe-crest fe-crest-fallback">${safe((c.short_name||c.display_name||state.club||'FC').split(/\s+/).slice(0,2).map(x=>x[0]).join('').toUpperCase())}</span>`;
  }
  function hero(){
    // Finance artwork is deliberately club-neutral. Identity and palette still
    // resolve from the active club, but club stadium/hero photos never override it.
    const c=identity();
    return `<header class="fe-hero" data-fm-club-theme="${safe(state.club_id)}" data-fm-club-name="${safe(state.club)}">
      <div class="fe-hero-left">${badge()}<div><span class="fe-eyebrow">${safe(c.display_name||state.club)} · CLUB FINANCES</span><h2>Finances &amp; contracts</h2>
        <p>Budgets, contracts and financial commitments in one place.</p></div></div>
      <div class="fe-hero-right"><span>SEASON &amp; FINANCIAL REVIEW</span><strong>${safe(state.season||state.date?.slice(0,4)||'—')}</strong><small>${dateLabel(state.date)}</small></div>
    </header>`;
  }
  const navTabs=[['overview','Overview'],['contracts','Contracts'],['transfers','Transfer Finances'],['history','Financial History']];
  function tabs(){return `<nav class="fe-tabs" aria-label="Finance sections">${navTabs.map(([id,text])=>
    `<button type="button" data-fe-tab="${id}" aria-current="${tab===id?'page':'false'}" class="${tab===id?'is-active':''}">${text}</button>`).join('')}</nav>`;}
  const card=(title,description,content,other='',cls='')=>`<section class="fe-panel ${cls}"><header class="fe-section-head"><div><h3>${title}</h3>${description?`<p>${description}</p>`:''}</div>${other}</header>${content}</section>`;
  function stat(key,label,value,description,chip='',kind=''){
    return `<article class="fe-stat ${kind}"><div class="fe-stat-top"><span class="fe-stat-icon">${icon(key)}</span><span class="fe-stat-label">${safe(label)}</span></div>
      <strong>${safe(value)}</strong><small>${safe(description)}</small>${chip?`<div class="fe-stat-chip">${chip}</div>`:''}</article>`;
  }
  function summary(){
    const wage=state.wage_budget_weekly_gbp,staff=state.staff_budget_weekly_gbp;
    const net=forecastNet();
    return `<section class="fe-stats" aria-label="Financial indicators">
      ${stat('bank','Bank Balance',compact(state.cash_gbp),'Actual operating cash','','fe-cash')}
      ${stat('transfer','Transfer Budget',compact(state.transfer_available_gbp??state.transfer_budget_gbp),'Available for agreed transfers')}
      ${stat('player','Wage Budget',compact(wage)+' /wk',`${compact(state.weekly_payroll_gbp)} committed`,`<span class="fe-mini-track"><i style="width:${percent(state.weekly_payroll_gbp,wage)}%"></i></span>`)}
      ${stat('staff','Staff Budget',compact(staff)+' /wk',`${compact(state.staff_weekly_wages_gbp)} committed`, `<span class="fe-mini-track"><i style="width:${percent(state.staff_weekly_wages_gbp,staff)}%"></i></span>`)}
      ${stat('chart','Monthly Forecast',compact(net),'Estimated recurring result','',net>=0?'fe-cash':'fe-loss')}
    </section>`;
  }
  const forecastNet=()=>amount(state.monthly_income_gbp)-amount(state.forecast_monthly_wages_gbp)-amount(state.monthly_operating_costs_gbp);
  const button=(text,action,extra='')=>`<button type="button" ${action} class="fe-button ${extra}">${safe(text)} ${icon('arrow')}</button>`;
  function wageMeter(label,spent,budget){
    const left=budget-spent,used=percent(spent,budget);
    return `<div class="fe-wage-block"><div class="fe-wage-header"><strong>${label}</strong><span>${Math.round(100*amount(spent)/Math.max(1,amount(budget)))}% used</span></div>
      <div class="fe-meter" role="progressbar" aria-label="${safe(label)} used" aria-valuemin="0" aria-valuemax="100" aria-valuenow="${Math.round(used)}"><i style="width:${used}%"></i></div>
      <div class="fe-wage-numbers"><div><small>Committed / wk</small><strong>${gbp(spent)}</strong></div><div><small>Room remaining / wk</small><strong class="${left>=0?'fe-good':'fe-bad'}">${gbp(left)}</strong></div><div><small>Board budget / wk</small><strong>${gbp(budget)}</strong></div></div></div>`;
  }
  function topEarners(rows,staffMode=false){
    if(!rows.length)return '<p class="fe-empty">No active contracts recorded.</p>';
    return `<div class="fe-earners"><div class="fe-earners-head"><span>${staffMode?'STAFF MEMBER':'PLAYER'}</span><span>${staffMode?'DEPARTMENT':'ROLE'}</span><span>WAGE / WK</span></div>
      ${rows.slice(0,5).map(x=>`<div class="fe-earner-row"><div>${staffMode?`<span class="fe-mini-avatar">${safe(x.name?.slice(0,1)||'?')}</span>`:portrait(x)}<strong>${safe(x.name)}</strong></div><span>${safe(staffMode?roleName(x.role):x.role)}</span><strong>${gbp(x.weekly_wage_gbp)}</strong></div>`).join('')}</div>`;
  }
  function portrait(p){
    const entry={id:p.player_id,name:p.name,short_name:p.name,position:p.position,club_id:state.club_id};
    return window.FMPortraits?.portrait?.(entry,'fe-mini-avatar')||`<span class="fe-mini-avatar">${safe(p.name?.slice(0,1)||'?')}</span>`;
  }
  const roleName=r=>({'coach':'Coach','fitness':'Fitness Coach','medic':'Medical Staff','scout':'Scout'}[r]||r||'Staff');
  function wageStructure(){
    const rows=[...(state.contracts||[])].sort((a,b)=>amount(b.weekly_wage_gbp)-amount(a.weekly_wage_gbp));
    return card('Wage Structure','First-team and academy contracts',wageMeter('Player wages',state.weekly_payroll_gbp,state.wage_budget_weekly_gbp)+
      '<h4>Highest paid players</h4>'+topEarners(rows),button('View contracts','data-fe-tab="contracts"','fe-outline'),'fe-wage-panel');
  }
  function staffBudget(){
    const rows=state.staff_contracts||[];
    return card('Staff Budget','Independent wage allowance for club employees',
      wageMeter('Staff wages',state.staff_weekly_wages_gbp,state.staff_budget_weekly_gbp)+
      '<h4>Highest paid staff</h4>'+topEarners(rows,true)+
      '<p class="fe-policy-foot">Staff salaries are paid from club cash but do not consume the players’ wage ceiling.</p>',
      button('Manage staff','data-fe-staff','fe-outline'),'fe-staff-panel');
  }
  function forecastTable(){
    const staff=amount(state.staff_weekly_wages_gbp)*52/12;
    const player=amount(state.forecast_monthly_wages_gbp)-staff;
    return `<div class="fe-flow"><span>Estimated monthly income</span><strong class="fe-good">+${compact(state.monthly_income_gbp)}</strong></div>
      <div class="fe-flow"><span>Player wages (est.)</span><strong>-${compact(player)}</strong></div>
      <div class="fe-flow"><span>Staff wages (est.)</span><strong>-${compact(staff)}</strong></div>
      <div class="fe-flow"><span>Other club operations</span><strong>-${compact(state.monthly_operating_costs_gbp)}</strong></div>
      <div class="fe-flow fe-total"><span>Forecast monthly result</span><strong class="${forecastNet()>=0?'fe-good':'fe-bad'}">${compact(forecastNet())}</strong></div>`;
  }
  function barChart(){
    const records=(state.history||[]).slice().reverse();
    if(!records.length)return `<div class="fe-chart-empty">${icon('chart')}<strong>No recorded monthly statements yet</strong>
      <span>Actual income and spending will appear after the first financial review. Current forecast is shown separately.</span></div>`;
    const values=records.map(m=>[amount(m.income_gbp),amount(m.wages_gbp)+amount(m.operations_gbp)]);
    const max=Math.max(1,...values.flat());
    const chartHeight=133,base=168,left=34,width=590,slot=width/Math.max(records.length,1);
    let bars='';
    records.forEach((m,i)=>{
      const [income,outgoing]=values[i],barW=Math.min(15,Math.max(5,slot*.28)),x=left+i*slot+slot*.27;
      const hi=chartHeight*income/max,ho=chartHeight*outgoing/max;
      bars+=`<rect x="${x.toFixed(1)}" y="${(base-hi).toFixed(1)}" width="${barW.toFixed(1)}" height="${hi.toFixed(1)}" rx="2" fill="#20caa5"><title>${safe(m.period)} income: ${gbp(income)}</title></rect>
        <rect x="${(x+barW+3).toFixed(1)}" y="${(base-ho).toFixed(1)}" width="${barW.toFixed(1)}" height="${ho.toFixed(1)}" rx="2" fill="#ea4568"><title>${safe(m.period)} expenses: ${gbp(outgoing)}</title></rect>`;
      if(records.length<=12)bars+=`<text x="${(left+i*slot+slot*.5).toFixed(1)}" y="190" text-anchor="middle" fill="#a1c0d3" font-size="10">${safe(m.period.slice(5,7))}/${safe(m.period.slice(2,4))}</text>`;
    });
    return `<div class="fe-chart-scroll"><svg class="fe-chart" viewBox="0 0 665 214" role="img" aria-label="Recorded club income and expenses by month">
      ${[0,.25,.5,.75,1].map(fr=>`<line x1="34" y1="${base-chartHeight*fr}" x2="635" y2="${base-chartHeight*fr}" stroke="#43617c" stroke-opacity=".39"/><text x="26" y="${base-chartHeight*fr+4}" fill="#8aaec3" text-anchor="end" font-size="10">${fr===0?'0':compact(max*fr)}</text>`).join('')}
      ${bars}<line x1="34" y1="168" x2="635" y2="168" stroke="#5c83a0"/></svg></div>
      <div class="fe-legend"><span><i class="fe-income-dot"></i>Income</span><span><i class="fe-expense-dot"></i>Expenses</span></div>`;
  }
  function incomeCard(){
    const count=(state.history||[]).length;
    return card('Income & Expenses',count?'Recorded monthly cashflow':'Monthly operating forecast · recorded figures appear after review',
      count?barChart():`<div class="fe-prestatement">No accounting months closed yet. Estimates are clearly marked and do not represent booked cashflow.</div>${forecastTable()}`,
      `<span class="fe-pill">${count?count+' month(s) recorded':'Forecast only'}</span>`,'fe-income-panel');
  }
  function priorities(){
    const rows=(state.contracts||[]).filter(x=>x.renewal).map(x=>({...x,remaining:daysUntil(x.expires_on,state.date)}))
      .sort((a,b)=>a.remaining-b.remaining||a.name.localeCompare(b.name));
    if(!rows.length)return '<div class="fe-empty">No contracts currently available for negotiation.</div>';
    return `<div class="fe-priorities">${rows.slice(0,4).map(p=>{
      const urgent=p.remaining<=90,soon=p.remaining<=365;
      const expiring=p.remaining<0?'Expired':urgent?'Contract expiring':soon?'Renewal recommended':'Future review';
      const s=urgent?'fe-critical':soon?'fe-soon':'fe-normal';
      return `<article class="fe-priority ${s}"><div class="fe-priority-profile">${portrait(p)}<div><span class="fe-priority-tag">${expiring}</span>
        <strong>${safe(p.name)}</strong><small>${safe(p.age)} years · ${safe(p.position)} · OVR ${amount(p.ovr).toFixed(1)}</small></div></div>
        <div class="fe-priority-wage">${gbp(p.weekly_wage_gbp)} <small>/ wk</small></div>
        <p>${p.remaining<0?'Agreement expired':`Expires in ${Math.max(0,Math.ceil(p.remaining/30.44))} months`}</p>
        <button type="button" class="fe-contract-action" data-fe-negotiate="${safe(p.player_id)}">Open negotiation →</button></article>`;
    }).join('')}</div>`;
  }
  function priorityCard(){return card('Contract Priorities','Players needing a contract decision, ordered by expiration',priorities(),button('View all','data-fe-tab="contracts"','fe-outline'),'fe-priority-panel');}
  function financeSummary(){const finance=state.installment_finance||{};
    const fees=amount(state.loan_fees_received_gbp)-amount(state.loan_fees_paid_gbp);
    const upcoming=(finance.payments||[]).filter(p=>!p.paid).slice().sort((a,b)=>String(a.due_on).localeCompare(String(b.due_on))).slice(0,5);
    return `<div class="fe-transfer-metrics"><div><span>${icon('calendar')}</span><strong>${compact(finance.outstanding_payable_gbp)}</strong><small>Outstanding payments</small></div>
      <div><span>${icon('bank')}</span><strong>${compact(finance.outstanding_receivable_gbp)}</strong><small>Outstanding receipts</small></div>
      <div><span>${icon('transfer')}</span><strong class="${fees>=0?'fe-good':'fe-bad'}">${compact(fees)}</strong><small>Net loan fees · career</small></div></div>
      <h4>Upcoming payments</h4>${upcoming.length?`<div class="fe-upcoming">${upcoming.map(p=>`<div><span>${dateLabel(p.due_on)}</span><span>${safe(p.deal_id)}</span><strong>${gbp(p.amount_gbp)}</strong></div>`).join('')}</div>`:'<div class="fe-transfer-empty">No outstanding instalments.</div>'}`;
  }
  function transferCard(){return card('Transfer Finances','Committed fees, instalments and loan fees',financeSummary(),button('View all','data-fe-tab="transfers"','fe-outline'),'fe-transfer-panel');}
  function overview(){return `<div class="fe-major-grid">${incomeCard()}${wageStructure()}${staffBudget()}</div><div class="fe-lower-grid">${priorityCard()}${transferCard()}</div>`;}
  function contractTable(){
    const q=search.trim().toLowerCase();let rows=(state.contracts||[]).filter(p=>(!onlyExpiring||daysUntil(p.expires_on,state.date)<=365)&&`${p.name} ${p.position} ${p.role}`.toLowerCase().includes(q));
    rows.sort((a,b)=>sortBy==='wage'?amount(b.weekly_wage_gbp)-amount(a.weekly_wage_gbp):sortBy==='ovr'?amount(b.ovr)-amount(a.ovr):sortBy==='name'?String(a.name).localeCompare(String(b.name)):String(a.expires_on).localeCompare(String(b.expires_on)));
    return `<div class="fe-toolbar"><input type="search" id="fe-player-search" placeholder="Search player or position" value="${safe(search)}" aria-label="Search contracts"/>
      <select data-fe-sort aria-label="Sort contracts"><option value="expiry" ${sortBy==='expiry'?'selected':''}>Expiry first</option><option value="wage" ${sortBy==='wage'?'selected':''}>Highest salary</option><option value="ovr" ${sortBy==='ovr'?'selected':''}>Highest OVR</option><option value="name" ${sortBy==='name'?'selected':''}>Name</option></select>
      <label><input type="checkbox" id="fe-expiring" ${onlyExpiring?'checked':''}/> Expiring within 12 months</label></div>
      <div class="fe-table-wrap"><table class="fe-table"><thead><tr><th>Player</th><th>Position</th><th>OVR</th><th>Wage / week</th><th>Expires</th><th>Role</th><th>Negotiation</th></tr></thead><tbody>
      ${rows.map(p=>`<tr><td><div class="fe-player-cell">${portrait(p)}<div><strong>${safe(p.name)}</strong><small>${safe(p.age)} years old</small></div></div></td><td>${safe(p.position)}</td>
        <td><span class="fe-rating">${amount(p.ovr).toFixed(1)}</span></td><td>${gbp(p.weekly_wage_gbp)}</td><td>${dateLabel(p.expires_on)}${daysUntil(p.expires_on,state.date)<=365?'<span class="fe-status-tag">Expiring</span>':''}</td>
        <td>${safe(p.role)}</td><td><button class="fe-contract-action" type="button" data-fe-negotiate="${safe(p.player_id)}" ${p.renewal?'':'disabled'}>Open negotiation →</button>
        ${p.renewal?.wage_range?`<small class="fe-wage-hint">Expected ${gbp(p.renewal.wage_range.low_gbp)}–${gbp(p.renewal.wage_range.high_gbp)}/wk</small>`:''}</td></tr>`).join('')}
      </tbody></table>${!rows.length?'<div class="fe-empty">No players match your filters.</div>':''}</div>`;
  }
  function staffTable(){
    return `<div class="fe-table-wrap"><table class="fe-table fe-staff-table"><thead><tr><th>Member</th><th>Department</th><th>Quality</th><th>Wage / week</th><th>Until</th></tr></thead><tbody>
      ${(state.staff_contracts||[]).map(p=>`<tr><td><strong>${safe(p.name)}</strong></td><td>${safe(roleName(p.role))}</td><td>${safe(p.quality)}</td><td>${gbp(p.weekly_wage_gbp)}</td><td>${dateLabel(p.expires_on)}</td></tr>`).join('')}</tbody></table></div>`;
  }
  function contracts(){return `${priorityCard()}${card('Professional Contracts',`${state.contracts?.length||0} registered players · all renewals use the existing agent negotiation system`,contractTable())}
    ${card('Staff Contracts',`${state.staff_contracts?.length||0} active appointments · staff salaries consume a separate board limit`,staffTable(),button('Manage staff','data-fe-staff','fe-outline'))}`;}
  function transferFinances(){
    const records=(state.installment_finance?.payments||[]).slice().sort((a,b)=>String(a.due_on).localeCompare(String(b.due_on)));
    return `${transferCard()}${card('Scheduled Transfer Instalments','Actual deferred payments and receipts from confirmed agreements',
      records.length?`<div class="fe-table-wrap"><table class="fe-table"><thead><tr><th>Due date</th><th>Deal</th><th>Payment</th><th>Direction</th><th>Amount</th><th>Status</th></tr></thead><tbody>
      ${records.map(p=>`<tr><td>${dateLabel(p.due_on)}</td><td>${safe(p.deal_id)}</td><td>${safe(p.number)}</td><td>${safe(p.direction)}</td><td>${gbp(p.amount_gbp)}</td><td>${p.paid?'Paid':'Scheduled'}</td></tr>`).join('')}</tbody></table></div>`:'<p class="fe-empty">No instalment agreements recorded.</p>')}
    ${card('Available Deferred Credit','Guaranteed payment obligations remain due even after a season change',`<div class="fe-credit-value">${gbp(state.installment_finance?.available_credit_gbp)}</div><p class="fe-policy-foot">${safe(state.installment_finance?.credit_policy||'')}</p>`)}
    ${card('Loan Fees','Amounts already paid at registration, not purchase options',`<div class="fe-transfer-metrics"><div><strong>${gbp(state.loan_fees_paid_gbp)}</strong><small>Paid · career</small></div><div><strong>${gbp(state.loan_fees_received_gbp)}</strong><small>Received · career</small></div><div><strong>${gbp(amount(state.loan_fees_received_gbp)-amount(state.loan_fees_paid_gbp))}</strong><small>Net · career</small></div></div>`)}
    `;
  }
  function history(){const months=state.history||[];
    return `${card('Recorded Financial History','Only completed accounting months are included, not invented historical values',barChart())}
      ${card('Monthly Ledger','Real saved income, expenses and closing balance',
        months.length?`<div class="fe-table-wrap"><table class="fe-table"><thead><tr><th>Month</th><th>Income</th><th>Wages</th><th>Operations</th><th>Net result</th><th>Closing cash</th></tr></thead><tbody>
        ${months.map(m=>`<tr><td>${safe(m.period)}</td><td class="fe-good">${gbp(m.income_gbp)}</td><td>${gbp(m.wages_gbp)}</td><td>${gbp(m.operations_gbp)}</td><td class="${m.net_gbp>=0?'fe-good':'fe-bad'}">${gbp(m.net_gbp)}</td><td>${gbp(m.closing_cash_gbp)}</td></tr>`).join('')}</tbody></table></div>`:'<p class="fe-empty">The first actual statement will be recorded at the next monthly accounting review.</p>')}
      ${card('Current Operating Forecast','Projection based on the current registered budget and staff wages',forecastTable())}`;
  }
  function render(){
    if(!state||!host)return;
    host.innerHTML=`<div class="fe-root">${hero()}${tabs()}${summary()}
      <main class="fe-content">${tab==='overview'?overview():tab==='contracts'?contracts():tab==='transfers'?transferFinances():history()}</main>
      <p class="fe-caveat">${safe(state.note)} Financial statements reflect actual booked reviews; historical projections are not backfilled.</p></div>`;
    window.FMClubIdentity?.paintWithin?.(host);
  }
  async function refresh(){
    if(!host)return;const request=++serial;
    try{
      const response=await fetch('/api/finances',{cache:'no-store'});
      if(!response.ok)throw Error(`HTTP ${response.status}`);
      const model=await response.json();if(request!==serial)return;
      state=model;
      await window.FMClubIdentity?.ready;
      if(request!==serial)return;
      render();
    }catch(error){if(request!==serial)return;host.innerHTML=`<section class="fe-panel fe-error"><h3>Financial data unavailable</h3><p>${safe(error.message)}</p><button type="button" data-fe-retry>Retry</button></section>`;}
  }
  function handleClick(event){
    const el=event.target.closest('button');if(!el)return;
    if(el.dataset.feTab){tab=el.dataset.feTab;render();return;}
    if(el.hasAttribute('data-fe-retry')){refresh();return;}
    if(el.dataset.feNegotiate){window.FMNavigation?.negotiateContract?.(el.dataset.feNegotiate);return;}
    if(el.hasAttribute('data-fe-staff'))window.FMNavigation?.navigate?.('Staff');
  }
  function handleChange(e){if(e.target.id==='fe-expiring'){onlyExpiring=e.target.checked;render();}if(e.target.hasAttribute('data-fe-sort')){sortBy=e.target.value;render();}}
  function handleInput(e){if(e.target.id!=='fe-player-search')return;search=e.target.value;const at=e.target.selectionStart;render();const input=host?.querySelector('#fe-player-search');input?.focus();if(at!=null)input?.setSelectionRange(at,at);}
  function mount(element){
    if(host!==element){host=element;host.addEventListener('click',handleClick);host.addEventListener('change',handleChange);host.addEventListener('input',handleInput);}
    if(!state){host.innerHTML='<section class="fe-panel fe-loading">Loading finances…</section>';}
    refresh();
  }
  window.FMFinances=Object.freeze({mount,refresh});
})();
