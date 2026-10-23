# GPT-31 — Scenic map cards and transparent orbit core

Implemented STEP 1 and STEP 2 from `delegation/GPT-31_scenic_cards.md`, applying the lead's local-only source requirement over the original scraping spec. No web downloads were performed.

## Changes

- `scripts/build_map_backgrounds.py`: executable, repository-relative Pillow/numpy pipeline; centre crop/resize to 480×600 RGB, saturation .25, contrast 1.35, SHARPEN, brightness .42, blue-black/map-colour duotone, WebP quality 85. Supports `--map`, deterministic repeat output, missing-source reporting and a manifest retaining other maps when rebuilding one.
- `assets/map-photos/README.md`: capture instructions and all seven landmarks, accepted filenames, HUD/viewmodel commands, landscape ≥1920 px guidance and rebuild commands.
- `tests/test_map_backgrounds.py`: eight synthetic-image cases cover every map, dimensions/mode, darkness bounds, output files, repeatability, missing sources and single-map manifest preservation.
- `pyproject.toml`: added Pillow to dev extras. numpy already exists in project dependencies; no duplicate or requests dependency added.
- `web/public/map-bg/manifest.json`: currently empty. No owner screenshots exist; the script reports all seven missing. The manifest prevents requests for absent WebPs and consequent expected 404 console errors.
- `web/src/data.ts`: shared base-path-aware `assetUrl()` and cached background-manifest loader.
- `web/src/pages/TeamsHub.tsx`: manifest-selected scenic layers with hidden image decode probes, radar/biome fallback and Cache stripe fallback. Failed decoding restores the fallback without a visible broken image. Asset URLs use the shared helper.
- `web/src/pages/teamsHubOrbit.ts`: initial card dimensions are 164×210; existing measured-size ellipse spacing remains in use, including its reserved hover scale.
- `web/src/teams-hub.css`: removed the core radial fill and badge pseudo-background; core, wrappers and orbit have transparent backgrounds, no borders/shadows/backdrop blur. Drop shadows apply to badge/text. Cards are 164×210, with a 78% scenic layer, .65 opacity, specified fade mask, 36px dark top gradient, title shadow, frosted rate disc, cinematic zoom and themed border glow. Active/dimmed, dashed empty states, mobile layout, reduced motion and view transitions remain.
- `web/e2e/smoke.py`: replaces radial-core expectations with ancestor transparency checks, retains desktop overlap assertions at 1440×900 and 1280×800, and adds synthetic scenic success/decode failure, sizing, masks, frosted disc, deployment URL, keyboard zoom and reduced-motion checks.

## Verification

- `.venv/bin/python -m pytest -q`: **256 passed, 3 skipped** (19.38s). One existing joblib physical-core detection warning.
- Production build: **passed**, TypeScript and Vite, 92 modules. No npm executable is available, so ran the exact package build steps:
  ```sh
  cd web
  NODE_BIN=/Users/stephen/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node
  "$NODE_BIN" node_modules/typescript/bin/tsc -b
  "$NODE_BIN" node_modules/vite/bin/vite.js build
  ```
- Full background generation and `--map mirage`: **passed**, missing photos reported; empty manifest written. No placeholder photos were shipped.
- Python compilation with warnings treated as errors: **passed**. All **10** embedded orbit browser JavaScript expressions parse with Node.
- Direct execution of `orbitLayout()` at stage widths 900, 960, 1100 and 1200: **passed**, every card at maximum hover scale stays inside the stage with ≥16px pairwise gaps. Larger cards require stage heights of 837–979px in these cases; the page scrolls vertically.
- **Live browser smoke remains unverified.** The repository Python environment lacks Playwright. An available Node Playwright runtime was used to probe the installed Chromium shell; macOS terminated it before page creation with `bootstrap_check_in … Permission denied (1100)` / `SIGTRAP`. No live computed-style assertions or screenshots passed. Static geometry checks do not substitute for the viewport smoke.

## Next steps

Supply owner screenshots under `assets/map-photos/`, run the background script and rebuild. In an environment with Playwright/Chromium launch access, serve `web/dist` and run:

```sh
python3 web/e2e/smoke.py http://localhost:4173 --orbit-only --shots /tmp/gpt31-shots
```

Also serve the build under a `/site-preview/` prefix and run the same smoke against that URL to confirm the relative-base deployment in a browser.
