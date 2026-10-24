# GPT-38 — Orbit v4 implementation report

Scope: frontend source and checks under `web/`, plus this report. No backend, exported data, npm dependencies, or owner image assets changed. The two artwork/particle subtasks were delegated as requested by the owner specification.

## Implemented items 1–6

1. **Particle team logo** — `web/src/components/ParticleLogoCanvas.tsx` and `particle-logo.css` sample each available `logos/teams/<slug>.png` through `assetUrl`. `teamPalette()` in `web/src/theme.ts` shares the existing primary/secondary palette. The logo is 168px with a blurred echo; the canvas caps core + dust particles at 2,000 and backing resolution at 2× DPR. Visibility/intersection observers suspend animation; reduced motion shows the original image. Missing/unreadable logos use `TeamShield`. The team name uses the requested 34px metallic gradient.
2. **Orbital engine** — `web/src/pages/OrbitalPhysicsEngine.ts` drives the cards, depth scale and both ray endpoints from one rAF loop, without per-frame React renders. Hover/focus brakes through time-normalised damping; leaving resumes. Hidden/offscreen stages pause. Existing arrow order, Enter navigation, View Transitions and Escape return focus remain. Reduced motion fixes the ring at its starting phase.
3. **Landmarks** — `web/src/components/MapLandmarkArt.tsx` and `map-landmark-art.css` provide seven original architectural SVG drawings with rear/foreground layers, details and map-coloured god rays. The 110px art sits beneath owner photos; decoded photos take precedence at 0.78 opacity without blur. Missing/bad photos retain the drawings. Cards have a themed 2px top strip.
4. **Rates** — `orbitRate()` in `web/src/pages/teamsHubOrbit.ts` now uses absolute thresholds: ≥60% `#22C55E` with glow, ≥50% `#F8FAFC`, otherwise `#F43F5E`. Relative best/worst badges still use the existing index minimum-sample rule. Available cards show an 80%-width orange T / blue CT bar with accessible exact rates; missing side data is marked and muted.
5. **Breadcrumb clipping** — `TeamsHub.tsx` now restores focus with `preventScroll` and resets scroll when revealing a team orbit. This removes the focus-driven scrolling path that can move breadcrumbs behind the sticky header. Breadcrumb scroll margins were also added. Screenshot reproduction/visual confirmation was blocked by this session's browser restrictions; direct-load and map-return checks are included in smoke at both target viewports.
6. **Smoke coverage** — `web/e2e/smoke.py --orbit-only` now includes seven moving phase samples at each target viewport, aligned rays, braking/resume, keyboard pause, static reduced motion, boundary rate colours (including low samples), T/CT bars, both supplied team PNGs, bounded canvas particles, hidden/offscreen pause, static/shield fallbacks, photo precedence/failure, and breadcrumb visibility after map return.

## Geometry and numeric-spec decisions

- Cards have the requested **168×216 CSS layout size**. A responsive orbit scale is applied before the ±5% depth and hover scale. A fixed full-size seven-card ellipse cannot remain collision-free throughout rotation inside the requested short viewports. `orbitLayout()` therefore fits the entire moving ellipse conservatively with a 16px gap, rather than allowing collisions or scrolling. This means rendered cards are smaller than 168×216 on desktop viewport budgets; representative stage fits are approximately 0.60× at 1144×570 and 0.71× at 1296×670. Browser aesthetic review remains necessary for this tradeoff.
- The engine follows the explicit `0.00025 rad/ms` value. That mathematically produces a roughly **25.1-second** revolution; the owner's parenthetical “about four minutes” is inconsistent with that numeric value.

## Validation

| Check | Result |
| --- | --- |
| `.venv/bin/python -m pytest -q` | **285 passed, 3 skipped**, 20.02s; one existing joblib physical-core detection warning |
| TypeScript + Vite production build | **Passed**, 97 modules; generated `web/dist` |
| `node web/e2e/orbit_geometry.mjs` | **Passed**: 8,640 phases across 24 viewport budgets, maximum depth + hover scale, 16px gaps and containment; ranking/totals and absolute threshold boundaries |
| Actual rAF hook with deterministic clock/DOM adapter, in `orbit_geometry.mjs` | **Passed**: rotation, damping, resume, hidden/offscreen pause, reduced motion, ray endpoints and cleanup |
| `.venv/bin/python -m py_compile web/e2e/smoke.py` | **Passed** |
| `.venv/bin/python web/e2e/smoke.py --orbit-only` | **Not executed successfully**: Python `playwright` is absent. Offline installation has no cached package. A launch attempt with available Node Playwright/Chromium failed with sandbox `MachPortRendezvousServer … Permission denied`; starting the local HTTP server also failed with `Operation not permitted`. No browser screenshots or browser-pass claim. |

`npm` is absent from PATH, so the package's exact build steps were run directly:

```sh
cd web
NODE=/Users/stephen/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node
"$NODE" node_modules/typescript/bin/tsc -b
"$NODE" node_modules/vite/bin/vite.js build
```

## Immediate follow-up

