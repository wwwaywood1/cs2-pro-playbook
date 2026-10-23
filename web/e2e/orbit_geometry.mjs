// Run from the repo root: node web/e2e/orbit_geometry.mjs
// Uses the actual TypeScript source, including the measured-size rounding reserve.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import ts from '../node_modules/typescript/lib/typescript.js';
const source = fs.readFileSync(new URL('../src/pages/teamsHubOrbit.ts', import.meta.url), 'utf8');
const compiled = ts.transpile(source, { module: ts.ModuleKind.ES2022 });
const { orbitLayout, orbitStats, ORBIT_CARD_SIZE } = await import('data:text/javascript;base64,' + Buffer.from(compiled).toString('base64'));
let layouts = 0;
for (const width of [900, 960, 1000, 1050, 1100, 1150, 1200, 1280]) {
  for (const requestedHeight of [435, 570, 670]) {
    const node = { width: ORBIT_CARD_SIZE.width + 1, height: ORBIT_CARD_SIZE.height + 1 };
    const nodes = Array(7).fill(node);
    const min = orbitLayout(width, requestedHeight, nodes).minHeight;
    const height = Math.max(requestedHeight, min);
    const { points } = orbitLayout(width, height, nodes);
    for (const [i, a] of points.entries()) {
      assert(a.x - node.width * .54 >= 15.99 && a.x + node.width * .54 <= width - 15.99);
      assert(a.y - node.height * .54 >= 15.99 && a.y + node.height * .54 <= height - 15.99);
      for (const b of points.slice(i + 1)) {
        assert(Math.max(Math.abs(a.x - b.x) - node.width * 1.08,
                        Math.abs(a.y - b.y) - node.height * 1.08) >= 15.99,
               `${width}x${height} nodes overlap or lose the 16px hover gap`);
      }
    }
    if (width >= 1000 && requestedHeight >= 570) assert(height === requestedHeight, 'desktop orbit must not expand past the viewport budget');
    layouts++;
  }
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
console.log(`PASS: ${layouts} orbit layouts at max hover scale; minimum-sample ranking and visible-pool totals`);
