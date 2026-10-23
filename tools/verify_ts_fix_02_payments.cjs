/* Run with node. No packages or browser are required. */
'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs'), vm = require('node:vm'), path = require('node:path');
const context = {module:{exports:{}}};
vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../frontend/portable/transfer_payments.js'),'utf8'),context);
const h = context.module.exports;
let checks = 0;
function test(name, fn) { fn(); checks++; console.log('PASS ' + name); }
for (const [raw,want] of [['0',0],['1234567',1234567],['1,234,567',1234567],['1.234.567',1234567],['\u00a3 1,000',1000],['500,000,000',500000000]]) {
  test('whole pounds: ' + raw, () => assert.equal(h.amount(raw),want));
}
for (const raw of ['-1','1.5','1,50','abc','','500000001','Infinity','1e6','1,2,3']) {
  test('invalid amount: ' + raw, () => assert.throws(() => h.amount(raw)));
}
for (const count of [2,4,6]) for (const interval of [6,12,18]) {
  test(`${count} payments / ${interval} months`, () => {
    const rows=h.schedule(1000003,count,interval,'2026-08-31');
    assert.equal(rows.length,count);
    assert.equal(rows.reduce((n,r)=>n+r.amount_gbp,0),1000003);
    assert.equal(rows[0].months,interval);
    assert.equal(rows.at(-1).months,count*interval);
    assert.equal(rows.at(-1).due_on,h.plusMonths('2026-08-31',count*interval));
  });
}
test('calendar month clamp',()=>assert.equal(h.plusMonths('2026-08-31',6),'2027-02-28'));
test('leap day preserved when valid',()=>assert.equal(h.plusMonths('2027-08-31',6),'2028-02-29'));
test('leap day to ordinary February',()=>assert.equal(h.plusMonths('2028-02-29',12),'2029-02-28'));
test('four yearly payments are not at 6/18/30/42',()=>assert.equal(JSON.stringify(h.schedule(6000000,4,12,'2026-08-21').map(r=>r.months)),'[12,24,36,48]'));
test('zero total produces no dated obligation',()=>assert.equal(h.schedule(0,4,6,'2026-08-21').length,0));
test('fractional schedules are not accepted',()=>assert.throws(()=>h.schedule(5,6,6,'2026-08-21')));
console.log(JSON.stringify({checks,failed:0}));
