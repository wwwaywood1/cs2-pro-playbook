// Actual React markup checks without a browser: node web/e2e/render_view_cones.cjs
const fs = require('node:fs');
const path = require('node:path');
const os = require('node:os');
const esbuild = require('esbuild');
const components = path.resolve(__dirname, '../src/components');
const temporary = fs.mkdtempSync(path.join(os.tmpdir(), 'view-cones-render-'));
const source = fs.readFileSync(path.join(components, 'RoundReplay.tsx'), 'utf8')
  .replace('const [time, setTime] = useState(0);', 'const [time, setTime] = useState((globalThis as any).testTime);');
const checks = `
import { renderToStaticMarkup } from 'react-dom/server';
import assert from 'node:assert/strict';
const fixture: ReplayRound = {
  demo_id: 'test', round_num: 1, map: 'de_mirage', duration: 2,
  teams: {T: 'T', CT: 'CT'}, winner: 'T',
  players: [{name: 'T', side: 'T', team: 'T'}, {name: 'CT', side: 'CT', team: 'CT'}],
  frames: [[[800,300],[600,400]], [[790,310],[600,400]], [[780,320],null]],
  yaw: [[350,90],[10,null],[30,null]],
  events: [{t: 2, kind: 'kill', by: 0, victim: 1, at: [600,400], weapon: 'ak47'}], wp_t: [],
};
function markup(at: number, reduced: boolean, replay = fixture) {
  Object.assign(globalThis, {testTime: at, window: {matchMedia: () => ({matches: reduced})}});
  return renderToStaticMarkup(<ReplayViewer replay={replay} />);
}
const count = (html: string, cls: string) => (html.match(new RegExp('class="'+cls+'"','g')) || []).length;
for (const reduced of [false, true]) {
  let html = markup(0, reduced);
  assert.equal(count(html, 'replay-view-cone'), 2);
  assert.ok(html.includes('rotate(350)') && html.includes('rotate(90)'));
  assert.ok(html.includes('fill="#efad55" opacity="0.34"') && html.includes('fill="#62b5ff" opacity="0.34"'));
  assert.ok(html.indexOf('replay-view-cones') < html.indexOf('replay-player-marker'));
  const wedge = html.match(/class="replay-view-cone" d="M 0 0 L ([\\d.e+-]+) ([\\d.e+-]+)/)!;
  assert.ok(Math.abs(Math.hypot(Number(wedge[1]), Number(wedge[2])) - 30) < .001);
  assert.ok(Math.abs(Math.atan2(-Number(wedge[2]), Number(wedge[1])) * 180 / Math.PI - 20) < .001);
  html = markup(.5, reduced);
  assert.ok(html.includes('rotate('+(reduced ? 350 : 0)+')'));
  assert.equal(count(markup(1, reduced), 'replay-view-cone'), 1);
  html = markup(2, reduced);
  assert.equal(count(html, 'replay-view-cone'), 1);
  assert.equal(count(html, 'replay-player'), 1);
  assert.equal(count(markup(0, reduced, {...fixture, yaw: undefined}), 'replay-view-cone'), 0);
}
console.log('PASS: 22 React view-cone assertions (geometry, sides, layering, motion, dead/unknown, legacy).');
`;
try {
  const bundle = path.join(temporary, 'check.cjs');
  esbuild.buildSync({ stdin: {contents: source + checks, loader: 'tsx', resolveDir: components},
    bundle: true, jsx: 'automatic', platform: 'node', format: 'cjs', outfile: bundle,
    loader: {'.css': 'empty'}, define: {'import.meta.env.BASE_URL': '"/"', 'process.env.NODE_ENV': '"production"'} });
  require(bundle);
} finally {
  fs.rmSync(temporary, {recursive: true, force: true});
}
