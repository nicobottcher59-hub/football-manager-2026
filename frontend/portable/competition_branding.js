/* TS-UI-01A.3: Competition identity registry.
 * Existing stable competition IDs map to reusable brand assets, never to club
 * colours. To add a tournament, register its ID, theme and images here. */
(() => {
  'use strict';
  const themes=Object.freeze({
    'dev-premier':{key:'premier',accent:'#c18bf6',glow:'193,139,246',shade:'#321347',logo:'assets/competitions/premier-league.png',icon:'assets/competitions/premier-league-icon.png'},
    'fa-cup':{key:'fa',accent:'#f46a78',glow:'244,106,120',shade:'#481d2c',logo:'assets/competitions/fa-cup.png',icon:'assets/competitions/fa-cup-icon.png'},
    'carabao-cup':{key:'carabao',accent:'#35d49d',glow:'53,212,157',shade:'#093b32',logo:'assets/competitions/carabao-cup.png',icon:'assets/competitions/carabao-cup.png'},
    'champions-league':{key:'champions',accent:'#638eff',glow:'99,142,255',shade:'#122d70',logo:'assets/competitions/champions-league.png',icon:'assets/competitions/champions-league-icon.png'},
    // The remaining real Python-world competition IDs: independent accents,
    // no invented sponsor logos. An ID-keyed imported PNG replaces the fallback.
    'dev-championship':{key:'championship',accent:'#77b8ed',glow:'119,184,237',shade:'#14344e',logo:null,icon:null},
    'dev-league-one':{key:'league-one',accent:'#e8ab70',glow:'232,171,112',shade:'#3d2b22',logo:null,icon:null},
    'dev-league-two':{key:'league-two',accent:'#76d4b7',glow:'118,212,183',shade:'#173d37',logo:null,icon:null},
    'efl-trophy':{key:'efl-trophy',accent:'#dd90cd',glow:'221,144,205',shade:'#44243d',logo:null,icon:null},
    'europa-league':{key:'europa',accent:'#f4a455',glow:'244,164,85',shade:'#46301f',logo:null,icon:null},
    'conference-league':{key:'conference',accent:'#8ad97b',glow:'138,217,123',shade:'#203f2c',logo:null,icon:null},
  });
  const neutral=Object.freeze({key:'neutral',accent:'#79bce4',glow:'121,188,228',shade:'#173447',logo:null,icon:null});
  const validHex=value=>typeof value==='string' && /^#[0-9a-fA-F]{6}$/.test(value);
  const rgb=hex=>[1,3,5].map(i=>parseInt(hex.slice(i,i+2),16));
  const darkShade=hex=>'#'+rgb(hex).map((n,i)=>Math.round(n*.25+[7,27,46][i]*.75).toString(16).padStart(2,'0')).join('');
  const resolve=id=>{
    const base=themes[String(id)]||neutral;
    const importedTheme=window.FMEntityAssets?.getCompetitionTheme?.(id);
    const importedLogo=importedTheme?.logo||window.FMEntityAssets?.getCompetition?.(id);
    const accent=validHex(importedTheme?.primary_color)?importedTheme.primary_color:base.accent;
    const shade=validHex(importedTheme?.secondary_color)?importedTheme.secondary_color:
      accent!==base.accent?darkShade(accent):base.shade;
    return {...base,accent,glow:rgb(accent).join(','),shade,
      logo:importedLogo||base.logo,icon:importedLogo||base.icon};
  };
  function vars(id) {
    const t=resolve(id);
    return `--ci-accent:${t.accent};--ci-rgb:${t.glow};--ci-shade:${t.shade};--ci-logo:${t.logo?`url('${t.logo}')`:'none'};--ci-symbol:${t.icon?`url('${t.icon}')`:'none'};`;
  }
  function badge(id,className='') {
    const t=resolve(id);
    // Compact views deliberately use a symbol-only PNG to avoid shrinking
    // a long competition wordmark into a 20px-high chip.
    const useFull=className.includes('ci-full-logo');
    const image=useFull?t.logo:t.icon;
    return image?`<img data-fm-asset="optional" class="${className}" src="${window.FMEntityAssets?.url(image)||image}" alt="" loading="lazy" draggable="false">`:
      `<span class="ci-generic-logo ${className}" aria-hidden="true">✦</span>`;
  }
  window.FMCompetitionBranding=Object.freeze({resolve,vars,badge});
})();
