// Static rendering regression checks for new and legacy lab exports.
// Run from the repo root: node web/e2e/lab_render.mjs
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';
import { createRequire } from 'node:module';
import ts from '../node_modules/typescript/lib/typescript.js';
process.env.NODE_ENV = 'production';
const require = createRequire(new URL('../package.json', import.meta.url));
const React = require('react');
const { renderToStaticMarkup } = require('react-dom/server');
const root = path.resolve(new URL('../src', import.meta.url).pathname);
const read = file => JSON.parse(fs.readFileSync(new URL(`../public/data/${file}`, import.meta.url), 'utf8'));
const original = { lab: read('ai_lab.json'), ct: read('de_mirage/ct_patterns.json'), replays: read('de_mirage/replay/index.json') };
original.ct.embedding.points = original.ct.embedding.points.slice(0, 3);
let fixture = structuredClone(original);
const data = {
  getAILab: () => fixture.lab, getCTPatterns: () => fixture.ct, getReplayIndex: () => fixture.replays,
  getIndex: () => read('index.json'),
  useData: load => ({ data: load(), loading: false, error: null }), assetUrl: value => value,
};
const modules = new Map();
function load(file) {
  if (modules.has(file)) return modules.get(file).exports;
  const module = { exports: {} }; modules.set(file, module);
  const code = ts.transpileModule(fs.readFileSync(file, 'utf8'), {compilerOptions: {
    module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.ReactJSX,
  }}).outputText;
  const localRequire = name => {
    if (name.endsWith('.css')) return {};
    if (name.endsWith('.json')) return JSON.parse(fs.readFileSync(path.resolve(path.dirname(file), name), 'utf8'));
    if (/\/data$/.test(name)) return data;
    if (name === 'react-router-dom') return {
      useSearchParams: () => [new URLSearchParams()],
      Link: ({to, children, ...props}) => React.createElement('a', {...props, href: to}, children),
    };
    if (/\/Segmented$/.test(name)) return { __esModule: true,
      default: ({children}) => React.createElement('div', null, children) };
    if (/\/RecipeRadar$/.test(name)) return { __esModule: true, default: props => React.createElement('svg', null, props.overlay?.(0)) };
    if (/\/RoundReplay$/.test(name)) return { ReplayButton: props => React.createElement('button', {'data-replay': `${props.demoId}:${props.round}`}, '回放') };
    if (!name.startsWith('.')) return require(name);
    const target = path.resolve(path.dirname(file), name);
    return load(['.tsx', '.ts'].map(ext => target + ext).find(fs.existsSync));
  };
  vm.runInThisContext(`(function(require,module,exports){${code}\n})`, {filename:file})(localRequire, module, module.exports);
  return module.exports;
}
const Lab = load(path.join(root, 'pages/AILab.tsx')).default;
const Defense = load(path.join(root, 'components/CTDefense.tsx')).default;
const render = Component => renderToStaticMarkup(React.createElement(Component, {map:'de_mirage'}));
const groups = html => [...html.matchAll(/data-group="([^"]+)"/g)].map(match => match[1]);
// Explicit metadata must win even when a selected state's value is zero.
fixture.lab.shap.active_groups = ['alive_diff'];
fixture.lab.shap.inactive_groups_note_zh = '当前模型仅使用已列出的输入';
fixture.lab.model_accuracy = {...fixture.lab.model_accuracy, folds:7, matches:321, rows:123456};
let html = render(Lab);
assert.deepEqual(groups(html), ['alive_diff']);
assert(html.includes('当前模型仅使用已列出的输入'));
assert(html.includes('7 折按比赛留出验证 · 321 场比赛 · 123,456 个秒级状态'));
// Legacy exports infer activity across every example, rather than just the selected state.
fixture = structuredClone(original);
delete fixture.lab.shap.active_groups;
delete fixture.lab.shap.inactive_groups_note_zh;
for (const round of fixture.lab.shap.rounds) for (const state of round.states) state.shap_values.active_utility = 0;
fixture.lab.shap.rounds.at(-1).states.at(-1).shap_values.active_utility = .1;
html = render(Lab);
assert(groups(html).includes('active_utility'), 'a group active in a later example must remain visible');
assert(!groups(html).includes('positional_spread_pinch'), 'globally inactive legacy group must be hidden');
assert(html.includes('shap-additivity'), 'additivity output remains present');
// Explicit false must disable a point even if its replay exists in the index.
const point = fixture.ct.embedding.points[0];
point.replay_available = false;
fixture.replays[point.demo_id] = [point.round_num];
html = render(Lab);
assert(/<circle[^>]*opacity="0.12"[^>]*aria-disabled="true"[^>]*>/.test(html));
assert(html.includes('无回放'));
assert(!html.includes('未导出此回合回放'));
// The new statistical metadata and exclusions are rendered precisely.
fixture.ct.chi_square.p_display = 'p < 0.0001';
fixture.ct.chi_square.cramers_v = .23456;
fixture.ct.metadata.excluded_pistol_rounds = 123;
html = render(Defense);
assert(html.includes('p &lt; 0.0001'));
assert(html.includes("Cramér&#x27;s V = 0.23"));
assert(html.includes('已排除手枪局 123 回合'));
assert.equal((html.match(/data-kind="mean"/g) ?? []).length, 0);
assert.equal((html.match(/data-kind="sample"/g) ?? []).length, 0);
assert.equal((html.match(/data-kind="medoid"/g) ?? []).length, 5);
assert.equal((html.match(/<circle/g) ?? []).length, 10);
assert.equal((html.match(/data-time="10"/g) ?? []).length, 5);
assert.equal((html.match(/data-time="20"/g) ?? []).length, 5);
assert(!/<input[^>]*checked/.test(html), 'mean checkbox is initially off');
// Missing p_display still gets a readable tiny-p bound; no fabricated effect size.
delete fixture.ct.chi_square.p_display;
delete fixture.ct.chi_square.cramers_v;
fixture.ct.chi_square.p = 1e-107;
html = render(Defense);
assert(html.includes('p &lt; 0.0001'));
assert(!html.includes('1.000e-107'));
const observed = fixture.ct.chi_square.observed;
const n = observed.flat().reduce((sum, value) => sum + value, 0);
const dimension = Math.min(observed.length - 1, observed[0].length - 1);
const effect = Math.sqrt(fixture.ct.chi_square.statistic / (n * dimension));
assert(html.includes(`Cramér&#x27;s V = ${effect.toFixed(2)}`), 'legacy V uses the observed contingency table');
delete fixture.ct.chi_square.observed;
html = render(Defense);
assert(!html.includes('Cramér'), 'do not invent V when neither V nor a contingency table is exported');
// Floor changes break paths without inventing 10s/20s endpoints at 12s/18s.
const Trajectories = load(path.join(root, 'components/CTTrajectories.tsx')).default;
const snapshots = [10, 12, 18, 20].map((time, index) => ({t_s: time,
  positions: Array.from({length: 5}, (_, slot) => [100 + slot * 20 + index, 200 + index, index < 2 ? 0 : 1]),
}));
for (const level of [0, 1]) {
  html = renderToStaticMarkup(React.createElement('svg', null,
    React.createElement(Trajectories, {snapshots, level, kind: 'medoid'})));
  assert.equal((html.match(/data-kind="medoid"/g) ?? []).length, 5);
  assert.equal((html.match(/<circle/g) ?? []).length, 5);
  assert.equal((html.match(new RegExp(`data-time="${level === 0 ? 10 : 20}"`, 'g')) ?? []).length, 5);
  assert(!/data-time="(?:12|18)"/.test(html));
}
console.log('PASS: actual lab/CT components render new and legacy schemas, dynamic counts, inactive SHAP filtering, unavailable replays, statistical metadata and five medoid paths with ten endpoints');
console.log('PASS: floor changes split paths and preserve only actual starting/ending timestamp markers');
// Archive coverage uses team recipe IDs and the exported cluster list, with no 0-count basis.
const Details = load(path.join(root, 'components/TeamDetails.tsx')).default;
const team = read('de_mirage/teams/falcons.json');
team.matches = [];
team.insights = [];
fixture = structuredClone(original);
const coverage = () => renderToStaticMarkup(React.createElement(Details, {team}));
html = coverage();
const recipeCount = new Set(team.tactics.T.recipes.map(r => r.value)).size;
assert(html.includes(`收录 ${recipeCount} 套进攻套路`));
assert(html.includes(`${fixture.ct.clusters.length} 类 CT 阵型`));
assert(!html.includes('数据依据（0 条）'));
team.tactics.T.recipes = [];
fixture.ct.clusters = [];
html = coverage();
assert(!html.includes('数据依据（0 条）'));
assert(!html.includes('收录 0 套') && !html.includes('0 类 CT 阵型'));
console.log('PASS: actual team archive renders real tactical coverage and hides zero evidence counts');
