# GPT-24 match dates report

Completed backend first, then frontend in `/Users/stephen/Downloads/cs2-pro-playbook`.

## Delivered

- Reused the existing `config/events.json` schedule and extracted `playbook.dedupe.demo_event_slug` for shared path identity. Added `playbook/dates.py` and the empty override registry `config/match_dates.csv` (`demo_id,date`).
- Rank distinct HLTV series IDs across each event's raw inventory and spread them evenly over its inclusive date range, rounded to the nearest day. Three distinct IDs are required. Alias spellings share a ranking. Sparse/no-ID series use the event start with `event` precision; unknown events stay null. Maps in one archive/series share their date. Manual dates apply to the entire series as `exact`; conflicting dates fail explicitly.
- Export date/precision/event into team match rows, complete hub archives, recipe examples and round replays. Sort matches/examples newest first; add per-map `min_date`/`max_date` and global `data_through` to `index.json`.
- Shared bilingual date labels and precision tooltips appear in both archives, recipe examples, replay titles and match search. Event-only dates display `YYYY-MM · Event`.
- Both archives have segmented 全部 / 近 3 个月 / 近 1 个月 filters using calendar months relative to `data_through`, including month-end/leap-year clamping. Unknown dates remain visible under 全部. Ctrl+K searches opponent, event and date, then opens/focuses the selected archive row. Footer shows 数据截至.
- Synced 2,733 generated JSON files to `web/public/data` and rebuilt `web/dist`. No dependencies added; no image source files, `.github`, or `delegation/design-skills/` edited.

## Precision counts

| Population | Demos | day (estimated) | event | exact | unknown |
| --- | ---: | ---: | ---: | ---: | ---: |
| Parsed input | 316 | 234 | 81 | 0 | 1 |
| After deduplication | 289 | 207 | 81 | 0 | 1 |
| Six active exported maps | 283 | 201 | 81 | 0 | 1 |

27 duplicate recordings were excluded. `data_through` is **2026-10-14**. It is the latest assigned date, including event-start fallbacks, rather than a verified last match timestamp. No manual overrides have been supplied.

Every identified event has a configured date range. The sole undated demo is `hltv-de_mirage-2394170`: its flat fixture path identifies no event. Its date and precision remain null; add a verified CSV override if needed.

## Validation

- `PATH="<existing bundled Node runtime>:$PATH" .venv/bin/python -m pytest -q`: **213 passed**, no skips, one existing joblib physical-core discovery warning (logical-core fallback). [Log](GPT-24_pytest.log).
- `.venv/bin/python -u -m playbook export`: **passed, exit 0**, six active maps. Existing warnings: joblib core discovery and ignored Inferno route callout `Boiler`. [Log](GPT-24_export.log).
- TypeScript `tsc -b web` and Vite `build web`: **passed** using the existing Node runtime at `/Users/stephen/Library/Application Support/Codex/artifact-sessions/runtime-generations/generation-bev1yC/runtime/bin/node`. Other available Node binaries hit an existing Rollup/macOS code-signing mismatch. [Build log](GPT-24_build.log).
- Indexed-output audit: **passed** for 566 team match rows, 566 hub rows, 297 recipe examples, 2,195 replays and all six map date ranges; metadata matches the canonical demo registry and lists are newest first. Counts exclude older unreferenced generated files already present in the output tree. [Audit](GPT-24_audit.json).
- Added nine date tests covering interpolation, raw-inventory stability, series/alias sharing, overrides/conflicts, unknown events, complete archive ordering and frontend calendar boundaries. Replay schema test now checks date metadata.
- `web/e2e/smoke.py` compiles and includes deterministic date/precision/filter/search/footer coverage that works with sample or full data. Browser smoke **not executed**: Chromium launch was denied by this sandbox (`bootstrap_check_in ... Permission denied (1100)`). Run it outside the sandbox with the repository's documented sample-data workflow to complete visual/interaction verification.

## Round 2

