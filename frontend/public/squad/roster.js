/* UI-3 roster table: purely presentational, fed by the Python read model.
   All unknown finance/season metrics render as unavailable (never estimated). */
(() => {
  'use strict';
  const state = {
    tab:'general', query:'', position:'all', availability:'all', group:'technical',
    expanded:null, more:false, season:'', competition:'all', sort:{general:['name','asc'],attributes:['name','asc'],season:['name','asc']}
  };
  const html = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const dec = value => Number.isFinite(Number(value)) && value !== null && value !== ''
    ? Number(value).toFixed(1).replace('.', ',') : '—';
  const title = name => String(name).replaceAll('_',' ').replace(/\b\w/g, c => c.toUpperCase());
  const empty = value => value == null || value === '' ? '<span class="rt-unavailable" title="Not recorded by the current Python engine">—</span>' : html(value);
  const percent = x => x == null ? empty(null) : `${dec(x)}%`;
  const legacyShirt = (position) => `<span class="rt-avatar ${position==='GK'?'rt-keeper':''}" aria-label="Player portrait placeholder"><svg viewBox="0 0 48 48" aria-hidden="true"><path d="M14 8h20l9 6 4 12-10 4-4-7v21H15V23l-4 7L1 26l4-12z" fill="currentColor" stroke="#9dd8ff" stroke-width="1.5"/><path d="M20 9c3 4 5 4 8 0" fill="none" stroke="#cdf2ff" stroke-width="2"/></svg></span>`;
  const face = (player,classes='') => window.FMPortraits?.portrait(player, classes) || legacyShirt(player.primary_position);
  const nation = (country) => window.FMPortraits?.nation(country) || html(country || 'Unknown');
  const contractDate = date => {
    const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(String(date||''));
    if(!match)return String(date||'—');
    const month=['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'][Number(match[2])-1];
    return month ? `${Number(match[3])} ${month} ${match[1]}` : String(date);
  };
  function contractCell(p){
    const details=p.contract_details;
    if(!details)return empty(p.contract);
    const amount=Number(details.weekly_wage_gbp);
    const wage=details.weekly_wage || (Number.isFinite(amount)&&amount>=0 ? `£${amount.toLocaleString('en-GB',{maximumFractionDigits:0})}` : null);
    const expiry=contractDate(details.expires_on);
    const expired=details.status==='out_of_contract_retained';
    return `<span class="rt-contract-cell${expired?' is-expired':''}" title="${html((wage||'Unknown wage')+'/week · '+(expired?'Expired '+expiry:'until '+expiry))}"><strong>${wage?html(wage)+'/w':empty(null)}</strong><small>${expired?'Expired':`until ${html(expiry)}`}</small></span>`;
  }
  const ratingClass = v => v < 60 ? 'rt-low' : v < 75 ? 'rt-medium' : v < 85 ? 'rt-good' : 'rt-high';
  const chip = v => v == null ? empty(null) : `<span class="rt-number ${ratingClass(v)}">${dec(v)}</span>`;
  const bar = n => n == null ? empty(null) : `<span class="rt-bar"><span style="width:${Math.max(0,Math.min(100,Number(n)))}%"></span></span><span>${dec(n)}%</span>`;
  const GENERAL = [
    ['position','Pos',65],['act','GRL',75],['base_ovr','Base OVR',90],
    ['market_value','Market value',110],['contract','Contract',170],['primary_position','Main pos.',90],
    ['secondary_positions','Other positions',155],['happiness','Happiness',110],
    ['age','Age',60],['number','No.',65],['morale','Morale',100],
    ['condition','Condition',140],['sharpness','Sharpness',100],
    ['foot','Foot',75],['transfer_status','Availability',125]
  ];
  const STATS = [
    ['appearances','Apps',75],['starts','Starts',75],['minutes','Minutes',90],
    ['goals','Goals',75],['assists','Assists',75],['clean_sheets','Clean sheets',115],
    ['xg','xG',90],['xa','xA',90],['pass_completion','Pass %',105],
    ['shots','Shots',75],['shots_on_target','Shots on target',135],['tackles','Tackles',90],
    ['yellow_cards','Yellow',80],['red_cards','Red',70],['average_match_rating','Avg rating',112]
  ];
  const ROLE_NAMES = {
    normal:'Available',transfer_listed:'Transfer listed',loan_listed:'Loan listed',untouchable:'Untouchable'
  };
  const ATTR_GROUPS = [
    ['technical','Technical'],['mental','Mental'],['physical','Physical'],['goalkeeping','Goalkeeping'],['all','All attributes']
  ];
  const select = (id, value, choices, label) => `<label class="rt-filter-label">${html(label)}<select id="${id}" data-roster-filter="${id}">${choices.map(([key,text]) => `<option value="${html(key)}" ${key===value?'selected':''}>${html(text)}</option>`).join('')}</select></label>`;
  function columns(data){
    if(state.tab==='general')return GENERAL;
    if(state.tab==='season')return STATS.filter(([key])=>!data.statistics?.supported || data.statistics.supported.includes(key));
    const names = ['technical','mental','physical','goalkeeping'];
    const groups = state.group === 'all' ? names : [state.group];
    const example = {attributes:Object.assign({},...data.roster.map(p=>Object.fromEntries(Object.entries(p.attributes||{}).filter(([,v])=>v))))};
    const attr = groups.flatMap(group => Object.keys(example.attributes?.[group]||{}).map(field => [`attr:${group}.${field}`,title(field),95]));
    return [['position','Pos',65],['act','GRL',75],['base_ovr','Base OVR',90],...attr];
  }
  function val(p,key){
    if(key.startsWith('attr:')){const [group,field]=key.slice(5).split('.');return p.attributes?.[group]?.[field]??null;}
    if(state.tab==='season')return p.season_stats?.[key]??null;
    if(key==='secondary_positions')return (p.secondary_positions||[]).join(', ');
    if(key==='position')return p.primary_position;
    return p[key]??null;
  }
  // Field order, not alphabetical. Map includes every Position enum value,
  // plus common aliases for when imported datasets eventually arrive.
  const POSITION_ORDER = ['GK','RB','RCB','CB','LCB','LB','RWB','LWB','RM','RDM','DM','CDM','LDM','RCM','CM','LCM','LM','RAM','AM','CAM','LAM','RW','RF','SS','LW','LF','CF','ST'];
  const positionRank = value => {
    const index=POSITION_ORDER.indexOf(String(value||'').toUpperCase());
    return index<0?POSITION_ORDER.length:index;
  };
  function compare(a,b,key,dir){
    const scalar=(p)=>key==='name'?p.name:key==='market_value'?p.market_value_gbp:key==='contract'?p.contract_details?.weekly_wage_gbp??null:val(p,key);
    const x=scalar(a),y=scalar(b);
    if(x==null && y==null)return a.name.localeCompare(b.name);
    if(x==null)return 1; // unknowns always at bottom
    if(y==null)return -1;
    if(key==='position'||key==='primary_position'){
      const diff=positionRank(x)-positionRank(y);
      if(diff)return dir==='asc'?diff:-diff;
      // A position group should be stable and useful: better OVR first.
      return (Number(b.base_ovr)||0)-(Number(a.base_ovr)||0)||a.name.localeCompare(b.name);
    }
    const sort=typeof x==='number'&&typeof y==='number'?x-y:String(x).localeCompare(String(y),undefined,{numeric:true});
    return (dir==='asc'?sort:-sort)||a.name.localeCompare(b.name);
  }
  function rows(data){
    const q=state.query.toLocaleLowerCase();
    const filtered=data.roster.filter(p=>(!q || `${p.name} ${p.nationality} ${p.primary_position}`.toLocaleLowerCase().includes(q))
      &&(state.position==='all'||p.primary_position===state.position||p.secondary_positions.includes(state.position))
      &&(state.availability==='all'|| (state.availability==='injured'?!p.available:p.transfer_status===state.availability)));
    const [key,dir]=state.sort[state.tab];
    return filtered.sort((a,b)=>compare(a,b,key,dir));
  }
  function formatCell(p,key){
    const v=val(p,key);
    if(key==='base_ovr'||key==='act')return chip(v);
    if(key.startsWith('attr:'))return `<span class="rt-attribute ${v>=85?'rt-attr-great':v>=75?'rt-attr-good':v>=60?'rt-attr-mid':'rt-attr-low'}">${v==null?'—':html(v)}</span>`;
    if(key==='condition')return `<span class="rt-condition ${v<55?'is-exhausted':v<75?'is-tired':''}">${bar(v)}</span>`;
    if(['morale','sharpness'].includes(key))return `<span class="rt-tonal">${percent(v)}</span>`;
    if(key==='market_value')return `<span title="Estimated market value; actual asking price may differ">${empty(v)}</span>`;
    if(key==='contract')return contractCell(p);
    if(key==='happiness')return empty(v);
    if(key==='transfer_status')return `<span class="rt-status ${v!=='normal'?'rt-flagged':''}">${ROLE_NAMES[v]||title(v)}</span>`;
    if(key==='number')return v==null?empty(null):`#${html(v)}`;
    if(key==='secondary_positions')return v?html(v):'—';
    if(key==='xg'||key==='xa'||key==='average_match_rating')return dec(v);
    if(key==='pass_completion')return percent(v);
    return empty(v);
  }
  function familiarities(p){
    const items=p.familiarities||[];
    if(!items.length)return '<section class="rt-familiarity rt-card"><h3>Positional familiarity</h3><p class="rt-muted">No positional learning data recorded.</p></section>';
    return `<section class="rt-familiarity rt-card"><div class="rt-card-header"><span>Positional familiarity</span><small>Live Python · effective score</small></div><div class="rt-familiarity-grid">${items.map(item=>`<div class="rt-fam"><div class="rt-fam-heading"><strong>${html(item.position)}</strong><span class="rt-fam-kind">${item.is_primary?'Primary':item.is_secondary?'Secondary':'Learned'}</span><b>${dec(item.effective)}</b></div><div class="rt-fam-meter"><span class="${ratingClass(item.effective)}" style="width:${Math.max(0,Math.min(100,item.effective))}%"></span></div><small>${item.peak == null?'Inferred from positional compatibility':`Peak ${dec(item.peak)} · ${Math.round(item.minutes)} mins`}</small></div>`).join('')}</div><p class="rt-fam-hint">Familiarity changes with playing time and inactivity. Values shown are read from the active player model.</p></section>`;
  }
  function bestAttributes(p){
    const values=Object.entries(p.attributes||{}).flatMap(([category,items])=>Object.entries(items||{}).filter(([,v])=>typeof v==='number').map(([name,value])=>({category,name,value})));
    values.sort((a,b)=>b.value-a.value||a.name.localeCompare(b.name));
    return `<section class="rt-key-attributes rt-card"><div class="rt-card-header"><span>Attribute highlights</span><small>Python attributes</small></div><div class="rt-top-attributes">${values.slice(0,6).map(a=>`<div class="rt-top-attribute"><span>${html(title(a.name))}</span>${chip(a.value)}</div>`).join('')||'<span class="rt-muted">No attributes recorded.</span>'}</div></section>`;
  }
  function fact(name,value,hint=''){
    return `<div class="rt-fact"><span>${html(name)}</span><strong>${value}</strong>${hint?`<small>${html(hint)}</small>`:''}</div>`;
  }
  function expanded(p, span, data){
    const avail=p.injury?'Injured':p.suspension?'Suspended':'Available';
    const fn=window.FMPortraits?.nation;
    const flag=fn?fn(p.nationality):html(p.nationality);
    return `<tr class="rt-expanded"><td colspan="${span}"><div class="rt-expanded-inner">
      <div class="rt-detail-toolbar"><span>Player details</span><div class="rt-detail-controls"><button type="button" class="rt-detail-manage" data-open-career-player="${html(p.id)}">Career history ↗</button>
        ${data.readonly?`<button type="button" class="rt-detail-manage" data-open-transfer-offer="${html(p.id)}">Make transfer offer →</button>`:`<button type="button" data-roster-more="${html(p.id)}" aria-expanded="${state.more}" class="rt-detail-manage">${state.more?'Hide management':'Player management'}</button>`}
        <button type="button" data-roster-expand="${html(p.id)}" class="rt-detail-close" aria-label="Close details for ${html(p.name)}">Close details <span aria-hidden="true">×</span></button>
      </div></div>
      <section class="rt-expanded-hero rt-card">
        <div class="rt-hero-profile">${face(p,'rt-portrait-large')}<div class="rt-profile-identity"><div class="rt-hero-overline">FIRST TEAM · ${html(p.primary_position)}</div><h2>${html(p.name)}</h2><div class="rt-profile-country">${flag}<span>· ${p.age} years old</span></div><div class="rt-hero-positions"><span class="rt-role-badge">${html(p.primary_position)} · Primary</span>${(p.secondary_positions||[]).map(pos=>`<span class="rt-role-badge minor">${html(pos)} · Secondary</span>`).join('')}</div><span class="rt-status-availability ${avail!=='Available'?'rt-alert':''}">${html(avail)}</span></div></div>
        <div class="rt-hero-scores"><div><small>Current GRL</small>${chip(p.act)}<span>ACT</span></div><div><small>Base overall</small>${chip(p.base_ovr)}<span>OVR</span></div><p>OVR: primary position · ACT: current context</p></div>
      </section>
      <section class="rt-expand-status rt-card" aria-label="Player status and information">
        ${fact('Morale',percent(p.morale))}
        ${fact('Condition',percent(p.condition),p.condition<75?'Fitness warning':'Physical status')}
        ${fact('Match sharpness',percent(p.sharpness))}
        ${fact('Preferred foot',html(title(p.foot)))}
        ${fact('Market value',empty(p.market_value),`Estimate · ${p.market_value_as_of||'current month'} · Asking price unknown`)}
        ${fact('Contract',empty(p.contract),'Signed weekly salary and contract expiration')}
        ${fact('Happiness',empty(p.happiness),'Separate system pending')}
      </section>
      <div class="rt-expanded-detail">${familiarities(p)}${bestAttributes(p)}</div>
      <section class="ts22-graphics rt-card" data-player-graphics="${html(p.id)}"><p>Loading attribute charts...</p></section>
      ${state.more?`<section class="rt-admin rt-card"><div class="rt-card-header"><span>Player management</span><small>Only active controls affect the DEV session</small></div>
        ${data.readonly?`<div class="ts22-readonly-actions"><button disabled>Negotiate with club (future)</button><button disabled>Declare interest (future)</button><button disabled>Contact player (future)</button></div>`:`<div class="rt-admin-controls">${select('rt-player-number',p.number==null?'':String(p.number),[['','Not assigned'],...Array.from({length:99},(_,i)=>[String(i+1),String(i+1)])],'Squad number')}${select('rt-transfer-status',p.transfer_status,Object.entries(ROLE_NAMES),'Transfer / loan status')}</div>
        <div class="rt-admin-actions"><button type="button" disabled title="Player conversations not implemented"><span class="rt-action-icon">✉</span><strong>Talk to player</strong><small>Planned</small></button><button type="button" disabled title="Training focus not implemented"><span class="rt-action-icon">◆</span><strong>Individual training</strong><small>Planned</small></button><button type="button" data-open-finances title="Open Finances to renew player contracts"><span class="rt-action-icon">▤</span><strong>Open Finances</strong><small>Renew contract</small></button></div>
        <p class="rt-fam-hint">Go to Finances to renew contracts and view wage budgets. Dorsal and transfer/loan flags remain development metadata; transfers and conversations are not yet active.</p>`}
      </section>`:''}
    </div></td></tr>`;
  }
  function summary(data){
    const values=data.roster.map(p=>p.act).filter(v=>typeof v==='number');
    const avg=values.length?values.reduce((a,b)=>a+b,0)/values.length:null;
    return `<div class="rt-overview"><div class="rt-title"><h2>${data.readonly?html(data.club)+' - Squad':'Squad'}</h2><p>${data.readonly?'Inspect':'Manage'} the complete first-team roster — sortable tables and player details</p></div><div class="rt-totals"><div><strong>${data.roster.length}</strong><span>Players</span></div><div><strong>${dec(avg)}</strong><span>Average GRL</span></div><div><strong>${data.roster.filter(p=>p.available).length}</strong><span>Available</span></div><div><strong>${html(data.stats_selection?.season||'Career')}</strong><span>Season</span></div></div></div>`;
  }
  function render(data){
    const cols=columns(data),list=rows(data),[sortedKey,sortedDir]=state.sort[state.tab];
    const allPositions=[...new Set(data.roster.flatMap(p=>[p.primary_position,...p.secondary_positions]))].sort();
    const groupSelector=state.tab==='attributes'?select('rt-attribute-group',state.group,ATTR_GROUPS,'Attribute group'):'';
    const selectedSeason=state.season||data.stats_selection?.season||data.statistics?.current_season;
    const coverage=data.statistics?.coverage?.[selectedSeason];
    const seasonNote=state.tab==='season'?`<div class="rt-stats-note"><strong>${coverage?.complete?'Recorded season statistics.':'Historical coverage is incomplete.'}</strong> ${coverage?.complete?'All completed, tracked matches; no shoot-out goals.':`Verified legacy totals are retained. Detailed tracking ${coverage?.from?'from '+html(coverage.from):'is not available for this season'}. Missing details remain unavailable; competition filters show recorded matches only.`} Pass % uses completed / attempted passes. Match rating is not current GRL. ${html(data.statistics?.clean_sheet_definition||'')}</div>`:'';
    const statsFilters=state.tab==='season'?select('rt-season',selectedSeason,(data.statistics?.seasons||[]).map(x=>[x,x]),'Season')+select('rt-competition',state.competition,[['all','All competitions'],...(data.statistics?.competitions||[]).map(x=>[x.id,x.name])],'Competition'):'';
    queueMicrotask(()=>window.FMPlayerPresentation?.hydrate(document,data));
    return `${window.FMPlayerPresentation?.clubHeader(data)||''}${summary(data)}<section class="rt-panel">
      ${!data.readonly ? `<div class="rt-academy-entry"><button type="button" data-open-youth-academy>View Youth Academy · U17 / U21 / Next academy intake</button></div>` : ''}
      <div class="rt-tabs" role="tablist" aria-label="Squad table views">${[['general','General'],['attributes','Attributes'],['season','Season stats']].map(([k,label])=>`<button type="button" role="tab" aria-selected="${state.tab===k}" data-roster-tab="${k}" class="${state.tab===k?'active':''}">${label}</button>`).join('')}</div>
      <div class="rt-tools"><label class="rt-search-label">Search players<input id="rt-search" type="search" value="${html(state.query)}" placeholder="Search name, position or nationality…" autocomplete="off" data-roster-query/></label>${select('rt-position',state.position,[['all','All positions'],...allPositions.map(p=>[p,p])],'Position')}${select('rt-availability',state.availability,[['all','All statuses'],['normal','Available'],['injured','Injured or suspended'],...Object.entries(ROLE_NAMES).filter(([k])=>k!=='normal')],'Status')}${groupSelector}${statsFilters}<div class="rt-sort-caption">Click a heading to sort ↑↓</div></div>
      ${seasonNote}<div class="rt-table-wrap" tabindex="0" role="region" aria-label="Scrollable roster table"><table class="rt-table"><thead><tr><th scope="col" class="rt-sticky rt-name-head" aria-sort="${sortedKey==='name'?(sortedDir==='asc'?'ascending':'descending'):'none'}"><button type="button" data-roster-sort="name">Player ${sortedKey==='name'?(sortedDir==='asc'?'↑':'↓'):'↕'}</button></th>${cols.map(([key,name,width])=>`<th scope="col" style="min-width:${width}px" aria-sort="${sortedKey===key?(sortedDir==='asc'?'ascending':'descending'):'none'}"><button type="button" title="Sort ${html(name)}" data-roster-sort="${html(key)}">${html(name)} ${sortedKey===key?(sortedDir==='asc'?'↑':'↓'):'↕'}</button></th>`).join('')}</tr></thead><tbody>${list.map(p=>`<tr class="rt-player-row ${state.expanded===p.id?'rt-open':''}"><th scope="row" class="rt-sticky"><div class="ts22-player-cell"><button type="button" class="rt-player-trigger" data-roster-expand="${html(p.id)}" aria-expanded="${state.expanded===p.id}">${face(p)}<span class="rt-player-name"><strong>${html(p.name)}</strong><small>${nation(p.nationality)} <span class="rt-position-muted">· ${html(p.primary_position)}</span></small></span></button><button type="button" class="rt-history-shortcut" data-open-career-player="${html(p.id)}" title="Open the career history of ${html(p.name)}" aria-label="Career history of ${html(p.name)}">↗</button><button type="button" class="ts22-more" data-roster-expand="${html(p.id)}" aria-label="${state.expanded===p.id?'Collapse':'Expand'} details for ${html(p.name)}" aria-expanded="${state.expanded===p.id}" title="${state.expanded===p.id?'Collapse':'Expand'} details">${state.expanded===p.id?'−':'+'}</button></div></th>${cols.map(([key])=>`<td>${formatCell(p,key)}</td>`).join('')}</tr>${state.expanded===p.id?expanded(p,cols.length+1,data):''}`).join('')}</tbody></table>${!list.length?'<p class="rt-no-results">No players match those filters.</p>':''}</div>
      <div class="rt-footnote"><span>${list.length} of ${data.roster.length} players · Fixed player column · Horizontal scroll for more attributes</span><span>GRL = current ACT / Base OVR shown separately</span></div></section>`;
  }
  function onClick(button, refresh){
    if(button.dataset.rosterTab){state.tab=button.dataset.rosterTab;state.expanded=null;refresh();return true;}
    if(button.dataset.rosterSort){
      const key=button.dataset.rosterSort; const current=state.sort[state.tab];
      state.sort[state.tab]=[key,current[0]===key&&current[1]==='asc'?'desc':'asc'];refresh();return true;
    }
    if(button.dataset.rosterMore){const same=state.expanded===button.dataset.rosterMore;state.expanded=button.dataset.rosterMore;state.more=same?!state.more:true;refresh();return true;}
    if(button.dataset.rosterExpand){state.more=false;state.expanded=state.expanded===button.dataset.rosterExpand?null:button.dataset.rosterExpand;refresh();return true;}
    return false;
  }
  function onChange(target, command, refresh){
    if(target.id==='rt-season'){state.season=target.value;window.FMRoster.reload?.();return true;}
    if(target.id==='rt-competition'){state.competition=target.value;window.FMRoster.reload?.();return true;}
    if(target.dataset.rosterFilter && !['rt-player-number','rt-transfer-status'].includes(target.id)){
      if(target.id==='rt-position')state.position=target.value;
      if(target.id==='rt-availability')state.availability=target.value;
      if(target.id==='rt-attribute-group')state.group=target.value;
      refresh();return true;
    }
    const playerId=state.expanded;
    if(!playerId)return false;
    if(target.id==='rt-player-number'){
      command({action:'squad_number',player_id:playerId,number:target.value===''?null:Number(target.value)},'Development squad number updated.');return true;
    }
    if(target.id==='rt-transfer-status'){
      command({action:'transfer_status',player_id:playerId,status:target.value},'Development transfer status updated.');return true;
    }
    return false;
  }
  function onInput(target, refresh){
    if(!target.matches('[data-roster-query]'))return false;
    state.query=target.value;
    const pos=target.selectionStart;
    refresh();
    const replacement=document.getElementById('rt-search');
    replacement?.focus();
    if(pos!==null)replacement?.setSelectionRange(pos,pos);
    return true;
  }
  window.FMRoster={render,onClick,onChange,onInput,format:dec,state,positionRank};
})();
