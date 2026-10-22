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

## Round 2 — desktop segmented-check visibility and diagnostics (2026-10-22)

Scope: `web/e2e/smoke.py` and this appended section only. No `web/src` changes. The entire `run_route`/`run_routes`/`main` suffix, including every 375px mobile check, is byte-for-byte unchanged from the round-2 baseline at `/private/tmp/gpt27-round2/smoke-before.py`.

### Diagnosis and track/state mapping

The old `check_segmented_layout` only excluded tracks with no client rects. Layout boxes are insufficient to establish visibility under collapsed `<details>`: their descendant buttons can have measurable boxes while the hidden Segmented highlight has not received its visible-layout measurement. This is a test-visibility artefact; there is no demonstrated visible UI defect warranting a source change. All six failed cases reach the hub, including `command_palette`, whose test navigates from tactics to a team.

Source inspection identifies the controls exposed to this false positive:

- Team slide (`hub_team`, final `command_palette` state): `segmented hud-segmented match-time-filter`, pressed **全部 / All**, under closed `.hub-team-results` (`web/src/pages/TeamsHub.tsx::TeamPanel`/`Results`).
- Map slide (`hub_map`, legacy `team`, `archive_replay`): `match-time-filter` (**全部 / All**) under `.hub-team-matches`; `tabs` (**T**) under `.hub-team-basis`; side (**T**), layer and phase tracks under `.hub-team-radar` (`web/src/components/TeamDetails.tsx`, `web/src/pages/TeamsHub.tsx::TeamMapView`/`MapControls`). Opening the match archive still leaves the basis/radar sections collapsed.
- `match_dates` opens the team results and then navigates to a map match archive; the other collapsed map sections remain mounted. Its mocked date rows do not change those visibility rules.

These are source-derived candidate mismatches, consistent with the lead's successful visible-track probe; this host could not collect the six routes' actual browser rectangles. The new runner explicitly prints the exact class, pressed label, closed ancestor/reason and signed x/y/width/height deltas for excluded hidden mismatches, so a subsequent run can confirm the offending tracks rather than infer them from a timeout.

### Check changes

- `SEGMENTED_LAYOUT` returns structured `mismatches`, `skipped`, and `labelMismatches`. Diagnostics include track index/class, pressed label, button/highlight rectangles, signed deltas and highlight animation state.
- Exclude non-summary content of **any** closed ancestor `<details>`, CSS/content-visibility-hidden tracks, and zero-size tracks. Summary controls remain eligible; an outer collapsed details still hides an inner summary. Opening a section makes its controls eligible immediately.
- Keep the **1.5px** tolerance on all four dimensions for rendered tracks, including offscreen and transformed tracks. A visible track with a missing highlight or zero-size selected button fails. Running/pending highlight transitions are polled until settled; they are never exempted.
- The wait returns either an aligned report or the final failing report after 9 seconds, inside the 10-second outer limit. A real mismatch is recorded with JSON diagnostics instead of the former generic timeout, and later route assertions can continue.
- Preserve nowrap/no-shrink/single-line/no-clipping label assertions, using the same rendered-track visibility policy.

### Validation and remaining runner check

- **PASS** `.venv/bin/python -m pytest -q`: **234 passed, 2 skipped, 1 warning**, 18.41s. Existing joblib physical-core fallback warning. Log: `/private/tmp/gpt27-round2/pytest.log`.
- **PASS** `.venv/bin/python -m py_compile web/e2e/smoke.py`.
- **PASS** execute the actual extracted `SEGMENTED_LAYOUT` JavaScript in Node against controlled DOM-interface fixtures: aligned rectangles; >1.5px failure in each dimension; diagnostic class/pressed/deltas; missing highlight; visible zero-size selection; closed/open/nested details and visible summaries; hidden/zero-size tracks; transformed alignment and misalignment; running/pending/finished highlight transitions; failing diagnostic return at the deadline. Harness: `/private/tmp/gpt27-round2/regression.cjs`. This checks predicate logic, not browser layout.
- **PASS** byte comparison confirms the mobile/shared runner suffix is unchanged.
- **BLOCKED locally** live Chromium: the installed headless shell exits at `bootstrap_check_in … MachPortRendezvousServer … Permission denied (1100)`. The native Chrome fallback is also unavailable to this session. No browser smoke pass or measured hidden-track deltas are claimed.

Next runner check: rerun `python3 web/e2e/smoke.py http://localhost:4173` against sample and real bundles, retaining the new `info … excluded non-rendered segmented mismatches` output. Confirm the six desktop timeouts disappear, opened archive controls pass, and any remaining visible mismatch produces its class/pressed/deltas. Mobile overflow failures and the real-data sample-specific win assertion remain outside this round's scope.