In an environment with Python Playwright and browser/server execution available, serve `web/dist` and run:

```sh
python web/e2e/smoke.py http://localhost:4173 --orbit-only --shots /tmp/gpt38-orbit
```

Review the 1440×900 / 1280×800 direct-load and map-return screenshots, especially responsive card readability and the enlarged central logo. Do not replace the current exported data with sample data for this run.


## Round 2

Continued the interrupted run on 2026-10-24 after inspecting the current frontend and the lead's smoke log. Source/test edits remain under `web/`; this requested report append is the only intentional edit outside it. No data export, dependency installation, backend change, or owner-asset edit was performed. This checkout has no `.git` directory, so a Git diff was unavailable.

### Findings and completed fixes

- **Card clipping:** retained the partial compact-card fix in `web/src/teams-hub.css`: landmark SVGs are explicitly absolute, rather than inheriting the generic card-child `position: relative` and consuming a grid row. Art/photos occupy the upper 40%; explicit rows reserve space for the name, 52px ring, side bar, rate label, match count, and compact low-sample chip. The available-card rows, gaps, padding and borders total 212px inside the 216px logical card. Badges remain absolute within the artwork. Smoke checks all data children for containment.
- **Logo clarity:** retained `ParticleLogoCanvas.tsx`'s edge-weighted sampling, 0.8–1.4px particles, primary-colour luminance variation (Spirit uses white), 0.65px ambient drift, reduced pointer displacement, and 20 faint dust particles. `particle-logo.css` leaves the real PNG visible at 25% beneath the particles. The smoke checks now cover installed Vitality, Falcons and Spirit logos.
- **Reduced-motion geometry:** found and corrected a remaining CSS cascade bug. The broad reduced-motion `:is(...)` reset inherited the specificity of `.hub-kpis .stat`, overriding the orbit's `translate: -50% -50%` with `none !important`. That displaced every card by half its unscaled dimensions while the rays retained their correct centres. The generic reset now excludes `.hub-orbit-node`; desktop static cards keep their fitted depth scale and centering, and mobile keeps its grid placement. The engine already measures and repaints on both stage/node ResizeObserver deliveries and window resize, including while static.
- **Phase-0 failure:** retained the partial smoke fix that installs Playwright's clock **before reloading/mounting** the engine. Installing it over an already scheduled native rAF can orphan the first callback. The engine still pauses hidden/offscreen stages and brakes on hover/focus. The moving-card hover test now bypasses Playwright's pre-hover stability wait, then verifies the actual braking and resume behavior.
- **Canvas expected `none`, actual `block`:** the former reduced-motion selector depended on `.is-animated`, but reduced motion switches the component to `.is-static`. The partial fix targets `.particle-logo .particle-logo-canvas` regardless of animation state. Added missing-PNG/TeamShield coverage for this condition.
- **Regression coverage:** added static reduced-motion resizing in both directions between 1440×900 and 1280×800, explicit computed centering checks, and measured desktop stage widths to the exhaustive geometry sweep.

The cards retain a **168×216 logical size** and the existing conservative whole-orbit fit. Their rendered dimensions remain smaller on these viewport budgets; this pass fixes internal clipping without claiming that seven full-size rectangles can rotate through every phase within the available stage. Browser review of readability and logo appearance remains outstanding.

### Build and test results

| Check | Round 2 result |
| --- | --- |
| `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider` | **297 passed, 3 skipped**, 22.76s; one joblib physical-core detection warning |
| TypeScript `tsc -b` + Vite production build | **Passed**, 97 modules, Vite build 1.75s; rebuilt `web/dist` from the existing public assets/data |
| `node web/e2e/orbit_geometry.mjs` | **Passed: 10,800 phases across 30 stage budgets**, max depth + hover scale, 16px card gaps and containment, ranking/totals and absolute rate boundaries |
| Actual rAF hook deterministic adapter | **Passed:** rotation, braking, resume, hidden/offscreen pause, reduced-motion resize, ray endpoints, and cleanup |
| Python AST parsing of `web/e2e/smoke.py` | **Passed** |
| `.venv/bin/python web/e2e/smoke.py --orbit-only` | **Blocked:** Python Playwright is not installed (`ModuleNotFoundError`). No browser-pass claim. |
| Local HTTP server / available Node Playwright browser | **Blocked:** binding localhost returns `PermissionError: [Errno 1] Operation not permitted`; the installed Chromium headless shell fails at `MachPortRendezvousServer` with `Permission denied (1100)`. |

The exact production build commands were:

```sh
cd web
NODE=/Users/stephen/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node
"$NODE" node_modules/typescript/bin/tsc -b
"$NODE" node_modules/vite/bin/vite.js build
```

Immediate follow-up on the Linux browser runner, with the current export served and Python Playwright available:

```sh
python web/e2e/smoke.py http://localhost:4173 --orbit-only --shots /tmp/gpt38-round2
```

Review card contents and Falcons/Vitality/Spirit silhouettes at both target viewports, including static resize and map-return breadcrumbs. Do not run the data export for this verification.
