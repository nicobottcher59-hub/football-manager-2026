/* UI-3.5: embedded, sidebar-free Match Center. Only the Python API provides sporting data. */
(() => {
 'use strict';
 const root=document.getElementById('fm-match-root');
 const safe=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
 const fmt=n=>Number(n).toLocaleString('en-GB',{maximumFractionDigits:1});
 const dateLabel=d=>{const stamp=new Date(`${d}T12:00:00Z`);return Number.isNaN(stamp.getTime())?d:new Intl.DateTimeFormat('en-GB',{weekday:'short',day:'numeric',month:'short',year:'numeric',timeZone:'UTC'}).format(stamp);};
 const shirtSvg=`<svg viewBox="0 0 48 52" aria-hidden="true"><path d="M14 4 6 8 1 21l10 5 3-8v30h20V18l3 8 10-5-5-13-8-4-5 4H19z" fill="currentColor" stroke="#dff6ff" stroke-opacity=".56" stroke-width="1.25"/><path d="M19 8q5 6 10 0" fill="none" stroke="#f4fcff" stroke-opacity=".58"/></svg>`;
 let data=null,mode='prematch',selectedSlot=null, eventFilter='all',pending=false;
 let draftKits=null, selectedBenchId=null, dragPlayer=null;
 const icon={arrow:'➜',close:'×',left:'‹'};
 const requestedFixture=new URLSearchParams(location.search).get('fixture');
 async function api(method='GET',payload){const response=await fetch('/api/match',{method,headers:method==='POST'?{'Content-Type':'application/json'}:{},cache:'no-store',body:payload?JSON.stringify(payload):undefined}); const result=await response.json();if(!response.ok)throw new Error(result.error||'Python API error');return result;}
 function shellMessage(type,extra={}){if(window.parent!==window){window.parent.postMessage({type,...extra},location.origin);return true;}return false;}
 function notifyParent(){shellMessage('fm-match-world-changed');}
 function returnToGame(back=false){if(!shellMessage(back?'fm-match-back':'fm-match-return'))location.href='/portable/';}
 function clubLink(club,body,playerId=''){return `<button type="button" class="fm-profile-link" data-profile-club="${safe(club.id)}" ${playerId?`data-profile-player="${safe(playerId)}"`:''}>${body}</button>`;}
 function playerMetrics(player){const condition=Number(player.condition),act=Number(player.act),grade=condition>=85?'fresh':condition>=65?'tired':'low';return `<span class="fm-player-metrics"><b title="Current rating (ACT) in the selected position and role">${Number.isFinite(act)?fmt(act):'—'} <small>GRL</small></b><i class="${grade}" title="Physical condition">${Number.isFinite(condition)?fmt(condition)+'%':'—'}</i></span>`;}
 function crest(id,name,large=false){const letters=name==='Northbridge FC'?'N':name.split(' ').slice(0,2).map(s=>s[0]).join('').toUpperCase();return `<span class="fm-crest ${large?'big':''} ${id==='northbridge'?'fm-crest-home':'fm-crest-rival'}" aria-label="${safe(name)} crest"><span>${safe(letters)}</span></span>`;}
 function shirt(player,club,side='home',className='',previewColor=null){const color=previewColor||data?.kits?.[side]||'default';return `<span class="fm-jersey ${className}" data-team="${club.managed?'managed':'opponent'}" data-kit="${safe(color)}">${shirtSvg}<strong>${safe(player.number)}</strong></span>`;}
 function position(slot){const map={gk:[50,88],rb:[87,70],rcb:[62,70],cb:[50,70],lcb:[38,70],lb:[13,70],rwb:[87,60],lwb:[13,60],rdm:[64,52],ldm:[36,52],dm:[50,53],rcm:[69,43],lcm:[31,43],cm:[50,43],ram:[65,30],lam:[35,30],am:[50,32],rw:[84,20],lw:[16,20],rm:[88,39],lm:[12,39],rst:[62,14],lst:[38,14],st:[50,12]};return map[slot]||[50,50];}
 function pitch(club,side){return `<div class="fm-field fm-prematch-field" data-pitch-club="${safe(club.id)}" aria-label="${safe(club.name)} starting XI"><div class="fm-field-lines"><div class="fm-centre-circle"></div><div class="fm-top-box"></div><div class="fm-bottom-box"></div><div class="fm-halfway"></div></div>${club.starters.map(p=>{const fallback=position(p.slot_id),x=Number.isFinite(p.x)?p.x:fallback[0],y=Number.isFinite(p.y)?p.y:fallback[1];return `<div class="fm-on-pitch" data-pitch-slot="${safe(p.slot_id)}" data-x="${x}" data-y="${y}" style="left:${x}%;top:${y}%" title="${safe(p.name)} | ${safe(p.position)}">${shirt(p,club,side)}${clubLink(club,`<span class="fm-pitch-name">${safe(p.short_name||p.name)}</span>`,p.id)}${playerMetrics(p)}</div>`;}).join('')}</div>`;}
 function arrangePitches(){if(!window.FMFormationLayout)return;root.querySelectorAll('.fm-prematch-field').forEach(field=>{const nodes=[...field.querySelectorAll('[data-pitch-slot]')],points={},slots=[];for(const n of nodes){points[n.dataset.pitchSlot]={x:Number(n.dataset.x),y:Number(n.dataset.y)};slots.push({slot_id:n.dataset.pitchSlot});}if(!nodes.length)return;try{const placed=window.FMFormationLayout.arrange(points,slots,{width:field.clientWidth,height:field.clientHeight,cardWidth:Math.max(...nodes.map(n=>n.offsetWidth)),cardHeight:Math.max(...nodes.map(n=>n.offsetHeight)),gap:5,margin:8});for(const n of nodes){const p=placed[n.dataset.pitchSlot];n.style.left=p.x+'px';n.style.top=p.y+'px';}}catch(e){console.warn('Compact pitch layout unavailable',e.message);}});}
 function substituteBar(club,side){return `<section class="fm-subs"><h3>SUBSTITUTES <small>${club.bench.length}</small><span class="fm-metric-legend">GRL current / condition %</span></h3><div class="fm-subs-list">${club.bench.map(p=>`<div class="fm-sub">${shirt(p,club,side,'fm-mini-jersey')}${clubLink(club,`<span title="${safe(p.name)}">${safe(p.short_name||p.name)}</span>`,p.id)}${playerMetrics(p)}</div>`).join('')}</div></section>`;}
 function availability(club){const players=club.unavailable;return `<section class="fm-unavailable"><h3>UNAVAILABLE <small>${players.length}</small></h3>${players.length?`<div class="fm-unavailable-list">${players.map(p=>`<div class="fm-unavailable-row"><span class="fm-medical-symbol">${p.injury?'✚':'!'}</span><strong>${safe(p.name)}</strong><span>${p.injury?`Injured · ${safe(p.injury)}${p.return_on?' / Return: '+safe(p.return_on):''}`:`Suspended · ${p.suspension} game(s)`}</span></div>`).join('')}</div>`:'<p class="fm-muted">No unavailable players recorded for this team.</p>'}</section>`;}
 function teamPanel(club,side){return `<article class="fm-team-panel"><header class="fm-team-header">${clubLink(club,crest(club.id,club.name))}<div class="fm-team-identity"><h2>${clubLink(club,safe(club.name))}</h2><small>${safe(club.manager)}</small></div><div class="fm-formation"><strong>${safe(club.formation)}</strong><small>${club.managed?'Your XI':'Opponent XI'}</small></div></header>${pitch(club,side)}${substituteBar(club,side)}${availability(club)}</article>`;}
 function matchBanner(){const m=data.match;return `<div class="fm-match-info"><div class="fm-info-left"><span class="fm-competition-icon">🏆</span><div><b>${safe(m.competition)} · ${safe(m.round)}</b><span>${dateLabel(m.date)} <i>·</i> ${m.kickoff?safe(new Date(m.kickoff).toLocaleTimeString('en-GB',{hour:'2-digit',minute:'2-digit',timeZone:'UTC'}))+' UTC':'Time not set'}</span><span>${safe(m.stadium)}</span></div></div><div class="fm-versus-strip">${clubLink(data.home,crest(data.home.id,data.home.name,true))}<div class="fm-vs-name"><b>${clubLink(data.home,safe(data.home.name))}</b><small>HOME</small></div><em>VS</em><div class="fm-vs-name"><b>${clubLink(data.away,safe(data.away.name))}</b><small>AWAY</small></div>${clubLink(data.away,crest(data.away.id,data.away.name,true))}</div><div class="fm-info-right"><strong>☁ ${safe(m.weather)}</strong><strong>♙ ${safe(m.referee)}</strong></div></div>`;}
 function preMatch(){const m=data.match;return `<div class="fm-scene fm-pre-scene"><header class="fm-pre-top"><button class="fm-back" id="fm-back">← <span>Back</span></button><div><h1>Pre-Match</h1><p>Match information, lineups, availability and match-day options</p></div><span class="fm-phase-badge">MATCHDAY · PYTHON DEV</span></header>${matchBanner()}${planPanel()}<section class="fm-teams-grid">${teamPanel(data.home,'home')}${teamPanel(data.away,'away')}</section><nav class="fm-actions" aria-label="Match actions"><button class="fm-action fm-action-primary" id="fm-quick">▶ <span><b>Quick Sim</b><small>Simulate this match</small></span></button><button class="fm-action" disabled title="Immersive match playback is not implemented">▣ <span><b>Immersive Match</b><small>Coming soon</small></span></button><button class="fm-action" id="fm-kits">♧ <span><b>Kit Settings</b><small>Choose match-only shirt colours</small></span></button><button class="fm-action" id="fm-tactics">♧ <span><b>Match Tactics</b><small>One-off adjustments for this fixture</small></span></button></nav><div id="fm-notice" role="alert"></div></div>`;}
 function statCard(k,title,h,a,format='number'){if(h===null||a===null)return `<div class="fm-stat"><label>${title}</label><p class="fm-stat-unavailable">Not tracked</p></div>`;const total=Math.max(Number(h)+Number(a),1);const v=x=>format==='pct'?`${fmt(x)}%`:format==='decimal'?Number(x).toFixed(2):fmt(x);return `<div class="fm-stat"><label>${title}</label><div class="fm-stat-values"><b>${v(h)}</b><b>${v(a)}</b></div><div class="fm-comparison"><i style="width:${Math.max(0,Math.min(100,Number(h)/total*100))}%"></i><i></i></div></div>`;}
 const filters=[['all','All Events'],['goals','Goals'],['cards','Cards'],['subs','Substitutions'],['injuries','Injuries'],['key','Key Moments']];
 function eventName(e){switch(e.kind){case 'goal':return `GOAL · ${e.player}`;case 'card':return `${e.card==='red'?'Red':'Yellow'} card · ${e.player}`;case 'tactical_plan':return `Plan ${e.plan} ${e.applied?'applied':'not triggered'}`;case 'substitution':return 'Substitution';case 'half_time':return 'Half-time';case 'full_time':return 'Full-time';case 'shootout_kick':return e.scored?'Penalty scored':'Penalty missed';case 'injury':return 'Injury';default:return e.kind;}}
 function eventDetail(e){switch(e.kind){case 'goal':return e.assist?`Assist: ${e.assist}`:'Unassisted';case 'card':return e.card==='red'?'Sending off':'Booking';case 'tactical_plan':return `${e.name} | ${e.condition} | score ${e.own_goals}-${e.opponent_goals}`;case 'substitution':return `${e.player_out}  →  ${e.player_in}`;case 'half_time':return 'End of the first half';case 'full_time':return 'Final whistle';case 'shootout_kick':return `${e.player} · shootout ${e.home_score}–${e.away_score}`;default:return '';}}
 function eventSymbol(e){return {tactical_plan:'◇',goal:'⚽',card:e.card==='red'?'🟥':'🟨',substitution:'⇄',half_time:'◷',full_time:'◷',shootout_kick:'⚽',injury:'✚'}[e.kind]||'•';}
 function filteredEvents(){return (data.events||[]).filter(e=>eventFilter==='all'||eventFilter==='goals'&&e.kind==='goal'||eventFilter==='cards'&&e.kind==='card'||eventFilter==='subs'&&e.kind==='substitution'||eventFilter==='injuries'&&e.kind==='injury'||eventFilter==='key'&&['goal','card','shootout_kick','injury','tactical_plan'].includes(e.kind));}
 // Keep event icon and event description on the SAME side as the team.
 function resultTimeline(){
  const es=filteredEvents();
  const eventSide=e=>`<span class="fm-event-icon" aria-hidden="true">${eventSymbol(e)}</span><span class="fm-event-copy"><strong>${safe(eventName(e))}</strong><small>${safe(eventDetail(e))}</small></span>`;
  return `<div class="fm-events-head"><h2>Match Events <small>Chronological match report</small></h2><div class="fm-event-filters" role="group" aria-label="Filter match events">${filters.map(([v,t])=>`<button type="button" data-filter="${v}" class="${eventFilter===v?'active':''}">${t}</button>`).join('')}</div></div><div class="fm-timeline">${es.length?es.map(e=>{
    const neutral=!e.club_id;
    const isHome=e.club_id===data.home.id;
    return `<div class="fm-event fm-event-${safe(e.kind)} ${neutral?'fm-event-neutral':isHome?'fm-event-home':'fm-event-away'}"><div class="fm-event-side fm-home-lane">${!neutral&&isHome?eventSide(e):''}</div><time>${safe(e.minute)}′</time><div class="fm-event-side fm-away-lane">${neutral||!isHome?eventSide(e):''}</div></div>`;
   }).join(''):`<div class="fm-no-events">${eventFilter==='injuries'?'There were no recorded injury events in this match.':'No recorded events in this category.'}</div>`}</div>`;
 }
 function resultView(){const h=data.home,a=data.away,m=data.match;const hs=h.statistics,as=a.statistics;const pen=data.penalties;const aggregate=data.aggregate;return `<div class="fm-scene fm-result-scene"><header class="fm-final-header"><div class="fm-final-club">${crest(h.id,h.name,true)}<div><h1>${safe(h.name)}</h1><small>HOME</small></div></div><div class="fm-scoreboard"><strong>${h.goals}</strong><div><span>FULL TIME</span><small>FT</small></div><strong>${a.goals}</strong></div><div class="fm-final-club right">${crest(a.id,a.name,true)}<div><h1>${safe(a.name)}</h1><small>AWAY</small></div></div><button id="fm-result-continue" class="fm-continue">Continue <span>➜</span></button></header>${pen?`<div class="fm-decider">Penalty shootout: ${pen.home} – ${pen.away} ${data.winner_club_id?`· ${safe(data.winner_club_id===h.id?h.name:a.name)} advanced`:''}</div>`:data.decision==='extra_time'?'<div class="fm-decider">Decided after extra time</div>':''}${aggregate && (aggregate.home!==h.goals||aggregate.away!==a.goals)?`<div class="fm-decider">Aggregate score: ${aggregate.home} – ${aggregate.away}</div>`:''}<section class="fm-stats-panel">${statCard('pos','Possession',hs.possession,as.possession,'pct')}${statCard('xg','xG',hs.xg,as.xg,'decimal')}${statCard('shots','Shots',hs.shots,as.shots)}${statCard('sot','On target',hs.shots_on_target,as.shots_on_target)}${statCard('passes','Completed passes',hs.passes,as.passes)}${statCard('accuracy','Pass accuracy',hs.pass_accuracy,as.pass_accuracy,'pct')}${statCard('fouls','Fouls',hs.fouls,as.fouls)}${statCard('corners','Corners',hs.corners,as.corners)}</section>${data.new_injuries?.length?`<section class="fm-unavailable"><h3>POST-MATCH MEDICAL ASSESSMENT</h3>${data.new_injuries.map(p=>`<p><strong>${safe(p.player)}</strong>: ${safe(p.detail)}. Expected return: ${safe(p.return_on||'Not recorded')}.</p>`).join('')}</section>`:''}<section class="fm-events-panel">${resultTimeline()}</section><footer class="fm-result-note">Stats, scorers, assists, cards, substitutes and shootout kicks from Python. Tackles, in-play missed penalties and in-match injuries are not tracked by the current engine. Save the complete career to keep this report after restarting.</footer><div id="fm-notice" role="alert"></div></div>`;}
 function optionList(items,valueGetter,labelGetter,selected){return items.map(v=>`<option value="${safe(valueGetter(v))}" ${String(valueGetter(v))===String(selected)?'selected':''}>${safe(labelGetter(v))}</option>`).join('');}
 // All player changes go through the existing match-only Python tactical API.
 // Drag sources are validated against current starters/bench before submission.
 function matchTacticPitch(club,side){
  return `<div class="fm-field fm-tactics-field" aria-label="Editable starting eleven"><div class="fm-field-lines"><div class="fm-centre-circle"></div><div class="fm-top-box"></div><div class="fm-bottom-box"></div><div class="fm-halfway"></div></div>${club.starters.map(p=>{
    const target=club.managed?data.tactical?.studio?.shapes?.in_possession?.[p.slot_id]:null;
    const [x,y]=target?[target.x,target.y]:position(p.slot_id);
    return `<button type="button" class="fm-on-pitch fm-tactic-player ${selectedSlot===p.slot_id?'fm-player-active':''} ${selectedBenchId?'fm-drop-ready':''}" style="left:${x}%;top:${y}%" draggable="true" data-drag-kind="starter" data-player-id="${safe(p.id)}" data-slot-id="${safe(p.slot_id)}" aria-label="${safe(p.name)} at ${safe(p.position)}. Click to edit or drop a bench player to replace" title="Drag to swap positions, or drop a substitute">${shirt(p,club,side)}<span class="fm-pitch-name">${safe(p.short_name||p.name)}</span></button>`;
  }).join('')}</div>`;
 }
 function matchBench(club,side){
  return `<section class="fm-match-bench"><header><div><h3>Available substitutes <span>${club.bench.length}</span></h3><p>Drag a substitute onto a shirt, or select one and click the player to replace.</p></div><span class="fm-bench-hint">↔ DRAG & DROP</span></header><div class="fm-match-bench-grid">${club.bench.map(p=>`<button type="button" draggable="true" class="fm-bench-player ${selectedBenchId===p.id?'fm-bench-selected':''}" data-drag-kind="bench" data-player-id="${safe(p.id)}" aria-pressed="${selectedBenchId===p.id}" title="${safe(p.name)} · drag onto a starter">${shirt(p,club,side,'fm-mini-jersey')}<span class="fm-bench-player-copy"><strong>${safe(p.short_name||p.name)}</strong><small>${safe(p.position)} · ${fmt(p.condition)}% fitness</small></span><span class="fm-bench-handle" aria-hidden="true">⠿</span></button>`).join('')}</div></section>`;
 }
 function tacticsView(){
  const t=data.tactical, fields=t.tactics.fields,slots=t.slots;
  const slot=slots.find(s=>s.slot_id===selectedSlot)||slots[0];
  selectedSlot=slot.slot_id;
  const side=data.match.managed_home?'home':'away';
  return `<div class="fm-scene fm-tactics-scene"><header class="fm-pre-top fm-tactics-header"><button class="fm-back" id="fm-tactics-back">← <span>Back to Pre-Match</span></button><div><h1>Match Tactics</h1><p>Shape, roles and match-only instructions · your usual tactic stays untouched.</p></div><span class="fm-match-only-tag">THIS MATCH ONLY</span><button type="button" class="fm-secondary-button" id="fm-reset-tactics">↺ Reset changes</button></header>
    ${planPanel()}<section class="fm-tactic-controls"><label>Formation<select id="fm-formation">${optionList(t.formations,f=>f.id,f=>f.name,t.formation.id)}</select></label><label>Team approach<select id="fm-preset">${optionList(t.tactics.presets.filter(p=>p.id!=='custom'),p=>p.id,p=>p.name,t.tactics.preset)}</select></label><div class="fm-tactic-current"><span>Current style</span><b>${safe(t.tactics.style)}</b></div></section>
    <div class="fm-tactics-main"><section class="fm-tactical-left"><div class="fm-tactical-pitch-title"><div><h2>Starting XI <small>11 / 11</small></h2><p>Select a shirt to edit its role. Drag shirts to swap positions.</p></div><span>${safe(data.managed.formation)}</span></div>${matchTacticPitch(data.managed,side)}${matchBench(data.managed,side)}<div class="fm-swap-status" id="fm-swap-status" role="status">${selectedBenchId?'Substitute selected. Click a shirt on the pitch to replace its player.':'Select or drag any bench player onto a starting position.'}</div>
      <details class="fm-swap-fallback"><summary>Use dropdowns instead of dragging</summary><div class="fm-dual-select"><label>Starting XI<select id="fm-swap-starter">${optionList(t.starters,p=>p.id,p=>p.name,t.starters[0].id)}</select></label><label>Bench<select id="fm-swap-bench">${optionList(t.bench,p=>p.id,p=>p.name,t.bench[0]?.id)}</select></label><button id="fm-swap" class="fm-secondary-button">Swap players</button></div></details></section>
      <section class="fm-tactical-right"><div class="fm-role-heading"><div><small>SELECTED POSITION</small><h2>${safe(slot.position)} · ${safe(data.managed.starters.find(p=>p.slot_id===selectedSlot)?.name||'Starter')}</h2></div><span class="fm-role-pill">Player role</span></div><label>Role<select id="fm-role">${optionList(slot.roles,r=>r.id,r=>r.name,slot.role_id)}</select></label><h3>Player instructions <button id="fm-reset-individual" type="button" class="fm-inline-reset">Reset individual</button></h3><div class="fm-field-grid">${slot.individual.filter(field=>field.options.length>0||field.kind==='target').map(f=>`<label>${safe(f.label)}<select data-individual="${safe(f.field)}"><option value="default" ${f.override===null?'selected':''}>Role default · ${safe(f.effective||'none')}</option>${f.kind==='target'?`${optionList(t.targets.players,p=>'player:'+p.id,p=>p.name,f.override)}${optionList(t.targets.roles,r=>'role:'+r,r=>r,f.override)}`:optionList(f.options,x=>x,x=>x,f.override)}</select></label>`).join('')}</div><h3>Team instructions</h3><div class="fm-field-grid">${fields.filter(f=>f.options.length>0).map(f=>`<label>${safe(f.label)}<small>${safe(f.group.replaceAll('_',' '))}</small><select data-team-group="${safe(f.group)}" data-team-field="${safe(f.field)}">${optionList(f.options,x=>x,x=>x,f.value)}</select></label>`).join('')}</div></section></div><div id="fm-notice" role="alert"></div></div>`;
 }
 const kitColors={default:null,dark:'#1b2d40',light:'#f4f7ff',blue:'#138ae8',red:'#e74555',purple:'#853ce1',yellow:'#f1c344',green:'#17a273'};
 const kitHue=(side,color)=>kitColors[color]|| (side==='home'?'#1b2d40':'#853ce1');
 function kitDistance(a,b){const color=(s,k)=>{const h=kitHue(s,k).replace('#','');return [0,2,4].map(i=>parseInt(h.substring(i,i+2),16));};const x=color('home',a),y=color('away',b);return Math.sqrt(x.reduce((sum,v,i)=>sum+(v-y[i])**2,0));}
 function kitCard(side,club){
  const color=draftKits[side],hue=kitHue(side,color),other=side==='home'?'HOME':'AWAY';
  const options=(data.kit_choices||[]);
  return `<article class="fm-kit-card" style="--kit-accent:${hue}"><header class="fm-kit-card-header">${crest(club.id,club.name,true)}<div><h2>${safe(club.name)}</h2><span>${other} · ${color==='default'?'Club default kit':color[0].toUpperCase()+color.slice(1)+' kit'}</span></div><span class="fm-kit-club-role">${other}</span></header>
    <div class="fm-kit-showcase"><div class="fm-kit-stage"><span class="fm-kit-glow"></span><span class="fm-kit-spotlight"></span>${shirt({number:10},club,side,'fm-kit-hero-jersey',color)}<div class="fm-kit-stage-bottom"><span>10</span> <span>${safe(club.name)}</span></div></div>
    <div class="fm-kit-options"><label>Shirt colour<select id="fm-kit-${side}">${optionList(options,v=>v,v=>v==='default'?'Club default':v[0].toUpperCase()+v.slice(1),color)}</select></label><div class="fm-kit-swatches" role="group" aria-label="${other} kit colors">${options.map(opt=>`<button type="button" class="fm-kit-swatch ${color===opt?'active':''}" data-kit-side="${side}" data-kit-color="${safe(opt)}" aria-label="${side} ${opt} kit" aria-pressed="${color===opt}" title="${safe(opt)}"><span style="background:${kitHue(side,opt)}"></span>${color===opt?'<b aria-hidden="true">✓</b>':''}</button>`).join('')}</div><div class="fm-kit-outfit"><span>MATCH KIT</span><div class="fm-kit-outfit-row"><div>${shirt({number:10},club,side,'fm-mini-jersey',color)}<small>Shirt</small></div><div><i class="fm-kit-shorts" style="background:${hue}"></i><small>Shorts</small></div><div><i class="fm-kit-socks" style="--sock-color:${hue}"></i><small>Socks</small></div></div></div></div></div></article>`;
 }
 function kitsView(){
  if(!draftKits)draftKits={home:data.kits?.home||'default',away:data.kits?.away||'default'};
  const distance=kitDistance(draftKits.home,draftKits.away),distinct=distance>=115;
  return `<div class="fm-scene fm-kit-scene"><header class="fm-pre-top"><button class="fm-back" id="fm-kits-back">← <span>Back to Pre-Match</span></button><div><h1>Kit Settings</h1><p>Choose the two teams' appearance for this fixture.</p></div><span class="fm-match-only-tag">THIS MATCH ONLY</span></header>
    <div class="fm-kit-titlebar"><span>⚽ MATCHDAY KITS</span><strong>${safe(data.home.name)} <b>VS</b> ${safe(data.away.name)}</strong></div><section class="fm-kit-settings">${kitCard('home',data.home)}<div class="fm-kit-versus" aria-hidden="true">VS</div>${kitCard('away',data.away)}</section>
    <div class="fm-kit-summary"><div class="fm-kit-contrast ${distinct?'good':'warn'}"><span class="fm-kit-contrast-icon">${distinct?'✓':'!'}</span><div><h3>${distinct?'Distinct shirt colours':'Similar shirt colours'}</h3><p>${distinct?'The selected shirt colours are easy to tell apart.':'Consider using more distinct colours for the two teams.'}</p></div></div><div class="fm-kit-pair">${shirt({number:10},data.home,'home','fm-mini-jersey',draftKits.home)}<span>${safe(data.home.name)}</span><em>VS</em>${shirt({number:10},data.away,'away','fm-mini-jersey',draftKits.away)}<span>${safe(data.away.name)}</span></div></div>
    <div class="fm-kit-footer"><button type="button" class="fm-secondary-button" id="fm-reset-kits">↺ Reset to default</button><button id="fm-save-kits" class="fm-primary-button">✓ Save for this match</button></div><div id="fm-notice" role="alert"></div></div>`;
 }

 function planRuleRow(st,rule){
  return `<div class="fm-plan-rule"><label>Minute<input type="number" data-match-rule-minute min="1" max="119" value="${rule.minute}"></label><label>Plan<select data-match-rule-plan>${['A','B','C'].filter(key=>st.plans[key]).map(key=>`<option value="${key}" ${key===rule.plan?'selected':''}>${key} - ${safe(st.library.find(e=>e.id===st.plans[key])?.name)}</option>`).join('')}</select></label><label>Condition<select data-match-rule-condition>${[['always','Any score'],['leading','Leading'],['level','Level'],['trailing','Trailing']].map(([v,t])=>`<option value="${v}" ${v===rule.condition?'selected':''}>${t}</option>`).join('')}</select></label><button type="button" data-match-remove-rule aria-label="Remove rule">&times;</button></div>`;
 }
 function planPanel(){
  const st=data.tactical?.studio;if(!st)return '';
  const assigned=['A','B','C'].filter(key=>st.plans[key]);
  return `<section class="fm-match-plans"><header><div><strong>TACTICAL PLANS</strong><small>Saved in Tactical Studio. Match-only changes do not replace your usual setup.</small></div><div class="fm-plan-quick">${['A','B','C'].map(key=>{const entry=st.library.find(e=>e.id===st.plans[key]);return `<button type="button" data-match-plan="${key}" ${entry?'':'disabled'} title="Use this plan from kickoff"><b>${key}</b> ${safe(entry?.name||'Unassigned')}</button>`;}).join('')}</div></header>
   <details class="fm-match-schedule"><summary>During-match schedule (${st.rules.length})</summary><p>The engine checks each rule once, before that minute, using the actual score. No manual intervention is possible after Quick Sim has finished.</p><div id="fm-match-rules">${st.rules.map(r=>planRuleRow(st,r)).join('')}</div><div class="fm-match-rule-actions"><button type="button" id="fm-add-match-rule" ${assigned.length?'':'disabled'}>+ Add rule</button><button type="button" id="fm-save-match-rules">Apply for this match</button></div></details></section>`;
 }
 function error(msg){const dest=document.getElementById('fm-notice');if(dest)dest.innerHTML=`<div class="fm-error">${safe(msg)}</div>`;else root.innerHTML=`<div class="fm-error fm-fatal">${safe(msg)} <a href="/portable/#page/Home" target="_top">Return to game</a></div>`;}
 function setBusy(v){pending=v;if(v)root.querySelectorAll('button,select').forEach(el=>{el.disabled=true;});else render();}
 async function command(payload,keepMode=mode){if(pending)return;setBusy(true);try{data=await api('POST',{...payload,fixture_id:data.match.fixture_id});mode=data.status==='finished'?'result':keepMode;render();if(data.status==='finished')notifyParent();}catch(e){setBusy(false);error(e.message);}}
 function bind(){root.querySelectorAll('[data-profile-club]').forEach(el=>el.addEventListener('click',()=>{const clubId=el.dataset.profileClub,playerId=el.dataset.profilePlayer||null;if(!shellMessage('fm-open-club',{clubId,playerId}))location.href='/portable/#club/'+encodeURIComponent(clubId)+(playerId?'/'+encodeURIComponent(playerId):'');}));bindMatchPlans();const on=(id,fn)=>{const el=document.getElementById(id);if(el)el.addEventListener('click',fn);};on('fm-back',()=>returnToGame(true));on('fm-tactics-back',()=>{mode='prematch';render();});on('fm-kits-back',()=>{mode='prematch';render();});on('fm-tactics',()=>{mode='tactics';selectedSlot=data.tactical.slots[0].slot_id;selectedBenchId=null;render();});on('fm-kits',()=>{draftKits={home:data.kits?.home||'default',away:data.kits?.away||'default'};mode='kits';render();});on('fm-quick',()=>command({action:'quick_sim'},'result'));on('fm-reset-tactics',()=>command({action:'reset_match_tactics'},'tactics'));
  on('fm-save-kits',()=>command({action:'match_kits',home:draftKits.home,away:draftKits.away},'prematch'));
  on('fm-reset-kits',()=>{draftKits={home:'default',away:'default'};render();});
  for(const side of ['home','away'])document.getElementById(`fm-kit-${side}`)?.addEventListener('change',e=>{draftKits[side]=e.target.value;render();});
  root.querySelectorAll('[data-kit-color]').forEach(el=>el.addEventListener('click',()=>{draftKits[el.dataset.kitSide]=el.dataset.kitColor;render();}));
  on('fm-reset-individual',()=>command({action:'match_tactic',command:{action:'reset_player_instructions',slot_id:selectedSlot}},'tactics'));
  on('fm-swap',()=>command({action:'match_tactic',command:{action:'swap_bench',starter_id:document.getElementById('fm-swap-starter').value,bench_id:document.getElementById('fm-swap-bench').value}},'tactics'));
  const changes=[['fm-formation',e=>({action:'formation',id:e.target.value})],['fm-preset',e=>({action:'preset',id:e.target.value})],['fm-role',e=>({action:'role',slot_id:selectedSlot,role_id:e.target.value})]];
  for(const [id,builder] of changes){const element=document.getElementById(id);element?.addEventListener('change',e=>command({action:'match_tactic',command:builder(e)},'tactics'));}
  root.querySelectorAll('[data-slot]').forEach(el=>el.addEventListener('click',()=>{selectedSlot=el.dataset.slot;selectedBenchId=null;render();}));
  bindTacticDragging();
  root.querySelectorAll('[data-team-field]').forEach(el=>el.addEventListener('change',()=>command({action:'match_tactic',command:{action:'team_instruction',group:el.dataset.teamGroup,field:el.dataset.teamField,value:el.value}},'tactics')));
  root.querySelectorAll('[data-individual]').forEach(el=>el.addEventListener('change',()=>command({action:'match_tactic',command:{action:'player_instruction',slot_id:selectedSlot,field:el.dataset.individual,value:el.value}},'tactics')));
  bindEventFilters();
  on('fm-result-continue',async()=>{if(pending)return;setBusy(true);try{const pr=await fetch('/api/progression',{cache:'no-store'}).then(r=>r.json());if(pr.match_day){data=await api();mode=data.status==='finished'?'result':'prematch';render();return;}const r=await fetch('/api/progression',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action:'advance_day'})});const j=await r.json();if(!r.ok)throw new Error(j.error||'Unable to continue');notifyParent();returnToGame();}catch(e){setBusy(false);error(e.message);}});
 }

 function bindMatchPlans(){
  root.querySelectorAll('[data-match-plan]').forEach(el=>el.addEventListener('click',()=>command({action:'match_tactic',command:{action:'studio_activate_plan',plan:el.dataset.matchPlan}},mode)));
  const schedule=root.querySelector('.fm-match-schedule');if(!schedule)return;
  schedule.addEventListener('click',event=>{const button=event.target.closest('button');if(!button||pending)return;
   if(button.hasAttribute('data-match-remove-rule')){button.closest('.fm-plan-rule').remove();return;}
   if(button.id==='fm-add-match-rule'){
    const rows=schedule.querySelectorAll('.fm-plan-rule'),st=data.tactical.studio;
    if(rows.length>=6){error('At most six in-match plan rules.');return;}
    const plan=['A','B','C'].find(key=>st.plans[key]);if(plan)document.getElementById('fm-match-rules').insertAdjacentHTML('beforeend',planRuleRow(st,{plan,minute:60+rows.length*5,condition:'always'}));return;
   }
   if(button.id==='fm-save-match-rules'){
    const rules=Array.from(schedule.querySelectorAll('.fm-plan-rule')).map(row=>({minute:Number(row.querySelector('[data-match-rule-minute]').value),plan:row.querySelector('[data-match-rule-plan]').value,condition:row.querySelector('[data-match-rule-condition]').value}));
    command({action:'match_tactic',command:{action:'studio_rules',rules}},mode);
   }
  });
 }
 function swapTacticPlayers(from,to){
  if(pending||!from||!to)return;
  if(from.kind===to.kind&&from.playerId===to.playerId)return;
  let action=null;
  if(from.kind==='starter'&&to.kind==='starter'&&from.slotId!==to.slotId)action={action:'swap_starters',first:from.slotId,second:to.slotId};
  else if(from.kind==='bench'&&to.kind==='starter')action={action:'swap_bench',starter_id:to.playerId,bench_id:from.playerId};
  else if(from.kind==='starter'&&to.kind==='bench')action={action:'swap_bench',starter_id:from.playerId,bench_id:to.playerId};
  if(!action)return;
  if(to.slotId)selectedSlot=to.slotId;
  selectedBenchId=null;
  command({action:'match_tactic',command:action},'tactics');
 }
 function bindTacticDragging(){
  const tokens=root.querySelectorAll('[data-drag-kind]');
  if(!tokens.length)return;
  const read=el=>({kind:el.dataset.dragKind,playerId:el.dataset.playerId,slotId:el.dataset.slotId||null});
  tokens.forEach(el=>{
   el.addEventListener('dragstart',event=>{
    if(pending){event.preventDefault();return;}
    dragPlayer=read(el);event.dataTransfer.effectAllowed='move';
    event.dataTransfer.setData('text/plain',el.dataset.playerId);
    el.classList.add('fm-is-dragging');
    root.querySelector('.fm-tactics-field')?.classList.add('fm-drag-in-progress');
   });
   el.addEventListener('dragover',event=>{
    if(dragPlayer&&dragPlayer.playerId!==el.dataset.playerId&&(dragPlayer.kind!=='bench'||el.dataset.dragKind==='starter')){
     event.preventDefault();event.dataTransfer.dropEffect='move';el.classList.add('fm-drag-over');
    }
   });
   el.addEventListener('dragleave',()=>el.classList.remove('fm-drag-over'));
   el.addEventListener('drop',event=>{
    event.preventDefault();event.stopPropagation();el.classList.remove('fm-drag-over');
    const from=dragPlayer;dragPlayer=null;
    root.querySelectorAll('.fm-is-dragging,.fm-drag-over').forEach(x=>x.classList.remove('fm-is-dragging','fm-drag-over'));
    root.querySelector('.fm-tactics-field')?.classList.remove('fm-drag-in-progress');
    swapTacticPlayers(from,read(el));
   });
   el.addEventListener('dragend',()=>{
    dragPlayer=null;root.querySelectorAll('.fm-is-dragging,.fm-drag-over').forEach(x=>x.classList.remove('fm-is-dragging','fm-drag-over'));
    root.querySelector('.fm-tactics-field')?.classList.remove('fm-drag-in-progress');
   });
   el.addEventListener('click',()=>{
    if(pending)return;
    const item=read(el);
    if(item.kind==='bench'){selectedBenchId=selectedBenchId===item.playerId?null:item.playerId;render();return;}
    if(selectedBenchId){swapTacticPlayers({kind:'bench',playerId:selectedBenchId},item);return;}
    selectedSlot=item.slotId;render();
   });
  });
 }
 function bindEventFilters(){root.querySelectorAll('[data-filter]').forEach(el=>el.addEventListener('click',()=>{eventFilter=el.dataset.filter;const panel=root.querySelector('.fm-events-panel');if(panel)panel.innerHTML=resultTimeline();bindEventFilters();}));}
 function render(){pending=false;if(data.status==='no_match'){root.innerHTML=`<div class="fm-empty-state"><h1>No match waiting today</h1><p>${safe(data.message)}</p><a href="/portable/#page/Home" target="_top">Back to the game</a></div>`;return;}root.innerHTML=mode==='result'?resultView():mode==='tactics'?tacticsView():mode==='kits'?kitsView():preMatch();bind();requestAnimationFrame(arrangePitches);}
 async function init(){try{data=await api();if(requestedFixture&&data.match?.fixture_id&&data.match.fixture_id!==requestedFixture&&data.status==='prematch'){throw new Error('This Match Center refers to an older fixture. Return to the game and open Go to Match again.');}mode=data.status==='finished'?'result':'prematch';render();}catch(e){error(e.message);}}
 let layoutFrame=0;window.addEventListener('resize',()=>{cancelAnimationFrame(layoutFrame);layoutFrame=requestAnimationFrame(arrangePitches);});
 init();
})();
