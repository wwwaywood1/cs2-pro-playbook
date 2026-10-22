# GPT-21 round 5 report

Completed in `/Users/stephen/Downloads/cs2-pro-playbook`, 2026-10-22. Implemented A → B → C → D in place, with the requested pytest run after each part and a final review pass. **Feature implementation: done. Browser/visual verification: partial because of environment restrictions.**

The requested brief was absent from the working tree. Restored `delegation/GPT-21_round5.md` and its three referenced review/copy inputs from the existing `delegation/_r5.tgz` before starting. Imported the supplied copy under `round5` in both locales. No npm dependencies added. Did not modify `playbook/`, exported data, images, `.github/`, or `delegation/design-skills/`. This directory has no `.git`; `delegation/GPT-21_changes.diff` records the source changes against the initial snapshot (27 source/test files).

## A. Bugs

| Item | Status | Implementation |
| --- | --- | --- |
| A1 Verse overlap | Done | `web/src/pages/TeamsHub.tsx:Verse` now renders one plain text node per vertical column. Removed the nested per-character inline boxes, character animation, and glint layer from `web/src/teams-hub.css`. The verse stays at opacity 0.28 with no animation, including after side/layer rerenders. Other player entrance effects remain. |
| A2 Replay clipping | Done | `web/src/components/RoundReplay.tsx:ReplayViewer` and `web/src/replay.css` use a square radar in the left column and events, controls, scrubber and WP in the right. Viewport height limits the square and sidebar; event history scrolls independently. Narrow-screen fallback stacks the columns. Added a 1440×900 WP containment regression to smoke.py; visual confirmation remains pending. |
| A3 Recipe desync | Done | Removed independent hover/focus preview state in `web/src/pages/Tactics.tsx`. The selected URL recipe supplies title, utility, site, routes and legend together. Radar state is keyed by map/side/recipe ID; hover cannot replace the expanded recipe. Added matching recipe IDs for regression checks. |
| A4 Player first screen | Done | Reserved 112px beneath the viewport-bounded player radar for captions/disclosure, kept the details title ahead of content, and moved large role stats below the named detail sections. Hover can open linked details without exposing a large stat as the next section's first content. Exact viewport appearance still requires browser QA. |
| A5 CT setup codes | Done | Added `web/src/labels.ts:ctSetupLabel`, using `round5.ct_setup_fmt` and combining M+C. Applied to hub summary/archive, tactics setup headings/rankings and setup tables. `A2 M1 B1 C1` renders `A 区 2 人 · 中路 2 人 · B 区 1 人`. |
| A6 Portrait callout | Done | `PlayerCards` sorts early T zone shares, passes the highest-share place through `calloutLabel`, then uses `round5.portrait_place`; KPR remains. No coarse lane fallback. The current NiKo export actually ranks `BackAlley` first at 0.324: the UI follows that callout instead of inventing a Top Mid result or showing the B lane. |
| A7 Route names | Done | Both SVG titles and the route legend use `round5.route_name`, the first non-spawn `via` callout and a single percent suffix. |

## B. Replay upgrade

| Item | Status | Implementation |
| --- | --- | --- |
| Countdown | Done | `web/src/replayMath.ts:roundClock` counts down from 1:55 after freeze end and switches to 0:40 on plant. Elapsed seconds remain as secondary text. Values clamp to zero and use tabular numerals. |
| Identity and deaths | Done | Four-character player abbreviations accompany living dots; full names remain on hover/focus/selection. Grey crosses persist at exported death coordinates, with a last-known-position fallback. |
| Kill line / feed | Done | Attacker-to-victim line fades over 1.5s. Right-column history includes attacker, weapon, translated headshot label and victim. Clicking history seeks and pauses. |
| Utility | Done | Smoke discs last 18s with countdown rings and radius `144 / map.radar.scale`; molotov areas last 7s with radius `120 / scale`. Flashes briefly pulse white. Missing scale uses a point glyph rather than an invented physical radius. |
| Event anchors | Done | Kill, smoke and plant anchors appear on scrubber and WP chart. Both support mouse and keyboard seeking. WP samples retain their original second indices. |
| Keyboard | Done | Space toggles playback; arrows seek ±3s; K jumps to the next kill; P jumps to plant. G uses the selected recipe's median commit time when available, otherwise the first T-on-CT kill. The recipe timestamp is explicitly identified as a median in the button tooltip: replay exports contain no per-round commit field. Missing destinations disable their buttons. |
| Lifecycle/accessibility | Done | Retained keyed round reset, RAF/listener cleanup, reduced-motion autoplay handling, URL replay state, native modal focus containment, scroll lock and opener restoration. No yaw/view cones were invented. |

## C. HUD system

| Item | Status | Implementation |
| --- | --- | --- |
| Shared segmented control | Done | `web/src/components/Segmented.tsx` provides one measured sliding highlight, inset track, ResizeObserver cleanup, arrow/Home/End access and reduced-motion support. Reused for T/CT, layers, phases, speeds, usage tiers, sites, floors and heatmap modes across hub/tactics/lineups/replay/heatmaps, plus archive tabs. Multi-select grenade filters retain their checkbox-like behavior. |
| Selected cards | Done | `web/src/hud.css` replaces the full green outline/left stripe with a thin top highlight and subtle radial glow; selectors override existing page-specific selection rules. |
| Radar frames | Done | Added actual radar wrappers with L corners and faint grid ticks, transparent SVG backgrounds and vignetted map imagery. Tactics frame dimensions follow its viewport-sized square. |
| Numeric typography | Done | Site-wide tabular numerals. Added shared `web/src/components/Num.tsx`, used by `CountUp`/primary stats and direct lineup/tactics/archive values, with numeric units at 60% size and reduced opacity. Accessible complete values remain intact. |

