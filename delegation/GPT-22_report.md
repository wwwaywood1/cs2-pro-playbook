# GPT-22 edge fixes

## 1. Ghost checkbox during player entrance

- Code-level cause: `usePlayerEntrance` in `web/src/pages/teamsHubMotion.ts` settled the entrance from window **capture** listeners. That schedules a render before React's delegated checkbox handler. A controlled checkbox has already undergone native click pre-activation at this point; a render with the old `checked` prop can restore its old value before React processes `onChange`. No entrance-dependent panel key or checkbox remount was found. Portrait-transfer capture listeners only remove a pointer-transparent image.
- Fix: listen for entrance-skipping `click` and `keydown` events in the **bubble** phase, after React handles the real control. No event cancellation or replacement activation is introduced. `PlayerView` keeps its existing local ghost state as the source of truth; URL re-reading was not restored.
- Coverage: `check_hub_entrance` in `web/e2e/smoke.py` now checks Space during a full entrance, retaining checkbox focus, checked state, settled entrance, and URL state. Its pointer case issues one physical click with `force=True` so actionability waits cannot simply wait out the entrance animation. Existing short-entrance and reduced-motion coverage remains.

## 2. Intermittent lineup callout expansion

- Cause: `Lineups` derived `clusterIds` exclusively from search parameters, while `web/src/main.tsx` enables `v7_startTransition` for `HashRouter`. The previous smoke check dispatched a click and immediately sampled `.radar-reset` with non-retrying `count()`, racing the navigation commit. Card selection/hover does not rebuild the cluster membership: `candidates` and `clusters` are memoized independently of selection, and cluster elements have stable keys. Synthetic dispatch also bypassed a separate real-pointer issue: route hit areas were painted after callout circles and could intercept a click over a callout.
- Fix: `web/src/pages/Lineups.tsx` applies landing picks and the primary selection locally and immediately, then mirrors them into the URL. The last observed URL landing value and map are tracked separately, preserving Back/Forward and map-change synchronization without undoing an urgent pick on an unrelated render. `web/src/components/Radar.tsx` paints callouts after routes so hover cannot put a route hit area above a callout.
- Coverage: `check_lineups` now performs a physical click on the callout circle, uses retrying expectations for the reset button and collapsed cluster layer, and waits for the shareable landing URL before reading it. It retains card filtering, throw positions, arrow keyboard selection, and Escape-reset checks. No arbitrary settling sleep or repeated click was added.

## Validation

- `.venv/bin/python -m pytest -q`: **196 passed, 1 skipped**, 16.34s after edits. One existing joblib physical-core detection warning.
- TypeScript check: **passed** using the installed VS Code Node runtime, since `node`/`npm` are absent from PATH:
  ```sh
  ELECTRON_RUN_AS_NODE=1 '/Applications/Visual Studio Code.app/Contents/MacOS/Code' web/node_modules/typescript/bin/tsc --project web/tsconfig.json --noEmit
  ```
  Electron emitted a macOS codesign diagnostic; the compiler exited successfully with no TypeScript errors.
- `web/e2e/smoke.py`: Python AST parsing passed.
- Browser was **not run**, as required. The event-order diagnosis and pointer-layer correction were reviewed from source; runtime confirmation remains `python web/e2e/smoke.py` in a browser-capable environment.
- No dependencies added; no edits to `playbook/`, data, or images. This checkout has no `.git` metadata; changes were compared against temporary copies of the four edited files.
