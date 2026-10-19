/* TS-19 Tactical Studio. Native pointer/keyboard input; no build/runtime tooling.
 * Percent coordinates share the Python tactical_geometry convention (attack up).
 * Overlays are estimates from a static shape, never event heatmaps or forecasts.
 */
(function(global){
  'use strict';
  const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const clamp=(v,lo,hi)=>Math.max(lo,Math.min(hi,v));
  const gaussian=(x,y,p,sx,sy)=>Math.exp(-.5*(((x-p.x)/sx)**2+((y-p.y)/sy)**2));
  const coverage=(points,x,y)=>1-Math.exp(-points.reduce((sum,p)=>sum+gaussian(x,y,p,.16,.13),0));
  const restCover=(points,x)=>1-Math.exp(-points.reduce((sum,p)=>sum+gaussian(x,.72,p,.18,.18)*clamp((p.y-.34)/.26,0,1),0));
  const modes=[['coverage','Coverage','Estimated occupation'],['vulnerabilities','Vulnerabilities','Cover behind the ball'],['laboratory','Laboratory','Compare spatial occupation']];
  let context=null, mode='none', libraryOpen=false, scheduleOpen=false, librarySelection='', opponentChoice='actual';
  let observer=null, frame=0, drag=null, keyboard=null, pending=null, heatSurface=null, history=[], redo=[], suppressClickUntil=0;
  function outfield(data,points){return data.slots.filter(s=>s.position!=='GK').map(s=>({x:points[s.slot_id].x/100,y:points[s.slot_id].y/100}));}
  function marker(slot,player,pos,selected,studio){
    const label=displayPosition(studio,slot.position,pos),keeper=slot.position==='GK';
    const instructions=keeper?'Fixed goalkeeper. Click to view role.':'Drag to set phase target; arrows to move, Enter to apply, Escape to cancel.';
    return `<button type="button" class="fm-token ts-token ${keeper?'keeper':''} ${selected?'selected':''}" data-slot="${esc(slot.slot_id)}" data-studio-slot="${esc(slot.slot_id)}" style="left:${pos.x.toFixed(2)}%;top:${pos.y.toFixed(2)}%" aria-label="${esc(player.short_name)} at ${esc(label)}. ${instructions}" title="${esc(player.name)} | ${esc(player.role)} | ${Number(player.act).toFixed(1)} ACT"><span class="ts-token-core">${esc(label)}</span><span class="ts-token-name ${pos.y>85?'above':''}">${esc(player.short_name)}</span></button>`;
  }
  function footer(data,phase){
    return `<div class="ts-analysis-controls"><span class="ts-eyebrow">PITCH LAYERS</span><div class="ts-analysis-buttons">${modes.map(([key,name,hint])=>`<button type="button" data-studio="mode" data-mode="${key}" class="${mode===key?'active':''}" aria-pressed="${mode===key}" title="${hint}"><span aria-hidden="true">${key==='coverage'?'&#9678;':key==='vulnerabilities'?'&#9651;':'&#9671;'}</span>${name}</button>`).join('')}</div><button type="button" data-studio="mode" data-mode="none" class="ts-clear-layer" title="Hide analysis layer" aria-label="Hide analysis layer">&#215;</button></div>
      <div class="ts-overlay-summary" aria-live="polite"><div data-studio-summary></div><label class="ts-lab-opponent" ${mode!=='laboratory'?'hidden':''}>Compare against<select data-studio-opponent aria-label="Laboratory opponent"><option value="actual">${esc(data.studio.opponent.name)} &middot; ${esc(data.studio.opponent.formation)}</option>${data.formations.map(f=>`<option value="${esc(f.id)}" ${f.id===opponentChoice?'selected':''}>Catalogue: ${esc(f.name)}</option>`).join('')}</select></label></div>
      <div class="ts-board-tools"><span>Drag an outfield marker &middot; Goalkeeper fixed &middot; Arrows + Enter for keyboard placement</span><div><button type="button" data-studio="undo" title="Undo last position edit" ${history.length?'':'disabled'}>&#8630; Undo</button><button type="button" data-studio="copy-phase" title="Copy the other phase into this one">Copy other phase</button><button type="button" data-studio="reset-phase" title="Remove custom targets in this phase">Reset targets</button></div></div>`;
  }
  function option(entry,selected){return `<option value="${esc(entry.id)}" ${entry.id===selected?'selected':''}>${esc(entry.name)}</option>`;}
  function library(data){
    if(!data.studio)return '';
    const st=data.studio,active=st.library.find(e=>e.id===st.active_id);
    const valid=st.library.some(e=>e.id===librarySelection);
    if(!valid)librarySelection=st.active_id||st.library[0]?.id||'';
    const name=active?.name||data.formation.name;
    return `<section class="ts-library fm-panel" aria-label="Tactic library and match plans"><div class="ts-library-top"><div class="ts-library-identity"><span class="ts-studio-icon" aria-hidden="true">&#9671;</span><div><span class="ts-eyebrow">TACTICAL STUDIO</span><div class="ts-library-name">${esc(active?.name||'Working tactic')} <span class="ts-save-state ${st.dirty?'dirty':''}">${st.dirty?'Unsaved changes':'Saved template'}</span></div></div></div><div class="ts-library-buttons"><button type="button" data-studio="toggle-library" aria-expanded="${libraryOpen}">&#9638; Library <span>${st.library.length}</span></button><button type="button" data-studio="toggle-schedule" aria-expanded="${scheduleOpen}">&#9201; Match schedule <span>${st.rules.length}</span></button><button type="button" class="ts-save-quick" data-studio="quick-save">${active?'Save changes':'Save tactic'}</button></div></div>
    <div class="ts-plan-strip"><span class="ts-eyebrow">MATCH PLANS</span>${['A','B','C'].map(key=>{const id=st.plans[key],entry=st.library.find(e=>e.id===id);return `<div class="ts-plan ${id===st.active_id&&!st.dirty?'active':''}"><button type="button" data-studio="activate-plan" data-plan="${key}" ${entry?'':'disabled'} title="Load this saved plan into the current lineup"><b>${key}</b></button><div><small>Plan ${key}</small><select data-studio-plan="${key}" aria-label="Assign tactic to plan ${key}"><option value="">Not assigned</option>${st.library.map(e=>option(e,id)).join('')}</select></div><button type="button" class="ts-plan-apply" data-studio="activate-plan" data-plan="${key}" ${entry?'':'disabled'} aria-label="Apply plan ${key}">&#8599;</button></div>`;}).join('')}</div>
    ${libraryOpen?`<div class="ts-library-body"><div class="ts-library-save"><label>Tactic name<input id="ts-tactic-name" maxlength="60" value="${esc(name)}" autocomplete="off"></label><button type="button" data-studio="save">${active?'Overwrite current':'Save tactic'}</button><button type="button" data-studio="save-new">Save as new</button></div><div class="ts-library-manage"><label>Saved tactics<select id="ts-library-select" aria-label="Saved tactics"><option value="">Select a tactic</option>${st.library.map(e=>option(e,librarySelection)).join('')}</select></label><div>${[['load','Load'],['rename','Rename'],['duplicate','Duplicate'],['delete','Delete']].map(([key,label])=>`<button type="button" data-studio="${key}" ${librarySelection?'':'disabled'}>${label}</button>`).join('')}</div></div><p>Templates store shapes, football positions, roles and instructions &mdash; not player selections. Save the <strong>complete career</strong> to keep the library after closing the game.</p></div>`:''}
    ${scheduleOpen?`<div class="ts-schedule"><div class="ts-schedule-heading"><strong>During the match</strong><small>Checked once before the chosen minute. Only a matching score condition applies the plan.</small></div><div id="ts-plan-rules">${st.rules.map(rule=>ruleRow(st,rule)).join('')}</div><div class="ts-rule-actions"><button type="button" data-studio="add-rule" ${Object.values(st.plans).some(Boolean)?'':'disabled'}>+ Add rule</button><button type="button" data-studio="save-rules">Save schedule</button><span>Up to six changes &middot; extra-time rules run only if extra time is played.</span></div></div>`:''}</section>`;
  }
  function ruleRow(st,rule){
    return `<div class="ts-rule"><label>Minute<input type="number" min="1" max="119" value="${rule.minute}" data-rule-minute aria-label="Plan minute"></label><label>Use plan<select data-rule-plan aria-label="Scheduled plan">${['A','B','C'].filter(p=>st.plans[p]).map(p=>`<option value="${p}" ${p===rule.plan?'selected':''}>${p} &middot; ${esc(st.library.find(e=>e.id===st.plans[p])?.name)}</option>`).join('')}</select></label><label>When<select data-rule-condition aria-label="Plan score condition">${[['always','Any score'],['leading','Leading'],['level','Level'],['trailing','Trailing']].map(([v,n])=>`<option value="${v}" ${v===rule.condition?'selected':''}>${n}</option>`).join('')}</select></label><button type="button" data-studio="remove-rule" aria-label="Remove plan rule">&#215;</button></div>`;
  }
  // Zone definitions come from Python so the chooser and command validation agree.
  function positionOptions(studio,point,goalkeeper=false){
    if(!point||!Number.isFinite(point.x)||!Number.isFinite(point.y)||point.x<4||point.x>96||point.y<4||point.y>96)return [];
    if(goalkeeper)return [{position:'GK',label:'Goalkeeper'}];
    const x=point.x/100,y=point.y/100,e=1e-7;
    const zones=(studio?.position_zones||[]).filter(z=>x>=z.x_min-e&&x<=z.x_max+e&&y>=z.y_min-e&&y<=z.y_max+e);
    // A shared boundary can contain both winger and midfielder labels for the
    // same underlying LW/RW code. Show one compatible choice, not duplicates.
    return zones.filter((z,i)=>zones.findIndex(other=>other.position===z.position)===i);
  }
  function displayPosition(studio,position,point){
    return positionOptions(studio,point,position==='GK').find(z=>z.position===position)?.display_position||position;
  }
  function isGoalkeeper(slotId){
    return context?.data?.slots?.some(s=>s.slot_id===slotId&&s.position==='GK');
  }
  function positionControl(data,slot,phase='in_possession'){
    const point=data.studio.shapes[phase]?.[slot.slot_id];
    const options=positionOptions(data.studio,point,slot.position==='GK');
    const compatible=options.some(z=>z.position===slot.position);
    return `<div class="ts-position-control"><label>Position in this zone<select data-studio-position="${esc(slot.slot_id)}" ${slot.position==='GK'||!options.length?'disabled':''}>${!compatible?`<option value="" disabled selected>${esc(slot.position)} (current; outside zone)</option>`:''}${options.map(z=>`<option value="${z.position}" ${z.position===slot.position?'selected':''}>${esc(z.display_position||z.position)} &middot; ${esc(z.label)}</option>`).join('')}</select></label><p>Options follow the marker in this phase. The chosen football position applies in both phases; compatible roles and familiarity use the existing rules. Phase locations stay independent.</p><button type="button" data-studio="reset-point" data-slot-id="${esc(slot.slot_id)}" ${slot.position==='GK'?'disabled title="Goalkeeper position is fixed"':''}>Reset this phase target</button></div>`;
  }
  function focusSlot(slotId){
    const token=Array.from(context?.root.querySelectorAll('[data-studio-slot]')||[]).find(el=>el.dataset.studioSlot===slotId);
    token?.focus({preventScroll:true});
  }
  function closePlacement(){
    const dialog=context?.root.querySelector('.ts-placement-dialog');
    if(dialog){dialog.close();dialog.remove();}
    context?.root.classList.remove('ts-placing');
  }
  function cancelPlacement(){
    const slotId=pending?.slotId;pending=null;closePlacement();
    if(context){setVisual(context.shape());context.announce('Placement cancelled. No changes applied.');focusSlot(slotId);}
  }
  function proposePosition(state){
    const slot=context.data.slots.find(s=>s.slot_id===state.slotId);
    const point=state.points[state.slotId];
    point.x=Number(point.x.toFixed(4));point.y=Number(point.y.toFixed(4));
    const options=positionOptions(context.data.studio,point,slot.position==='GK');
    if(!options.length){finishPreview();context.announce('No compatible position in this area. Refresh the editor and try again.',true);return;}
    state.originalPosition=slot.position;state.revision=context.data.studio.revision;
    if(slot.position==='GK'){finishPreview();return;}
    pending=state;drag=null;keyboard=null;context.root.classList.add('ts-placing');
    const player=context.data.starters.find(p=>p.slot_id===state.slotId);
    const html=`<dialog class="ts-placement-dialog" aria-labelledby="ts-placement-title" aria-describedby="ts-placement-note"><div class="ts-placement-head"><div><span class="ts-eyebrow">${state.phase==='in_possession'?'IN POSSESSION':'OUT OF POSSESSION'}</span><h2 id="ts-placement-title">Choose position</h2></div><button type="button" data-studio="cancel-placement" aria-label="Cancel placement">&#215;</button></div><p class="ts-placement-player">${esc(player?.short_name||state.slotId)} <span>Current: ${esc(slot.position)}</span></p><p id="ts-placement-note">Choose a position compatible with this area. Nothing changes until you choose.</p><div class="ts-placement-options">${options.map(z=>`<button type="button" data-studio="confirm-placement" data-position="${z.position}" ${z.position===slot.position?'autofocus':''}><b>${esc(z.display_position||z.position)}</b><span>${esc(z.label)}${z.display_position&&z.display_position!==z.position?`<small>Uses existing ${esc(z.position)} roles</small>`:z.position===slot.position?'<small>Keep current position</small>':''}</span><span aria-hidden="true">&#8594;</span></button>`).join('')}</div><p class="ts-placement-footnote">Position and role apply in both phases. This move sets only the selected phase location; the other phase stays in place.</p><div class="ts-placement-actions"><button type="button" data-studio="cancel-placement">Cancel move</button></div></dialog>`;
    context.root.insertAdjacentHTML('beforeend',html);
    const dialog=context.root.querySelector('.ts-placement-dialog');
    dialog.addEventListener('cancel',event=>{event.preventDefault();cancelPlacement();});
    dialog.addEventListener('click',event=>{if(event.target===dialog){const r=dialog.getBoundingClientRect();if(event.clientX<r.left||event.clientX>r.right||event.clientY<r.top||event.clientY>r.bottom)cancelPlacement();}});
    dialog.showModal();
    (dialog.querySelector('[autofocus]')||dialog.querySelector('[data-position]'))?.focus({preventScroll:true});
    setVisual(state.points);
  }
  // Fixed scale: red=low, yellow=medium, green=high. Never normalize each tactic
  // independently, which would make different formations impossible to compare.
  const HEAT_STOPS=[[0,[239,68,68]],[.25,[245,158,11]],[.5,[250,204,21]],[.75,[132,204,22]],[1,[34,197,94]]];
  function coverageColor(value){
    value=clamp(Number.isFinite(value)?value:0,0,1);
    const index=Math.min(3,Math.floor(value*4)),[a,left]=HEAT_STOPS[index],[b,right]=HEAT_STOPS[index+1],t=(value-a)/(b-a);
    return left.map((v,i)=>Math.round(v+(right[i]-v)*t));
  }
  function paintCoverage(painter,points,width,height){
    if(!heatSurface)heatSurface=global.document.createElement('canvas');
    const cols=80,rows=100;
    if(heatSurface.width!==cols||heatSurface.height!==rows){heatSurface.width=cols;heatSurface.height=rows;}
    const buffer=heatSurface.getContext('2d'),image=buffer.createImageData(cols,rows);
    for(let row=0;row<rows;row++)for(let col=0;col<cols;col++){
      const rgb=coverageColor(coverage(points,(col+.5)/cols,(row+.5)/rows));
      const offset=4*(row*cols+col);image.data[offset]=rgb[0];image.data[offset+1]=rgb[1];image.data[offset+2]=rgb[2];image.data[offset+3]=174;
    }
    buffer.putImageData(image,0,0);painter.imageSmoothingEnabled=true;painter.imageSmoothingQuality='high';
    painter.drawImage(heatSurface,0,0,width,height);
  }
  function rivalPoints(){
    const {data,phase}=context,opposite=phase==='in_possession'?'out_of_possession':'in_possession';
    const slots=opponentChoice==='actual'?data.studio.opponent.shapes[opposite]:data.formations.find(f=>f.id===opponentChoice)?.slots||[];
    return slots.filter(p=>(p.position||p.label)!=='GK').map(p=>({x:1-p.x/100,y:1-p.y/100}));
  }
  function summary(points){
    if(mode==='none')return '<span class="ts-neutral-note">Phase targets feed the match engine. Manual targets override automatic positioning for that marker.</span>';
    if(mode==='coverage'){
      const zones=[['Left',.2],['Centre',.5],['Right',.8]].map(([name,x])=>[name,Math.round(100*[.3,.5,.7].reduce((s,y)=>s+coverage(points,x,y),0)/3)]);
      return `<span class="ts-legend"><i class="coverage"></i>Low (red) &middot; Medium (yellow) &middot; High (green)</span>${zones.map(([name,v])=>`<span>${name} <b>${v}%</b></span>`).join('')}<small>Geometric estimate, not a measured match heatmap.</small>`;
    }
    if(mode==='vulnerabilities'){
      const vulnerable=[['Left channel',.16],['Central channel',.5],['Right channel',.84]].filter(([,x])=>restCover(points,x)<.55).map(([name])=>name);
      return `<span class="ts-legend"><i class="vulnerabilities"></i>${context.phase==='in_possession'?'Rest defence after a loss':'Defensive cover'}</span><strong class="${vulnerable.length?'ts-warn':'ts-safe'}">${vulnerable.length?esc(vulnerable.join(' / '))+' exposed':'No major channel gap in this shape'}</strong><small>Static spacing warning, not a guaranteed counterattack or automatic penalty.</small>`;
    }
    const rivals=rivalPoints();let own=0,away=0;
    for(let x=.1;x<1;x+=.1)for(let y=.1;y<1;y+=.1){const diff=coverage(points,x,y)-coverage(rivals,x,y);if(diff>.18)own++;if(diff<-.18)away++;}
    return `<span class="ts-legend"><i class="laboratory"></i>Blue: your occupation &middot; amber: opposition</span><span>Favourable cells <b>${own}</b> &middot; Opponent cells <b>${away}</b></span><small>${opponentChoice==='actual'?'Current opponent and opposite phase.':'Hypothetical catalogue structure.'} This is not a match-result prediction.</small>`;
  }
  function draw(){
    frame=0;if(!context)return;
    const canvas=context.root.querySelector('.ts-overlay');if(!canvas)return;
    const bounds=canvas.getBoundingClientRect();if(!bounds.width||!bounds.height)return;
    const dpr=Math.min(2,global.devicePixelRatio||1);
    if(canvas.width!==Math.round(bounds.width*dpr)||canvas.height!==Math.round(bounds.height*dpr)){
      canvas.width=Math.round(bounds.width*dpr);canvas.height=Math.round(bounds.height*dpr);
    }
    const painter=canvas.getContext('2d');painter.setTransform(dpr,0,0,dpr,0,0);painter.clearRect(0,0,bounds.width,bounds.height);
    const raw=(pending?.points||drag?.points||keyboard?.points||context.shape()),points=outfield(context.data,raw),rivals=mode==='laboratory'?rivalPoints():[];
    if(mode==='coverage')paintCoverage(painter,points,bounds.width,bounds.height);
    if(mode!=='none'&&mode!=='coverage'){
      const cols=30,rows=38,w=bounds.width/cols,h=bounds.height/rows;
      for(let col=0;col<cols;col++)for(let row=0;row<rows;row++){
        const x=(col+.5)/cols,y=(row+.5)/rows;let amount=0,color='';
        if(mode==='vulnerabilities'){
          // Vulnerability is a rest-defence estimate in our half, not just an
          // inverted heatmap that paints the opponent's goal as dangerous.
          amount=(1-restCover(points,x))*clamp((y-.43)/.22,0,1)*clamp((.99-y)/.12,0,1);
          color=`rgba(247,88,105,${(amount*.54).toFixed(3)})`;
        }
        if(mode==='laboratory'){const diff=coverage(points,x,y)-coverage(rivals,x,y);amount=Math.abs(diff);color=diff>=0?`rgba(45,189,245,${amount*.47})`:`rgba(248,183,77,${amount*.45})`;}
        painter.fillStyle=color;painter.fillRect(col*w,row*h,w+.5,h+.5);
      }
      if(mode==='laboratory')rivals.forEach(p=>{painter.beginPath();painter.arc(p.x*bounds.width,p.y*bounds.height,8,0,Math.PI*2);painter.strokeStyle='#f3bd65';painter.lineWidth=1.5;painter.stroke();});
    }
    canvas.setAttribute('aria-hidden',mode==='none'?'true':'false');canvas.setAttribute('role','img');canvas.setAttribute('aria-label',mode==='coverage'?'Estimated coverage: red low, yellow medium, green high. See the numeric channel summary below.':'Tactical '+mode+' layer');
    const dest=context.root.querySelector('[data-studio-summary]');if(dest)dest.innerHTML=summary(points);
    const lab=context.root.querySelector('.ts-lab-opponent');if(lab)lab.hidden=mode!=='laboratory';
    context.root.querySelectorAll('[data-studio="mode"][data-mode]').forEach(b=>{b.classList.toggle('active',b.dataset.mode===mode);b.setAttribute('aria-pressed',String(b.dataset.mode===mode));});
  }
  function redraw(){if(frame)global.cancelAnimationFrame(frame);frame=global.requestAnimationFrame(draw);}
  async function send(payload,message){
    if(!context||context.busy())return false;
    return context.command({...payload,expected_revision:context.data.studio.revision},message);
  }
  function currentTargets(){return Object.entries(context.data.studio.anchors[context.phase]||{}).filter(([slot_id])=>!isGoalkeeper(slot_id)).map(([slot_id,p])=>({slot_id,x:p.x,y:p.y}));}
  function setVisual(points){context.root.querySelectorAll('[data-studio-slot]').forEach(el=>{const p=points[el.dataset.studioSlot];if(p){el.style.left=p.x+'%';el.style.top=p.y+'%';el.classList.toggle('ts-manual',Boolean(context.data.studio.anchors[context.phase]?.[el.dataset.studioSlot]));}});redraw();}
  function finishPreview(){drag=null;keyboard=null;context?.root.classList.remove('ts-dragging');if(context)setVisual(context.shape());}
  async function commitPosition(state,position){
    if(context.data.studio.revision!==state.revision){cancelPlacement();context.announce('Tactics changed. Drop the marker again.',true);return;}
    const {slotId,points,phase,before,revision,originalPosition}=state,p=points[slotId];
    pending=null;closePlacement();
    const changed=position!==originalPosition;
    const ok=await send({action:'studio_place',slot_id:slotId,phase,position,x:p.x,y:p.y},changed?`Position ${position} applied with a compatible role. Other phase location preserved.`:'Phase target applied. Football position and role unchanged.');
    if(ok){
      // Like existing explicit role/position edits, changing the role family
      // ends the target-only undo chain. Do not restore coordinates without
      // restoring the corresponding position and silently create a mismatch.
      if(changed){history=[];}
      else {history.push({phase,points:before,revision:revision+1});if(history.length>20)history.shift();}
      redo=[];context.root.querySelector('[data-studio="undo"]')?.toggleAttribute('disabled',!history.length);
    }
    drag=null;keyboard=null;context?.root.classList.remove('ts-dragging');if(context){setVisual(context.shape());focusSlot(slotId);}
  }
  function pointerDown(event){
    const token=event.target.closest('[data-studio-slot]');
    if(!token||event.button!==0||context.busy()||pending||isGoalkeeper(token.dataset.studioSlot))return;
    if(keyboard)finishPreview();
    const field=context.root.querySelector('.fm-pitch'),bounds=field.getBoundingClientRect(),points=context.shape();
    drag={slotId:token.dataset.studioSlot,token,pointerId:event.pointerId,bounds,points:structuredClone(points),phase:context.phase,before:currentTargets(),startX:event.clientX,startY:event.clientY,moved:false};
    token.setPointerCapture(event.pointerId);event.preventDefault();token.focus();
  }
  function pointerMove(event){
    if(!drag||drag.pointerId!==event.pointerId)return;
    const b=drag.bounds;if(Math.hypot(event.clientX-drag.startX,event.clientY-drag.startY)<3&&!drag.moved)return;
    drag.moved=true;context.root.classList.add('ts-dragging');
    drag.points[drag.slotId]={x:clamp((event.clientX-b.left)/b.width*100,4,96),y:clamp((event.clientY-b.top)/b.height*100,4,96)};
    setVisual(drag.points);
  }
  function pointerUp(event){
    if(!drag||drag.pointerId!==event.pointerId)return;
    const state=drag;drag=null;state.token.releasePointerCapture?.(event.pointerId);context.root.classList.remove('ts-dragging');
    if(state.moved){suppressClickUntil=Date.now()+350;proposePosition(state);}else context.select(state.slotId);
  }
  function pointerCancel(){if(drag)finishPreview();}
  function keyDown(event){
    const token=event.target.closest('[data-studio-slot]');
    if(event.key==='Escape'&&(drag||keyboard)){event.preventDefault();finishPreview();context.announce('Placement cancelled.');return;}
    if(!token||context.busy()||pending)return;
    if(isGoalkeeper(token.dataset.studioSlot)){
      if(event.key.startsWith('Arrow'))event.preventDefault();
      return;
    }
    if(event.key==='Enter'&&keyboard){event.preventDefault();const state=keyboard;keyboard=null;proposePosition(state);return;}
    const offsets={ArrowLeft:[-1,0],ArrowRight:[1,0],ArrowUp:[0,-1],ArrowDown:[0,1]};
    if(!offsets[event.key])return;event.preventDefault();
    if(!keyboard||keyboard.slotId!==token.dataset.studioSlot)keyboard={slotId:token.dataset.studioSlot,points:structuredClone(context.shape()),phase:context.phase,before:currentTargets()};
    const step=event.shiftKey?5:1,p=keyboard.points[keyboard.slotId],delta=offsets[event.key];
    p.x=clamp(p.x+delta[0]*step,4,96);p.y=clamp(p.y+delta[1]*step,4,96);setVisual(keyboard.points);
  }
  function keepEdits(){return !context.data.studio.dirty||global.confirm('Load this template and replace the working tactic? Unsaved changes will be discarded.');}
  async function click(event){
    const b=event.target.closest('button');if(!b)return;
    if(b.dataset.studioSlot){if(Date.now()>suppressClickUntil&&!drag&&!keyboard&&!pending)context.select(b.dataset.studioSlot);return;}
    const action=b.dataset.studio;if(!action)return;
    if(context.busy())return;
    if(action==='cancel-placement'){cancelPlacement();return;}
    if(action==='confirm-placement'){if(pending)return commitPosition(pending,b.dataset.position);return;}
    const st=context.data.studio,q=selector=>context.root.querySelector(selector);
    if(action==='mode'){mode=mode===b.dataset.mode?'none':b.dataset.mode;redraw();return;}
    if(action==='toggle-library'){libraryOpen=!libraryOpen;context.render();return;}
    if(action==='toggle-schedule'){scheduleOpen=!scheduleOpen;context.render();return;}
    if(action==='quick-save'){
      if(!st.active_id){libraryOpen=true;context.render();q('#ts-tactic-name')?.focus();return;}
      const active=st.library.find(e=>e.id===st.active_id);return send({action:'studio_save',entry_id:active.id,name:active.name},'Tactic template updated. Save the career to persist it to disk.');
    }
    if(action==='save'||action==='save-new')return send({action:'studio_save',name:q('#ts-tactic-name').value,...(action==='save'&&st.active_id?{entry_id:st.active_id}:{})},'Tactic saved in the library. Remember to save your career.');
    if(action==='activate-plan'){if(keepEdits())return send({action:'studio_activate_plan',plan:b.dataset.plan},'Saved match plan loaded.');return;}
    if(action==='load'){if(librarySelection&&keepEdits())return send({action:'studio_load',entry_id:librarySelection},'Tactic loaded using the current eleven.');return;}
    if(action==='delete'){if(librarySelection&&global.confirm('Delete this tactic? Its plan assignments and scheduled rules will also be removed.'))return send({action:'studio_delete',entry_id:librarySelection},'Tactic deleted.');return;}
    if(action==='rename'||action==='duplicate'){
      const entry=st.library.find(e=>e.id===librarySelection);if(!entry)return;
      const name=global.prompt(action==='rename'?'New tactic name':'Name for the duplicate',entry.name+(action==='duplicate'?' copy':''));
      if(name!==null)return send({action:'studio_'+action,entry_id:entry.id,name},'Library updated.');return;
    }
    if(action==='reset-point'&&isGoalkeeper(b.dataset.slotId))return;
    if(action==='reset-point')return send({action:'studio_point',slot_id:b.dataset.slotId,phase:context.phase,reset:true},'Automatic phase positioning restored for this marker.');
    if(action==='reset-phase'){if(global.confirm('Remove manual targets in this phase and return to automatic positioning?'))return send({action:'studio_shape',phase:context.phase,points:[]},'Automatic phase shape restored.');return;}
    if(action==='copy-phase'){
      const phase=context.phase==='in_possession'?'out_of_possession':'in_possession',points=context.data.studio.shapes[phase];
      if(global.confirm('Replace this phase with the other phase\'s current shape?'))return send({action:'studio_shape',phase:context.phase,points:Object.entries(points).filter(([slot_id])=>!isGoalkeeper(slot_id)).map(([slot_id,p])=>({slot_id,...p}))},'Shape copied; the two phases can now be edited independently.');return;
    }
    if(action==='undo'){
      const state=history.at(-1);if(!state)return;
      if(state.revision!==st.revision){history=[];context.announce('Other tactical edits were made. Position undo was cleared.');context.render();return;}
      history.pop();const ok=await send({action:'studio_shape',phase:state.phase,points:state.points},'Previous phase targets restored.');
      if(ok&&history.length)history.at(-1).revision=st.revision+1;return;
    }
    if(action==='add-rule'){
      const rows=context.root.querySelectorAll('.ts-rule');if(rows.length>=6){context.announce('A maximum of six plan rules is supported.',true);return;}
      const plan=['A','B','C'].find(p=>st.plans[p]);if(plan)q('#ts-plan-rules').insertAdjacentHTML('beforeend',ruleRow(st,{plan,minute:60+rows.length*5,condition:'always'}));return;
    }
    if(action==='remove-rule'){b.closest('.ts-rule').remove();return;}
    if(action==='save-rules'){
      const rules=Array.from(context.root.querySelectorAll('.ts-rule')).map(row=>({plan:row.querySelector('[data-rule-plan]').value,minute:Number(row.querySelector('[data-rule-minute]').value),condition:row.querySelector('[data-rule-condition]').value}));
      return send({action:'studio_rules',rules},'Match plan schedule saved.');
    }
  }
  function change(event){
    const e=event.target;if(context.busy())return;
    if(e.id==='ts-library-select'){librarySelection=e.value;context.render();return;}
    if(e.dataset.studioPlan)return send({action:'studio_plan',plan:e.dataset.studioPlan,entry_id:e.value||null},'Plan assignment saved.');
    if(e.hasAttribute('data-studio-opponent')){opponentChoice=e.value;redraw();return;}
    if(e.dataset.studioPosition)return send({action:'studio_position',slot_id:e.dataset.studioPosition,position:e.value,phase:context.phase},'Football position changed; compatible role and ACT updated.');
  }
  function mount(value){
    if(observer)observer.disconnect();
    pending=null;drag=null;keyboard=null;context=value;value.root.classList.remove('ts-placing','ts-dragging');
    const root=value.root;
    if(!root.dataset.studioBound){
      root.dataset.studioBound='yes';root.addEventListener('pointerdown',pointerDown);root.addEventListener('pointermove',pointerMove);root.addEventListener('pointerup',pointerUp);root.addEventListener('pointercancel',pointerCancel);
      root.addEventListener('keydown',keyDown);root.addEventListener('click',click);root.addEventListener('change',change);
    }
    const field=root.querySelector('.ts-overlay');if(field&&typeof ResizeObserver!=='undefined'){observer=new ResizeObserver(redraw);observer.observe(field);}
    root.querySelector('[data-studio="undo"]')?.toggleAttribute('disabled',!history.length||history.at(-1).revision!==value.data.studio.revision);
    redraw();
  }
  const api={marker,footer,library,positionControl,mount,refresh:redraw,coverage,coverageColor,positionOptions,restCover,outfield};
  if(typeof module!=='undefined'&&module.exports)module.exports=api;
  global.FMStudio=api;
})(typeof window!=='undefined'?window:globalThis);