## D. Player workflows

| Item | Status | Implementation |
| --- | --- | --- |
| D1 Practice binds | Done | `web/src/practice.ts` builds numeric-only setpos/setang commands. Lineup buttons copy `bind "KP_ENTER" "setpos …;setang …"`. Recipe buttons use resolved most-used lineups in throw order and generate a namespaced alias cycle that wraps to the first throw. Missing lineups/coordinates disable generation. `PracticeCopy` provides feedback and a visible manual-copy fallback, with timer cleanup. Existing raw command copying remains available. |
| D2 Point-and-click | Done | Landing-cluster selection now filters the actual card list and exposes every remaining throw position. Clicking/Enter on a throw marker selects its card. Cluster membership and selected lineup are retained in URL `landing`/`id`; Escape and reset clear the cluster filter. The landing pick performs one URL update, avoiding competing selection/filter writes. |
| D3 Ctrl+K palette | Done | `web/src/components/CommandPalette.tsx` searches maps, teams, recipes/spot names, lineup from→to callouts and players. Per-map data loads on demand after a short debounce through existing cached data APIs. Search supports combined map/place/grenade text, including compact Chinese smoke terms. Arrows/Enter navigate; Escape closes and restores focus; native dialog contains focus. Player results without a hub roster navigate to a filtered player listing. No external dependencies. |
| D4 Ghost overlay | Done | `web/src/heatmap.ts:differenceRgba` compares the selected player's spatial distribution with baseline.json for the same side/phase/view, amber above and teal below. Exposure totals are normalized before comparison; all floors share one symmetric scale. Available in the hub player view and legacy heatmap workspace; checkbox state is URL-backed. Empty comparisons remain transparent. |

## Verification

Required command: `.venv/bin/python -m pytest -q`.

| Stage | Result | Log |
| --- | --- | --- |
| A | **196 passed, 1 skipped**, 21.32s | `delegation/GPT-21_pytest_A.log` |
| B | **196 passed, 1 skipped**, 18.05s | `delegation/GPT-21_pytest_B.log` |
| C | **196 passed, 1 skipped**, 15.76s | `delegation/GPT-21_pytest_C.log` |
| D | **196 passed, 1 skipped**, 17.08s | `delegation/GPT-21_pytest_D.log` |
| Final source review | **196 passed, 1 skipped**, 18.45s | `delegation/GPT-21_pytest_final.log` |

The same existing joblib physical-core-detection warning appears; it falls back to logical cores.

Additional checks:

- **PASS:** Installed TypeScript compiler, strict source options, **0 diagnostics**. Node/npm are absent, so `delegation/outputs/gpt21_typecheck.py` executes the installed TypeScript compiler through macOS JavaScriptCore with a filesystem-backed virtual compiler host. It checks all `web/src` TS/TSX files and their actual declarations; it is not an `npm run build` claim. Reproduce: `.venv/bin/python delegation/outputs/gpt21_typecheck.py`. Log: `delegation/GPT-21_typecheck.log`.
- **PASS:** Installed native esbuild production-mode bundle of `web/src/main.tsx`, including imports, TSX and CSS, with `--bundle --format=esm --jsx=automatic`, `import.meta.env.BASE_URL="/"`, `process.env.NODE_ENV="production"`. Temporary build outputs were removed.
- **PASS:** **22 runtime checks** against the real bundled helpers: freeze/plant clocks, timer clamping, utility durations/scales, player interpolation/death fallback, bind construction, ordered alias wrapping, incomplete data, ghost signs/exposure normalization/all-floor scale and CT setup formatting. Reproduce: `.venv/bin/python delegation/outputs/GPT-21_verify.py`. Log: `delegation/GPT-21_runtime.log`.
- **PASS:** `web/e2e/smoke.py` parses; both locales have 507 matching keys and matching placeholders; literal translation references resolve. Log: `delegation/GPT-21_static.log`.
- **Updated, not executed:** `web/e2e/smoke.py` now checks cluster filtering/reset and binds, recipe synchronization, 1440×900 WP containment, abbreviations/clock/killfeed/kill-line lifetime, event anchors and hotkeys, shared control keyboard/highlight behavior, stable verse, heading-before-stats, ghost toggle and palette navigation.

### Partial / skipped verification and next checks

- **Partial:** Browser/runtime layout QA. Python Playwright is unavailable. A localhost server attempt failed with `PermissionError: [Errno 1] Operation not permitted`; an isolated Chrome headless launch exited **134**. No screenshot, browser smoke or exact visual pass is claimed.
- **Skipped:** Standard `npm run build`/Vite build because Node/npm are not installed. Source type checking and esbuild bundling passed independently.
- **Not verified in-game:** CS2 console acceptance of the generated practice scripts; aliases and numeric command order were checked locally.

Next in an environment with Node and browser tooling: run `cd web && npm run build`, serve `web/dist`, then `.venv/bin/python web/e2e/smoke.py http://localhost:4173` from the repository root. Inspect NiKo at 1440×900 after hovering map markers and switching layers/sides, and verify the entire replay WP chart remains visible. No data regeneration is required for these frontend changes.
