# GPT-28 — replay facing direction and view cones

Implemented the parser, targeted demo refresh, compact replay export and frontend cones. Export and preview data are rebuilt locally.

## Implementation

- `playbook/parse.py::position_yaw`, `parse_demo`: awpy **3.1.0** does **not** resolve the `yaw` tick alias (it returned only null strings). The working pawn property is `m_angEyeAngles`, encoded as `QAngle(pitch, yaw, roll)`. Extract its second component after the existing 1 Hz sample join into nullable **Float64 world degrees**; malformed/nonfinite angles become null. Existing position fields remain intact.
- Benchmark on `2394216_tyloo-vs-pain-m1-mirage` (1,661,374 tick rows): original six properties **0.295s**, adding `m_angEyeAngles` **0.397s**. String extraction runs only on sampled rows.
- `playbook/store.py::is_parsed`: the store has no parse-version key. Schema-based invalidation now requires `positions.yaw: Float64`, so ordinary parsing will refresh old caches. Legacy tables still load through the existing diagonal concatenation.
- `scripts/reparse_replay_yaw.py`: decode only eye angles for demos referenced by existing replay files, join on `(tick, steamid)`, preserve row order and all non-yaw values, and replace each position parquet atomically. Uses `GameDemo` for retained multipart round ownership/tick offsets. All other tables are hashed before/after.
- `playbook/replay.py::radar_yaw`, `build_round`: add top-level `yaw[second][player]`, parallel to `frames`, integer **0–359 radar degrees clockwise from right**. Dead, unseen and unknown samples are null; old positions lacking yaw remain exportable.
- `web/src/components/RoundReplay.tsx`, `web/src/replayMath.ts::frameYaw`, `web/src/types.ts`: cones behind living player markers, **40°**, **22 screen px**, side colors at **0.18 opacity**, no pointer interception. Interpolate by the shortest arc through 0/360. Reduced motion holds the current second's direction while retaining cones. Missing yaw produces no cone.

## Refresh, metadata and delivery

- `.venv/bin/python scripts/reparse_replay_yaw.py`: **207 demos**, including **9 multipart games**, **167.650s wall time**. Refreshed **4,250,290 position rows**; **3,364,313 / 3,364,313 live rows** have yaw. Only the yaw portion needed by replay was re-parsed; no full semantic rebuild was necessary.
- Every existing non-yaw position value compared equal before replacement. All non-position parquet tables were byte-identical, including match/source/HLTV metadata and semantic tables. Combined SHA-256 before/after: `bfc45441663b53066e5606ac29b18847fe1574954a21ed6586ff924eb4b6178c`.
- Per-demo times/coverage and metadata hashes: `delegation/GPT-28_yaw_timings.json`.
- `.venv/bin/python -m playbook export`: **529.085s wall time**, exit 0; **27 duplicates removed**, **283 active-pool matches** across six maps. Existing dates, roster indexes and frames preserved in all **2,195 replay files**. Yaw populated for **1,619,461 / 1,619,461 visible samples**; every dead/unseen sample has null yaw.
- `cp -R data/site/. site-preview/data/`: **0.619s**; all source files byte-compared with preview. Also copied the newly built `web/dist/index.html` and `web/dist/assets/.` into `site-preview/`, so its frontend includes the cones. Total copied source files: **2,671**.

## Orientation check

World yaw points along `(cos(yaw), sin(yaw))`; `MapMeta.to_radar` negates the world y direction. Therefore export **`round(-world_yaw) % 360`**, with no extra 90° rotation.

Real Mirage sample: `2394216_tyloo-vs-pain-m1-mirage`, **piriajr (T), round 16, t=1s, tick 128354**, `TSpawn`. World `(1422.0944, 36.4371)`, yaw **−162.27562°**. The actual `build_round` output is radar **[930,335]**, yaw **162°**: left and slightly down toward the observed `TopofMid` centre, radar **[716,404]** (world `[348.9260,-306.3344]`). Unrounded facing differs from the bearing by **0.011°**. This is a numeric/data check, not an in-game screenshot.

## Validation

- Full pytest with Node available: **251 passed**, **29.51s**, one existing joblib physical-core detection warning. Includes real single-demo/multipart parser checks, nullable yaw, cache invalidation, refresh invariants, export alignment/dead/unknown/legacy handling, cardinal directions and TypeScript shortest-angle/reduced-motion tests. Log: `/tmp/gpt28-pytest.log`.
- After strengthening the orientation fixture with the real piriajr sample: `pytest tests/test_view_cones.py -q`: **14 passed**, **0.36s**.
- TypeScript and production Vite build passed: from `web/`, `node node_modules/typescript/bin/tsc -b && node node_modules/vite/bin/vite.js build`. Vite: **90 modules**, **1.86s**. Used Node **24.19.0** from `/Users/stephen/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node` (not on the default shell PATH).
- `node web/e2e/render_view_cones.cjs`: **22 actual React static-render assertions passed**, covering geometry, colors, layering, interpolation, reduced motion, dead/unknown players and old JSONs. Uses existing esbuild/React dependencies; no dependencies added.
- `web/e2e/view_cones.mjs` adds desktop/mobile browser checks and passed `node --check`. **Browser execution remains unverified**: this sandbox denies localhost binding (`PermissionError: Operation not permitted`) and Chromium launch (`MachPortRendezvousServer … Permission denied (1100)`). Static-render checks do not establish browser pixel layout or live playback.
- After export, validated array dimensions, integer range, visible/dead coverage and baseline replay/date/frame preservation; preview files were byte-compared. Export log: `/tmp/gpt28-export.log`.

On a host that permits Chromium, serve `site-preview/` and run `node web/e2e/view_cones.mjs http://localhost:4173` with Playwright available. This is the remaining browser verification.
