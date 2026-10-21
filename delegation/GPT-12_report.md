# GPT-12 — frontend unification completion report

Completed 2026-10-21. Scope: `web/src` and this report only. No dependencies, Python files (including the smoke runner), data, images, `.github`, or design-skill files were changed in this pass. This directory has no Git metadata; the supplied `.gpt12-before/web/src` snapshot was used to identify the prior session's work.

## What was already done

The interrupted session had already changed or added 26 frontend files relative to the supplied snapshot. It was substantially implemented, rather than a set of missing component stubs:

- `theme.css` extracted the hub's palette, typography, surfaces, radii, shadows, easing and durations; `theme.ts` extracted the team palette table.
- `motion.ts`, `motion.css`, and `components/{Motion,CountUp,Page,RouteTransition}.tsx` supplied reduced-motion handling, route/stage motion, delegated pointer springs, reveal/stagger, tilt/specular, spotlight, parallax, digit reels and page/metric primitives.
- `components/{Layout,Stat}.tsx` wired navigation transitions and reusable animated statistics.
- `pages/{TeamsHub,teamsHubMotion}` used the shared motion, counters and palette while retaining the hub-specific portrait/intro choreography.
- Home had the seven-map radar deck and three entry points. Tactics had counters, recipe entrances, selected-card tilt and radar reveal. Lineups, Teams/Team, Players and both heatmap pages had shared headings, contexts, metric strips and entrances.
- The three existing page stylesheets plus `styles.css` had shared-theme overrides; both locale dictionaries had the new Chinese-first copy.

There were no unresolved component imports or TypeScript diagnostics at the beginning of this pass. The remaining problems were interaction, CSS ownership, accessibility and incomplete state styling.

## What this pass completed

### Shared system and routing

- `components/RouteTransition.tsx`: path changes now commit the destination outlet immediately, with the short CSS fade/slide entrance. Removed the delayed outgoing outlet: its `useSearchParams` effects could observe the new location and rewrite the destination query during the exit. Same-path query changes keep their existing tree, focus and filter state. Path changes still move focus to main content and reset scroll. Hub depth transitions retain their existing outgoing-stage choreography.
- `motion.ts`: removed the unused outer-route exit timing and added `motionScrollBehavior()`, which reads the current accessibility preference when scrolling.
- `components/{Motion,Page}.tsx`: `Stagger` supports semantic `dl` containers; key-number strips now enter in sequence without breaking their definition-list structure.
- `motion.css`: radar reveals use opacity/blur without transforming measured geometry. Increased the shared tilt selector's specificity so old card rules cannot override pointer-motion ownership.
- `theme.ts`: restored the hub's original blue secondary fallback for teams outside the curated palette table; pages without team context retain amber/gold/steel. Team and TeamHeatmap share that same table/fallback.

### Per-page finishing and shared styling

- **Home** (`styles.css`): removed the legacy map-card hover transform that overrode spring tilt; added shared section-heading spacing/type.
- **Lineups** (`pages/Lineups.tsx`): deep-link and radar-driven scrolling obey live reduced-motion preferences. Cards can be selected with Enter/Space while preserving nested copy-button behavior, refs and smoke selectors. Radar reveal now preserves geometry.
- **Tactics** (`pages/Tactics.tsx`): radar reveal now preserves the geometry used by viewport/DPR sizing. The existing one-screen bounds, floor controls, viewboxes and grenade glyphs were retained.
- **Team** (`pages/Team.tsx`): completed keyboard tab behavior (arrows/Home/End and roving tab stops) and economy-panel entrance.
- **Team heatmap** (`pages/TeamHeatmap.tsx`): completed the themed header/back-button treatment for missing-team, empty-map and map-fetch-error states; radar reveal preserves geometry.
- **Teams, Players and heatmap lists**: reviewed the existing shared surfaces, metric strips and staggered cards; retained their data/link behavior.
- `styles.css`: completed shared panel/control styling, 44px help-button width, usable inline link/check targets, team-card column sizing, section headings and result-count treatment.
- `heatmap.css`: removed route-specific shell overrides so heatmaps use the same navigation/footer layout; replaced legacy panel fallbacks with shared tokens and provided an explicit radar-background fallback outside a heatmap page.

Files edited **in this pass** (12): `web/src/theme.ts`, `web/src/motion.ts`, `web/src/motion.css`, `web/src/styles.css`, `web/src/heatmap.css`, `web/src/components/Motion.tsx`, `web/src/components/Page.tsx`, `web/src/components/RouteTransition.tsx`, `web/src/pages/Lineups.tsx`, `web/src/pages/Tactics.tsx`, `web/src/pages/Team.tsx`, `web/src/pages/TeamHeatmap.tsx`.

## Validation and remaining uncertainty

- No Node/npm, build, dependency installation or emitted JavaScript was used. The installed TypeScript 5.6 compiler API was run through macOS JavaScriptCore using the existing read-only command `python3 .gpt12-before/check_types.py`. Final result: `[]` (zero pre-emit diagnostics), including strict types, unused imports/parameters and module resolution under `web/tsconfig.json`.
- Static relative-import audit: zero unresolved TS/TSX/CSS/JSON paths. Both locale dictionaries have matching keys/placeholders and every literal TSX translation key resolves. All seven Home radar files and the lower Nuke radar exist.
- All six frontend stylesheets parse without errors using `tinycss2`. No merge-conflict markers were found.
- Existing smoke selector tokens remain present, including lineup/copy/filter selectors and hub count/intro/navigation selectors. `web/e2e/smoke.py` is byte-identical to the supplied snapshot. This is a static selector check, not an executed browser test.
- Browser rendering, exact hub visual parity, live WAAPI interruption, focus/scroll timing and actual contrast/layout have **not** been verified at runtime. Known-team palette values and hub-specific choreography were retained, but visual parity still needs browser confirmation.

When Node is available, run `cd web && npm run build`, serve the resulting site (for example `npm run preview -- --host 127.0.0.1`), then run the existing `python3 web/e2e/smoke.py http://127.0.0.1:4173` from the repository root using the environment with Playwright installed. Also inspect both heatmap routes and Tactics at 1280/1920px and 375px; exercise Back/Forward, deep links, keyboard selection, query-only filtering and a live reduced-motion toggle. The checked-in `web/dist` was not regenerated.
