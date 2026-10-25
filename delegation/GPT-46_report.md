# GPT-46 — frontend v4.1 resumed

Date: 2026-10-25. Resumed `delegation/GPT-46_frontend_v41.md` and retained the interrupted run's partial frontend work. All nine frontend items are implemented. Browser validation remains blocked by this session's sandbox; the backend export contract has one outstanding failure.

Implementation and generated-data changes are confined to `web/`. This explicitly requested report is the sole exception. No edits to `playbook/`, `tests/`, `data/site/`, or `site-preview/`. The checkout has no `.git`, so a reliable before/after Git diff is unavailable.

## Nine items

| Item | Result / files |
| --- | --- |
| 1. SHAP | `web/src/pages/AILab.tsx` uses `active_groups`; legacy data scans every example/state and hides globally zero groups. The exported inactive-group note appears below the bars in small text. Additivity still sums all contributions at full precision. |
| 2. Replay availability | Explicit `replay_available: false` disables scatter activation and keyboard selection, dims the point, and shows `无回放`. Older exports use the replay index. Removed the missing-export dead-end message from medoid selection. Disabled points use a disabled cursor. |
| 3. Counts | Model folds, matches, and state counts come from `model_accuracy`; orbit totals come from the displayed pool's JSON entries. Synced the current export into `web/public/data`; the built model card now receives **745 matches**, replacing the stale public export's 615. No source hardcoded match/round sample counts were found. |
| 4. CT statistics | `web/src/components/CTDefense.tsx` prefers `p_display` and formats tiny legacy p-values as `p < 0.0001`. Cramér's V renders to two decimals; legacy fallback derives it from the observed contingency table, and omits it when neither source is available. Pistol exclusion count appears when supplied, including zero. |
| 5. CT trajectories | Defaults to only five solid medoid paths and 10s/20s endpoint markers. `叠加簇均值轨迹` is unchecked initially and adds dashed mean paths. Sample paths are absent. `CTTrajectories.tsx` also splits floor changes without inventing endpoints at intermediate times; endpoint titles include actual timestamps. |
| 6. Empty orbit cards | `web/src/teams-hub.css` applies `grayscale(100%) brightness(.35)` to empty-map artwork/photos, including focus/hover; `暂无数据` remains. |
| 7. Transition | `web/src/pages/teamsHubRoute.ts` cross-fades the complete scene for 180ms, with an immediate destination shell and five portrait skeletons. No loading-dot overlay or separate title/logo transfer. Unsupported native transitions use an immediate commit plus 180ms opacity entrance; reduced motion commits instantly. Superseded native callbacks cannot restore stale routes. Portrait assets retain skeletons until load/error. |
| 8. Team-map basis | `web/src/components/TeamDetails.tsx` renders distinct team recipe counts and exported CT cluster counts; zero evidence counts are hidden. |
| 9. Orbit spacing | Desktop stage gets 28px recovered from space above it; vertical orbit margin reserves hover clearance. Card dimensions remain 196×252 before the existing fit. Tests compare the former fit and confirm unchanged fitted sizes, >=16px bottom clearance, and cover both desktop stage budgets. The recent-results toggle is in the introduction. |

## Validation

Commands below run from `/Users/stephen/Downloads/cs2-pro-playbook`. `node` was absent from PATH; the locally cached runtime was used directly:

```sh
NODE=/Users/stephen/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node
"$NODE" web/node_modules/typescript/bin/tsc -b web
"$NODE" web/node_modules/vite/bin/vite.js build web
"$NODE" web/e2e/orbit_geometry.mjs
"$NODE" web/e2e/lab_render.mjs
"$NODE" web/e2e/hub_route.mjs
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider --basetemp=web/.gpt46-pytest
```

- **TypeScript and production build: PASS.** The first two commands execute the same build steps as `web/package.json`'s build script. Latest assets: `index-BOHdBzFq.css`, `index-EwWSXUcb.js`. See `web/gpt46-build.log` and `web/gpt46-typescript.log`.
- **Orbit geometry: PASS.** 25,200 phases; full hero exclusion, unchanged fitted card sizes, bottom clearance including hover, actual rAF engine rotation/damping/resume, hidden/offscreen pause, reduced-motion resize, aligned rays, cleanup. Middle-depth card sizes: 145.9×187.6 at 1440×900; 109.6×140.9 at 1280×800. See `web/gpt46-orbit-geometry.log`.
- **Actual component static renders: PASS.** New and legacy SHAP metadata, activity in later examples, explicit replay false overriding the index, dynamic sample counts, exported and derived V, no fabricated V, five default paths/ten endpoint dots, floor-change endpoint correctness, real archive coverage, and absent zero-count basis. See `web/gpt46-lab-render.log`.
- **Actual route-hook lifecycle: PASS.** Native snapshot lifecycle, a single fade, rapid navigation, stale callback cancellation, immediate fallback with 180ms opacity frames, reduced-motion changes, and cleanup. See `web/gpt46-hub-route.log`. These deterministic checks do not measure browser paint timing.
- **Browser smoke updated for items 1–8, plus item 9 geometry.** Added a legacy-schema scenario, actual fade-duration capture (removes a vacuous empty-animation assertion), timestamp checks, slow-data shell checks, empty-photo styling, dynamic counts, and zero-basis coverage. Corrected an inherited assertion that still expected the old 170–180px logo / 261px hero instead of the current 206px logo / 230×285px hero. Python syntax and `--help` loading pass.
- **Browser execution: BLOCKED, not passed.** Restored Python Playwright from existing local wheel caches temporarily. Both `--lab-only` and `--orbit-only` fail before route assertions because Chromium's Mach-port `bootstrap_check_in` is denied (permission 1100). A local `http.server` also fails to bind with `PermissionError: [Errno 1] Operation not permitted`. No escalation was available. See `web/gpt46-smoke-lab.log`, `web/gpt46-smoke-orbit.log`, `web/gpt46-server.log`. Thus the <=200ms shell timing, pixel layout, and first-screen toggle are implemented and asserted in smoke but remain unmeasured here.
- **Pytest: 300 passed, 3 skipped, 1 failed.** `tests/test_ai_lab.py:311`, `test_exported_contract`, raises `KeyError: 'label_callouts_15_20s'` in `data/site/*/ct_patterns.json`. This is a backend export/test mismatch; it is outside the authorized frontend edit scope. See `web/gpt46-pytest.log`.
- `scripts/sync_web_data.py` completed without replacing source export data. The lab and all eight CT JSON files in `web/public/data` matched `data/site` after sync; `web/dist` was rebuilt from that snapshot. See `web/gpt46-data-sync.log`.

Temporary extracted tools and pytest temporary directories were removed after checking; validation logs remain under `web/`.

## Follow-up

1. GPT-45 should finish the `label_callouts_15_20s` export contract, re-export, and rerun pytest. Frontend renders exported labels directly.
2. After any further export changes, rerun `.venv/bin/python scripts/sync_web_data.py` and the production build.
3. In a CLI session permitting localhost and Chromium, serve `web/dist`, then run `web/e2e/smoke.py http://localhost:4173 --lab-only` and `--orbit-only` (optionally `--shots web/gpt46-shots`). Those runs are still required for browser-level sign-off.