- Fixed the actual source of `Request is not JSON serializable` in `web/e2e/smoke.py:mock_json` / `check_match_dates`: Python Playwright invokes a two-argument handler with `(Route, Request)`, so `lambda request, payload=payload` replaced the captured fixture with a `Request`. JSON mocks now use a one-argument closure. The exception surfaced at `unroute`, but the handler signature caused it.
- All seven checks that install routes now register them **inside** `try` and call `page.unroute_all(behavior='ignoreErrors')` in `finally`, including on partial setup failure. Replay pending-response cleanup has its own nested `finally`, so it cannot prevent route removal.
- `run_routes` gives each desktop/mobile check a fresh page and closes it in `finally`. Unrouting alone does not clear `web/src/data.ts`'s promise cache or an open command-palette dialog; those states can otherwise contaminate later hash-route visits.
- Added `tests/test_smoke_routes.py`: 14 browser-free regression cases exercise the real check functions with Playwright-compatible one-/two-argument callback dispatch and interrupted registration/assertions. They verify serializable fixture payloads and route removal. A fifteenth case verifies page isolation after a recorded UI failure.

### Review of each supplied desktop failure

| Check | Finding / action |
| --- | --- |
| `match_dates` | Confirmed handler binding bug; fixed and covered by regression tests for all three distinct JSON payloads. |
| `command_palette` | Reviewed `web/src/components/CommandPalette.tsx`: map and lineup entries match `mirage`. Broken index mocking can prevent results, and an assertion leaves the modal open. Fixed mock binding and page isolation; no independently confirmed app defect. |
| `team` | Reviewed `web/src/App.tsx:TeamRedirect` and `web/src/pages/TeamsHub.tsx:MapPanel`: redirect uses replacement history; hub readiness depends on the mocked index/bundle. Fresh-page isolation removes inherited mock/cache state; no independently confirmed app defect. |
| `team_shields` | Reviewed `TeamsHub.tsx:Asset` and `web/src/components/TeamShield.tsx`: empty asset slots select the shared shield. Setup/removal protected; no independently confirmed app defect. |
| `radar6` | Reviewed `TeamsHub.tsx:PlayerView` and `web/src/components/PlayerRadar6.tsx`: selected side drives percentiles; missing CT lurk displays an em dash. Setup/removal protected; no independently confirmed app defect. |
| `players` | Reviewed `web/src/i18n.ts:setLang` and the header toggle: language updates and persists. A command-palette modal left by an earlier failure can intercept the click. Fresh pages prevent that cascade; no independently confirmed app defect. |

### Validation and remaining browser check

- `PATH="/Users/stephen/Library/Application Support/Codex/artifact-sessions/runtime-generations/generation-bev1yC/runtime/bin:$PATH" .venv/bin/python -m pytest -q`: **228 passed**, no skips, one existing joblib physical-core warning. [Log](GPT-24_round2_pytest.log).
- Existing bundled Node: `node web/node_modules/typescript/bin/tsc -b web`: **passed**. Vite sample build in `/private/tmp/gpt24-r2-a4usu1ml/web`: **passed**. Source, public assets and `samples/site` were staged in isolation; repository production data and `web/dist` were preserved. [Build log](GPT-24_round2_build.log).
- Attempted the final smoke script with the existing Playwright environment at `/Users/stephen/Documents/Codex/2026-10-19/cs2-pro-playbook-is-a-python/work/cs2-pro-playbook/.venv/bin/python`. Chromium fails before any check runs: macOS `bootstrap_check_in ... Permission denied (1100)`. A local HTTP server is also denied (`socket.bind: Operation not permitted`). [Smoke launch log](GPT-24_round2_smoke.log).
- The supplied `GPT-24_smoke_failures.txt` includes the six desktop failures only; it omits the six mobile failure details. Their cause cannot be established from this excerpt, and a passing browser run is **not claimed**. Next check: outside this sandbox, serve `/private/tmp/gpt24-r2-a4usu1ml/web/dist` on port 4173 and run that workspace's `web/e2e/smoke.py` with the existing Playwright Python. This reruns every desktop and 375px mobile check independently with sample data.
