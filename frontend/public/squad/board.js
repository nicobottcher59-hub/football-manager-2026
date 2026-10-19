/* Schematic positional board for UI only. FastMatchSimulator owns real match logic.
 * Browser global and CommonJS export so tests can verify both phase profiles. */
(function (global) {
  'use strict';
  const baseByPosition = {
    GK:[50,90], RB:[83,75],RCB:[61,75],CB:[50,75],LCB:[39,75],LB:[17,75],
    RWB:[85,65],LWB:[15,65],DM:[50,59],RCM:[64,49],CM:[50,49],LCM:[36,49],
    AM:[50,34],RW:[84,26],LW:[16,26],SS:[50,24],ST:[50,14]
  };
  const levels = {very_low:0,low:25,normal:50,high:75,very_high:100};
  const measure = (value, fallback=50) => value in levels ? levels[value] : fallback;
  const clamp = (n,min,max)=>Math.max(min,Math.min(max,n));
  const field = (data, group, name, fallback='normal') =>
    (data.tactics.fields.find(item=>item.group===group && item.field===name)||{}).value || fallback;
  const level = (data,group,name,def=50)=>measure(field(data,group,name),def);
  function base(slot) {
    const id = slot.slot_id;
    const p = slot.position;
    // The Python catalogue is authoritative for every named formation. Keep
    // old position-based fallback for the standalone/UI demo payload.
    if (Number.isFinite(slot.base_x) && Number.isFinite(slot.base_y)) {
      return [slot.base_x, slot.base_y];
    }
    const xy = (baseByPosition[p]||[50,50]).slice();
    if (/^(rdm|ram|rst)$/.test(id)) xy[0]=p==='ST'?61:p==='AM'?61:63;
    if (/^(ldm|lam|lst)$/.test(id)) xy[0]=p==='ST'?39:p==='AM'?39:37;
    return xy;
  }
  function lineFor(y) { return y>=67 ? 'defensive' : y>=40 ? 'midfield' : 'attacking'; }
  function place(data, phase) {
    const group=phase==='out_of_possession'?'out_of_possession':'in_possession';
    const fields=data.tactics.fields;
    const value=(name,g=group,def='normal')=>field(data,g,name,def);
    const num=(name,g=group,def=50)=>level(data,g,name,def);
    const inPossession=group==='in_possession';
    const map={};
    for(const slot of data.slots){
      let [x,y]=base(slot);
      const line=lineFor(y);
      if(slot.position !== 'GK'){
        const widthField={defensive:'defensive_line_width',midfield:'midfield_width',attacking:'attacking_line_width'}[line];
        let widthFactor = .58 + num(widthField)/100*.86;
        if(!inPossession){
          widthFactor *= 1.15-num('horizontal_compactness')/260;
          widthFactor *= 1.11-num('protect_centre')/420;
        }
        x = 50+(x-50)*widthFactor;
        const defGap=num('defense_midfield_gap');
        const attGap=num('midfield_attack_gap');
        if(line==='midfield') y+=(defGap-50)*-.12;
        if(line==='attacking') y+= (attGap-50)*-.11+(defGap-50)*-.055;
        if(inPossession){
          const forward=(num('verticality')-50)*.042 + (num('tempo')-50)*.024;
          y-=line==='attacking'?forward:line==='midfield'?forward*.65:forward*.16;
          y+=(num('patience')-50)*.018;
          y+=(num('support_closeness')-50)*(line==='midfield'? .035:-.01);
          x += (x-50)*(num('switch_play')-50)/950;
          if(line==='defensive') y+=(num('build_from_back')-50)*.039;
          if(line==='attacking') x+=(x-50)*(num('crossing_frequency')-50)/1150;
          if(slot.position==='RB'||slot.position==='LB'||slot.position==='RWB'||slot.position==='LWB'){
            x+=(x-50)*(num('overlap_frequency')-50)/450;
          }
          if(line==='midfield') y-=(num('long_shot_frequency')-50)*.033;
          if(line==='attacking') y-=(num('passing_risk')-50)*.018;
          if(line==='midfield') y-=(num('pass_speed')-50)*.018;
          if(line==='attacking') y+=(num('central_focus')-50)*.018;
          const length=value('pass_length');
          y-=(['very_short','short','mixed','long','very_long'].indexOf(length)-2)*.8;
        } else {
          const block=(num('block_height')-50)*.2;
          const lineHeight=(num('defensive_line_height')-50)*.15;
          const press=(num('pressing_intensity')-50)*.09;
          y-=(line==='defensive'?block*.45+lineHeight:line==='midfield'?block: block+press);
          y += (50-num('vertical_compactness'))*(y-50)/430;
          if(line==='defensive') y-=num('offside_trap','out_of_possession',0) || (value('offside_trap')==='on'?3:0);
          if(line==='midfield') y-= (num('defensive_aggression')-50)*.05;
          if(line==='defensive') y-=(num('protect_box')-50)*-.03;
          const marking=value('marking_style');
          if(marking==='man')x+=(x>=50?1:-1)*1.2;
          const scheme=value('pressing_scheme');
          if(scheme==='constant')y-=1.8;
          if(scheme==='trap_inside')x+=(50-x)*.06;
          if(scheme==='trap_outside')x+=(x-50)*.06;
          const force=value('force_direction');
          if(force==='inside')x+=(50-x)*.055;
          if(force==='outside')x+=(x-50)*.055;
          if(line==='attacking')y-=(num('cross_tolerance')-50)*.018;
        }
        const tLoss=value('after_loss','transition','hold_shape');
        const tWin=value('after_win','transition','hold_possession');
        if(inPossession){
          if(tWin==='counter'||tWin==='direct') y-=(line==='attacking'?3:1);
          if(tWin==='expand')x+=(x-50)*.05;
          y-= (num('transition_speed','transition')-50)*.015;
          if(line==='attacking') y-=(num('counterattack_risk','transition')-50)*.023;
        } else {
          if(tLoss==='counterpress')y-=(line==='attacking'?4:1);
          if(tLoss==='regroup')y+=line==='attacking'?2:3;
        }
        // Score-sensitive management is applied inside the live simulation.
        x=clamp(x,7,93); y=clamp(y,8,84);
      } else if(inPossession){
        y-=(num('goalkeeper_release_speed','transition')-50)*.025;
      }
      // Single-player movement instruction is drawn as a small displacement within the phase.
      const personal=slot.individual||[];
      const personalValue=(key)=>{const item=personal.find(ins=>ins.field===key);return item?item.effective:'base';};
      const pos = personalValue(inPossession?'in_possession_position':'out_of_possession_position');
      if (pos==='wide') x+=(x>=50?1:-1)*3;
      if (pos==='inside') x+=(50-x)*.25;
      if (pos==='midfield') y+=(50-y)*.22;
      if (pos==='advance'||pos==='step_up') y-=5;
      if (pos==='drop_deep'||pos==='drop') y+=5;
      if (pos==='return_to_base'&&!inPossession) {x=50+(x-50)*.94;}
      const explicit=data.studio?.anchors?.[group]?.[slot.slot_id];
      map[slot.slot_id]=explicit ? {x:explicit.x,y:explicit.y} : {x:clamp(x,5,95),y:clamp(y,5,95)};
    }
    return map;
  }
  const exports={place,base,levels};
  if(typeof module!=='undefined' && module.exports) module.exports=exports;
  global.FMTacticalBoard=exports;
})(typeof window !== 'undefined'? window : this);
