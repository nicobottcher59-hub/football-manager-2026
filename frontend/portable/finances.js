'use strict';
/* TS-24.2: live Python-backed club budget and professional agreements. */
(() => {
  let host=null,state=null,loading=false;
  let query='',expiringOnly=false;
  const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const gbp=v=>`${Number(v)<0?'-':''}£${Math.abs(Number(v)||0).toLocaleString('en-GB',{maximumFractionDigits:0})}`;
  const compact=n=>{const v=Number(n)||0;return Math.abs(v)>=1e6?`${v<0?'-':''}£${(Math.abs(v)/1e6).toFixed(1).replace(/\.0$/,'')}M`:
                           Math.abs(v)>=1e3?`${v<0?'-':''}£${(Math.abs(v)/1e3).toFixed(1).replace(/\.0$/,'')}K`:gbp(v);};
  const shortDate=s=>{if(!s)return '—';const [y,m,d]=s.split('-');return `${d}/${m}/${y}`;};
  const tile=(label,value,note,accent='')=>`<div class="fe-stat ${accent}"><span>${esc(label)}</span><strong>${esc(value)}</strong><small>${esc(note)}</small></div>`;
  function draw(){
    if(!host||!state)return;
    const spent=state.weekly_payroll_gbp,budget=state.wage_budget_weekly_gbp;
    const pct=Math.max(0,Math.min(100,100*spent/Math.max(1,budget)));
    const months=state.history||[];
    const filtered=(state.contracts||[]).filter(p=>(!expiringOnly||(new Date(p.expires_on+'T00:00:00')-new Date(state.date+'T00:00:00'))/(24*3600*1000) <= 365)
      && `${p.name} ${p.position}`.toLowerCase().includes(query.toLowerCase()));
    host.innerHTML=`<section class="fe-heading"><div><span class="fe-eyebrow">CLUB OPERATIONS · TS-24.2</span><h2>Finances & contracts</h2><p>${esc(state.club)} · ${esc(state.date)} · persistent Python economy</p></div><span class="fe-tier">English tier ${esc(state.tier)}</span></section>
    <section class="fe-stats" aria-label="Financial summary">
      ${tile('Available transfer funds',compact(state.transfer_available_gbp??state.transfer_budget_gbp),'Agreed club terms reserve guaranteed fees')}
      ${tile('Wage budget / week',compact(budget),'Board-approved ceiling')}
      ${tile('Committed wages / week',compact(spent),'First team + youth agreements (staff separate)')}
      ${tile('Bank balance',compact(state.cash_gbp),'Actual operating cash',state.cash_gbp<0?'fe-warning':'fe-positive')}
    </section>
    <div class="fe-overview">
      <section class="fe-panel"><div class="fe-section-head"><div><h3>Wage budget</h3><p>Committed weekly wages compared with the board limit</p></div><span class="fe-pill">${Math.round(pct)}% used</span></div>
        <div class="fe-meter" role="progressbar" aria-valuemin="0" aria-valuemax="100" aria-valuenow="${Math.round(pct)}" aria-label="Wage budget used"><div style="width:${pct}%"></div></div>
        <div class="fe-two"><div><span>Committed</span><strong>${gbp(spent)} / wk</strong></div><div><span>Room remaining</span><strong class="${state.wage_headroom_weekly_gbp<0?'fe-text-warn':'fe-text-good'}">${gbp(state.wage_headroom_weekly_gbp)} / wk</strong></div></div>
        <div class="fe-minor">${compact(state.academy_weekly_wages_gbp)} / wk of the total is academy player pay. Staff: ${compact(state.staff_weekly_wages_gbp||0)} / wk outside the player wage budget. Youth scouts use a separate recruitment allocation.</div>
      </section>
      <section class="fe-panel"><div class="fe-section-head"><div><h3>Operating forecast</h3><p>Recurring monthly estimates, not invented match-by-match receipts</p></div><span class="fe-pill">GBP / month</span></div>
        <div class="fe-flow"><span>Estimated club income</span><strong class="fe-text-good">+${compact(state.monthly_income_gbp)}</strong></div>
        <div class="fe-flow"><span>Player + staff wages (approx.)</span><strong>-${compact(state.forecast_monthly_wages_gbp)}</strong></div>
        <div class="fe-flow"><span>Other club operations</span><strong>-${compact(state.monthly_operating_costs_gbp)}</strong></div>
        <div class="fe-flow fe-total"><span>Forecast monthly result</span><strong class="${(state.monthly_income_gbp-state.forecast_monthly_wages_gbp-state.monthly_operating_costs_gbp)>=0?'fe-text-good':'fe-text-warn'}">${compact(state.monthly_income_gbp-state.forecast_monthly_wages_gbp-state.monthly_operating_costs_gbp)}</strong></div>
      </section>
    </div>
    <section class="fe-panel"><div class="fe-section-head"><div><h3>Transfer installments</h3><p>Guaranteed commitments survive future sales and season changes. Dates start at actual registration.</p></div></div>
      <div class="fe-two"><div><span>Outstanding payments</span><strong>${gbp(state.installment_finance?.outstanding_payable_gbp||0)}</strong></div><div><span>Outstanding receipts</span><strong>${gbp(state.installment_finance?.outstanding_receivable_gbp||0)}</strong></div></div>
      <p class="fe-minor">Available deferred credit: ${gbp(state.installment_finance?.available_credit_gbp||0)}. ${esc(state.installment_finance?.credit_policy||'')}</p>
      ${(state.installment_finance?.payments||[]).length?`<div class="fe-table-wrap"><table class="fe-table"><thead><tr><th>Due</th><th>Deal</th><th>Payment</th><th>Direction</th><th>Amount</th><th>Status</th></tr></thead><tbody>${state.installment_finance.payments.slice(-90).map(r=>`<tr><td>${shortDate(r.due_on)}</td><td>${esc(r.deal_id)}</td><td>${r.number}</td><td>${esc(r.direction)}</td><td>${gbp(r.amount_gbp)}</td><td>${r.paid?'Paid':'Scheduled'}</td></tr>`).join('')}</tbody></table></div>`:'<p class="fe-empty">No installment agreements recorded.</p>'}
    </section>
    <section class="fe-panel"><div class="fe-section-head"><div><h3>Professional contracts <span class="fe-muted">(${state.contracts.length})</span></h3><p>Agent-led discussions: salary, signing fees, bonuses, roles and contract duration.</p></div><span class="fe-pill">Manager decisions</span></div>
      <div class="fe-toolbar"><input id="fe-player-search" type="search" value="${esc(query)}" placeholder="Search name or position" aria-label="Search contracts"/><label><input type="checkbox" id="fe-expiring" ${expiringOnly?'checked':''}/> Expiring within 12 months</label></div>
      <div class="fe-table-wrap"><table class="fe-table"><thead><tr><th>Player</th><th>Pos</th><th>OVR</th><th>Signed wage</th><th>Until</th><th>Role</th><th>Contract discussion</th></tr></thead><tbody>${filtered.map(p=>{
        const expected=p.renewal?.wage_range;
        return `<tr><td><strong>${esc(p.name)}</strong><small>${p.age} years old</small></td><td>${esc(p.position)}</td><td><span class="fe-rating">${Number(p.ovr).toFixed(1)}</span></td><td>${gbp(p.weekly_wage_gbp)} / wk</td><td><span class="${p.status==='out_of_contract_retained'?'fe-text-warn':''}">${shortDate(p.expires_on)}</span>${p.status==='out_of_contract_retained'?'<small>Paid interim retention</small>':''}</td><td><span class="fe-role">${esc(p.role)}</span></td><td><button type="button" class="fe-open-negotiation" data-fe-negotiate="${esc(p.player_id)}">Open Negotiation →</button><small>${expected?`Expected ~${gbp(expected.low_gbp)}–${gbp(expected.high_gbp)}/wk`:'View player & agent'}</small></td></tr>`;
      }).join('')}</tbody></table>${filtered.length?'':'<p class="fe-empty">No players match these filters.</p>'}</div>
    </section>
    <section class="fe-panel"><div class="fe-section-head"><div><h3>Monthly club ledger</h3><p>Recorded on the first of each month, with real saved cash movements</p></div><span class="fe-pill">${months.length} entries shown</span></div>
      ${months.length?`<div class="fe-table-wrap"><table class="fe-table fe-ledger"><thead><tr><th>Period</th><th>Income</th><th>Wages</th><th>Operations</th><th>Net</th><th>Closing balance</th></tr></thead><tbody>${months.map(m=>`<tr><td>${esc(m.period)}</td><td class="fe-text-good">${compact(m.income_gbp)}</td><td>${compact(m.wages_gbp)}</td><td>${compact(m.operations_gbp)}</td><td class="${m.net_gbp>=0?'fe-text-good':'fe-text-warn'}">${compact(m.net_gbp)}</td><td>${compact(m.closing_cash_gbp)}</td></tr>`).join('')}</tbody></table></div>`:'<p class="fe-empty">Your first payroll and income statement will be recorded at the next monthly review.</p>'}
    </section>
    <p class="fe-caveat">${esc(state.note)} ${esc(state.contracts_note)} Club offers can be negotiated under Transfers; player movement still awaits personal terms.</p>`;
    host.setAttribute('aria-busy',String(loading));
  }
  async function refresh(){
    if(!host)return;
    try{const response=await fetch('/api/finances',{cache:'no-store'});if(!response.ok)throw Error(`HTTP ${response.status}`);state=await response.json();draw();}
    catch(error){host.innerHTML=`<section class="fe-panel"><h3>Financial data unavailable</h3><p>${esc(error.message)}</p><button type="button" data-fe-refresh="1">Retry</button></section>`;}
  }
  function mount(element){
    if(host!==element){host=element;
      host.addEventListener('click',event=>{if(event.target.closest('[data-fe-refresh]'))refresh();const button=event.target.closest('[data-fe-negotiate]');if(button)window.FMNavigation?.negotiateContract(button.dataset.feNegotiate);});
      host.addEventListener('input',event=>{if(event.target.id==='fe-player-search'){query=event.target.value;const caret=event.target.selectionStart;draw();const input=host.querySelector('#fe-player-search');input?.focus();if(caret!==null)input?.setSelectionRange(caret,caret);}});
      host.addEventListener('change',event=>{if(event.target.id==='fe-expiring'){expiringOnly=event.target.checked;draw();}});
    }
    host.innerHTML='<section class="fe-panel">Loading finances...</section>';
    refresh();
  }
  window.FMFinances=Object.freeze({mount,refresh});
})();
