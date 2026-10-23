/* TS-FIX-02: deterministic money/schedule helpers shared by the live UI and tests. */
(() => {
  'use strict';
  const amount = raw => {
    const text = String(raw ?? '').trim().replace(/^\u00a3\s*/, '').replace(/\s/g, '');
    if (!/^\d+$/.test(text) && !/^\d{1,3}(,\d{3})+$/.test(text) && !/^\d{1,3}(\.\d{3})+$/.test(text)) {
      throw new Error('Enter whole pounds, with optional thousands separators (for example 1,500,000).');
    }
    const value = Number(text.replace(/[,.]/g, ''));
    if (!Number.isSafeInteger(value) || value < 0 || value > 500000000) {
      throw new Error('Enter an amount from \u00a30 to the technical limit of \u00a3500,000,000.');
    }
    return value;
  };
  const format = value => Number(value || 0).toLocaleString('en-GB', {maximumFractionDigits: 0});
  const plusMonths = (iso, months) => {
    const [y, m, day] = iso.split('-').map(Number);
    const first = new Date(Date.UTC(y, m - 1 + months, 1));
    const end = new Date(Date.UTC(first.getUTCFullYear(), first.getUTCMonth() + 1, 0)).getUTCDate();
    first.setUTCDate(Math.min(day, end));
    return first.toISOString().slice(0, 10);
  };
  const schedule = (total, count, interval, date) => {
    if (!total) return [];
    if (![2, 4, 6].includes(count) || ![6, 12, 18].includes(interval) || !Number.isSafeInteger(total) || total < count) {
      throw new Error('Choose 2, 4 or 6 payments, every 6, 12 or 18 months.');
    }
    const each = Math.floor(total / count), remainder = total % count;
    return Array.from({length: count}, (_, i) => ({number: i + 1,
      months: (i + 1) * interval, due_on: plusMonths(date, (i + 1) * interval),
      amount_gbp: each + (i === count - 1 ? remainder : 0)}));
  };
  const api = Object.freeze({amount, format, plusMonths, schedule});
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  if (typeof window !== 'undefined') window.FMTransferPayments = api;
})();
