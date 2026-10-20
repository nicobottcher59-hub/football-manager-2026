const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const context = {window: Object.create(null)};
vm.createContext(context);
vm.runInContext(fs.readFileSync(path.join(__dirname, '../../frontend/portable/competition_branding.js'),'utf8'),context);
const brand = context.window.FMCompetitionBranding;
const cases = {'dev-premier':'premier','carabao-cup':'carabao','fa-cup':'fa','champions-league':'champions'};
for (const [id,key] of Object.entries(cases)) {
  assert.equal(brand.resolve(id).key,key);
  assert.match(brand.vars(id),/^--ci-accent:#[0-9a-f]{6};/i);
  assert.match(brand.badge(id),/assets\/competitions\//);
}
const missing = brand.resolve(`evil');alert(1);//`);
assert.equal(missing.key,'neutral');
assert.equal(missing.logo,null);
assert.doesNotMatch(brand.vars(`evil');alert(1);//`),/evil|alert/);
assert.match(brand.badge('missing'),/ci-generic-logo/);
console.log('5 shared-branding runtime checks passed');
