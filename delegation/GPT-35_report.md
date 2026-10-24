# GPT-35 — Cache landing-spot names

Completed `delegation/GPT-35_cache_spot_names.md`: **46 spots named**, **4 Cache recipes updated**, and **204 lineup cards** now have community landing names. Confidence: **33 high / 9 medium / 4 low**.

## Inputs and naming evidence

- `delegation/inputs/spots/de_cache_spots.csv`: 46 smoke/molotov rows with every requested column, exact world/radar coordinates, throw and match counts, timing and recipe usage. Breakdown: T 12 smoke + 12 molotov; CT 10 smoke + 12 molotov. The template `en`/`zh` columns remain empty; final names are in the TOML.
- `delegation/inputs/spots/de_cache_T.png` and `de_cache_CT.png`: **visually inspected both final images**. Every spot has a yellow short-ID label, with leader lines separating near-overlaps (including T 065/076 and CT 000/014). Grey circles = smoke, orange triangles = molotov; all 47 observed configured callout medians are labelled in cyan.
- `delegation/GPT-35_build_inputs.py` reproduces the inputs using `scripts/spot_briefs.py` and the project radar `web/public/radars/de_cache.png`, then redraws the dense labels.
- Names use `config/maps/de_cache.toml`, `web/src/i18n/zh.json`, and `delegation/inputs/de_cache_callouts.csv`; Chinese keeps 公路、棋盘房、爆头位、警家连接. Side, timing and height distinguish early Garage/Z map-control utility, A catwalk variants, B Heaven and Headshot. No Sunroom target was inferred where none was present.
- `config/spots/de_cache.toml` has one entry per CSV ID, exact x/y, and radius 200 for smoke / 150 for molotov. IDs are traceability keys; runtime matching remains nearest x/y within radius for the same side/type.

## Low-confidence locations

These four entries intentionally describe a location instead of asserting a conventional target.

| Spot ID | English / Chinese | Reason |
| --- | --- | --- |
| `de_cache-ct-molotov-s016` | Molotov in mid east of Vents / 中路通风管东侧的火 | 10 throws / 8 matches, median 41.2 s; mid east of the vent entrance. The centroid does not establish a distinct conventional target (vents, garage, or a specific box). |
| `de_cache-ct-molotov-s021` | Molotov above B heaven / B 区天堂上方的火 | 6 throws / 2 matches, median 6.1 s; z=2410.1, roughly 614 units above the observed Heaven median (z=1796). An overhead landing, not enough evidence to call it a normal Heaven clear. |
| `de_cache-ct-smoke-s007` | Smoke in B site towards Tree room / B 包点内靠树房一侧的烟 | 6 throws / 4 matches; ground-level B-site interior (z=1614), towards Tree room and below the rafters area. Not a clearly identified Tree-room entrance or Heaven smoke. |
| `de_cache-t-smoke-s068` | Smoke in A site below Squeaky / A 包点内铁门南侧的烟 | 5 throws / 3 matches, median 45.6 s; northern A-site interior south of Squeaky. Too little evidence to distinguish a specific box/boost target or a standard execute smoke. |

## Four recipe titles before / after

Titles below follow `web/src/pages/Tactics.tsx::recipeSpots`: core entries sorted by `order`, omitting icons. Options are excluded from the title but are also named. Original labels/order are saved in `delegation/inputs/spots/de_cache_recipe_titles_before.json`.

### `de_cache-a-r01`

- Before: Corner + BombsiteA + ForkLift + Catwalk #2 + Quad
- After (English): A corner molotov + A cross smoke (truck side) + Forklift molotov + Catwalk smoke (A main end) + Quad molotov
- After (中文): A 区底角火 + A 区过点烟（卡车侧） + 叉车火 + A 区猫道烟（A 主道侧） + 四箱火

### `de_cache-a-r02`

- Before: BombsiteA #2 + BombsiteA
- After (English): Forklift smoke (site side) + A cross smoke (truck side)
- After (中文): 叉车烟（包点侧） + A 区过点烟（卡车侧）

### `de_cache-b-r01`

- Before: BombsiteB #2 + Heaven + BombsiteB
- After (English): Tree room smoke + B heaven molotov + Headshot molotov
- After (中文): 树房烟 + B 区天堂火 + 爆头位火

### `de_cache-b-r02`

- Before: BombsiteB #2 + Heaven + BombsiteB
- After (English): Tree room smoke + B heaven smoke + Headshot molotov
- After (中文): 树房烟 + B 区天堂烟 + 爆头位火

## Export, cards and preview

- `playbook/export.py::export_site` now attaches optional bilingual names to lineup landing centroids using the existing `name_spots` matcher and the same map config. Previously lineup cards ignored the naming configuration entirely.
- `web/src/types.ts::Lineup` declares optional `name`; `web/src/pages/Lineups.tsx` renders `lineup.name?.[lang]` with the existing localized callout fallback. This works for every map with a spot config; older/sample exports still render normally.
- Re-exported all seven active maps with `.venv/bin/python -m playbook export` (exit 0). Cache remains **426 lineups / 4 recipes**. All **46 smoke/molotov spots** and **17 core/option references** have the configured English and Chinese names.
- **204 / 231 smoke/molotov cards** match a configured location (119 smoke, 85 molotov). The other 27 smoke/molotov lineups and all 195 flash/HE cards retain callout names; this brief names the 46 exported smoke/molotov spots, not every possible landing.
- Copied the production build into `site-preview/`; copied `data/site/.` into `site-preview/data/`, `web/public/data/`, and `web/dist/data/` so the preview and subsequent builds share the final export.
- `delegation/GPT-35_verify.py` verifies unique IDs, exact coordinates/radii, all spot/recipe names, nearest-location lineup names, and SHA-256 equality for **3156 source files in each of the three copies** (zero mismatches). Results: `delegation/inputs/spots/de_cache_verification.json`.

## Validation and limits

- `.venv/bin/python -m pytest -q`: **274 passed, 3 skipped**. Extended `tests/test_export_lineups.py` to exercise names present/absent, unmatched landings and a completely empty lineup export while retaining reference integrity checks.
- `tsc -b`: passed. `vite build`: passed (92 modules). No node/npm is on PATH. Used `/Applications/ChatGPT.app/Contents/Resources/cua_node/bin/node` for TypeScript, and `/Users/stephen/Library/Application Support/Codex/artifact-sessions/runtime-generations/generation-lmSeWG/runtime/bin/node` for Vite. The latter supports the installed native Rollup dependency; the app-bundled Node rejected its code signature.
- The existing joblib warning about physical-core detection remains non-fatal; it falls back to logical cores.
- **Live browser page inspection could not run:** the sandbox refuses `python -m http.server ... --bind 127.0.0.1` with `PermissionError: [Errno 1] Operation not permitted`. Recipe/card naming was checked in exported data and the rendering code; both radar images were visually inspected. Browser verification of the completed `site-preview` remains an outside-sandbox follow-up.
- This repository copy has no `.git` directory; no commit was created.

Reproduce from the repository root:

```sh
.venv/bin/python delegation/GPT-35_build_inputs.py
.venv/bin/python -m playbook export
cp -R data/site/. site-preview/data/
cp -R data/site/. web/public/data/
cp -R data/site/. web/dist/data/
.venv/bin/python delegation/GPT-35_verify.py
.venv/bin/python -m pytest -q
```
