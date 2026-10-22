/* TS-CORE-01: optional visual-asset overlays keyed only by stable world IDs.
   Pure presentation. A missing manifest/image never changes simulation state. */
(() => {
 'use strict';
 const registry={clubs:Object.create(null),players:Object.create(null),competitions:Object.create(null)};
 const safeId = value => typeof value==='string' && value.length>0 && value.length<160 && !['__proto__','constructor','prototype'].includes(value);
 const safePath = value => typeof value==='string' && value.length<320 &&
   /^assets\/[a-zA-Z0-9_./-]+\.(?:png|jpe?g|webp|svg)$/.test(value) &&
   !value.split('/').some(p=>p==='..'||p==='.'||!p);
 const safeColor = value => typeof value==='string' && /^#[a-fA-F0-9]{6}$/.test(value);
 const safeText = value => typeof value==='string' && value.length<=160 ? value : null;
 const safe = value => String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
 function load(items,kind) {
   if(!items||typeof items!=='object'||Array.isArray(items))return;
   for(const [id,record] of Object.entries(items)){
     if(!safeId(id)||!record||((typeof record!=='object'&&typeof record!=='string')||Array.isArray(record)))continue;
     if(kind==='clubs' && (typeof record!=='object'||Array.isArray(record)))continue;
     if(kind==='players') {
       const photo=typeof record==='string'?record:record.photo;
       if(safePath(photo))registry.players[id]={photo};
       continue;
     }
     if(kind==='competitions'){
       const logo=typeof record==='string'?record:record.logo;
       if(safePath(logo))registry.competitions[id]={logo};
       continue;
     }
     const fields={};
     for(const k of ['crest','hero_image','medical_image','kit_image','away_kit_image','goalkeeper_kit_image'])
       if(safePath(record[k]))fields[k]=record[k];
     for(const k of ['display_name','short_name'])if(safeText(record[k]))fields[k]=record[k];
     for(const k of ['primary_color','secondary_color','accent_color'])if(safeColor(record[k]))fields[k]=record[k];
     registry.clubs[id]=fields;
   }
 }
 const getClub=id=>safeId(String(id??'')) ? registry.clubs[String(id)]||null : null;
 const getPhoto=id=>registry.players[String(id??'')]?.photo||null;
 const getCompetition=id=>registry.competitions[String(id??'')]?.logo||null;
 const getKit=(id,kind='home')=>{
   const rec=getClub(id);return rec?.[kind==='away'?'away_kit_image':kind==='goalkeeper'?'goalkeeper_kit_image':'kit_image']||null;
 };
 // Paths are intentionally relative to /portable/ for every iframe and page.
 const url=path=>safePath(path)?'/portable/'+path:null;
 function image(path,klass='',alt=''){
   if(!safePath(path))return '';
   return `<img data-fm-asset="optional" class="${safe(klass)}" src="${safe(url(path))}" alt="${safe(alt)}" loading="lazy" decoding="async">`;
 }
 // Broken optional photos keep the illustrated portrait underneath; missing
 // logos/crests use neutral symbols without borrowing another club's image.
 document.addEventListener('error',event=>{
   const element=event.target;
   if(!(element instanceof HTMLImageElement)||!element.hasAttribute('data-fm-asset'))return;
   if(element.classList.contains('fm-photo-real'))element.remove();
   else{
     const fallback=document.createElement('span');fallback.className='fm-asset-fallback';fallback.textContent='⚽';
     fallback.setAttribute('aria-hidden','true');element.replaceWith(fallback);
   }
 },true);
 const ready=fetch('/portable/data/entity-assets.json',{cache:'no-store'})
   .then(r=>r.ok?r.json():null).then(value=>{
     if(value?.schema_version!==1)return false;
     for(const kind of Object.keys(registry))load(value[kind],kind);
     window.dispatchEvent(new CustomEvent('fm-assets-ready'));
     return true;
   }).catch(()=>false);
 window.FMEntityAssets=Object.freeze({getClub,getPhoto,getCompetition,getKit,url,image,safePath,ready});
})();
