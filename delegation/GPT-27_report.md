# GPT-27 desktop smoke fixes

Scope: frontend source and smoke checks under `web/`, plus this report. No backend, export data, config, npm dependencies, or mobile layout changes. This checkout has no `.git` directory, so changes were reviewed against temporary pre-edit copies.

## Changes

1. **TeamsHub at 1280×800** — `web/src/pages/TeamsHub.tsx::HubRadar` now measures before paint and after committed layout changes, observes the controls/header/warnings above the radar, and remeasures after fonts load and viewport resizing. Its document-coordinate budget includes offset-parent borders and remains independent of entrance/parallax transforms and scrolling. Previously only the page, radar and topbar were observed; controls could wrap/reposition the radar without changing the page's total size. `web/src/teams-hub.css` compacts analysis/header spacing and KPI sizes on desktop viewports ≤850px high. The radar still uses remaining viewport height, with 24px clearance. Verse typography, opacity, translation and entrance styling retain their full strength.

2. **Real Mirage lineup responsiveness** — `web/src/pages/Lineups.tsx` previously rendered all 2,443 cards with copy controls, SVG icons and reveal styles. Shared map-link hover/focus also rerendered that whole list. A large landing pick additionally rendered every matching trajectory in `web/src/components/Radar.tsx`. These are concrete unbounded rendering workloads; browser CPU profiling was unavailable here.
   - Initially mount 60 cards; localized **Show more / 显示更多** appends another 60. Result/filter totals and overview cluster counts continue to include all exported lineups.
   - Result-set changes and Reset return to the first batch. A selected card outside the batch remains mounted as one extra card, so deep links and radar selection can still scroll to it without expanding thousands of cards.
   - Expanded SVG trajectories follow the visible card batch (plus the active linked route). Overview clusters still represent every eligible lineup. Show more also reveals the corresponding routes.
   - Preserve `id`/`landing` URLs, local map picking, selection, clear button, Escape and Back/Forward handling. Pagination adds no URL parameters.
   - Memoize the radar component and stabilize its parent callbacks; retain the existing memoized cluster geometry.

3. **Segmented highlight** — `web/src/components/Segmented.tsx` retains button-relative offsets, nowrap tracks and keyboard navigation. It now coalesces observer measurements into an animation frame and explicitly measures after `document.fonts.ready`, later font-loading events and window resize. Pending frames/listeners are cleaned up.

4. **Browser regression checks** — `web/e2e/smoke.py` now distinguishes full result totals from mounted batches, checks Show more, CT/tier/technique filtering, map-pick clear/selection, and a tail deep link. With `--shots`, it captures the initial lineup page under the original 10-second screenshot limit. Desktop segmented checks compare highlight x/y/width/height with the pressed button after fonts and resize. Existing 1280×800 and 1440×900 radar geometry assertions remain. The three deferred mobile checks remain unchanged.

## Validation

- **PASS** `.venv/bin/python -m pytest -q`: **234 passed, 2 skipped, 1 warning**, 16.69s. Log: `/private/tmp/gpt27-pytest.log`. Warning: existing joblib physical-core detection fallback.
- **PASS** `.venv/bin/python -m pytest -q tests/test_smoke_routes.py`: **15 passed** after smoke-check edits.
- **PASS** `.venv/bin/python -m py_compile web/e2e/smoke.py`.
- **PASS** production build, including TypeScript: `PATH='/Users/stephen/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin:'"$PATH" node /private/tmp/npmcli/package/bin/npm-cli.js --prefix web run build`. Log: `/private/tmp/gpt27-build.log`. This is the available-runtime equivalent of `cd web && npm run build`.
- **PASS** actual React static-render checks against `data/site/de_mirage/lineups.json` (2,443 rows) and sample data (45 rows), using a temporary esbuild harness with injected data/state: 60 initial cards, 120 next-batch cards, CT filtered totals, 61 cards including a selected tail result, and 60 expanded trajectories for a pick containing all 2,443 IDs. Harness: `/private/tmp/gpt27-render-check.cjs`. These validate rendered output, not live effects/navigation or browser layout.
- Before/after static markup comparison: **2,443 → 60 initial cards**, **4,522,057 → 126,637 HTML characters**. This supports the rendering-workload diagnosis; it is not a browser latency benchmark.
- `web/public/data/de_mirage/lineups.json` already contains all 2,443 real rows. Data was not synchronized or replaced.

## Browser verification still required

This host denies localhost binding (`PermissionError: [Errno 1] Operation not permitted`) and Chromium launch (`bootstrap_check_in … MachPortRendezvousServer … Permission denied (1100)`). Therefore no claim is made that browser timing, screenshots, desktop geometry or highlight pixel alignment have passed. No security settings were changed.

On the lead's Linux runner, rebuild and serve the current real-data bundle, then rerun:

```sh
cd web && npm run build && cd ..
python3 -m http.server 4173 --directory web/dist
# In another terminal:
python3 web/e2e/smoke.py http://localhost:4173 --shots /tmp/gpt27-real-shots
```

Confirm CT clicks and the initial screenshot finish within 10s, exercise tail `id`/large `landing` URLs and Show more, and rerun the desktop player geometry against both sample and real data at 1280×800 and 1440×900. Only the three known 375px failures are deferred.
