/* TS-FIX-06 — Shared Transfers vocabulary, dedicated structured loan bargaining. */
(() => {
'use strict';
const h=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const fmt=n=>'£'+Number(n||0).toLocaleString('en-GB');
const amount=v=>window.FMTransferPayments.amount(v);
const badge=(id,name)=>{
  const identity=window.FMClubIdentity?.resolve?.(id,name)||{crest:null,display_name:name||id};
  const icon=identity.crest;
  const url=icon&&(window.FMEntityAssets?.url?.(icon)||'/portable/'+icon);
  return url?`<img class="tr-small-club-image" src="${h(url)}" alt="${h(name)} crest" data-fm-asset="optional">`:
    `<span class="tr-small-club-image tr-club-placeholder" aria-label="${h(name)} club crest unavailable">${h((name||'?').split(/\s+/).slice(0,2).map(p=>p[0]).join(''))}</span>`;
};
const dateForBuyback=(iso)=>{const original=iso||'2026-07-01';return window.FMTransferPayments.plusMonths(original,36);};
const number=(label,value,name,min=0,max=500000000)=>`<label>${label}<div class="tr-money"><span aria-hidden="true">£</span><input type="text" name="${name}" data-loan-money inputmode="numeric" value="${h(window.FMTransferPayments.format(value||0))}" aria-label="${h(label)}" /></div></label>`;
function bonus(kind='appearances',threshold=20,value=10000){
 const kinds=[['appearances','Appearances'],['goals','Goals'],['assists','Assists'],['promotion','Promotion']];
 return `<div class="ln-bonus-row" data-ln-bonus><select data-ln-kind aria-label="Bonus trigger">${kinds.map(([id,label])=>`<option value="${id}" ${kind===id?'selected':''}>${label}</option>`).join('')}</select><input data-ln-threshold aria-label="Trigger" type="number" min="1" max="100" value="${h(threshold)}"><div class="tr-money"><span>£</span><input data-loan-money data-ln-amount inputmode="numeric" aria-label="Bonus amount" value="${h(window.FMTransferPayments.format(value||0))}"></div><button type="button" class="tr-btn" data-ln-remove>×</button></div>`;
}
function render(args){
 const {player,managerId,managerName,parentId,parentName,borrowerId,borrowerName,talk,day,destinations=[]}=args;
 const t=talk?.terms||{};const purchase=t.purchase||{};const option=!!t.purchase;
 const isOut=parentId===managerId;
 const opponentId=isOut?borrowerId:parentId, opponentName=isOut?borrowerName:parentName;
 const patience=talk?.patience??100;
 const editable=!talk||talk.status==='counter';
 const history=talk?.history||[];
 const borrowerOptions=isOut?destinations.map(d=>`<option value="${h(d.id)}" ${d.id===borrowerId?'selected':''}>${h(d.name)}</option>`).join(''):`<option value="${h(managerId)}">${h(managerName)}</option>`;
 const portrait=window.FMPortraits?.portrait?.(player,'tr-player-face')||`<div class="ln-avatar">${h((player.name||'?').slice(0,1))}</div>`;
 const flag=window.FMPortraits?.nation?.(player.nationality,'tr-player-nation')||h(player.nationality||'');
 const canAccept=talk?.status==='counter'&&history.at(-1)?.by_club_id!==managerId;
 return `<section class="ln-negotiation">
    <header class="ln-hero"><div class="ln-player" data-fm-club-theme="${h(parentId)}" data-fm-club-name="${h(parentName)}">${portrait}<div><small class="tr-kicker">LOAN NEGOTIATION · ${h(talk?.status||'OPENING TALKS')}</small><h2>${h(player.name)}</h2><p>${h(player.position)} · ${h(player.age)} years · ${flag}</p><p>OVR ${player.ovr==null?'??':Number(player.ovr).toFixed(1)} · ${isOut?'Your player':'Outside scouting knowledge may be incomplete'}</p></div></div>
    <div class="ln-identity" data-fm-club-theme="${h(opponentId)}">${badge(opponentId,opponentName)}<div><small>OTHER CLUB</small><strong>${h(opponentName)}</strong><span>${isOut?'Borrower':'Parent club'}</span></div></div>
    <div class="ln-identity">${badge(managerId,managerName)}<div><small>YOUR CLUB</small><strong>${h(managerName)}</strong><span>${isOut?'Lender':'Borrower'}</span></div></div></header>
    <div class="ln-columns"><form class="tr-panel ln-form" id="tr-loan-form" data-ln-talk="${h(talk?.id||'')}">
    <div class="tr-kicker">YOUR PROPOSAL</div><h3>Build your loan offer</h3><p>Both clubs review the full package. All terms can be countered.</p>
    ${isOut?`<label class="ln-full">Borrowing club<select name="borrower_id" ${talk?'disabled':''}>${borrowerOptions}</select></label>`:`<input type="hidden" name="borrower_id" value="${h(managerId)}">`}
    <div class="ln-fields"><label>Loan duration<select name="months" ${editable?'':'disabled'}>${[[6,'6 months'],[12,'1 year'],[24,'2 years']].map(([v,label])=>`<option value="${v}" ${v===(t.months||12)?'selected':''}>${label}</option>`).join('')}</select></label>
    <label>Promised playing time<select name="playing_time" ${editable?'':'disabled'}>${[['starter','Regular starter'],['rotation','Rotation'],['backup','Backup']].map(([id,label])=>`<option value="${id}" ${id===(t.playing_time||'rotation')?'selected':''}>${label}</option>`).join('')}</select></label></div>
    <label class="ln-slider">Borrower pays <strong data-ln-share>${t.borrower_wage_percent??50}%</strong> of weekly wages<input name="borrower_wage_percent" type="range" min="0" max="100" step="5" value="${t.borrower_wage_percent??50}" ${editable?'':'disabled'}></label>
    <label class="ln-check"><input type="checkbox" name="recall_allowed" ${t.recall_allowed?'checked':''} ${editable?'':'disabled'}> Parent club can recall after 30 days</label>
    <div class="ln-section"><label class="ln-check"><input type="checkbox" id="ln-option" ${option?'checked':''} ${editable?'':'disabled'}> Include an option to buy</label><p>The following purchase package is binding only if the option is exercised. The fee, installments, bonuses and clauses match permanent transfers.</p>
    <div id="ln-purchase" ${option?'':'hidden'}>
      ${number('Upfront purchase price',purchase.fixed_gbp||0,'fixed_gbp')}
      <label class="ln-check"><input id="ln-install-toggle" type="checkbox" ${purchase.installments_gbp?'checked':''} ${editable?'':'disabled'}> Additional guaranteed installments</label>
      <div id="ln-install-fields" ${purchase.installments_gbp?'':'hidden'}>
        ${number('Total deferred purchase amount',purchase.installments_gbp||0,'installments_gbp')}
        <div class="ln-fields ln-sliders"><label>Number of installments<input type="range" name="installment_count" min="0" max="2" step="1" value="${[2,4,6].indexOf(purchase.installment_count||2)}" aria-label="Installment count"><span class="ln-marks"><span>2</span><span>4</span><span>6</span></span></label><label>Payment frequency<input type="range" name="installment_interval_months" min="0" max="2" step="1" value="${[6,12,18].indexOf(purchase.installment_interval_months||6)}" aria-label="Months between payments"><span class="ln-marks"><span>6 months</span><span>12 months</span><span>18 months</span></span></label></div>
      </div>
      <p class="ln-payment-summary" id="ln-finance-summary">Purchase terms are due only after activation.</p>
      <div class="ln-section"><div class="ln-toolbar"><strong>Performance bonuses</strong><button type="button" class="tr-btn" data-ln-add-bonus ${editable?'':'disabled'}>+ Add bonus</button></div><div id="ln-bonuses">${(purchase.bonuses||[]).map(b=>bonus(b.kind,b.threshold,b.amount_gbp)).join('')}</div></div>
      <div class="ln-fields"><label>Future sale percentage<select name="sell_on_type"><option value="none" ${!purchase.sell_on_type||purchase.sell_on_type==='none'?'selected':''}>None</option><option value="gross" ${purchase.sell_on_type==='gross'?'selected':''}>Gross fee</option><option value="profit" ${purchase.sell_on_type==='profit'?'selected':''}>Profit only</option></select></label><label>Sell-on share (%)<input type="number" name="sell_on_percent" min="0" max="35" step="1" value="${purchase.sell_on_percent||0}"></label></div>
      <label class="ln-check"><input type="checkbox" id="ln-buyback" ${purchase.buyback_gbp?'checked':''} ${editable?'':'disabled'}> Include seller buyback right</label>
      <div id="ln-buyback-fields" ${purchase.buyback_gbp?'':'hidden'}>${number('Buyback fee',purchase.buyback_gbp||0,'buyback_gbp')}<label>Buyback expiry<input type="date" name="buyback_until" value="${h(purchase.buyback_until||dateForBuyback(day))}"></label></div>
    </div></div>
    <div class="ln-actions">${editable?`<button class="tr-btn tr-btn-primary" type="submit">${talk?'Send revised loan offer':'Submit loan proposal'} →</button>`:''}${canAccept?`<button class="tr-btn" type="button" data-ln-accept="${h(talk.id)}">Accept club counteroffer</button>`:''}${talk&&['counter','pending_window'].includes(talk.status)?`<button class="tr-btn" type="button" data-ln-walk="${h(talk.id)}">Walk away</button>`:''}<button type="button" class="tr-btn" data-tr-loan-cancel>Back to loans</button></div>
    <div id="ln-feedback" aria-live="polite" role="status"></div></form>
    <aside class="ln-right"><section class="tr-panel"><div class="tr-kicker">NEGOTIATION STATUS</div><div class="ln-toolbar"><h3>${h((talk?.status||'Open').replaceAll('_',' '))}</h3><strong>${patience<=25?'Critical':patience<=60?'Tense':'Open'}</strong></div><div class="ln-tolerance" role="meter" aria-label="Seller/borrower patience" aria-valuenow="${patience}" aria-valuemin="0" aria-valuemax="100"><span style="width:${patience}%"></span></div><small>Patience, not probability of accepting your offer</small><p>${h(talk?.reason||'The other club is willing to discuss a loan package.')}</p>${talk?.status==='pending_window'?`<p><strong>Agreement reached; waiting for the next registration window.</strong> No player or wage payments move yet.</p>`:''}</section>
    <section class="tr-panel"><div class="tr-kicker">CURRENT COUNTERPART TERMS</div>${talk?`<strong>${h(opponentName)}</strong><p>${h(t.months)} months · ${t.borrower_wage_percent}% wages paid by borrower · ${h(t.playing_time)} minutes role</p><p>Recall: ${t.recall_allowed?'Included':'Not included'} · Purchase option: ${t.purchase?fmt(t.purchase.fixed_gbp)+' upfront + '+fmt(t.purchase.installments_gbp)+' deferred':'None'}</p>`:'<p>Submit your own opening terms to receive a response. No hidden minimum price is displayed.</p>'}</section>
    <section class="tr-panel"><div class="tr-kicker">CONVERSATION HISTORY</div><div class="ln-timeline">${history.length?history.map(r=>`<article class="ln-message">${badge(r.by_club_id,r.club)}<div><div class="ln-toolbar"><strong>${h(r.club)}</strong><small>${h(r.date)}</small></div><p>${h(r.note)}</p><small>${r.terms.months} months · ${r.terms.borrower_wage_percent}% wages · ${h(r.terms.playing_time)} · purchase ${r.terms.purchase?fmt(r.terms.purchase.fixed_gbp)+' upfront':'none'}</small></div></article>`).join(''):'<p>No messages yet. You decide the first proposal.</p>'}</div></section></aside></div></section>`;
}
function sync(host){
 const f=host.querySelector('#tr-loan-form');if(!f)return;
 const $=id=>f.querySelector(id);
 if($('#ln-purchase'))$('#ln-purchase').hidden=!$('#ln-option').checked;
 if($('#ln-install-fields'))$('#ln-install-fields').hidden=!$('#ln-install-toggle').checked;
 if($('#ln-buyback-fields'))$('#ln-buyback-fields').hidden=!$('#ln-buyback').checked;
 const share=f.elements.namedItem('borrower_wage_percent');if(share){const out=f.querySelector('[data-ln-share]');if(out)out.textContent=share.value+'%';}
 const summary=$('#ln-finance-summary');if(summary){try{
 const fixed=amount(f.elements.namedItem('fixed_gbp').value);
 const deferred=$('#ln-install-toggle').checked?amount(f.elements.namedItem('installments_gbp').value):0;
 const count=[2,4,6][Number(f.elements.namedItem('installment_count').value)],months=[6,12,18][Number(f.elements.namedItem('installment_interval_months').value)];
 f.elements.namedItem('installment_count').setAttribute('aria-valuetext',count+' payments');
 f.elements.namedItem('installment_interval_months').setAttribute('aria-valuetext','Every '+months+' months');
 summary.textContent=fmt(fixed)+' on option exercise + '+fmt(deferred)+' deferred. '+(deferred?count+' payments every '+months+' months (last after '+(count*months)+' months).':'No installments.');
 }catch{summary.textContent='Enter valid amounts to calculate the purchase payment schedule.';}}
}
function read(form){
 const f=form.elements; const terms={months:Number(f.namedItem('months').value),borrower_wage_percent:Number(f.namedItem('borrower_wage_percent').value),playing_time:f.namedItem('playing_time').value,recall_allowed:f.namedItem('recall_allowed').checked,purchase:null};
 if(form.querySelector('#ln-option').checked){
   const deferred=form.querySelector('#ln-install-toggle').checked?amount(f.namedItem('installments_gbp').value):0;
   const bonuses=[];
   for(const row of form.querySelectorAll('[data-ln-bonus]'))bonuses.push({kind:row.querySelector('[data-ln-kind]').value,threshold:Number(row.querySelector('[data-ln-threshold]').value),amount_gbp:amount(row.querySelector('[data-ln-amount]').value)});
   const sell=f.namedItem('sell_on_type').value;
   terms.purchase={fixed_gbp:amount(f.namedItem('fixed_gbp').value),installments_gbp:deferred,installment_count:deferred?[2,4,6][Number(f.namedItem('installment_count').value)]:0,installment_interval_months:deferred?[6,12,18][Number(f.namedItem('installment_interval_months').value)]:0,
     bonuses,sell_on_type:sell,sell_on_percent:sell==='none'?0:Number(f.namedItem('sell_on_percent').value),
     buyback_gbp:form.querySelector('#ln-buyback').checked?amount(f.namedItem('buyback_gbp').value):null,buyback_until:form.querySelector('#ln-buyback').checked?f.namedItem('buyback_until').value:null};
   if(terms.purchase.fixed_gbp+terms.purchase.installments_gbp<5000)throw Error('Purchase options need at least £5,000 guaranteed.');
 }
 return terms;
}
window.FMLoanNegotiations=Object.freeze({render,sync,read,bonus});
})();
