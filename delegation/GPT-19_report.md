# GPT-19 round 4 report

All work was performed in `/Users/stephen/Downloads/cs2-pro-playbook`.

## 0. Pipeline and generated data — DONE

- Read `DESIGN.md` entry-route notes, `playbook/replay.py`, and the frontend data types before implementing the UI.
- `.venv/bin/python -m pytest -q`: **196 passed, 1 skipped**, 28.70 s. The existing joblib physical-core detection warning is non-fatal.
- `.venv/bin/python -m playbook export`: **passed**, exporting Ancient, Anubis, Dust II, Inferno, Mirage and Nuke. Win-probability accuracy 0.743, baseline 0.697, log loss 0.471, 289 matches.
- Copied the complete `data/site` tree to `web/public/data` using Python `shutil.copytree`, replacing the data directory. Deliberately did not invoke the radar-copying portion of `scripts/sync_web_data.py`; images were not changed.
- Verified all **2,733 JSON files** in the copy are byte-identical to their source. All **2,195 replay rounds** listed in the six active maps' replay indexes exist, match their map/demo/round keys, have ten players, and have consistent frame widths. All **297 recipe example rows** marked `replay: true` resolve through those indexes.
- Example: `data/site/de_ancient/replay/2394210_the-mongolz-vs-b8-m1-ancient/19.json` exists and is copied to `web/public/data`.
- Verified Falcons replay coverage: 14 Ancient, 10 Anubis, 27 Dust II, 10 Inferno, 15 Mirage and 9 Nuke match records have indexed replays.

## 1. Review fixes

1. **Hub team-on-map slide — DONE.** `TeamsHub.tsx` moves the former overview details into `TeamDetails.tsx`'s single details card. Three cards below the portraits expose match records with n/W/L, tempo/CT/recipe details, and the heatmap tool. Each collapsed card has a one-line preview. Existing statistics, insights, economy tables, signature radar and heatmap controls remain accessible inside the cards.
2. **Player grenade layer — DONE.** The utility layer uses grenade icons and `round4.util_legend` instead of the heat gradient. Pointer click or Enter/Space on a spot selects its most frequent lineup reference and draws the throw position, translated callout, and trajectory from `lineups.json` on the same radar. Individual lineup links remain in the detail list. Other layers retain the heat legend and place markers.
3. **Lineup radar clusters — DONE.** `Radar.tsx` counts filtered lineup records, sizes circles by that count, and repeatedly merges colliding bubbles using their radii plus spacing. Merged clusters expand their full membership. Count text is enlarged and high-contrast; labels use `round4.cluster_count`.
4. **Recipe spots — DONE.** `Tactics.tsx` and shared `SpotList` sort by `order`, with unknown orders last. Each spot shows its translated throw callout and a muted example thrower/team using the supplied copy. Hub signature spot references also carry that metadata. Historical recipe arrays and generated naming are unchanged.
5. **Home map cards — DONE.** The primary link covers the card and opens tactics, with a separate smaller lineup link. Cache has a disabled grey state and coming-soon badge, with no links. HUD map coverage counts maps with matches.
6. **Portrait preview — DONE.** Hover/focus reveals the T early main lane from the heatmap summary and the matching team's player KPR below the name. The line reserves space and truncates within the card.

## 2. 2D replay — DONE

- Added `web/src/components/RoundReplay.tsx` and `web/src/replay.css`, mounted once in `App.tsx`. `data.ts` supplies cached replay and optional replay-index loaders.
- Native modal dialog provides focus containment, focus restoration, close button and Escape handling. Closing a hub replay preserves the map slide. Browser Back closes a replay opened through either entry point; direct replay links close by removing the replay parameter.
- Radar shows ten amber T / blue CT player dots, names on hover/focus, interpolation between one-second samples, timed kill crosses with exact victim removal, fading grenade glyphs, and the plant.
- Title includes teams, round and winner. Controls include play/pause, 1×/2×/4× speeds, a scrubber and localized time. A T-probability line and playhead appear under the radar, with an empty-data state when probabilities are unavailable.
- Reduced-motion users start paused; a live preference change pauses playback. Explicit playback remains available.
- Recipe examples marked `replay: true` expose a replay button. Archive WP bars expose pointer/keyboard replay controls only for rounds listed in `replay/index.json`.
- Query state uses `replay=<demo_id>:<round>` while retaining existing map/team/recipe parameters.

## Copy and constraints — DONE

- Both locale dictionaries contain `round4` exactly matching `delegation/inputs/copy_round4.json`; new supplied copy remains Chinese in both, as allowed.
- No npm dependencies added. No changes to `.github`, `delegation/design-skills`, raw data or images.
- No Node/npm production build was attempted. This checkout has no `.git` metadata, so validation used explicit file/data checks rather than `git diff`.

## Validation and remaining checks

- **PASS:** Python tests and export above.
- **PASS:** native existing esbuild parses all **39 TS/TSX files**, resolves an in-memory frontend bundle with React/router externalized, and parses all four edited CSS files. No production build artifacts were written. These checks do not perform TypeScript semantic checking.
- **PASS:** `.venv/bin/python -m py_compile web/e2e/smoke.py` and supplied-copy/data integrity checks.
- **DONE:** Updated smoke expectations for collision-merged cluster counts, filtering, home links and three archive cards. Added response-fixture coverage for recipe and archive replay opening, reduced-motion startup, kill/plant scrubbing, speed selection, Back/Forward, Escape and the close button. Non-indexed rounds are checked as static bars.
- **SKIPPED: TypeScript semantic check, production build and browser execution.** Node/npm are unavailable as stated in the assignment; `.venv/bin/python web/e2e/smoke.py --help` fails at import with `ModuleNotFoundError: No module named 'playwright'`. Browser behavior and rendered desktop layout therefore remain unverified, rather than claimed as passing.
- **Next check in a provisioned environment:** follow the sample-data workflow documented at the top of `web/e2e/smoke.py`, run `npm run build`, then execute the Playwright smoke suite. Re-sync production data afterward; manually inspect Falcons' Mirage archive, grenade trajectories and replay at desktop size.
