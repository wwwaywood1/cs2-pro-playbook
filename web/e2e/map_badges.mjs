// Run from the repo root: node web/e2e/map_badges.mjs
// Unit tests for the 王牌图/短板图 (best/weakest map) rule in src/pages/teamsHubOrbit.ts.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import ts from '../node_modules/typescript/lib/typescript.js';

const source = fs.readFileSync(new URL('../src/pages/teamsHubOrbit.ts', import.meta.url), 'utf8');
const compiled = ts.transpile(source, { module: ts.ModuleKind.ES2022 });
const { wilson, mapBadges, orbitStats, BADGE_MIN_MATCHES } = await import('data:text/javascript;base64,' + Buffer.from(compiled).toString('base64'));
let passed = 0;
const check = (name, actual, expected) => { assert.deepEqual(actual, expected, name); passed++; };
const near = (actual, expected, name) => { assert(actual.every((v, i) => Math.abs(v - expected[i]) < 5e-4), `${name}: ${actual}`); passed++; };
const map = (id, wins, n, rounds = null) => ({ map: id, n_matches: n, map_win_rate: wins / n, round_win_rate: rounds });
const none = { best: undefined, worst: undefined };

// Wilson 95% score interval (reference values computed independently).
near(wilson(.5, 8), [.2152, .7848], '4/8');
near(wilson(7 / 8, 8), [.5291, .9776], '7/8');
near(wilson(32 / 38, 38), [.6958, .9256], '32/38');
near(wilson(0, 10), [0, .2775], '0/10');
near(wilson(1, 10), [.7225, 1], '10/10');
check('no sample is uninformative', wilson(.5, 0), [0, 1]);

assert.equal(BADGE_MIN_MATCHES, 8);
// Vitality (D-04): 7/8 on Cache must not beat 32/38 on Dust2.
check('evidence beats a tiny perfect-ish sample', mapBadges([
  map('de_cache', 7, 8, .615), map('de_dust2', 32, 38, .625), map('de_anubis', 9, 19, .511),
], 5), { best: 'de_dust2', worst: 'de_anubis' });
// Monte / Astralis (D-04): equal map rates get neither badge.
check('tied rates', mapBadges([map('de_dust2', 4, 10, .48), map('de_mirage', 4, 10, .5), map('de_nuke', 4, 10, .46)], 5), none);
// FURIA (D-04): 22/37 vs 3/8, intervals overlap heavily.
check('heavily overlapping intervals', mapBadges([map('de_dust2', 22, 37, .53), map('de_anubis', 3, 8, .449)], 5), none);
// MOUZ: 26/35 vs 16/34 overlap by less than half the mean margin (about p < .05).
check('modest overlap still separates', mapBadges([map('de_mirage', 26, 35, .573), map('de_dust2', 16, 34, .495)], 5),
  { best: 'de_mirage', worst: 'de_dust2' });
// Spirit (D-04): map and round win rates disagree, so the order is not trusted.
check('round win rates contradict the order', mapBadges([map('de_ancient', 30, 34, .554), map('de_nuke', 8, 30, .566)], 5), none);
check('the same order in round win rates keeps the badges', mapBadges([map('de_ancient', 30, 34, .58), map('de_nuke', 8, 30, .47)], 5),
  { best: 'de_ancient', worst: 'de_nuke' });
// Ties on the Wilson bound break on round win rate.
check('lower-bound tie breaks on round win rate', mapBadges([
  map('de_ancient', 18, 20, .55), map('de_inferno', 18, 20, .6), map('de_nuke', 2, 20, .4),
], 5).best, 'de_inferno');
check('upper-bound tie breaks on round win rate', mapBadges([
  map('de_ancient', 18, 20, .6), map('de_inferno', 2, 20, .45), map('de_nuke', 2, 20, .41),
], 5).worst, 'de_nuke');
// Minimum samples: max(BADGE_MIN_MATCHES, the export's reliability minimum).
check('maps under 8 matches are ignored', mapBadges([map('de_dust2', 7, 7), map('de_nuke', 0, 7), map('de_mirage', 5, 10)], 5), none);
check('a higher export minimum raises the bar', mapBadges([map('de_dust2', 18, 20), map('de_nuke', 2, 20)], 25), none);
check('fewer than two eligible maps', mapBadges([map('de_dust2', 18, 20)], 5), none);
check('no export minimum', mapBadges([map('de_dust2', 18, 20), map('de_nuke', 2, 20)], undefined), none);
check('missing rates are ignored', mapBadges([{ map: 'de_dust2', n_matches: 20, map_win_rate: null }, map('de_nuke', 2, 20)], 5), none);
// orbitStats restricts both totals and badges to the seven pool nodes.
check('pool only', orbitStats([map('de_overpass', 20, 20), map('de_dust2', 18, 20), map('de_nuke', 2, 20)], 5),
  { matches: 40, best: 'de_dust2', worst: 'de_nuke' });
console.log(`PASS: ${passed} map badge checks (Wilson bounds, ties, overlap, round-rate guard, minimum samples)`);
