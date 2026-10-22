# GPT-23 v3 implementation report

Work directory: `/Users/stephen/Downloads/cs2-pro-playbook`.

## Delivered

| Item | Status | Implementation |
| --- | --- | --- |
| 1. Route names | Done | `playbook/tactics.py`: validated map-specific names, last non-core callout, fallback callout name; invalid config keys logged once. Route identity and share remain unchanged. |
| 2. Recipe extras | Done | Paired median entry gap on the leading two routes; other-site plant rate and all three intent thresholds. Exact execute-window/rush and missing-entry rules in `DESIGN.md`. |
| 3. Player six-axis profile | Done | `playbook/radar6.py`, attached by `playbook/export.py`: raw values, same-map/side midrank percentiles for >=50-round players, trade components, utility counts and clutch samples/total. CT lurk and unavailable observations are null. |
| 4. Replay extras | Done | `playbook/replay.py`: occupied cells in a reusable map-wide 15×15 grid, rounded per-second T control, actor-side kill WPA from held-out WP with terminal outcome fallback. |
| 5. Route/recipe UI | Done | Route legend uses standard names and shares; recipe cards show the three requested Chinese badges and paired entry delay. Legacy exports retain fallbacks. |
| 6. Player radar UI | Done | `PlayerRadar6.tsx`: dependency-free SVG, selected side, hover/focus percentiles and one-line definitions. Integrated into the hub player view and standalone players page. Missing axes have gaps and dashes. |
| 7. Replay UI | Done | Thin T 控图 series under WP; signed WPA percentages in killfeed. Null/missing optional data stays absent. |
| 8. Team placeholders | Done | `TeamShield.tsx`: shared neutral dark shield with short team name, including failed-logo fallback. Existing supplied logos still load from the asset registry. |
| View cones | Skipped as instructed | Need per-player sampled eye/view yaw keyed by demo/round/player/second; pitch is useful for vertical aim. Existing grenade throw yaw is insufficient. |

## Definitions and limits

- All definitions and denominators are in `DESIGN.md`, section “GPT-23 metrics”.
- Existing recipes choose the eventual plant site as target. Consequently the literal other-site plant criterion normally yields no `fake` badge; discovering a pre-rotation fake would require a separate attempted-target recipe grouping. No unverified coordinate boxes were introduced.
- Molotov displacement uses the nearest 1 Hz sample, the replay's 120-unit XY radius, a 120-unit Z tolerance, and >150 units displacement within 3.5 seconds. This is a movement proxy, not causal fire damage.
- Clutch raw WPA is mean outcome minus starting held-out WP per observed 1vN; sample count and sum are also exported. CT lurk is deliberately undefined.
- T control measures proximity to observed occupied cells, without navmesh, walls, floors or sight lines. Kill WPA uses the existing floor(t) to floor(t)+2 sampled window, so nearby actions can share a swing.
- Verse strength/column wipe and data-derived portrait callouts were preserved. No image source files, `.github`, or `delegation/design-skills/` were edited. No npm dependencies were added.

## Validation

