# GPT-30 — Orbit card backdrop and transparent core

Implemented the brief in the four requested frontend files. No dependencies added or backend/data export edits made.

## Changes

- `web/src/pages/teamsHubOrbit.ts`: exports the stable seven-map pool with the specified ambient RGBA colours and shared grey empty-map glow. Orbit geometry is unchanged.
- `web/src/pages/TeamsHub.tsx::TeamPanel`: replaces the old `.hub-map-preview` image with exactly one decorative `.map-card-bg` per node. Radar URLs retain `import.meta.env.BASE_URL`, supporting relative-base HashRouter deployments. Empty maps retain their radar and use grey ambient light; Cache uses the CSS diagonal grid and requests no missing radar.
- `web/src/teams-hub.css`: card base is `#0B1116`; masked radar uses 165% sizing, 40% grayscale, 130% contrast, −8° / 1.05 scale and .16 opacity. An independent ambient gradient sits above the texture and below all text/badges. Interactive hover/focus moves the texture to −4° / 1.18 scale and .32 opacity over .35s. Added a 1px top highlight and subtle breathing win-rate ring shadow. Empty nodes retain dashed borders and do not enlarge or gain a hover shadow. Existing active/dimmed states, semantic colours and shared view transitions remain.
- Core background now uses the specified radial gradient with transparent outer edges, `border: none` and `box-shadow: none`. Ray start positions and stacked content are preserved.
- Reduced motion disables backdrop transforms/transitions, keeps opacity fixed at .16 even during hover/focus, and stops the ring breathing. Orbit selectors meet or exceed the existing shared card rule's specificity.
- `web/e2e/smoke.py::check_orbit_backdrops`: checks every node's single radar/grid, deployment-relative URL, loaded radar asset, exact glow, text stacking, hover opacity, empty hover behaviour, transparent radial core, and reduced motion. Updated the old preview assertion and geometry expectations for the radial core and non-enlarging empty cards. Included in `--orbit-only`.

## Verification

- `.venv/bin/python -m pytest -q`: **248 passed, 3 skipped**, 19.79s. One existing joblib warning about physical CPU detection.
- Production build: **passed**, TypeScript and Vite (92 modules). This shell has no `npm` executable, so ran the exact build-script steps with the installed Node runtime:

  ```sh
  cd web
  NODE_BIN=/Users/stephen/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node
  "$NODE_BIN" node_modules/typescript/bin/tsc -b
  "$NODE_BIN" node_modules/vite/bin/vite.js build
  ```

- `.venv/bin/python -m py_compile web/e2e/smoke.py`: **passed**.
- Parsed **21 browser JavaScript expressions** from the modified smoke functions with Node: **passed**. This verifies syntax, not browser assertions.
- Browser smoke: **blocked before assertions, not passed**. Attempted `web/e2e/smoke.py http://localhost:4173 --orbit-only --shots /tmp/gpt30-shots` using the sibling checkout's existing Playwright Python environment. Chromium failed at launch with macOS `bootstrap_check_in … Permission denied (1100)` / `SIGTRAP`. No screenshots or live computed-style results were obtained.

The build regenerated `web/dist` and TypeScript build metadata.

## Follow-up

Run the browser checks from a terminal with Chromium/server access, without replacing the current exported data:

```sh
# Terminal 1, repository root
python3 -m http.server 4173 --directory web/dist
# Terminal 2, with web/e2e/requirements.txt and Playwright Chromium installed
python3 web/e2e/smoke.py http://localhost:4173 --orbit-only --shots /tmp/gpt30-shots
```

Live visual contrast, computed styles, navigation and geometry remain to be confirmed by that run.
