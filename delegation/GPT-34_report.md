# GPT-34 — Cache support and orbit fixes

## A. Cache

- Added `config/maps/de_cache.toml` with the standard seven regions and **all 47 observed live callouts** (the requested 40 plus MidRoof, BackHall, TTruck, Lockers, Red, ABoost and Middle). Added matching Chinese/English entries in `web/src/i18n/{zh,en}.json`.
- Final radar transform: **pos_x = -2000.0, pos_y = 3250.0, scale = 5.5**. The classic overview values already align; no adjustment was necessary. Pixel conversion is `((x + 2000) / 5.5, (3250 - y) / 5.5)`.
- Verification overlay: [`inputs/cache_radar_check.png`](inputs/cache_radar_check.png), generated from **all eight demos**, **121,170 living-player one-second samples**, and **93 plants** (46 A / 47 B). Visual inspection aligns spawn rooms, garage, mid, A main, checkers, heaven and both plant zones with the overview. All samples are inside 1024²; **121,113 / 121,170 (99.953%)** are within 6 px of the overview's nonblack footprint. This image-footprint check includes walls/props/upper floors and is supporting evidence, not nav-mesh verification.
- Reproduce with `.venv/bin/python scripts/check_cache_radar.py`. It writes the overlay, per-demo statistics in `delegation/inputs/cache_radar_check.json`, the checker inventory `de_cache_callouts.csv`, and `de_cache_callout_evidence.csv` (coordinates, A/B plant-round presence, early T/CT presence).
- Ambiguous lane/region assignments have `# ?` evidence comments. Examples: Garage has 1,856 early T / 5 CT samples and A/B plant-round T presence 1,499/1,854, so it is MID. Highway has 716 early CT / 0 T and A/B presence 428/30; it remains the shared MID/A rotation. Toxic and Ladder are on A in this radar (A/B presence 44/3 and 22/1), despite potentially misleading generic names. Connector, CTLane and Bear are CT rotation links; Vents remains a shared mid/B passage.
- Copied the unchanged awpy/Valve radar into `web/public/radars/de_cache.png` and `site-preview/radars/de_cache.png`. Existing `.gitignore` rules exclude both destinations. SHA-256: `94c058b3deaa5cc24be81006322da3af1ef0bbded116160a3fcdea6d87227967`.
- Removed the frontend Cache exclusion from availability and hover previews. Teams with Cache matches get the normal map node, scenic/radar fallback, and map/player navigation. Teams with zero Cache matches retain the dashed disabled node and grid fallback, labelled **暂无数据**; they do not request a possibly absent Cache radar in a sample-only deployment. Home uses exported match availability for Cache and labels absent data **暂无数据**.

### Data regeneration and verification

- `.venv/bin/python -u -m playbook relabel de_cache`: **8 demos relabelled**. **0** living-position samples retain an OTHER lane.
- `.venv/bin/python -u -m playbook export`: **exit 0**; all seven active maps exported. Logs: `_sync/gpt34/export.log`.
- Ran `scripts/sync_web_data.py`, `cp -R data/site/. site-preview/data/`, rebuilt `web/dist`, and copied the completed build into `site-preview/`. SHA-256 comparison: **3156 source files checked against each of web/public/data, web/dist/data and site-preview/data; 0 mismatches**. Preview HTML and Cache radar match the build/public assets. Evidence: `_sync/gpt34/sync-verification.json`.
- Regenerated Cache data contains **8 matches, 7 teams, 36 players, 426 lineups and 4 execute recipes**. Existing replay selection policy exports **12 example rounds across 4 demos**; it does not promise every round of every Cache match.
- Direct data verification checks **852** lineup endpoint transforms within 0.06 px (allowing exported world/pixel rounding), and **10,663** replay player positions across **1,265 frames** exactly against transformed parsed positions. Also verified **91 tactical spot transforms** and **47 heatmap callout anchors** against the calibrated source observations. Evidence: `_sync/gpt34/export-verification.json`; reproduction helper: `_sync/gpt34/verify_export.py`.

## B. Orbit

- `web/src/pages/teamsHubOrbit.ts::orbitStats` filters both sample totals and rankings to the seven rendered pool maps. Best/weakest badges require `index.json.min_matches_reliable`; no badge is assigned until the index loads. Vitality Ancient (2 maps, 100%) is excluded at the current minimum of 5. With the current export, Cache (8 maps, 87.5%) gets the best-map badge and Anubis (19 maps, 47.4%) the weakest-map badge; the subtitle is 138 matches across seven nodes. Low-sample cards also use neutral rate colour.
- Reduced cards to **156×178** and tightened stage padding. A staggered ring separates shoulder/side columns horizontally, avoiding the excessive vertical radius of a regular seven-node ellipse. Measured card sizes still reserve **1.08× hover scale + 16 px spacing**, with the ellipse fallback retained at narrower desktop widths. Mobile remains a grid.
- `LowSampleBanner` has an opt-in compact `!` chip on the match-count row, with the full warning as `title` and accessible label. Other banners retain their existing full wording.
- Subtitle sums the map nodes actually shown, rather than using a potentially broader team total. Cache's eight maps now participate normally.
- Updated `web/e2e/smoke.py`: viewport bounds and card-content containment at **1440×900 / 1280×800**, existing no-overlap/hover/focus checks, screenshot capture, dynamic badge threshold, stale-total regression, compact warnings, positive/empty Cache home/team states, Cache tactics/lineups/players/player-detail/replay routes, and radar fallback for Cache. `--orbit-only` now runs the orbit and Cache regressions against current data.

## Checks and limitations

- `.venv/bin/python scripts/check_map_config.py --all`: **8 maps pass**, including Cache's full inventory and both translations.
- `.venv/bin/python -m pytest -q`: **272 passed, 3 skipped**, one existing joblib physical-core-detection warning (27.24 s). New `tests/test_cache_map.py` covers callout coverage, important lane assignments, overview corners and observed plant medians.
- `node web/e2e/orbit_geometry.mjs`: **24 layouts pass** at maximum hover scale, preserving stage bounds and 16 px pairwise gaps. Also tests minimum-sample changes, unknown threshold, no reliable samples, and exclusion of historical maps from totals/ranking.
- TypeScript/Vite production build: **passed** (92 modules). No `npm`/`node` is on PATH here; the available Node executable is `/Users/stephen/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node`, used for the exact `tsc -b` and `vite build` package steps.
- Python smoke/helper compilation with warnings treated as errors: **passed**. All **25** embedded orbit/Cache browser JavaScript expressions parse with Node.
- **Live browser smoke and new viewport screenshots could not run in this sandbox.** The Python venv lacks Playwright; probing the available Node Playwright runtime with installed Chromium shell revision 1248 fails before page creation with macOS `bootstrap_check_in ... Permission denied (1100)` / SIGTRAP. Starting Vite also fails with `listen EPERM 127.0.0.1:4173`. These are execution restrictions; static geometry checks are not a substitute for browser-computed layout. The supplied `delegation/inputs/vitality_orbit_1440.png` was inspected and retained unchanged as the before reference.

Outside this sandbox, install `web/e2e/requirements.txt`, serve the completed build, then run:

```sh
python3 web/e2e/smoke.py http://localhost:4173 --orbit-only --shots /tmp/gpt34-shots
```

Repeat under the `/site-preview/` prefix to verify the relative-base deployment. The smoke captures `vitality_orbit_1440.png` and `vitality_orbit_1280.png` in the specified shots directory. This repository copy has no `.git` metadata; no commit was created.