- `.venv/bin/python -m pytest -q` with the bundled Node runtime added to `PATH`: **204 passed**, no skips, one joblib physical-core discovery warning (logical-core fallback); 32.35 s. See `delegation/GPT-23_pytest.log`.
- Added `tests/test_gpt23_metrics.py`: numerical checks for route config validation/logging, all intent thresholds, every radar axis, side/sample peer eligibility, trades at the four-second boundary, fire displacement boundaries, occupied-grid control and kill WPA signs/terminal states. `tests/test_replay.py` also verifies replay schema integration; its additional assertions pass (1 test).
- TypeScript `tsc -b web`: passed using the existing bundled Node 24.19.0 and installed dependencies. Production Vite build: **passed after syncing full exported JSON**; final artifacts are in `web/dist`. Commands/output: `delegation/GPT-23_build.log`.
- `web/e2e/smoke.py`: fixtures/assertions updated for names, intent badges/delay, control/WPA, side-specific radar tooltips and neutral shields; Python compilation passed. Browser intentionally **not run**, per owner instruction; Claude should run the smoke suite with sample data.
- `PYTHONUNBUFFERED=1 .venv/bin/python -m playbook export`: **passed**, exit 0. See `delegation/GPT-23_export.log`. Six active maps exported; model scored 289 matches (including maps outside the active export pool), accuracy 0.743 vs 0.697 baseline, log loss 0.471. Inferno draft key `Boiler` was ignored and logged once, as required.
- Export audit **passed**: 834 players / 1668 side profiles (344 eligible), 99 recipes, 181 named routes, 2195 replays and 14455 kill events. Checked profile eligibility/bounds/null semantics, CT lurk nulls, route names, recipe fields, control/frame alignment and WP/WPA bounds. 150 kill events retain null WPA: 113 lack the exact pre-event sampled state, 2 lack the post-event state, and 35 have no known actor. These are preserved as missing observations, not fabricated zeros. Replay mean 12,873 bytes, maximum 20,496 bytes. Counts are in `delegation/GPT-23_audit.json`.
- Synced 2733 exported JSON files into `web/public/data`; image assets were not copied or changed.

## Falcons on Mirage

Source: completed Mirage export, `data/site/de_mirage/players.json`. Each cell is **raw / percentile (0–100)**; a dash means unavailable. Filtered by the exported canonical team name; no roster filtering was applied.

| Player | Side | Rounds | Entry | Trade | Lurk distance | Space gain | Utility impact | Clutch WPA |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| karrigan | T | 142 | 0.1761 / 35.2 | 0.1223 / 51.1 | 1268.2094 / 55.7 | 1433.7255 / 37.5 | 0.0986 / 80.7 | 0.0671 / 75.0 |
| karrigan | CT | 175 | 0.0857 / 5.2 | 0.1151 / 40.6 | — / — | 600.4639 / 3.1 | 0.0571 / 56.2 | -0.0391 / 36.5 |
| kyousuke | T | 142 | 0.2324 / 71.6 | 0.1431 / 71.6 | 1135.3259 / 39.8 | 1505.4143 / 62.5 | 0.0211 / 12.5 | 0.0160 / 58.0 |
| kyousuke | CT | 175 | 0.2343 / 69.8 | 0.1178 / 42.7 | — / — | 982.2759 / 69.8 | 0.0229 / 13.5 | -0.0041 / 49.0 |
| m0NESY | T | 142 | 0.2042 / 60.2 | 0.1313 / 58.0 | 1097.2113 / 33.0 | 1332.9280 / 8.0 | 0.1197 / 87.5 | 0.0177 / 60.2 |
| m0NESY | CT | 175 | 0.2914 / 92.7 | 0.1261 / 53.1 | — / — | 729.4514 / 30.2 | 0.0571 / 56.2 | -0.0792 / 17.7 |
| NiKo | T | 142 | 0.1408 / 8.0 | 0.1023 / 26.1 | 1376.5959 / 71.6 | 1366.0583 / 12.5 | 0.0352 / 28.4 | 0.0256 / 64.8 |
| NiKo | CT | 175 | 0.2400 / 71.9 | 0.1319 / 59.4 | — / — | 1001.7872 / 82.3 | 0.0171 / 3.1 | 0.0926 / 80.2 |
| TeSeS | T | 142 | 0.2394 / 73.9 | 0.1485 / 78.4 | 1561.4986 / 96.6 | 1369.8335 / 14.8 | 0.0423 / 33.0 | 0.0553 / 69.3 |
| TeSeS | CT | 175 | 0.1486 / 20.8 | 0.1258 / 50.0 | — / — | 987.3862 / 71.9 | 0.0343 / 19.8 | -0.0444 / 32.3 |
