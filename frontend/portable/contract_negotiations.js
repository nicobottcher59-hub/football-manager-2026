'use strict';
/* TS-FIX-03: one player-agent negotiation experience, shared by incoming
 * transfer contracts and renewals launched from Finances. Money is not guessed
 * or prefilled; all valuation and acceptance decisions stay on the server.
 */
(() => {
  let host=null,playerId=null,model=null,pending=false,feedback='';
  const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const currency=n=>`£${Math.max(0,Number(n)||0).toLocaleString('en-GB',{maximumFractionDigits:0})}`;
  const amount=v=>{const n=String(v??'0').replace(/[£,\s]/g,'');if(!/^\d+$/.test(n))throw Error('Enter a whole GBP amount, without decimals');const value=Number(n);if(!Number.isSafeInteger(value))throw Error('Amount exceeds the supported technical limit');return value;};
  const roles=[['star','Star player'],['important','Important player'],['regular','Regular starter'],['rotation','Rotation'],['backup','Backup']];
  const types=[['appearances','Appearances'],['goals','Goals'],['assists','Assists'],['clean_sheets','Clean sheets (GK/defence)'],['promotion','Promotion']];
  const opt=(v,title,current)=>`<option value="${esc(v)}" ${v===current?'selected':''}>${esc(title)}</option>`;
  const choices=(data,pick)=>data.map(([a,b])=>opt(a,b,pick)).join('');
  function badgeLevel(patience){return patience<=25?'Critical':patience<=55?'Tense':patience<=80?'Cautious':'Open';}
  const crest=(clubId,name,cls='cn-crest')=>{
    const identity=window.FMClubIdentity?.resolve?.(clubId,name)||{display_name:name||'Club',crest:null};
    const uri=identity.crest&&(window.FMEntityAssets?.url?.(identity.crest)||'/portable/'+identity.crest);
    return uri?`<img class="${cls}" src="${esc(uri)}" alt="" loading="lazy" data-fm-asset="optional">`:
       `<span class="${cls} cn-crest-placeholder" title="Club insignia not imported">${esc((identity.display_name||'?').split(/\s+/).slice(0,2).map(w=>w[0]).join(''))}</span>`;
  };
  function bonusRow(kind='appearances',threshold=20,sum=0){
    const id=Math.random().toString(36).slice(2,8);
    return `<div class="cn-bonus-row" data-cn-bonus-row><label>Milestone<select name="bonus_kind">${choices(types,kind)}</select></label>
      <label>Trigger<input name="bonus_threshold" type="number" min="1" max="100" step="1" value="${Number(threshold)}"></label>
      <label>Bonus amount (£)<input class="cn-money" name="bonus_amount" inputmode="numeric" type="text" value="${currency(sum)}" aria-label="Performance bonus amount"></label>
      <button type="button" class="tr-btn" data-cn-remove-bonus="${id}" aria-label="Remove bonus">×</button></div>`;
  }
  function form({quote,current,talk,mode='renewal',id='cn-renewal-form'}){
    const state=talk||{},closed=['ended','renewed','completed','declined'].includes(state.status);
    if(closed)return `<section class="tr-panel cn-offer"><span class="tr-kicker">CONTRACT DISCUSSION</span><h3>${state.status==='renewed'||state.status==='completed'?'Agreement completed':'Negotiations closed'}</h3>
      <p>${esc(state.reason||'No further proposals can be made in this discussion.')}</p>${current?`<p>Signed weekly wage: <strong>${currency(current.weekly_wage_gbp)}</strong></p>`:''}</section>`;
    const q=quote||{};
    const range=q.wage_range||q.range;
    return `<section class="tr-panel cn-offer"><span class="tr-kicker">YOUR OFFER · PLAYER CONTRACT</span><h3>Build your contract offer</h3>
      <p>Set your own weekly salary. The player's agent evaluates the whole package.</p>
      <div class="cn-expectation"><span>Indicative wage expectation</span><strong>${range?`${currency(range.low_gbp)} – ${currency(range.high_gbp)} /wk`:'Not available'}</strong><small>Approximate discussion range, not a minimum or acceptance threshold</small></div>
      <form id="${id}" data-cn-form><div class="cn-wage"><label>Weekly salary (£)<div class="cn-money-control"><b>£</b><input name="weekly_wage_gbp" class="cn-money" type="text" inputmode="numeric" required value="0" aria-label="Proposed weekly wage"></div></label>
      <div class="cn-increments"><button class="tr-btn" type="button" data-cn-add="1000" data-cn-field="weekly_wage_gbp">+£1K</button><button class="tr-btn" type="button" data-cn-add="5000" data-cn-field="weekly_wage_gbp">+£5K</button><button class="tr-btn" type="button" data-cn-add="10000" data-cn-field="weekly_wage_gbp">+£10K</button></div></div>
      <div class="cn-terms"><label>Contract duration<select name="years">${Array.from({length:Math.max(1,q.max_years||5)},(_,i)=>opt(i+1,`${i+1} ${i===0?'year':'years'}`,q.years||2)).join('')}</select></label>
        <label>Promised squad role<select name="role">${choices(roles,q.role||current?.role||'regular')}</select></label></div>
      <label class="cn-signing">Signing-on bonus (£)<div class="cn-money-control"><b>£</b><input name="signing_bonus_gbp" class="cn-money" type="text" inputmode="numeric" value="0" required></div></label>
      <section class="cn-bonuses"><div class="cn-section-heading"><div><strong>Performance bonuses <span>(optional)</span></strong><small>Pay once if a recorded milestone is achieved.</small></div><button type="button" class="tr-btn" data-cn-add-bonus>+ Add bonus</button></div>
        <div class="cn-bonus-list" data-cn-bonuses></div><p class="cn-bonus-empty" data-cn-bonus-empty>No performance bonuses selected.</p></section>
      <div class="cn-actions"><button type="button" class="tr-btn" data-cn-preview>Evaluate proposal</button><button class="tr-btn tr-btn-primary" type="submit">Submit offer →</button><button type="button" class="tr-btn" data-cn-reset>Reset terms</button></div>
      <div class="cn-preview" data-cn-preview-output role="status">Only confirmed salary and signing bonus are immediate obligations. Performance bonuses are conditional.</div></form></section>`;
  }
  function panel({quote,talk,clubId,clubName}){
    const data=talk||{},p=Math.max(0,Math.min(100,Number(data.patience??100))),level=badgeLevel(p),history=data.history||[];
    const counter=data.status==='counter'?data.counter:null;
    const ended=['ended','declined'].includes(data.status),success=['renewed','completed'].includes(data.status);
    return `<section class="tr-panel cn-agent-panel"><div class="cn-status-head"><span class="tr-kicker">NEGOTIATION STATUS</span><span class="tr-status-chip ${p<=25?'is-critical':''}">${success?'Agreed':ended?'Talks ended':data.status==='counter'?'Agent counteroffer':'Player talks'}</span></div>
      <div class="tr-patience"><strong>Relationship & tolerance</strong><div class="tr-tolerance-row"><div class="tr-tolerance-track" role="meter" aria-label="Player agent patience" aria-valuemin="0" aria-valuemax="100" aria-valuenow="${p}" aria-valuetext="${level}"><i style="left:${Math.max(1,Math.min(99,100-p))}%"></i></div><span class="tr-tolerance-label">${level}</span></div>
      <p>${esc(data.reason||'The agent is ready to hear your opening proposal. The bar reflects patience, not acceptance probability.')}</p></div>
      <div class="cn-agent-cards"><div class="cn-agent-card"><h4>Player & agent</h4><strong>Personal terms</strong><small>The player's role, contract length and ambitions affect the response.</small></div>
      <div class="cn-agent-card"><h4>Agent's current terms</h4>${counter?`<strong>${currency(counter.weekly_wage_gbp)} /wk</strong><p>${esc(String(counter.years))} year(s) · ${esc(counter.role)} · ${currency(counter.signing_bonus_gbp)} signing fee</p><small>${counter.bonuses?.length?counter.bonuses.map(b=>`${currency(b.amount_gbp)} on ${b.threshold} ${esc(b.kind)}`).join(' · '):'No performance bonuses required'}</small>`:'<p>No counterproposal received yet.</p>'}
        ${counter?`<button class="tr-btn tr-btn-primary" type="button" ${data.mode==='transfer'?`data-tr-personal-accept="${esc(data.dealId||'')}"`:'data-cn-accept="1"'}>Accept agent's terms →</button>`:''}</div></div>
      <div class="cn-thread"><span class="tr-kicker">CONVERSATION</span><div role="log" aria-label="Agent negotiation conversation" class="cn-thread-list">${history.length?[...history].reverse().map(e=>{
        const own=e.actor==='club',terms=e.terms||{};
        return `<article class="cn-message ${own?'is-own':''}"><div class="cn-message-crest">${own?crest(clubId,clubName):'<span class="cn-agent-avatar">AG</span>'}</div><div class="cn-message-body"><header><strong>${own?esc(clubName||'Your club'):'Player agent'}</strong><time>${esc(e.on_date||'')}</time></header><p>${esc(e.note||'')}</p><strong>${currency(terms.weekly_wage_gbp)} /wk</strong><small>${esc(terms.years||'')} years · ${esc(terms.role||'')} · ${currency(terms.signing_bonus_gbp)} signing bonus</small>
        ${terms.bonuses?.length?`<small>${terms.bonuses.map(b=>`${currency(b.amount_gbp)} at ${b.threshold} ${esc(b.kind)}`).join(' · ')}</small>`:''}</div></article>`;
      }).join(''):'<p class="cn-empty-thread">No messages yet. Your opening wage is entirely your choice.</p>'}</div></div>
      ${data.mode==='renewal'&&!ended&&!success?`<div class="cn-withdraw"><button type="button" class="tr-btn tr-btn-danger" data-cn-walk>Walk away</button><div data-cn-walk-confirm hidden><p>End these contract discussions? Your club cannot sign in this round.</p><button class="tr-btn tr-btn-danger" type="button" data-cn-confirm-walk>Confirm withdrawal</button><button class="tr-btn" type="button" data-cn-cancel-walk>Keep negotiating</button></div></div>`:''}
    </section>`;
  }
  function readForm(f){
    const bonuses=[],seen=new Set();
    for(const row of f.querySelectorAll('[data-cn-bonus-row]')){
      const kind=row.querySelector('[name=bonus_kind]').value;
      if(seen.has(kind))throw Error('Each type of performance bonus can appear only once');seen.add(kind);
      bonuses.push({kind,threshold:Number(row.querySelector('[name=bonus_threshold]').value),amount_gbp:amount(row.querySelector('[name=bonus_amount]').value)});
    }
    return {weekly_wage_gbp:amount(f.elements.namedItem('weekly_wage_gbp').value),
      years:Number(f.elements.namedItem('years').value),role:f.elements.namedItem('role').value,
      signing_bonus_gbp:amount(f.elements.namedItem('signing_bonus_gbp').value),bonuses};
  }
  // Shared editor actions work in the Transfer screen and the Renewal screen.
  document.addEventListener('click',event=>{
    const button=event.target.closest('button[data-cn-add-bonus],button[data-cn-remove-bonus],button[data-cn-preview],button[data-cn-reset],button[data-cn-add]');
    if(!button)return;
    const f=button.closest('form[data-cn-form]');if(!f)return;
    if(button.hasAttribute('data-cn-add-bonus')){
      const list=f.querySelector('[data-cn-bonuses]');if(list.children.length>=3)return;
      const next=types.find(([kind])=>![...list.querySelectorAll('[name=bonus_kind]')].some(el=>el.value===kind))?.[0]||'appearances';
      list.insertAdjacentHTML('beforeend',bonusRow(next,next==='promotion'?1:next==='appearances'?20:next==='clean_sheets'?5:10));
      f.querySelector('[data-cn-bonus-empty]').hidden=true;
    }else if(button.hasAttribute('data-cn-remove-bonus')){
      button.closest('[data-cn-bonus-row]')?.remove();f.querySelector('[data-cn-bonus-empty]').hidden=!!f.querySelector('[data-cn-bonus-row]');
    }else if(button.hasAttribute('data-cn-add')){
      const field=f.elements.namedItem(button.dataset.cnField);
      if(field)field.value=Math.min(1500000,amount(field.value)+Number(button.dataset.cnAdd)).toLocaleString('en-GB');
    }else if(button.hasAttribute('data-cn-reset')){
      f.querySelectorAll('.cn-money').forEach(input=>input.value='0');
      f.querySelector('[data-cn-bonuses]').replaceChildren();f.querySelector('[data-cn-bonus-empty]').hidden=false;
    }else if(button.hasAttribute('data-cn-preview')){
      try{const terms=readForm(f),out=f.querySelector('[data-cn-preview-output]');
        out.innerHTML=`<strong>${currency(terms.weekly_wage_gbp)} /wk</strong> · ${terms.years} years · ${currency(terms.signing_bonus_gbp)} signing bonus<br>${terms.bonuses.length?`Up to ${currency(terms.bonuses.reduce((n,b)=>n+b.amount_gbp,0))} in conditional bonuses.`:'No conditional bonuses.'}<br>This summarizes commitments; it does not predict acceptance.`;
      }catch(error){f.querySelector('[data-cn-preview-output]').textContent=error.message;}
    }
  });
  document.addEventListener('focusout',e=>{if(e.target.matches('input.cn-money')){
    try{const n=amount(e.target.value);e.target.value=e.target.closest('.cn-money-control')?n.toLocaleString('en-GB'):currency(n);}catch(_){/* Keep invalid input so the form can show an error. */}
  }});
  function renewalView(d){
    const player=d.player,club=window.FMClubIdentity?.resolve?.(d.club_id,d.club)||{display_name:d.club};
    const nation=window.FMPortraits?.nation?.(player.nationality,'tr-player-nation')||esc(player.nationality);
    const face=window.FMPortraits?.portrait?.(player,'tr-player-face')||`<span class="tr-player-face">${esc(player.name[0])}</span>`;
    const talk={...d.talk,mode:'renewal'};
    return `<div class="tr-immersive tr-fix02 cn-screen"><header class="tr-immersive-header"><div class="tr-page-title"><button type="button" class="tr-back" data-cn-back>← Back to Finances</button><h1>Contract Negotiation</h1></div><span class="tr-immersive-tag">TS-FIX-03 · PLAYER & AGENT</span></header>
      <section class="tr-neg-hero cn-hero"><div class="tr-hero-player" data-fm-club-theme="${esc(d.club_id)}">${face}<div class="tr-player-identity"><h2>${esc(player.name)}</h2><p>${esc(player.age)} years · ${esc(player.position)} · ${nation}</p><div class="tr-rating-facts"><div><small>OVR</small><strong>${esc(player.ovr)}</strong></div><div><small>Current wage</small><strong>${currency(d.current.weekly_wage_gbp)}/wk</strong></div><span class="tr-tag">Renewal</span></div></div></div>
       <div class="tr-hero-club tr-own-club">${crest(d.club_id,d.club,'tr-neg-club-image')}<div><small class="tr-kicker">YOUR CLUB</small><h3>${esc(club.display_name||d.club)}</h3><p>Discussing an extension</p></div></div><div class="tr-hero-budget"><small>Current agreement until</small><strong>${esc(d.current.expires_on)}</strong><span>Remaining wage capacity: ${currency(d.wage_headroom_gbp)}/wk</span></div></section>
       <div class="cn-global-feedback" role="status" aria-live="polite">${esc(feedback)}</div>
       <div class="tr-neg-layout">${form({quote:d.quote,current:d.current,talk,id:'cn-renewal-form'})}${panel({quote:d.quote,talk,clubId:d.club_id,clubName:d.club})}</div>
      </div>`;
  }
  function draw(){if(!host||!model)return;host.innerHTML=renewalView(model);window.FMClubIdentity?.paintWithin?.(host);}
  async function refresh(){if(!host||!playerId)return;
    try{const response=await fetch(`/api/contracts?player_id=${encodeURIComponent(playerId)}`,{cache:'no-store'}),d=await response.json();if(!response.ok)throw Error(d.error||`HTTP ${response.status}`);model=d;draw();}
    catch(e){host.innerHTML=`<section class="tr-panel"><h3>Contract discussion unavailable</h3><p>${esc(e.message)}</p><button data-cn-back class="tr-btn">Back to Finances</button></section>`;}
  }
  async function send(command){if(pending)return;pending=true;host.setAttribute('aria-busy','true');
    try{const response=await fetch('/api/finances',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(command)}),res=await response.json();if(!response.ok)throw Error(res.error||`HTTP ${response.status}`);feedback=res.status==='renewed'?'Contract signed and financial commitments recorded.':res.reason||'Negotiation updated.';await refresh();}
    catch(e){feedback=e.message;const msg=host.querySelector('.cn-global-feedback');if(msg)msg.textContent=feedback;}
    finally{pending=false;host?.setAttribute('aria-busy','false');}
  }
  function mount(element,pid){if(host!==element){host=element;
    host.addEventListener('submit',event=>{if(event.target.id!=='cn-renewal-form')return;event.preventDefault();
      try{const terms=readForm(event.target);send({action:'contract_offer',player_id:playerId,terms});}
      catch(e){feedback=e.message;const output=host.querySelector('.cn-global-feedback');if(output)output.textContent=feedback;}
    });
    host.addEventListener('click',event=>{const button=event.target.closest('button');if(!button)return;
      if(button.hasAttribute('data-cn-back'))window.FMNavigation?.navigate('Finances');
      if(button.hasAttribute('data-cn-accept'))send({action:'contract_accept',player_id:playerId});
      if(button.hasAttribute('data-cn-walk')){const c=host.querySelector('[data-cn-walk-confirm]');if(c)c.hidden=false;}
      if(button.hasAttribute('data-cn-cancel-walk')){const c=host.querySelector('[data-cn-walk-confirm]');if(c)c.hidden=true;}
      if(button.hasAttribute('data-cn-confirm-walk'))send({action:'contract_walk_away',player_id:playerId});
    });
  }playerId=pid;model=null;feedback='';host.innerHTML='<section class="tr-panel">Loading contract negotiation...</section>';refresh();}
  window.FMContractNegotiations=Object.freeze({mount,refresh,form,panel,readForm,currency});
})();
