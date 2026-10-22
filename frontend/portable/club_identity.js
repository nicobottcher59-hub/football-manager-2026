/* TS-UI-01A.3 — Reusable, presentation-only club identity and theme.
 * The stable simulation club ID resolves its public art and palette. No world,
 * result, calendar, or save data is modified here. */
(() => {
  'use strict';
  let catalog = Object.create(null);
  let last = null;
  const safeAsset = value => window.FMEntityAssets?.safePath?.(value) || (typeof value==='string' && /^assets\/[A-Za-z0-9/_-]+\.(?:png|webp|jpg|svg)$/.test(value)) ? value : null;
  const safeColor = value => typeof value === 'string' && /^#[0-9a-fA-F]{6}$/.test(value) ? value.toLowerCase() : null;
  const DEFAULT = Object.freeze({primary:'#1487d8',accent:'#d5ad70',secondary:'#ffffff'});
  const RGB = hex => [1,3,5].map(i=>parseInt(hex.slice(i,i+2),16));
  const HEX = arr => '#'+arr.map(n=>Math.max(0,Math.min(255,Math.round(n))).toString(16).padStart(2,'0')).join('');
  const blend = (a,b,weight) => HEX(RGB(a).map((channel,i)=>channel*(1-weight)+RGB(b)[i]*weight));
  const luminance = hex => {
    const c=RGB(hex).map(v=>{const x=v/255;return x<=.04045?x/12.92:((x+.055)/1.055)**2.4;});
    return .2126*c[0]+.7152*c[1]+.0722*c[2];
  };
  const fallback = (id,name) => ({id,display_name:name || id || 'Club',short_name:name || id || 'Club',
    crest:null,hero_image:null,founded:null,stadium:null,location:null,
    primary_color:DEFAULT.primary,secondary_color:DEFAULT.secondary,accent_color:DEFAULT.accent,visual_only:false});

  function resolve(id,name) {
    // Neither the catalog nor the supplied ID is ever trusted as executable CSS.
    const original=Object.hasOwn(catalog,String(id)) ? catalog[String(id)] : null;
    const imported=window.FMEntityAssets?.getClub?.(id);
    const data={...(original && typeof original==='object' && !Array.isArray(original) ? original : {}),
                ...(imported||{})};
    return {...fallback(id,name),...data,id,
      display_name:String(data.display_name || name || id || 'Club'),
      short_name:String(data.short_name || data.display_name || name || id || 'Club'),
      crest:safeAsset(data.crest),hero_image:safeAsset(data.hero_image),
      medical_image:safeAsset(data.medical_image),kit_image:safeAsset(data.kit_image),
      away_kit_image:safeAsset(data.away_kit_image),goalkeeper_kit_image:safeAsset(data.goalkeeper_kit_image),
      primary_color:safeColor(data.primary_color)||DEFAULT.primary,
      secondary_color:safeColor(data.secondary_color)||DEFAULT.secondary,
      accent_color:safeColor(data.accent_color)||DEFAULT.accent};
  }

  function theme(id,name) {
    const item=resolve(id,name);
    const primary=item.primary_color;
    // Dark club colours are brightened until icon and border accents are visible.
    // A club with white/black colours is still rendered over the common dark base.
    const highlight=luminance(primary)<.11 ? blend(primary,'#ffffff',.36) : blend(primary,'#ffffff',.13);
    return Object.freeze({id:item.id,primary,secondary:item.secondary_color,
      accent:item.accent_color,highlight,
      rgb:RGB(primary).join(','),
      highlightRgb:RGB(highlight).join(','),
      soft:blend(primary,'#122131',.78),
      border:blend(primary,'#516778',.51)});
  }

  // Scoped team colours for visiting players in Scout/Transfer profiles.
  // Player-club colours MUST NOT replace the manager-club theme in navigation.
  const crestPalette = new Map();
  const selectColour = async path => {
    if (crestPalette.has(path)) return crestPalette.get(path);
    const result = (async () => {
      try {
        const resource = window.FMEntityAssets?.url?.(path) || '/portable/' + path;
        const picture = new Image();
        picture.decoding = 'async';
        picture.src = resource;
        await picture.decode();
        const canvas = document.createElement('canvas');
        canvas.width = canvas.height = 48;
        const ctx = canvas.getContext('2d', {willReadFrequently:true});
        if (!ctx) return null;
        ctx.clearRect(0,0,48,48);
        ctx.drawImage(picture,0,0,48,48);
        const pixels=ctx.getImageData(0,0,48,48).data;
        const groups=new Map();
        for(let i=0;i<pixels.length;i+=4){
          if(pixels[i+3]<170)continue;
          const r=pixels[i],g=pixels[i+1],b=pixels[i+2];
          const max=Math.max(r,g,b),min=Math.min(r,g,b),delta=max-min;
          if(max<48||max>247||delta<36||delta/max<.24)continue;
          let hue=0;
          if(max===r)hue=(g-b)/delta;
          else if(max===g)hue=2+(b-r)/delta;
          else hue=4+(r-g)/delta;
          hue=(hue*60+360)%360;
          const key=Math.floor(hue/24);
          const weight=(delta/max)**1.35;
          const cur=groups.get(key)||{score:0,r:0,g:0,b:0};
          cur.score+=weight;cur.r+=r*weight;cur.g+=g*weight;cur.b+=b*weight;
          groups.set(key,cur);
        }
        const dominant=[...groups.values()].sort((a,b)=>b.score-a.score)[0];
        if(!dominant||dominant.score<2)return null;
        return HEX([dominant.r/dominant.score,dominant.g/dominant.score,dominant.b/dominant.score]);
      } catch(_) { return null; } // Missing or unsupported assets remain neutral.
    })();
    crestPalette.set(path,result);
    return result;
  };
  function setScopedColour(element,hex){
    if(!element||!safeColor(hex))return;
    const highlight=luminance(hex)<.11?blend(hex,'#ffffff',.36):blend(hex,'#ffffff',.13);
    element.style.setProperty('--player-club-rgb',RGB(hex).join(','));
    element.style.setProperty('--player-club-primary',hex);
    element.style.setProperty('--player-club-highlight',highlight);
    element.style.setProperty('--player-club-highlight-rgb',RGB(highlight).join(','));
  }
  function paintWithin(scope){
    if(!scope)return;
    for(const element of scope.querySelectorAll('[data-fm-club-theme]')){
      const clubId=element.dataset.fmClubTheme;
      if(!clubId)continue;
      const clubName=element.dataset.fmClubName||'';
      const item=resolve(clubId,clubName);
      const fromCatalog=Object.hasOwn(catalog,String(clubId))?catalog[String(clubId)]?.primary_color:null;
      const imported=window.FMEntityAssets?.getClub?.(clubId)?.primary_color;
      setScopedColour(element,safeColor(imported)||safeColor(fromCatalog)||DEFAULT.primary);
      if(!safeColor(imported)&&!safeColor(fromCatalog)&&item.crest){
        selectColour(item.crest).then(colour=>{
          if(colour && element.isConnected && element.dataset.fmClubTheme===clubId)
            setScopedColour(element,colour);
        });
      }
    }
  }

  function applyTheme(id,name) {
    const colors=theme(id,name);
    const root=document.documentElement;
    // All vars are allowlisted/derived from validated 6-digit HEX colours.
    root.style.setProperty('--club-primary',colors.primary);
    root.style.setProperty('--club-accent',colors.accent);
    root.style.setProperty('--ui-club-rgb',colors.rgb);
    root.style.setProperty('--ui-club-highlight-rgb',colors.highlightRgb);
    root.style.setProperty('--ui-club-highlight',colors.highlight);
    root.style.setProperty('--ui-club-soft',colors.soft);
    root.style.setProperty('--ui-club-border',colors.border);
    root.dataset.visualClubId=String(id||'');
    return colors;
  }

  function applyShell(id,name) {
    if (!id) return;
    last={id,name};
    const item=resolve(id,name);
    applyTheme(id,name);
    const identity=document.querySelector('.club-identity');
    if (!identity) return;
    identity.dataset.clubId=String(id);
    const strong=identity.querySelector('strong');
    if (strong) strong.textContent=item.display_name;
    const symbol=identity.querySelector('.tsui-top-crest, .tsui-top-placeholder, svg, img');
    if (item.crest) {
      if (!symbol || symbol.tagName.toLowerCase()!=='img') {
        const img=document.createElement('img');img.className='tsui-top-crest';img.dataset.fmAsset='optional';
        img.alt='';img.src=window.FMEntityAssets?.url(item.crest)||item.crest;
        if (symbol) symbol.replaceWith(img);else identity.prepend(img);
      } else if (symbol.getAttribute('src')!==(window.FMEntityAssets?.url(item.crest)||item.crest)) symbol.src=window.FMEntityAssets?.url(item.crest)||item.crest;
    } else if (symbol) {
      const placeholder=document.createElement('span');
      placeholder.className='tsui-top-placeholder';placeholder.setAttribute('aria-hidden','true');
      placeholder.textContent='\u26bd';symbol.replaceWith(placeholder);
    }
  }

  const ready=fetch('/portable/data/club-identities.json',{cache:'no-store'})
    .then(response=>{if(!response.ok)throw Error('Identity catalog not found');return response.json();})
    .then(async data=>{
      if(data.schema_version!==1 || !data.clubs || typeof data.clubs!=='object' || Array.isArray(data.clubs))
        throw Error('Invalid identity catalog schema');
      catalog=data.clubs;
      await window.FMEntityAssets?.ready;
      if(last)applyShell(last.id,last.name);
      window.dispatchEvent(new CustomEvent('fm-identity-ready'));
      return true;
    }).catch(error=>{console.warn('Visual identity catalog unavailable; using fallback palette',error);return false;});
  window.addEventListener('fm-assets-ready',()=>{if(last)applyShell(last.id,last.name);});
  window.FMClubIdentity=Object.freeze({resolve,theme,applyTheme,applyShell,paintWithin,ready});
})();
