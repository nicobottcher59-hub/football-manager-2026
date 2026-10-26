/* TS-UI-15: reusable neutral newsroom media by event category.
 * Never assign a stock portrait to a named player. A player's photo comes only
 * from the persistent, ID-keyed FMEntityAssets player registry. */
(() => {
  'use strict';
  const prefix = '/portable/assets/news/';
  const library = Object.freeze({
    stadium: ['stadium-floodlights-01.webp','stadium-crowd-02.webp','stadium-night-03.webp'],
    training: ['training-pitch-01.webp','training-session-02.webp'],
    press: ['press-scrum-01.webp','press-conference-02.webp','press-interview-03.webp'],
    board: ['board-signing-01.webp','board-review-02.webp','board-agreement-03.webp']
  });
  const categoryPools = Object.freeze({
    result: ['stadium','training'], title: ['stadium'], award: ['stadium','press'],
    transfer: ['board','press'], loan: ['board','training'],
    medical: ['training'], training: ['training'], academy: ['training'],
    press: ['press'], manager: ['press'], board: ['board'], finance: ['board'],
    fixture: ['stadium'], match: ['stadium'], world: ['stadium','press']
  });
  const asset = (kind, filename) => kind==='built-in' ? '/portable/assets/'+filename : prefix+filename;
  const additional = Object.freeze({
    training: ['/portable/assets/training/training-session-dusk.jpg','/portable/assets/youth/academy-training-ground.webp'],
    press: ['/portable/assets/staff/football-analysis-room.webp'],
    board: ['/portable/assets/finances/finance-operations.webp'],
    medical: ['/portable/assets/medical/medical-suite-generic.webp'],
    stadium: ['/portable/assets/competitions/competition-centre-hero.webp'],
    team: ['/portable/assets/dressing-room/locker-room-team-talk.webp']
  });
  const safe = value => String(value??'').replace(/[&<>"']/g, c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  function hash(value) {
    let valueHash=2166136261;
    for(const character of String(value??''))valueHash=Math.imul(valueHash ^ character.charCodeAt(0),16777619);
    return valueHash >>> 0;
  }
  function imagesFor(category) {
    const groups = categoryPools[category] || ['stadium','press','training','board'];
    const all = groups.flatMap(group => [...library[group].map(filename=>asset('news',filename)), ...(additional[group]||[])]);
    if(category==='medical')all.unshift(...additional.medical);
    return all;
  }
  const assignments=new Map();
  function choice(story) {
    const id=String(story?.id||'unknown'), category=String(story?.category||'world');
    if(assignments.has(id))return assignments.get(id);
    const choices=imagesFor(category);
    const image=choices[hash(id+'|'+category)%choices.length];
    assignments.set(id,image);
    return image;
  }
  // Avoid using the same illustrative scene on neighbouring headlines. The
  // choice is fixed for the story ID during this session, including dialogs.
  function assignSequence(stories) {
    const recent=[];
    for(const story of (stories||[])){
      const id=String(story?.id||'unknown');
      const choices=imagesFor(String(story?.category||'world'));
      if(!assignments.has(id)){
        const start=hash(id+'|'+story.category)%choices.length;
        let image=choices[start];
        for(let offset=0;offset<choices.length;offset++){
          const trial=choices[(start+offset)%choices.length];
          if(!recent.slice(-3).includes(trial)){image=trial;break;}
        }
        assignments.set(id,image);
      }
      recent.push(assignments.get(id));
    }
  }
  // Photo identity is strictly a registered player ID. No name matching and
  // no AI-generated lookalikes of named players, staff or club officials.
  function playerPhoto(story) {
    if(!story?.player_id)return null;
    const file=window.FMEntityAssets?.getPhoto?.(story.player_id);
    return file && window.FMEntityAssets?.safePath?.(file)
      ? window.FMEntityAssets.url(file) : null;
  }
  function markup(story, className='') {
    const scene=choice(story), photo=playerPhoto(story);
    const cls=String(className).replace(/[^a-zA-Z0-9_ -]/g,'');
    return `<span class="nr-media ${cls}${photo?' nr-has-player':''}" aria-hidden="true">
      <img class="nr-media-scene" src="${safe(scene)}" alt="" loading="lazy" decoding="async">
      ${photo?`<img class="nr-media-player fm-photo-real" data-fm-asset="optional" src="${safe(photo)}" alt="" loading="lazy" decoding="async">`:''}
    </span>`;
  }
  window.FMNewsMedia = Object.freeze({choice,playerPhoto,markup,imagesFor,assignSequence,library});
})();
