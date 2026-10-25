// Run from the repo root: node web/e2e/orbit_geometry.mjs
// Uses the actual TypeScript source, including the measured-size rounding reserve.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import ts from '../node_modules/typescript/lib/typescript.js';
const source = fs.readFileSync(new URL('../src/pages/teamsHubOrbit.ts', import.meta.url), 'utf8');
const compiled = ts.transpile(source, { module: ts.ModuleKind.ES2022 });
const { orbitLayout, orbitStats, ORBIT_CARD_SIZE, ORBIT_CORE_SIZE, orbitRate } = await import('data:text/javascript;base64,' + Buffer.from(compiled).toString('base64'));
let layouts = 0;
// Include the measured stage budgets at both requested desktop viewports.
for (const width of [900, 960, 1000, 1050, 1100, 1144, 1150, 1200, 1280, 1296]) {
  for (const height of [435, 570, 600, 670, 700]) {
    const node = { width: ORBIT_CARD_SIZE.width + 1, height: ORBIT_CARD_SIZE.height + 1 };
    const nodes = Array(7).fill(node);
    for (let degree = 0; degree < 360; degree++) {
      const { points } = orbitLayout(width, height, nodes, degree * Math.PI / 180);
      for (const [i, a] of points.entries()) {
        const aw = node.width * a.scale * 1.0, ah = node.height * a.scale * 1.0;
        assert(a.x - aw / 2 >= 9.99 && a.x + aw / 2 <= width - 9.99);
        assert(a.y - ah / 2 >= 9.99 && a.y + ah / 2 <= height - 9.99);
        assert(Math.max(Math.abs(a.x - width / 2) - (aw + ORBIT_CORE_SIZE.width) / 2,
                        Math.abs(a.y - height / 2) - (ah + ORBIT_CORE_SIZE.height) / 2) >= 9.99,
               `${width}x${height} phase ${degree}: card overlaps the centre logo/name/count`);
        for (const b of points.slice(i + 1)) {
          assert(Math.max(Math.abs(a.x - b.x) - (aw + node.width * b.scale * 1.0) / 2,
                          Math.abs(a.y - b.y) - (ah + node.height * b.scale * 1.0) / 2) >= 9.99,
                 `${width}x${height} phase ${degree}: nodes overlap or lose 10px gap`);
        }
      }
      layouts++;
    }
  }
}
// The hero is large at both desktop sizes; the fit must reserve its full bounds.
assert.deepEqual(ORBIT_CARD_SIZE, { width: 196, height: 252 });
assert.deepEqual(ORBIT_CORE_SIZE, { width: 230, height: 285 });
for (const [viewport, width, height, minimum] of [
  ['1440x900', 1296, 730, 140], ['1280x800', 1144, 630, 100],
]) {
  const { scale } = orbitLayout(width, height, Array(7).fill({ width: 197, height: 253 }));
  const rendered = ORBIT_CARD_SIZE.width * scale;
  assert(rendered >= minimum && rendered <= 196, `${viewport}: rendered width ${rendered}`);
  console.log(`PASS: ${viewport}: ${rendered.toFixed(1)}x${(252 * scale).toFixed(1)}px at middle depth, full 230x285 hero clearance`);
}
const maps = [
  { map: 'de_ancient', n_matches: 2, map_win_rate: 1 },
  { map: 'de_dust2', n_matches: 38, map_win_rate: .84 },
  { map: 'de_cache', n_matches: 8, map_win_rate: .5 },
  { map: 'de_anubis', n_matches: 19, map_win_rate: .47 },
  { map: 'de_overpass', n_matches: 100, map_win_rate: 0 },
];
assert.deepEqual(orbitStats(maps, 5), {matches: 67, best: 'de_dust2', worst: 'de_anubis'});
assert.deepEqual(orbitStats(maps, 20), {matches: 67, best: 'de_dust2', worst: undefined});
assert.deepEqual(orbitStats(maps, undefined), {matches: 67, best: undefined, worst: undefined});
assert.deepEqual(orbitStats(maps, 50), {matches: 67, best: undefined, worst: undefined});
assert.deepEqual([null, undefined, 0, .4999, .5, .5999, .6, .65, 1].map(orbitRate),
  ['neutral', 'neutral', 'weak', 'weak', 'neutral', 'neutral', 'strong', 'strong', 'strong']);
console.log(`PASS: ${layouts} orbit phases at max depth + hover scale; minimum-sample ranking and visible-pool totals`);

// Exercise the actual rAF hook with a deterministic clock and a tiny DOM adapter.
// Browser smoke remains responsible for CSS, hit-testing, focus and screenshots.
const reactShim = `export const useRef = value => globalThis.orbitFixture.ref(value);
export const useLayoutEffect = (callback, deps) => globalThis.orbitFixture.effect(callback, deps);`;
const asModule = code => 'data:text/javascript;base64,' + Buffer.from(code).toString('base64');
const engineSource = fs.readFileSync(new URL('../src/pages/OrbitalPhysicsEngine.ts', import.meta.url), 'utf8');
const engineModule = ts.transpile(engineSource, { module: ts.ModuleKind.ES2022 })
  .replace('from "react"', `from "${asModule(reactShim)}"`)
  .replace('from "./teamsHubOrbit"', `from "${asModule(compiled)}"`);
