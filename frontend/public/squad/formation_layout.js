/* TS-19.1.1: visual-only spacing for fixed-size lineup cards.
 * Input coordinates are still provided by the existing tactical diagram model.
 * No slot, role, match-engine or tactical data is changed by this module.
 */
(function (global) {
  'use strict';
  const clamp = (v, min, max) => Math.max(min, Math.min(max, v));

  function arrange(points, slots, options) {
    const width = Number(options.width);
    const height = Number(options.height);
    const cardWidth = Number(options.cardWidth);
    const cardHeight = Number(options.cardHeight);
    const gap = Number(options.gap ?? 7);
    const margin = Number(options.margin ?? 7);
    if (![width, height, cardWidth, cardHeight, gap, margin].every(Number.isFinite) ||
        width <= 0 || height <= 0 || cardWidth <= 0 || cardHeight <= 0) {
      throw new TypeError('Positive pitch and card dimensions are required');
    }
    const minX = cardWidth / 2 + margin;
    const maxX = width - minX;
    const minY = cardHeight / 2 + margin;
    const maxY = height - minY;
    // Smaller containers cannot physically fit five fixed-size cards abreast.
    // The CSS pitch minimum width/height is responsible for that constraint.
    if (maxX <= minX || maxY <= minY) throw new RangeError('Pitch is smaller than the card');
    const nodes = slots.map((slot, order) => {
      const point = points[slot.slot_id];
      if (!point || !Number.isFinite(point.x) || !Number.isFinite(point.y)) {
        throw new TypeError('Missing or invalid tactical position: ' + slot.slot_id);
      }
      return {id: slot.slot_id, order, x: clamp(point.x * width / 100, minX, maxX),
        y: clamp(point.y * height / 100, minY, maxY)};
    });
    // Players on the same tactical line share a row. Keeping their original
    // left-to-right order makes overlaps impossible without changing roles.
    const sorted = [...nodes].sort((a, b) => a.y - b.y || a.x - b.x || a.order - b.order);
    const rows = [];
    for (const node of sorted) {
      const candidate = rows[rows.length - 1];
      // Group near-identical vertical levels, not whole adjacent lines.
      if (candidate && Math.abs(node.y - candidate.mean) <= Math.min(42, height * .075)) {
        candidate.items.push(node);
        candidate.mean = candidate.items.reduce((sum, item) => sum + item.y, 0) / candidate.items.length;
      } else rows.push({items: [node], mean: node.y});
    }
    const verticalStep = cardHeight + gap;
    // If there is room, preserve each row's target height; otherwise distribute
    // the rows evenly without allowing a card to leave the pitch.
    const step = rows.length > 1 ? Math.min(verticalStep, (maxY - minY) / (rows.length - 1)) : 0;
    const ys = rows.map(row => clamp(row.mean, minY, maxY));
    for (let i = 1; i < ys.length; i++) ys[i] = Math.max(ys[i], ys[i - 1] + step);
    if (ys.length && ys[ys.length - 1] > maxY) {
      ys[ys.length - 1] = maxY;
      for (let i = ys.length - 2; i >= 0; i--) ys[i] = Math.min(ys[i], ys[i + 1] - step);
    }
    if (ys.length && ys[0] < minY) {
      ys[0] = minY;
      for (let i = 1; i < ys.length; i++) ys[i] = Math.max(ys[i], ys[i - 1] + step);
    }
    const out = {};
    rows.forEach((row, rowIndex) => {
      const items = [...row.items].sort((a, b) => a.x - b.x || a.order - b.order);
      const separation = Math.min(cardWidth + gap, (maxX - minX) / Math.max(items.length - 1, 1));
      const xs = items.map(item => item.x);
      for (let i = 1; i < xs.length; i++) xs[i] = Math.max(xs[i], xs[i - 1] + separation);
      if (xs[xs.length - 1] > maxX) {
        xs[xs.length - 1] = maxX;
        for (let i = xs.length - 2; i >= 0; i--) xs[i] = Math.min(xs[i], xs[i + 1] - separation);
      }
      if (xs[0] < minX) {
        xs[0] = minX;
        for (let i = 1; i < xs.length; i++) xs[i] = Math.max(xs[i], xs[i - 1] + separation);
      }
      items.forEach((item, i) => {out[item.id] = {x: xs[i], y: ys[rowIndex]};});
    });
    // Tactical sliders can bring nominally separate lines extremely close.
    // Resolve the remaining inter-row contacts without shrinking any card or
    // altering a player's Python position/role. This pass is deterministic.
    const placed = [];
    const fixed = {};
    const minDx = cardWidth + gap;
    const minDy = cardHeight + gap;
    const ordered = [...nodes].sort((a,b)=>out[a.id].y-out[b.id].y || out[a.id].x-out[b.id].x || a.order-b.order);
    for(const node of ordered){
      const preferred=out[node.id];
      const collides=point=>placed.some(other=>Math.abs(point.x-other.x)<minDx-0.01 && Math.abs(point.y-other.y)<minDy-0.01);
      let best=preferred;
      if(collides(preferred)){
        const xOptions=[preferred.x,minX,maxX,...placed.flatMap(other=>[other.x-minDx,other.x+minDx])];
        const yOptions=[preferred.y,minY,maxY,...placed.flatMap(other=>[other.y-minDy,other.y+minDy])];
        let bestCost=Infinity;
        for(const rawX of xOptions)for(const rawY of yOptions){
          const point={x:clamp(rawX,minX,maxX),y:clamp(rawY,minY,maxY)};
          if(collides(point))continue;
          const dx=point.x-preferred.x,dy=point.y-preferred.y;
          const cost=dx*dx + dy*dy*1.2;
          if(cost<bestCost){best=point;bestCost=cost;}
        }
        if(bestCost===Infinity)throw new RangeError('Pitch cannot accommodate all fixed-size player cards');
      }
      fixed[node.id]=best;
      placed.push(best);
    }
    return fixed;
  }
  const api = Object.freeze({arrange});
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  global.FMFormationLayout = api;
})(typeof window !== 'undefined' ? window : this);
