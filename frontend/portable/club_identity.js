/* TS-UI-01A.3 — Reusable, presentation-only club identity and theme.
 * The stable simulation club ID resolves its public art and palette. No world,
 * result, calendar, or save data is modified here. */
(() => {
  'use strict';
  let catalog = Object.create(null);
  let last = null;
  const safeAsset = value => typeof value === 'string' && /^assets\/[A-Za-z0-9/_-]+\.(?:png|webp|jpg|svg)$/.test(value) ? value : null;
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
    const data=Object.hasOwn(catalog,String(id)) ? catalog[id] : null;
    if (!data || typeof data !== 'object' || Array.isArray(data)) return fallback(id,name);
    return {...fallback(id,name),...data,id,display_name:String(data.display_name || name || id),
      crest:safeAsset(data.crest),hero_image:safeAsset(data.hero_image),
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
        const img=document.createElement('img');img.className='tsui-top-crest';
        img.alt='';img.src=item.crest;
        if (symbol) symbol.replaceWith(img);else identity.prepend(img);
      } else if (symbol.getAttribute('src')!==item.crest) symbol.src=item.crest;
    } else if (symbol) {
      const placeholder=document.createElement('span');
      placeholder.className='tsui-top-placeholder';placeholder.setAttribute('aria-hidden','true');
      placeholder.textContent='\u26bd';symbol.replaceWith(placeholder);
    }
  }

  const ready=fetch('data/club-identities.json',{cache:'no-store'})
    .then(response=>{if(!response.ok)throw Error('Identity catalog not found');return response.json();})
    .then(data=>{
      if(data.schema_version!==1 || !data.clubs || typeof data.clubs!=='object' || Array.isArray(data.clubs))
        throw Error('Invalid identity catalog schema');
      catalog=data.clubs;
      if(last)applyShell(last.id,last.name);
      window.dispatchEvent(new CustomEvent('fm-identity-ready'));
      return true;
    }).catch(error=>{console.warn('Visual identity catalog unavailable; using fallback palette',error);return false;});
  window.FMClubIdentity=Object.freeze({resolve,theme,applyTheme,applyShell,ready});
})();
