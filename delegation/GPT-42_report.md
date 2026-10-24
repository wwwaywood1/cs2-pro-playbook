# GPT-42 — Bigger orbit map cards

Completed on 2026-10-24 after reading GPT-40's completed report. Intentional repository edits are confined to `web/` plus this requested report. This checkout has no `.git`, so Git status/diff is unavailable. No data export or production map-background regeneration was run; existing natural-colour image assets were retained.

## Changes

- `web/src/pages/teamsHubOrbit.ts`: increased `ORBIT_CARD_SIZE` from 168×216 to **224×288** logical pixels. Replaced the conservative angular ellipse with a power-4 rounded orbit, parameterised by distance in card-relative units to avoid bunching along the short axis. The fit reserves 16px between cards, 16px around a **300×128** centre exclusion box, the existing ±5% depth, 8% hover enlargement and measured-size rounding. A phase-sampling movement bound also reserves clearance between samples. Fits are cached by stage/card dimensions, so animation frames only interpolate the path.
- `web/src/teams-hub.css`: photo/artwork height is **55%**. Explicit data rows fit within the 288px card. Decoded photos use full opacity with no mask, tint, brightness/contrast adjustment or hover colour effect. Photo cards lose the map-colour background wash and coloured active shadow; the remaining text-edge fade is neutral dark. Inactive photo cards also retain full opacity. The 2px map-colour accent remains, without its glow.
- Desktop layout: placed the logo/name and preview in adjacent columns within the centre exclusion box, using a 72px logo and 20px name. Combined the introductory title/help into one row and reduced the orbit's top margin, recovering 30px for the stage while keeping its lower edge at approximately the same viewport position. The existing measured-header sticky breadcrumbs remain in place. Mobile retains its grid layout.
- `web/e2e/orbit_geometry.mjs`: extended coverage to 50 stage budgets / **18,000 phases**, including the new desktop heights. Checks containment, card gaps, centre clearance and the actual size increase against the previous fit; retained rAF/damping/pause/reduced-motion/resize/ray/cleanup checks.
- `web/e2e/smoke.py`: updated logical dimensions, minimum rendered sizes, centre clearance, the compact centre columns, 55% artwork/photo height, neutral fade, full photo opacity and focus-state colour checks. Existing breadcrumb visibility, content containment, routing and photo failure fallback checks remain.

## Rendered size from the production geometry

These are calculated dimensions at middle depth using the previously measured stage widths, not browser measurements of this change. The existing depth effect varies both dimensions by ±5%.

| Viewport | Stage | New card | Increase over previous fit |
| --- | --- | --- | --- |
| 1440×900 | 1296×700 | **170.1×218.7px** | **1.42×** |
| 1280×800 | 1144×600 | **136.3×175.2px** | **1.37×** |

## Validation

- **PASS** TypeScript + Vite production build (102 modules), using the existing ad-hoc-signed Node executable from GPT-40. Refreshed `web/dist/` and TypeScript build metadata; no dependency or lockfile changes.
- **PASS** orbit geometry: 18,000 phases, size targets, 16px card/centre gaps, containment and actual animation-hook lifecycle checks.
- **PASS** Python AST validation of `web/e2e/smoke.py` with warnings treated as errors.
- **PYTEST FAILURES:** **290 passed, 3 skipped, 7 failed** in 22.03s. All seven are `tests/test_map_backgrounds.py::test_darkroom_synthetic_image[<map>]` at line 22. That existing test expects mean brightness below 85 (and subsequently maximum brightness ≤120), whereas the existing `scripts/build_map_backgrounds.py:25` `darkroom()` now preserves natural colour using contrast 1.08 / brightness 0.88. The synthetic white-centre crop has mean **223.6667**. These backend tests and generator were not changed because this task permits edits only in `web/`. A separate existing joblib physical-core detection warning falls back to logical cores.
- **NOT RUN:** browser smoke/screenshots; the project's Python environment lacks `playwright`. CSS rendering, actual viewport fit, centre text wrapping and breadcrumb visibility still require the browser check below. No browser-pass claim.

Commands executed:

```sh
# From web/
caffeinate -i /private/tmp/gpt40-node node_modules/typescript/bin/tsc -b
caffeinate -i /private/tmp/gpt40-node node_modules/vite/bin/vite.js build
# From repository root
/private/tmp/gpt40-node web/e2e/orbit_geometry.mjs
caffeinate -i .venv/bin/python -B -m pytest -q -p no:cacheprovider
```

## Immediate follow-up

On the configured browser runner, serve the built site with its existing real data and run:

```sh
python3 -m http.server 4173 --directory web/dist
python3 web/e2e/smoke.py http://localhost:4173 --orbit-only --shots /tmp/gpt42-orbit
```

Review 1440×900 and 1280×800 moving/focused/reduced-motion/map-return screenshots, including long team names in the compact centre. Separately update the backend brightness-test expectations to match the already-adopted natural-colour asset policy; this requires scope beyond `web/`.
