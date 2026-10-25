// Deterministic lifecycle checks for the actual route hook. Browser smoke owns pixels/timing.
// Run from the repository root: node web/e2e/hub_route.mjs
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import ts from '../node_modules/typescript/lib/typescript.js';

const source = fs.readFileSync(new URL('../src/pages/teamsHubRoute.ts', import.meta.url), 'utf8');
const compiled = ts.transpileModule(source, {compilerOptions: {
  module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020,
}}).outputText;
function fixture(native) {
  const slots = [], effects = [], transitions = [], animations = [];
  let cursor = 0, dirty = false, pending = [], route, reduced = false, result;
  const effect = (callback, deps) => {
    const i = cursor++, old = effects[i];
    if (!old || !deps?.every((value, j) => Object.is(value, old.deps?.[j]))) {
      pending.push(() => { old?.cleanup?.(); effects[i] = {deps, cleanup: callback()}; });
    }
  };
  const react = {
    useState(initial) {
      const i = cursor++;
      if (!(i in slots)) slots[i] = initial;
      return [slots[i], value => { slots[i] = value; dirty = true; }];
    },
    useRef(initial) { return slots[cursor++] ??= {current: initial}; },
    useEffect: effect, useLayoutEffect: effect,
  };
  const doc = native ? { startViewTransition(update) {
    const transition = { update, skipped: false,
      ready: new Promise(() => {}), finished: new Promise(() => {}),
      skipTransition() { this.skipped = true; },
    };
    transitions.push(transition);
    return transition;
  }} : {};
  const module = {exports: {}};
  const context = vm.createContext({document: doc});
  const require = name => name === 'react' ? react : {flushSync: callback => callback()};
  vm.runInContext(`(function(require,module,exports){${compiled}\n})`, context)(require, module, module.exports);
  const host = {animate(frames, options) {
    const animation = {frames: JSON.parse(JSON.stringify(frames)), ...options, cancelled: false,
      cancel() { this.cancelled = true; }};
    animations.push(animation);
    return animation;
  }};
  const render = (next = route, motion = reduced) => {
    route = next; reduced = motion;
    for (let commits = 0; ; commits++) {
      assert(commits < 10, 'route must settle without an effect loop');
      cursor = 0; pending = []; dirty = false;
      result = module.exports.useHubRoute(route, reduced);
      result.host.current = host;
      pending.forEach(callback => callback());
      if (!dirty) break;
    }
    return result.route;
  };
  return {render, transitions, animations,
    dispose() { effects.forEach(item => item?.cleanup?.()); }};
}
const orbit = {team: 'vitality', map: '', player: ''};
const mirage = {...orbit, map: 'de_mirage'};
const nuke = {...orbit, map: 'de_nuke'};
const dust = {...orbit, map: 'de_dust2'};

const native = fixture(true);
assert.deepEqual(native.render(orbit), orbit);
assert.deepEqual(native.render(mirage), orbit, 'outgoing scene remains until the native snapshot callback');
native.transitions[0].update();
assert.deepEqual(native.render(), mirage);
assert.equal(native.transitions[0].skipped, false, 'committing a destination must not cancel its own fade');
assert(native.animations.every(animation => animation.cancelled), 'native fade must not overlap a second host animation');
native.render(nuke);
const superseded = native.transitions.at(-1);
native.render(dust);
assert(superseded.skipped, 'rapid navigation skips the previous snapshot');
superseded.update();
assert.deepEqual(native.render(), mirage, 'stale native callback cannot restore an old destination');
native.transitions.at(-1).update();
assert.deepEqual(native.render(), dust);
native.render(nuke);
const pending = native.transitions.at(-1);
assert.deepEqual(native.render(nuke, true), nuke, 'turning on reduced motion commits immediately');
assert(pending.skipped);
pending.update();
assert.deepEqual(native.render(), nuke);
native.dispose();
assert(native.transitions.at(-1).skipped, 'unmount releases the native snapshot');

const fallback = fixture(false);
fallback.render(orbit);
assert.deepEqual(fallback.render(mirage), mirage, 'fallback mounts the destination without an exit delay');
const animation = fallback.animations.at(-1);
assert.equal(animation.duration, 180);
assert.equal(animation.easing, 'linear');
assert.deepEqual(animation.frames, [{opacity: 0}, {opacity: 1}]);
const count = fallback.animations.length;
assert.deepEqual(fallback.render(nuke, true), nuke);
assert.equal(fallback.animations.length, count, 'reduced motion starts no entrance animation');
assert(animation.cancelled);
fallback.dispose();
console.log('PASS: actual route hook native snapshot, single fade, rapid navigation, stale callback cancellation, immediate 180ms opacity fallback, reduced motion and cleanup');
