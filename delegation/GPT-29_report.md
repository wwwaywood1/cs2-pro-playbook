# GPT-29 — Radial Tactical Hub

Implemented frontend changes in `web/`; no npm dependencies added.

## Changes

- `web/src/pages/TeamsHub.tsx`: replaced the team map grid on desktop with seven clockwise ellipse nodes: Dust II, Mirage, Ancient, Anubis, Inferno, Nuke, Cache. Cache is always dashed / “即将上线”; missing and zero-match maps show “暂无数据”. These placeholders remain focusable for the seven-node keyboard sequence but cannot navigate.
- Centre: existing team logo / `TeamShield`, team name, match total and seven-map caption; double dashed rings; hover/focus HUD with T/CT rates and the team's most-used recipe, using Chinese spot names. Team profiles and tactics load lazily through the existing request cache; older hover responses cannot overwrite the current preview. No preview fetch blocks navigation.
- `web/src/teams-hub.css`: responsive stage with maximum Rx 410 / Ry 215, clockwise positions starting at −90°, compact 156px cards, semantic focus colours, solid active rays with moving highlights, and reduced-motion support. At short desktop heights the centre becomes compact; below 900px the existing grid pattern is retained. Long recipe names stay in the DOM and truncate visually to keep the HUD inside the core.
- `web/src/pages/teamsHubRoute.ts`: local route transition hook observes HashRouter state, including browser Back/Forward. Team identity and selected map share named View Transition anchors into the map heading; the stage collapses/fades independently. Anchors animate for 320ms; map KPIs, insight and portrait cards unfold with 40ms stagger. Unsupported browsers retain the existing 320ms slide exit; reduced motion swaps immediately. Existing Escape handling and focus restoration return to the opened node.
- Results disclosure remains immediately below the orbit in normal flow, with the match-time filter inside. Player entrance implementation and verse were left unchanged.
- `web/e2e/smoke.py`: added seven-node/order, inert Cache/empty maps, hover preview, arrow/Tab/Enter, Escape focus/highlight, Back/Forward, reduced motion, API fallback, stage containment at 1440×900 and 1280×800, and drawer checks. Existing console/page-error collection and 375px overflow checks remain. Added `--orbit-only` so the current exported data can be checked without replacing it with sample data.

## Verification

- `.venv/bin/python -m pytest -q`: **248 passed, 3 skipped**, one existing joblib CPU-count warning (17.12s).
- Production build: **passed**, TypeScript and Vite. `npm` is absent from this shell; executed the exact build-script steps using the installed Node runtime:

  ```sh
  cd web
  NODE_BIN=/Users/stephen/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node
  "$NODE_BIN" node_modules/typescript/bin/tsc -b
  "$NODE_BIN" node_modules/vite/bin/vite.js build
  ```

- `.venv/bin/python -m py_compile web/e2e/smoke.py`: **passed**.
- SHA-256 comparison of **10,159 files** under `playbook/`, `data/` and `web/public/data/`: **no changes**.
- Browser smoke: **blocked before assertions, not passed**. Used the existing Playwright installation from the sibling Codex checkout. Chromium launch fails with macOS `bootstrap_check_in … Permission denied (1100)` / `SIGTRAP`. Starting Vite also fails with `listen EPERM`; Chrome UI access is unavailable. Consequently visual layout, live shared transitions and absence of browser console errors still need a browser run. Logs: `/private/tmp/gpt29-orbit-smoke.log` and `/private/tmp/gpt29-smoke.log`.

## Immediate follow-up

In a terminal with browser/server access and the Python tooling from `web/e2e/requirements.txt`, run these in separate terminals from the repository root:

```sh
python3 -m http.server 4173 --directory web/dist
python3 web/e2e/smoke.py http://localhost:4173 --orbit-only --shots /tmp/gpt29-shots
```

This exercises current exported data without changing `playbook/`, `data/` or `web/public/data/`. Full smoke mode continues to expect the sample export documented at the top of the test file.
