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
  });
  const neutral=Object.freeze({key:'neutral',accent:'#79bce4',glow:'121,188,228',shade:'#173447',logo:null,icon:null});
  const resolve=id=>themes[String(id)]||neutral;
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
    return image?`<img class="${className}" src="${image}" alt="" loading="lazy" draggable="false">`:
      `<span class="ci-generic-logo ${className}" aria-hidden="true">✦</span>`;
  }
  window.FMCompetitionBranding=Object.freeze({resolve,vars,badge});
})();
