/* TS-UI-08.04 — National flags for compact player identities.
 * Supports stable ISO-3166 alpha-2 codes and common imported nationality names.
 * Special constituent-nation flags are bundled locally; no external network.
 * Unknown names get a neutral marker, never a guessed national flag.
 */
(() => {
  'use strict';
  const esc = v => String(v ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const names = {
    argentina:'AR',albania:'AL',algeria:'DZ',andorra:'AD',angola:'AO',armenia:'AM',australia:'AU',austria:'AT',azerbaijan:'AZ',
    bahrain:'BH',bangladesh:'BD',belarus:'BY',belgium:'BE',benin:'BJ',bolivia:'BO',bosnia:'BA','bosnia and herzegovina':'BA',
    botswana:'BW',brazil:'BR',brasil:'BR',bulgaria:'BG',burkinafaso:'BF',cameroon:'CM',canada:'CA',chile:'CL',china:'CN',
    colombia:'CO','costa rica':'CR',croatia:'HR',cuba:'CU',cyprus:'CY',czechia:'CZ','czech republic':'CZ',denmark:'DK',
    'dominican republic':'DO',ecuador:'EC',egypt:'EG','el salvador':'SV',estonia:'EE',ethiopia:'ET',finland:'FI',france:'FR',
    gabon:'GA',gambia:'GM',georgia:'GE',germany:'DE',ghana:'GH',greece:'GR',guatemala:'GT',guinea:'GN',haiti:'HT',honduras:'HN',
    hungary:'HU',iceland:'IS',india:'IN',indonesia:'ID',iran:'IR',iraq:'IQ',ireland:'IE','republic of ireland':'IE',israel:'IL',
    italy:'IT','ivory coast':'CI','cote d ivoire':'CI',jamaica:'JM',japan:'JP',jordan:'JO',kazakhstan:'KZ',kenya:'KE',kosovo:'XK',
    latvia:'LV',lebanon:'LB',liberia:'LR',libya:'LY',lithuania:'LT',luxembourg:'LU',madagascar:'MG',malaysia:'MY',mali:'ML',
    malta:'MT',mexico:'MX',moldova:'MD',montenegro:'ME',morocco:'MA',mozambique:'MZ',namibia:'NA',nepal:'NP',
    netherlands:'NL',holland:'NL','new zealand':'NZ',nicaragua:'NI',niger:'NE',nigeria:'NG','north macedonia':'MK',norway:'NO',
    oman:'OM',pakistan:'PK',palestine:'PS',panama:'PA',paraguay:'PY',peru:'PE',philippines:'PH',poland:'PL',portugal:'PT',
    qatar:'QA',romania:'RO',russia:'RU','saudi arabia':'SA',senegal:'SN',serbia:'RS','sierra leone':'SL',singapore:'SG',
    slovakia:'SK',slovenia:'SI','south africa':'ZA','south korea':'KR',korea:'KR',spain:'ES','sri lanka':'LK',sudan:'SD',
    sweden:'SE',switzerland:'CH',syria:'SY',taiwan:'TW',tanzania:'TZ',thailand:'TH',togo:'TG',tunisia:'TN',turkey:'TR',
    turkiye:'TR',uganda:'UG',ukraine:'UA','united arab emirates':'AE','united kingdom':'GB','great britain':'GB',
    'united states':'US','united states of america':'US',usa:'US',uruguay:'UY',uzbekistan:'UZ',venezuela:'VE',vietnam:'VN',zambia:'ZM',zimbabwe:'ZW',
  };
  // England, Scotland and Wales need distinct flags, not the UK flag.
  const constituent = {england:'england',scotland:'scotland',wales:'wales'};
  const normalize = v => String(v ?? '').normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase().trim().replace(/[^a-z0-9]+/g,' ').replace(/\s+/g,' ');
  function render(nationality, className='') {
    const name = String(nationality || 'Unknown').trim();
    const normalized = normalize(name);
    const token = constituent[normalized];
    let inner;
    if (token) {
      inner = `<img src="/portable/assets/flags/${token}.svg" alt="" loading="lazy" data-fm-asset="flag">`;
    } else {
      const code = normalized === 'northern ireland' ? 'GB' : (/^[a-z]{2}$/.test(normalized) ? normalized.toUpperCase() : names[normalized]);
      inner = /^[A-Z]{2}$/.test(code || '') ? `<span class="fm-flag-emoji" aria-hidden="true">${[...code].map(c=>String.fromCodePoint(127397 + c.charCodeAt(0))).join('')}</span>`
        : '<span class="fm-flag-unavailable" aria-hidden="true">◇</span>';
    }
    return `<span class="fm-flag-only ${esc(className)}" role="img" aria-label="${esc(name)}" title="${esc(name)}">${inner}</span>`;
  }
  window.FMNationFlags = Object.freeze({render});
})();
