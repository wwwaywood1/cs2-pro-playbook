# GPT-40 frontend lab report — 2026-10-24

Completed sections A–D. Repository edits are confined to `web/` plus this requested report. No data export or sync script was run. This checkout has no `.git`, so verification used source inspection and filesystem paths.

- **A / Orbit:** `web/src/components/Layout.tsx` measures the sticky topbar using ResizeObserver. `web/src/teams-hub.css` keeps orbit breadcrumbs sticky beneath that measured height. The supplied failure geometry shows intact node/ray placement after scrolling, while the previous relative breadcrumb could move under the topbar; `scroll-margin-top` alone does not keep it visible. Kept the visibility predicate intact and added breadcrumb/topbar rectangles and scrollY to failure diagnostics. This diagnosis/fix still requires the lead's browser confirmation.
- **A / Particles:** `web/src/components/ParticleLogoCanvas.tsx` exposes `data-sampling-done` and `data-sampled-source` only after PNG pixel sampling completes. `web/e2e/smoke.py` waits for both completion and the requested team's source, avoiding a stale previous-team canvas satisfying the particle-count wait during a route transition.
- **B / Lab:** Added `#/lab` and the nav entry. Four panels provide map/cluster/snapshot distance-kernel examples and actual PCA points; a keyboard sample selector and replay links where exported; grouped Shapley bars with the full-precision additive identity/residual; observed occupied-grid ownership and before/after smoke counterfactual cells; exported model metrics and references with copy support. Exactly the six references in the JSON are rendered. Paper-scope statements appear in the distinct `论文结论（Dust2）` note. No paper outcome percentages or unverified citations were added.
- **C / CT defense:** The existing CT side selector reveals dynamic cluster cards with exported Chinese labels, shares, counts, CT win rates, 95% CIs, all context preferences and their map-relative percentage-point differences. Selection overlays mean paths, actual medoid paths from the matching attention export, and available replay samples on the existing RecipeRadar. Exported radar coordinates are already transformed; they are not transformed twice. Fixed player identities are retained within each trajectory. Nuke paths split at floor changes; replay samples lack floors and therefore are not overlaid on Nuke. Shows method, outlier count, cluster-size warning, chi-square summary and sparse-cell caveat. Overpass is shown only on explicit map selection and marked historical.
- **D / Fingerprints:** Team map slides show paired horizontal bars for team cluster shares and the exported same-map professional average, with labels and differences. No panel is rendered for missing fingerprints or fewer than 30 included CT rounds. Positioned after the roster so the existing map summary remains the first content.

Source changes:

- `web/src/App.tsx`, `web/src/data.ts`, `web/src/labTypes.ts`, `web/src/lab.css`, `web/src/teams-hub.css`
- `web/src/pages/AILab.tsx`, `web/src/pages/Tactics.tsx`, `web/src/pages/TeamsHub.tsx`
- `web/src/components/Layout.tsx`, `web/src/components/ParticleLogoCanvas.tsx`, `web/src/components/RecipeRadar.tsx`
- `web/src/components/CTDefense.tsx`, `web/src/components/CTTrajectories.tsx`, `web/src/components/TeamFingerprint.tsx`
- `web/e2e/smoke.py`

Static data: copied the existing `data/site/ai_lab.json` and eight `data/site/<map>/ct_patterns.json` files into their matching `web/public/data/` locations. All nine copies were verified byte-for-byte. No other site JSON was regenerated. The Vite build refreshed ignored `web/dist/` outputs; TypeScript refreshed its ignored build metadata.

Scientific presentation decisions:

- Attention is explicitly a distance kernel with self edges, not a trained GAT. The projection is labelled PCA, not UMAP. Clicking a point identifies that round and its cluster; the left radar remains explicitly labelled as the cluster medoid. An exported replay can be opened separately.
- SHAP explains the existing calibrated match-held-out model. Active utility and spread/pinch remain exactly zero. Observed replay control is displayed separately from model lane-occupancy inputs. Accuracy is shown as the exported 75.04%, not an aspirational number from the original spec.
- Space control discloses straight-line world XY distances, occupied-cell masking, no NavMesh/walls/floor model, and the actual smoke penalty. The supplied example changes T control by approximately **−1.12 pp**, which is preserved. Connecting snapshot positions does not reconstruct unseen movement or imply navigable paths.
- Means and medoids are distinguished; different rounds' colored slots do not imply the same named player. Replay samples are limited to available files in the existing replay index.

Validation results:

- **PASS:** TypeScript, `node web/node_modules/typescript/bin/tsc -b web` (final source).
- **PASS:** Vite production build from `web/`, `node node_modules/vite/bin/vite.js build` (102 modules; final output built successfully).
- **PASS:** `node web/e2e/orbit_geometry.mjs`: 10,800 orbit phases plus rAF/damping/pause/reduced-motion/ray/cleanup checks.
- **PASS:** `caffeinate -i .venv/bin/python -B -m pytest -q -p no:cacheprovider`: **297 passed, 3 skipped** in 24s. One joblib physical-core-detection warning fell back to logical cores.
- **PASS:** Python AST parsing of the extended smoke script and byte-for-byte data-copy checks.
- **NOT RUN:** Browser smoke/visual checks, per the lab's explicit Mac restriction. The project's `.venv` also lacks the `playwright` package (`smoke.py --help` fails at import); the lead's configured Linux browser environment is required.

Local build tooling: this shell has no `npm`/`node` on PATH. Used the installed app-bundled Node CLI directly. Its hardened macOS signature initially rejected Rollup's existing native addon because of different Team IDs. A temporary copy of Node with an ad-hoc signature successfully ran Vite; dependencies and lockfiles were not changed. Long checks used `caffeinate -i`.

Lead follow-up, serving the current `web/dist` data without an export/sync:

```sh
python3 -m http.server 4173 --directory web/dist
# In another terminal with Playwright and Chromium installed:
python3 web/e2e/smoke.py http://localhost:4173 --orbit-only --shots /tmp/gpt40-orbit
python3 web/e2e/smoke.py http://localhost:4173 --lab-only --shots /tmp/gpt40-lab
```

The new `--lab-only` suite checks all four panels, exact exported reference IDs/count, the Dust2 note, time scrubbing/additivity/zero groups, counterfactual cell ownership, cluster count/share sum/card selection, mean/medoid/sample paths, chi-square warning, fingerprint shares and the inclusive 30-versus-29-round boundary. The shared runner also checks 375px overflow. Browser results remain outstanding; do not treat the CSS breadcrumb correction as browser-verified yet.
