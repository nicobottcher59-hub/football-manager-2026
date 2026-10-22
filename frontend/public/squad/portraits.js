/* UI-3.1: deterministic illustrated PLACEHOLDER player portraits.
 * Portraits are associated with stable player IDs, not with roles or positions.
 * They do not claim to represent real people; future licensed/imported images can
 * replace this presentation service without changing the Python game model. */
(() => {
  'use strict';
  const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  function hash(value) {
    let h = 2166136261;
    for (const c of String(value ?? 'unknown')) { h ^= c.charCodeAt(0); h = Math.imul(h, 16777619); }
    return h >>> 0;
  }
  const skins = ['#f3ceac','#e5b58b','#b87955','#d99e75','#a86f51','#f2d4b6','#c78c68','#8d6048'];
  const hairs = ['#1d1b1d','#29201c','#423027','#6b4730','#181b22','#302424','#5c371f','#252d32'];
  const shirts = ['#2677be','#286fba','#1d65b1','#2b86ce'];
  function portrait(player, classes = '') {
    const key = player?.id || player?.name || 'unknown';
    const h = hash(key), skin = skins[h % skins.length], hair = hairs[(h >>> 4) % hairs.length];
    const keeper = ['GK'].includes(player?.primary_position || player?.position);
    const clubId=player?.club_id||player?.team_id||player?.clubId;
    const identity=clubId?window.FMClubIdentity?.resolve?.(clubId,player?.club):null;
    const themed=identity?.primary_color||document.documentElement.style.getPropertyValue('--club-primary').trim();
    const kit = keeper ? '#e7aa43' : /^#[0-9a-fA-F]{6}$/.test(themed) ? themed : shirts[(h >>> 7) % shirts.length];
    const side = (h % 7) - 3, style = (h >>> 9) % 6, beard = (h >>> 12) % 4;
    const fringe = [
      'M18 35Q15 9 43 11Q70 11 72 35Q63 28 56 24Q40 33 18 35Z',
      'M20 34Q14 16 31 14Q54 6 70 27L68 35Q54 20 42 25Q28 31 20 34Z',
      'M19 35Q12 15 37 12Q67 8 71 32L64 31Q56 24 49 25Q32 32 19 35Z',
      'M20 35Q11 21 24 14Q34 9 41 15Q51 7 62 17Q73 17 70 37L62 30Q49 30 41 25Q29 33 20 35Z',
      'M22 33Q19 17 34 16Q53 12 67 22L67 33Q51 26 43 27Q29 30 22 33Z',
      'M20 35Q14 19 30 12Q58 3 72 30L68 38Q63 22 55 23Q43 24 20 35Z',
    ][style];
    const beardMarkup = beard===0 ? '' : `<path d="M30 63Q36 ${68+beard*2} 45 69Q54 ${68+beard*2} 61 63Q59 76 45 78Q31 76 30 63Z" fill="${hair}" opacity="${beard===1?'.21':'.62'}"/><path d="M38 63Q45 60 52 63" stroke="${hair}" stroke-width="${beard===1?'1.5':'3'}" fill="none" opacity=".7"/>`;
    const imported=window.FMEntityAssets?.getPhoto?.(player?.id);
    return `<span class="fm-face ${esc(classes)}" role="img" aria-label="Player portrait: ${esc(player?.name || 'Player')}">
      ${imported?`<img class="fm-photo-real" data-fm-asset="optional" src="${esc(window.FMEntityAssets.url(imported))}" alt="" loading="lazy" decoding="async">`:''}
      <svg viewBox="0 0 90 104" aria-hidden="true" focusable="false" xmlns="http://www.w3.org/2000/svg">
        <rect width="90" height="104" rx="7" fill="#123555"/><path d="M0 0H90L57 104H0Z" fill="#205c82" opacity=".46"/><path d="M4 95L86 12" stroke="#67dbef" stroke-width="1.6" opacity=".13"/>
        <path d="M3 104Q4 84 22 79L36 76H54L70 80Q87 84 87 104Z" fill="${kit}"/><path d="M6 102Q11 88 28 84L22 104ZM84 102Q79 88 62 84L68 104Z" fill="#092b55" opacity=".32"/>
        <path d="M33 78Q45 93 57 78" stroke="#eaf8ff" stroke-width="2" fill="none" opacity=".5"/>
        <path d="M37 66V81Q45 89 53 81V66Z" fill="${skin}"/><path d="M39 71H51V78Q45 81 39 78Z" fill="#46231b" opacity=".13"/>
        <ellipse cx="19" cy="50" rx="5" ry="8" fill="${skin}"/><ellipse cx="71" cy="50" rx="5" ry="8" fill="${skin}"/>
        <path d="M19 39Q19 23 31 19Q42 14 55 18Q70 24 71 42L68 58Q62 75 45 77Q28 75 22 58Z" fill="${skin}"/>
        <path d="M46 19Q69 25 66 50Q67 66 58 70Q70 58 71 42L69 28Z" fill="#442b24" opacity=".08"/>
        <path d="${fringe}" fill="${hair}"/><path d="M20 34Q16 36 18 50L22 56L24 35ZM70 35Q74 38 72 52L68 56L66 35Z" fill="${hair}"/>
        <path d="M29 ${44+side*.3}Q36 41 40 44M50 44Q57 41 64 ${44-side*.3}" stroke="${hair}" stroke-width="3" stroke-linecap="round" fill="none"/>
        <ellipse cx="34" cy="50" rx="3" ry="2.1" fill="#182329"/><ellipse cx="56" cy="50" rx="3" ry="2.1" fill="#182329"/>
        <path d="M45 49L42 59Q45 61 48 59" stroke="#8b5942" stroke-width="1.5" fill="none" stroke-linecap="round"/>
        ${beardMarkup}<path d="M38 65Q45 68 52 65" stroke="#6e453a" stroke-width="1.9" fill="none" stroke-linecap="round"/>
        <path d="M22 93Q45 99 68 93" stroke="#9cddfc" stroke-width="1" opacity=".35" fill="none"/>
      </svg></span>`;
  }
  function nation(nationality, extraClass = '') {
    const name = String(nationality || 'Unknown');
    const known = {England:'england', Scotland:'scotland', Wales:'wales', Brazil:'brazil', France:'france', Spain:'spain', Argentina:'argentina', Germany:'germany', Italy:'italy'};
    const flags = {brazil:'🇧🇷',france:'🇫🇷',spain:'🇪🇸',argentina:'🇦🇷',germany:'🇩🇪',italy:'🇮🇹',scotland:'🏴',wales:'🏴'};
    const code = known[name.toLowerCase().replace(/^./,c=>c.toUpperCase())] || known[name] || 'other';
    return `<span class="fm-nation ${esc(extraClass)}"><span class="fm-country-icon ${esc(code)}" aria-hidden="true">${flags[code]||''}</span>${esc(name)}</span>`;
  }
  window.FMPortraits = Object.freeze({portrait, nation, hash});
})();