const { useOrbitalPhysicsEngine } = await import(asModule(engineModule));
const refs = [], effects = [], listeners = new Map(), raf = new Map();
let cursor = 0, time = 1, nextFrame = 0, intersection, resize;
const windowListeners = new Map();
globalThis.orbitFixture = {
  ref(value) { const i = cursor++; return refs[i] ??= { current: value }; },
  effect(callback, deps) {
    const i = cursor++, previous = effects[i];
    if (previous && deps?.every((value, j) => value === previous.deps?.[j])) return;
    previous?.cleanup?.();
    effects[i] = { deps, cleanup: callback() };
  },
};
globalThis.document = {
  hidden: false,
  addEventListener: (name, callback) => listeners.set(name, callback),
  removeEventListener: name => listeners.delete(name),
};
globalThis.window = {
  matchMedia: () => ({ matches: false, addEventListener() {}, removeEventListener() {} }),
  addEventListener: (name, callback) => windowListeners.set(name, callback),
  removeEventListener: name => windowListeners.delete(name),
};
globalThis.ResizeObserver = class {
  constructor(callback) { resize = callback; }
  observe() {}
  disconnect() {}
};
globalThis.IntersectionObserver = class {
  constructor(callback) { intersection = callback; }
  observe() {}
  disconnect() {}
};
globalThis.requestAnimationFrame = callback => { raf.set(++nextFrame, callback); return nextFrame; };
globalThis.cancelAnimationFrame = id => raf.delete(id);
const nodes = Array.from({ length: 7 }, () => ({
  offsetWidth: ORBIT_CARD_SIZE.width, offsetHeight: ORBIT_CARD_SIZE.height,
  style: { setProperty(name, value) { this[name] = value; } },
}));
const rays = { setAttribute(name, value) { this[name] = value; } };
const lines = Array.from({ length: 7 }, () => ({ setAttribute(name, value) { this[name] = Number(value); } }));
const stage = { dataset: {}, clientWidth: 1140, clientHeight: 570,
  querySelector() { return rays; }, querySelectorAll(selector) {
  return selector === '.hub-orbit-node' ? nodes : [lines[Number(selector.match(/nth-child\((\d+)\)/)[1]) - 1]];
} };
const host = { current: stage };
const render = (paused = false, reduced = false) => { cursor = 0; useOrbitalPhysicsEngine(host, paused, reduced); };
const advance = count => { for (let i = 0; i < count; i++) {
  time += 1000 / 60;
  const pending = [...raf.values()]; raf.clear(); pending.forEach(callback => callback(time));
} };
render(); advance(120);
assert(Number(stage.dataset.phase) > .2, 'rAF must rotate the ring');
render(true); advance(110);
assert.equal(stage.dataset.running, 'false', 'focus/hover must brake to rest');
const stopped = stage.dataset.phase;
advance(60); assert.equal(stage.dataset.phase, stopped);
render(); advance(60); assert.notEqual(stage.dataset.phase, stopped, 'leaving must resume');
const moving = stage.dataset.phase;
document.hidden = true; listeners.get('visibilitychange')(); advance(60);
assert.equal(stage.dataset.phase, moving, 'hidden tabs must stop scheduling rAF');
document.hidden = false; listeners.get('visibilitychange')(); advance(60);
assert.notEqual(stage.dataset.phase, moving);
intersection([{ isIntersecting: false }]);
const offscreen = stage.dataset.phase; advance(60); assert.equal(stage.dataset.phase, offscreen);
intersection([{ isIntersecting: true }]); advance(60); assert.notEqual(stage.dataset.phase, offscreen);
render(false, true); advance(60);
assert.equal(stage.dataset.phase, '0'); assert.equal(stage.dataset.running, 'false');
// A stopped/reduced orbit must refit immediately on resize, with no React render.
stage.clientWidth = 1150; stage.clientHeight = 570;
windowListeners.get('resize')();
stage.clientWidth = 1296; stage.clientHeight = 700;
resize();
const measured = nodes.map(node => ({ width: node.offsetWidth + 1, height: node.offsetHeight + 1 }));
const expected = orbitLayout(stage.clientWidth, stage.clientHeight, measured).points;
assert.equal(rays.viewBox, '0 0 1296 700');
assert(nodes.every((node, i) => Math.abs(parseFloat(node.style['--orbit-x']) - expected[i].x) < 1e-6 &&
  Math.abs(parseFloat(node.style['--orbit-y']) - expected[i].y) < 1e-6), 'static resize refits node centres');
assert(lines.every((line, i) => Math.abs(line.x2 - expected[i].x) < 1e-6 && Math.abs(line.y2 - expected[i].y) < 1e-6), 'rays follow node centres');
effects.forEach(effect => effect?.cleanup?.());
assert.equal(raf.size, 0, 'unmount must cancel the last frame');
assert.equal(windowListeners.size, 0, 'unmount must remove resize listener');
console.log('PASS: actual rAF engine rotation, damping, resume, hidden/offscreen pause, static reduced-motion resize, rays and cleanup');
