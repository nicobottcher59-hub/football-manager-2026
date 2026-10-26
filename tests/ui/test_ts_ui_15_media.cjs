'use strict';
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const path=require('node:path');
const root=path.resolve(__dirname,'../../frontend/portable');
let portrait=null;
const context={window:{FMEntityAssets:{getPhoto:id=>id==='registered-player'?portrait:null,
  safePath:p=>typeof p==='string'&&/^assets\/[\w./-]+\.(png|webp)$/.test(p),
  url:p=>'/portable/'+p}},console};
vm.createContext(context);
vm.runInContext(fs.readFileSync(path.join(root,'news_media.js'),'utf8'),context);
const media=context.window.FMNewsMedia;
assert.equal(Object.keys(media.library).length,4);
for(const category of ['result','title','transfer','loan','award','training','press','medical','board']){
  const pools=media.imagesFor(category);
  assert.ok(pools.length>=3,category+' lacks variation');
  const s={id:category+'-id-123',category};
  assert.equal(media.choice(s),media.choice(s),'selection must be stable');
  assert.ok(pools.includes(media.choice(s)),'choice must be from category');
  assert.match(media.markup(s),/nr-media-scene/);
}
const p={id:'transfer:001',category:'transfer',player_id:'registered-player'};
assert.equal(media.playerPhoto(p),null,'no invented player photo');
portrait='assets/players/registered-player.png';
assert.equal(media.playerPhoto(p),'/portable/assets/players/registered-player.png');
assert.match(media.markup(p),/nr-media-player/);
assert.doesNotMatch(media.markup({...p,player_id:'different-player'}),/nr-media-player/);
portrait='../unsafe.png';assert.equal(media.playerPhoto(p),null,'reject invalid photo paths');
console.log('PASS TS-UI-15 neutral pool, deterministic selection, real player photo precedence');
